import math

import numpy as np
import pytest

from jezero import terrain


def plane(a, b, h=12, w=15, res=20.0):
    """z = a*E + b*N with E to the east and N to the north (rows go south)."""
    rows, cols = np.mgrid[0:h, 0:w]
    e = cols * res
    n = -rows * res
    return a * e + b * n


def test_slope_of_plane_is_exact():
    z = plane(0.3, -0.4)
    s = terrain.slope_degrees(z, 20.0, 20.0)
    expected = math.degrees(math.atan(0.5))
    assert np.allclose(s[1:-1, 1:-1], expected)
    # edges have an incomplete 3x3 window -> NoData, never extrapolated
    assert np.isnan(s[0]).all() and np.isnan(s[-1]).all()
    assert np.isnan(s[:, 0]).all() and np.isnan(s[:, -1]).all()


def test_anisotropic_pixels():
    rows, cols = np.mgrid[0:10, 0:10]
    z = 0.2 * cols * 5.0 + 0.1 * (-rows * 10.0)
    gx, gy = terrain.horn_gradients(z, 5.0, 10.0)
    assert np.allclose(gx[1:-1, 1:-1], 0.2) and np.allclose(gy[1:-1, 1:-1], 0.1)


def test_aspect_points_downslope():
    z = plane(-0.2, 0.0)  # descends toward the east
    assert np.allclose(terrain.aspect_degrees(z, 20, 20)[1:-1, 1:-1], 90.0)
    z = plane(0.0, 0.2)   # descends toward the south
    assert np.allclose(terrain.aspect_degrees(z, 20, 20)[1:-1, 1:-1], 180.0)


def test_hillshade_orientation():
    flat = terrain.hillshade(plane(0, 0), 20, 20, 315, 45)
    assert np.allclose(flat[1:-1, 1:-1], math.sin(math.radians(45)))
    # surface facing north-west (descends to NW) faces a NW light -> brighter than flat
    facing = terrain.hillshade(plane(0.3, -0.3), 20, 20, 315, 45)
    away = terrain.hillshade(plane(-0.3, 0.3), 20, 20, 315, 45)
    assert (facing[1:-1, 1:-1] > flat[1:-1, 1:-1]).all()
    assert (away[1:-1, 1:-1] < flat[1:-1, 1:-1]).all()
    # facing the light directly with slope = 90 - altitude gives full illumination
    t = math.tan(math.radians(45))
    g = t / math.sqrt(2)
    full = terrain.hillshade(plane(g, -g), 20, 20, 315, 45)
    assert np.allclose(full[1:-1, 1:-1], 1.0)


def test_tri_riley_plane():
    a, res = 0.25, 20.0
    z = plane(a, 0.0, res=res)
    tri = terrain.tri_riley(z)
    assert np.allclose(tri[1:-1, 1:-1], math.sqrt(6) * a * res)


def test_nodata_propagates_to_3x3_only():
    z = plane(0.1, 0.1, 20, 20)
    z[10, 10] = np.nan
    s = terrain.slope_degrees(z, 20, 20)
    assert np.isnan(s[9:12, 9:12]).all()
    assert np.isfinite(s[5, 5]) and np.isfinite(s[10, 13])


def test_blockwise_identical_to_whole_array():
    rng = np.random.default_rng(3)
    z = np.cumsum(np.cumsum(rng.normal(size=(157, 203)), 0), 1)
    z[40:45, 70:90] = np.nan
    for fn, kw in [(terrain.slope_degrees, dict(res_x=20.0, res_y=20.0)),
                   (terrain.hillshade, dict(res_x=20.0, res_y=20.0)),
                   (terrain.tri_riley, {})]:
        whole = fn(z, **kw)
        blocks = terrain.blockwise(fn, z, block=37, **kw)
        assert np.array_equal(np.isnan(whole), np.isnan(blocks))
        assert np.allclose(whole[np.isfinite(whole)], blocks[np.isfinite(blocks)])


def test_to_float_with_nan():
    a = np.array([[0, 5], [7, -3.4e38]], dtype="f4")
    out = terrain.to_float_with_nan(a, nodata=np.float32(-3.4e38))
    assert np.isnan(out[1, 1]) and out[0, 0] == 0
    out = terrain.to_float_with_nan(a, nodata=0)
    assert np.isnan(out[0, 0])
    out = terrain.to_float_with_nan(a, nodata=None, valid_mask=np.array([[1, 0], [1, 1]]))
    assert np.isnan(out[0, 1])


def test_invalid_resolution():
    with pytest.raises(ValueError):
        terrain.slope_degrees(np.zeros((3, 3)), 0, 1)
