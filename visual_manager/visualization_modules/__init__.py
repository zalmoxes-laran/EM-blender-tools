"""
Visualization Modules for Visual Manager
This module provides advanced visualization capabilities including transparency,
clipping planes, color overlays, preset management, smart suggestions, validation,
temporal integration, and a centralized management system for EM-TOOLS.
"""

import bpy

# Import core visualization modules
from .proxy_transparency import register_transparency, unregister_transparency
from .clipping_section import register_clipping, unregister_clipping  
from .proxy_color_overlay import register_overlay, unregister_overlay
from .utils import clean_all_materials, register_utils, unregister_utils

# Import centralized management system
from .manager import VisualizationManager, get_manager
from .unified_operators import register_unified_operators, unregister_unified_operators
from .integration import (
    register_visualization_modules, 
    quick_focus_mode, 
    quick_epoch_analysis,
    create_presentation_setup,
    create_analysis_setup
)

# Import advanced systems
from .preset_system import (
    register_preset_system, 
    unregister_preset_system,
    get_preset_manager,
    save_current_as_preset,
    load_preset_by_name
)
from .smart_suggestions import (
    register_smart_suggestions,
    unregister_smart_suggestions,
    get_suggestions_for_context
)
from .validation import (
    register_validation,
    unregister_validation,
    quick_validation_check,
    run_minimal_tests
)
from .temporal_integration import (
    register_temporal_integration,
    unregister_temporal_integration,
    get_temporal_controller,
    quick_temporal_analysis,
    start_epoch_sequence
)

# Module info
__all__ = [
    'register', 'unregister', 'clean_all_materials',
    'get_manager', 'quick_focus_mode', 'quick_epoch_analysis',
    'create_presentation_setup', 'create_analysis_setup',
    'get_preset_manager', 'save_current_as_preset', 'load_preset_by_name',
    'get_suggestions_for_context', 'quick_validation_check',
    'get_temporal_controller', 'quick_temporal_analysis', 'start_epoch_sequence'
]

def register():
    """Register all visualization modules."""
    print("=== REGISTERING ADVANCED VISUALIZATION SYSTEM ===")
    
    # Register core modules first
    print("Registering core visualization modules...")
    register_transparency()
    register_clipping()
    register_overlay()
    register_utils()
    
    # Register centralized management system
    print("Registering unified management system...")
    register_unified_operators()
    
    # Register advanced systems
    print("Registering preset system...")
    register_preset_system()
    
    print("Registering smart suggestions...")
    register_smart_suggestions()
    
    print("Registering validation system...")
    register_validation()
    
    print("Registering temporal integration...")
    register_temporal_integration()
    
    # Register modules with the central manager
    print("Registering modules with central manager...")
    register_visualization_modules()
    
    # Setup event handlers for EM-TOOLS integration
    setup_em_tools_integration()
    
    # Run initial validation
    run_initial_validation()
    
    print("=== ADVANCED VISUALIZATION SYSTEM REGISTRATION COMPLETE ===")

def unregister():
    """Unregister all visualization modules."""
    print("=== UNREGISTERING ADVANCED VISUALIZATION SYSTEM ===")
    
    # Clear all active visualizations before unregistering
    try:
        manager = get_manager()
        manager.clear_all_modules()
    except:
        pass
    
    # Cleanup event handlers
    cleanup_em_tools_integration()
    
    # Unregister advanced systems in reverse order
    unregister_temporal_integration()
    unregister_validation()
    unregister_smart_suggestions()
    unregister_preset_system()
    
    # Unregister core systems
    unregister_unified_operators()
    unregister_utils()
    unregister_overlay()
    unregister_clipping()
    unregister_transparency()
    
    print("=== ADVANCED VISUALIZATION SYSTEM UNREGISTRATION COMPLETE ===")

def setup_em_tools_integration():
    """Setup integration with EM-TOOLS systems."""
    try:
        from .integration import handle_em_selection_change, handle_epoch_change, handle_property_change
        
        # Get the manager and subscribe to events
        manager = get_manager()
        
        # Subscribe to relevant events
        manager.subscribe_to_event('selection_changed', handle_em_selection_change)
        manager.subscribe_to_event('epoch_changed', handle_epoch_change)
        manager.subscribe_to_event('property_changed', handle_property_change)
        
        print("Setup EM-TOOLS integration events")
        
    except Exception as e:
        print(f"Warning: Could not setup EM-TOOLS integration: {e}")

def cleanup_em_tools_integration():
    """Cleanup EM-TOOLS integration."""
    try:
        # Stop any running timers
        temporal_controller = get_temporal_controller()
        temporal_controller.stop_auto_advance()
        
        print("Cleaned up EM-TOOLS integration")
    except Exception as e:
        print(f"Warning: Error cleaning up EM-TOOLS integration: {e}")

def run_initial_validation():
    """Run initial validation to ensure system is working."""
    try:
        # Run a quick validation check
        context = bpy.context
        if quick_validation_check(context):
            print("✓ Initial validation passed")
        else:
            print("⚠ Initial validation failed - some features may not work correctly")
            
    except Exception as e:
        print(f"Warning: Could not run initial validation: {e}")

# Convenience functions for other EM-TOOLS modules
def is_visualization_active():
    """Check if any visualizations are currently active."""
    try:
        manager = get_manager()
        return len(manager.get_active_modules()) > 0
    except:
        return False

def get_active_visualizations():
    """Get list of currently active visualization modules."""
    try:
        manager = get_manager()
        return manager.get_active_modules()
    except:
        return []

def clear_all_visualizations():
    """Clear all active visualizations - safe wrapper."""
    try:
        manager = get_manager()
        manager.clear_all_modules()
        return True
    except Exception as e:
        print(f"Error clearing visualizations: {e}")
        return False

def get_system_status():
    """Get comprehensive system status."""
    try:
        manager = get_manager()
        perf_info = manager.get_performance_info()
        
        status = {
            'manager_active': True,
            'active_modules': manager.get_active_modules(),
            'performance_mode': perf_info['performance_mode'],
            'target_objects': perf_info['target_objects'],
            'system_health': 'good'
        }
        
        # Quick health check
        if perf_info['target_objects'] > 1000:
            status['system_health'] = 'performance_mode'
        elif perf_info['pending_updates'] > 10:
            status['system_health'] = 'high_load'
        
        return status
    except Exception as e:
        return {
            'manager_active': False,
            'error': str(e),
            'system_health': 'error'
        }

def apply_smart_preset_for_context(context):
    """Apply the best preset for current context automatically."""
    try:
        suggestions = get_suggestions_for_context(context)
        if suggestions:
            # Apply the highest confidence suggestion
            best_suggestion = max(suggestions, key=lambda s: s['confidence'])
            if best_suggestion['preset_id']:
                preset_manager = get_preset_manager()
                return preset_manager.load_preset(best_suggestion['preset_id'])
        return False
    except Exception as e:
        print(f"Error applying smart preset: {e}")
        return False
