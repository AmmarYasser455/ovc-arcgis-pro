# -*- coding: utf-8 -*-
"""
OVC ArcGIS Pro - Cursor Helper Utilities

This module provides helper functions for working with ArcPy data access
cursors, making it easier to read and write feature data.
"""

import arcpy
from typing import Dict, List, Any, Optional, Tuple, Generator
from contextlib import contextmanager


def get_oid_field(feature_class: str) -> str:
    """
    Get the OID field name for a feature class.
    
    Args:
        feature_class: Path to the feature class
        
    Returns:
        OID field name (typically "OBJECTID" or "FID")
    """
    desc = arcpy.Describe(feature_class)
    return desc.OIDFieldName


def get_shape_field(feature_class: str) -> str:
    """
    Get the shape field name for a feature class.
    
    Args:
        feature_class: Path to the feature class
        
    Returns:
        Shape field name (typically "Shape" or "SHAPE")
    """
    desc = arcpy.Describe(feature_class)
    return desc.shapeFieldName


def get_spatial_reference(feature_class: str) -> arcpy.SpatialReference:
    """
    Get the spatial reference for a feature class.
    
    Args:
        feature_class: Path to the feature class
        
    Returns:
        SpatialReference object
    """
    desc = arcpy.Describe(feature_class)
    return desc.spatialReference


def count_features(
    feature_class: str,
    where_clause: Optional[str] = None
) -> int:
    """
    Count features in a feature class.
    
    Args:
        feature_class: Path to the feature class
        where_clause: Optional SQL where clause
        
    Returns:
        Number of features
    """
    result = arcpy.management.GetCount(feature_class)
    return int(result[0])


def read_features_to_dict(
    feature_class: str,
    geometry_token: str = "SHAPE@",
    additional_fields: Optional[List[str]] = None,
    where_clause: Optional[str] = None
) -> Dict[int, Dict[str, Any]]:
    """
    Read features from a feature class into a dictionary.
    
    Args:
        feature_class: Path to the feature class
        geometry_token: Geometry token (SHAPE@, SHAPE@XY, etc.)
        additional_fields: Optional list of additional field names
        where_clause: Optional SQL where clause
        
    Returns:
        Dictionary mapping OID to feature dictionary
    """
    oid_field = get_oid_field(feature_class)
    fields = [oid_field, geometry_token]
    
    if additional_fields:
        fields.extend(additional_fields)
    
    result = {}
    
    with arcpy.da.SearchCursor(
        feature_class,
        fields,
        where_clause=where_clause
    ) as cursor:
        for row in cursor:
            oid = row[0]
            feature = {
                "OID": oid,
                "geometry": row[1]
            }
            
            if additional_fields:
                for i, field in enumerate(additional_fields):
                    feature[field] = row[2 + i]
            
            result[oid] = feature
    
    return result


def read_geometries_to_dict(
    feature_class: str,
    where_clause: Optional[str] = None
) -> Dict[int, arcpy.Geometry]:
    """
    Read only geometries from a feature class into a dictionary.
    
    More memory-efficient than read_features_to_dict when only
    geometry is needed.
    
    Args:
        feature_class: Path to the feature class
        where_clause: Optional SQL where clause
        
    Returns:
        Dictionary mapping OID to geometry
    """
    oid_field = get_oid_field(feature_class)
    fields = [oid_field, "SHAPE@"]
    
    result = {}
    
    with arcpy.da.SearchCursor(
        feature_class,
        fields,
        where_clause=where_clause
    ) as cursor:
        for row in cursor:
            oid = row[0]
            geometry = row[1]
            # Check if geometry is valid (cursor returns None for null geometries)
            if geometry is not None:
                result[oid] = geometry
    
    return result


def iterate_features(
    feature_class: str,
    fields: List[str],
    where_clause: Optional[str] = None
) -> Generator[Tuple, None, None]:
    """
    Iterate over features in a feature class.
    
    Generator that yields tuples of field values.
    
    Args:
        feature_class: Path to the feature class
        fields: List of field names/tokens to read
        where_clause: Optional SQL where clause
        
    Yields:
        Tuples of field values
    """
    with arcpy.da.SearchCursor(
        feature_class,
        fields,
        where_clause=where_clause
    ) as cursor:
        for row in cursor:
            yield row


def create_output_feature_class(
    output_path: str,
    geometry_type: str,
    spatial_reference: arcpy.SpatialReference,
    field_definitions: List[Tuple[str, str, Optional[int], Optional[int]]]
) -> str:
    """
    Create an output feature class with specified schema.
    
    Args:
        output_path: Full path for the new feature class
        geometry_type: "POLYGON", "POLYLINE", "POINT", etc.
        spatial_reference: Spatial reference object
        field_definitions: List of (name, type, precision, scale) tuples
            Type can be: "TEXT", "DOUBLE", "LONG", "DATE", "SHORT"
        
    Returns:
        Path to created feature class
    """
    import os
    
    out_dir = os.path.dirname(output_path)
    out_name = os.path.basename(output_path)
    
    # Create the feature class
    arcpy.management.CreateFeatureclass(
        out_dir,
        out_name,
        geometry_type,
        spatial_reference=spatial_reference
    )
    
    # Add fields
    for field_def in field_definitions:
        name = field_def[0]
        field_type = field_def[1]
        precision = field_def[2] if len(field_def) > 2 else None
        scale = field_def[3] if len(field_def) > 3 else None
        
        if field_type == "TEXT":
            arcpy.management.AddField(
                output_path,
                name,
                "TEXT",
                field_length=255
            )
        elif field_type == "DOUBLE":
            arcpy.management.AddField(
                output_path,
                name,
                "DOUBLE",
                field_precision=precision or 18,
                field_scale=scale or 8
            )
        elif field_type == "LONG":
            arcpy.management.AddField(
                output_path,
                name,
                "LONG"
            )
        elif field_type == "SHORT":
            arcpy.management.AddField(
                output_path,
                name,
                "SHORT"
            )
        elif field_type == "DATE":
            arcpy.management.AddField(
                output_path,
                name,
                "DATE"
            )
        else:
            arcpy.management.AddField(
                output_path,
                name,
                field_type
            )
    
    return output_path


@contextmanager
def insert_cursor(
    feature_class: str,
    fields: List[str]
):
    """
    Context manager for insert cursor.
    
    Args:
        feature_class: Path to the feature class
        fields: List of field names
        
    Yields:
        InsertCursor object
    """
    cursor = arcpy.da.InsertCursor(feature_class, fields)
    try:
        yield cursor
    finally:
        del cursor


def batch_insert_rows(
    feature_class: str,
    fields: List[str],
    rows: List[Tuple],
    batch_size: int = 1000
) -> int:
    """
    Insert multiple rows into a feature class in batches.
    
    Args:
        feature_class: Path to the feature class
        fields: List of field names
        rows: List of row tuples to insert
        batch_size: Number of rows per batch (for progress)
        
    Returns:
        Number of rows inserted
    """
    count = 0
    
    with arcpy.da.InsertCursor(feature_class, fields) as cursor:
        for row in rows:
            cursor.insertRow(row)
            count += 1
    
    return count


def validate_feature_class(
    feature_class: str,
    required_geometry_type: Optional[str] = None,
    required_fields: Optional[List[str]] = None
) -> Tuple[bool, str]:
    """
    Validate that a feature class meets requirements.
    
    Args:
        feature_class: Path to the feature class
        required_geometry_type: Expected geometry type (e.g., "Polygon")
        required_fields: List of required field names
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not arcpy.Exists(feature_class):
        return False, f"Feature class does not exist: {feature_class}"
    
    try:
        desc = arcpy.Describe(feature_class)
    except Exception as e:
        return False, f"Cannot describe feature class: {str(e)}"
    
    # Check geometry type
    if required_geometry_type:
        actual_type = desc.shapeType.lower()
        required_lower = required_geometry_type.lower()
        if actual_type != required_lower:
            return False, (
                f"Expected geometry type '{required_geometry_type}', "
                f"got '{desc.shapeType}'"
            )
    
    # Check required fields
    if required_fields:
        existing_fields = [f.name.upper() for f in desc.fields]
        for field in required_fields:
            if field.upper() not in existing_fields:
                return False, f"Required field not found: {field}"
    
    return True, ""
