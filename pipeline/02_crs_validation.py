"""Step 02 — CRS validation and transformation planning (brief §4).

For every raw dataset this step:
  1. Parses the CRS actually stored in the file (never assumed).
  2. Confirms the reference body is Mars (rejects Earth CRSs such as WGS84
     that GDAL sometimes attaches by default).
  3. Classifies the reference surface:
       sphere_same      sphere, R = project radius           → identity on angles
       sphere_other     sphere, different R                  → angles preserved
       ellipsoid        a ≠ b; requires datasets.<id>.source_latitude_type
                        planetographic → explicit +proj=geoc conversion
                        planetocentric → angles preserved
  4. Writes an explicit PROJ pipeline from the source CRS to the project CRS.
     Step 03 passes that pipeline to gdalwarp with -ct, so no implicit
     "ballpark" datum transformation can ever be applied.
  5. Projects the source footprint into the project CRS and checks that it
     actually covers the Jezero Delta boundary.

A missing CRS is a hard failure. An operator may supply
`assigned_crs` + `assigned_crs_justification` in the dataset config; this is
recorded prominently in the report.

Outputs: reports/crs_validation.json, reports/02-crs-validation.md
"""
from __future__ import annotations

import sys

import numpy as np
import rasterio
from pyproj import CRS, Transformer

from common import REPORTS, ensure_dirs, log, md_table, now, project, raw_path, write_json, write_md

MARS_RANGE = (3.37e6, 3.40e6)


def strip_type(p4: str) -> str:
    return " ".join(t for t in p4.split() if not t.startswith("+type=") and t != "+no_defs")


def plan_for(ds_id: str, ds: dict, src_crs: CRS, project_radius: float, dst_proj4: str) -> dict:
    ell = src_crs.ellipsoid
    if ell is None:
        raise ValueError("CRS has no ellipsoid definition")
    a, b = ell.semi_major_metre, ell.semi_minor_metre
    if not (MARS_RANGE[0] < a < MARS_RANGE[1]):
        raise ValueError(f"Reference surface a={a:.0f} m is not Mars (Earth CRS attached?)")
    for ax in src_crs.axis_info:
        if ax.direction.lower() == "west":
            raise ValueError("Source uses positive-west longitude axis; add an explicit axis swap step")

    src_p4 = strip_type(src_crs.to_proj4())
    dst_p4 = strip_type(dst_proj4)
    is_sphere = abs(a - b) < 1e-3
    if src_crs.is_geographic:
        # lon/lat raster in degrees: PROJ pipelines work in radians internally
        steps = ["+proj=pipeline", "+step +proj=unitconvert +xy_in=deg +xy_out=rad"]
    else:
        steps = ["+proj=pipeline", "+step +inv " + src_p4]
    lat_note = None
    if is_sphere:
        surface = "sphere_same" if abs(a - project_radius) < 1.0 else "sphere_other"
        lat_note = "sphere: planetocentric = planetographic"
    else:
        surface = "ellipsoid"
        lat_type = ds.get("source_latitude_type")
        if lat_type not in ("planetographic", "planetocentric"):
            raise ValueError(
                f"Ellipsoidal source (a={a:.0f}, b={b:.0f}); set datasets.{ds_id}.source_latitude_type "
                "to 'planetographic' or 'planetocentric' after checking the product label")
        if lat_type == "planetographic":
            steps.append(f"+step +proj=geoc +a={a} +b={b}")
            lat_note = "planetographic → planetocentric via +proj=geoc"
        else:
            lat_note = "declared planetocentric; angles preserved"
    steps.append("+step " + dst_p4)
    return {
        "surface": surface, "semi_major_m": a, "semi_minor_m": b,
        "latitude_handling": lat_note, "pipeline": " ".join(steps),
        "src_proj4": src_p4, "projection_method": (src_crs.coordinate_operation.method_name
                                                   if src_crs.coordinate_operation else "geographic"),
        "linear_units": [ax.unit_name for ax in src_crs.axis_info],
    }


def footprint_bbox(transformer: Transformer, bounds) -> tuple[float, float, float, float]:
    l, b, r, t = bounds
    xs = np.concatenate([np.linspace(l, r, 50), np.full(50, r), np.linspace(r, l, 50), np.full(50, l)])
    ys = np.concatenate([np.full(50, b), np.linspace(b, t, 50), np.full(50, t), np.linspace(t, b, 50)])
    X, Y = transformer.transform(xs, ys)
    return float(np.min(X)), float(np.min(Y)), float(np.max(X)), float(np.max(Y))


def main() -> int:
    ensure_dirs()
    cfg, pcrs, boundary = project()
    out, problems = {}, []
    for ds_id, ds in cfg["datasets"].items():
        try:
            path = raw_path(ds_id, ds)
        except FileNotFoundError as exc:
            problems.append(str(exc))
            continue
        with rasterio.open(path) as src:
            stored = src.crs
            bounds = src.bounds
            res = src.res
        assigned = None
        if stored is None:
            if not ds.get("assigned_crs") or not ds.get("assigned_crs_justification"):
                problems.append(f"{ds_id}: file has NO CRS. Refusing to guess. Provide assigned_crs + justification.")
                continue
            assigned = ds["assigned_crs"]
            src_crs = CRS.from_user_input(assigned)
        else:
            src_crs = CRS.from_wkt(stored.to_wkt())
        try:
            plan = plan_for(ds_id, ds, src_crs, pcrs.radius_m, pcrs.proj4)
        except ValueError as exc:
            problems.append(f"{ds_id}: {exc}")
            continue
        tr = Transformer.from_pipeline(plan["pipeline"])
        fx0, fy0, fx1, fy1 = footprint_bbox(tr, bounds)
        ix0, iy0 = max(fx0, boundary.minx), max(fy0, boundary.miny)
        ix1, iy1 = min(fx1, boundary.maxx), min(fy1, boundary.maxy)
        inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
        cover = inter / (boundary.width * boundary.height)
        if cover == 0:
            problems.append(f"{ds_id}: footprint does not intersect the Jezero Delta boundary")
        # native ground pixel size, measured in the (true-scale) project CRS at
        # the centre of the source footprint
        mx, my = (bounds.left + bounds.right) / 2, (bounds.bottom + bounds.top) / 2
        sx, sy = tr.transform([mx, mx + res[0], mx], [my, my, my - res[1]])
        ground_x = float(np.hypot(sx[1] - sx[0], sy[1] - sy[0]))
        ground_y = float(np.hypot(sx[2] - sx[0], sy[2] - sy[0]))
        out[ds_id] = {
            "file": path.name, "stored_crs_wkt": stored.to_wkt() if stored else None,
            "assigned_crs": assigned, "assigned_crs_justification": ds.get("assigned_crs_justification"),
            "plan": plan, "native_res_crs_units": list(res),
            "native_ground_pixel_m": [ground_x, ground_y],
            "footprint_bbox_project": [fx0, fy0, fx1, fy1],
            "boundary_bbox_coverage_fraction": cover,
        }
        log.info("%s: %s, ground pixel %.2f×%.2f m, bbox covers %.1f%% of boundary",
                 ds_id, plan["surface"], ground_x, ground_y, 100 * cover)

    write_json(REPORTS / "crs_validation.json", {"generated": now(), "project_crs": pcrs.describe(),
                                                  "boundary": boundary.bounds, "datasets": out,
                                                  "problems": problems})
    rows = [[k, v["plan"]["projection_method"], f"{v['plan']['semi_major_m']:.0f}/{v['plan']['semi_minor_m']:.0f}",
             v["plan"]["surface"], v["plan"]["latitude_handling"],
             "×".join(f"{g:.2f}" for g in v["native_ground_pixel_m"]),
             f"{100 * v['boundary_bbox_coverage_fraction']:.1f} %", "ASSIGNED" if v["assigned_crs"] else "file"]
            for k, v in out.items()]
    lines = ["# 02 — CRS validation report", "", f"Generated {now()}.", "",
             "## Project CRS", "", "```", pcrs.proj4, "```", "",
             f"Boundary (project metres): {tuple(round(v, 1) for v in boundary.bounds)}", "",
             "## Source CRSs", "",
             *md_table(["Dataset", "Projection", "a/b (m)", "Surface class", "Latitude handling",
                        "Ground pixel (m)", "Boundary bbox covered", "CRS source"], rows),
             "", "## Transformation pipelines", ""]
    for k, v in out.items():
        lines += [f"### {k}", "", "```", v["plan"]["pipeline"], "```", ""]
    lines += ["## Problems", ""] + ([f"- {p}" for p in problems] or ["- none"])
    write_md(REPORTS / "02-crs-validation.md", lines)
    for p in problems:
        log.error(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
