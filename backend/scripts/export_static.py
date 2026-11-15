"""Export everything the map needs as static files, for free static hosting.

    cd backend
    python scripts/export_static.py                       # → ../frontend/public/map
    python scripts/export_static.py --layers ctx_ortho    # re-render one layer

Writes
  config.json                 the same document as GET /api/v1/config, plus a
                              per-layer `static_max_zoom`
  coverage/<layer>.geojson    coverage footprints
  tiles/<layer>/<z>/<x>/<y>.webp
  empty.webp                  served (by a host rewrite) for tiles that do not exist

Tiles are rendered by the API's own renderer (jezero.raster.tiles), so they are
pixel-identical to what the API would serve, then encoded as WebP. Each layer
is rendered only down to the first zoom level at least as fine as its native
pixel size; OpenLayers up-samples beyond that, exactly as it would have shown
the API's over-zoomed tiles. Tiles with no valid pixel are not written.

Numerical values never come from these images — inspect / route still go to
the API, which reads native pixels.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from PIL import Image  # noqa: E402
from fastapi import Response  # noqa: E402

from jezero.config import get_settings  # noqa: E402

DEFAULT_OUT = HERE.parents[1] / "frontend" / "public" / "map"

_st = None


def _state():
    global _st
    if _st is None:
        from jezero.api.state import build_state
        _st = build_state(get_settings())
    return _st


def static_max_zoom(grid, resolution_m: float) -> int:
    """First zoom whose pixel is at least as fine as the layer's native pixel."""
    return grid.zoom_for_resolution(resolution_m)


def tile_range(grid, z: int, bounds) -> tuple[range, range]:
    span = grid.tile_size * grid.resolutions[z]
    ox, oy = grid.origin
    cols, rows = grid.matrix_size(z)
    x0 = max(0, int((bounds[0] - ox) // span))
    x1 = min(cols - 1, int((bounds[2] - ox) // span))
    y0 = max(0, int((oy - bounds[3]) // span))
    y1 = min(rows - 1, int((oy - bounds[1]) // span))
    return range(x0, x1 + 1), range(y0, y1 + 1)


def _render_row(args) -> tuple[int, int]:
    """Render one row of tiles (one worker task). Returns (written, empty)."""
    lid, z, xs, y, out, quality, lossless = args
    from jezero.raster import tiles
    st = _state()
    layer = st.catalog.get(lid)
    written = empty = 0
    for x in xs:
        rgba = tiles.render_rgba(st.catalog, st.grid, layer, z, x, y)
        if rgba is None:
            empty += 1
            continue
        d = Path(out) / "tiles" / lid / str(z) / str(x)
        d.mkdir(parents=True, exist_ok=True)
        img = Image.fromarray(rgba, mode="RGBA")
        img.save(d / f"{y}.webp", format="WEBP", quality=quality, lossless=lossless, method=4, alpha_quality=100)
        written += 1
    return written, empty


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--layers", nargs="*", help="only these layer ids (default: all)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--quality", type=int, default=85, help="WebP quality (lossy)")
    ap.add_argument("--lossless", action="store_true", help="lossless WebP (≈3× larger)")
    ap.add_argument("--extra-zoom", type=int, default=0,
                    help="render this many zoom levels beyond the native one (default 0)")
    args = ap.parse_args()

    from jezero.api.routes_map import project_config
    st = _state()
    out: Path = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    cfg = project_config(Response(), st)
    for entry in cfg["layers"]:
        lyr = st.catalog.get(entry["id"])
        entry["static_max_zoom"] = min(st.grid.max_zoom, static_max_zoom(st.grid, lyr.resolution_m) + args.extra_zoom)
    cfg["static"] = {"tile_template": "tiles/{layer}/{z}/{x}/{y}.webp", "format": "webp",
                     "generated_from_catalog": st.catalog.version}

    # coverage footprints
    cov_dir = out / "coverage"
    cov_dir.mkdir(exist_ok=True)
    for entry in cfg["layers"]:
        p = st.catalog.coverage_path(entry["id"])
        if p is not None:
            shutil.copyfile(p, cov_dir / f"{entry['id']}.geojson")
            entry["coverage_geojson"] = f"coverage/{entry['id']}.geojson"
        else:
            entry["coverage_geojson"] = None

    Image.new("RGBA", (st.grid.tile_size,) * 2, (0, 0, 0, 0)).save(out / "empty.webp", format="WEBP", lossless=True)

    todo = [e for e in cfg["layers"] if not args.layers or e["id"] in args.layers]
    tasks = []
    for entry in todo:
        lid = entry["id"]
        if not st.catalog.get(lid).path.exists():
            print(f"!! {lid}: raster missing — skipped", file=sys.stderr)
            continue
        shutil.rmtree(out / "tiles" / lid, ignore_errors=True)
        lossless = args.lossless
        for z in range(entry["static_max_zoom"] + 1):
            xs, ys = tile_range(st.grid, z, st.catalog.get(lid).bounds)
            tasks += [(lid, z, list(xs), y, str(out), args.quality, lossless) for y in ys]

    t0 = time.time()
    written = empty = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, (w, e) in enumerate(pool.map(_render_row, tasks, chunksize=4), 1):
            written += w
            empty += e
            if i % 200 == 0 or i == len(tasks):
                print(f"  {i}/{len(tasks)} rows · {written} tiles written · {empty} empty · {time.time() - t0:.0f}s",
                      flush=True)

    (out / "config.json").write_text(json.dumps(cfg, separators=(",", ":")))
    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    nfiles = sum(1 for f in out.rglob("*") if f.is_file())
    print(f"Done: {written} tiles, {nfiles} files, {total / 1e6:.0f} MB in {out}")
    for entry in cfg["layers"]:
        print(f"  {entry['id']:<16} max zoom {entry['static_max_zoom']} "
              f"({st.grid.resolutions[entry['static_max_zoom']]:.2f} m/px; native {entry['resolution_m']:.2f} m)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
