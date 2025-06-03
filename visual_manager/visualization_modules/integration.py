"""
Integration Layer for Visualization Modules
This module bridges existing visualization modules with the centralized manager system.
"""

import bpy
from typing import List, Dict, Any

from .manager import register_module, get_manager
from .proxy_transparency import apply_transparency_to_material, get_objects_for_transparency_mode
from .proxy_color_overlay import apply_color_overlay_to_material, get_overlay_color_for_object
from .clipping_section import create_clipping_material_nodes, create_clipping_volume
from .utils import get_em_objects

# Integration functions for transparency module
def apply_transparency_visualization(objects: List, settings: Dict[str, Any]):
    """
    Unified apply function for transparency visualization.
    
    Args:
        objects: List of objects to apply transparency to
        settings: Transparency settings dictionary
    """
    try:
        transparency_factor = settings.get('transparency_factor', 0.5)
        transparency_mode = settings.get('transparency_mode', 'SELECTION')
        affect_selected_only = settings.get('affect_selected_only', False)
        affect_visible_only = settings.get('affect_visible_only', True)
        
        # Get objects to make transparent based on mode
        objects_to_transparent = get_objects_for_transparency_mode(transparency_mode)
        
        # Filter by selection/visibility if needed
        if affect_selected_only:
            selected_names = {obj.name for obj in bpy.context.selected_objects}
            objects_to_transparent = [obj for obj in objects_to_transparent if obj.name in selected_names]
        
        if affect_visible_only:
            objects_to_transparent = [obj for obj in objects_to_transparent if not obj.hide_viewport]
        
        # Apply transparency
        for obj in objects_to_transparent:
            if obj.data and obj.data.materials:
                for material in obj.data.materials:
                    if material:
                        apply_transparency_to_material(material, transparency_factor)
        
        print(f"Applied transparency to {len(objects_to_transparent)} objects")
        
    except Exception as e:
        print(f"Error in transparency visualization: {e}")
        raise

def clear_transparency_visualization():
    """Clear transparency effects from all materials."""
    try:
        em_objects = get_em_objects()
        for obj in em_objects:
            if obj.data and obj.data.materials:
                for material in obj.data.materials:
                    if material:
                        apply_transparency_to_material(material, 0.0)  # Remove transparency
        
        print("Cleared transparency from all objects")
        
    except Exception as e:
        print(f"Error clearing transparency visualization: {e}")
        raise

# Integration functions for color overlay module
def apply_color_overlay_visualization(objects: List, settings: Dict[str, Any]):
    """
    Unified apply function for color overlay visualization.
    
    Args:
        objects: List of objects to apply overlay to
        settings: Color overlay settings dictionary
    """
    try:
        overlay_strength = settings.get('overlay_strength', 0.5)
        overlay_mode = settings.get('overlay_mode', 'EM_TYPE')
        custom_overlay_color = settings.get('custom_overlay_color', (1.0, 0.5, 0.0))
        blend_mode = settings.get('blend_mode', 'ADD')
        affect_emission = settings.get('affect_emission', True)
        
        # Create a settings object for compatibility
        class OverlaySettings:
            def __init__(self):
                self.overlay_strength = overlay_strength
                self.overlay_mode = overlay_mode
                self.custom_overlay_color = custom_overlay_color
                self.blend_mode = blend_mode
                self.affect_emission = affect_emission
        
        overlay_settings = OverlaySettings()
        
        # Apply overlay to target objects
        target_objects = get_em_objects() if not objects else objects
        
        for obj in target_objects:
            if obj.data and obj.data.materials:
                overlay_color = get_overlay_color_for_object(obj, overlay_settings)
                
                for material in obj.data.materials:
                    if material:
                        apply_color_overlay_to_material(material, overlay_color, overlay_settings)
        
        print(f"Applied color overlay to {len(target_objects)} objects")
        
    except Exception as e:
        print(f"Error in color overlay visualization: {e}")
        raise

def clear_color_overlay_visualization():
    """Clear color overlay effects from all materials."""
    try:
        # Use the existing clear operator functionality
        bpy.ops.visual.clear_color_overlay()
        print("Cleared color overlay from all objects")
        
    except Exception as e:
        print(f"Error clearing color overlay visualization: {e}")
        raise

# Integration functions for clipping module
def apply_clipping_visualization(objects: List, settings: Dict[str, Any]):
    """
    Unified apply function for clipping visualization.
    
    Args:
        objects: List of objects to apply clipping to
        settings: Clipping settings dictionary
    """
    try:
        section_color = settings.get('section_color', (0.4, 0.2, 0.6))
        clipping_distance = settings.get('clipping_distance', 10.0)
        clipping_mode = settings.get('clipping_mode', 'PLANE')
        affect_all_objects = settings.get('affect_all_objects', False)
        use_camera_clipping = settings.get('use_camera_clipping', False)
        
        # Create a settings object for compatibility
        class ClippingSettings:
            def __init__(self):
                self.section_color = section_color
                self.clipping_distance = clipping_distance
                self.clipping_mode = clipping_mode
                self.affect_all_objects = affect_all_objects
                self.use_camera_clipping = use_camera_clipping
        
        clipping_settings = ClippingSettings()
        
        # Find or create clipping object
        scene = bpy.context.scene
        clipping_objects = [obj for obj in scene.objects if obj.name.startswith('CLIP_')]
        
        if not clipping_objects:
            # Create a new clipping volume
            clipping_object = create_clipping_volume(clipping_settings)
        else:
            clipping_object = clipping_objects[0]  # Use existing
        
        if not clipping_object:
            raise Exception("Failed to create or find clipping object")
        
        # Get target objects
        if affect_all_objects:
            target_objects = [obj for obj in scene.objects if obj.type == 'MESH' and not obj.name.startswith('CLIP_')]
        else:
            target_objects = get_em_objects()
        
        # Apply clipping to materials
        for obj in target_objects:
            if obj.data and obj.data.materials:
                for material in obj.data.materials:
                    if material:
                        create_clipping_material_nodes(material, clipping_object, clipping_settings)
        
        print(f"Applied clipping effect to {len(target_objects)} objects")
        
    except Exception as e:
        print(f"Error in clipping visualization: {e}")
        raise

def clear_clipping_visualization():
    """Clear clipping effects from all materials."""
    try:
        # Use the existing clear operator functionality
        bpy.ops.visual.clear_clipping_effect()
        print("Cleared clipping effects from all objects")
        
    except Exception as e:
        print(f"Error clearing clipping visualization: {e}")
        raise

# EM-TOOLS specific integration functions
def get_objects_by_em_filter(filter_type: str, filter_value: str = None) -> List:
    """
    Get objects based on EM-specific filters.
    
    Args:
        filter_type: Type of filter ('epoch', 'property', 'node_type', 'selection')
        filter_value: Value to filter by (epoch name, property value, etc.)
        
    Returns:
        List of filtered objects
    """
    scene = bpy.context.scene
    filtered_objects = []
    
    if filter_type == 'selection':
        # Return selected EM objects
        selected_names = {obj.name for obj in bpy.context.selected_objects}
        em_objects = get_em_objects()
        filtered_objects = [obj for obj in em_objects if obj.name in selected_names]
    
    elif filter_type == 'epoch' and hasattr(scene, 'em_list'):
        # Filter by epoch
        for em_item in scene.em_list:
            if hasattr(em_item, 'epoch') and em_item.epoch == filter_value:
                obj = bpy.data.objects.get(em_item.name)
                if obj and obj.type == 'MESH':
                    filtered_objects.append(obj)
    
    elif filter_type == 'node_type' and hasattr(scene, 'em_list'):
        # Filter by EM node type
        for em_item in scene.em_list:
            if hasattr(em_item, 'node_type') and em_item.node_type == filter_value:
                obj = bpy.data.objects.get(em_item.name)
                if obj and obj.type == 'MESH':
                    filtered_objects.append(obj)
    
    elif filter_type == 'property':
        # Filter by property value (would need integration with property system)
        # This would require extending the existing property visualization system
        filtered_objects = get_em_objects()  # Fallback to all EM objects
    
    return filtered_objects

def register_visualization_modules():
    """Register all visualization modules with the central manager."""
    manager = get_manager()
    
    # Register transparency module
    register_module(
        module_id='transparency',
        apply_func=apply_transparency_visualization,
        clear_func=clear_transparency_visualization,
        default_settings={
            'transparency_factor': 0.5,
            'transparency_mode': 'SELECTION',
            'affect_selected_only': False,
            'affect_visible_only': True
        }
    )
    
    # Register color overlay module
    register_module(
        module_id='color_overlay',
        apply_func=apply_color_overlay_visualization,
        clear_func=clear_color_overlay_visualization,
        default_settings={
            'overlay_strength': 0.5,
            'overlay_mode': 'EM_TYPE',
            'custom_overlay_color': (1.0, 0.5, 0.0),
            'blend_mode': 'ADD',
            'affect_emission': True
        }
    )
    
    # Register clipping module
    register_module(
        module_id='clipping',
        apply_func=apply_clipping_visualization,
        clear_func=clear_clipping_visualization,
        default_settings={
            'section_color': (0.4, 0.2, 0.6),
            'clipping_distance': 10.0,
            'clipping_mode': 'PLANE',
            'affect_all_objects': False,
            'use_camera_clipping': False
        }
    )
    
    print("Registered all visualization modules with manager")

# Event handlers for EM-TOOLS integration
def handle_em_selection_change():
    """Handle selection changes in EM context."""
    manager = get_manager()
    if manager.is_module_active('transparency'):
        # Update transparency based on new selection
        transparency_settings = manager.get_module_settings('transparency')
        if transparency_settings and transparency_settings.get('transparency_mode') == 'SELECTION':
            manager.schedule_update('transparency')

def handle_epoch_change():
    """Handle epoch selection changes."""
    manager = get_manager()
    
    # Update any epoch-based visualizations
    if manager.is_module_active('transparency'):
        transparency_settings = manager.get_module_settings('transparency')
        if transparency_settings and transparency_settings.get('transparency_mode') == 'EPOCH':
            manager.schedule_update('transparency')
    
    if manager.is_module_active('color_overlay'):
        overlay_settings = manager.get_module_settings('color_overlay')
        if overlay_settings and overlay_settings.get('overlay_mode') == 'EPOCH':
            manager.schedule_update('color_overlay')

def handle_property_change():
    """Handle property selection changes."""
    manager = get_manager()
    
    # Update property-based visualizations
    if manager.is_module_active('color_overlay'):
        overlay_settings = manager.get_module_settings('color_overlay')
        if overlay_settings and overlay_settings.get('overlay_mode') == 'PROPERTY':
            manager.schedule_update('color_overlay')

# Convenience functions for external integration
def quick_focus_mode(objects: List = None):
    """Quick function to enter focus mode for selected objects."""
    manager = get_manager()
    
    # Clear existing visualizations
    manager.clear_all_modules()
    
    # Apply focus mode
    transparency_settings = {
        'transparency_factor': 0.7,
        'transparency_mode': 'SELECTION',
        'affect_selected_only': False,
        'affect_visible_only': True
    }
    
    overlay_settings = {
        'overlay_strength': 0.3,
        'overlay_mode': 'CUSTOM',
        'custom_overlay_color': (1.0, 0.8, 0.2),
        'blend_mode': 'ADD'
    }
    
    manager.activate_module('transparency', transparency_settings)
    manager.activate_module('color_overlay', overlay_settings)

def quick_epoch_analysis():
    """Quick function to set up epoch analysis visualization."""
    manager = get_manager()
    
    # Clear existing visualizations
    manager.clear_all_modules()
    
    # Apply epoch analysis mode
    overlay_settings = {
        'overlay_strength': 0.6,
        'overlay_mode': 'EPOCH',
        'blend_mode': 'OVERLAY'
    }
    
    transparency_settings = {
        'transparency_factor': 0.5,
        'transparency_mode': 'EPOCH'
    }
    
    manager.activate_module('color_overlay', overlay_settings)
    manager.activate_module('transparency', transparency_settings)

def create_presentation_setup():
    """Create a complete setup optimized for presentations."""
    # This could be called from other parts of EM-TOOLS
    bpy.ops.visual.create_visualization_setup(
        include_clipping=False,
        include_camera_setup=True,
        optimize_for_presentation=True
    )

def create_analysis_setup():
    """Create a complete setup optimized for analysis."""
    # This could be called from other parts of EM-TOOLS
    bpy.ops.visual.create_visualization_setup(
        include_clipping=True,
        include_camera_setup=True,
        optimize_for_presentation=False
    )
