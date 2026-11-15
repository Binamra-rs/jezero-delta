"""Step 03 — reproject authoritative datasets into the project CRS as COGs (brief §4.2, §5).

Raw files are only ever opened read-only. For each dataset:

  gdalwarp  -s_srs <stored or assigned CRS> -t_srs <project CRS>
            -ct "<explicit PROJ pipeline from step 02>"
            -te <grid-aligned extent> -tr <res> <res> -r <method>
            -of VRT                                  (lazy)
  gdal_translate -of COG  (DEFLATE, predictor, 512 px blocks, overviews,
            provenance written as metadata items)

Target pixel size: the larger of the native ground pixel dimensions measured
in the project CRS (step 02), rounded UP to the millimetre — never finer than
the source, so no resolution is invented. Override per dataset with
`target_resolution_m` (must still be >= native).

Resampling (brief §4.2):
  imagery                         bilinear (or `resampling: cubic` in config)
  continuous, target/native ≤ 1.5 bilinear
  continuous, target/native > 1.5 average  (area-weighted downsampling)
  categorical                     nearest
Overviews: AVERAGE for continuous/imagery, NEAREST for categorical.

Every output pixel grid is aligned to the project boundary origin
(top-left), so origin + k·res holds exactly for every dataset.

Outputs: processed/<dataset>.tif, reports/reprojection.json, reports/03-reprojection.md
"""
from __future__ import annotations

import math
import sys

import numpy as np
import rasterio
from osgeo import gdal

from common import (REPORTS, WORK, ensure_dirs, log, md_table, now, project, processed_path,
                    raw_path, read_json, run, write_json, write_md)

F32_NODATA = float(np.finfo(np.float32).min)


def target_resolution(ds: dict, native: list[float]) -> float:
    native_max = max(native)
    auto = math.ceil(native_max * 1000.0) / 1000.0
    want = ds.get("target_resolution_m")
    if want is None:
        return auto
    if want < native_max * 0.999:
        raise ValueError(f"target_resolution_m {want} is finer than native {native_max:.3f} m (would invent resolution)")
    return float(want)


def aligned_extent(boundary, fp, res: float):
    """Intersection of footprint bbox and boundary, snapped outward onto the boundary-aligned grid."""
    x0, y0 = max(fp[0], boundary.minx), max(fp[1], boundary.miny)
    x1, y1 = min(fp[2], boundary.maxx), min(fp[3], boundary.maxy)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("footprint does not intersect boundary")
    c0 = math.floor((x0 - boundary.minx) / res)
    c1 = math.ceil((x1 - boundary.minx) / res)
    r0 = math.floor((boundary.maxy - y1) / res)
    r1 = math.ceil((boundary.maxy - y0) / res)
    # never extend past the boundary
    max_c = math.ceil(boundary.width / res)
    max_r = math.ceil(boundary.height / res)
    c0, r0, c1, r1 = max(c0, 0), max(r0, 0), min(c1, max_c), min(r1, max_r)
    minx = boundary.minx + c0 * res
    maxy = boundary.maxy - r0 * res
    return (minx, maxy - (r1 - r0) * res, minx + (c1 - c0) * res, maxy), (c1 - c0, r1 - r0)


def choose_resampling(ds: dict, res: float, native: list[float]) -> tuple[str, str]:
    kind = ds.get("kind", "continuous")
    if ds.get("resampling"):
        method = ds["resampling"]
    elif kind == "categorical":
        method = "near"
    elif ds.get("role") == "imagery":
        method = "bilinear"
    else:
        method = "average" if res / min(native) > 1.5 else "bilinear"
    ovr = "NEAREST" if kind == "categorical" else "AVERAGE"
    return method, ovr


def main(only: list[str] | None = None) -> int:
    ensure_dirs()
    cfg, pcrs, boundary = project()
    crsval = read_json(REPORTS / "crs_validation.json")
    if crsval.get("problems"):
        log.error("Step 02 reported problems; fix them before reprojecting")
        return 1
    records = {}
    for ds_id, ds in cfg["datasets"].items():
        if only and ds_id not in only:
            continue
        v = crsval["datasets"].get(ds_id)
        if v is None:
            log.error("%s missing from crs_validation.json", ds_id)
            return 1
        src = raw_path(ds_id, ds)
        native = v["native_ground_pixel_m"]
        res = target_resolution(ds, native)
        te, size = aligned_extent(boundary, v["footprint_bbox_project"], res)
        method, ovr = choose_resampling(ds, res, native)

        with rasterio.open(src) as s:
            src_nodata = s.nodata
            dtype = s.dtypes[0]
        if ds.get("nodata_override") is not None:
            src_nodata = ds["nodata_override"]

        is_imagery = ds.get("role") == "imagery"

        if is_imagery:
            gdal_types = {
                "uint8": "Byte",
                "uint16": "UInt16",
                "int16": "Int16",
                "uint32": "UInt32",
                "int32": "Int32",
                "float32": "Float32",
                "float64": "Float64",
            }
            out_type = gdal_types.get(dtype.lower())
    
            if out_type is None:
                raise ValueError(f"Unsupported imagery dtype for GDAL: {dtype}")
        else:
            out_type = "Float32"
    
        nod_args: list[str] = []
        if is_imagery:
            nod_args = ["-srcnodata", str(src_nodata), "-dstnodata", str(src_nodata)] if src_nodata is not None else ["-dstalpha"]
        else:
            if src_nodata is not None:
                nod_args += ["-srcnodata", repr(float(src_nodata))]
            nod_args += ["-dstnodata", repr(F32_NODATA)]

        s_srs = ["-s_srs", v["assigned_crs"]] if v.get("assigned_crs") else []
        vrt = WORK / f"{ds_id}.warp.vrt"
        warp_cmd = ["gdalwarp", "-overwrite", *s_srs, "-t_srs", pcrs.proj4, "-ct", v["plan"]["pipeline"],
                    "-te", *[repr(c) for c in te], "-ts", str(size[0]), str(size[1]),
                    "-r", method, *nod_args, "-ot", out_type, "-wo", "NUM_THREADS=ALL_CPUS",
                    "-of", "VRT", str(src), str(vrt)]
        run(warp_cmd)

        out = processed_path(ds_id)
        tmp = out.with_suffix(".tmp.tif")
        meta = {
            "JEZERO_DATASET": ds_id, "JEZERO_TITLE": ds["title"], "JEZERO_SOURCE": ds.get("source", ""),
            "JEZERO_DOI": ds.get("doi") or "", "JEZERO_PRODUCT_ID": ds.get("product_id") or "",
            "JEZERO_RAW_SHA256": read_json(REPORTS / "inventory.json")["datasets"][ds_id]["sha256"],
            "JEZERO_CRS_ID": f"{pcrs.crs_id}@v{pcrs.version}", "JEZERO_RESAMPLING": method,
            "JEZERO_NATIVE_GROUND_PIXEL_M": f"{native[0]:.4f}x{native[1]:.4f}",
            "JEZERO_UNITS": ds.get("units", ""), "JEZERO_CREATED": now(),
        }
        mo = [a for k, val in meta.items() for a in ("-mo", f"{k}={val}")]
        pred = "YES" if not is_imagery else "NO"
        tr_cmd = ["gdal_translate", "-of", "COG", "-co", "COMPRESS=DEFLATE", "-co", f"PREDICTOR={pred}",
                  "-co", "BLOCKSIZE=512", "-co", f"OVERVIEW_RESAMPLING={ovr}", "-co", "BIGTIFF=IF_SAFER",
                  "-co", "NUM_THREADS=ALL_CPUS", "-co", "SPARSE_OK=TRUE", *mo, str(vrt), str(tmp)]
        run(tr_cmd)
        tmp.replace(out)

        # verify the product
        with rasterio.open(out) as o:
            t = o.transform
            dx = (t.c - boundary.minx) / res
            dy = (boundary.maxy - t.f) / res
            aligned = abs(dx - round(dx)) < 1e-6 and abs(dy - round(dy)) < 1e-6
            crs_ok = o.crs is not None and abs(o.crs.to_dict().get("R", 0) - pcrs.radius_m) < 1e-3 \
                and abs(o.crs.to_dict().get("lon_0", -1) - pcrs.lon0_deg) < 1e-9
            valid = int(o.dataset_mask(out_shape=(min(o.height, 2048), min(o.width, 2048))).astype(bool).sum())
        if not (aligned and crs_ok):
            log.error("%s: output verification failed (aligned=%s crs_ok=%s)", ds_id, aligned, crs_ok)
            return 1
        records[ds_id] = {
            "source_file": src.name, "output": out.name, "source_crs": v["plan"]["src_proj4"],
            "destination_crs": pcrs.proj4, "pipeline": v["plan"]["pipeline"],
            "native_ground_pixel_m": native, "output_resolution_m": res, "resampling": method,
            "overview_resampling": ovr, "extent": te, "size_px": size, "output_dtype": out_type,
            "nodata": {"source": src_nodata, "output": None if is_imagery and src_nodata is None else
                       (src_nodata if is_imagery else F32_NODATA)},
            "grid_aligned_to_boundary": aligned, "crs_verified": crs_ok, "valid_sample_px": valid,
            "commands": [warp_cmd, tr_cmd], "gdal_version": gdal.__version__,
        }
        log.info("%s → %s at %.3f m (%s)", ds_id, out.name, res, method)

    prev = read_json(REPORTS / "reprojection.json")["datasets"] if (REPORTS / "reprojection.json").exists() else {}
    prev.update(records)
    write_json(REPORTS / "reprojection.json", {"generated": now(), "datasets": prev})
    rows = [[k, r["output_resolution_m"], "×".join(f"{n:.3f}" for n in r["native_ground_pixel_m"]),
             r["resampling"], r["overview_resampling"], f"{r['size_px'][0]}×{r['size_px'][1]}",
             ", ".join(f"{e:.1f}" for e in r["extent"]), "yes" if r["grid_aligned_to_boundary"] else "NO"]
            for k, r in prev.items()]
    lines = ["# 03 — Processing and reprojection report", "", f"Generated {now()} with GDAL {gdal.__version__}.", "",
             f"Destination CRS: `{pcrs.proj4}`", "",
             *md_table(["Dataset", "Output px (m)", "Native ground px (m)", "Resampling", "Overviews",
                        "Size", "Extent (minx, miny, maxx, maxy)", "Grid aligned"], rows), "",
             "Exact commands per dataset are recorded in `reports/reprojection.json`.",
             "Raw files were opened read-only; outputs carry provenance metadata (`gdalinfo` → JEZERO_*).", "",
             "Observed alignment errors are measured separately in `07-alignment.md`."]
    write_md(REPORTS / "03-reprojection.md", lines)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
