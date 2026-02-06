# -*- coding: utf-8 -*-
"""
OVC ArcGIS Pro - Core Spatial Operations

This module provides high-level spatial analysis operations used by
the QC checks. These operations handle the core overlap detection
and spatial relationship analysis.
"""

import arcpy
from typing import List, Dict, Tuple, Optional, Generator
from dataclasses import dataclass

from core.geometry import (
    get_geometry_area,
    get_intersection_geometry,
    geometries_intersect,
    get_geometry_extent,
    validate_polygon_geometry,
    is_geometry_null
)


@dataclass
class OverlapResult:
    """Result of an overlap detection between two features."""
    fid_a: int
    fid_b: int
    overlap_geometry: arcpy.Geometry
    overlap_area: float
    overlap_ratio: float
    overlap_type: str


class SpatialIndex:
    """
    Simple spatial index using extent-based filtering.
    
    Uses a grid-based approach to reduce the number of geometry
    comparisons needed for overlap detection.
    """
    
    def __init__(self, cell_size: float = 100.0):
        """
        Initialize spatial index.
        
        Args:
            cell_size: Grid cell size in map units
        """
        self.cell_size = cell_size
        self.grid: Dict[Tuple[int, int], List[int]] = {}
        self.geometries: Dict[int, arcpy.Geometry] = {}
        self.extents: Dict[int, Tuple[float, float, float, float]] = {}
    
    def insert(self, fid: int, geometry) -> None:
        """
        Insert a feature into the spatial index.
        
        Args:
            fid: Feature ID
            geometry: Feature geometry
        """
        if is_geometry_null(geometry):
            return
        
        extent = get_geometry_extent(geometry)
        if extent is None:
            return
        
        self.geometries[fid] = geometry
        self.extents[fid] = extent
        
        # Calculate grid cells that this extent overlaps
        xmin, ymin, xmax, ymax = extent
        col_min = int(xmin // self.cell_size)
        col_max = int(xmax // self.cell_size)
        row_min = int(ymin // self.cell_size)
        row_max = int(ymax // self.cell_size)
        
        for col in range(col_min, col_max + 1):
            for row in range(row_min, row_max + 1):
                key = (col, row)
                if key not in self.grid:
                    self.grid[key] = []
                self.grid[key].append(fid)
    
    def query_candidates(self, fid: int) -> List[int]:
        """
        Find candidate features that may intersect with the given feature.
        
        Args:
            fid: Feature ID to query
            
        Returns:
            List of candidate feature IDs
        """
        if fid not in self.extents:
            return []
        
        extent = self.extents[fid]
        xmin, ymin, xmax, ymax = extent
        
        col_min = int(xmin // self.cell_size)
        col_max = int(xmax // self.cell_size)
        row_min = int(ymin // self.cell_size)
        row_max = int(ymax // self.cell_size)
        
        candidates = set()
        for col in range(col_min, col_max + 1):
            for row in range(row_min, row_max + 1):
                key = (col, row)
                if key in self.grid:
                    candidates.update(self.grid[key])
        
        # Remove self from candidates
        candidates.discard(fid)
        
        return list(candidates)
    
    def query_by_extent(self, extent: Tuple[float, float, float, float]) -> List[int]:
        """
        Find candidate features that may intersect with the given extent.
        
        Args:
            extent: Tuple of (xmin, ymin, xmax, ymax)
            
        Returns:
            List of candidate feature IDs
        """
        xmin, ymin, xmax, ymax = extent
        
        col_min = int(xmin // self.cell_size)
        col_max = int(xmax // self.cell_size)
        row_min = int(ymin // self.cell_size)
        row_max = int(ymax // self.cell_size)
        
        candidates = set()
        for col in range(col_min, col_max + 1):
            for row in range(row_min, row_max + 1):
                key = (col, row)
                if key in self.grid:
                    candidates.update(self.grid[key])
        
        return list(candidates)


def extents_intersect(
    extent_a: Tuple[float, float, float, float],
    extent_b: Tuple[float, float, float, float]
) -> bool:
    """
    Quick check if two bounding box extents intersect.
    
    Args:
        extent_a: (xmin, ymin, xmax, ymax) of first feature
        extent_b: (xmin, ymin, xmax, ymax) of second feature
        
    Returns:
        True if extents overlap
    """
    return not (
        extent_a[2] < extent_b[0] or  # a.xmax < b.xmin
        extent_a[0] > extent_b[2] or  # a.xmin > b.xmax
        extent_a[3] < extent_b[1] or  # a.ymax < b.ymin
        extent_a[1] > extent_b[3]     # a.ymin > b.ymax
    )


def classify_overlap(
    overlap_ratio: float,
    duplicate_threshold: float = 0.90,
    partial_threshold: float = 0.50
) -> str:
    """
    Classify an overlap based on the overlap ratio.
    
    Args:
        overlap_ratio: Ratio of overlap area to smaller feature area
        duplicate_threshold: Minimum ratio for duplicate classification
        partial_threshold: Minimum ratio for partial classification
        
    Returns:
        Classification string: "DUPLICATE", "PARTIAL", or "SLIVER"
    """
    if overlap_ratio >= duplicate_threshold:
        return "DUPLICATE"
    elif overlap_ratio >= partial_threshold:
        return "PARTIAL"
    else:
        return "SLIVER"


def find_pairwise_overlaps(
    features: Dict[int, arcpy.Geometry],
    min_overlap_area: float = 1.0,
    duplicate_threshold: float = 0.90,
    partial_threshold: float = 0.50,
    progress_callback: Optional[callable] = None
) -> Generator[OverlapResult, None, None]:
    """
    Find all pairwise overlaps between polygon features.
    
    Uses spatial indexing to minimize geometry comparisons.
    
    Args:
        features: Dictionary mapping FID to geometry
        min_overlap_area: Minimum overlap area to report (sq map units)
        duplicate_threshold: Ratio threshold for duplicate classification
        partial_threshold: Ratio threshold for partial classification
        progress_callback: Optional callback(current, total) for progress
        
    Yields:
        OverlapResult objects for each detected overlap
    """
    if not features:
        return
    
    # Build spatial index
    # Estimate cell size based on average feature extent
    extents = {}
    total_width = 0
    total_height = 0
    
    for fid, geom in features.items():
        extent = get_geometry_extent(geom)
        if extent:
            extents[fid] = extent
            total_width += extent[2] - extent[0]
            total_height += extent[3] - extent[1]
    
    if not extents:
        return
    
    avg_size = max((total_width + total_height) / (2 * len(extents)), 10.0)
    cell_size = avg_size * 2  # Use 2x average feature size as cell size
    
    sindex = SpatialIndex(cell_size=cell_size)
    for fid, geom in features.items():
        sindex.insert(fid, geom)
    
    # Track processed pairs to avoid duplicates
    processed_pairs = set()
    fids = list(features.keys())
    total = len(fids)
    
    for idx, fid_a in enumerate(fids):
        if progress_callback:
            progress_callback(idx, total)
        
        geom_a = features[fid_a]
        if not validate_polygon_geometry(geom_a):
            continue
        
        area_a = get_geometry_area(geom_a)
        if area_a <= 0:
            continue
        
        extent_a = extents.get(fid_a)
        if extent_a is None:
            continue
        
        # Get candidates from spatial index
        candidates = sindex.query_candidates(fid_a)
        
        for fid_b in candidates:
            # Skip if already processed this pair
            pair_key = (min(fid_a, fid_b), max(fid_a, fid_b))
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)
            
            geom_b = features[fid_b]
            if not validate_polygon_geometry(geom_b):
                continue
            
            area_b = get_geometry_area(geom_b)
            if area_b <= 0:
                continue
            
            extent_b = extents.get(fid_b)
            if extent_b is None:
                continue
            
            # Quick extent check
            if not extents_intersect(extent_a, extent_b):
                continue
            
            # Detailed geometry intersection
            intersection = get_intersection_geometry(geom_a, geom_b, dimension=4)
            if intersection is None:
                continue
            
            overlap_area = get_geometry_area(intersection)
            if overlap_area < min_overlap_area:
                continue
            
            # Calculate ratio based on smaller feature
            min_area = min(area_a, area_b)
            overlap_ratio = overlap_area / min_area if min_area > 0 else 0
            
            overlap_type = classify_overlap(
                overlap_ratio,
                duplicate_threshold,
                partial_threshold
            )
            
            yield OverlapResult(
                fid_a=fid_a,
                fid_b=fid_b,
                overlap_geometry=intersection,
                overlap_area=overlap_area,
                overlap_ratio=overlap_ratio,
                overlap_type=overlap_type
            )


def find_features_intersecting_buffer(
    features: Dict[int, arcpy.Geometry],
    buffer_geometry,
    min_intersection_area: float = 0.5
) -> List[Tuple[int, arcpy.Geometry, float]]:
    """
    Find features that intersect with a buffered geometry.
    
    Args:
        features: Dictionary mapping FID to polygon geometry
        buffer_geometry: The buffer geometry to test against
        min_intersection_area: Minimum intersection area to report
        
    Returns:
        List of (fid, intersection_geometry, intersection_area) tuples
    """
    results = []
    
    if is_geometry_null(buffer_geometry):
        return results
    
    buffer_extent = get_geometry_extent(buffer_geometry)
    if buffer_extent is None:
        return results
    
    for fid, geom in features.items():
        if not validate_polygon_geometry(geom):
            continue
        
        feat_extent = get_geometry_extent(geom)
        if feat_extent is None:
            continue
        
        # Quick extent check
        if not extents_intersect(buffer_extent, feat_extent):
            continue
        
        # Detailed intersection
        intersection = get_intersection_geometry(geom, buffer_geometry, dimension=4)
        if intersection is None:
            continue
        
        inter_area = get_geometry_area(intersection)
        if inter_area >= min_intersection_area:
            results.append((fid, intersection, inter_area))
    
    return results
