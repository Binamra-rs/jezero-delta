"""Colour ramps for scientific layers (256-entry RGBA lookup tables).

Ramps are perceptually ordered and colour-blind aware. The same stops are
served to the frontend legend through the catalog API, so the legend is
always generated from exactly what the tile renderer uses.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

# (position 0..1, hex colour)
RAMPS: dict[str, list[tuple[float, str]]] = {
    "gray": [(0.0, "#000000"), (1.0, "#ffffff")],
    # elevation: deep blue-violet lows → teal → sand → pale highs (batlow-like)
    "elevation": [(0.0, "#011959"), (0.2, "#1b5a62"), (0.4, "#4d734d"), (0.6, "#a08a2c"),
                  (0.8, "#f19d6b"), (1.0, "#faccfa")],
    # thermal inertia: inferno-like
    "thermal": [(0.0, "#000004"), (0.2, "#3b0f70"), (0.4, "#8c2981"), (0.6, "#de4968"),
                (0.8, "#fe9f6d"), (1.0, "#fcfdbf")],
    # slope: sequential light → dark orange-red
    "slope": [(0.0, "#fff5eb"), (0.25, "#fdd0a2"), (0.5, "#fd8d3c"), (0.75, "#d94801"), (1.0, "#7f2704")],
    # roughness: viridis-like
    "roughness": [(0.0, "#440154"), (0.25, "#3b528b"), (0.5, "#21918c"), (0.75, "#5ec962"), (1.0, "#fde725")],
}


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


@lru_cache
def lut(name: str) -> np.ndarray:
    stops = RAMPS[name]
    pos = np.array([p for p, _ in stops])
    rgb = np.array([_hex(c) for _, c in stops], dtype="f8")
    x = np.linspace(0, 1, 256)
    out = np.empty((256, 4), dtype="u1")
    for i in range(3):
        out[:, i] = np.round(np.interp(x, pos, rgb[:, i])).astype("u1")
    out[:, 3] = 255
    return out


def apply(values: np.ndarray, valid: np.ndarray, vmin: float, vmax: float, ramp: str) -> np.ndarray:
    """Map float values to RGBA; invalid pixels are fully transparent."""
    span = vmax - vmin if vmax > vmin else 1.0
    t = np.clip((np.where(valid, values, vmin) - vmin) / span, 0.0, 1.0)
    idx = np.round(t * 255).astype("u1")
    rgba = lut(ramp)[idx]
    rgba[..., 3] = np.where(valid, 255, 0)
    return rgba


def legend(ramp: str) -> list[dict]:
    return [{"position": p, "color": c} for p, c in RAMPS[ramp]]
