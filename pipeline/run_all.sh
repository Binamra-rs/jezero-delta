#!/usr/bin/env bash
# Run the full, reproducible raster pipeline. Stops at the first failing step.
# Usage: JEZERO_DATA_DIR=/srv/jezero/data ./pipeline/run_all.sh
set -euo pipefail
cd "$(dirname "$0")"
for step in 01_inventory 02_crs_validation 03_reproject 04_derivatives 05_coverage 06_vertical 07_alignment 08_catalog; do
  echo "=== ${step} ==="
  python3 "${step}.py"
done
echo "Pipeline complete. Reports in \${JEZERO_DATA_DIR:-../data}/reports"
