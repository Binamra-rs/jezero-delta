"""Proxy for NASA/JPL's public Mars 2020 (Perseverance) raw-image feed.

Upstream: https://mars.nasa.gov/rss/api/?feed=raw_images&category=mars2020&feedtype=json
(the feed behind https://mars.nasa.gov/mars2020/multimedia/raw-images/). It is
public and needs no API key, but it is undocumented, so:

  * every field is read defensively and normalised into a stable shape;
  * only https image URLs on *.nasa.gov are passed to the browser;
  * responses are cached in memory (default 10 min) to stay polite;
  * any upstream failure becomes a clear 502 for the client.

Why a backend proxy at all: the browser cannot rely on CORS from the feed,
and the API keeps one place to validate, cache and reshape the data.
Images themselves are loaded by the browser straight from mars.nasa.gov.
Credit for every image: NASA/JPL-Caltech (raw, unprocessed engineering data).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

# Camera groups → instrument identifiers used by the feed's `camera.instrument`.
CAMERA_GROUPS: dict[str, tuple[str, tuple[str, ...]]] = {
    "mastcamz": ("Mastcam-Z", ("MCZ_LEFT", "MCZ_RIGHT")),
    "navcam": ("Navigation cameras", ("NAVCAM_LEFT", "NAVCAM_RIGHT")),
    "hazcam_front": ("Front hazard cameras", ("FRONT_HAZCAM_LEFT_A", "FRONT_HAZCAM_LEFT_B",
                                              "FRONT_HAZCAM_RIGHT_A", "FRONT_HAZCAM_RIGHT_B")),
    "hazcam_rear": ("Rear hazard cameras", ("REAR_HAZCAM_LEFT", "REAR_HAZCAM_RIGHT")),
    "supercam": ("SuperCam RMI", ("SUPERCAM_RMI",)),
    "sherloc": ("SHERLOC WATSON / ACI", ("SHERLOC_WATSON", "SHERLOC_ACI")),
    "pixl": ("PIXL MCC", ("PIXL_MCC",)),
    "cachecam": ("CacheCam", ("CACHECAM",)),
    "skycam": ("SkyCam (MEDA)", ("SKYCAM",)),
}
INSTRUMENT_GROUP = {inst: g for g, (_, insts) in CAMERA_GROUPS.items() for inst in insts}

MAX_PER_PAGE = 50
MAX_SOL = 20000


class UpstreamError(RuntimeError):
    """The NASA feed could not be reached or returned something unusable."""


@dataclass(frozen=True)
class Query:
    page: int = 0
    per_page: int = 24
    sol_min: int | None = None
    sol_max: int | None = None
    camera: str | None = None        # key of CAMERA_GROUPS
    order: str = "desc"               # by sol
    full_frame_only: bool = True

    def validate(self) -> "Query":
        if not 0 <= self.page <= 10_000:
            raise ValueError("page out of range")
        if not 1 <= self.per_page <= MAX_PER_PAGE:
            raise ValueError(f"per_page must be 1..{MAX_PER_PAGE}")
        for v in (self.sol_min, self.sol_max):
            if v is not None and not 0 <= v <= MAX_SOL:
                raise ValueError("sol out of range")
        if self.sol_min is not None and self.sol_max is not None and self.sol_min > self.sol_max:
            raise ValueError("sol_min must be <= sol_max")
        if self.camera is not None and self.camera not in CAMERA_GROUPS:
            raise ValueError("unknown camera group")
        if self.order not in ("asc", "desc"):
            raise ValueError("order must be asc or desc")
        return self


def build_params(q: Query) -> dict[str, str]:
    p = {"feed": "raw_images", "category": "mars2020", "feedtype": "json", "ver": "1.2",
         "num": str(q.per_page), "page": str(q.page), "order": f"sol {q.order}"}
    if q.sol_min is not None:
        p["condition_2"] = f"{q.sol_min}:sol:gte"
    if q.sol_max is not None:
        p["condition_3"] = f"{q.sol_max}:sol:lte"
    if q.camera:
        p["search"] = "|".join(CAMERA_GROUPS[q.camera][1])
    if q.full_frame_only:
        p["extended"] = "sample_type::full,"
    return p


def safe_url(url: Any) -> str | None:
    if not isinstance(url, str):
        return None
    u = urlparse(url.strip())
    host = (u.hostname or "").lower()
    if u.scheme == "https" and (host == "nasa.gov" or host.endswith(".nasa.gov")):
        return url.strip()
    if u.scheme == "http" and (host == "mars.nasa.gov" or host.endswith(".nasa.gov")):
        return "https://" + url.strip()[len("http://"):]  # same host, force TLS
    return None


def _int(v: Any) -> int | None:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _float(v: Any) -> float | None:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def normalize(item: dict[str, Any]) -> dict[str, Any] | None:
    """Reshape one feed item; returns None if it has no usable image URL."""
    files = item.get("image_files") or {}
    small = safe_url(files.get("small"))
    medium = safe_url(files.get("medium"))
    large = safe_url(files.get("large"))
    full = safe_url(files.get("full_res"))
    thumb = small or medium or large or full
    if not thumb:
        return None
    cam = item.get("camera") or {}
    inst = str(cam.get("instrument") or "UNKNOWN")
    ext = item.get("extended") or {}
    return {
        "id": str(item.get("imageid") or ""),
        "sol": _int(item.get("sol")),
        "instrument": inst,
        "camera_group": INSTRUMENT_GROUP.get(inst),
        "camera_label": CAMERA_GROUPS[INSTRUMENT_GROUP[inst]][0] if inst in INSTRUMENT_GROUP else inst.replace("_", " ").title(),
        "filter_name": cam.get("filter_name"),
        "title": str(item.get("title") or ""),
        "caption": str(item.get("caption") or ""),
        "credit": str(item.get("credit") or "NASA/JPL-Caltech"),
        "date_taken_utc": item.get("date_taken_utc"),
        "date_taken_mars": item.get("date_taken_mars"),
        "date_received": item.get("date_received"),
        "site": _int(item.get("site")),
        "drive": _int(item.get("drive")),
        "sample_type": item.get("sample_type"),
        "mast_az_deg": _float(ext.get("mastAz")),
        "mast_el_deg": _float(ext.get("mastEl")),
        "dimension": ext.get("dimension"),
        "thumb": thumb,
        "medium": medium or large or full or thumb,
        "large": large or full or medium or thumb,
        "full_res": full,
        "link": safe_url(item.get("link")),
    }


def normalize_page(raw: dict[str, Any], q: Query) -> dict[str, Any]:
    if not isinstance(raw, dict) or not isinstance(raw.get("images"), list):
        raise UpstreamError("Unexpected response shape from the NASA raw-image feed")
    images = [n for n in (normalize(i) for i in raw["images"] if isinstance(i, dict)) if n]
    if q.full_frame_only:
        images = [i for i in images if (i["sample_type"] or "Full").lower() != "thumbnail"]
    total = _int(raw.get("total_results")) or _int(raw.get("total_images"))
    return {"page": q.page, "per_page": q.per_page, "total": total, "images": images}


class RawImageClient:
    def __init__(self, base_url: str, timeout: float = 20.0, cache_seconds: int = 600, max_entries: int = 512):
        self.base_url = base_url
        self.cache_seconds = cache_seconds
        self.max_entries = max_entries
        self._cache: dict[tuple, tuple[float, dict]] = {}
        self._lock = threading.Lock()
        import httpx  # imported here so the pure helpers above work without it

        self._httpx = httpx
        self._http = httpx.Client(timeout=timeout, follow_redirects=True,
                                  headers={"User-Agent": "JezeroDeltaExplorer/1.0 (raw-image proxy)",
                                           "Accept": "application/json"})

    def close(self) -> None:
        self._http.close()

    def fetch(self, q: Query) -> dict[str, Any]:
        q = q.validate()
        params = build_params(q)
        key = tuple(sorted(params.items()))
        now = time.time()
        with self._lock:
            hit = self._cache.get(key)
            if hit and hit[0] > now:
                return {**hit[1], "cached": True}
        try:
            r = self._http.get(self.base_url, params=params)
            r.raise_for_status()
            raw = r.json()
        except (self._httpx.HTTPError, ValueError) as exc:
            raise UpstreamError(f"NASA raw-image feed unavailable: {exc.__class__.__name__}") from None
        page = normalize_page(raw, q)
        page.update({"source": "NASA/JPL-Caltech · Mars 2020 Perseverance raw images",
                     "source_url": "https://mars.nasa.gov/mars2020/multimedia/raw-images/",
                     "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))})
        with self._lock:
            if len(self._cache) >= self.max_entries:
                for k in sorted(self._cache, key=lambda k: self._cache[k][0])[: self.max_entries // 4]:
                    self._cache.pop(k, None)
            self._cache[key] = (now + self.cache_seconds, page)
        return {**page, "cached": False}


def camera_groups() -> list[dict[str, Any]]:
    return [{"id": k, "label": v[0], "instruments": list(v[1])} for k, v in CAMERA_GROUPS.items()]
