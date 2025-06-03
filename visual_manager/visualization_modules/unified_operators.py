"""
Unified Operators for Visualization Modules
This module provides high-level operators that use the centralized visualization manager.
"""

import bpy
from bpy.types import Operator, PropertyGroup
from bpy.props import BoolProperty, StringProperty, FloatProperty, EnumProperty, IntProperty

from .manager import get_manager, clear_all_visualizations, update_all_visualizations

class VisualizationManagerSettings(PropertyGroup):
    """Global settings for the visualization manager"""
    
    auto_update_on_selection: BoolProperty(
        name="Auto Update on Selection",
        description="Automatically update visualizations when selection changes",
        default=True
    ) # type: ignore
    
    performance_mode_threshold: IntProperty(
        name="Performance Mode Threshold",
        description="Number of objects before entering performance mode",
        min=100,
        max=5000,
        default=1000
    ) # type: ignore
    
    show_performance_info: BoolProperty(
        name="Show Performance Info",
        description="Display performance information in the UI",
        default=False
    ) # type: ignore
    
    enable_material_backup: BoolProperty(
        name="Enable Material Backup",
        description="Create material backups for safe restoration",
        default=True
    ) # type: ignore

class VISUAL_OT_unified_apply_visualization(Operator):
    """Apply a visualization using the unified system"""
    bl_idname = "visual.unified_apply_visualization"
    bl_label = "Apply Visualization"
    bl_description = "Apply a visualization module using the unified system"
    bl_options = {'REGISTER', 'UNDO'}
    
    module_id: StringProperty(
        name="Module ID",
        description="ID of the visualization module to apply"
    ) # type: ignore
    
    def execute(self, context):
        manager = get_manager()
        
        if not self.module_id:
            self.report({'ERROR'}, "No module ID specified")
            return {'CANCELLED'}
        
        try:
            # Get settings from scene properties
            settings = self._get_module_settings(context, self.module_id)
            
            # Activate the module
            success = manager.activate_module(self.module_id, settings)
            
            if success:
                self.report({'INFO'}, f"Applied {self.module_id} visualization")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, f"Failed to apply {self.module_id} visualization")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Error applying visualization: {str(e)}")
            return {'CANCELLED'}
    
    def _get_module_settings(self, context, module_id):
        """Get settings for a specific module from scene properties."""
        scene = context.scene
        settings = {}
        
        if module_id == 'transparency':
            if hasattr(scene, 'transparency_settings'):
                ts = scene.transparency_settings
                settings = {
                    'transparency_factor': ts.transparency_factor,
                    'transparency_mode': ts.transparency_mode,
                    'affect_selected_only': ts.affect_selected_only,
                    'affect_visible_only': ts.affect_visible_only
                }
        
        elif module_id == 'color_overlay':
            if hasattr(scene, 'color_overlay_settings'):
                cos = scene.color_overlay_settings
                settings = {
                    'overlay_strength': cos.overlay_strength,
                    'overlay_mode': cos.overlay_mode,
                    'custom_overlay_color': tuple(cos.custom_overlay_color),
                    'blend_mode': cos.blend_mode,
                    'affect_emission': cos.affect_emission
                }
        
        elif module_id == 'clipping':
            if hasattr(scene, 'clipping_settings'):
                cs = scene.clipping_settings
                settings = {
                    'section_color': tuple(cs.section_color),
                    'clipping_distance': cs.clipping_distance,
                    'clipping_mode': cs.clipping_mode,
                    'affect_all_objects': cs.affect_all_objects
                }
        
        return settings

class VISUAL_OT_unified_clear_visualization(Operator):
    """Clear a specific visualization using the unified system"""
    bl_idname = "visual.unified_clear_visualization"
    bl_label = "Clear Visualization"
    bl_description = "Clear a specific visualization module"
    bl_options = {'REGISTER', 'UNDO'}
    
    module_id: StringProperty(
        name="Module ID",
        description="ID of the visualization module to clear"
    ) # type: ignore
    
    def execute(self, context):
        manager = get_manager()
        
        if not self.module_id:
            self.report({'ERROR'}, "No module ID specified")
            return {'CANCELLED'}
        
        try:
            success = manager.deactivate_module(self.module_id)
            
            if success:
                self.report({'INFO'}, f"Cleared {self.module_id} visualization")
                return {'FINISHED'}
            else:
                self.report({'WARNING'}, f"Module {self.module_id} was not active")
                return {'FINISHED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Error clearing visualization: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_unified_clear_all_visualizations(Operator):
    """Clear all active visualizations"""
    bl_idname = "visual.unified_clear_all_visualizations"
    bl_label = "Clear All Visualizations"
    bl_description = "Clear all active visualization modules and restore materials"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            clear_all_visualizations()
            self.report({'INFO'}, "Cleared all visualizations")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error clearing all visualizations: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_unified_update_all_visualizations(Operator):
    """Update all active visualizations"""
    bl_idname = "visual.unified_update_all_visualizations"
    bl_label = "Update All Visualizations"
    bl_description = "Update all active visualization modules"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            update_all_visualizations()
            self.report({'INFO'}, "Updated all active visualizations")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error updating visualizations: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_smart_visualization_preset(Operator):
    """Apply smart visualization presets based on current context"""
    bl_idname = "visual.smart_visualization_preset"
    bl_label = "Smart Visualization Preset"
    bl_description = "Apply intelligent visualization preset based on current selection and context"
    bl_options = {'REGISTER', 'UNDO'}
    
    preset_type: EnumProperty(
        name="Preset Type",
        description="Type of smart preset to apply",
        items=[
            ('FOCUS', "Focus Mode", "Highlight selected objects, make others transparent"),
            ('EPOCH', "Epoch Analysis", "Color by epoch, clip non-active epochs"),
            ('PROPERTY', "Property Analysis", "Color by properties, smart transparency"),
            ('PRESENTATION', "Presentation Mode", "Clean view with subtle highlights"),
            ('ANALYSIS', "Analysis Mode", "Full transparency and clipping controls")
        ],
        default='FOCUS'
    ) # type: ignore
    
    def execute(self, context):
        manager = get_manager()
        scene = context.scene
        
        try:
            # Clear existing visualizations first
            clear_all_visualizations()
            
            if self.preset_type == 'FOCUS':
                # Focus mode: transparent non-selected, highlight selected
                if hasattr(scene, 'transparency_settings'):
                    transparency_settings = {
                        'transparency_factor': 0.7,
                        'transparency_mode': 'SELECTION',
                        'affect_selected_only': False,
                        'affect_visible_only': True
                    }
                    manager.activate_module('transparency', transparency_settings)
                
                if hasattr(scene, 'color_overlay_settings'):
                    overlay_settings = {
                        'overlay_strength': 0.3,
                        'overlay_mode': 'CUSTOM',
                        'custom_overlay_color': (1.0, 0.8, 0.2),  # Golden highlight
                        'blend_mode': 'ADD'
                    }
                    manager.activate_module('color_overlay', overlay_settings)
            
            elif self.preset_type == 'EPOCH':
                # Epoch analysis mode
                if hasattr(scene, 'color_overlay_settings'):
                    overlay_settings = {
                        'overlay_strength': 0.6,
                        'overlay_mode': 'EPOCH',
                        'blend_mode': 'OVERLAY'
                    }
                    manager.activate_module('color_overlay', overlay_settings)
                
                if hasattr(scene, 'transparency_settings'):
                    transparency_settings = {
                        'transparency_factor': 0.5,
                        'transparency_mode': 'EPOCH',
                        'affect_selected_only': False,
                        'affect_visible_only': True
                    }
                    manager.activate_module('transparency', transparency_settings)
            
            elif self.preset_type == 'PROPERTY':
                # Property analysis mode
                if hasattr(scene, 'color_overlay_settings'):
                    overlay_settings = {
                        'overlay_strength': 0.8,
                        'overlay_mode': 'PROPERTY',
                        'blend_mode': 'COLOR'
                    }
                    manager.activate_module('color_overlay', overlay_settings)
            
            elif self.preset_type == 'PRESENTATION':
                # Clean presentation mode
                if hasattr(scene, 'color_overlay_settings'):
                    overlay_settings = {
                        'overlay_strength': 0.2,
                        'overlay_mode': 'EM_TYPE',
                        'blend_mode': 'OVERLAY'
                    }
                    manager.activate_module('color_overlay', overlay_settings)
            
            elif self.preset_type == 'ANALYSIS':
                # Full analysis mode - activate all modules with moderate settings
                if hasattr(scene, 'transparency_settings'):
                    transparency_settings = {
                        'transparency_factor': 0.4,
                        'transparency_mode': 'SELECTION'
                    }
                    manager.activate_module('transparency', transparency_settings)
                
                if hasattr(scene, 'color_overlay_settings'):
                    overlay_settings = {
                        'overlay_strength': 0.5,
                        'overlay_mode': 'EM_TYPE',
                        'blend_mode': 'ADD'
                    }
                    manager.activate_module('color_overlay', overlay_settings)
                
                # Create a camera clipping plane if camera is active
                if scene.camera:
                    bpy.ops.visual.create_camera_clipping_plane()
            
            self.report({'INFO'}, f"Applied {self.preset_type.lower()} visualization preset")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error applying preset: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_visualization_performance_info(Operator):
    """Display visualization performance information"""
    bl_idname = "visual.visualization_performance_info"
    bl_label = "Show Performance Info"
    bl_description = "Display current visualization performance information"
    
    def execute(self, context):
        manager = get_manager()
        perf_info = manager.get_performance_info()
        
        message = f"""Visualization Performance Info:
        
Performance Mode: {'Yes' if perf_info['performance_mode'] else 'No'}
Active Modules: {perf_info['active_modules']}
Target Objects: {perf_info['target_objects']}
Pending Updates: {perf_info['pending_updates']}
Material Snapshots: {perf_info['material_snapshots']}
Last Update: {perf_info['last_update']:.2f}s ago"""
        
        def draw(self, context):
            lines = message.split('\n')
            for line in lines:
                if line.strip():
                    self.layout.label(text=line.strip())
        
        context.window_manager.popup_menu(draw, title="Performance Information", icon='INFO')
        return {'FINISHED'}

class VISUAL_OT_create_visualization_setup(Operator):
    """Create a complete visualization setup for current scene"""
    bl_idname = "visual.create_visualization_setup"
    bl_label = "Create Visualization Setup"
    bl_description = "Create a complete visualization setup optimized for the current scene"
    bl_options = {'REGISTER', 'UNDO'}
    
    include_clipping: BoolProperty(
        name="Include Clipping",
        description="Create clipping volumes for section analysis",
        default=True
    ) # type: ignore
    
    include_camera_setup: BoolProperty(
        name="Setup Cameras",
        description="Setup cameras with labels and clipping planes",
        default=True
    ) # type: ignore
    
    optimize_for_presentation: BoolProperty(
        name="Presentation Mode",
        description="Optimize settings for presentation/documentation",
        default=False
    ) # type: ignore
    
    def execute(self, context):
        scene = context.scene
        
        try:
            # Clear existing visualizations
            clear_all_visualizations()
            
            # Create standard collections if they don't exist
            collections_to_create = ["CAMS", "EM", "Proxy", "RM"]
            for collection_name in collections_to_create:
                if not bpy.data.collections.get(collection_name):
                    collection = bpy.data.collections.new(collection_name)
                    scene.collection.children.link(collection)
            
            # Setup camera system if requested
            if self.include_camera_setup:
                if scene.camera:
                    # Move camera to CAMS collection
                    cams_collection = bpy.data.collections.get("CAMS")
                    if cams_collection and scene.camera.name not in cams_collection.objects:
                        # Remove from other collections
                        for collection in scene.camera.users_collection:
                            if collection != cams_collection:
                                collection.objects.unlink(scene.camera)
                        # Add to CAMS
                        cams_collection.objects.link(scene.camera)
                    
                    # Create camera clipping plane if clipping is enabled
                    if self.include_clipping:
                        bpy.ops.visual.create_camera_clipping_plane()
                
                # Update camera list
                bpy.ops.visual.update_camera_list()
            
            # Apply appropriate visualization preset
            if self.optimize_for_presentation:
                bpy.ops.visual.smart_visualization_preset(preset_type='PRESENTATION')
            else:
                bpy.ops.visual.smart_visualization_preset(preset_type='ANALYSIS')
            
            setup_components = []
            setup_components.append("Collections created")
            if self.include_camera_setup:
                setup_components.append("Camera setup")
            if self.include_clipping:
                setup_components.append("Clipping volumes")
            setup_components.append("Visualization presets")
            
            self.report({'INFO'}, f"Created visualization setup: {', '.join(setup_components)}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error creating visualization setup: {str(e)}")
            return {'CANCELLED'}

def register_unified_operators():
    """Register all unified operators."""
    classes = [
        VisualizationManagerSettings,
        VISUAL_OT_unified_apply_visualization,
        VISUAL_OT_unified_clear_visualization,
        VISUAL_OT_unified_clear_all_visualizations,
        VISUAL_OT_unified_update_all_visualizations,
        VISUAL_OT_smart_visualization_preset,
        VISUAL_OT_visualization_performance_info,
        VISUAL_OT_create_visualization_setup,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
    
    # Add settings to scene
    if not hasattr(bpy.types.Scene, "visualization_manager_settings"):
        bpy.types.Scene.visualization_manager_settings = bpy.props.PointerProperty(type=VisualizationManagerSettings)

def unregister_unified_operators():
    """Unregister all unified operators."""
    # Remove scene properties
    if hasattr(bpy.types.Scene, "visualization_manager_settings"):
        del bpy.types.Scene.visualization_manager_settings
    
    classes = [
        VISUAL_OT_create_visualization_setup,
        VISUAL_OT_visualization_performance_info,
        VISUAL_OT_smart_visualization_preset,
        VISUAL_OT_unified_update_all_visualizations,
        VISUAL_OT_unified_clear_all_visualizations,
        VISUAL_OT_unified_clear_visualization,
        VISUAL_OT_unified_apply_visualization,
        VisualizationManagerSettings,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            pass
