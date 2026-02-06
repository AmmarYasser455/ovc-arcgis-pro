# -*- coding: utf-8 -*-
"""
OVC ArcGIS Pro - Configuration Constants

This module contains all configuration constants, default values, and
threshold settings used throughout the OVC toolbox.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class OverlapConfig:
    """Configuration for building overlap detection."""
    
    # Minimum area (sq meters) for an overlap to be considered a violation
    min_overlap_area_m2: float = 1.0
    
    # Ratio thresholds for classification
    duplicate_ratio_min: float = 0.90  # >= 90% overlap = duplicate
    partial_ratio_min: float = 0.50    # >= 50% overlap = partial
    # Below partial_ratio_min = sliver


@dataclass(frozen=True)
class RoadConflictConfig:
    """Configuration for building-road conflict detection."""
    
    # Buffer distance around roads (meters)
    buffer_distance_m: float = 5.0
    
    # Minimum intersection area to flag as conflict
    min_overlap_area_m2: float = 0.5


@dataclass(frozen=True)
class RoadQCConfig:
    """Configuration for road network quality control."""
    
    # Tolerance for dangle/endpoint matching (meters)
    dangle_tolerance_m: float = 0.5
    
    # Minimum segment length to consider for analysis
    min_segment_length_m: float = 1.0
    
    # Buffer for boundary edge detection
    boundary_buffer_m: float = 5.0


@dataclass(frozen=True)
class OutputConfig:
    """Configuration for output settings."""
    
    # Field names for output feature classes
    field_id_a: str = "SOURCE_FID_A"
    field_id_b: str = "SOURCE_FID_B"
    field_overlap_area: str = "OVERLAP_AREA_M2"
    field_overlap_ratio: str = "OVERLAP_RATIO"
    field_overlap_type: str = "OVERLAP_TYPE"
    field_error_type: str = "ERROR_TYPE"
    field_timestamp: str = "CHECK_TIME"
    field_road_id: str = "ROAD_FID"
    
    # Overlap type values
    type_duplicate: str = "DUPLICATE"
    type_partial: str = "PARTIAL"
    type_sliver: str = "SLIVER"


# Default configuration instances
DEFAULT_OVERLAP_CONFIG = OverlapConfig()
DEFAULT_ROAD_CONFLICT_CONFIG = RoadConflictConfig()
DEFAULT_ROAD_QC_CONFIG = RoadQCConfig()
DEFAULT_OUTPUT_CONFIG = OutputConfig()
