"""Step 04 — terrain derivatives: slope, hillshade, TRI (brief §6).

Computed once from the reprojected DEM COGs (never on request) with the
validated implementations in backend/jezero/terrain.py, block clear
 block with a
1-pixel halo (identical to whole-array results; see tests/test_terrain.py).

Independent check: slope is recomputed with `gdaldem slope -alg Horn` and the
two are compared on every valid pixel; the maximum difference is reported.

Outputs: processed/slope_<dem>.tif, hillshade_<dem>.tif, tri_<dem>.tif,
         reports/derivatives.json, reports/04-derivatives.md
"""
from __future__ import annotations

import sys

import numpy as np
import rasterio
from rasterio.windows import Window

from common import (PROCESSED, REPORTS, WORK, dem_dataset_ids, ensure_dirs, log, md_table, now, project,
                    run, write_json, write_md)
from jezero import terrain

F32_NODATA = float(np.finfo(np.float32).min)
BLOCK = 2048
SHORT = {"ctx_dem": "ctx", "hirise_dtm_1": "hirise_1", "hirise_dtm_2": "hirise_2"}


def to_cog(src_tif, dst, meta: dict, overview: str = "AVERAGE") -> list[str]:
    mo = [a for k, v in meta.items() for a in ("-mo", f"{k}={v}")]
    cmd = ["gdal_translate", "-of", "COG", "-co", "COMPRESS=DEFLATE", "-co", "BLOCKSIZE=512",
           "-co", f"OVERVIEW_RESAMPLING={overview}", "-co", "BIGTIFF=IF_SAFER", "-co", "SPARSE_OK=TRUE",
           *mo, str(src_tif), str(dst)]
    run(cmd)
    return cmd


def derive(dem_id: str, params: dict) -> dict:
    src_path = PROCESSED / f"{dem_id}.tif"
    short = SHORT.get(dem_id, dem_id)
    hs = params["hillshade"]
    outs = {k: WORK / f"{k}_{short}.tif" for k in ("slope", "hillshade", "tri")}
    with rasterio.open(src_path) as src:
        res_x, res_y = src.res
        prof = src.profile.copy()
        prof.update(driver="GTiff", tiled=True, blockxsize=512, blockysize=512, compress="deflate", count=1,
                    BIGTIFF="IF_SAFER")
        f_prof = {**prof, "dtype": "float32", "nodata": F32_NODATA}
        h_prof = {**prof, "dtype": "uint8", "nodata": 0}
        with rasterio.open(outs["slope"], "w", **f_prof) as d_s, \
             rasterio.open(outs["hillshade"], "w", **h_prof) as d_h, \
             rasterio.open(outs["tri"], "w", **f_prof) as d_t:
            for r0 in range(0, src.height, BLOCK):
                for c0 in range(0, src.width, BLOCK):
                    r1, c1 = min(r0 + BLOCK, src.height), min(c0 + BLOCK, src.width)
                    rr0, cc0 = max(r0 - 1, 0), max(c0 - 1, 0)
                    rr1, cc1 = min(r1 + 1, src.height), min(c1 + 1, src.width)
                    win = Window(cc0, rr0, cc1 - cc0, rr1 - rr0)
                    z = terrain.to_float_with_nan(src.read(1, window=win), src.nodata,
                                                  src.read_masks(1, window=win) > 0)
                    sl = r0 - rr0, c0 - cc0
                    crop = (slice(sl[0], sl[0] + r1 - r0), slice(sl[1], sl[1] + c1 - c0))
                    s = terrain.slope_degrees(z, res_x, res_y)[crop]
                    h = terrain.hillshade(z, res_x, res_y, hs["azimuth_deg"], hs["altitude_deg"], hs["z_factor"])[crop]
                    t = terrain.tri_riley(z)[crop]
                    out_win = Window(c0, r0, c1 - c0, r1 - r0)
                    d_s.write(np.where(np.isfinite(s), s, F32_NODATA).astype("f4"), 1, window=out_win)
                    # hillshade 1..255, 0 reserved for NoData
                    hv = np.where(np.isfinite(h), 1 + np.round(h * 254), 0).astype("u1")
                    d_h.write(hv, 1, window=out_win)
                    d_t.write(np.where(np.isfinite(t), t, F32_NODATA).astype("f4"), 1, window=out_win)

    base_meta = {"JEZERO_DERIVED_FROM": dem_id, "JEZERO_SOURCE_RESOLUTION_M": f"{res_x}",
                 "JEZERO_CREATED": now(), "JEZERO_NOTE": "Derived product - not a direct measurement"}
    cmds = {}
    cmds["slope"] = to_cog(outs["slope"], PROCESSED / f"slope_{short}.tif",
                           {**base_meta, "JEZERO_ALGORITHM": "Horn (1981) 3x3", "JEZERO_UNITS": "degrees"})
    cmds["hillshade"] = to_cog(outs["hillshade"], PROCESSED / f"hillshade_{short}.tif",
                               {**base_meta, "JEZERO_ALGORITHM": "Lambert n.L with Horn gradients",
                                "JEZERO_AZIMUTH_DEG": hs["azimuth_deg"], "JEZERO_ALTITUDE_DEG": hs["altitude_deg"],
                                "JEZERO_Z_FACTOR": hs["z_factor"], "JEZERO_UNITS": "1-255 (0=NoData)"})
    cmds["tri"] = to_cog(outs["tri"], PROCESSED / f"tri_{short}.tif",
                         {**base_meta, "JEZERO_ALGORITHM": "Riley et al. (1999) TRI", "JEZERO_UNITS": "m"})

    # independent cross-check against gdaldem
    gd = WORK / f"gdaldem_slope_{short}.tif"
    run(["gdaldem", "slope", "-alg", "Horn", "-of", "GTiff", str(src_path), str(gd)])
    max_diff, n = 0.0, 0
    with rasterio.open(PROCESSED / f"slope_{short}.tif") as a, rasterio.open(gd) as b:
        for _, w in a.block_windows(1):
            x = a.read(1, window=w).astype("f8")
            y = b.read(1, window=w).astype("f8")
            ok = (x != F32_NODATA) & np.isfinite(y) & (y != b.nodata) & (y >= 0)
            if ok.any():
                max_diff = max(max_diff, float(np.max(np.abs(x[ok] - y[ok]))))
                n += int(ok.sum())
    return {"input": src_path.name, "source_resolution_m": [res_x, res_y],
            "outputs": [f"slope_{short}.tif", f"hillshade_{short}.tif", f"tri_{short}.tif"],
            "params": params, "commands": cmds,
            "gdaldem_slope_check": {"pixels_compared": n, "max_abs_diff_deg": max_diff,
                                    "passed": max_diff < 2e-2}}


def main() -> int:
    ensure_dirs()
    cfg, _, _ = project()
    params = cfg["derivatives"]
    results = {}
    for dem_id in dem_dataset_ids(cfg):
        if not (PROCESSED / f"{dem_id}.tif").exists():
            log.error("%s not reprojected yet (run step 03)", dem_id)
            return 1
        log.info("Deriving terrain products from %s", dem_id)
        results[dem_id] = derive(dem_id, params)
    write_json(REPORTS / "derivatives.json", {"generated": now(), "derivatives": results})
    rows = [[k, "×".join(f"{v:.3f}" for v in r["source_resolution_m"]), ", ".join(r["outputs"]),
             f"{r['gdaldem_slope_check']['max_abs_diff_deg']:.2e}°",
             "pass" if r["gdaldem_slope_check"]["passed"] else "FAIL"] for k, r in results.items()]
    lines = ["# 04 — Terrain derivative report", "", f"Generated {now()}.", "",
             "Algorithms and parameters are specified in `docs/04-terrain-derivatives.md`.", "",
             *md_table(["Input DEM", "Resolution (m)", "Outputs", "Max |Δslope| vs gdaldem", "Check"], rows)]
    write_md(REPORTS / "04-derivatives.md", lines)
    return 0 if all(r["gdaldem_slope_check"]["passed"] for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
