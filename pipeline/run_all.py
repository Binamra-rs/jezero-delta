"""Cross-platform pipeline runner (Windows, macOS, Linux) — no Docker needed.

    conda activate jezero
    python pipeline/run_all.py              # all steps
    python pipeline/run_all.py --from 03    # resume from a step
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = ["01_inventory", "02_crs_validation", "03_reproject", "04_derivatives",
         "05_coverage", "06_vertical", "07_alignment", "08_catalog"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="01", help="first step number, e.g. 03")
    args = ap.parse_args()
    missing = [t for t in ("gdalwarp", "gdal_translate", "gdaldem") if shutil.which(t) is None]
    if missing:
        print(f"GDAL command-line tools not found: {', '.join(missing)}. "
              "Activate the conda environment (conda activate jezero).", file=sys.stderr)
        return 2
    for step in STEPS:
        if step[:2] < args.start:
            continue
        print(f"\n=== {step} ===", flush=True)
        rc = subprocess.call([sys.executable, str(HERE / f"{step}.py")], cwd=HERE)
        if rc != 0:
            print(f"\nStep {step} failed (exit {rc}). Fix the reported problem and re-run with --from {step[:2]}.",
                  file=sys.stderr)
            return rc
    print("\nPipeline complete. Reports are in data/reports/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
