"""Pack the processed rasters the API needs into one tar file for a free API host.

    cd backend
    python scripts/make_api_bundle.py            # → ../dist/jezero-api-data.tar
    python scripts/make_api_bundle.py --full     # include every processed raster

Upload the tar somewhere public (e.g. as a GitHub Release asset — free, up to
2 GB per file) and give its URL to the API host as JEZERO_DATA_URL; the Render
Dockerfile downloads and unpacks it at build time.

The slim bundle (default) leaves out what the API does not need when tiles
are served statically:
  * hillshade_*.tif               not a map layer; only used for tiles
  * slope_hirise_*, tri_hirise_*  ~1 GB; their inspect values are recomputed
                                  from the HiRISE DTM (jezero.raster.sampler —
                                  same algorithm, identical values)
"""
from __future__ import annotations

import argparse
import json
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from jezero.config import get_settings  # noqa: E402

SLIM_EXCLUDE_PREFIXES = ("hillshade_", "slope_hirise_", "tri_hirise_")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=HERE.parents[1] / "dist" / "jezero-api-data.tar")
    ap.add_argument("--full", action="store_true", help="include every processed raster")
    args = ap.parse_args()

    processed = get_settings().processed_dir
    cat = json.loads((processed / "catalog.json").read_text())
    files = [processed / "catalog.json", *sorted((processed / "coverage").glob("*.geojson"))]
    for layer in cat["layers"]:
        f = processed / layer["file"]
        if not args.full and f.name.startswith(SLIM_EXCLUDE_PREFIXES):
            continue
        files.append(f)
        # derived layers recomputed on demand need their source DEM
    for layer in cat["layers"]:
        src = processed / f"{layer.get('source_dataset', '')}.tif"
        if layer.get("derivative") and src.exists() and src not in files:
            files.append(src)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.out, "w") as tar:
        for f in files:
            tar.add(f, arcname=f"processed/{f.relative_to(processed).as_posix()}")
            print(f"  + {f.relative_to(processed)}  ({f.stat().st_size / 1e6:.1f} MB)")
    print(f"Wrote {args.out} ({args.out.stat().st_size / 1e6:.0f} MB)")
    if args.out.stat().st_size > 2_000_000_000:
        print("!! Larger than 2 GB: GitHub Release assets are limited to 2 GB.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
