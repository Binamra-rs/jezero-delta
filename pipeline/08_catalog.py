"""Step 08 — build processed/catalog.json, the backend's layer registry.

The backend serves ONLY rasters listed here (by id; no paths ever come from
clients). Each entry carries resolution, units, NoData, value statistics,
styling range, coverage footprint and provenance for the UI legend and the
point-inspection panel.
"""
from __future__ import annotations

import sys

import numpy as np
import rasterio

from common import PROCESSED, REPORTS, ensure_dirs, log, now, project, read_json, write_json


def stats_for(path) -> dict:
    with rasterio.open(path) as src:
        scale = max(1.0, max(src.width, src.height) / 2048)
        shape = (max(1, int(src.height / scale)), max(1, int(src.width / scale)))
        arr = src.read(1, out_shape=shape, masked=True).astype("f8")
        v = arr.compressed()
        v = v[np.isfinite(v)]
        info = {"res_m": [float(src.res[0]), float(src.res[1])], "dtype": src.dtypes[0], "nodata": src.nodata,
                "bounds": list(src.bounds), "width": src.width, "height": src.height,
                "overviews": src.overviews(1), "tags": src.tags()}
    if v.size:
        info["stats"] = {"min": float(v.min()), "max": float(v.max()), "mean": float(v.mean()),
                         "p02": float(np.percentile(v, 2)), "p98": float(np.percentile(v, 98))}
    return info


def main() -> int:
    ensure_dirs()
    cfg, pcrs, boundary = project()
    inv = read_json(REPORTS / "inventory.json")["datasets"]
    rep = read_json(REPORTS / "reprojection.json")["datasets"]
    cov = read_json(REPORTS / "coverage.json")["layers"] if (REPORTS / "coverage.json").exists() else {}
    layers = []
    for layer in cfg["layers"]:
        lid = layer["id"]
        path = PROCESSED / f"{lid}.tif"
        if not path.exists():
            log.warning("layer %s has no processed raster; omitted from catalog", lid)
            continue
        info = stats_for(path)
        src_ds = layer.get("dataset") or layer.get("derived_from")
        ds = cfg["datasets"][src_ds]
        st = info.get("stats", {})
        rng = layer.get("range") or ([st.get("p02"), st.get("p98")] if st else None)
        entry = {
            "id": lid, "title": layer["title"], "group": layer.get("group"), "style": layer["style"],
            "unit": layer.get("unit", ""), "file": path.name,
            "kind": "derived" if layer.get("derived_from") else "authoritative",
            "derivative": layer.get("derivative"), "source_dataset": src_ds,
            "source_title": ds["title"], "source": ds.get("source"), "doi": ds.get("doi"),
            "product_id": ds.get("product_id"), "raw_sha256": inv.get(src_ds, {}).get("sha256"),
            "native_ground_pixel_m": rep.get(src_ds, {}).get("native_ground_pixel_m"),
            "resolution_m": info["res_m"][0], "resampling": rep.get(src_ds, {}).get("resampling"),
            "dtype": info["dtype"], "nodata": info["nodata"], "bounds": info["bounds"],
            "width": info["width"], "height": info["height"], "stats": st, "range": rng,
            "default_visible": bool(layer.get("default_visible")), "default_opacity": layer.get("default_opacity", 1.0),
            "coverage": cov.get(lid), "coverage_geojson": f"coverage/{lid}.geojson"
            if (PROCESSED / "coverage" / f"{lid}.geojson").exists() else None,
        }
        layers.append(entry)
    write_json(PROCESSED / "catalog.json", {"generated": now(), "crs": pcrs.describe(),
                                             "boundary": list(boundary.bounds), "layers": layers})
    log.info("catalog: %d layers", len(layers))
    return 0


if __name__ == "__main__":
    sys.exit(main())
