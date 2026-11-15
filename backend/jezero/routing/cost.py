"""Terrain traversal cost model.

Edge cost for moving from cell a to its 8-neighbour b:

    C(a,b) = d(a,b) · [ 1 + α·½(f(s_a)+f(s_b)) + β·½(g(r_a)+g(r_b))
                          + γ_up·max(G,0) + γ_down·max(−G,0) ]

    d       horizontal ground distance between cell centres
            (res for cardinal moves, res·√2 for diagonal moves)
    G       signed grade of the move, (z_b − z_a)/d  (uphill positive)
    s       local Horn slope of the cell (degrees)
    r       local roughness (Riley TRI, metres), optional
    f(s)    (tan s / tan s_max)^p           ∈ [0, 1] on passable cells
    g(r)    r / r_ref

A cell is BLOCKED if its elevation or slope is NoData, if s > s_max, or if
r > r_max (when configured). A move is BLOCKED if either end is blocked, if
the edge grade angle exceeds the profile's limit, or — for diagonal moves —
if either of the two orthogonal cells it passes between is blocked (no
corner cutting). Every multiplier term is ≥ 0, so C(a,b) ≥ d(a,b); this is
what makes the octile-distance heuristic admissible and consistent.

These parameters are planning weights for exploration studies. They are not
certified rover mobility limits (see docs/05-astar-routing.md).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Mapping

import numpy as np

# (d_row, d_col); row index increases southward
DIRECTIONS: tuple[tuple[int, int], ...] = (
    (-1, 0), (1, 0), (0, 1), (0, -1),      # N S E W
    (-1, 1), (-1, -1), (1, 1), (1, -1),    # NE NW SE SW
)


@dataclass(frozen=True)
class CostProfile:
    name: str
    label: str
    description: str
    max_slope_deg: float
    max_edge_grade_deg: float
    alpha: float
    slope_exponent: float = 2.0
    beta: float = 0.0
    roughness_ref_m: float = 1.0
    max_roughness_m: float | None = None
    gamma_up: float = 0.0
    gamma_down: float = 0.0

    def __post_init__(self) -> None:
        for field in ("alpha", "beta", "gamma_up", "gamma_down"):
            if getattr(self, field) < 0:
                raise ValueError(f"{field} must be >= 0 (keeps the A* heuristic admissible)")
        if not 0 < self.max_slope_deg < 90 or not 0 < self.max_edge_grade_deg < 90:
            raise ValueError("Slope limits must be in (0, 90) degrees")
        if self.slope_exponent <= 0 or self.roughness_ref_m <= 0:
            raise ValueError("slope_exponent and roughness_ref_m must be positive")

    @classmethod
    def from_config(cls, name: str, cfg: Mapping[str, Any]) -> "CostProfile":
        return cls(
            name=name,
            label=str(cfg.get("label", name)),
            description=str(cfg.get("description", "")),
            max_slope_deg=float(cfg["max_slope_deg"]),
            max_edge_grade_deg=float(cfg.get("max_edge_grade_deg", cfg["max_slope_deg"])),
            alpha=float(cfg.get("alpha", 0.0)),
            slope_exponent=float(cfg.get("slope_exponent", 2.0)),
            beta=float(cfg.get("beta", 0.0)),
            roughness_ref_m=float(cfg.get("roughness_ref_m", 1.0)),
            max_roughness_m=None if cfg.get("max_roughness_m") is None else float(cfg["max_roughness_m"]),
            gamma_up=float(cfg.get("gamma_up", 0.0)),
            gamma_down=float(cfg.get("gamma_down", 0.0)),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def min_multiplier(self) -> float:
        """Lower bound on the cost multiplier over all passable edges."""
        return 1.0


@dataclass
class EdgeWeights:
    """Directed edge weights for every cell and direction (inf = blocked)."""

    weights: np.ndarray        # (8, H, W) float64
    passable: np.ndarray       # (H, W) bool
    res: float

    @property
    def shape(self) -> tuple[int, int]:
        return self.passable.shape  # type: ignore[return-value]


def _shift(arr: np.ndarray, dr: int, dc: int, fill) -> np.ndarray:
    """Value of the neighbour at (r+dr, c+dc) for every cell (fill outside)."""
    h, w = arr.shape
    p = np.pad(arr, 1, mode="constant", constant_values=fill)
    return p[1 + dr:1 + dr + h, 1 + dc:1 + dc + w]


def cell_passable(elev: np.ndarray, slope: np.ndarray, profile: CostProfile,
                  rough: np.ndarray | None = None, mask: np.ndarray | None = None) -> np.ndarray:
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(elev) & np.isfinite(slope) & (slope <= profile.max_slope_deg)
        if profile.max_roughness_m is not None:
            if rough is None:
                raise ValueError("Profile has max_roughness_m but no roughness grid supplied")
            ok &= np.isfinite(rough) & (rough <= profile.max_roughness_m)
    if mask is not None:
        ok &= mask.astype(bool)
    return ok


def build_edge_weights(elev: np.ndarray, slope: np.ndarray, res: float, profile: CostProfile,
                       rough: np.ndarray | None = None, mask: np.ndarray | None = None) -> EdgeWeights:
    """Vectorised edge-weight construction shared by A* and the Dijkstra reference."""
    elev = np.asarray(elev, dtype="f8")
    slope = np.asarray(slope, dtype="f8")
    if elev.shape != slope.shape:
        raise ValueError("Elevation and slope grids must have the same shape")
    if res <= 0:
        raise ValueError("Resolution must be positive")

    passable = cell_passable(elev, slope, profile, rough, mask)

    tan_max = math.tan(math.radians(profile.max_slope_deg))
    with np.errstate(invalid="ignore"):
        f = (np.tan(np.radians(np.where(passable, slope, 0.0))) / tan_max) ** profile.slope_exponent
        term = profile.alpha * f
        if profile.beta > 0:
            if rough is None:
                raise ValueError("Profile has beta > 0 but no roughness grid supplied")
            r = np.where(passable & np.isfinite(rough), rough, 0.0)
            term = term + profile.beta * (r / profile.roughness_ref_m)
    term = np.where(passable, term, 0.0)

    grade_limit = math.tan(math.radians(profile.max_edge_grade_deg))
    out = np.full((8,) + elev.shape, np.inf, dtype="f8")
    z_safe = np.where(passable, elev, 0.0)

    for k, (dr, dc) in enumerate(DIRECTIONS):
        nb_pass = _shift(passable, dr, dc, False)
        ok = passable & nb_pass
        if dr != 0 and dc != 0:  # no corner cutting through blocked cells
            ok &= _shift(passable, dr, 0, False) & _shift(passable, 0, dc, False)
        d = res * math.hypot(dr, dc)
        dz = _shift(z_safe, dr, dc, 0.0) - z_safe
        grade = dz / d
        ok &= np.abs(grade) <= grade_limit
        mult = (1.0 + 0.5 * (term + _shift(term, dr, dc, 0.0))
                + profile.gamma_up * np.maximum(grade, 0.0)
                + profile.gamma_down * np.maximum(-grade, 0.0))
        out[k] = np.where(ok, d * mult, np.inf)

    return EdgeWeights(weights=out, passable=passable, res=float(res))
