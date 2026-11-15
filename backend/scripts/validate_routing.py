"""Generate the A* validation report (brief §7.6, deliverable 10).

Runs A* and an independent SciPy Dijkstra on many synthetic grids for every
configured profile and writes a Markdown report. Re-run after any change to
the cost model:

    python scripts/validate_routing.py --out ../docs/results/astar-validation.md
    python scripts/validate_routing.py --dem /data/processed/ctx_dem.tif   # real DEM too
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import platform
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jezero import terrain  # noqa: E402
from jezero.config import load_project_config  # noqa: E402
from jezero.routing.astar import NoRouteError, astar  # noqa: E402
from jezero.routing.cost import CostProfile, build_edge_weights  # noqa: E402
from jezero.routing.reference import dijkstra_cost  # noqa: E402


def synthetic(seed: int, h: int, w: int, relief: float, nan_frac: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    z = gaussian_filter(rng.normal(size=(h, w)), 5)
    z = (z - z.min()) / (np.ptp(z) + 1e-12) * relief
    if nan_frac:
        holes = gaussian_filter(rng.normal(size=(h, w)), 4)
        z[holes > np.quantile(holes, 1 - nan_frac)] = np.nan
    return z


def run_case(z, res, profile, rng, pairs):
    s = terrain.slope_degrees(z, res, res)
    r = terrain.tri_riley(z)
    e = build_edge_weights(z, s, res, profile, rough=r)
    cells = np.argwhere(e.passable)
    rows = []
    for _ in range(pairs):
        if len(cells) < 2:
            break
        a, b = (tuple(int(v) for v in c) for c in cells[rng.choice(len(cells), 2, replace=False)])
        t0 = time.perf_counter()
        ref, _ = dijkstra_cost(e, a, b)
        t1 = time.perf_counter()
        try:
            got = astar(e, a, b)
            cost, exp = got.cost, got.expansions
        except NoRouteError:
            cost, exp = math.inf, 0
        t2 = time.perf_counter()
        ok = (math.isinf(ref) and math.isinf(cost)) or abs(ref - cost) <= 1e-9 * max(1.0, ref)
        rows.append((ok, ref, cost, exp, t2 - t1, t1 - t0))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[2] / "docs/results/astar-validation.md")
    ap.add_argument("--dem", type=Path, help="optional processed DEM COG to include a real-terrain case")
    ap.add_argument("--pairs", type=int, default=20)
    args = ap.parse_args()

    cfg = load_project_config()
    profiles = {n: CostProfile.from_config(n, p) for n, p in cfg["routing"]["profiles"].items()}
    rng = np.random.default_rng(2026)

    cases = [
        ("smooth 60×80, 150 m relief", synthetic(1, 60, 80, 150, 0.0)),
        ("rough 60×80, 300 m relief", synthetic(2, 60, 80, 300, 0.0)),
        ("60×80 with 10 % NoData", synthetic(3, 60, 80, 150, 0.10)),
        ("120×120 with 5 % NoData", synthetic(4, 120, 120, 250, 0.05)),
    ]
    if args.dem:
        import rasterio
        with rasterio.open(args.dem) as src:
            win = rasterio.windows.Window(0, 0, min(300, src.width), min(300, src.height))
            z = terrain.to_float_with_nan(src.read(1, window=win, masked=False), src.nodata)
            cases.append((f"real DEM {args.dem.name} 300×300 window", z))

    lines = [
        "# A* validation report", "",
        f"Generated {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')} "
        f"on Python {platform.python_version()} / NumPy {np.__version__}.", "",
        "A* (backend/jezero/routing/astar.py) is compared against SciPy's compiled Dijkstra "
        "(backend/jezero/routing/reference.py) on the **same directed edge weights**. "
        "A case passes when both report no route, or the costs agree to 1e-9 relative.", "",
        "| Terrain | Profile | Pairs | Passed | Unreachable | Mean A* expansions | Mean A* time | Mean Dijkstra time |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    total = failed = 0
    for name, z in cases:
        for pname, prof in profiles.items():
            rows = run_case(z, 20.0, prof, rng, args.pairs)
            n = len(rows); ok = sum(r[0] for r in rows); unreach = sum(math.isinf(r[1]) for r in rows)
            total += n; failed += n - ok
            exp = np.mean([r[3] for r in rows]) if rows else 0
            ta = np.mean([r[4] for r in rows]) * 1e3 if rows else 0
            td = np.mean([r[5] for r in rows]) * 1e3 if rows else 0
            lines.append(f"| {name} | {pname} | {n} | {ok} | {unreach} | {exp:.0f} | {ta:.1f} ms | {td:.1f} ms |")
    lines += ["", f"**Result: {total - failed}/{total} cases agree with Dijkstra.**", "",
              "Behavioural tests (detours around steep terrain, NoData handling, blocked cells, "
              "corner cutting, endpoints, boundary mask, directional costs) are in "
              "`backend/tests/test_routing.py`; run `pytest -q backend/tests`."]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
