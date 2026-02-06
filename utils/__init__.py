# -*- coding: utf-8 -*-
"""
OVC ArcGIS Pro - Utilities Module

This package contains utility functions for cursor operations,
messaging, and other common tasks.
"""

from utils.cursor_helpers import (
    get_oid_field,
    get_shape_field,
    get_spatial_reference,
    count_features,
    read_features_to_dict,
    read_geometries_to_dict,
    iterate_features,
    create_output_feature_class,
    insert_cursor,
    batch_insert_rows,
    validate_feature_class
)

from utils.messaging import (
    ToolMessenger,
    ProgressTracker,
    format_number,
    format_area,
    get_timestamp
)

__all__ = [
    # Cursor helpers
    "get_oid_field",
    "get_shape_field",
    "get_spatial_reference",
    "count_features",
    "read_features_to_dict",
    "read_geometries_to_dict",
    "iterate_features",
    "create_output_feature_class",
    "insert_cursor",
    "batch_insert_rows",
    "validate_feature_class",
    # Messaging
    "ToolMessenger",
    "ProgressTracker",
    "format_number",
    "format_area",
    "get_timestamp"
]
