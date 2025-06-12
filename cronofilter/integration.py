"""
CronoFilter Integration Module
============================

This module handles the integration of CronoFilter with the main addon,
specifically ensuring that custom chronological horizons are included
in Heriverse JSON exports.

Import this module after CronoFilter is registered to enable the integration.
"""

import bpy

# Import the direct integration patch
from .json_exporter_patch import register_delayed_initialization, print_context_summary

def initialize_cronofilter_integration():
    """
    Initialize the complete CronoFilter integration.
    This should be called after both CronoFilter and the main addon are loaded.
    """
    print("CronoFilter: Starting integration with Heriverse export system...")
    
    # Register the direct JSONExporter patch
    register_delayed_initialization()
    
    print("CronoFilter: Integration initialization complete")

# Utility functions for external use
def get_horizon_count():
    """Get the number of enabled custom horizons"""
    try:
        if hasattr(bpy.types.Scene, 'cf_settings'):
            scene = bpy.context.scene
            if hasattr(scene, 'cf_settings'):
                cf_settings = scene.cf_settings
                return sum(1 for h in cf_settings.horizons if h.enabled)
    except:
        pass
    return 0

def validate_horizons_for_export():
    """
    Validate that all enabled horizons have valid data for export.
    Returns True if all are valid, False otherwise.
    """
    try:
        if not hasattr(bpy.types.Scene, 'cf_settings'):
            return True  # No CronoFilter data, nothing to validate
        
        scene = bpy.context.scene
        if not hasattr(scene, 'cf_settings'):
            return True
        
        cf_settings = scene.cf_settings
        
        for horizon in cf_settings.horizons:
            if horizon.enabled:
                # Check for valid time range
                if horizon.start_time >= horizon.end_time:
                    print(f"CronoFilter: Invalid time range for horizon '{horizon.label}': {horizon.start_time} >= {horizon.end_time}")
                    return False
                
                # Check for valid label
                if not horizon.label.strip():
                    print(f"CronoFilter: Empty label for horizon")
                    return False
        
        return True
        
    except Exception as e:
        print(f"CronoFilter: Error validating horizons: {e}")
        return False

def get_export_preview():
    """
    Get a preview of what will be exported in the context section.
    Useful for debugging and user feedback.
    """
    try:
        from .json_exporter_patch import get_context_preview
        return get_context_preview()
    except:
        return {}

def print_export_summary():
    """Print a summary of what will be exported"""
    try:
        from .json_exporter_patch import print_context_summary
        print_context_summary()
    except Exception as e:
        print(f"CronoFilter: Error printing export summary: {e}")

# Auto-initialize when imported (but not if running as main)
if __name__ != "__main__":
    print("CronoFilter integration module loaded")