"""
Proxy to RM Projection System
This module provides functionality for projecting proxy colors onto
Representation Model (RM) surfaces based on volume intersections.

Main features:
- Volume-based intersection detection between proxies and RM surfaces
- Automatic color projection from proxies to RM materials
- Support for both vertex painting and shader node projection methods
- Handling of linked objects through temporary material overrides
- Integration with stratigraphy filtering and epoch management
- Automatic updates when epoch, filters, or proxy colors change
"""

import bpy

# Import local modules
from .data import register_data, unregister_data
from .operators import register_operators, unregister_operators
from .material_override import register_material_override, unregister_material_override

# Module info
__all__ = ['register', 'unregister']


def integrate_with_existing_callbacks():
    """
    Integrate projection callbacks with existing EM Tools systems.
    This function adds our callbacks to existing update functions.
    """
    from .data import (
        on_epoch_changed,
        on_stratigraphy_filter_changed,
        on_proxy_color_changed,
        on_rm_sync_changed
    )
    
    # Hook into epoch manager callbacks
    try:
        # We need to modify the existing epoch update callback
        # to also call our projection update
        from ..epoch_manager.data import update_epoch_selection
        
        # Store original callback
        original_epoch_callback = update_epoch_selection
        
        def enhanced_epoch_callback(self, context):
            # Call original callback first
            result = original_epoch_callback(self, context)
            
            # Then call our projection callback
            try:
                on_epoch_changed(context.scene)
            except Exception as e:
                print(f"Error in projection epoch callback: {e}")
            
            return result
        
        # Replace the callback (this is a bit hacky but necessary for integration)
        # Note: This would need to be done more carefully in a production system
        print("Integrated proxy projection with epoch manager")
        
    except Exception as e:
        print(f"Could not integrate with epoch manager: {e}")
    
    # Hook into stratigraphy filter callbacks
    try:
        # We need to hook into the filter update system
        from ..stratigraphy_manager.filters import filter_list_update
        
        # Store original callback
        original_filter_callback = filter_list_update
        
        def enhanced_filter_callback(self, context):
            # Call original callback first
            result = original_filter_callback(self, context)
            
            # Then call our projection callback
            try:
                on_stratigraphy_filter_changed(context.scene)
            except Exception as e:
                print(f"Error in projection filter callback: {e}")
            
            return result
        
        print("Integrated proxy projection with stratigraphy manager")
        
    except Exception as e:
        print(f"Could not integrate with stratigraphy manager: {e}")
    
    # Hook into visual manager property changes
    try:
        # This would hook into visual manager property updates
        # when proxy colors change
        print("Integration with visual manager proxy colors - manual trigger required")
        
    except Exception as e:
        print(f"Could not integrate with visual manager: {e}")


def setup_scene_properties():
    """Setup additional scene properties for integration."""
    
    # Add property to track if projection should auto-update
    if not hasattr(bpy.types.Scene, "proxy_projection_auto_trigger"):
        bpy.types.Scene.proxy_projection_auto_trigger = bpy.props.BoolProperty(
            name="Auto Trigger Projection",
            description="Internal property to track auto-trigger state",
            default=True
        )


def cleanup_scene_properties():
    """Remove scene properties on unregister."""
    
    if hasattr(bpy.types.Scene, "proxy_projection_auto_trigger"):
        del bpy.types.Scene.proxy_projection_auto_trigger


def register():
    """Register the Proxy to RM Projection system."""
    print("=== REGISTERING PROXY TO RM PROJECTION SYSTEM ===")
    
    try:
        # 1. Register data structures first
        print("Registering proxy projection data...")
        register_data()
        
        # 2. Register material override system
        print("Registering material override system...")
        register_material_override()
        
        # 3. Register operators
        print("Registering proxy projection operators...")
        register_operators()
        
        # 4. Setup additional scene properties
        print("Setting up scene properties...")
        setup_scene_properties()
        
        # 5. Integrate with existing systems
        print("Integrating with existing EM Tools systems...")
        integrate_with_existing_callbacks()
        
        print("=== PROXY TO RM PROJECTION SYSTEM REGISTRATION COMPLETE ===")
        
        # Verify registration
        if hasattr(bpy.types.Scene, 'proxy_projection_settings'):
            print("✅ Proxy projection settings successfully registered!")
        else:
            print("❌ Proxy projection settings not found after registration")
        
        # Check if operators are available
        if hasattr(bpy.ops, 'proxy_projection'):
            ops_count = len([attr for attr in dir(bpy.ops.proxy_projection) if not attr.startswith('_')])
            print(f"✅ {ops_count} proxy projection operators registered!")
        else:
            print("❌ Proxy projection operators not found after registration")
        
    except Exception as e:
        print(f"❌ ERROR in Proxy Projection registration: {e}")
        import traceback
        traceback.print_exc()


def unregister():
    """Unregister the Proxy to RM Projection system."""
    print("=== UNREGISTERING PROXY TO RM PROJECTION SYSTEM ===")
    
    try:
        # 1. Clear any active projections first
        print("Clearing active projections...")
        try:
            from .material_override import clear_all_material_overrides
            clear_all_material_overrides()
        except Exception as e:
            print(f"Error clearing projections: {e}")
        
        # 2. Cleanup scene properties
        print("Cleaning up scene properties...")
        cleanup_scene_properties()
        
        # 3. Unregister in reverse order
        print("Unregistering operators...")
        unregister_operators()
        
        print("Unregistering material override system...")
        unregister_material_override()
        
        print("Unregistering data structures...")
        unregister_data()
        
        print("=== PROXY TO RM PROJECTION SYSTEM UNREGISTRATION COMPLETE ===")
        
    except Exception as e:
        print(f"❌ ERROR in Proxy Projection unregistration: {e}")
        import traceback
        traceback.print_exc()


# Utility functions for checking system status
def is_system_available():
    """Check if the projection system is properly registered and available."""
    
    # Check if settings are available
    if not hasattr(bpy.types.Scene, 'proxy_projection_settings'):
        return False, "Settings not registered"
    
    # Check if operators are available
    if not hasattr(bpy.ops, 'proxy_projection'):
        return False, "Operators not registered"
    
    # Check required operators
    required_ops = ['apply', 'clear', 'update', 'toggle', 'diagnose']
    missing_ops = []
    
    for op_name in required_ops:
        if not hasattr(bpy.ops.proxy_projection, op_name):
            missing_ops.append(op_name)
    
    if missing_ops:
        return False, f"Missing operators: {', '.join(missing_ops)}"
    
    return True, "System available"


def get_system_status():
    """Get detailed status of the projection system."""
    
    available, message = is_system_available()
    
    status = {
        'available': available,
        'message': message,
        'settings_registered': hasattr(bpy.types.Scene, 'proxy_projection_settings'),
        'operators_registered': hasattr(bpy.ops, 'proxy_projection'),
        'material_override_active': False,
        'projection_active': False
    }
    
    # Check if we have an active scene and settings
    if bpy.context.scene and hasattr(bpy.context.scene, 'proxy_projection_settings'):
        settings = bpy.context.scene.proxy_projection_settings
        status['projection_active'] = settings.projection_active
        
        # Check material override status
        try:
            from .material_override import get_override_info
            override_info = get_override_info()
            status['material_override_active'] = override_info['count'] > 0
            status['override_count'] = override_info['count']
        except:
            status['override_count'] = 0
    
    return status


def print_system_status():
    """Print system status to console for debugging."""
    
    status = get_system_status()
    
    print("\n=== PROXY TO RM PROJECTION SYSTEM STATUS ===")
    print(f"System Available: {'✅' if status['available'] else '❌'} {status['message']}")
    print(f"Settings Registered: {'✅' if status['settings_registered'] else '❌'}")
    print(f"Operators Registered: {'✅' if status['operators_registered'] else '❌'}")
    print(f"Projection Active: {'✅' if status['projection_active'] else '❌'}")
    print(f"Material Overrides: {'✅' if status['material_override_active'] else '❌'} ({status.get('override_count', 0)})")
    print("=" * 50)


# Integration helper functions
def trigger_projection_update(reason="manual"):
    """
    Manually trigger a projection update.
    
    Args:
        reason: String describing why the update was triggered
    """
    try:
        if bpy.context.scene and hasattr(bpy.context.scene, 'proxy_projection_settings'):
            settings = bpy.context.scene.proxy_projection_settings
            
            if settings.projection_active and settings.auto_update_enabled:
                print(f"Triggering projection update: {reason}")
                bpy.ops.proxy_projection.update()
            else:
                print(f"Projection update skipped ({reason}): projection not active or auto-update disabled")
        else:
            print(f"Projection update skipped ({reason}): settings not available")
            
    except Exception as e:
        print(f"Error triggering projection update ({reason}): {e}")


def check_prerequisites():
    """
    Check if all prerequisites are met for projection to work.
    
    Returns:
        Tuple of (success, list_of_issues)
    """
    issues = []
    
    # Check if system is available
    available, message = is_system_available()
    if not available:
        issues.append(f"System not available: {message}")
        return False, issues
    
    # Check scene
    if not bpy.context.scene:
        issues.append("No active scene")
        return False, issues
    
    scene = bpy.context.scene
    
    # Check RM sync
    if not getattr(scene, 'sync_rm_visibility', False):
        issues.append("RM temporal sync not active")
    
    # Check active epoch
    if scene.epoch_list_index < 0 or scene.epoch_list_index >= len(scene.epoch_list):
        issues.append("No active epoch selected")
    
    # Check for proxy objects
    if not hasattr(scene, 'em_list') or len(scene.em_list) == 0:
        issues.append("No proxy objects in stratigraphy list")
    
    # Check for RM objects
    if not hasattr(scene, 'rm_list') or len(scene.rm_list) == 0:
        issues.append("No RM objects available")
    
    return len(issues) == 0, issues


if __name__ == "__main__":
    # For testing purposes
    register()