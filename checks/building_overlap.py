# -*- coding: utf-8 -*-
"""
OVC ArcGIS Pro - Building Overlap Detection

This module implements the core building overlap detection logic,
finding polygon features that overlap with each other.
"""

import arcpy
import os
import datetime
from typing import Dict, List, Tuple, Optional

# Import from sibling packages (relative to toolbox location)
import sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from core.config import OverlapConfig, OutputConfig, DEFAULT_OUTPUT_CONFIG
from core.geometry import (
    get_geometry_area,
    get_intersection_geometry,
    validate_polygon_geometry,
    get_geometry_extent,
    ensure_projected_crs,
    get_unit_conversion_factor
)
from core.spatial_ops import (
    SpatialIndex,
    extents_intersect,
    classify_overlap,
    OverlapResult
)
from utils.cursor_helpers import (
    get_oid_field,
    get_spatial_reference,
    count_features,
    read_geometries_to_dict,
    create_output_feature_class,
    validate_feature_class
)
from utils.messaging import (
    ToolMessenger,
    ProgressTracker,
    format_number,
    format_area,
    get_timestamp
)


class BuildingOverlapChecker:
    """
    Detects overlapping polygon features.
    
    This class implements the core overlap detection algorithm,
    finding pairs of features that share common area above a
    specified threshold.
    """
    
    def __init__(
        self,
        config: Optional[OverlapConfig] = None,
        output_config: Optional[OutputConfig] = None,
        verbose: bool = False
    ):
        """
        Initialize the overlap checker.
        
        Args:
            config: Overlap detection configuration
            output_config: Output field configuration
            verbose: Enable verbose logging
        """
        self.config = config or OverlapConfig()
        self.output_config = output_config or DEFAULT_OUTPUT_CONFIG
        self.verbose = verbose
        self.messenger = ToolMessenger("BuildingOverlap")
    
    def check_overlaps(
        self,
        input_features: str,
        output_features: str,
        min_overlap_area: Optional[float] = None,
        use_selected: bool = False
    ) -> Tuple[int, Dict[str, int]]:
        """
        Run overlap detection on input features.
        
        Args:
            input_features: Path to input polygon feature class/layer
            output_features: Path for output overlap feature class
            min_overlap_area: Override minimum overlap area (sq map units)
            use_selected: Only process selected features
            
        Returns:
            Tuple of (total_overlaps, stats_dict)
        """
        self.messenger.start_timer()
        
        # Validate input
        self.messenger.info("Validating input features...")
        is_valid, error_msg = validate_feature_class(
            input_features,
            required_geometry_type="Polygon"
        )
        if not is_valid:
            raise ValueError(f"Invalid input: {error_msg}")
        
        # Get spatial reference
        spatial_ref = get_spatial_reference(input_features)
        original_sr = spatial_ref
        working_fc = input_features
        temp_projected = None
        
        # Auto-reproject if geographic coordinates
        if not ensure_projected_crs(spatial_ref):
            self.messenger.info(
                "Input is in geographic coordinates. "
                "Auto-projecting to UTM for accurate area calculations..."
            )
            # Get centroid to determine UTM zone
            desc = arcpy.Describe(input_features)
            extent = desc.extent
            center_lon = (extent.XMin + extent.XMax) / 2
            center_lat = (extent.YMin + extent.YMax) / 2
            
            # Calculate UTM zone
            utm_zone = int((center_lon + 180) / 6) + 1
            # Determine if north or south hemisphere
            if center_lat >= 0:
                epsg = 32600 + utm_zone  # UTM North
            else:
                epsg = 32700 + utm_zone  # UTM South
            
            utm_sr = arcpy.SpatialReference(epsg)
            self.messenger.info(f"Using UTM Zone {utm_zone} (EPSG:{epsg})")
            
            # Project to scratch geodatabase (in_memory doesn't support Project)
            scratch_gdb = arcpy.env.scratchGDB
            temp_projected = os.path.join(scratch_gdb, "ovc_temp_projected")
            if arcpy.Exists(temp_projected):
                arcpy.management.Delete(temp_projected)
            
            arcpy.management.Project(input_features, temp_projected, utm_sr)
            working_fc = temp_projected
            spatial_ref = utm_sr
        
        # Get unit conversion (should be 1.0 for projected)
        units_to_meters = get_unit_conversion_factor(spatial_ref)
        
        # Determine effective minimum area
        effective_min_area = min_overlap_area
        if effective_min_area is None:
            effective_min_area = self.config.min_overlap_area_m2
        
        # For projected CRS, units are already in meters
        effective_min_area_map = effective_min_area
        
        self.messenger.info(f"Minimum overlap area: {format_area(effective_min_area)}")
        
        # Read geometries from working feature class (projected if needed)
        self.messenger.info("Reading input features...")
        
        selected_ids = None  # Initialize before conditional
        if use_selected:
            # Check if there's a selection on original input
            desc = arcpy.Describe(input_features)
            if hasattr(desc, "FIDSet") and desc.FIDSet:
                selected_ids = set(int(x) for x in desc.FIDSet.split(";") if x)
                self.messenger.info(f"Processing {len(selected_ids)} selected features")
            else:
                self.messenger.warning("No features selected, processing all features")
                use_selected = False
        
        # Read from working FC (which may be projected version)
        geometries = read_geometries_to_dict(working_fc)
        
        if use_selected and selected_ids:
            geometries = {k: v for k, v in geometries.items() if k in selected_ids}
        
        total_features = len(geometries)
        self.messenger.info(f"Loaded {format_number(total_features, 0)} features")
        
        if total_features == 0:
            self.messenger.warning("No features to process")
            # Cleanup temp data
            if temp_projected and arcpy.Exists(temp_projected):
                arcpy.management.Delete(temp_projected)
            return 0, {"total_features": 0, "overlaps": 0}
        
        # Create output feature class (use original SR so it matches input)
        self.messenger.info("Creating output feature class...")
        self._create_output_schema(output_features, original_sr)
        
        # Run overlap detection
        self.messenger.info("Detecting overlaps...")
        overlaps = self._find_overlaps(
            geometries,
            effective_min_area_map
        )
        
        # Write results (geometries need to be reprojected back if we projected)
        self.messenger.info("Writing results...")
        overlap_count = self._write_overlaps(
            output_features,
            overlaps,
            original_sr,
            reproject_from=spatial_ref if temp_projected else None
        )
        
        # Cleanup temp data
        if temp_projected and arcpy.Exists(temp_projected):
            try:
                arcpy.management.Delete(temp_projected)
            except Exception:
                pass  # Ignore cleanup errors
        
        # Calculate statistics
        stats = self._calculate_stats(overlaps)
        stats["total_features"] = total_features
        stats["overlaps"] = overlap_count
        
        # Report summary
        self.messenger.report_summary(
            total_features=total_features,
            violations_found=overlap_count,
            additional_stats={
                "Duplicate overlaps": stats.get("duplicates", 0),
                "Partial overlaps": stats.get("partials", 0),
                "Sliver overlaps": stats.get("slivers", 0),
                "Total overlap area": format_area(
                    stats.get("total_area", 0) * (units_to_meters ** 2)
                )
            }
        )
        
        return overlap_count, stats
    
    def _create_output_schema(
        self,
        output_path: str,
        spatial_reference: arcpy.SpatialReference
    ) -> None:
        """Create the output feature class with proper schema."""
        
        out_dir = os.path.dirname(output_path)
        out_name = os.path.basename(output_path)
        
        # Delete if exists
        if arcpy.Exists(output_path):
            arcpy.management.Delete(output_path)
        
        # Create feature class
        arcpy.management.CreateFeatureclass(
            out_dir,
            out_name,
            "POLYGON",
            spatial_reference=spatial_reference
        )
        
        # Add fields
        cfg = self.output_config
        
        arcpy.management.AddField(output_path, cfg.field_id_a, "LONG")
        arcpy.management.AddField(output_path, cfg.field_id_b, "LONG")
        arcpy.management.AddField(
            output_path, cfg.field_overlap_area, "DOUBLE",
            field_precision=18, field_scale=4
        )
        arcpy.management.AddField(
            output_path, cfg.field_overlap_ratio, "DOUBLE",
            field_precision=8, field_scale=4
        )
        arcpy.management.AddField(
            output_path, cfg.field_overlap_type, "TEXT",
            field_length=20
        )
        arcpy.management.AddField(
            output_path, cfg.field_timestamp, "TEXT",
            field_length=30
        )
    
    def _find_overlaps(
        self,
        geometries: Dict[int, arcpy.Geometry],
        min_area: float
    ) -> List[OverlapResult]:
        """
        Find all pairwise overlaps between geometries.
        
        Uses spatial indexing to minimize comparisons.
        """
        results = []
        
        if len(geometries) < 2:
            return results
        
        # Build spatial index
        extents = {}
        total_width = 0
        total_height = 0
        
        for fid, geom in geometries.items():
            extent = get_geometry_extent(geom)
            if extent:
                extents[fid] = extent
                total_width += extent[2] - extent[0]
                total_height += extent[3] - extent[1]
        
        if not extents:
            return results
        
        avg_size = max((total_width + total_height) / (2 * len(extents)), 10.0)
        cell_size = avg_size * 2
        
        sindex = SpatialIndex(cell_size=cell_size)
        for fid, geom in geometries.items():
            sindex.insert(fid, geom)
        
        # Set up progress
        fids = list(geometries.keys())
        total = len(fids)
        progress = ProgressTracker("Checking overlaps", total, step_size=max(1, total // 100))
        progress.start()
        
        processed_pairs = set()
        
        for idx, fid_a in enumerate(fids):
            progress.update(idx, f"Checking feature {idx + 1} of {total}")
            
            geom_a = geometries[fid_a]
            if not validate_polygon_geometry(geom_a):
                continue
            
            area_a = get_geometry_area(geom_a)
            if area_a <= 0:
                continue
            
            extent_a = extents.get(fid_a)
            if extent_a is None:
                continue
            
            candidates = sindex.query_candidates(fid_a)
            
            for fid_b in candidates:
                pair_key = (min(fid_a, fid_b), max(fid_a, fid_b))
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)
                
                geom_b = geometries[fid_b]
                if not validate_polygon_geometry(geom_b):
                    continue
                
                area_b = get_geometry_area(geom_b)
                if area_b <= 0:
                    continue
                
                extent_b = extents.get(fid_b)
                if extent_b is None:
                    continue
                
                if not extents_intersect(extent_a, extent_b):
                    continue
                
                # Get intersection
                intersection = get_intersection_geometry(geom_a, geom_b, dimension=4)
                if intersection is None:
                    continue
                
                overlap_area = get_geometry_area(intersection)
                if overlap_area < min_area:
                    continue
                
                # Calculate ratio
                min_feature_area = min(area_a, area_b)
                overlap_ratio = overlap_area / min_feature_area if min_feature_area > 0 else 0
                
                overlap_type = classify_overlap(
                    overlap_ratio,
                    self.config.duplicate_ratio_min,
                    self.config.partial_ratio_min
                )
                
                results.append(OverlapResult(
                    fid_a=fid_a,
                    fid_b=fid_b,
                    overlap_geometry=intersection,
                    overlap_area=overlap_area,
                    overlap_ratio=overlap_ratio,
                    overlap_type=overlap_type
                ))
        
        progress.finish()
        return results
    
    def _write_overlaps(
        self,
        output_path: str,
        overlaps: List[OverlapResult],
        spatial_reference: arcpy.SpatialReference,
        reproject_from: Optional[arcpy.SpatialReference] = None
    ) -> int:
        """Write overlap results to output feature class.
        
        Args:
            output_path: Path to output feature class
            overlaps: List of overlap results
            spatial_reference: Target spatial reference for output
            reproject_from: If set, reproject geometries from this SR to target
        """
        
        if not overlaps:
            self.messenger.info("No overlaps to write")
            return 0
        
        cfg = self.output_config
        fields = [
            "SHAPE@",
            cfg.field_id_a,
            cfg.field_id_b,
            cfg.field_overlap_area,
            cfg.field_overlap_ratio,
            cfg.field_overlap_type,
            cfg.field_timestamp
        ]
        
        timestamp = get_timestamp()
        count = 0
        
        with arcpy.da.InsertCursor(output_path, fields) as cursor:
            for overlap in overlaps:
                geom = overlap.overlap_geometry
                
                # Reproject geometry if needed
                if reproject_from is not None:
                    try:
                        geom = geom.projectAs(spatial_reference)
                    except Exception:
                        pass  # Keep original geometry if projection fails
                
                row = (
                    geom,
                    overlap.fid_a,
                    overlap.fid_b,
                    overlap.overlap_area,
                    overlap.overlap_ratio,
                    overlap.overlap_type,
                    timestamp
                )
                cursor.insertRow(row)
                count += 1
        
        return count
    
    def _calculate_stats(
        self,
        overlaps: List[OverlapResult]
    ) -> Dict[str, any]:
        """Calculate statistics from overlap results."""
        
        stats = {
            "duplicates": 0,
            "partials": 0,
            "slivers": 0,
            "total_area": 0.0
        }
        
        for overlap in overlaps:
            stats["total_area"] += overlap.overlap_area
            
            if overlap.overlap_type == "DUPLICATE":
                stats["duplicates"] += 1
            elif overlap.overlap_type == "PARTIAL":
                stats["partials"] += 1
            else:
                stats["slivers"] += 1
        
        return stats


def run_building_overlap_check(
    input_features: str,
    output_features: str,
    min_overlap_area: float = 1.0,
    use_selected: bool = False,
    duplicate_threshold: float = 0.90,
    partial_threshold: float = 0.50
) -> Tuple[int, Dict[str, int]]:
    """
    Convenience function to run building overlap check.
    
    Args:
        input_features: Path to input polygon features
        output_features: Path for output overlap features
        min_overlap_area: Minimum overlap area in square meters
        use_selected: Only process selected features
        duplicate_threshold: Ratio threshold for duplicate classification
        partial_threshold: Ratio threshold for partial classification
        
    Returns:
        Tuple of (overlap_count, stats_dict)
    """
    config = OverlapConfig(
        min_overlap_area_m2=min_overlap_area,
        duplicate_ratio_min=duplicate_threshold,
        partial_ratio_min=partial_threshold
    )
    
    checker = BuildingOverlapChecker(config=config)
    
    return checker.check_overlaps(
        input_features=input_features,
        output_features=output_features,
        min_overlap_area=min_overlap_area,
        use_selected=use_selected
    )
