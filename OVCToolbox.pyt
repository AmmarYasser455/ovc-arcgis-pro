# -*- coding: utf-8 -*-
"""
OVC - Overlap Violation Checker
ArcGIS Pro Python Toolbox

A production-quality spatial QC toolbox for detecting geometry violations
in polygon and line feature classes.

Author: Ammar Yasser
Version: 3.0.0
"""

import arcpy
import os
import sys

# Ensure our modules are importable
TOOLBOX_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLBOX_DIR not in sys.path:
    sys.path.insert(0, TOOLBOX_DIR)


class Toolbox(object):
    """
    Overlap Violation Checker (OVC) Toolbox.
    
    Contains spatial quality control tools for detecting geometry
    violations in feature classes.
    """
    
    def __init__(self):
        """Initialize the toolbox."""
        self.label = "Overlap Violation Checker"
        self.alias = "OVC"
        self.tools = [
            BuildingOverlapChecker,
            BuildingRoadConflictChecker,
            RoadDangleChecker,
            RoadDisconnectedChecker,
            RoadSelfIntersectionChecker,
        ]


class BuildingOverlapChecker(object):
    """
    Building Overlap Checker Tool.
    
    Detects overlapping polygon features and classifies them by
    severity (duplicate, partial, sliver).
    """
    
    def __init__(self):
        """Initialize the tool."""
        self.label = "Building Overlap Checker"
        self.description = (
            "Detects overlapping polygon features and creates an output "
            "feature class containing the overlap geometries with classification."
        )
        self.canRunInBackground = True
        self.category = "Building QC"
    
    def getParameterInfo(self):
        """
        Define the tool parameters.
        
        Returns:
            List of arcpy.Parameter objects
        """
        # Parameter 0: Input Features
        param_input = arcpy.Parameter(
            displayName="Input Features",
            name="input_features",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )
        param_input.filter.list = ["Polygon"]
        
        # Parameter 1: Minimum Overlap Area
        param_min_area = arcpy.Parameter(
            displayName="Minimum Overlap Area (square meters)",
            name="min_overlap_area",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input"
        )
        param_min_area.value = 1.0
        param_min_area.filter.type = "Range"
        param_min_area.filter.list = [0.0, 1000000.0]
        
        # Parameter 2: Process Selected Only
        param_selected = arcpy.Parameter(
            displayName="Process Selected Features Only",
            name="use_selected",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        param_selected.value = False
        
        # Parameter 3: Duplicate Threshold
        param_dup_thresh = arcpy.Parameter(
            displayName="Duplicate Threshold (overlap ratio)",
            name="duplicate_threshold",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
            category="Advanced"
        )
        param_dup_thresh.value = 0.90
        param_dup_thresh.filter.type = "Range"
        param_dup_thresh.filter.list = [0.5, 1.0]
        
        # Parameter 4: Partial Threshold
        param_partial_thresh = arcpy.Parameter(
            displayName="Partial Threshold (overlap ratio)",
            name="partial_threshold",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
            category="Advanced"
        )
        param_partial_thresh.value = 0.50
        param_partial_thresh.filter.type = "Range"
        param_partial_thresh.filter.list = [0.1, 0.9]
        
        # Parameter 5: Output Feature Class
        param_output = arcpy.Parameter(
            displayName="Output Feature Class",
            name="output_features",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output"
        )
        
        # Parameter 6: Overlap Count (derived output)
        param_count = arcpy.Parameter(
            displayName="Overlap Count",
            name="overlap_count",
            datatype="GPLong",
            parameterType="Derived",
            direction="Output"
        )
        
        return [
            param_input,
            param_min_area,
            param_selected,
            param_dup_thresh,
            param_partial_thresh,
            param_output,
            param_count
        ]
    
    def isLicensed(self):
        """Check if the tool is licensed to execute."""
        return True
    
    def updateParameters(self, parameters):
        """
        Modify parameter values and properties.
        
        Called whenever a parameter is changed.
        """
        # Auto-suggest output name based on input
        if parameters[0].altered and not parameters[5].altered:
            if parameters[0].valueAsText:
                input_name = os.path.basename(parameters[0].valueAsText)
                base_name = os.path.splitext(input_name)[0]
                # Suggest in same workspace if possible
                ws = arcpy.env.workspace or os.path.dirname(parameters[0].valueAsText)
                if not ws:
                    ws = arcpy.env.scratchGDB
                suggested_output = os.path.join(ws, f"{base_name}_overlaps")
                parameters[5].value = suggested_output
        
        return
    
    def updateMessages(self, parameters):
        """
        Validate parameters and set messages.
        
        Called after updateParameters; modify messages for validation.
        """
        # Validate duplicate threshold > partial threshold
        if parameters[3].value and parameters[4].value:
            if parameters[4].value >= parameters[3].value:
                parameters[4].setWarningMessage(
                    "Partial threshold should be less than duplicate threshold"
                )
        
        # Check input has features
        if parameters[0].valueAsText:
            try:
                count = int(arcpy.management.GetCount(parameters[0].valueAsText)[0])
                if count == 0:
                    parameters[0].setWarningMessage("Input feature class is empty")
            except Exception:
                pass
        
        return
    
    def execute(self, parameters, messages):
        """
        Execute the tool.
        
        Args:
            parameters: List of parameter objects
            messages: Message object for reporting
        """
        # Extract parameter values
        input_features = parameters[0].valueAsText
        min_overlap_area = parameters[1].value
        use_selected = parameters[2].value or False
        duplicate_threshold = parameters[3].value or 0.90
        partial_threshold = parameters[4].value or 0.50
        output_features = parameters[5].valueAsText
        
        # Import the checker module
        from checks.building_overlap import BuildingOverlapChecker as Checker
        from core.config import OverlapConfig
        
        # Create configuration
        config = OverlapConfig(
            min_overlap_area_m2=min_overlap_area,
            duplicate_ratio_min=duplicate_threshold,
            partial_ratio_min=partial_threshold
        )
        
        # Run the check
        checker = Checker(config=config)
        
        try:
            overlap_count, stats = checker.check_overlaps(
                input_features=input_features,
                output_features=output_features,
                min_overlap_area=min_overlap_area,
                use_selected=use_selected
            )
            
            # Set derived output
            parameters[6].value = overlap_count
            
            # Add result to display
            arcpy.SetParameterAsText(5, output_features)
            
        except Exception as e:
            arcpy.AddError(f"Tool execution failed: {str(e)}")
            raise
        
        return
    
    def postExecute(self, parameters):
        """
        Post-execution cleanup and actions.
        
        Called after execute completes.
        """
        # Optionally add output to current map
        try:
            output_fc = parameters[5].valueAsText
            if arcpy.Exists(output_fc):
                # Get current map
                aprx = arcpy.mp.ArcGISProject("CURRENT")
                active_map = aprx.activeMap
                if active_map:
                    # Check if not already added
                    layer_exists = any(
                        lyr.name == os.path.basename(output_fc)
                        for lyr in active_map.listLayers()
                    )
                    if not layer_exists:
                        active_map.addDataFromPath(output_fc)
        except Exception:
            # Silently handle errors in post-execute
            pass
        
        return


# Placeholder for future tools - Phase 2 & 3

class BuildingRoadConflictChecker(object):
    """
    Building-Road Conflict Checker Tool.
    
    Detects buildings that overlap with buffered road geometries.
    """
    
    def __init__(self):
        self.label = "Building-Road Conflict Checker"
        self.description = (
            "Detects buildings that overlap with buffered road geometries, "
            "indicating potential conflicts or digitization errors."
        )
        self.canRunInBackground = True
        self.category = "Building QC"
    
    def getParameterInfo(self):
        """Define the tool parameters."""
        
        # Parameter 0: Building Features
        param_buildings = arcpy.Parameter(
            displayName="Building Features",
            name="building_features",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )
        param_buildings.filter.list = ["Polygon"]
        
        # Parameter 1: Road Features
        param_roads = arcpy.Parameter(
            displayName="Road Features",
            name="road_features",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )
        param_roads.filter.list = ["Polyline"]
        
        # Parameter 2: Buffer Distance
        param_buffer = arcpy.Parameter(
            displayName="Road Buffer Distance (meters)",
            name="buffer_distance",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input"
        )
        param_buffer.value = 5.0
        param_buffer.filter.type = "Range"
        param_buffer.filter.list = [0.1, 100.0]
        
        # Parameter 3: Minimum Conflict Area
        param_min_area = arcpy.Parameter(
            displayName="Minimum Conflict Area (square meters)",
            name="min_conflict_area",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input"
        )
        param_min_area.value = 0.5
        param_min_area.filter.type = "Range"
        param_min_area.filter.list = [0.0, 10000.0]
        
        # Parameter 4: Output Feature Class
        param_output = arcpy.Parameter(
            displayName="Output Feature Class",
            name="output_features",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output"
        )
        
        # Parameter 5: Conflict Count (derived)
        param_count = arcpy.Parameter(
            displayName="Conflict Count",
            name="conflict_count",
            datatype="GPLong",
            parameterType="Derived",
            direction="Output"
        )
        
        return [
            param_buildings,
            param_roads,
            param_buffer,
            param_min_area,
            param_output,
            param_count
        ]
    
    def isLicensed(self):
        return True
    
    def updateParameters(self, parameters):
        # Auto-suggest output name
        if parameters[0].altered and not parameters[4].altered:
            if parameters[0].valueAsText:
                input_name = os.path.basename(parameters[0].valueAsText)
                base_name = os.path.splitext(input_name)[0]
                ws = arcpy.env.workspace or arcpy.env.scratchGDB
                parameters[4].value = os.path.join(ws, f"{base_name}_road_conflicts")
        return
    
    def updateMessages(self, parameters):
        return
    
    def execute(self, parameters, messages):
        """Execute the tool."""
        building_features = parameters[0].valueAsText
        road_features = parameters[1].valueAsText
        buffer_distance = parameters[2].value
        min_conflict_area = parameters[3].value or 0.5
        output_features = parameters[4].valueAsText
        
        from checks.building_road_conflict import BuildingRoadConflictChecker as Checker
        from core.config import RoadConflictConfig
        
        config = RoadConflictConfig(
            buffer_distance_m=buffer_distance,
            min_overlap_area_m2=min_conflict_area
        )
        
        checker = Checker(config=config)
        
        try:
            conflict_count, stats = checker.check_conflicts(
                building_features=building_features,
                road_features=road_features,
                output_features=output_features,
                buffer_distance=buffer_distance,
                min_conflict_area=min_conflict_area
            )
            
            parameters[5].value = conflict_count
            arcpy.SetParameterAsText(4, output_features)
            
        except Exception as e:
            arcpy.AddError(f"Tool execution failed: {str(e)}")
            raise
        
        return
    
    def postExecute(self, parameters):
        try:
            output_fc = parameters[4].valueAsText
            if arcpy.Exists(output_fc):
                aprx = arcpy.mp.ArcGISProject("CURRENT")
                active_map = aprx.activeMap
                if active_map:
                    layer_exists = any(
                        lyr.name == os.path.basename(output_fc)
                        for lyr in active_map.listLayers()
                    )
                    if not layer_exists:
                        active_map.addDataFromPath(output_fc)
        except Exception:
            pass
        return


# ─────────────────────────────────────────────────────────────────────
# ROAD QC  –  shared helpers (used by all three road tools)
# ─────────────────────────────────────────────────────────────────────

def _auto_project_roads(road_features):
    """
    If *road_features* is in a geographic CRS, project to the
    appropriate UTM zone in scratchGDB and return
    ``(working_fc, utm_sr, temp_path)``.
    If already projected, return ``(road_features, sr, None)``.
    """
    from core.geometry import ensure_projected_crs
    from utils.cursor_helpers import get_spatial_reference

    sr = get_spatial_reference(road_features)
    if ensure_projected_crs(sr):
        return road_features, sr, None

    desc = arcpy.Describe(road_features)
    ext = desc.extent
    lon = (ext.XMin + ext.XMax) / 2
    lat = (ext.YMin + ext.YMax) / 2
    zone = int((lon + 180) / 6) + 1
    epsg = (32600 if lat >= 0 else 32700) + zone
    utm_sr = arcpy.SpatialReference(epsg)

    scratch = arcpy.env.scratchGDB
    temp_fc = os.path.join(scratch, "ovc_temp_roads_proj")
    if arcpy.Exists(temp_fc):
        arcpy.management.Delete(temp_fc)
    arcpy.management.Project(road_features, temp_fc, utm_sr)
    return temp_fc, utm_sr, temp_fc


def _extract_endpoints(geom):
    """Return list of (x, y) tuples for start/end of each part."""
    endpoints = []
    for part in geom:
        if part is None or len(part) < 2:
            continue
        s = part[0]
        e = part[len(part) - 1]
        if s is not None:
            endpoints.append((s.X, s.Y))
        if e is not None:
            endpoints.append((e.X, e.Y))
    return endpoints


def _extract_vertices(geom):
    """Return list-of-parts, each part a list of (x, y)."""
    parts = []
    for part in geom:
        if part is None:
            continue
        pts = [(pt.X, pt.Y) for pt in part if pt is not None]
        if len(pts) >= 2:
            parts.append(pts)
    return parts


def _cleanup(path):
    if path and arcpy.Exists(path):
        try:
            arcpy.management.Delete(path)
        except Exception:
            pass


def _add_to_map(output_fc):
    """Try to add a feature class to the active map."""
    try:
        if arcpy.Exists(output_fc):
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            active_map = aprx.activeMap
            if active_map:
                layer_exists = any(
                    lyr.name == os.path.basename(output_fc)
                    for lyr in active_map.listLayers()
                )
                if not layer_exists:
                    active_map.addDataFromPath(output_fc)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────
# Tool 3 – Road Dangle Checker  (O(n) spatial-hash)
# ─────────────────────────────────────────────────────────────────────

class RoadDangleChecker(object):
    """
    Detects dangling endpoints in road networks — line endpoints
    that do not connect to any other road within a snap tolerance.

    Uses spatial-hash indexing for O(n) performance.
    """

    def __init__(self):
        self.label = "Road Dangle Checker"
        self.description = (
            "Detects dangling endpoints in road networks where "
            "line endpoints do not connect to any other road. "
            "Uses spatial-hash indexing for fast O(n) processing."
        )
        self.canRunInBackground = True
        self.category = "Road QC"

    def getParameterInfo(self):
        param_roads = arcpy.Parameter(
            displayName="Road Features",
            name="road_features",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
        )
        param_roads.filter.list = ["Polyline"]

        param_tol = arcpy.Parameter(
            displayName="Snap Tolerance (meters)",
            name="dangle_tolerance",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
        )
        param_tol.value = 0.5
        param_tol.filter.type = "Range"
        param_tol.filter.list = [0.01, 100.0]

        param_output = arcpy.Parameter(
            displayName="Output Feature Class",
            name="output_features",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output",
        )

        param_count = arcpy.Parameter(
            displayName="Dangle Count",
            name="dangle_count",
            datatype="GPLong",
            parameterType="Derived",
            direction="Output",
        )

        return [param_roads, param_tol, param_output, param_count]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        if parameters[0].altered and not parameters[2].altered:
            if parameters[0].valueAsText:
                base = os.path.splitext(os.path.basename(parameters[0].valueAsText))[0]
                ws = arcpy.env.workspace or arcpy.env.scratchGDB
                parameters[2].value = os.path.join(ws, f"{base}_dangles")
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        """Execute the Road Dangle Checker."""
        road_features = parameters[0].valueAsText
        tolerance = parameters[1].value or 0.5
        output_features = parameters[2].valueAsText

        from checks.road_qc.engine import find_dangles
        from core.geometry import validate_line_geometry
        from utils.cursor_helpers import (
            read_geometries_to_dict, get_spatial_reference, validate_feature_class,
        )
        from utils.messaging import ToolMessenger, format_number

        messenger = ToolMessenger("RoadDangle")
        messenger.start_timer()

        # Validate
        ok, err = validate_feature_class(road_features, required_geometry_type="Polyline")
        if not ok:
            arcpy.AddError(f"Invalid input: {err}")
            return

        # Auto-project if geographic
        working_fc, proj_sr, temp_fc = _auto_project_roads(road_features)
        if temp_fc:
            messenger.info(f"Auto-projected to UTM (EPSG:{proj_sr.factoryCode})")

        # Read projected geometries for analysis
        proj_roads = read_geometries_to_dict(working_fc)
        messenger.info(f"Loaded {format_number(len(proj_roads), 0)} road segments")

        # Read original geometries for correct output coordinates
        orig_roads = proj_roads if temp_fc is None else read_geometries_to_dict(road_features)

        # Build endpoint dict (projected coords for analysis)
        ep_dict = {}
        for fid, geom in proj_roads.items():
            if not validate_line_geometry(geom):
                continue
            ep_dict[fid] = _extract_endpoints(geom)

        total_eps = sum(len(v) for v in ep_dict.values())
        messenger.info(f"Collected {format_number(total_eps, 0)} endpoints")

        # Run spatial-hash dangle detection
        dangles = find_dangles(ep_dict, tolerance)
        messenger.info(f"Found {format_number(len(dangles), 0)} dangling endpoints")

        # Build original-CRS endpoint map for output
        orig_ep_dict = {}
        for fid, geom in orig_roads.items():
            if fid in ep_dict:
                orig_ep_dict[fid] = _extract_endpoints(geom)

        # Write output in ORIGINAL CRS
        out_dir = os.path.dirname(output_features)
        out_name = os.path.basename(output_features)
        original_sr = get_spatial_reference(road_features)

        if arcpy.Exists(output_features):
            arcpy.management.Delete(output_features)
        arcpy.management.CreateFeatureclass(out_dir, out_name, "POINT", spatial_reference=original_sr)
        arcpy.management.AddField(output_features, "ROAD_FID", "LONG")

        count = 0
        with arcpy.da.InsertCursor(output_features, ["SHAPE@XY", "ROAD_FID"]) as cur:
            for fid, _, _, ep_idx in dangles:
                orig_pts = orig_ep_dict.get(fid)
                if orig_pts and ep_idx < len(orig_pts):
                    x, y = orig_pts[ep_idx]
                    cur.insertRow(((x, y), fid))
                    count += 1

        _cleanup(temp_fc)

        parameters[3].value = count
        arcpy.SetParameterAsText(2, output_features)

        messenger.report_summary(
            total_features=len(proj_roads),
            violations_found=count,
            additional_stats={"Tolerance": f"{tolerance} m"},
        )

    def postExecute(self, parameters):
        _add_to_map(parameters[2].valueAsText)


# ─────────────────────────────────────────────────────────────────────
# Tool 4 – Road Disconnected Segment Checker
# ─────────────────────────────────────────────────────────────────────

class RoadDisconnectedChecker(object):
    """
    Detects completely disconnected road segments — segments whose
    EVERY endpoint is a dangle (no connection to the rest of the
    network).
    """

    def __init__(self):
        self.label = "Road Disconnected Segment Checker"
        self.description = (
            "Finds road segments that are completely isolated from "
            "the network — neither start nor end connects to any "
            "other road within the snap tolerance."
        )
        self.canRunInBackground = True
        self.category = "Road QC"

    def getParameterInfo(self):
        param_roads = arcpy.Parameter(
            displayName="Road Features",
            name="road_features",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
        )
        param_roads.filter.list = ["Polyline"]

        param_tol = arcpy.Parameter(
            displayName="Snap Tolerance (meters)",
            name="dangle_tolerance",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input",
        )
        param_tol.value = 0.5
        param_tol.filter.type = "Range"
        param_tol.filter.list = [0.01, 100.0]

        param_output = arcpy.Parameter(
            displayName="Output Feature Class",
            name="output_features",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output",
        )

        param_count = arcpy.Parameter(
            displayName="Disconnected Count",
            name="disconnected_count",
            datatype="GPLong",
            parameterType="Derived",
            direction="Output",
        )

        return [param_roads, param_tol, param_output, param_count]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        if parameters[0].altered and not parameters[2].altered:
            if parameters[0].valueAsText:
                base = os.path.splitext(os.path.basename(parameters[0].valueAsText))[0]
                ws = arcpy.env.workspace or arcpy.env.scratchGDB
                parameters[2].value = os.path.join(ws, f"{base}_disconnected")
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        """Execute the Road Disconnected Segment Checker."""
        road_features = parameters[0].valueAsText
        tolerance = parameters[1].value or 0.5
        output_features = parameters[2].valueAsText

        from checks.road_qc.engine import find_disconnected
        from core.geometry import validate_line_geometry
        from utils.cursor_helpers import (
            read_geometries_to_dict, get_spatial_reference, validate_feature_class,
        )
        from utils.messaging import ToolMessenger, format_number

        messenger = ToolMessenger("RoadDisconnected")
        messenger.start_timer()

        ok, err = validate_feature_class(road_features, required_geometry_type="Polyline")
        if not ok:
            arcpy.AddError(f"Invalid input: {err}")
            return

        working_fc, proj_sr, temp_fc = _auto_project_roads(road_features)
        if temp_fc:
            messenger.info(f"Auto-projected to UTM (EPSG:{proj_sr.factoryCode})")

        proj_roads = read_geometries_to_dict(working_fc)
        messenger.info(f"Loaded {format_number(len(proj_roads), 0)} road segments")

        orig_roads = proj_roads if temp_fc is None else read_geometries_to_dict(road_features)

        ep_dict = {}
        for fid, geom in proj_roads.items():
            if not validate_line_geometry(geom):
                continue
            ep_dict[fid] = _extract_endpoints(geom)

        disconnected_fids, _ = find_disconnected(ep_dict, tolerance)
        messenger.info(
            f"Found {format_number(len(disconnected_fids), 0)} disconnected segments"
        )

        # Write output — copy the original line geometries for disconnected roads
        out_dir = os.path.dirname(output_features)
        out_name = os.path.basename(output_features)
        original_sr = get_spatial_reference(road_features)

        if arcpy.Exists(output_features):
            arcpy.management.Delete(output_features)
        arcpy.management.CreateFeatureclass(
            out_dir, out_name, "POLYLINE", spatial_reference=original_sr,
        )
        arcpy.management.AddField(output_features, "ROAD_FID", "LONG")

        disc_set = set(disconnected_fids)
        count = 0
        with arcpy.da.InsertCursor(output_features, ["SHAPE@", "ROAD_FID"]) as cur:
            for fid in disconnected_fids:
                geom = orig_roads.get(fid)
                if geom is not None:
                    cur.insertRow((geom, fid))
                    count += 1

        _cleanup(temp_fc)

        parameters[3].value = count
        arcpy.SetParameterAsText(2, output_features)

        messenger.report_summary(
            total_features=len(proj_roads),
            violations_found=count,
            additional_stats={"Tolerance": f"{tolerance} m"},
        )

    def postExecute(self, parameters):
        _add_to_map(parameters[2].valueAsText)


# ─────────────────────────────────────────────────────────────────────
# Tool 5 – Road Self-Intersection Checker
# ─────────────────────────────────────────────────────────────────────

class RoadSelfIntersectionChecker(object):
    """
    Detects road segments that cross themselves.
    """

    def __init__(self):
        self.label = "Road Self-Intersection Checker"
        self.description = (
            "Finds road segments that cross themselves — a common "
            "digitization error indicating geometry corruption."
        )
        self.canRunInBackground = True
        self.category = "Road QC"

    def getParameterInfo(self):
        param_roads = arcpy.Parameter(
            displayName="Road Features",
            name="road_features",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
        )
        param_roads.filter.list = ["Polyline"]

        param_output = arcpy.Parameter(
            displayName="Output Feature Class",
            name="output_features",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output",
        )

        param_count = arcpy.Parameter(
            displayName="Self-Intersection Count",
            name="selfx_count",
            datatype="GPLong",
            parameterType="Derived",
            direction="Output",
        )

        return [param_roads, param_output, param_count]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        if parameters[0].altered and not parameters[1].altered:
            if parameters[0].valueAsText:
                base = os.path.splitext(os.path.basename(parameters[0].valueAsText))[0]
                ws = arcpy.env.workspace or arcpy.env.scratchGDB
                parameters[1].value = os.path.join(ws, f"{base}_self_intersections")
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        """Execute the Road Self-Intersection Checker."""
        road_features = parameters[0].valueAsText
        output_features = parameters[1].valueAsText

        from checks.road_qc.engine import find_self_intersections
        from core.geometry import validate_line_geometry
        from utils.cursor_helpers import (
            read_geometries_to_dict, get_spatial_reference, validate_feature_class,
        )
        from utils.messaging import ToolMessenger, format_number

        messenger = ToolMessenger("RoadSelfIntersection")
        messenger.start_timer()

        ok, err = validate_feature_class(road_features, required_geometry_type="Polyline")
        if not ok:
            arcpy.AddError(f"Invalid input: {err}")
            return

        # Self-intersection uses vertex coordinates directly — no projection
        # needed (we only test topological crossing, not metric distance).
        # But if we need output in original CRS we keep both.
        working_fc, proj_sr, temp_fc = _auto_project_roads(road_features)
        if temp_fc:
            messenger.info(f"Auto-projected to UTM (EPSG:{proj_sr.factoryCode})")

        proj_roads = read_geometries_to_dict(working_fc)
        messenger.info(f"Loaded {format_number(len(proj_roads), 0)} road segments")

        orig_roads = proj_roads if temp_fc is None else read_geometries_to_dict(road_features)

        # Build vertex dict (use original CRS coords for output-ready points)
        orig_verts = {}
        for fid, geom in orig_roads.items():
            if not validate_line_geometry(geom):
                continue
            orig_verts[fid] = _extract_vertices(geom)

        selfx = find_self_intersections(orig_verts)
        messenger.info(
            f"Found {format_number(len(selfx), 0)} self-intersecting segments"
        )

        # Write output points in original CRS
        out_dir = os.path.dirname(output_features)
        out_name = os.path.basename(output_features)
        original_sr = get_spatial_reference(road_features)

        if arcpy.Exists(output_features):
            arcpy.management.Delete(output_features)
        arcpy.management.CreateFeatureclass(
            out_dir, out_name, "POINT", spatial_reference=original_sr,
        )
        arcpy.management.AddField(output_features, "ROAD_FID", "LONG")

        count = 0
        with arcpy.da.InsertCursor(output_features, ["SHAPE@XY", "ROAD_FID"]) as cur:
            for fid, ix, iy in selfx:
                cur.insertRow(((ix, iy), fid))
                count += 1

        _cleanup(temp_fc)

        parameters[2].value = count
        arcpy.SetParameterAsText(1, output_features)

        messenger.report_summary(
            total_features=len(proj_roads),
            violations_found=count,
        )

    def postExecute(self, parameters):
        _add_to_map(parameters[1].valueAsText)
