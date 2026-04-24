"""
EMTools Keymap Manager - Sistema centralizzato per le scorciatoie da tastiera
Gestisce tutte le combinazioni di tasti personalizzate per EMtools
"""

import bpy
from bpy.types import KeyMapItem
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

# Lista globale per tenere traccia delle keymaps registrate
addon_keymaps = []

class EMKeymapManager:
    """Manager per le scorciatoie da tastiera di EMtools"""
    
    @staticmethod
    def register_keymaps():
        """Registra tutte le scorciatoie da tastiera di EMtools"""
        wm = bpy.context.window_manager
        
        # Keymap per la 3D Viewport
        km = wm.keyconfigs.addon.keymaps.new(name='3D View', space_type='VIEW_3D')
        
        # F5 - Ricarica GraphML attivo (universale per "refresh")
        kmi = km.keymap_items.new(
            'em_tools.reload_active_graphml', 
            type='F5', 
            value='PRESS',
            shift=True,
        )
        addon_keymaps.append((km, kmi))
        
        # Option+F - Seleziona elemento lista basandosi sul proxy attivo
        kmi = km.keymap_items.new(
            'em_tools.select_list_item', 
            type='F', 
            value='PRESS',
            alt=True  # ALT è Option su Mac
        )
        addon_keymaps.append((km, kmi))
        
        # Aggiungi qui altre scorciatoie future
        # Esempio: Ctrl+Shift+E per export
        # kmi = km.keymap_items.new(
        #     'em_tools.quick_export', 
        #     type='E', 
        #     value='PRESS',
        #     shift=True,
        #     ctrl=True
        # )
        # addon_keymaps.append((km, kmi))
        
        logger.info(f"Registered {len(addon_keymaps)} EMtools keymaps")
    
    @staticmethod
    def unregister_keymaps():
        """Rimuove tutte le scorciatoie da tastiera di EMtools"""
        try:
            wm = bpy.context.window_manager
            for km, kmi in addon_keymaps:
                km.keymap_items.remove(kmi)
            addon_keymaps.clear()
            logger.info("Unregistered all EMtools keymaps")
        except Exception as e:
            logger.error(f"Error unregistering keymaps: {e}")

class EMToolsSelectListItem(bpy.types.Operator):
    """Seleziona elemento nella lista EM basandosi sul proxy attivo nella scena"""
    bl_idname = "em_tools.select_list_item"
    bl_label = "Select List Item"
    bl_description = "Select element in EM list corresponding to active proxy (Option+F)"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            # Chiama l'operatore select.listitem esistente con list_type="em_list"
            # Uso getattr perché 'select' potrebbe causare conflitti
            select_op = getattr(bpy.ops, 'select')
            select_op.listitem(list_type="em_list")
            
            self.report({'INFO'}, "List item selected based on active proxy")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to select list item: {str(e)}")
            logger.error(f"Error in select_list_item: {e}")
            return {'CANCELLED'}
    
    @classmethod
    def poll(cls, context):
        """Determina se l'operatore può essere eseguito - ✅ CLEAN VERSION"""
        if context.scene is None or not hasattr(context.scene, 'em_tools'):
            return False
        strat = context.scene.em_tools.stratigraphy
        return len(strat.units) > 0

class EMToolsReloadActiveGraphML(bpy.types.Operator):
    """Ricarica il file GraphML attualmente attivo"""
    bl_idname = "em_tools.reload_active_graphml"
    bl_label = "Reload Active GraphML"
    bl_description = "Reload the currently active GraphML file (F5)"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            em_tools = context.scene.em_tools
            
            # Controlla se c'è un file GraphML attivo
            if not em_tools.graphml_files:
                self.report({'WARNING'}, "No GraphML files loaded")
                return {'CANCELLED'}
            
            if em_tools.active_file_index < 0 or em_tools.active_file_index >= len(em_tools.graphml_files):
                self.report({'WARNING'}, "No active GraphML file selected")
                return {'CANCELLED'}
            
            active_file = em_tools.graphml_files[em_tools.active_file_index]
            
            # Controlla se il file ha un path valido
            if not active_file.graphml_path or active_file.graphml_path == "":
                self.report({'WARNING'}, "Active GraphML file has no valid path")
                return {'CANCELLED'}
            
            # Chiama l'operatore di import esistente
            # Uso getattr perché 'import' è una parola riservata Python
            import_op = getattr(bpy.ops, 'import')
            import_op.em_graphml(graphml_index=em_tools.active_file_index)
            
            self.report({'INFO'}, f"Reloaded: {active_file.name}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to reload GraphML: {str(e)}")
            logger.error(f"Error in reload_active_graphml: {e}")
            return {'CANCELLED'}
    
    @classmethod
    def poll(cls, context):
        """Determina se l'operatore può essere eseguito"""
        return (
            context.scene is not None and
            hasattr(context.scene, 'em_tools') and
            len(context.scene.em_tools.graphml_files) > 0
        )

# Lista delle classi da registrare
classes = [
    EMToolsSelectListItem,
    EMToolsReloadActiveGraphML,
]

def register():
    """Registra il keymap manager e le sue classi"""
    # Registra le classi
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
            logger.debug(f"Registered keymap class: {cls.__name__}")
        except Exception as e:
            logger.warning(f"Could not register {cls.__name__}: {e}")
    
    # Registra le keymaps
    EMKeymapManager.register_keymaps()

def unregister():
    """Rimuove il keymap manager e le sue classi"""
    # Rimuove le keymaps
    EMKeymapManager.unregister_keymaps()
    
    # Rimuove le classi
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
            logger.debug(f"Unregistered keymap class: {cls.__name__}")
        except Exception as e:
            logger.warning(f"Could not unregister {cls.__name__}: {e}")

if __name__ == "__main__":
    register()