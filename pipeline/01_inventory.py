"""Step 01 — dataset inventory, checksums and integrity (brief §2).

* Computes SHA-256 of every raw file and compares with data/raw/SHA256SUMS
  (created on first run; any later mismatch aborts the pipeline).
* Optionally compares with a publisher checksum (datasets.<id>.sha256).
* Decodes every block of every band to prove the file is readable.
* Records driver, size, dtype, CRS, transform, resolution, extent, NoData,
  units/tags and overviews.
* Makes raw files read-only.

Outputs: reports/inventory.json, reports/01-dataset-inventory.md, raw/SHA256SUMS
"""
from __future__ import annotations

import os
import stat
import sys

import rasterio

from common import RAW, REPORTS, ensure_dirs, log, md_table, now, project, raw_path, sha256, write_json, write_md


def describe(path) -> dict:
    with rasterio.open(path) as src:
        bad_blocks = 0
        for b in range(1, src.count + 1):
            for _, window in src.block_windows(b):
                try:
                    src.read(b, window=window)
                except Exception:  # noqa: BLE001 - any decode failure is a corruption signal
                    bad_blocks += 1
        crs = src.crs
        return {
            "driver": src.driver,
            "width": src.width,
            "height": src.height,
            "count": src.count,
            "dtypes": list(src.dtypes),
            "nodata": src.nodata,
            "mask_flags": [str(f) for f in src.mask_flag_enums[0]] if src.count else [],
            "crs_wkt": crs.to_wkt() if crs else None,
            "crs_proj4": crs.to_proj4() if crs else None,
            "transform": list(src.transform)[:6],
            "res": list(src.res),
            "bounds": list(src.bounds),
            "units": list(src.units) if any(src.units) else None,
            "scales": list(src.scales),
            "offsets": list(src.offsets),
            "descriptions": list(src.descriptions),
            "tags": src.tags(),
            "band1_tags": src.tags(1) if src.count else {},
            "overviews": src.overviews(1) if src.count else [],
            "unreadable_blocks": bad_blocks,
        }


def main() -> int:
    ensure_dirs()
    cfg, _, _ = project()
    sums_file = RAW / "SHA256SUMS"
    recorded = {}
    if sums_file.exists():
        for line in sums_file.read_text().splitlines():
            if line.strip():
                digest, name = line.split(None, 1)
                recorded[name.strip().lstrip("*")] = digest

    inventory, problems = {}, []
    for ds_id, ds in cfg["datasets"].items():
        try:
            path = raw_path(ds_id, ds)
        except FileNotFoundError as exc:
            problems.append(str(exc))
            continue
        log.info("Inventory %s (%s)", ds_id, path.name)
        digest = sha256(path)
        if path.name in recorded and recorded[path.name] != digest:
            problems.append(f"{ds_id}: SHA-256 changed since first inventory — raw file was modified or replaced")
        if ds.get("sha256") and ds["sha256"].lower() != digest:
            problems.append(f"{ds_id}: SHA-256 does not match the publisher checksum")
        recorded.setdefault(path.name, digest)
        meta = describe(path)
        if meta["unreadable_blocks"]:
            problems.append(f"{ds_id}: {meta['unreadable_blocks']} unreadable blocks (corrupt download?)")
        exp = ds.get("expected_resolution_m")
        res_note = None
        if exp and meta["crs_proj4"] and "+units=m" in (meta["crs_proj4"] or ""):
            ratio = max(meta["res"]) / exp
            if not 0.8 <= ratio <= 1.25:
                res_note = f"native pixel {meta['res']} m differs from expected {exp} m"
                problems.append(f"{ds_id}: {res_note} (reported, not an error)")
        if ds.get("nodata_override") is not None and meta["nodata"] != ds["nodata_override"]:
            log.warning("%s: header NoData=%s, project enforces documented NoData=%s",
                        ds_id, meta["nodata"], ds["nodata_override"])
        inventory[ds_id] = {
            "title": ds["title"], "source": ds.get("source"), "doi": ds.get("doi"),
            "product_id": ds.get("product_id"), "file": path.name,
            "size_bytes": path.stat().st_size, "sha256": digest,
            "download_date": ds.get("download_date"),
            "expected_resolution_m": exp, "resolution_note": res_note,
            "units_declared": ds.get("units"), "nodata_override": ds.get("nodata_override"),
            "metadata": meta,
        }
        # immutable raw data
        mode = path.stat().st_mode
        os.chmod(path, mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))

    sums_file_tmp = RAW / "SHA256SUMS.tmp"
    try:
        sums_file_tmp.write_text("".join(f"{d}  {n}\n" for n, d in sorted(recorded.items())))
        sums_file_tmp.replace(sums_file)
    except PermissionError:
        log.warning("raw/ is not writable; SHA256SUMS not updated")

    write_json(REPORTS / "inventory.json", {"generated": now(), "datasets": inventory, "problems": problems})
    rows = [[k, v["title"], v["file"], f"{v['size_bytes']/1e6:.1f} MB",
             "×".join(f"{r:.3f}" for r in v["metadata"]["res"]), v["metadata"]["dtypes"][0],
             v["metadata"]["nodata"], v["doi"] or v["product_id"], f"`{v['sha256'][:16]}…`"]
            for k, v in inventory.items()]
    lines = ["# 01 — Dataset inventory", "", f"Generated {now()}.", "",
             *md_table(["ID", "Title", "File", "Size", "Pixel (CRS units)", "Type", "NoData", "DOI / product", "SHA-256"], rows),
             "", "Full metadata (CRS WKT, transform, tags) is in `reports/inventory.json`; "
             "full checksums in `raw/SHA256SUMS`.", "", "## Problems", ""]
    lines += [f"- {p}" for p in problems] or ["- none"]
    write_md(REPORTS / "01-dataset-inventory.md", lines)
    fatal = [p for p in problems if "not found" in p or "SHA-256" in p or "unreadable" in p or "not set" in p]
    for p in problems:
        log.warning(p)
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
