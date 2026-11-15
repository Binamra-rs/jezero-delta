"""Shared helpers for the raster-processing pipeline.

Directory layout (all under $JEZERO_DATA_DIR, default <repo>/data):

    raw/         immutable original downloads (made read-only by step 01)
    processed/   COGs in the canonical project CRS + catalog.json
    reports/     machine-readable JSON + Markdown reports
    work/        scratch space, safe to delete

Every step is idempotent and never writes inside raw/.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from jezero.config import load_project_config  # noqa: E402
from jezero.crs import Boundary, MarsEquirectangular  # noqa: E402

DATA = Path(os.environ.get("JEZERO_DATA_DIR", REPO / "data"))
RAW, PROCESSED, REPORTS, WORK = DATA / "raw", DATA / "processed", DATA / "reports", DATA / "work"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pipeline")


def ensure_dirs() -> None:
    for d in (PROCESSED, REPORTS, WORK):
        d.mkdir(parents=True, exist_ok=True)


def project() -> tuple[dict, MarsEquirectangular, Boundary]:
    cfg = load_project_config()
    crs = MarsEquirectangular.from_config(cfg["crs"])
    return cfg, crs, Boundary.from_config(cfg["boundary"], crs)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path, chunk: int = 16 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str))
    tmp.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def run(cmd: list[str]) -> str:
    """Run a GDAL command, logging it exactly as executed (for the reports)."""
    log.info("$ %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr}")
    return proc.stdout


def raw_path(ds_id: str, ds: dict) -> Path:
    name = ds.get("raw_filename")
    if not name:
        raise FileNotFoundError(f"datasets.{ds_id}.raw_filename is not set in config/project.yaml")
    p = RAW / name
    if not p.exists():
        raise FileNotFoundError(f"Raw file for {ds_id} not found: {p}")
    return p


def processed_path(layer_or_ds: str) -> Path:
    return PROCESSED / f"{layer_or_ds}.tif"


def dem_dataset_ids(cfg: dict) -> list[str]:
    return [k for k, v in cfg["datasets"].items() if v.get("role") == "elevation"]


def md_table(header: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for r in rows:
        out.append("| " + " | ".join("" if v is None else str(v) for v in r) + " |")
    return out
