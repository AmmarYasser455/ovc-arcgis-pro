# -*- coding: utf-8 -*-
"""
OVC - Overlap Violation Checker
ArcGIS Pro Python Toolbox

A production-quality spatial QC toolbox for detecting geometry violations
in polygon and line feature classes.

Author: Ammar Yasser
Version: 1.0.0
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
            # Future tools:
            # RoadDangleChecker,
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


class RoadDangleChecker(object):
    """
    Road Dangle Checker Tool.
    
    Detects dangling endpoints in road networks.
    [Placeholder - to be implemented in Phase 3]
    """
    
    def __init__(self):
        self.label = "Road Dangle Checker"
        self.description = "Detects dangling endpoints in road networks."
        self.canRunInBackground = True
        self.category = "Road QC"
    
    def getParameterInfo(self):
        return []
    
    def isLicensed(self):
        return True
    
    def execute(self, parameters, messages):
        arcpy.AddError("This tool is not yet implemented.")
        return
