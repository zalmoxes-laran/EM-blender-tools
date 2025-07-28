# landscape_system/__init__.py
"""
Sistema Landscape per la gestione di Multiple Extended Matrices (grafi multipli)
Sistema SEMPLICE - modifica solo il comportamento dei pannelli esistenti
"""

import bpy
from bpy.types import Operator, Menu
from bpy.props import BoolProperty, StringProperty

# ============================================================================
# MENU INFORMATIVO
# ============================================================================

class EM_MT_LandscapeInfo(Menu):
    """Menu informativo per Landscape Mode"""
    bl_label = "Multigraph Mode Info"
    bl_idname = "EM_MT_LandscapeInfo"
    bl_description = "Information about Multigraph Mode for Extended Matrices"
    
    def draw(self, context):
        layout = self.layout
        
        layout.label(text="Multigraph Mode", icon='WORLD')
        layout.separator()
        layout.label(text="Allows to manage and filter multiple Extended Matrices representing:")
        layout.label(text="• a bunch of artifacts composing a collection")
        layout.label(text="• excavation areas composing a site")
        layout.label(text="• several sites that compose a Larger Landscape")

        layout.separator()
        layout.label(text="Requirements to activate:")
        layout.label(text="• Load 2+ Extended Matrices (GraphML)")
        layout.label(text="• Both must be valid (green icon)")
        layout.separator()
        layout.label(text="When active:")
        layout.label(text="• All lists show data from all matrices")
        layout.label(text="• Names prefixed with [GRAPH_CODE]")
        layout.label(text="• Epoch Manager → hidden")
        layout.label(text="• CronoFilter → visible (macrochronologies)")

# ============================================================================
# OPERATORI LANDSCAPE
# ============================================================================

class EM_OT_ToggleLandscapeMode(Operator):
    """Toggle Landscape mode on/off"""
    bl_idname = "em.toggle_landscape_mode"
    bl_label = "Toggle Landscape Mode"
    bl_description = "Enable/disable Landscape mode for multiple Extended Matrices"
    
    enable: BoolProperty(
        name="Enable",
        description="True to enable, False to disable Landscape mode",
        default=True
    )
    
    def execute(self, context):
        scene = context.scene
        
        if self.enable:
            # Verifica che ci siano almeno 2 grafi caricati
            # ✅ CORRETTO: Usa la stessa logica dell'EM Setup
            loaded_graphs = []
            if hasattr(scene, 'em_tools'):
                for graph_file in scene.em_tools.graphml_files:
                    # Prima controlla la proprietà is_graph
                    if hasattr(graph_file, 'is_graph') and graph_file.is_graph:
                        loaded_graphs.append(graph_file)
                    else:
                        # Fallback: controlla se il grafo esiste nel sistema
                        from ..s3Dgraphy import get_graph
                        if get_graph(graph_file.name):
                            loaded_graphs.append(graph_file)
                
                if len(loaded_graphs) < 2:
                    self.report({'ERROR'}, "Need at least 2 Extended Matrices to enable Landscape mode")
                    return {'CANCELLED'}
            else:
                self.report({'ERROR'}, "No Extended Matrices found")
                return {'CANCELLED'}
            
            # Attiva Landscape mode
            scene.landscape_mode_active = True
            self.report({'INFO'}, f"Landscape mode enabled ({len(loaded_graphs)} matrices)")
        else:
            # Disattiva Landscape mode
            scene.landscape_mode_active = False
            self.report({'INFO'}, "Landscape mode disabled")
        
        return {'FINISHED'}

# ============================================================================
# PROPRIETÀ LANDSCAPE
# ============================================================================

def register_landscape_properties():
    """Registra le proprietà essenziali per la modalità Landscape"""
    
    # Proprietà principale per abilitare la modalità Landscape
    bpy.types.Scene.landscape_mode_active = BoolProperty(
        name="Landscape Mode Active",
        description="Enable Landscape mode for multiple Extended Matrices management",
        default=False,
        update=on_landscape_mode_change
    )
    
    # Proprietà per memorizzare l'ultimo grafo attivo (per quando si disattiva Landscape)
    bpy.types.Scene.last_active_graph_code = StringProperty(
        name="Last Active Graph Code",
        description="Code of the last active graph before enabling Landscape mode",
        default=""
    )
    
    print("✅ Landscape properties registered")

def on_landscape_mode_change(self, context):
    """Callback quando cambia la modalità Landscape"""
    scene = context.scene
    
    if scene.landscape_mode_active:
        print("🌍 Switched to Landscape mode")
        # Salva il grafo attivo corrente
        if hasattr(scene, 'em_tools') and scene.em_tools.active_file_index >= 0:
            active_file = scene.em_tools.graphml_files[scene.em_tools.active_file_index]
            scene.last_active_graph_code = getattr(active_file, 'graph_code', '')
        
        # Ricarica tutte le liste in modalità Landscape
        from .populate_functions import populate_lists_landscape_mode
        populate_lists_landscape_mode(context)
    else:
        print("📊 Switched to single graph mode")
        # Ricarica solo il grafo precedentemente attivo
        from .populate_functions import populate_lists_single_mode
        populate_lists_single_mode(context)

# ============================================================================
# REGISTRAZIONE SEMPLIFICATA
# ============================================================================

def register():
    """Registra il sistema Landscape"""
    print("🌍 Registering Landscape system...")
    
    # 1. Registra proprietà
    register_landscape_properties()
    
    # 2. Registra operatori e menu
    classes = [
        EM_MT_LandscapeInfo,
        EM_OT_ToggleLandscapeMode,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError as e:
            print(f"Warning: {cls.__name__} already registered: {e}")
    
    print("✅ Landscape system registered successfully!")

def unregister():
    """Disregistra il sistema Landscape"""
    print("🌍 Unregistering Landscape system...")
    
    # 1. Disregistra operatori e menu
    classes = [
        EM_OT_ToggleLandscapeMode,
        EM_MT_LandscapeInfo,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"Error unregistering {cls.__name__}: {e}")
    
    # 2. Rimuovi proprietà
    landscape_props = [
        'landscape_mode_active',
        'last_active_graph_code'
    ]
    
    for prop_name in landscape_props:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)
    
    print("✅ Landscape system unregistered!")

if __name__ == "__main__":
    register()