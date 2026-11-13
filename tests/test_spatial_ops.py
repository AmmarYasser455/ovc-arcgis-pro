"""Tests for the arcpy-free helpers in core.spatial_ops (arcpy is stubbed)."""
import pytest

from core.config import DEFAULT_OVERLAP_CONFIG as CFG
from core.spatial_ops import classify_overlap, extents_intersect


@pytest.mark.parametrize(
    "ratio, expected",
    [
        (1.0, "DUPLICATE"),
        (0.90, "DUPLICATE"),
        (0.8999, "PARTIAL"),
        (0.50, "PARTIAL"),
        (0.4999, "SLIVER"),
        (0.0, "SLIVER"),
    ],
)
def test_classify_overlap_boundaries(ratio, expected):
    assert classify_overlap(ratio) == expected


def test_classify_overlap_matches_config_defaults():
    assert classify_overlap(CFG.duplicate_ratio_min) == "DUPLICATE"
    assert classify_overlap(CFG.partial_ratio_min) == "PARTIAL"


def test_classify_overlap_custom_thresholds():
    assert classify_overlap(0.7, duplicate_threshold=0.6, partial_threshold=0.3) == "DUPLICATE"
    assert classify_overlap(0.2, duplicate_threshold=0.6, partial_threshold=0.3) == "SLIVER"


def test_extents_intersect_overlapping_and_disjoint():
    assert extents_intersect((0, 0, 10, 10), (5, 5, 15, 15))
    assert not extents_intersect((0, 0, 10, 10), (11, 0, 20, 10))
    assert not extents_intersect((0, 0, 10, 10), (0, 11, 10, 20))


def test_extents_intersect_touching_edges_count_as_intersecting():
    assert extents_intersect((0, 0, 10, 10), (10, 0, 20, 10))


def test_extents_intersect_contained():
    assert extents_intersect((0, 0, 10, 10), (2, 2, 3, 3))
