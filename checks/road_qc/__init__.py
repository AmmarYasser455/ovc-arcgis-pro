# -*- coding: utf-8 -*-
"""
OVC ArcGIS Pro - Road QC Checks Module

This package contains road network quality control checks:
- Dangle detection (spatial-hash O(n))
- Disconnected segment detection
- Self-intersection detection
"""

from checks.road_qc.engine import (
    find_dangles,
    find_disconnected,
    find_self_intersections,
)

__all__ = [
    "find_dangles",
    "find_disconnected",
    "find_self_intersections",
]
