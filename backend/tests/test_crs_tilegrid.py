import math

import numpy as np
import pytest

from jezero.crs import Boundary, CoordinateError, MarsEquirectangular, normalize_lon_360
from jezero.tilegrid import TileGrid, TileIndexError

CFG = {
    "body": "Mars", "projection": "equirectangular", "radius_m": 3396190.0,
    "central_meridian_deg_e": 77.40, "standard_parallel_deg": 18.45,
}
BOUNDARY = {"lon_min_e": 77.30, "lon_max_e": 77.50, "lat_min_n": 18.38, "lat_max_n": 18.56, "snap_m": 20.0}


@pytest.fixture
def crs():
    return MarsEquirectangular.from_config(CFG)


def test_origin_and_central_meridian(crs):
    x, y = crs.forward(77.40, 0.0)
    assert x == pytest.approx(0.0, abs=1e-9) and y == pytest.approx(0.0, abs=1e-9)


def test_round_trip(crs):
    rng = np.random.default_rng(1)
    for lon, lat in zip(rng.uniform(77.0, 78.0, 500), rng.uniform(18.0, 19.0, 500), strict=False):
        x, y = crs.forward(lon, lat)
        lon2, lat2 = crs.inverse(x, y)
        assert lon2 == pytest.approx(lon, abs=1e-10)
        assert lat2 == pytest.approx(lat, abs=1e-10)


def test_array_matches_scalar(crs):
    lon = np.array([77.31, 77.45, 77.49]); lat = np.array([18.39, 18.44, 18.55])
    xa, ya = crs.forward_array(lon, lat)
    for i in range(3):
        assert (xa[i], ya[i]) == pytest.approx(crs.forward(lon[i], lat[i]))
    lo, la = crs.inverse_array(xa, ya)
    assert np.allclose(lo, lon) and np.allclose(la, lat)


def test_true_scale_on_standard_parallel(crs):
    # 1 degree of longitude along lat_ts equals the true arc length on the sphere
    x0, _ = crs.forward(77.0, 18.45)
    x1, _ = crs.forward(78.0, 18.45)
    arc = math.radians(1.0) * CFG["radius_m"] * math.cos(math.radians(18.45))
    assert x1 - x0 == pytest.approx(arc, rel=1e-12)
    # meridian is always true scale
    _, y0 = crs.forward(77.4, 18.0); _, y1 = crs.forward(77.4, 19.0)
    assert y1 - y0 == pytest.approx(math.radians(1.0) * CFG["radius_m"], rel=1e-12)


def test_scale_error_inside_boundary_below_0p1_percent(crs):
    for lat in (18.38, 18.56):
        assert abs(crs.scale_factor_x(lat) - 1.0) < 1e-3


def test_longitude_conventions(crs):
    assert normalize_lon_360(-282.6) == pytest.approx(77.4)
    assert normalize_lon_360(437.4) == pytest.approx(77.4)
    assert normalize_lon_360(360.0) == 0.0
    # -282.6 (west-positive style input in east-negative form) maps to the same x
    assert crs.forward(-282.6, 18.4)[0] == pytest.approx(crs.forward(77.4, 18.4)[0])


@pytest.mark.parametrize("bad", [(77.4, 91.0), (float("nan"), 18.0), (77.0, float("inf"))])
def test_rejects_malformed(crs, bad):
    with pytest.raises(CoordinateError):
        crs.forward(*bad)


def test_rejects_non_mars():
    with pytest.raises(ValueError):
        MarsEquirectangular.from_config({**CFG, "radius_m": 6378137.0})
    with pytest.raises(ValueError):
        MarsEquirectangular.from_config({**CFG, "body": "Earth"})


def test_proj4_and_wkt_mention_mars_sphere(crs):
    assert "+R=3396190.0" in crs.proj4 and "+proj=eqc" in crs.proj4
    assert "3396190.0" in crs.wkt2 and "WGS" not in crs.wkt2


def test_against_pyproj_if_available(crs):
    pyproj = pytest.importorskip("pyproj")
    t = pyproj.Transformer.from_crs(pyproj.CRS.from_proj4(crs.geographic_proj4),
                                    pyproj.CRS.from_proj4(crs.proj4), always_xy=True)
    for lon, lat in [(77.30, 18.38), (77.45, 18.44), (77.50, 18.56)]:
        assert t.transform(lon, lat) == pytest.approx(crs.forward(lon, lat), abs=1e-6)


def test_boundary_snapped_and_contains(crs):
    b = Boundary.from_config(BOUNDARY, crs)
    for v in b.bounds:
        assert v / 20.0 == pytest.approx(round(v / 20.0))
    x, y = crs.forward(77.45, 18.44)
    assert b.contains(x, y)
    assert not b.contains(*crs.forward(77.60, 18.44))
    assert 10_000 < b.width < 12_500 and 10_000 < b.height < 11_500


def test_tilegrid(crs):
    b = Boundary.from_config(BOUNDARY, crs)
    g = TileGrid.build(b, 256, 0.5)
    assert g.matrix_size(0) == (1, 1)
    assert g.resolutions[-1] <= 0.5 < g.resolutions[-2]
    for z in range(1, len(g.resolutions)):
        assert g.resolutions[z] == pytest.approx(g.resolutions[z - 1] / 2)
    z = 4
    cols, rows = g.matrix_size(z)
    # tiles cover the boundary exactly from the top-left origin with no gaps
    first = g.tile_bounds(z, 0, 0)
    last = g.tile_bounds(z, cols - 1, rows - 1)
    assert first[0] == b.minx and first[3] == b.maxy
    assert last[2] >= b.maxx and last[1] <= b.miny
    right = g.tile_bounds(z, 1, 0)
    assert right[0] == pytest.approx(first[2])
    with pytest.raises(TileIndexError):
        g.tile_bounds(z, cols, 0)
    with pytest.raises(TileIndexError):
        g.tile_bounds(g.max_zoom + 1, 0, 0)
