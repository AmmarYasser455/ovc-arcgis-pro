# -*- coding: utf-8 -*-
"""
OVC ArcGIS Pro - Geometry Utilities

This module provides geometry helper functions for working with ArcPy
geometry objects. These utilities handle common operations like area
calculation, intersection testing, and geometry validation.
"""

import arcpy
from typing import Optional, Tuple, List, Union


def is_geometry_null(geometry) -> bool:
    """
    Check if a geometry is null or empty.
    
    Works with geometries from cursors and other sources.
    
    Args:
        geometry: An ArcPy geometry object
        
    Returns:
        True if geometry is None, null, or empty
    """
    if geometry is None:
        return True
    try:
        # Try pointCount first (works for most geometry types)
        if hasattr(geometry, 'pointCount') and geometry.pointCount == 0:
            return True
        # Only check area for polygon types (polylines have area 0 by design)
        geom_type = getattr(geometry, 'type', '').lower()
        if 'polygon' in geom_type:
            if hasattr(geometry, 'area') and geometry.area == 0:
                return True
        # For lines, check length instead
        if 'line' in geom_type:
            if hasattr(geometry, 'length') and geometry.length == 0:
                return True
        return False
    except Exception:
        return True


def get_geometry_area(geometry) -> float:
    """
    Get the area of a geometry in the geometry's native units.
    
    Args:
        geometry: An ArcPy geometry object
        
    Returns:
        Area as float, or 0.0 if geometry is None/empty
    """
    if is_geometry_null(geometry):
        return 0.0
    
    try:
        area = geometry.area
        return float(area) if area else 0.0
    except Exception:
        return 0.0


def get_intersection_geometry(
    geom_a,
    geom_b,
    dimension: int = 4
) -> Optional[arcpy.Geometry]:
    """
    Calculate the intersection of two geometries.
    
    Args:
        geom_a: First geometry
        geom_b: Second geometry
        dimension: Output dimension (1=point, 2=line, 4=polygon)
        
    Returns:
        Intersection geometry, or None if no intersection
    """
    if geom_a is None or geom_b is None:
        return None
    
    if is_geometry_null(geom_a) or is_geometry_null(geom_b):
        return None
    
    try:
        intersection = geom_a.intersect(geom_b, dimension)
        if intersection is None or is_geometry_null(intersection):
            return None
        if get_geometry_area(intersection) <= 0:
            return None
        return intersection
    except Exception:
        return None


def geometries_intersect(
    geom_a,
    geom_b
) -> bool:
    """
    Test if two geometries intersect.
    
    Args:
        geom_a: First geometry
        geom_b: Second geometry
        
    Returns:
        True if geometries intersect, False otherwise
    """
    if geom_a is None or geom_b is None:
        return False
    
    if is_geometry_null(geom_a) or is_geometry_null(geom_b):
        return False
    
    try:
        return not geom_a.disjoint(geom_b)
    except Exception:
        return False


def get_geometry_extent(geometry) -> Optional[Tuple[float, float, float, float]]:
    """
    Get the bounding box extent of a geometry.
    
    Args:
        geometry: An ArcPy geometry object
        
    Returns:
        Tuple of (xmin, ymin, xmax, ymax) or None if invalid
    """
    if is_geometry_null(geometry):
        return None
    
    try:
        extent = geometry.extent
        return (extent.XMin, extent.YMin, extent.XMax, extent.YMax)
    except Exception:
        return None


def validate_polygon_geometry(geometry) -> bool:
    """
    Validate that a geometry is a valid polygon.
    
    Args:
        geometry: An ArcPy geometry object
        
    Returns:
        True if valid polygon, False otherwise
    """
    if is_geometry_null(geometry):
        return False
    
    try:
        geom_type = geometry.type.lower()
        if geom_type not in ("polygon",):
            return False
        
        if get_geometry_area(geometry) <= 0:
            return False
        
        return True
    except Exception:
        return False


def validate_line_geometry(geometry) -> bool:
    """
    Validate that a geometry is a valid line.
    
    Args:
        geometry: An ArcPy geometry object
        
    Returns:
        True if valid line, False otherwise
    """
    if is_geometry_null(geometry):
        return False
    
    try:
        geom_type = geometry.type.lower()
        # Accept polyline, line, or any line-like geometry
        if "line" not in geom_type:
            return False
        
        if geometry.length <= 0:
            return False
        
        return True
    except Exception:
        return False


def buffer_geometry(
    geometry,
    distance: float
) -> Optional[arcpy.Geometry]:
    """
    Create a buffer around a geometry.
    
    Args:
        geometry: An ArcPy geometry object
        distance: Buffer distance in geometry's units
        
    Returns:
        Buffered geometry, or None if operation fails
    """
    if is_geometry_null(geometry):
        return None
    
    if distance <= 0:
        return geometry
    
    try:
        return geometry.buffer(distance)
    except Exception:
        return None


def get_line_endpoints(geometry) -> List[arcpy.Point]:
    """
    Extract start and end points from a line geometry.
    
    Args:
        geometry: A polyline geometry
        
    Returns:
        List of endpoint Point objects
    """
    endpoints = []
    
    if is_geometry_null(geometry):
        return endpoints
    
    try:
        for part in geometry:
            if part is not None and len(part) >= 2:
                # Start point
                start_pt = part[0]
                if start_pt is not None:
                    endpoints.append(arcpy.Point(start_pt.X, start_pt.Y))
                
                # End point
                end_pt = part[len(part) - 1]
                if end_pt is not None:
                    endpoints.append(arcpy.Point(end_pt.X, end_pt.Y))
    except Exception:
        pass
    
    return endpoints


def point_distance(point_a: arcpy.Point, point_b: arcpy.Point) -> float:
    """
    Calculate Euclidean distance between two points.
    
    Args:
        point_a: First point
        point_b: Second point
        
    Returns:
        Distance as float
    """
    if point_a is None or point_b is None:
        return float('inf')
    
    try:
        dx = point_a.X - point_b.X
        dy = point_a.Y - point_b.Y
        return (dx * dx + dy * dy) ** 0.5
    except Exception:
        return float('inf')


def ensure_projected_crs(
    spatial_reference: arcpy.SpatialReference
) -> bool:
    """
    Check if a spatial reference is a projected coordinate system.
    
    Args:
        spatial_reference: An ArcPy SpatialReference object
        
    Returns:
        True if projected (meters/feet), False if geographic
    """
    if spatial_reference is None:
        return False
    
    try:
        # Check if it's a projected coordinate system
        return spatial_reference.type == "Projected"
    except Exception:
        return False


def get_unit_conversion_factor(
    spatial_reference: arcpy.SpatialReference
) -> float:
    """
    Get conversion factor to convert linear units to meters.
    
    Args:
        spatial_reference: An ArcPy SpatialReference object
        
    Returns:
        Conversion factor (multiply by this to get meters)
    """
    if spatial_reference is None:
        return 1.0
    
    try:
        # metersPerUnit property gives the conversion factor
        return spatial_reference.metersPerUnit
    except Exception:
        return 1.0
