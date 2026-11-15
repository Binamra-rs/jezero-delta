"""End-to-end API smoke test on synthetic rasters (no database needed).

Skipped automatically when rasterio/FastAPI are not installed. Builds a tiny
processed/ directory in the real project CRS and boundary, then exercises
config, tiles, inspection (incl. NoData), routing and input validation.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from affine import Affine  # noqa: E402

from jezero import terrain  # noqa: E402
from jezero.config import load_project_config  # noqa: E402
from jezero.crs import Boundary, MarsEquirectangular  # noqa: E402

F32 = float(np.finfo("float32").min)


def _write(path, arr, transform, crs_wkt, nodata, dtype="float32"):
    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1, dtype=dtype,
                       crs=crs_wkt, transform=transform, nodata=nodata, tiled=True, blockxsize=256,
                       blockysize=256) as dst:
        dst.write(arr.astype(dtype), 1)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    from fastapi.testclient import TestClient

    cfg = load_project_config()
    crs = MarsEquirectangular.from_config(cfg["crs"])
    b = Boundary.from_config(cfg["boundary"], crs)
    root = tmp_path_factory.mktemp("data")
    proc = root / "processed"
    proc.mkdir()
    res = 20.0
    w, h = int(round(b.width / res)), int(round(b.height / res))
    tr = Affine(res, 0, b.minx, 0, -res, b.maxy)
    rows, cols = np.mgrid[0:h, 0:w]
    z = -2500 + 80 * np.exp(-(((rows - h / 2) ** 2 + (cols - w / 2) ** 2) / (2 * 60.0 ** 2)))
    s = terrain.slope_degrees(z, res, res)
    hs = terrain.hillshade(z, res, res)
    tri = terrain.tri_riley(z)
    ti = np.full_like(z, 350.0)
    ti[:, : w // 2] = np.nan  # THEMIS missing on the west half → must report No Data
    wkt = crs.wkt2
    _write(proc / "ctx_dem.tif", z, tr, wkt, F32)
    _write(proc / "slope_ctx.tif", np.where(np.isfinite(s), s, F32), tr, wkt, F32)
    _write(proc / "tri_ctx.tif", np.where(np.isfinite(tri), tri, F32), tr, wkt, F32)
    _write(proc / "themis_ti.tif", np.where(np.isfinite(ti), ti, F32), tr, wkt, F32)
    _write(proc / "ctx_ortho.tif", np.clip(hs * 200 + 20, 1, 255), tr, wkt, 0, "uint8")

    def entry(lid, title, style, unit, kind, rng, src):
        return {"id": lid, "title": title, "style": style, "unit": unit, "file": f"{lid}.tif", "kind": kind,
                "source_dataset": src, "source_title": title, "resolution_m": res, "bounds": list(b.bounds),
                "range": rng, "default_visible": lid == "ctx_ortho", "default_opacity": 1.0}

    catalog = {"generated": "test", "crs": crs.describe(), "boundary": list(b.bounds), "layers": [
        entry("ctx_ortho", "CTX Orthomosaic", "gray", "DN", "authoritative", [1, 255], "ctx_ortho"),
        entry("ctx_dem", "CTX Elevation", "elevation", "m", "authoritative", [-2500, -2420], "ctx_dem"),
        entry("slope_ctx", "Slope (CTX)", "slope", "°", "derived", [0, 35], "ctx_dem"),
        entry("tri_ctx", "TRI (CTX)", "roughness", "m", "derived", [0, 5], "ctx_dem"),
        entry("themis_ti", "THEMIS TI", "thermal", "J", "authoritative", [100, 600], "themis_ti"),
    ]}
    (proc / "catalog.json").write_text(json.dumps(catalog))

    import os
    os.environ["JEZERO_DATA_DIR"] = str(root)
    os.environ["JEZERO_DB_PATH"] = str(root / "test.sqlite3")
    from jezero.config import get_settings
    get_settings.cache_clear()
    from jezero.api.main import app
    with TestClient(app) as c:
        c.meta = {"crs": crs, "b": b, "w": w, "h": h}
        yield c


def test_config(client):
    r = client.get("/api/v1/config")
    assert r.status_code == 200
    body = r.json()
    assert body["crs"]["proj4"].startswith("+proj=eqc")
    assert body["tilegrid"]["matrix_sizes"][0] == [1, 1]
    assert {l["id"] for l in body["layers"]} >= {"ctx_dem", "themis_ti"}


def test_tile_png_and_out_of_range(client):
    r = client.get("/api/v1/tiles/ctx_dem/0/0/0.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    etag = r.headers["etag"]
    assert client.get("/api/v1/tiles/ctx_dem/0/0/0.png", headers={"If-None-Match": etag}).status_code == 304
    assert client.get("/api/v1/tiles/ctx_dem/0/5/5.png").status_code == 404
    assert client.get("/api/v1/tiles/../../etc/passwd/0/0/0.png").status_code == 404
    assert client.get("/api/v1/tiles/not_a_layer/0/0/0.png").status_code == 404


def test_inspect_values_and_nodata(client):
    crs, b = client.meta["crs"], client.meta["b"]
    x_east, y = b.minx + 0.75 * b.width, b.miny + 0.5 * b.height
    r = client.get("/api/v1/inspect", params={"x": x_east, "y": y}).json()
    assert r["summary"]["thermal_inertia"]["value"] == pytest.approx(350.0)
    assert r["summary"]["elevation"]["in_coverage"] and r["summary"]["elevation"]["unit"] == "m"
    lon, lat = r["location"]["lon_e"], r["location"]["lat"]
    assert crs.forward(lon, lat) == pytest.approx((x_east, y))
    x_west = b.minx + 0.25 * b.width
    r = client.get("/api/v1/inspect", params={"x": x_west, "y": y}).json()
    assert r["summary"]["thermal_inertia"]["value"] is None
    assert r["summary"]["thermal_inertia"]["status"] == "no_data"


def test_inspect_rejects_outside_and_malformed(client):
    b = client.meta["b"]
    assert client.get("/api/v1/inspect", params={"x": b.maxx + 1000, "y": b.maxy}).status_code == 422
    assert client.get("/api/v1/inspect", params={"x": 1.0}).status_code == 422
    assert client.get("/api/v1/inspect", params={"lon_e": 77.4, "lat": 95}).status_code == 422


def test_route(client):
    b = client.meta["b"]
    cx, cy = 0.5 * (b.minx + b.maxx), b.miny + 0.5 * b.height
    span = min(10_000.0, b.width - 1000)  # a 10 km route fits the default cell budget
    body = {"start": {"x": cx - span / 2, "y": cy}, "end": {"x": cx + span / 2, "y": cy}, "profile": "balanced"}
    r = client.post("/api/v1/route", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["terrain"]["layer"] == "ctx_dem" and out["terrain"]["resolution_m"] == 20.0
    assert out["stats"]["distance_m"] >= span - 40
    assert "not a certified safe route" in out["label"].lower()
    outside = {**body, "end": {"x": b.maxx + 5000, "y": b.maxy}}
    assert client.post("/api/v1/route", json=outside).status_code == 422
    assert client.post("/api/v1/route", json={**body, "profile": "nope"}).status_code == 422


def test_waypoints_require_workspace_key(client):
    assert client.get("/api/v1/waypoints").status_code == 400
    assert client.get("/api/v1/waypoints", headers={"X-Workspace-Key": "short"}).status_code == 400
    assert client.post("/api/v1/waypoints", json={}).status_code in (400, 422)


def test_waypoint_crud_and_workspace_isolation(client):
    b = client.meta["b"]
    me = {"X-Workspace-Key": "A" * 43}
    other = {"X-Workspace-Key": "B" * 43}
    assert client.get("/api/v1/waypoints", headers=me).json() == []

    p = {"x": b.minx + 0.4 * b.width, "y": b.miny + 0.6 * b.height}
    r = client.post("/api/v1/waypoints", headers=me, json={"name": "  Habitat ", "description": "base", "location": p})
    assert r.status_code == 201, r.text
    wp = r.json()
    assert wp["name"] == "Habitat" and wp["description"] == "base"
    assert abs(wp["x"] - p["x"]) < 1e-6 and 0 <= wp["lon_e"] < 360 and wp["crs_version"] == 1
    r2 = client.post("/api/v1/waypoints", headers=me, json={"name": "Rover", "location": {"lon_e": wp["lon_e"], "lat": wp["lat"]}})
    assert r2.status_code == 201, r2.text
    assert [w["name"] for w in client.get("/api/v1/waypoints", headers=me).json()] == ["Habitat", "Rover"]

    # another workspace sees nothing and cannot touch them
    assert client.get("/api/v1/waypoints", headers=other).json() == []
    assert client.get(f"/api/v1/waypoints/{wp['id']}", headers=other).status_code == 404
    assert client.patch(f"/api/v1/waypoints/{wp['id']}", headers=other, json={"name": "x"}).status_code == 404
    assert client.delete(f"/api/v1/waypoints/{wp['id']}", headers=other).status_code == 404

    q = {"x": b.minx + 0.5 * b.width, "y": b.miny + 0.5 * b.height}
    r = client.patch(f"/api/v1/waypoints/{wp['id']}", headers=me, json={"name": "Hab 2", "location": q})
    assert r.status_code == 200, r.text
    up = r.json()
    assert up["name"] == "Hab 2" and up["description"] == "base" and abs(up["y"] - q["y"]) < 1e-6
    assert up["updated_at"] >= wp["updated_at"] and up["created_at"] == wp["created_at"]
    assert client.patch(f"/api/v1/waypoints/{wp['id']}", headers=me, json={"name": "   "}).status_code == 422

    outside = {"name": "far", "location": {"x": b.maxx + 5000, "y": b.maxy}}
    assert client.post("/api/v1/waypoints", headers=me, json=outside).status_code == 422

    assert client.delete(f"/api/v1/waypoints/{wp['id']}", headers=me).status_code == 204
    assert client.get(f"/api/v1/waypoints/{wp['id']}", headers=me).status_code == 404
    assert client.delete(f"/api/v1/waypoints/{wp['id']}", headers=me).status_code == 404
    assert [w["name"] for w in client.get("/api/v1/waypoints", headers=me).json()] == ["Rover"]


def test_hillshade_layers_not_served(client):
    ids = {layer["id"] for layer in client.get("/api/v1/config").json()["layers"]}
    assert not any(i.startswith("hillshade") for i in ids)


def test_raw_image_validation(client):
    assert client.get("/api/v1/raw-images/cameras").json()["cameras"][0]["id"] == "mastcamz"
    assert client.get("/api/v1/raw-images", params={"sol_min": 10, "sol_max": 5}).status_code == 422
    assert client.get("/api/v1/raw-images", params={"camera": "../etc"}).status_code == 422
