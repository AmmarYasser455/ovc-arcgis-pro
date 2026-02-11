# -*- coding: utf-8 -*-
"""
OVC ArcGIS Pro - Building-Road Conflict Detection

This module detects buildings that overlap with buffered road geometries,
indicating potential conflicts or digitization errors.
"""

import arcpy
import os
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# Import from sibling packages
import sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from core.config import RoadConflictConfig
from core.geometry import (
    get_geometry_area,
    get_intersection_geometry,
    get_geometry_extent,
    validate_polygon_geometry,
    validate_line_geometry,
    buffer_geometry,
    ensure_projected_crs,
    get_unit_conversion_factor,
    is_geometry_null
)
from core.spatial_ops import SpatialIndex, extents_intersect
from utils.cursor_helpers import (
    get_oid_field,
    get_spatial_reference,
    read_geometries_to_dict,
    validate_feature_class
)
from utils.messaging import (
    ToolMessenger,
    ProgressTracker,
    format_number,
    format_area,
    get_timestamp
)


@dataclass
class ConflictResult:
    """Result of a building-road conflict detection."""
    building_fid: int
    road_fid: int
    conflict_geometry: arcpy.Geometry
    conflict_area: float
    road_buffer_distance: float


class BuildingRoadConflictChecker:
    """
    Detects buildings that conflict with road buffers.
    
    This class identifies buildings that overlap with buffered road
    geometries, which may indicate:
    - Buildings encroaching on road right-of-way
    - Digitization errors
    - Missing setback compliance
    """
    
    def __init__(
        self,
        config: Optional[RoadConflictConfig] = None,
        verbose: bool = False
    ):
        """
        Initialize the conflict checker.
        
        Args:
            config: Road conflict detection configuration
            verbose: Enable verbose logging
        """
        self.config = config or RoadConflictConfig()
        self.verbose = verbose
        self.messenger = ToolMessenger("BuildingRoadConflict")
    
    def check_conflicts(
        self,
        building_features: str,
        road_features: str,
        output_features: str,
        buffer_distance: Optional[float] = None,
        min_conflict_area: Optional[float] = None
    ) -> Tuple[int, Dict[str, int]]:
        """
        Run conflict detection between buildings and roads.
        
        Args:
            building_features: Path to building polygon features
            road_features: Path to road line features
            output_features: Path for output conflict feature class
            buffer_distance: Override road buffer distance (meters)
            min_conflict_area: Override minimum conflict area (sq meters)
            
        Returns:
            Tuple of (total_conflicts, stats_dict)
        """
        self.messenger.start_timer()
        
        # Validate building input
        self.messenger.info("Validating building features...")
        is_valid, error_msg = validate_feature_class(
            building_features,
            required_geometry_type="Polygon"
        )
        if not is_valid:
            raise ValueError(f"Invalid building input: {error_msg}")
        
        # Validate road input
        self.messenger.info("Validating road features...")
        is_valid, error_msg = validate_feature_class(
            road_features,
            required_geometry_type="Polyline"
        )
        if not is_valid:
            raise ValueError(f"Invalid road input: {error_msg}")
        
        # Get spatial references
        building_sr = get_spatial_reference(building_features)
        road_sr = get_spatial_reference(road_features)
        
        # Check if they match
        if building_sr.factoryCode != road_sr.factoryCode:
            self.messenger.warning(
                "Building and road layers have different coordinate systems. "
                "Roads will be projected to match buildings."
            )
        
        original_sr = building_sr
        working_buildings = building_features
        working_roads = road_features
        temp_buildings = None
        temp_roads = None
        
        # Auto-reproject if geographic coordinates
        if not ensure_projected_crs(building_sr):
            self.messenger.info(
                "Input is in geographic coordinates. "
                "Auto-projecting to UTM for accurate calculations..."
            )
            # Get centroid to determine UTM zone
            desc = arcpy.Describe(building_features)
            extent = desc.extent
            center_lon = (extent.XMin + extent.XMax) / 2
            center_lat = (extent.YMin + extent.YMax) / 2
            
            # Calculate UTM zone
            utm_zone = int((center_lon + 180) / 6) + 1
            if center_lat >= 0:
                epsg = 32600 + utm_zone
            else:
                epsg = 32700 + utm_zone
            
            utm_sr = arcpy.SpatialReference(epsg)
            self.messenger.info(f"Using UTM Zone {utm_zone} (EPSG:{epsg})")
            
            # Project to scratch geodatabase (in_memory doesn't support Project)
            scratch_gdb = arcpy.env.scratchGDB
            
            # Project buildings
            temp_buildings = os.path.join(scratch_gdb, "ovc_temp_buildings")
            if arcpy.Exists(temp_buildings):
                arcpy.management.Delete(temp_buildings)
            arcpy.management.Project(building_features, temp_buildings, utm_sr)
            working_buildings = temp_buildings
            
            # Project roads
            temp_roads = os.path.join(scratch_gdb, "ovc_temp_roads")
            if arcpy.Exists(temp_roads):
                arcpy.management.Delete(temp_roads)
            arcpy.management.Project(road_features, temp_roads, utm_sr)
            working_roads = temp_roads
            
            building_sr = utm_sr
        
        # Get effective parameters
        effective_buffer = buffer_distance or self.config.buffer_distance_m
        effective_min_area = min_conflict_area or self.config.min_overlap_area_m2
        
        self.messenger.info(f"Road buffer distance: {effective_buffer:.1f} m")
        self.messenger.info(f"Minimum conflict area: {format_area(effective_min_area)}")
        
        # Read buildings
        self.messenger.info("Reading building features...")
        buildings = read_geometries_to_dict(working_buildings)
        self.messenger.info(f"Loaded {format_number(len(buildings), 0)} buildings")
        
        # Read roads
        self.messenger.info("Reading road features...")
        roads = read_geometries_to_dict(working_roads)
        self.messenger.info(f"Loaded {format_number(len(roads), 0)} roads")
        
        if len(buildings) == 0 or len(roads) == 0:
            self.messenger.warning("No features to process")
            self._cleanup_temp([temp_buildings, temp_roads])
            return 0, {"buildings": len(buildings), "roads": len(roads), "conflicts": 0}
        
        # Create output
        self.messenger.info("Creating output feature class...")
        self._create_output_schema(output_features, original_sr)
        
        # Find conflicts
        self.messenger.info("Detecting conflicts...")
        conflicts = self._find_conflicts(
            buildings,
            roads,
            effective_buffer,
            effective_min_area
        )
        
        # Write results
        self.messenger.info("Writing results...")
        conflict_count = self._write_conflicts(
            output_features,
            conflicts,
            original_sr,
            reproject_from=building_sr if temp_buildings else None
        )
        
        # Cleanup
        self._cleanup_temp([temp_buildings, temp_roads])
        
        # Stats
        stats = {
            "buildings": len(buildings),
            "roads": len(roads),
            "conflicts": conflict_count,
            "buffer_distance": effective_buffer
        }
        
        # Report summary
        self.messenger.report_summary(
            total_features=len(buildings),
            violations_found=conflict_count,
            additional_stats={
                "Roads analyzed": len(roads),
                "Buffer distance": f"{effective_buffer:.1f} m"
            }
        )
        
        return conflict_count, stats
    
    def _create_output_schema(
        self,
        output_path: str,
        spatial_reference: arcpy.SpatialReference
    ) -> None:
        """Create the output feature class with proper schema."""
        
        out_dir = os.path.dirname(output_path)
        out_name = os.path.basename(output_path)
        
        if arcpy.Exists(output_path):
            arcpy.management.Delete(output_path)
        
        arcpy.management.CreateFeatureclass(
            out_dir,
            out_name,
            "POLYGON",
            spatial_reference=spatial_reference
        )
        
        # Add fields
        arcpy.management.AddField(output_path, "BUILDING_FID", "LONG")
        arcpy.management.AddField(output_path, "ROAD_FID", "LONG")
        arcpy.management.AddField(
            output_path, "CONFLICT_AREA_M2", "DOUBLE",
            field_precision=18, field_scale=4
        )
        arcpy.management.AddField(
            output_path, "BUFFER_DIST_M", "DOUBLE",
            field_precision=10, field_scale=2
        )
        arcpy.management.AddField(
            output_path, "CHECK_TIME", "TEXT",
            field_length=30
        )
    
    def _find_conflicts(
        self,
        buildings: Dict[int, arcpy.Geometry],
        roads: Dict[int, arcpy.Geometry],
        buffer_distance: float,
        min_area: float
    ) -> List[ConflictResult]:
        """Find all building-road buffer conflicts using spatial indexing."""
        
        results = []
        
        # Build spatial index for buildings (grid-based)
        # Adaptive spatial index: cell size based on average building extent
        self.messenger.info("Building spatial index for buildings...")
        total_w = 0
        total_h = 0
        building_extents = {}
        for fid, geom in buildings.items():
            extent = get_geometry_extent(geom)
            if extent:
                building_extents[fid] = extent
                total_w += extent[2] - extent[0]
                total_h += extent[3] - extent[1]
        avg_sz = max((total_w + total_h) / (2 * max(len(building_extents), 1)), 10.0)
        cell_sz = max(avg_sz * 3, buffer_distance * 2)
        building_index = SpatialIndex(cell_size=cell_sz)
        
        for fid, geom in buildings.items():
            extent = get_geometry_extent(geom)
            if extent:
                building_extents[fid] = extent
                building_index.insert(fid, geom)  # Pass geometry, not extent
        
        # Pre-buffer all roads in batch for better performance
        self.messenger.info("Buffering roads...")
        buffered_roads = {}
        buffered_extents = {}
        for road_fid, road_geom in roads.items():
            if not validate_line_geometry(road_geom):
                continue
            buffered = buffer_geometry(road_geom, buffer_distance)
            if buffered is None:
                continue
            bext = get_geometry_extent(buffered)
            if bext is None:
                continue
            buffered_roads[road_fid] = buffered
            buffered_extents[road_fid] = bext
        
        self.messenger.info(
            f"Buffered {format_number(len(buffered_roads), 0)} of "
            f"{format_number(len(roads), 0)} roads"
        )
        
        # Process each buffered road against the building spatial index
        total_roads = len(buffered_roads)
        progress = ProgressTracker(
            "Checking road conflicts",
            total_roads,
            step_size=max(1, total_roads // 20)
        )
        progress.start()
        
        for idx, (road_fid, buffered) in enumerate(buffered_roads.items()):
            progress.update(idx)
            
            buffer_extent = buffered_extents[road_fid]
            
            # Query spatial index for candidate buildings
            candidates = building_index.query_by_extent(buffer_extent)
            
            for building_fid in candidates:
                building_geom = buildings.get(building_fid)
                if building_geom is None:
                    continue
                
                if not validate_polygon_geometry(building_geom):
                    continue
                
                building_extent = building_extents.get(building_fid)
                if building_extent is None:
                    continue
                
                # Quick extent check
                if not extents_intersect(buffer_extent, building_extent):
                    continue
                
                # Detailed intersection
                intersection = get_intersection_geometry(
                    building_geom, buffered, dimension=4
                )
                if intersection is None:
                    continue
                
                conflict_area = get_geometry_area(intersection)
                if conflict_area < min_area:
                    continue
                
                results.append(ConflictResult(
                    building_fid=building_fid,
                    road_fid=road_fid,
                    conflict_geometry=intersection,
                    conflict_area=conflict_area,
                    road_buffer_distance=buffer_distance
                ))
        
        progress.finish()
        return results
    
    def _write_conflicts(
        self,
        output_path: str,
        conflicts: List[ConflictResult],
        spatial_reference: arcpy.SpatialReference,
        reproject_from: Optional[arcpy.SpatialReference] = None
    ) -> int:
        """Write conflict results to output feature class."""
        
        if not conflicts:
            self.messenger.info("No conflicts to write")
            return 0
        
        fields = [
            "SHAPE@",
            "BUILDING_FID",
            "ROAD_FID",
            "CONFLICT_AREA_M2",
            "BUFFER_DIST_M",
            "CHECK_TIME"
        ]
        
        timestamp = get_timestamp()
        count = 0
        
        with arcpy.da.InsertCursor(output_path, fields) as cursor:
            for conflict in conflicts:
                geom = conflict.conflict_geometry
                
                if reproject_from is not None:
                    try:
                        geom = geom.projectAs(spatial_reference)
                    except Exception:
                        pass
                
                row = (
                    geom,
                    conflict.building_fid,
                    conflict.road_fid,
                    conflict.conflict_area,
                    conflict.road_buffer_distance,
                    timestamp
                )
                cursor.insertRow(row)
                count += 1
        
        return count
    
    def _cleanup_temp(self, temp_paths: List[Optional[str]]) -> None:
        """Clean up temporary datasets."""
        for path in temp_paths:
            if path and arcpy.Exists(path):
                try:
                    arcpy.management.Delete(path)
                except Exception:
                    pass


def run_building_road_conflict_check(
    building_features: str,
    road_features: str,
    output_features: str,
    buffer_distance: float = 5.0,
    min_conflict_area: float = 0.5
) -> Tuple[int, Dict[str, int]]:
    """
    Convenience function to run building-road conflict check.
    
    Args:
        building_features: Path to building polygon features
        road_features: Path to road line features
        output_features: Path for output conflict features
        buffer_distance: Road buffer distance in meters
        min_conflict_area: Minimum conflict area in square meters
        
    Returns:
        Tuple of (conflict_count, stats_dict)
    """
    config = RoadConflictConfig(
        buffer_distance_m=buffer_distance,
        min_overlap_area_m2=min_conflict_area
    )
    
    checker = BuildingRoadConflictChecker(config=config)
    
    return checker.check_conflicts(
        building_features=building_features,
        road_features=road_features,
        output_features=output_features,
        buffer_distance=buffer_distance,
        min_conflict_area=min_conflict_area
    )
