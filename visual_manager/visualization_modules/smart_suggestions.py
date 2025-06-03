"""
Smart Suggestions System for Visualization Modules
This module analyzes the current context and suggests appropriate visualizations.
"""

import bpy
from typing import List, Dict, Any, Tuple, Optional
from bpy.types import Operator, PropertyGroup
from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty

from .manager import get_manager
from .utils import get_em_objects
from .preset_system import get_preset_manager

class VisualizationSuggestion(PropertyGroup):
    """Individual visualization suggestion"""
    
    title: StringProperty(
        name="Title",
        description="Title of the suggestion",
        default=""
    ) # type: ignore
    
    description: StringProperty(
        name="Description",
        description="Detailed description of what this suggestion does",
        default=""
    ) # type: ignore
    
    reasoning: StringProperty(
        name="Reasoning",
        description="Why this suggestion is relevant",
        default=""
    ) # type: ignore
    
    preset_id: StringProperty(
        name="Preset ID",
        description="ID of preset to apply for this suggestion",
        default=""
    ) # type: ignore
    
    confidence: IntProperty(
        name="Confidence",
        description="Confidence level (0-100) for this suggestion",
        min=0,
        max=100,
        default=50
    ) # type: ignore
    
    priority: IntProperty(
        name="Priority",
        description="Priority level (higher = more important)",
        min=0,
        max=10,
        default=5
    ) # type: ignore
    
    icon: StringProperty(
        name="Icon",
        description="Icon name for UI display",
        default="LIGHTPROBE_PLANE"
    ) # type: ignore

class SmartSuggestionEngine:
    """Engine for analyzing context and generating visualization suggestions"""
    
    def __init__(self):
        self.analyzers = [
            self._analyze_selection_context,
            self._analyze_epoch_context,
            self._analyze_property_context,
            self._analyze_camera_context,
            self._analyze_scene_complexity,
            self._analyze_object_distribution,
            self._analyze_current_mode
        ]
    
    def generate_suggestions(self, context) -> List[Dict[str, Any]]:
        """
        Generate visualization suggestions based on current context.
        
        Args:
            context: Blender context
            
        Returns:
            List of suggestion dictionaries
        """
        suggestions = []
        
        # Run all analyzers
        for analyzer in self.analyzers:
            try:
                analyzer_suggestions = analyzer(context)
                suggestions.extend(analyzer_suggestions)
            except Exception as e:
                print(f"Error in analyzer {analyzer.__name__}: {e}")
        
        # Score and rank suggestions
        scored_suggestions = self._score_suggestions(suggestions, context)
        
        # Remove duplicates and low-confidence suggestions
        filtered_suggestions = self._filter_suggestions(scored_suggestions)
        
        # Sort by priority and confidence
        filtered_suggestions.sort(key=lambda s: (s['priority'], s['confidence']), reverse=True)
        
        return filtered_suggestions[:10]  # Return top 10 suggestions
    
    def _analyze_selection_context(self, context) -> List[Dict[str, Any]]:
        """Analyze current selection and suggest appropriate visualizations."""
        suggestions = []
        scene = context.scene
        
        selected_objects = context.selected_objects
        em_objects = get_em_objects()
        
        if not selected_objects:
            suggestions.append({
                'title': 'No Selection Focus',
                'description': 'No objects selected. Consider selecting objects to highlight specific elements.',
                'reasoning': 'No current selection detected',
                'preset_id': '',
                'confidence': 30,
                'priority': 2,
                'icon': 'RESTRICT_SELECT_OFF'
            })
            return suggestions
        
        selected_count = len(selected_objects)
        total_em_count = len(em_objects)
        
        if selected_count > 0 and selected_count < total_em_count * 0.3:
            # Few objects selected - good for focus mode
            suggestions.append({
                'title': 'Focus on Selected Objects',
                'description': f'Highlight {selected_count} selected objects and make others semi-transparent',
                'reasoning': f'Small selection ({selected_count}/{total_em_count} objects) ideal for focus visualization',
                'preset_id': 'focus_selected',
                'confidence': 85,
                'priority': 8,
                'icon': 'ZOOM_SELECTED'
            })
        
        elif selected_count > total_em_count * 0.7:
            # Many objects selected - might want to highlight non-selected
            suggestions.append({
                'title': 'Highlight Non-Selected',
                'description': 'Make non-selected objects more prominent for comparison',
                'reasoning': f'Large selection ({selected_count}/{total_em_count} objects) - might want to see what\'s not selected',
                'preset_id': 'focus_selected',  # Would need inverse version
                'confidence': 60,
                'priority': 5,
                'icon': 'ZOOM_OUT'
            })
        
        return suggestions
    
    def _analyze_epoch_context(self, context) -> List[Dict[str, Any]]:
        """Analyze epoch-related context for suggestions."""
        suggestions = []
        scene = context.scene
        
        # Check if we have epoch data
        if not hasattr(scene, 'epoch_list') or len(scene.epoch_list) == 0:
            return suggestions
        
        epoch_count = len(scene.epoch_list)
        
        if epoch_count > 1:
            suggestions.append({
                'title': 'Epoch Analysis',
                'description': f'Visualize {epoch_count} different time periods with color coding',
                'reasoning': f'Scene contains {epoch_count} epochs - temporal analysis would be valuable',
                'preset_id': 'epoch_analysis',
                'confidence': 75,
                'priority': 7,
                'icon': 'TIME'
            })
        
        # Check if there's an active epoch selection
        if hasattr(scene, 'epoch_list_index') and scene.epoch_list_index >= 0:
            if scene.epoch_list_index < len(scene.epoch_list):
                active_epoch = scene.epoch_list[scene.epoch_list_index]
                suggestions.append({
                    'title': f'Focus on {active_epoch.name} Epoch',
                    'description': f'Highlight objects from the {active_epoch.name} period',
                    'reasoning': f'Active epoch selection ({active_epoch.name}) suggests temporal focus',
                    'preset_id': 'epoch_analysis',
                    'confidence': 80,
                    'priority': 8,
                    'icon': 'SEQ_SEQUENCER'
                })
        
        return suggestions
    
    def _analyze_property_context(self, context) -> List[Dict[str, Any]]:
        """Analyze property-related context for suggestions."""
        suggestions = []
        scene = context.scene
        
        # Check if we have property data
        if hasattr(scene, 'selected_property') and scene.selected_property:
            property_name = scene.selected_property
            
            suggestions.append({
                'title': f'Property Analysis: {property_name}',
                'description': f'Visualize objects based on their {property_name} values',
                'reasoning': f'Active property selection ({property_name}) suggests property-based analysis',
                'preset_id': 'property_analysis',
                'confidence': 85,
                'priority': 9,
                'icon': 'PROPERTIES'
            })
        
        # Check if property values are available
        if hasattr(scene, 'property_values') and len(scene.property_values) > 0:
            value_count = len(scene.property_values)
            
            suggestions.append({
                'title': 'Color by Property Values',
                'description': f'Apply distinct colors for {value_count} different property values',
                'reasoning': f'Property values loaded ({value_count} unique values) - color coding would help differentiate',
                'preset_id': 'property_analysis',
                'confidence': 70,
                'priority': 6,
                'icon': 'COLOR'
            })
        
        return suggestions
    
    def _analyze_camera_context(self, context) -> List[Dict[str, Any]]:
        """Analyze camera-related context for suggestions."""
        suggestions = []
        scene = context.scene
        
        if scene.camera:
            camera_name = scene.camera.name
            
            # Check if we're in camera view
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            if space.region_3d.view_perspective == 'CAMERA':
                                suggestions.append({
                                    'title': 'Presentation Setup',
                                    'description': 'Optimize visualization for camera view presentation',
                                    'reasoning': 'Currently in camera view - presentation mode would be ideal',
                                    'preset_id': 'presentation_clean',
                                    'confidence': 90,
                                    'priority': 9,
                                    'icon': 'CAMERA_DATA'
                                })
                                
                                suggestions.append({
                                    'title': 'Camera Clipping Analysis',
                                    'description': 'Add clipping plane for sectional analysis from camera view',
                                    'reasoning': 'Camera view active - clipping would provide sectional insights',
                                    'preset_id': 'section_analysis',
                                    'confidence': 75,
                                    'priority': 7,
                                    'icon': 'MOD_BOOLEAN'
                                })
                            break
                    break
            
            # Check for labels
            label_objects = [obj for obj in scene.objects if obj.name.startswith(f'_generated.{camera_name}.')]
            if label_objects:
                suggestions.append({
                    'title': 'Label Enhancement',
                    'description': f'Enhance visibility of {len(label_objects)} camera labels',
                    'reasoning': f'Camera has {len(label_objects)} labels - enhancement would improve readability',
                    'preset_id': 'presentation_clean',
                    'confidence': 65,
                    'priority': 5,
                    'icon': 'OUTLINER_OB_FONT'
                })
        
        return suggestions
    
    def _analyze_scene_complexity(self, context) -> List[Dict[str, Any]]:
        """Analyze scene complexity and suggest optimizations."""
        suggestions = []
        
        em_objects = get_em_objects()
        object_count = len(em_objects)
        
        if object_count > 500:
            suggestions.append({
                'title': 'Performance Optimization',
                'description': 'Use simplified visualization for large scene',
                'reasoning': f'Large scene ({object_count} objects) - performance optimization recommended',
                'preset_id': 'presentation_clean',  # Lighter visualization
                'confidence': 80,
                'priority': 8,
                'icon': 'MODIFIER'
            })
        
        elif object_count > 100:
            suggestions.append({
                'title': 'Selective Visualization',
                'description': 'Apply visualization only to selected objects for better performance',
                'reasoning': f'Medium scene ({object_count} objects) - selective visualization recommended',
                'preset_id': 'focus_selected',
                'confidence': 60,
                'priority': 6,
                'icon': 'RESTRICT_SELECT_OFF'
            })
        
        return suggestions
    
    def _analyze_object_distribution(self, context) -> List[Dict[str, Any]]:
        """Analyze spatial distribution of objects."""
        suggestions = []
        scene = context.scene
        
        # Analyze object types if available
        if hasattr(scene, 'em_list'):
            node_types = {}
            for em_item in scene.em_list:
                if hasattr(em_item, 'node_type'):
                    node_type = em_item.node_type
                    node_types[node_type] = node_types.get(node_type, 0) + 1
            
            if len(node_types) > 2:
                suggestions.append({
                    'title': 'Material Type Analysis',
                    'description': f'Visualize {len(node_types)} different material types with color coding',
                    'reasoning': f'Scene contains diverse material types: {", ".join(node_types.keys())}',
                    'preset_id': 'material_study',
                    'confidence': 70,
                    'priority': 6,
                    'icon': 'MATERIAL'
                })
        
        return suggestions
    
    def _analyze_current_mode(self, context) -> List[Dict[str, Any]]:
        """Analyze current EM-TOOLS mode and context."""
        suggestions = []
        scene = context.scene
        
        # Check current display mode
        current_mode = getattr(scene, 'proxy_display_mode', 'select')
        
        if current_mode == 'Properties':
            suggestions.append({
                'title': 'Enhanced Property Visualization',
                'description': 'Apply advanced techniques to property visualization',
                'reasoning': 'Currently in Properties display mode - enhanced visualization would add insight',
                'preset_id': 'property_analysis',
                'confidence': 75,
                'priority': 7,
                'icon': 'PROPERTIES'
            })
        
        # Check if any visualizations are already active
        try:
            manager = get_manager()
            active_modules = manager.get_active_modules()
            
            if not active_modules:
                suggestions.append({
                    'title': 'Start with Focus Mode',
                    'description': 'Begin with a simple focus visualization',
                    'reasoning': 'No visualizations currently active - focus mode is a good starting point',
                    'preset_id': 'focus_selected',
                    'confidence': 60,
                    'priority': 5,
                    'icon': 'PLAY'
                })
            else:
                suggestions.append({
                    'title': 'Combine Techniques',
                    'description': f'Enhance current {", ".join(active_modules)} with additional techniques',
                    'reasoning': f'Active visualizations ({", ".join(active_modules)}) could be enhanced',
                    'preset_id': 'section_analysis',
                    'confidence': 50,
                    'priority': 4,
                    'icon': 'PLUS'
                })
        except:
            pass
        
        return suggestions
    
    def _score_suggestions(self, suggestions: List[Dict], context) -> List[Dict]:
        """Score suggestions based on context relevance."""
        for suggestion in suggestions:
            # Boost confidence based on context matches
            if context.selected_objects and 'selected' in suggestion['title'].lower():
                suggestion['confidence'] += 10
            
            if hasattr(context.scene, 'camera') and context.scene.camera and 'camera' in suggestion['title'].lower():
                suggestion['confidence'] += 15
            
            # Cap confidence at 100
            suggestion['confidence'] = min(suggestion['confidence'], 100)
        
        return suggestions
    
    def _filter_suggestions(self, suggestions: List[Dict]) -> List[Dict]:
        """Filter out duplicate and low-confidence suggestions."""
        # Remove duplicates by title
        seen_titles = set()
        filtered = []
        
        for suggestion in suggestions:
            if suggestion['title'] not in seen_titles and suggestion['confidence'] >= 40:
                seen_titles.add(suggestion['title'])
                filtered.append(suggestion)
        
        return filtered

# Global suggestion engine
suggestion_engine = SmartSuggestionEngine()

class VISUAL_OT_generate_suggestions(Operator):
    """Generate smart visualization suggestions"""
    bl_idname = "visual.generate_suggestions"
    bl_label = "Generate Smart Suggestions"
    bl_description = "Analyze current context and generate visualization suggestions"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        try:
            suggestions = suggestion_engine.generate_suggestions(context)
            
            # Clear existing suggestions
            context.scene.visualization_suggestions.clear()
            
            # Add new suggestions
            for suggestion_data in suggestions:
                suggestion = context.scene.visualization_suggestions.add()
                suggestion.title = suggestion_data['title']
                suggestion.description = suggestion_data['description']
                suggestion.reasoning = suggestion_data['reasoning']
                suggestion.preset_id = suggestion_data['preset_id']
                suggestion.confidence = suggestion_data['confidence']
                suggestion.priority = suggestion_data['priority']
                suggestion.icon = suggestion_data['icon']
            
            self.report({'INFO'}, f"Generated {len(suggestions)} suggestions")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error generating suggestions: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_apply_suggestion(Operator):
    """Apply a visualization suggestion"""
    bl_idname = "visual.apply_suggestion"
    bl_label = "Apply Suggestion"
    bl_description = "Apply the selected visualization suggestion"
    bl_options = {'REGISTER', 'UNDO'}
    
    suggestion_index: IntProperty(
        name="Suggestion Index",
        description="Index of suggestion to apply"
    ) # type: ignore
    
    def execute(self, context):
        scene = context.scene
        
        if self.suggestion_index < 0 or self.suggestion_index >= len(scene.visualization_suggestions):
            self.report({'ERROR'}, "Invalid suggestion index")
            return {'CANCELLED'}
        
        suggestion = scene.visualization_suggestions[self.suggestion_index]
        
        try:
            if suggestion.preset_id:
                # Apply the suggested preset
                preset_manager = get_preset_manager()
                success = preset_manager.load_preset(suggestion.preset_id)
                
                if success:
                    self.report({'INFO'}, f"Applied suggestion: {suggestion.title}")
                    return {'FINISHED'}
                else:
                    self.report({'ERROR'}, f"Failed to apply preset: {suggestion.preset_id}")
                    return {'CANCELLED'}
            else:
                self.report({'WARNING'}, "Suggestion has no associated preset")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Error applying suggestion: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_suggestions_popup(Operator):
    """Show suggestions in popup menu"""
    bl_idname = "visual.suggestions_popup"
    bl_label = "Visualization Suggestions"
    bl_description = "Show smart visualization suggestions"
    
    def invoke(self, context, event):
        # Generate suggestions first
        bpy.ops.visual.generate_suggestions()
        
        # Show popup
        return context.window_manager.invoke_popup(self, width=400)
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        if not scene.visualization_suggestions:
            layout.label(text="No suggestions available", icon='INFO')
            return
        
        layout.label(text="Smart Visualization Suggestions:", icon='LIGHTPROBE_PLANE')
        
        for i, suggestion in enumerate(scene.visualization_suggestions[:5]):  # Show top 5
            box = layout.box()
            
            # Title and confidence
            row = box.row()
            row.label(text=suggestion.title, icon=suggestion.icon)
            row.label(text=f"{suggestion.confidence}%")
            
            # Description
            box.label(text=suggestion.description)
            
            # Reasoning (smaller text)
            row = box.row()
            row.scale_y = 0.8
            row.label(text=f"Why: {suggestion.reasoning}")
            
            # Apply button
            row = box.row()
            op = row.operator("visual.apply_suggestion", text="Apply", icon='CHECKMARK')
            op.suggestion_index = i
    
    def execute(self, context):
        return {'FINISHED'}

def register_smart_suggestions():
    """Register smart suggestions system."""
    classes = [
        VisualizationSuggestion,
        VISUAL_OT_generate_suggestions,
        VISUAL_OT_apply_suggestion,
        VISUAL_OT_suggestions_popup,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
    
    # Add suggestions list to scene
    if not hasattr(bpy.types.Scene, "visualization_suggestions"):
        bpy.types.Scene.visualization_suggestions = CollectionProperty(type=VisualizationSuggestion)
    
    if not hasattr(bpy.types.Scene, "visualization_suggestions_index"):
        bpy.types.Scene.visualization_suggestions_index = IntProperty()

def unregister_smart_suggestions():
    """Unregister smart suggestions system."""
    # Remove scene properties
    if hasattr(bpy.types.Scene, "visualization_suggestions"):
        del bpy.types.Scene.visualization_suggestions
    
    if hasattr(bpy.types.Scene, "visualization_suggestions_index"):
        del bpy.types.Scene.visualization_suggestions_index
    
    classes = [
        VISUAL_OT_suggestions_popup,
        VISUAL_OT_apply_suggestion,
        VISUAL_OT_generate_suggestions,
        VisualizationSuggestion,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            pass

# Convenience functions
def get_suggestions_for_context(context):
    """Get suggestions for current context."""
    return suggestion_engine.generate_suggestions(context)

def auto_suggest_on_context_change(context):
    """Automatically generate suggestions when context changes."""
    try:
        # Check if auto-suggestions are enabled
        if hasattr(context.scene, 'visualization_manager_settings'):
            settings = context.scene.visualization_manager_settings
            if getattr(settings, 'auto_suggestions', False):
                bpy.ops.visual.generate_suggestions()
    except:
        pass  # Fail silently in handlers
