"""
Temporal Integration for Visualization Modules
This module provides advanced integration with EM-TOOLS epoch system,
including temporal transitions and chronological analysis.
"""

import bpy
import time
from typing import List, Dict, Any, Tuple, Optional
from bpy.types import Operator, PropertyGroup
from bpy.props import (
    StringProperty, BoolProperty, IntProperty, FloatProperty, 
    EnumProperty, CollectionProperty
)

from .manager import get_manager
from .utils import get_em_objects

class EpochVisualizationSettings(PropertyGroup):
    """Settings for epoch-based visualizations"""
    
    temporal_mode: EnumProperty(
        name="Temporal Mode",
        description="How to visualize temporal relationships",
        items=[
            ('SEQUENTIAL', "Sequential", "Show epochs in chronological order"),
            ('COMPARATIVE', "Comparative", "Compare multiple epochs simultaneously"),
            ('PROGRESSIVE', "Progressive", "Show cumulative progression through time"),
            ('FOCUS', "Focus", "Focus on single epoch with context")
        ],
        default='SEQUENTIAL'
    ) # type: ignore
    
    transition_duration: FloatProperty(
        name="Transition Duration",
        description="Duration of transitions between epochs (seconds)",
        min=0.1,
        max=10.0,
        default=2.0
    ) # type: ignore
    
    show_temporal_context: BoolProperty(
        name="Show Temporal Context",
        description="Show objects from adjacent time periods with reduced visibility",
        default=True
    ) # type: ignore
    
    context_transparency: FloatProperty(
        name="Context Transparency",
        description="Transparency level for temporal context objects",
        min=0.1,
        max=0.9,
        default=0.7
    ) # type: ignore
    
    use_chronological_colors: BoolProperty(
        name="Chronological Colors",
        description="Use colors that progress chronologically",
        default=True
    ) # type: ignore
    
    animate_transitions: BoolProperty(
        name="Animate Transitions",
        description="Use animated transitions between temporal states",
        default=False
    ) # type: ignore
    
    auto_advance: BoolProperty(
        name="Auto Advance",
        description="Automatically advance through epochs",
        default=False
    ) # type: ignore
    
    auto_advance_interval: FloatProperty(
        name="Auto Advance Interval",
        description="Interval between automatic advances (seconds)",
        min=1.0,
        max=30.0,
        default=5.0
    ) # type: ignore

class TemporalAnalyzer:
    """Analyzes temporal relationships in EM data"""
    
    def __init__(self):
        self.epoch_cache = {}
        self.temporal_relationships = {}
    
    def analyze_temporal_structure(self, context) -> Dict[str, Any]:
        """
        Analyze the temporal structure of the scene.
        
        Returns:
            Dictionary with temporal analysis results
        """
        scene = context.scene
        analysis = {
            'epochs': [],
            'temporal_span': {},
            'object_distributions': {},
            'relationships': {},
            'chronological_order': []
        }
        
        if not hasattr(scene, 'epoch_list') or len(scene.epoch_list) == 0:
            return analysis
        
        # Collect epoch information
        epochs_data = []
        for epoch in scene.epoch_list:
            epoch_info = {
                'name': epoch.name,
                'start_time': getattr(epoch, 'start_time', 0),
                'end_time': getattr(epoch, 'end_time', 0),
                'color': getattr(epoch, 'epoch_RGB_color', (0.5, 0.5, 0.5)),
                'objects': []
            }
            
            # Find objects in this epoch
            if hasattr(scene, 'em_list'):
                for em_item in scene.em_list:
                    if hasattr(em_item, 'epoch') and em_item.epoch == epoch.name:
                        epoch_info['objects'].append(em_item.name)
            
            epochs_data.append(epoch_info)
        
        # Sort by chronological order
        epochs_data.sort(key=lambda e: e['start_time'])
        
        analysis['epochs'] = epochs_data
        analysis['chronological_order'] = [e['name'] for e in epochs_data]
        
        # Calculate temporal span
        if epochs_data:
            analysis['temporal_span'] = {
                'earliest': min(e['start_time'] for e in epochs_data),
                'latest': max(e['end_time'] for e in epochs_data),
                'total_duration': max(e['end_time'] for e in epochs_data) - min(e['start_time'] for e in epochs_data)
            }
        
        # Analyze object distributions
        for epoch_info in epochs_data:
            analysis['object_distributions'][epoch_info['name']] = len(epoch_info['objects'])
        
        # Analyze relationships (overlaps, sequences, etc.)
        analysis['relationships'] = self._analyze_epoch_relationships(epochs_data)
        
        return analysis
    
    def _analyze_epoch_relationships(self, epochs_data: List[Dict]) -> Dict[str, Any]:
        """Analyze relationships between epochs."""
        relationships = {
            'overlapping': [],
            'sequential': [],
            'gaps': []
        }
        
        for i, epoch1 in enumerate(epochs_data):
            for j, epoch2 in enumerate(epochs_data[i+1:], i+1):
                # Check for overlap
                if (epoch1['start_time'] <= epoch2['end_time'] and 
                    epoch2['start_time'] <= epoch1['end_time']):
                    relationships['overlapping'].append((epoch1['name'], epoch2['name']))
                
                # Check for sequential relationship
                elif epoch1['end_time'] <= epoch2['start_time']:
                    gap_duration = epoch2['start_time'] - epoch1['end_time']
                    if gap_duration == 0:
                        relationships['sequential'].append((epoch1['name'], epoch2['name']))
                    else:
                        relationships['gaps'].append({
                            'before': epoch1['name'],
                            'after': epoch2['name'],
                            'duration': gap_duration
                        })
        
        return relationships
    
    def get_chronological_color_gradient(self, epoch_count: int) -> List[Tuple[float, float, float]]:
        """Generate a chronological color gradient."""
        colors = []
        
        # Define color progression (cool to warm over time)
        start_color = (0.2, 0.4, 0.8)  # Cool blue
        end_color = (0.8, 0.4, 0.2)    # Warm orange
        
        for i in range(epoch_count):
            if epoch_count == 1:
                factor = 0.5
            else:
                factor = i / (epoch_count - 1)
            
            color = (
                start_color[0] + (end_color[0] - start_color[0]) * factor,
                start_color[1] + (end_color[1] - start_color[1]) * factor,
                start_color[2] + (end_color[2] - start_color[2]) * factor
            )
            colors.append(color)
        
        return colors

class TemporalVisualizationController:
    """Controls temporal visualization states and transitions"""
    
    def __init__(self):
        self.current_state = None
        self.target_state = None
        self.transition_progress = 0.0
        self.is_transitioning = False
        self.timer_handle = None
        self.analyzer = TemporalAnalyzer()
    
    def apply_temporal_visualization(self, context, epoch_name: str, settings: EpochVisualizationSettings):
        """Apply temporal visualization for a specific epoch."""
        scene = context.scene
        manager = get_manager()
        
        # Analyze temporal structure
        temporal_analysis = self.analyzer.analyze_temporal_structure(context)
        
        if not temporal_analysis['epochs']:
            print("No temporal data available")
            return False
        
        # Find target epoch
        target_epoch = None
        for epoch_data in temporal_analysis['epochs']:
            if epoch_data['name'] == epoch_name:
                target_epoch = epoch_data
                break
        
        if not target_epoch:
            print(f"Epoch {epoch_name} not found")
            return False
        
        # Clear existing visualizations
        manager.clear_all_modules()
        
        # Apply visualization based on temporal mode
        if settings.temporal_mode == 'SEQUENTIAL':
            return self._apply_sequential_mode(context, target_epoch, temporal_analysis, settings)
        elif settings.temporal_mode == 'COMPARATIVE':
            return self._apply_comparative_mode(context, target_epoch, temporal_analysis, settings)
        elif settings.temporal_mode == 'PROGRESSIVE':
            return self._apply_progressive_mode(context, target_epoch, temporal_analysis, settings)
        elif settings.temporal_mode == 'FOCUS':
            return self._apply_focus_mode(context, target_epoch, temporal_analysis, settings)
        
        return False
    
    def _apply_sequential_mode(self, context, target_epoch, temporal_analysis, settings):
        """Apply sequential temporal visualization."""
        manager = get_manager()
        
        # Get chronological colors if enabled
        if settings.use_chronological_colors:
            colors = self.analyzer.get_chronological_color_gradient(len(temporal_analysis['epochs']))
            epoch_index = temporal_analysis['chronological_order'].index(target_epoch['name'])
            target_color = colors[epoch_index]
        else:
            target_color = target_epoch['color']
        
        # Apply color overlay for the target epoch
        overlay_settings = {
            'overlay_strength': 0.7,
            'overlay_mode': 'EPOCH',
            'blend_mode': 'OVERLAY',
            'affect_emission': True
        }
        
        # Apply transparency to non-target epochs
        transparency_settings = {
            'transparency_factor': 0.8,
            'transparency_mode': 'EPOCH',
            'affect_selected_only': False,
            'affect_visible_only': True
        }
        
        # Show temporal context if enabled
        if settings.show_temporal_context:
            transparency_settings['transparency_factor'] = settings.context_transparency
        
        manager.activate_module('color_overlay', overlay_settings)
        manager.activate_module('transparency', transparency_settings)
        
        return True
    
    def _apply_comparative_mode(self, context, target_epoch, temporal_analysis, settings):
        """Apply comparative temporal visualization."""
        manager = get_manager()
        
        # Use distinct colors for each epoch
        overlay_settings = {
            'overlay_strength': 0.6,
            'overlay_mode': 'EPOCH',
            'blend_mode': 'COLOR',
            'affect_emission': False
        }
        
        manager.activate_module('color_overlay', overlay_settings)
        
        return True
    
    def _apply_progressive_mode(self, context, target_epoch, temporal_analysis, settings):
        """Apply progressive temporal visualization."""
        manager = get_manager()
        
        # Show cumulative progression up to target epoch
        target_index = temporal_analysis['chronological_order'].index(target_epoch['name'])
        
        # Create gradient transparency for progression
        transparency_settings = {
            'transparency_factor': 0.3,  # Less transparent for more recent
            'transparency_mode': 'EPOCH',
            'affect_selected_only': False,
            'affect_visible_only': True
        }
        
        overlay_settings = {
            'overlay_strength': 0.5,
            'overlay_mode': 'EPOCH',
            'blend_mode': 'ADD',
            'affect_emission': True
        }
        
        manager.activate_module('transparency', transparency_settings)
        manager.activate_module('color_overlay', overlay_settings)
        
        return True
    
    def _apply_focus_mode(self, context, target_epoch, temporal_analysis, settings):
        """Apply focus temporal visualization."""
        manager = get_manager()
        
        # Strong focus on target epoch
        transparency_settings = {
            'transparency_factor': 0.9,
            'transparency_mode': 'EPOCH',
            'affect_selected_only': False,
            'affect_visible_only': True
        }
        
        overlay_settings = {
            'overlay_strength': 0.8,
            'overlay_mode': 'EPOCH',
            'blend_mode': 'OVERLAY',
            'affect_emission': True
        }
        
        manager.activate_module('transparency', transparency_settings)
        manager.activate_module('color_overlay', overlay_settings)
        
        # Add clipping if camera is available
        if context.scene.camera:
            clipping_settings = {
                'section_color': target_epoch['color'],
                'clipping_distance': 6.0,
                'use_camera_clipping': True,
                'affect_all_objects': False
            }
            manager.activate_module('clipping', clipping_settings)
        
        return True
    
    def start_temporal_sequence(self, context, settings: EpochVisualizationSettings):
        """Start an automated temporal sequence."""
        scene = context.scene
        
        if not hasattr(scene, 'epoch_list') or len(scene.epoch_list) == 0:
            return False
        
        temporal_analysis = self.analyzer.analyze_temporal_structure(context)
        
        self.current_epoch_index = 0
        self.epoch_sequence = temporal_analysis['chronological_order']
        self.sequence_settings = settings
        
        # Start with first epoch
        if self.epoch_sequence:
            self.apply_temporal_visualization(context, self.epoch_sequence[0], settings)
            
            if settings.auto_advance:
                self._start_auto_advance_timer(context)
        
        return True
    
    def advance_temporal_sequence(self, context):
        """Advance to the next epoch in the sequence."""
        if not hasattr(self, 'epoch_sequence') or not self.epoch_sequence:
            return False
        
        self.current_epoch_index = (self.current_epoch_index + 1) % len(self.epoch_sequence)
        current_epoch = self.epoch_sequence[self.current_epoch_index]
        
        self.apply_temporal_visualization(context, current_epoch, self.sequence_settings)
        
        return True
    
    def _start_auto_advance_timer(self, context):
        """Start the auto-advance timer."""
        if self.timer_handle:
            bpy.app.timers.unregister(self.timer_handle)
        
        def advance_callback():
            try:
                self.advance_temporal_sequence(context)
                return self.sequence_settings.auto_advance_interval if self.sequence_settings.auto_advance else None
            except:
                return None  # Stop timer on error
        
        self.timer_handle = bpy.app.timers.register(advance_callback, first_interval=self.sequence_settings.auto_advance_interval)
    
    def stop_auto_advance(self):
        """Stop the auto-advance timer."""
        if self.timer_handle:
            bpy.app.timers.unregister(self.timer_handle)
            self.timer_handle = None

# Global temporal controller
temporal_controller = TemporalVisualizationController()

class VISUAL_OT_temporal_analysis(Operator):
    """Apply temporal analysis visualization"""
    bl_idname = "visual.temporal_analysis"
    bl_label = "Temporal Analysis"
    bl_description = "Apply advanced temporal analysis visualization"
    bl_options = {'REGISTER', 'UNDO'}
    
    epoch_name: StringProperty(
        name="Epoch Name",
        description="Name of epoch to focus on"
    ) # type: ignore
    
    def execute(self, context):
        scene = context.scene
        
        if not hasattr(scene, 'epoch_temporal_settings'):
            self.report({'ERROR'}, "Temporal settings not available")
            return {'CANCELLED'}
        
        settings = scene.epoch_temporal_settings
        
        try:
            if self.epoch_name:
                success = temporal_controller.apply_temporal_visualization(context, self.epoch_name, settings)
            else:
                # Use currently selected epoch
                if hasattr(scene, 'epoch_list_index') and scene.epoch_list_index >= 0:
                    if scene.epoch_list_index < len(scene.epoch_list):
                        epoch = scene.epoch_list[scene.epoch_list_index]
                        success = temporal_controller.apply_temporal_visualization(context, epoch.name, settings)
                    else:
                        self.report({'ERROR'}, "Invalid epoch selection")
                        return {'CANCELLED'}
                else:
                    self.report({'ERROR'}, "No epoch selected")
                    return {'CANCELLED'}
            
            if success:
                epoch_name = self.epoch_name or scene.epoch_list[scene.epoch_list_index].name
                self.report({'INFO'}, f"Applied temporal analysis for {epoch_name}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Failed to apply temporal analysis")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Error applying temporal analysis: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_temporal_sequence(Operator):
    """Start temporal sequence visualization"""
    bl_idname = "visual.temporal_sequence"
    bl_label = "Start Temporal Sequence"
    bl_description = "Start automated temporal sequence through all epochs"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        
        if not hasattr(scene, 'epoch_temporal_settings'):
            self.report({'ERROR'}, "Temporal settings not available")
            return {'CANCELLED'}
        
        settings = scene.epoch_temporal_settings
        
        try:
            success = temporal_controller.start_temporal_sequence(context, settings)
            
            if success:
                self.report({'INFO'}, "Started temporal sequence")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Failed to start temporal sequence")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Error starting temporal sequence: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_temporal_advance(Operator):
    """Advance to next epoch in sequence"""
    bl_idname = "visual.temporal_advance"
    bl_label = "Next Epoch"
    bl_description = "Advance to the next epoch in the temporal sequence"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            success = temporal_controller.advance_temporal_sequence(context)
            
            if success:
                self.report({'INFO'}, "Advanced to next epoch")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Failed to advance sequence")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Error advancing sequence: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_temporal_stop(Operator):
    """Stop temporal sequence"""
    bl_idname = "visual.temporal_stop"
    bl_label = "Stop Sequence"
    bl_description = "Stop the temporal sequence and auto-advance"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            temporal_controller.stop_auto_advance()
            self.report({'INFO'}, "Stopped temporal sequence")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error stopping sequence: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_analyze_temporal_structure(Operator):
    """Analyze and display temporal structure"""
    bl_idname = "visual.analyze_temporal_structure"
    bl_label = "Analyze Temporal Structure"
    bl_description = "Analyze and display the temporal structure of the scene"
    
    def execute(self, context):
        try:
            analyzer = TemporalAnalyzer()
            analysis = analyzer.analyze_temporal_structure(context)
            
            if not analysis['epochs']:
                self.report({'WARNING'}, "No temporal data found")
                return {'CANCELLED'}
            
            # Prepare analysis message
            message_lines = []
            message_lines.append(f"Temporal Analysis Results:")
            message_lines.append(f"")
            message_lines.append(f"Epochs: {len(analysis['epochs'])}")
            
            if analysis['temporal_span']:
                span = analysis['temporal_span']
                message_lines.append(f"Time Span: {span['earliest']} - {span['latest']}")
                message_lines.append(f"Duration: {span['total_duration']} units")
            
            message_lines.append(f"")
            message_lines.append(f"Chronological Order:")
            for i, epoch_name in enumerate(analysis['chronological_order']):
                obj_count = analysis['object_distributions'].get(epoch_name, 0)
                message_lines.append(f"  {i+1}. {epoch_name} ({obj_count} objects)")
            
            if analysis['relationships']['overlapping']:
                message_lines.append(f"")
                message_lines.append(f"Overlapping Epochs:")
                for epoch1, epoch2 in analysis['relationships']['overlapping']:
                    message_lines.append(f"  • {epoch1} ↔ {epoch2}")
            
            # Show in popup
            def draw(self, context):
                for line in message_lines:
                    if line:
                        self.layout.label(text=line)
                    else:
                        self.layout.separator()
            
            context.window_manager.popup_menu(draw, title="Temporal Structure Analysis", icon='TIME')
            
            self.report({'INFO'}, f"Analyzed {len(analysis['epochs'])} epochs")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error analyzing temporal structure: {str(e)}")
            return {'CANCELLED'}

def register_temporal_integration():
    """Register temporal integration classes."""
    classes = [
        EpochVisualizationSettings,
        VISUAL_OT_temporal_analysis,
        VISUAL_OT_temporal_sequence,
        VISUAL_OT_temporal_advance,
        VISUAL_OT_temporal_stop,
        VISUAL_OT_analyze_temporal_structure,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
    
    # Add temporal settings to scene
    if not hasattr(bpy.types.Scene, "epoch_temporal_settings"):
        bpy.types.Scene.epoch_temporal_settings = bpy.props.PointerProperty(type=EpochVisualizationSettings)

def unregister_temporal_integration():
    """Unregister temporal integration classes."""
    # Stop any running timers
    temporal_controller.stop_auto_advance()
    
    # Remove scene properties
    if hasattr(bpy.types.Scene, "epoch_temporal_settings"):
        del bpy.types.Scene.epoch_temporal_settings
    
    classes = [
        VISUAL_OT_analyze_temporal_structure,
        VISUAL_OT_temporal_stop,
        VISUAL_OT_temporal_advance,
        VISUAL_OT_temporal_sequence,
        VISUAL_OT_temporal_analysis,
        EpochVisualizationSettings,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            pass

# Convenience functions
def get_temporal_controller():
    """Get the global temporal controller."""
    return temporal_controller

def quick_temporal_analysis(context, epoch_name: str):
    """Quick function to apply temporal analysis for an epoch."""
    settings = context.scene.epoch_temporal_settings if hasattr(context.scene, 'epoch_temporal_settings') else None
    if settings:
        return temporal_controller.apply_temporal_visualization(context, epoch_name, settings)
    return False

def start_epoch_sequence(context):
    """Quick function to start epoch sequence."""
    settings = context.scene.epoch_temporal_settings if hasattr(context.scene, 'epoch_temporal_settings') else None
    if settings:
        return temporal_controller.start_temporal_sequence(context, settings)
    return False
