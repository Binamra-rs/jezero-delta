"""Step 05 — spatial coverage and overlap report (brief §2, §5 AC-06).

Valid-data footprints are traced from each processed COG's mask (read at a
reduced size; the footprint is simplified to that reading's pixel size, which
is stated in the report). Footprints are written as GeoJSON **in the project
CRS** (coordinates in metres; the file carries a `crs` member naming it) and
are served to the frontend to draw honest coverage outlines.

Outputs: processed/coverage/<layer>.geojson, reports/coverage.json, reports/05-coverage.md
"""
from __future__ import annotations

import itertools
import json
import sys

import rasterio
from rasterio.features import shapes
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

from common import PROCESSED, REPORTS, ensure_dirs, log, md_table, now, project, write_json, write_md

MAX_DIM = 3000


def footprint(path):
    with rasterio.open(path) as src:
        scale = max(1.0, max(src.width, src.height) / MAX_DIM)
        h, w = int(round(src.height / scale)), int(round(src.width / scale))
        mask = src.dataset_mask(out_shape=(h, w)) > 0
        tr = src.transform * src.transform.scale(src.width / w, src.height / h)
        polys = [shape(g) for g, v in shapes(mask.astype("u1"), mask=mask, transform=tr) if v == 1]
        px = abs(tr.a)
    geom = unary_union(polys) if polys else None
    if geom is not None:
        geom = geom.simplify(px, preserve_topology=True)
    return geom, px


def main() -> int:
    ensure_dirs()
    cfg, pcrs, boundary = project()
    bpoly = box(*boundary.bounds)
    (PROCESSED / "coverage").mkdir(exist_ok=True)
    out, geoms = {}, {}
    ids = list(cfg["datasets"]) + [l["id"] for l in cfg["layers"] if l.get("derived_from")]
    for lid in ids:
        p = PROCESSED / f"{lid}.tif"
        if not p.exists():
            log.warning("%s: no processed raster", lid)
            continue
        geom, px = footprint(p)
        if geom is None or geom.is_empty:
            out[lid] = {"area_km2": 0, "boundary_fraction": 0, "trace_px_m": px}
            continue
        geom = geom.intersection(bpoly)
        geoms[lid] = geom
        out[lid] = {"area_km2": geom.area / 1e6, "boundary_fraction": geom.area / bpoly.area,
                    "bbox": list(geom.bounds), "trace_px_m": px}
        fc = {"type": "FeatureCollection",
              "crs": {"type": "name", "properties": {"name": f"{pcrs.crs_id}@v{pcrs.version}", "proj4": pcrs.proj4}},
              "features": [{"type": "Feature", "properties": {"layer": lid, "trace_px_m": px}, "geometry": mapping(geom)}]}
        (PROCESSED / "coverage" / f"{lid}.geojson").write_text(json.dumps(fc))

    overlaps = []
    for a, b in itertools.combinations([d for d in cfg["datasets"] if d in geoms], 2):
        inter = geoms[a].intersection(geoms[b]).area
        overlaps.append({"a": a, "b": b, "overlap_km2": inter / 1e6,
                         "fraction_of_a": inter / geoms[a].area if geoms[a].area else 0,
                         "fraction_of_b": inter / geoms[b].area if geoms[b].area else 0})

    problems = [f"{d}: covers {100 * out[d]['boundary_fraction']:.1f}% of the boundary"
                for d in ("ctx_ortho", "ctx_dem") if d in out and out[d]["boundary_fraction"] < 0.99]
    missing = [d for d in cfg["datasets"] if d not in geoms]
    problems += [f"{d}: no valid data inside the boundary" for d in missing]
    write_json(REPORTS / "coverage.json", {"generated": now(), "boundary_area_km2": bpoly.area / 1e6,
                                           "layers": out, "overlaps": overlaps, "problems": problems})
    rows = [[k, f"{v['area_km2']:.2f}", f"{100 * v['boundary_fraction']:.1f} %", f"{v['trace_px_m']:.1f}"]
            for k, v in out.items()]
    orows = [[o["a"], o["b"], f"{o['overlap_km2']:.2f}", f"{100 * o['fraction_of_a']:.1f} %",
              f"{100 * o['fraction_of_b']:.1f} %"] for o in overlaps]
    lines = ["# 05 — Spatial coverage and overlap report", "", f"Generated {now()}.", "",
             f"Project boundary: {bpoly.area / 1e6:.2f} km² in `{pcrs.crs_id}`.", "",
             "## Valid-data coverage inside the boundary", "",
             *md_table(["Layer", "Area (km²)", "Of boundary", "Footprint traced at (m)"], rows), "",
             "## Pairwise overlap of authoritative datasets", "",
             *md_table(["A", "B", "Overlap (km²)", "% of A", "% of B"], orows), "",
             "HiRISE DTMs are shown and used only inside the footprints above; the application never "
             "implies ~1 m terrain outside them.", "", "## Problems", ""]
    lines += [f"- {p}" for p in problems] or ["- none"]
    write_md(REPORTS / "05-coverage.md", lines)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
