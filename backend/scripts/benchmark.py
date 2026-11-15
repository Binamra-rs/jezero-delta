"""Performance measurements against a running deployment (brief §12).

Standard library only, so it runs anywhere:

    python scripts/benchmark.py --api https://api.astro-mars.wiki \
        [--waypoints]        # also time waypoint create/list/delete (throwaway workspace)

Measures: config load, tile response (cold & warm) per layer, point
inspection, route calculation (short / medium / long) and waypoint CRUD.
Prints a Markdown table to paste into docs/09-performance.md.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import time
import urllib.error
import urllib.request


def call(url: str, method: str = "GET", body: dict | None = None, key: str | None = None) -> tuple[float, int, bytes]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("X-Workspace-Key", key)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            payload = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        payload, status = e.read(), e.code
    return (time.perf_counter() - t0) * 1000, status, payload


def summarize(name: str, ms: list[float]) -> str:
    if not ms:
        return f"| {name} | 0 | – | – | – |"
    ms = sorted(ms)
    p95 = ms[min(len(ms) - 1, int(round(0.95 * (len(ms) - 1))))]
    return f"| {name} | {len(ms)} | {statistics.median(ms):.0f} ms | {p95:.0f} ms | {max(ms):.0f} ms |"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--tiles", type=int, default=40)
    ap.add_argument("--waypoints", action="store_true")
    a = ap.parse_args()
    api = a.api.rstrip("/")
    rows = []

    t, s, body = call(f"{api}/api/v1/config")
    cfg = json.loads(body)
    rows.append(summarize("GET /config (initial metadata)", [t]))
    tg = cfg["tilegrid"]
    minx, miny, maxx, maxy = cfg["boundary"]
    rnd = random.Random(7)

    for layer in cfg["layers"]:
        z = min(len(tg["resolutions"]) - 1, 5)
        cols, rws = tg["matrix_sizes"][z]
        coords = [(rnd.randrange(cols), rnd.randrange(rws)) for _ in range(a.tiles)]
        cold = [call(f"{api}/api/v1/tiles/{layer['id']}/{z}/{x}/{y}.png?bench={time.time()}")[0] for x, y in coords]
        warm = [call(f"{api}/api/v1/tiles/{layer['id']}/{z}/{x}/{y}.png?v={cfg['catalog_version']}")[0] for x, y in coords]
        rows.append(summarize(f"tile {layer['id']} z{z} (uncached)", cold))
        rows.append(summarize(f"tile {layer['id']} z{z} (cacheable URL)", warm))

    pts = [(rnd.uniform(minx, maxx), rnd.uniform(miny, maxy)) for _ in range(30)]
    rows.append(summarize("GET /inspect", [call(f"{api}/api/v1/inspect?x={x}&y={y}")[0] for x, y in pts]))

    rows.append(summarize("GET /raw-images (NASA proxy)", [call(f"{api}/api/v1/raw-images?per_page=24&page={i}")[0] for i in range(3)]))

    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    for label, d in (("route ~1 km", 500), ("route ~4 km", 2000), ("route ~10 km", 5000)):
        times = []
        for _ in range(3):
            body = {"start": {"x": cx - d, "y": cy}, "end": {"x": cx + d, "y": cy + d / 4}, "terrain_source": "ctx"}
            t, s, _ = call(f"{api}/api/v1/route", "POST", body)
            if s == 200:
                times.append(t)
        rows.append(summarize(f"POST /route {label} (CTX)", times))

    if a.waypoints:
        import secrets
        tok = secrets.token_urlsafe(32)   # throwaway anonymous workspace
        c, l, d = [], [], []
        for i in range(10):
            t, s, b = call(f"{api}/api/v1/waypoints", "POST",
                           {"name": f"bench {i}", "location": {"x": cx, "y": cy}}, tok)
            c.append(t)
            wid = json.loads(b)["id"]
            l.append(call(f"{api}/api/v1/waypoints", token=tok)[0])
            d.append(call(f"{api}/api/v1/waypoints/{wid}", "DELETE", token=tok)[0])
        rows += [summarize("POST /waypoints", c), summarize("GET /waypoints", l), summarize("DELETE /waypoints/{id}", d)]

    print("| Operation | n | median | p95 | max |\n|---|---:|---:|---:|---:|")
    print("\n".join(rows))


if __name__ == "__main__":
    main()
