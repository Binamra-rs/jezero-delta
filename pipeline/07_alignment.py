"""Step 07 — horizontal alignment check (brief §4.4).

Measures the planimetric offset between co-registered products after
reprojection, using normalised FFT cross-correlation with sub-pixel parabolic
peak refinement on overlapping windows:

  * HiRISE hillshade (area-averaged to 20 m) vs CTX hillshade — same
    illumination parameters, so terrain features correlate directly.
  * Optional landmarks: `config/landmarks.yaml` (name, lon_e, lat) — the
    report lists each landmark's projected coordinates and the sampled value
    of every layer there for manual checking against the imagery.

Offsets are **reported, never applied**. Flag threshold: 0.5 CTX pixels (10 m).

Outputs: reports/alignment.json, reports/07-alignment.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio
import yaml
from rasterio.warp import Resampling, reproject

from common import PROCESSED, REPO, REPORTS, ensure_dirs, log, md_table, now, project, write_json, write_md


def xcorr_shift(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    """Shift (dy, dx) in pixels that best aligns b onto a, and peak correlation."""
    a = (a - a.mean()) / (a.std() + 1e-12)
    b = (b - b.mean()) / (b.std() + 1e-12)
    win = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    aw, bw = a * win, b * win
    fa, fb = np.fft.fft2(aw), np.fft.fft2(bw)
    norm = np.sqrt(np.sum(aw ** 2) * np.sum(bw ** 2)) + 1e-12
    c = np.fft.fftshift(np.real(np.fft.ifft2(fa * np.conj(fb)))) / norm
    py, px = np.unravel_index(np.argmax(c), c.shape)

    def refine(m1, m0, p1):
        den = m1 - 2 * m0 + p1
        return 0.0 if den == 0 else 0.5 * (m1 - p1) / den

    dy = py - a.shape[0] // 2 + (refine(c[py - 1, px], c[py, px], c[py + 1, px]) if 0 < py < c.shape[0] - 1 else 0)
    dx = px - a.shape[1] // 2 + (refine(c[py, px - 1], c[py, px], c[py, px + 1]) if 0 < px < c.shape[1] - 1 else 0)
    return float(dy), float(dx), float(c[py, px])


def main() -> int:
    ensure_dirs()
    _, crs, _ = project()
    results, landmarks_out = {}, []
    ctx_hs = PROCESSED / "hillshade_ctx.tif"
    with rasterio.open(ctx_hs) as c:
        prof = c.profile
        a_full = c.read(1).astype("f8")
        a_full[a_full == 0] = np.nan
        res = c.res[0]
    for short in ("hirise_1", "hirise_2"):
        p = PROCESSED / f"hillshade_{short}.tif"
        if not p.exists():
            continue
        b_full = np.zeros((prof["height"], prof["width"]), "f8")
        with rasterio.open(p) as h:
            src = h.read(1).astype("f8")
            src[src == 0] = np.nan
            reproject(src, b_full, src_transform=h.transform, src_crs=h.crs, dst_transform=prof["transform"],
                      dst_crs=prof["crs"], resampling=Resampling.average, src_nodata=np.nan, dst_nodata=np.nan)
        win, shifts = 128, []
        for r in range(0, prof["height"] - win, win // 2):
            for col in range(0, prof["width"] - win, win // 2):
                A = a_full[r:r + win, col:col + win]
                B = b_full[r:r + win, col:col + win]
                if np.isfinite(A).all() and np.isfinite(B).all() and B.std() > 1:
                    dy, dx, peak = xcorr_shift(A, B)
                    if peak > 0.3:
                        shifts.append((dy * res, dx * res, peak))
        if shifts:
            s = np.array(shifts)
            results[f"hillshade_{short} vs hillshade_ctx"] = {
                "windows": len(s), "median_dy_m": float(np.median(s[:, 0])), "median_dx_m": float(np.median(s[:, 1])),
                "std_dy_m": float(s[:, 0].std()), "std_dx_m": float(s[:, 1].std()),
                "flag": bool(np.hypot(np.median(s[:, 0]), np.median(s[:, 1])) > 0.5 * res)}
        else:
            results[f"hillshade_{short} vs hillshade_ctx"] = {"windows": 0, "note": "insufficient overlap"}

    lm_file = REPO / "config" / "landmarks.yaml"
    if lm_file.exists():
        for lm in yaml.safe_load(lm_file.read_text()) or []:
            x, y = crs.forward(float(lm["lon_e"]), float(lm["lat"]))
            row = {"name": lm["name"], "lon_e": lm["lon_e"], "lat": lm["lat"], "x": x, "y": y, "values": {}}
            for tif in sorted(Path(PROCESSED).glob("*.tif")):
                with rasterio.open(tif) as src:
                    v = next(src.sample([(x, y)], masked=True))
                    row["values"][tif.stem] = None if np.ma.is_masked(v[0]) else float(v[0])
            landmarks_out.append(row)

    write_json(REPORTS / "alignment.json", {"generated": now(), "xcorr": results, "landmarks": landmarks_out})
    rows = [[k, v.get("windows"), f"{v.get('median_dx_m', float('nan')):.2f}", f"{v.get('median_dy_m', float('nan')):.2f}",
             f"{v.get('std_dx_m', float('nan')):.2f}", f"{v.get('std_dy_m', float('nan')):.2f}",
             "INVESTIGATE" if v.get("flag") else "ok"] for k, v in results.items()]
    lines = ["# 07 — Horizontal alignment report", "", f"Generated {now()}.", "",
             "Positive dx/dy: the second product must move east/south to match CTX.", "",
             *md_table(["Pair", "Windows", "median dx (m)", "median dy (m)", "std dx", "std dy", "Result"], rows),
             "", "Offsets are reported only. **No shift has been applied to any dataset.**", ""]
    if landmarks_out:
        lines += ["## Landmarks", "", *md_table(["Name", "lon E", "lat", "x (m)", "y (m)"],
                  [[l["name"], l["lon_e"], l["lat"], f"{l['x']:.1f}", f"{l['y']:.1f}"] for l in landmarks_out])]
    write_md(REPORTS / "07-alignment.md", lines)
    log.info("alignment: %s", results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
