"""Tests for core.spatial_ops.SpatialIndex using fake geometries (no arcpy)."""
from types import SimpleNamespace

import pytest

from core.spatial_ops import SpatialIndex


def geom(xmin, ymin, xmax, ymax):
    return SimpleNamespace(
        pointCount=4,
        type="polygon",
        area=max((xmax - xmin) * (ymax - ymin), 1e-9),
        extent=SimpleNamespace(XMin=xmin, YMin=ymin, XMax=xmax, YMax=ymax),
    )


@pytest.mark.parametrize("bad", [0, -5, float("nan"), float("inf"), None, "10", True])
def test_invalid_cell_size_rejected(bad):
    with pytest.raises(ValueError):
        SpatialIndex(bad)


def test_candidates_share_cells():
    idx = SpatialIndex(100.0)
    idx.insert(1, geom(0, 0, 50, 50))
    idx.insert(2, geom(40, 40, 90, 90))
    idx.insert(3, geom(1000, 1000, 1010, 1010))
    assert idx.query_candidates(1) == [2]
    assert idx.query_candidates(3) == []


def test_negative_coordinates_use_floor_cells():
    # Cell -1 spans [-100, 0): negative coordinates must floor, not truncate.
    idx = SpatialIndex(100.0)
    idx.insert(1, geom(-30, -30, -10, -10))
    idx.insert(2, geom(-60, -60, -20, -20))
    idx.insert(3, geom(10, 10, 20, 20))
    assert idx.query_candidates(1) == [2]
    assert (-1, -1) in idx.grid and (0, 0) in idx.grid


def test_reinsert_replaces_stale_entries():
    idx = SpatialIndex(100.0)
    idx.insert(1, geom(0, 0, 10, 10))
    idx.insert(2, geom(500, 500, 510, 510))
    idx.insert(1, geom(500, 500, 520, 520))  # feature moved
    assert idx.query_candidates(2) == [1]
    assert idx.query_by_extent((0, 0, 50, 50)) == []
    assert (0, 0) not in idx.grid


def test_remove():
    idx = SpatialIndex(100.0)
    idx.insert(1, geom(0, 0, 10, 10))
    idx.insert(2, geom(0, 0, 10, 10))
    idx.remove(1)
    idx.remove(99)  # unknown id is a no-op
    assert idx.query_candidates(2) == []
    assert idx.query_by_extent((0, 0, 5, 5)) == [2]


def test_real_location_utm_cairo():
    # Cairo, EPSG:32636 (WGS 84 / UTM 36N), (x=easting, y=northing), metres.
    # Approximate positions (rounded, hand-derived from lon/lat; central
    # meridian 33E): Cairo Tower ~(328900, 3325500), a block just east of it
    # spanning the 329000 m cell edge, and Giza ~(311000, 3321000).
    # Easting (~3.3e5) and northing (~3.3e6) differ by 10x, so an x/y swap
    # produces different cell keys and fails.
    idx = SpatialIndex(1000.0)  # 1 km cells
    idx.insert(1, geom(328900, 3325500, 328960, 3325560))  # tower footprint
    idx.insert(2, geom(328950, 3325400, 329050, 3325480))  # crosses x=329000
    idx.insert(3, geom(311000, 3321000, 311100, 3321100))  # Giza
    assert set(idx.grid) == {(328, 3325), (329, 3325), (311, 3321)}
    assert idx.grid[(328, 3325)] == [1, 2]
    assert idx.query_candidates(1) == [2]
    assert idx.query_candidates(3) == []
    assert idx.query_by_extent((329000, 3325000, 329500, 3325999)) == [2]
    assert idx.query_by_extent((3325000, 329000, 3325999, 329500)) == []


def test_null_geometry_not_indexed():
    idx = SpatialIndex(100.0)
    idx.insert(1, None)
    assert idx.extents == {}
