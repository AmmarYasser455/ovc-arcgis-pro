# -*- coding: utf-8 -*-
"""
OVC ArcGIS Pro - Messaging Utilities

This module provides user feedback and logging utilities for the
OVC toolbox, wrapping ArcPy's messaging system.
"""

import arcpy
import datetime
from typing import Optional


class ToolMessenger:
    """
    Utility class for sending messages to the ArcGIS Pro UI.
    
    Wraps arcpy messaging functions with consistent formatting
    and optional logging.
    """
    
    def __init__(self, tool_name: str = "OVC"):
        """
        Initialize the messenger.
        
        Args:
            tool_name: Name prefix for messages
        """
        self.tool_name = tool_name
        self.start_time: Optional[datetime.datetime] = None
    
    def info(self, message: str) -> None:
        """
        Send an informational message.
        
        Args:
            message: Message text
        """
        arcpy.AddMessage(f"[{self.tool_name}] {message}")
    
    def warning(self, message: str) -> None:
        """
        Send a warning message.
        
        Args:
            message: Warning text
        """
        arcpy.AddWarning(f"[{self.tool_name}] {message}")
    
    def error(self, message: str) -> None:
        """
        Send an error message.
        
        Args:
            message: Error text
        """
        arcpy.AddError(f"[{self.tool_name}] {message}")
    
    def debug(self, message: str, verbose: bool = False) -> None:
        """
        Send a debug message (only when verbose is True).
        
        Args:
            message: Debug text
            verbose: Whether to actually display the message
        """
        if verbose:
            arcpy.AddMessage(f"[{self.tool_name} DEBUG] {message}")
    
    def start_timer(self) -> None:
        """Start the execution timer."""
        self.start_time = datetime.datetime.now()
    
    def get_elapsed_time(self) -> str:
        """
        Get elapsed time since timer started.
        
        Returns:
            Formatted elapsed time string
        """
        if self.start_time is None:
            return "N/A"
        
        elapsed = datetime.datetime.now() - self.start_time
        total_seconds = elapsed.total_seconds()
        
        if total_seconds < 60:
            return f"{total_seconds:.1f} seconds"
        elif total_seconds < 3600:
            minutes = int(total_seconds // 60)
            seconds = int(total_seconds % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def report_summary(
        self,
        total_features: int,
        violations_found: int,
        additional_stats: Optional[dict] = None
    ) -> None:
        """
        Report a summary of processing results.
        
        Args:
            total_features: Number of features processed
            violations_found: Number of violations found
            additional_stats: Optional dictionary of additional statistics
        """
        self.info("-" * 50)
        self.info("PROCESSING SUMMARY")
        self.info("-" * 50)
        self.info(f"Total features analyzed: {total_features:,}")
        self.info(f"Violations detected: {violations_found:,}")
        
        if additional_stats:
            for key, value in additional_stats.items():
                if isinstance(value, float):
                    self.info(f"{key}: {value:,.2f}")
                elif isinstance(value, int):
                    self.info(f"{key}: {value:,}")
                else:
                    self.info(f"{key}: {value}")
        
        self.info(f"Execution time: {self.get_elapsed_time()}")
        self.info("-" * 50)


class ProgressTracker:
    """
    Utility class for tracking and reporting progress.
    
    Wraps ArcPy's progressor with convenient methods.
    """
    
    def __init__(
        self,
        label: str,
        total: int,
        step_size: int = 1
    ):
        """
        Initialize progress tracker.
        
        Args:
            label: Progress bar label
            total: Total number of steps
            step_size: How often to update (default: every step)
        """
        self.label = label
        self.total = total
        self.step_size = step_size
        self.current = 0
        self._last_reported = 0
    
    def start(self) -> None:
        """Initialize the progressor."""
        arcpy.SetProgressor(
            "step",
            self.label,
            0,
            self.total,
            self.step_size
        )
    
    def update(self, current: Optional[int] = None, status: Optional[str] = None) -> None:
        """
        Update progress.
        
        Args:
            current: Current step number (auto-increment if None)
            status: Optional status message
        """
        if current is not None:
            self.current = current
        else:
            self.current += 1
        
        # Only update UI periodically to avoid slowdown
        if self.current - self._last_reported >= self.step_size:
            if status:
                arcpy.SetProgressorLabel(status)
            arcpy.SetProgressorPosition(self.current)
            self._last_reported = self.current
    
    def finish(self) -> None:
        """Reset the progressor when done."""
        arcpy.ResetProgressor()


def format_number(value: float, decimals: int = 2) -> str:
    """
    Format a number for display with thousands separators.
    
    Args:
        value: Number to format
        decimals: Number of decimal places
        
    Returns:
        Formatted string
    """
    if decimals == 0:
        return f"{int(value):,}"
    return f"{value:,.{decimals}f}"


def format_area(area_sq_meters: float, unit: str = "m2") -> str:
    """
    Format an area value for display.
    
    Args:
        area_sq_meters: Area in square meters
        unit: Display unit ("m2", "ha", "km2")
        
    Returns:
        Formatted string with unit
    """
    if unit == "ha":
        value = area_sq_meters / 10000.0
        return f"{value:,.2f} ha"
    elif unit == "km2":
        value = area_sq_meters / 1000000.0
        return f"{value:,.4f} km²"
    else:
        return f"{area_sq_meters:,.2f} m²"


def get_timestamp() -> str:
    """
    Get current timestamp as formatted string.
    
    Returns:
        ISO format timestamp
    """
    return datetime.datetime.now().isoformat()
