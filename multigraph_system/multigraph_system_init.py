# multigraph_system_init.py
"""
Sistema di inizializzazione per il supporto multigraph
"""

import bpy
from bpy.props import BoolProperty, StringProperty, EnumProperty

def register_multigraph_properties():
    """
    Registra tutte le proprietà necessarie per il sistema multigraph
    """
    
    # Proprietà principale per abilitare la modalità multigraph
    bpy.types.Scene.show_all_graphs = BoolProperty(
        name="Show All Graphs",
        description="Display all loaded graphs in lists simultaneously",
        default=False,
        update=on_multigraph_mode_change
    )
    
    # Proprietà per l'indicatore viewport
    bpy.types.Scene.show_viewport_graph_info = BoolProperty(
        name="Show Graph Info in Viewport",
        description="Display active graph information in the 3D viewport",
        default=True,
        update=on_viewport_indicator_change
    )
    
    # Proprietà per memorizzare il grafo attivo corrente
    bpy.types.Scene.active_graph_code = StringProperty(
        name="Active Graph Code",
        description="Code of the currently active graph",
        default="UNKNOWN"
    )
    
    # Proprietà per la modalità di visualizzazione nomi
    bpy.types.Scene.name_display_mode = EnumProperty(
        name="Name Display Mode",
        description="How to display node names in lists",
        items=[
            ('CLEAN', "Clean Names", "Show names without graph prefixes"),
            ('FULL', "Full Names", "Show complete names with graph prefixes"),
            ('AUTO', "Auto", "Automatically choose based on multigraph mode")
        ],
        default='AUTO'
    )
    
    # Proprietà per filtrare per grafo specifico
    bpy.types.Scene.filter_by_graph = StringProperty(
        name="Filter by Graph",
        description="Show only nodes from specified graph (empty = show all)",
        default=""
    )
    
    print("Multigraph properties registered")

def on_multigraph_mode_change(self, context):
    """
    Callback chiamato quando cambia la modalità multigraph
    """
    scene = context.scene
    
    if scene.show_all_graphs:
        print("Switched to multigraph mode")
        # Ricarica tutte le liste in modalità multigraph
        reload_all_lists_multigraph(context)
    else:
        print("Switched to single graph mode")
        # Ricarica solo il grafo attivo
        reload_single_graph_lists(context)
    
    # Forza il refresh di tutte le aree UI
    refresh_all_ui_areas(context)

def on_viewport_indicator_change(self, context):
    """
    Callback per l'indicatore viewport
    """
    from .viewport_graph_indicator import register_viewport_indicator, unregister_viewport_indicator
    
    if context.scene.show_viewport_graph_info:
        register_viewport_indicator()
    else:
        unregister_viewport_indicator()

def reload_all_lists_multigraph(context):
    """
    Ricarica tutte le liste includendo tutti i grafi
    """
    scene = context.scene
    
    # Cancella le liste esistenti
    scene.em_list.clear()
    scene.em_properties_list.clear()
    scene.em_sources_list.clear()
    scene.em_extractors_list.clear()
    scene.em_combiners_list.clear()
    
    # Carica da tutti i grafi
    from ..s3Dgraphy import get_all_graphs
    
    all_graphs = get_all_graphs()
    
    for graph_id, graph in all_graphs.items():
        if graph:
            # Usa la funzione potenziata per popolare
            from .panel_integration import populate_blender_lists_from_graph_enhanced
            populate_blender_lists_from_graph_enhanced(context, graph)
    
    print(f"Loaded lists from {len(all_graphs)} graphs in multigraph mode")

def reload_single_graph_lists(context):
    """
    Ricarica le liste per il solo grafo attivo
    """
    scene = context.scene
    
    # Cancella le liste esistenti
    scene.em_list.clear()
    scene.em_properties_list.clear()
    scene.em_sources_list.clear()
    scene.em_extractors_list.clear()
    scene.em_combiners_list.clear()
    
    # Carica solo dal grafo attivo
    from ..s3Dgraphy import get_active_graph
    
    active_graph = get_active_graph()
    
    if active_graph:
        from .panel_integration import populate_blender_lists_from_graph_enhanced
        populate_blender_lists_from_graph_enhanced(context, active_graph)
        
        # Aggiorna il codice del grafo attivo
        graph_code = active_graph.attributes.get('graph_code', 'UNKNOWN')
        scene.active_graph_code = graph_code
        
        print(f"Loaded lists from active graph: {graph_code}")
    else:
        print("No active graph found")

def refresh_all_ui_areas(context):
    """
    Forza il refresh di tutte le aree UI
    """
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()

# Operatori di gestione del sistema
class EM_OT_ReloadMultigraphLists(bpy.types.Operator):
    """Reload all lists in current mode"""
    bl_idname = "em.reload_multigraph_lists"
    bl_label = "Reload Lists"
    bl_description = "Reload all lists in current display mode"

    def execute(self, context):
        scene = context.scene
        
        if scene.show_all_graphs:
            reload_all_lists_multigraph(context)
            self.report({'INFO'}, "Reloaded all graphs")
        else:
            reload_single_graph_lists(context)
            self.report({'INFO'}, "Reloaded active graph")
        
        return {'FINISHED'}

class EM_OT_SetActiveGraph(bpy.types.Operator):
    """Set active graph"""
    bl_idname = "em.set_active_graph"
    bl_label = "Set Active Graph"
    bl_description = "Set the specified graph as active"
    
    graph_code: StringProperty(
        name="Graph Code",
        description="Code of the graph to make active"
    )

    def execute(self, context):
        scene = context.scene
        
        # Trova e attiva il grafo specificato
        from ..s3Dgraphy import get_all_graphs, set_active_graph
        
        all_graphs = get_all_graphs()
        
        for graph_id, graph in all_graphs.items():
            if graph and graph.attributes.get('graph_code') == self.graph_code:
                set_active_graph(graph_id)
                scene.active_graph_code = self.graph_code
                
                # Se non siamo in modalità multigraph, ricarica le liste
                if not scene.show_all_graphs:
                    reload_single_graph_lists(context)
                
                self.report({'INFO'}, f"Set {self.graph_code} as active graph")
                return {'FINISHED'}
        
        self.report({'ERROR'}, f"Graph {self.graph_code} not found")
        return {'CANCELLED'}

class EM_OT_FilterByGraph(bpy.types.Operator):
    """Filter lists by specific graph"""
    bl_idname = "em.filter_by_graph"
    bl_label = "Filter by Graph"
    bl_description = "Show only items from specified graph"
    
    graph_code: StringProperty(
        name="Graph Code",
        description="Code of the graph to filter by (empty to show all)"
    )

    def execute(self, context):
        scene = context.scene
        scene.filter_by_graph = self.graph_code
        
        # Ricarica le liste con il filtro applicato
        if scene.show_all_graphs:
            reload_all_lists_multigraph(context)
        
        filter_text = f"by {self.graph_code}" if self.graph_code else "all graphs"
        self.report({'INFO'}, f"Filtering {filter_text}")
        
        return {'FINISHED'}

# Menu per selezione rapida del grafo
class EM_MT_GraphSelection(bpy.types.Menu):
    """Menu for quick graph selection"""
    bl_label = "Graph Selection"
    bl_idname = "EM_MT_graph_selection"

    def draw(self, context):
        layout = self.layout
        
        from ..s3Dgraphy import get_all_graphs
        
        all_graphs = get_all_graphs()
        scene = context.scene
        
        if not all_graphs:
            layout.label(text="No graphs loaded")
            return
        
        # Opzione per modalità multigraph
        layout.prop(scene, "show_all_graphs", text="Show All Graphs")
        layout.separator()
        
        # Lista grafi disponibili
        for graph_id, graph in all_graphs.items():
            if graph:
                graph_code = graph.attributes.get('graph_code', 'UNKNOWN')
                
                # Icona diversa per il grafo attivo
                icon = 'RADIOBUT_ON' if graph_code == scene.active_graph_code else 'RADIOBUT_OFF'
                
                op = layout.operator("em.set_active_graph", text=graph_code, icon=icon)
                op.graph_code = graph_code

# Pannello di controllo multigraph
class EM_PT_MultigraphControl(bpy.types.Panel):
    """Control panel for multigraph system"""
    bl_label = "Multigraph Control"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM"
    bl_idname = "EM_PT_MultigraphControl"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Modalità corrente
        box = layout.box()
        row = box.row(align=True)
        
        if scene.show_all_graphs:
            row.label(text="Mode: MULTIGRAPH", icon='OUTLINER_DATA_GREASEPENCIL')
        else:
            row.label(text=f"Mode: SINGLE ({scene.active_graph_code})", icon='OUTLINER_OB_GROUP_INSTANCE')
        
        # Toggle modalità
        row = layout.row(align=True)
        row.prop(scene, "show_all_graphs", text="Multigraph Mode")
        row.operator("em.reload_multigraph_lists", text="", icon='FILE_REFRESH')
        
        # Selezione grafo attivo
        if not scene.show_all_graphs:
            row = layout.row()
            row.menu("EM_MT_graph_selection", text=f"Active: {scene.active_graph_code}")
        
        # Opzioni avanzate
        col = layout.column(align=True)
        col.prop(scene, "show_viewport_graph_info", text="Viewport Indicator")
        col.prop(scene, "name_display_mode", text="Name Display")
        
        # Filtro per grafo (solo in modalità multigraph)
        if scene.show_all_graphs:
            col.prop(scene, "filter_by_graph", text="Filter")

def register():
    """Registra tutto il sistema multigraph"""
    
    # Registra le proprietà
    register_multigraph_properties()
    
    # Registra le classi
    classes = [
        EM_OT_ReloadMultigraphLists,
        EM_OT_SetActiveGraph,
        EM_OT_FilterByGraph,
        EM_MT_GraphSelection,
        EM_PT_MultigraphControl,
    ]
    
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Registra il sistema viewport
    from .viewport_graph_indicator import register as register_viewport
    register_viewport()
    
    # Registra le UIList potenziate
    from .enhanced_uilist import register as register_enhanced_uilist
    register_enhanced_uilist()
    
    # Registra l'integrazione pannelli
    from .panel_integration import register as register_panel_integration
    register_panel_integration()
    
    print("Multigraph system fully registered")

def unregister():
    """Disregistra tutto il sistema multigraph"""
    
    # Disregistra nell'ordine inverso
    from .panel_integration import unregister as unregister_panel_integration
    unregister_panel_integration()
    
    from .enhanced_uilist import unregister as unregister_enhanced_uilist
    unregister_enhanced_uilist()
    
    from .viewport_graph_indicator import unregister as unregister_viewport
    unregister_viewport()
    
    # Disregistra le classi
    classes = [
        EM_PT_MultigraphControl,
        EM_MT_GraphSelection,
        EM_OT_FilterByGraph,
        EM_OT_SetActiveGraph,
        EM_OT_ReloadMultigraphLists,
    ]
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    # Rimuovi le proprietà
    if hasattr(bpy.types.Scene, 'show_all_graphs'):
        del bpy.types.Scene.show_all_graphs
    if hasattr(bpy.types.Scene, 'show_viewport_graph_info'):
        del bpy.types.Scene.show_viewport_graph_info
    if hasattr(bpy.types.Scene, 'active_graph_code'):
        del bpy.types.Scene.active_graph_code
    if hasattr(bpy.types.Scene, 'name_display_mode'):
        del bpy.types.Scene.name_display_mode
    if hasattr(bpy.types.Scene, 'filter_by_graph'):
        del bpy.types.Scene.filter_by_graph
    
    print("Multigraph system fully unregistered")