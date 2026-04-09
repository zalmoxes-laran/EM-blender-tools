"""
Data structures for Proxy to RM Projection
This module contains all PropertyGroup definitions and callback functions
for the proxy-to-representation-model projection system.
"""

import bpy
from bpy.props import (
    BoolProperty,
    FloatProperty,
    EnumProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup


def update_projection_auto(self, context):
    """
    Called when auto-update settings change.
    Triggers automatic projection update if enabled.
    """
    if self.auto_update_enabled and self.projection_active:
        try:
            bpy.ops.proxy_projection.update()
        except:
            print("Could not auto-update proxy projection")


def update_projection_method(self, context):
    """
    Called when projection method changes.
    Re-applies projection with new method if active.
    """
    if self.projection_active and self.auto_update_enabled:
        try:
            bpy.ops.proxy_projection.apply()
        except:
            print("Could not update projection method")


def update_blend_strength(self, context):
    """
    Called when blend strength changes.
    Updates existing projection if active.
    """
    if self.projection_active and self.auto_update_enabled:
        try:
            bpy.ops.proxy_projection.update_strength()
        except:
            print("Could not update blend strength")


def update_hide_non_intersected(self, context):
    """
    Called when hide non-intersected option changes.
    Updates transparency of non-intersected areas.
    """
    if self.projection_active:
        try:
            bpy.ops.proxy_projection.update_visibility()
        except:
            print("Could not update visibility")


class ProxyProjectionSettings(PropertyGroup):
    """Settings for proxy to RM projection system"""
    
    # Main toggle
    projection_active: BoolProperty(
        name="Projection Active",
        description="Whether proxy projection is currently active",
        default=False,
        update=update_projection_auto
    )
    
    # Auto-update system
    auto_update_enabled: BoolProperty(
        name="Auto Update",
        description="Automatically update projection when epoch, filters, or proxy colors change",
        default=True,
        update=update_projection_auto
    )
    
    # Projection method
    projection_method: EnumProperty(
        name="Projection Method",
        description="Method used to apply proxy colors to RM surfaces",
        items=[
            ('VERTEX_PAINT', 'Vertex Paint', 'Use vertex colors for fast projection'),
            ('NODE_SHADER', 'Node Shader', 'Use shader nodes for advanced projection'),
        ],
        default='VERTEX_PAINT',
        update=update_projection_method
    )
    
    # Blend settings
    blend_strength: FloatProperty(
        name="Blend Strength",
        description="Strength of proxy color blending with original RM material",
        min=0.0,
        max=1.0,
        default=0.8,
        update=update_blend_strength
    )
    
    # Visibility options
    hide_non_intersected: BoolProperty(
        name="Hide Non-Intersected Areas",
        description="Make transparent the areas of RM that don't intersect with any proxy",
        default=False,
        update=update_hide_non_intersected
    )
    
    non_intersected_alpha: FloatProperty(
        name="Non-Intersected Alpha",
        description="Transparency level for non-intersected areas (0=invisible, 1=opaque)",
        min=0.0,
        max=1.0,
        default=0.2,
        update=update_hide_non_intersected
    )
    
    # Ray casting settings
    ray_casting_precision: EnumProperty(
        name="Ray Casting Precision",
        description="Precision level for ray casting calculations",
        items=[
            ('LOW', 'Low', 'Fast but less accurate'),
            ('MEDIUM', 'Medium', 'Balanced speed and accuracy'),
            ('HIGH', 'High', 'Slow but very accurate'),
        ],
        default='MEDIUM'
    )
    
    # Material override settings for linked objects
    override_linked_materials: BoolProperty(
        name="Override Linked Materials",
        description="Create temporary material overrides for linked objects",
        default=True
    )
    
    # Advanced settings
    show_advanced_settings: BoolProperty(
        name="Show Advanced Settings",
        description="Show advanced projection settings",
        default=False
    )
    
    # Ray distance limit
    max_ray_distance: FloatProperty(
        name="Max Ray Distance",
        description="Maximum distance for ray casting (0 = infinite)",
        min=0.0,
        default=10.0
    )
    
    # Performance settings
    batch_size: EnumProperty(
        name="Batch Size",
        description="Number of vertices to process in each batch",
        items=[
            ('SMALL', 'Small (1000)', 'Process 1000 vertices per batch'),
            ('MEDIUM', 'Medium (5000)', 'Process 5000 vertices per batch'),
            ('LARGE', 'Large (10000)', 'Process 10000 vertices per batch'),
        ],
        default='MEDIUM'
    )


# Callback functions for external triggers

def on_epoch_changed(scene):
    """
    Called when the active epoch changes.
    Updates projection if auto-update is enabled.
    """
    settings = scene.proxy_projection_settings
    if settings.auto_update_enabled and settings.projection_active:
        try:
            bpy.ops.proxy_projection.update()
        except:
            print("Could not update projection on epoch change")


def on_stratigraphy_filter_changed(scene):
    """
    Called when stratigraphy filters change.
    Updates proxy list and projection if auto-update is enabled.
    """
    settings = scene.proxy_projection_settings
    if settings.auto_update_enabled and settings.projection_active:
        try:
            bpy.ops.proxy_projection.update()
        except:
            print("Could not update projection on filter change")


def on_proxy_color_changed(scene):
    """
    Called when proxy colors change in visual manager.
    Updates projection colors if auto-update is enabled.
    """
    settings = scene.proxy_projection_settings
    if settings.auto_update_enabled and settings.projection_active:
        try:
            bpy.ops.proxy_projection.update()
        except:
            print("Could not update projection on color change")


def on_rm_sync_changed(scene):
    """
    Called when RM temporal sync changes.
    Enables/disables projection availability based on sync state.
    """
    settings = scene.proxy_projection_settings
    
    # Check if RM sync is active (you'll need to verify the exact property name)
    rm_sync_active = getattr(scene, 'sync_rm_visibility', False)
    
    if not rm_sync_active and settings.projection_active:
        # Disable projection if RM sync is turned off
        try:
            bpy.ops.proxy_projection.clear()
        except:
            print("Could not clear projection on RM sync disable")


def register_data():
    """Register all data classes and properties."""
    bpy.utils.register_class(ProxyProjectionSettings)
    
    # Add settings to scene
    if not hasattr(bpy.types.Scene, "proxy_projection_settings"):
        bpy.types.Scene.proxy_projection_settings = PointerProperty(type=ProxyProjectionSettings)


def unregister_data():
    """Unregister all data classes and properties."""
    # Remove properties
    if hasattr(bpy.types.Scene, "proxy_projection_settings"):
        del bpy.types.Scene.proxy_projection_settings
    
    # Unregister classes
    bpy.utils.unregister_class(ProxyProjectionSettings)
