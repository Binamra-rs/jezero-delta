"""Step 06 — vertical elevation compatibility (brief §2, §4.4).

Each HiRISE DTM is aggregated onto the exact CTX DEM grid by area averaging
(cells less than 90 % covered by valid HiRISE pixels are excluded) and
differenced against CTX: Δ = HiRISE − CTX. The two HiRISE DTMs are also
compared with each other on their common footprint.

Reported: count, mean, median, standard deviation, RMSE, NMAD, percentiles,
and a least-squares plane Δ = a + b·x + c·y to expose tilts. **No correction
is applied.** A systematic offset is flagged for investigation (e.g. vertical
datum / areoid differences, control) and recorded; correcting it requires a
documented decision in docs/02-crs.md.

Outputs: reports/vertical.json, reports/06-vertical.md, work/diff_<hirise>_ctx.tif
"""
from __future__ import annotations

import sys

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

from common import PROCESSED, REPORTS, WORK, ensure_dirs, log, md_table, now, project, write_json, write_md
from jezero import terrain

F32_NODATA = float(np.finfo(np.float32).min)


def onto_grid(src_path, dst_profile, valid_threshold=0.9):
    """Area-average src onto the destination grid; NaN where coverage < threshold."""
    h, w = dst_profile["height"], dst_profile["width"]
    with rasterio.open(src_path) as src:
        z = terrain.to_float_with_nan(src.read(1), src.nodata, src.read_masks(1) > 0)
        valid = np.isfinite(z).astype("f4")
        zf = np.where(np.isfinite(z), z, 0.0).astype("f8")
        out_sum = np.zeros((h, w), "f8")
        out_frac = np.zeros((h, w), "f4")
        kw = dict(src_transform=src.transform, src_crs=src.crs, dst_transform=dst_profile["transform"],
                  dst_crs=dst_profile["crs"], resampling=Resampling.average)
        reproject(zf * valid, out_sum, **kw)
        reproject(valid, out_frac, **kw)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = out_sum / out_frac
    mean[out_frac < valid_threshold] = np.nan
    return mean


def stats(d: np.ndarray, x: np.ndarray, y: np.ndarray) -> dict:
    ok = np.isfinite(d)
    v = d[ok]
    if v.size < 10:
        return {"n": int(v.size)}
    med = float(np.median(v))
    nmad = float(1.4826 * np.median(np.abs(v - med)))
    A = np.column_stack([np.ones(v.size), x[ok] - x[ok].mean(), y[ok] - y[ok].mean()])
    coef, *_ = np.linalg.lstsq(A, v, rcond=None)
    return {"n": int(v.size), "mean_m": float(v.mean()), "median_m": med, "std_m": float(v.std()),
            "rmse_m": float(np.sqrt(np.mean(v ** 2))), "nmad_m": nmad,
            "p01_m": float(np.percentile(v, 1)), "p05_m": float(np.percentile(v, 5)),
            "p95_m": float(np.percentile(v, 95)), "p99_m": float(np.percentile(v, 99)),
            "plane_offset_m": float(coef[0]), "plane_tilt_m_per_km_x": float(coef[1] * 1e3),
            "plane_tilt_m_per_km_y": float(coef[2] * 1e3),
            "systematic_offset_flag": bool(abs(med) > max(1.0, nmad))}


def main() -> int:
    ensure_dirs()
    _, _, _ = project()
    ctx = PROCESSED / "ctx_dem.tif"
    results = {}
    with rasterio.open(ctx) as c:
        prof = c.profile
        zc = terrain.to_float_with_nan(c.read(1), c.nodata, c.read_masks(1) > 0)
        rows, cols = np.mgrid[0:c.height, 0:c.width]
        xs = c.transform.c + (cols + 0.5) * c.transform.a
        ys = c.transform.f + (rows + 0.5) * c.transform.e
    hirise_on_ctx = {}
    for hid in ("hirise_dtm_1", "hirise_dtm_2"):
        p = PROCESSED / f"{hid}.tif"
        if not p.exists():
            log.warning("%s not processed", hid)
            continue
        zh = onto_grid(p, prof)
        hirise_on_ctx[hid] = zh
        d = zh - zc
        results[f"{hid} − ctx_dem"] = stats(d, xs, ys)
        with rasterio.open(WORK / f"diff_{hid}_ctx.tif", "w", **{**prof, "dtype": "float32",
                                                                  "nodata": F32_NODATA, "driver": "GTiff"}) as o:
            o.write(np.where(np.isfinite(d), d, F32_NODATA).astype("f4"), 1)
    if len(hirise_on_ctx) == 2:
        d = hirise_on_ctx["hirise_dtm_1"] - hirise_on_ctx["hirise_dtm_2"]
        results["hirise_dtm_1 − hirise_dtm_2 (at CTX 20 m)"] = stats(d, xs, ys)

    write_json(REPORTS / "vertical.json", {"generated": now(), "comparisons": results})
    keys = ["n", "mean_m", "median_m", "std_m", "rmse_m", "nmad_m", "p05_m", "p95_m",
            "plane_tilt_m_per_km_x", "plane_tilt_m_per_km_y", "systematic_offset_flag"]
    rows_md = [[k] + [(f"{v[x]:.2f}" if isinstance(v.get(x), float) else v.get(x)) for x in keys]
               for k, v in results.items()]
    lines = ["# 06 — Vertical elevation compatibility report", "", f"Generated {now()}.", "",
             "Δ computed on the CTX 20 m grid after area-averaging HiRISE (cells ≥ 90 % covered).", "",
             *md_table(["Comparison", "n", "mean", "median", "std", "RMSE", "NMAD", "p5", "p95",
                        "tilt x (m/km)", "tilt y (m/km)", "offset flag"], rows_md), "",
             "**No vertical correction has been applied.** A flagged offset must be investigated "
             "(vertical datum/areoid, control network, product version) before any correction is "
             "considered; any correction must be documented in docs/02-crs.md and applied only to "
             "derived products, never to raw files.",
             "", "Difference rasters for inspection: `work/diff_*_ctx.tif`."]
    write_md(REPORTS / "06-vertical.md", lines)
    return 0


if __name__ == "__main__":
    sys.exit(main())
