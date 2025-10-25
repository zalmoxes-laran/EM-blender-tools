"""
Mapping Preferences Module
Gestisce le preferenze per i percorsi personalizzati dei file di mapping
"""

import bpy
from bpy.types import AddonPreferences, Operator
from bpy.props import StringProperty, BoolProperty
import os

import logging
log = logging.getLogger(__name__)

class EMToolsMappingPreferences(AddonPreferences):
    """Preferenze per i percorsi di mapping personalizzati"""
    bl_idname = __package__
    
    # Percorsi personalizzati per i mapping
    custom_emdb_path: StringProperty(
        name="Custom EMdb Mappings Folder",
        description="Custom folder containing EMdb mapping JSON files",
        subtype='DIR_PATH',
        default="",
        update=lambda self, context: update_custom_mappings(self, context, 'emdb')
    )
    
    custom_pyarchinit_path: StringProperty(
        name="Custom pyArchInit Mappings Folder",
        description="Custom folder containing pyArchInit mapping JSON files",
        subtype='DIR_PATH',
        default="",
        update=lambda self, context: update_custom_mappings(self, context, 'pyarchinit')
    )
    
    # Flag per sapere se i percorsi sono stati inizializzati
    mappings_initialized: BoolProperty(
        name="Mappings Initialized",
        default=False
    )
    
    def draw(self, context):
        layout = self.layout
        
        # Sezione Custom Mapping Paths
        box = layout.box()
        box.label(text="Custom Mapping Directories", icon='FILEBROWSER')
        
        # EMdb mappings
        row = box.row()
        row.label(text="EMdb Mappings:")
        row = box.row()
        row.prop(self, "custom_emdb_path", text="")
        if self.custom_emdb_path and os.path.exists(self.custom_emdb_path):
            row = box.row()
            row.label(text="✓ Folder exists", icon='CHECKMARK')
        elif self.custom_emdb_path:
            row = box.row()
            row.label(text="⚠ Folder not found", icon='ERROR')
        
        box.separator()
        
        # pyArchInit mappings
        row = box.row()
        row.label(text="pyArchInit Mappings:")
        row = box.row()
        row.prop(self, "custom_pyarchinit_path", text="")
        if self.custom_pyarchinit_path and os.path.exists(self.custom_pyarchinit_path):
            row = box.row()
            row.label(text="✓ Folder exists", icon='CHECKMARK')
        elif self.custom_pyarchinit_path:
            row = box.row()
            row.label(text="⚠ Folder not found", icon='ERROR')
        
        box.separator()
        
        # Pulsante per ricaricare manualmente
        row = box.row()
        row.operator("emtools.reload_custom_mappings", 
                     text="Reload All Mappings", 
                     icon='FILE_REFRESH')
        
        # Info
        info_box = layout.box()
        info_box.label(text="ℹ Info:", icon='INFO')
        info_box.label(text="Place your custom mapping JSON files in these folders.")
        info_box.label(text="They will be loaded automatically and appear in dropdowns.")
        info_box.label(text="Custom mappings have priority over built-in ones.")


def update_custom_mappings(prefs, context, mapping_type):
    """Aggiorna i mapping quando viene modificato un percorso"""
    path = getattr(prefs, f"custom_{mapping_type}_path", "")
    
    if not path or not os.path.exists(path):
        log.warning(f"Custom {mapping_type} path not valid: {path}")
        return
    
    try:
        from s3dgraphy import add_custom_mapping_directory
        add_custom_mapping_directory(mapping_type, path, priority='high')
        log.info(f"✓ Registered custom {mapping_type} mappings from: {path}")
    except Exception as e:
        log.error(f"Error registering custom {mapping_type} mappings: {e}")


class EMTOOLS_OT_reload_custom_mappings(Operator):
    """Ricarica tutti i mapping personalizzati"""
    bl_idname = "emtools.reload_custom_mappings"
    bl_label = "Reload Custom Mappings"
    bl_description = "Reload all custom mapping directories"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        
        try:
            from s3dgraphy import add_custom_mapping_directory
            
            reloaded = []
            
            # Ricarica EMdb mappings
            if prefs.custom_emdb_path and os.path.exists(prefs.custom_emdb_path):
                add_custom_mapping_directory('emdb', prefs.custom_emdb_path, priority='high')
                reloaded.append('EMdb')
            
            # Ricarica pyArchInit mappings
            if prefs.custom_pyarchinit_path and os.path.exists(prefs.custom_pyarchinit_path):
                add_custom_mapping_directory('pyarchinit', prefs.custom_pyarchinit_path, priority='high')
                reloaded.append('pyArchInit')
            
            if reloaded:
                self.report({'INFO'}, f"Reloaded custom mappings: {', '.join(reloaded)}")
            else:
                self.report({'WARNING'}, "No valid custom mapping paths configured")
            
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error reloading mappings: {str(e)}")
            return {'CANCELLED'}


class EMTOOLS_OT_open_mapping_preferences(Operator):
    """Apri il pannello delle preferenze mapping"""
    bl_idname = "emtools.open_mapping_preferences"
    bl_label = "Open Mapping Preferences"
    bl_description = "Open the addon preferences to configure custom mapping paths"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        bpy.ops.preferences.addon_show(module=__package__)
        return {'FINISHED'}


# Lista delle classi da registrare
classes = [
    EMToolsMappingPreferences,
    EMTOOLS_OT_reload_custom_mappings,
    EMTOOLS_OT_open_mapping_preferences,
]


def register():
    """Registra le classi delle preferenze"""
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            log.debug(f"Registered mapping preference class: {cls.__name__}")
        except ValueError as e:
            log.warning(f'{cls} is already registered, unregister and retry...')
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)


def unregister():
    """Deregistra le classi delle preferenze"""
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


def initialize_custom_mappings():
    """Inizializza i percorsi personalizzati all'avvio dell'addon"""
    try:
        prefs = bpy.context.preferences.addons.get(__package__, None)
        if not prefs:
            log.warning("Cannot access addon preferences")
            return
        
        prefs = prefs.preferences
        
        # Se già inizializzato, salta
        if prefs.mappings_initialized:
            return
        
        from s3dgraphy import add_custom_mapping_directory
        
        # Registra i percorsi personalizzati se esistono
        if prefs.custom_emdb_path and os.path.exists(prefs.custom_emdb_path):
            add_custom_mapping_directory('emdb', prefs.custom_emdb_path, priority='high')
            log.info(f"✓ Loaded custom EMdb mappings from: {prefs.custom_emdb_path}")
        
        if prefs.custom_pyarchinit_path and os.path.exists(prefs.custom_pyarchinit_path):
            add_custom_mapping_directory('pyarchinit', prefs.custom_pyarchinit_path, priority='high')
            log.info(f"✓ Loaded custom pyArchInit mappings from: {prefs.custom_pyarchinit_path}")
        
        prefs.mappings_initialized = True
        
    except Exception as e:
        log.error(f"Error initializing custom mappings: {e}")