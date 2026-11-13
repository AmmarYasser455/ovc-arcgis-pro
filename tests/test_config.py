import dataclasses

import pytest

from core import config


def test_defaults():
    assert config.DEFAULT_OVERLAP_CONFIG.min_overlap_area_m2 == 1.0
    assert config.DEFAULT_ROAD_CONFLICT_CONFIG.buffer_distance_m == 5.0
    assert config.DEFAULT_ROAD_QC_CONFIG.dangle_tolerance_m == 0.5
    assert config.DEFAULT_OUTPUT_CONFIG.type_duplicate == "DUPLICATE"


def test_overlap_thresholds_ordered():
    c = config.DEFAULT_OVERLAP_CONFIG
    assert 0 < c.partial_ratio_min < c.duplicate_ratio_min <= 1


def test_configs_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.DEFAULT_ROAD_QC_CONFIG.dangle_tolerance_m = 9
