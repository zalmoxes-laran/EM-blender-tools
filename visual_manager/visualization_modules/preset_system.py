"""
Preset System for Visualization Modules
This module provides save/load functionality for visualization presets and templates.
"""

import bpy
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from bpy.types import Operator, PropertyGroup
from bpy.props import StringProperty, BoolProperty, CollectionProperty, IntProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper

from .manager import get_manager

class VisualizationPreset(PropertyGroup):
    """Individual visualization preset"""
    
    name: StringProperty(
        name="Preset Name",
        description="Name of this preset",
        default="New Preset"
    ) # type: ignore
    
    description: StringProperty(
        name="Description", 
        description="Description of what this preset does",
        default=""
    ) # type: ignore
    
    category: EnumProperty(
        name="Category",
        description="Category of this preset",
        items=[
            ('GENERAL', "General", "General purpose presets"),
            ('ANALYSIS', "Analysis", "Analysis and research presets"),
            ('PRESENTATION', "Presentation", "Presentation and documentation presets"),
            ('EPOCH', "Epoch", "Epoch-specific presets"),
            ('PROPERTY', "Property", "Property-based presets"),
            ('CUSTOM', "Custom", "User-created custom presets")
        ],
        default='GENERAL'
    ) # type: ignore
    
    is_built_in: BoolProperty(
        name="Built-in Preset",
        description="Whether this is a built-in preset",
        default=False
    ) # type: ignore
    
    json_data: StringProperty(
        name="JSON Data",
        description="Serialized preset data",
        default=""
    ) # type: ignore

class PresetManager:
    """Manager for visualization presets"""
    
    def __init__(self):
        self.presets_dir = self._get_presets_directory()
        self.built_in_presets = self._create_built_in_presets()
        self._ensure_presets_directory()
    
    def _get_presets_directory(self) -> Path:
        """Get the directory for storing presets."""
        # Store in Blender's user config directory
        config_dir = Path(bpy.utils.resource_path('USER')) / "config" / "em_tools" / "visualization_presets"
        return config_dir
    
    def _ensure_presets_directory(self):
        """Ensure the presets directory exists."""
        self.presets_dir.mkdir(parents=True, exist_ok=True)
    
    def _create_built_in_presets(self) -> Dict[str, Dict]:
        """Create built-in presets."""
        return {
            'focus_selected': {
                'name': 'Focus on Selected',
                'description': 'Highlight selected objects, make others semi-transparent',
                'category': 'GENERAL',
                'modules': {
                    'transparency': {
                        'transparency_factor': 0.7,
                        'transparency_mode': 'SELECTION',
                        'affect_selected_only': False,
                        'affect_visible_only': True
                    },
                    'color_overlay': {
                        'overlay_strength': 0.3,
                        'overlay_mode': 'CUSTOM',
                        'custom_overlay_color': (1.0, 0.8, 0.2),
                        'blend_mode': 'ADD',
                        'affect_emission': False
                    }
                }
            },
            'epoch_analysis': {
                'name': 'Epoch Analysis',
                'description': 'Color-code by epochs with transparency for inactive periods',
                'category': 'EPOCH',
                'modules': {
                    'color_overlay': {
                        'overlay_strength': 0.6,
                        'overlay_mode': 'EPOCH',
                        'blend_mode': 'OVERLAY',
                        'affect_emission': True
                    },
                    'transparency': {
                        'transparency_factor': 0.5,
                        'transparency_mode': 'EPOCH',
                        'affect_selected_only': False,
                        'affect_visible_only': True
                    }
                }
            },
            'property_analysis': {
                'name': 'Property Analysis',
                'description': 'Visualize objects by their property values',
                'category': 'PROPERTY',
                'modules': {
                    'color_overlay': {
                        'overlay_strength': 0.8,
                        'overlay_mode': 'PROPERTY',
                        'blend_mode': 'COLOR',
                        'affect_emission': False
                    }
                }
            },
            'presentation_clean': {
                'name': 'Clean Presentation',
                'description': 'Subtle enhancements suitable for presentations',
                'category': 'PRESENTATION',
                'modules': {
                    'color_overlay': {
                        'overlay_strength': 0.2,
                        'overlay_mode': 'EM_TYPE',
                        'blend_mode': 'OVERLAY',
                        'affect_emission': False
                    }
                }
            },
            'section_analysis': {
                'name': 'Section Analysis',
                'description': 'Full analysis setup with clipping and transparency',
                'category': 'ANALYSIS',
                'modules': {
                    'transparency': {
                        'transparency_factor': 0.4,
                        'transparency_mode': 'SELECTION',
                        'affect_selected_only': False,
                        'affect_visible_only': True
                    },
                    'color_overlay': {
                        'overlay_strength': 0.5,
                        'overlay_mode': 'EM_TYPE',
                        'blend_mode': 'ADD',
                        'affect_emission': True
                    },
                    'clipping': {
                        'section_color': (0.4, 0.2, 0.6),
                        'clipping_distance': 5.0,
                        'clipping_mode': 'PLANE',
                        'use_camera_clipping': True,
                        'affect_all_objects': False
                    }
                }
            },
            'material_study': {
                'name': 'Material Study',
                'description': 'Enhanced visualization for material analysis',
                'category': 'ANALYSIS',
                'modules': {
                    'color_overlay': {
                        'overlay_strength': 0.4,
                        'overlay_mode': 'EM_TYPE',
                        'blend_mode': 'MULTIPLY',
                        'affect_emission': True
                    },
                    'transparency': {
                        'transparency_factor': 0.2,
                        'transparency_mode': 'SELECTION',
                        'affect_selected_only': True,
                        'affect_visible_only': True
                    }
                }
            }
        }
    
    def save_preset(self, name: str, description: str, category: str = 'CUSTOM') -> bool:
        """
        Save current visualization state as a preset.
        
        Args:
            name: Name of the preset
            description: Description of the preset
            category: Category for organization
            
        Returns:
            bool: Success status
        """
        try:
            manager = get_manager()
            active_modules = manager.get_active_modules()
            
            if not active_modules:
                print("No active modules to save")
                return False
            
            # Collect current settings
            preset_data = {
                'name': name,
                'description': description,
                'category': category,
                'modules': {}
            }
            
            for module_id in active_modules:
                settings = manager.get_module_settings(module_id)
                if settings:
                    preset_data['modules'][module_id] = settings
            
            # Save to file
            filename = f"{self._sanitize_filename(name)}.json"
            filepath = self.presets_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(preset_data, f, indent=2)
            
            print(f"Saved preset: {name} to {filepath}")
            return True
            
        except Exception as e:
            print(f"Error saving preset: {e}")
            return False
    
    def load_preset(self, preset_id: str) -> bool:
        """
        Load a preset by ID or filename.
        
        Args:
            preset_id: ID of preset to load
            
        Returns:
            bool: Success status
        """
        try:
            # Check if it's a built-in preset
            if preset_id in self.built_in_presets:
                preset_data = self.built_in_presets[preset_id]
            else:
                # Load from file
                if not preset_id.endswith('.json'):
                    preset_id += '.json'
                
                filepath = self.presets_dir / preset_id
                if not filepath.exists():
                    print(f"Preset file not found: {filepath}")
                    return False
                
                with open(filepath, 'r') as f:
                    preset_data = json.load(f)
            
            # Apply the preset
            return self._apply_preset_data(preset_data)
            
        except Exception as e:
            print(f"Error loading preset: {e}")
            return False
    
    def _apply_preset_data(self, preset_data: Dict) -> bool:
        """Apply preset data to the visualization system."""
        try:
            manager = get_manager()
            
            # Clear existing visualizations
            manager.clear_all_modules()
            
            # Apply modules from preset
            modules = preset_data.get('modules', {})
            
            for module_id, settings in modules.items():
                success = manager.activate_module(module_id, settings)
                if not success:
                    print(f"Warning: Failed to activate module {module_id}")
            
            return True
            
        except Exception as e:
            print(f"Error applying preset data: {e}")
            return False
    
    def get_available_presets(self) -> List[Dict[str, str]]:
        """Get list of all available presets."""
        presets = []
        
        # Add built-in presets
        for preset_id, preset_data in self.built_in_presets.items():
            presets.append({
                'id': preset_id,
                'name': preset_data['name'],
                'description': preset_data['description'],
                'category': preset_data['category'],
                'is_built_in': True
            })
        
        # Add user presets
        if self.presets_dir.exists():
            for filepath in self.presets_dir.glob('*.json'):
                try:
                    with open(filepath, 'r') as f:
                        preset_data = json.load(f)
                    
                    presets.append({
                        'id': filepath.stem,
                        'name': preset_data.get('name', filepath.stem),
                        'description': preset_data.get('description', ''),
                        'category': preset_data.get('category', 'CUSTOM'),
                        'is_built_in': False
                    })
                except Exception as e:
                    print(f"Error reading preset file {filepath}: {e}")
        
        return presets
    
    def delete_preset(self, preset_id: str) -> bool:
        """Delete a user preset."""
        try:
            if preset_id in self.built_in_presets:
                print("Cannot delete built-in preset")
                return False
            
            if not preset_id.endswith('.json'):
                preset_id += '.json'
            
            filepath = self.presets_dir / preset_id
            if filepath.exists():
                filepath.unlink()
                print(f"Deleted preset: {preset_id}")
                return True
            else:
                print(f"Preset not found: {preset_id}")
                return False
                
        except Exception as e:
            print(f"Error deleting preset: {e}")
            return False
    
    def export_preset(self, preset_id: str, export_path: str) -> bool:
        """Export a preset to external file."""
        try:
            # Load preset data
            if preset_id in self.built_in_presets:
                preset_data = self.built_in_presets[preset_id]
            else:
                filepath = self.presets_dir / f"{preset_id}.json"
                with open(filepath, 'r') as f:
                    preset_data = json.load(f)
            
            # Save to export path
            with open(export_path, 'w') as f:
                json.dump(preset_data, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error exporting preset: {e}")
            return False
    
    def import_preset(self, import_path: str) -> bool:
        """Import a preset from external file."""
        try:
            with open(import_path, 'r') as f:
                preset_data = json.load(f)
            
            # Validate preset data
            if not all(key in preset_data for key in ['name', 'modules']):
                print("Invalid preset file format")
                return False
            
            # Save to user presets
            name = preset_data['name']
            filename = f"{self._sanitize_filename(name)}.json"
            filepath = self.presets_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(preset_data, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error importing preset: {e}")
            return False
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a name for use as filename."""
        import re
        # Replace invalid characters with underscores
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        # Remove leading/trailing whitespace and dots
        sanitized = sanitized.strip(' .')
        # Limit length
        return sanitized[:50] if sanitized else "preset"

# Global preset manager instance
preset_manager = PresetManager()

class VISUAL_OT_save_preset(Operator):
    """Save current visualization state as preset"""
    bl_idname = "visual.save_preset"
    bl_label = "Save Visualization Preset"
    bl_description = "Save current visualization state as a reusable preset"
    bl_options = {'REGISTER', 'UNDO'}
    
    preset_name: StringProperty(
        name="Preset Name",
        description="Name for the new preset",
        default="My Preset"
    ) # type: ignore
    
    preset_description: StringProperty(
        name="Description",
        description="Description of what this preset does",
        default=""
    ) # type: ignore
    
    preset_category: EnumProperty(
        name="Category",
        description="Category for organization",
        items=[
            ('GENERAL', "General", "General purpose presets"),
            ('ANALYSIS', "Analysis", "Analysis and research presets"),
            ('PRESENTATION', "Presentation", "Presentation and documentation presets"),
            ('EPOCH', "Epoch", "Epoch-specific presets"),
            ('PROPERTY', "Property", "Property-based presets"),
            ('CUSTOM', "Custom", "User-created custom presets")
        ],
        default='CUSTOM'
    ) # type: ignore
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)
    
    def draw(self, context):
        layout = self.layout
        
        layout.prop(self, "preset_name")
        layout.prop(self, "preset_description")
        layout.prop(self, "preset_category")
        
        # Show active modules
        try:
            from .manager import get_manager
            manager = get_manager()
            active_modules = manager.get_active_modules()
            
            if active_modules:
                box = layout.box()
                box.label(text="Active Modules to Save:")
                for module_id in active_modules:
                    box.label(text=f"• {module_id.title()}", icon='CHECKMARK')
            else:
                layout.label(text="No active visualizations to save", icon='ERROR')
        except:
            pass
    
    def execute(self, context):
        if not self.preset_name.strip():
            self.report({'ERROR'}, "Preset name cannot be empty")
            return {'CANCELLED'}
        
        try:
            success = preset_manager.save_preset(
                self.preset_name,
                self.preset_description,
                self.preset_category
            )
            
            if success:
                self.report({'INFO'}, f"Saved preset: {self.preset_name}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Failed to save preset")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Error saving preset: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_load_preset(Operator):
    """Load a visualization preset"""
    bl_idname = "visual.load_preset"
    bl_label = "Load Visualization Preset"
    bl_description = "Load a saved visualization preset"
    bl_options = {'REGISTER', 'UNDO'}
    
    preset_id: StringProperty(
        name="Preset ID",
        description="ID of preset to load"
    ) # type: ignore
    
    def execute(self, context):
        if not self.preset_id:
            self.report({'ERROR'}, "No preset specified")
            return {'CANCELLED'}
        
        try:
            success = preset_manager.load_preset(self.preset_id)
            
            if success:
                self.report({'INFO'}, f"Loaded preset: {self.preset_id}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Failed to load preset")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Error loading preset: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_delete_preset(Operator):
    """Delete a user preset"""
    bl_idname = "visual.delete_preset"
    bl_label = "Delete Preset"
    bl_description = "Delete a user-created preset"
    bl_options = {'REGISTER', 'UNDO'}
    
    preset_id: StringProperty(
        name="Preset ID",
        description="ID of preset to delete"
    ) # type: ignore
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)
    
    def execute(self, context):
        try:
            success = preset_manager.delete_preset(self.preset_id)
            
            if success:
                self.report({'INFO'}, f"Deleted preset: {self.preset_id}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Failed to delete preset")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Error deleting preset: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_export_preset(Operator, ExportHelper):
    """Export a preset to external file"""
    bl_idname = "visual.export_preset"
    bl_label = "Export Preset"
    bl_description = "Export a visualization preset to external file"
    filename_ext = ".empreset"
    
    preset_id: StringProperty(
        name="Preset ID",
        description="ID of preset to export"
    ) # type: ignore
    
    def execute(self, context):
        try:
            success = preset_manager.export_preset(self.preset_id, self.filepath)
            
            if success:
                self.report({'INFO'}, f"Exported preset to: {self.filepath}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Failed to export preset")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Error exporting preset: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_import_preset(Operator, ImportHelper):
    """Import a preset from external file"""
    bl_idname = "visual.import_preset"
    bl_label = "Import Preset"
    bl_description = "Import a visualization preset from external file"
    filename_ext = ".empreset"
    
    def execute(self, context):
        try:
            success = preset_manager.import_preset(self.filepath)
            
            if success:
                self.report({'INFO'}, f"Imported preset from: {self.filepath}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Failed to import preset")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Error importing preset: {str(e)}")
            return {'CANCELLED'}

def get_preset_enum_items(self, context):
    """Get preset items for enum property."""
    presets = preset_manager.get_available_presets()
    items = []
    
    for preset in presets:
        icon = 'PRESET' if preset['is_built_in'] else 'FILE'
        items.append((
            preset['id'],
            preset['name'],
            preset['description'],
            icon,
            len(items)
        ))
    
    return items if items else [('NONE', 'No Presets', 'No presets available')]

class VISUAL_OT_preset_menu(Operator):
    """Quick preset selection menu"""
    bl_idname = "visual.preset_menu"
    bl_label = "Visualization Presets"
    bl_description = "Quick access to visualization presets"
    
    preset_choice: EnumProperty(
        name="Preset",
        description="Choose a preset to apply",
        items=get_preset_enum_items
    ) # type: ignore
    
    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}
    
    def execute(self, context):
        if self.preset_choice and self.preset_choice != 'NONE':
            bpy.ops.visual.load_preset(preset_id=self.preset_choice)
        return {'FINISHED'}

def register_preset_system():
    """Register preset system classes."""
    classes = [
        VisualizationPreset,
        VISUAL_OT_save_preset,
        VISUAL_OT_load_preset,
        VISUAL_OT_delete_preset,
        VISUAL_OT_export_preset,
        VISUAL_OT_import_preset,
        VISUAL_OT_preset_menu,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
    
    # Add preset list to scene
    if not hasattr(bpy.types.Scene, "visualization_presets"):
        bpy.types.Scene.visualization_presets = CollectionProperty(type=VisualizationPreset)
    
    if not hasattr(bpy.types.Scene, "visualization_presets_index"):
        bpy.types.Scene.visualization_presets_index = IntProperty()

def unregister_preset_system():
    """Unregister preset system classes."""
    # Remove scene properties
    if hasattr(bpy.types.Scene, "visualization_presets"):
        del bpy.types.Scene.visualization_presets
    
    if hasattr(bpy.types.Scene, "visualization_presets_index"):
        del bpy.types.Scene.visualization_presets_index
    
    classes = [
        VISUAL_OT_preset_menu,
        VISUAL_OT_import_preset,
        VISUAL_OT_export_preset,
        VISUAL_OT_delete_preset,
        VISUAL_OT_load_preset,
        VISUAL_OT_save_preset,
        VisualizationPreset,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            pass

# Convenience functions
def get_preset_manager():
    """Get the global preset manager."""
    return preset_manager

def save_current_as_preset(name: str, description: str = "", category: str = "CUSTOM"):
    """Convenience function to save current state as preset."""
    return preset_manager.save_preset(name, description, category)

def load_preset_by_name(name: str):
    """Convenience function to load preset by name."""
    return preset_manager.load_preset(name)
