# enhanced_uilist.py
"""
UIList potenziate per la gestione multigraph con conversione nomi al volo
"""

import bpy
from bpy.types import UIList

class EM_STRAT_UL_List_Enhanced(UIList):
    """
    UIList potenziata per unità stratigrafiche con supporto multigraph
    """
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        from .name_conversion_utils import (
            format_name_for_display, 
            format_graph_code_for_display, 
            should_show_multigraph,
            get_active_graph_code
        )
        
        scene = context.scene
        is_multigraph = should_show_multigraph(context)
        is_in_scene = item.icon == 'RESTRICT_INSTANCED_OFF'
        
        # Layout principale
        row = layout.row(align=True)
        
        # Prima colonna: Chain icon (3%)
        first_split = row.split(factor=0.03)
        col1 = first_split.column(align=True)
        sub_col = col1.column(align=True)
        sub_col.enabled = is_in_scene
        
        op = sub_col.operator("select.fromlistitem", text="", icon=item.icon, emboss=False)
        if op:
            op.list_type = "em_list"
            op.specific_item = item.name
        
        remaining = first_split.column(align=True)
        
        if is_multigraph:
            # Modalità multigraph: Nome (20%) + Codice Grafo (8%) + Descrizione (67%) + Visibilità (2%)
            name_split = remaining.split(factor=0.20)
            
            # Colonna Nome
            col_name = name_split.column(align=True)
            display_name = format_name_for_display(item.name, "", is_multigraph)
            col_name.label(text=display_name)
            
            remaining2 = name_split.column(align=True)
            graph_split = remaining2.split(factor=0.10)  # 8% del rimanente 80%
            
            # Colonna Codice Grafo
            col_graph = graph_split.column(align=True)
            graph_code = format_graph_code_for_display(item.name, get_active_graph_code(context))
            
            # Usa un colore diverso per il codice grafo
            if graph_code and graph_code != "UNKNOWN":
                # Crea un box colorato per il codice grafo
                graph_box = col_graph.box()
                graph_row = graph_box.row(align=True)
                graph_row.scale_y = 0.8
                graph_row.label(text=graph_code)
            else:
                col_graph.label(text="--")
            
            # Colonna Descrizione + Visibilità
            desc_vis_split = graph_split.column(align=True).split(factor=0.95)
            
        else:
            # Modalità singolo grafo: Nome (25%) + Descrizione (73%) + Visibilità (2%)
            name_split = remaining.split(factor=0.25)
            
            # Colonna Nome
            col_name = name_split.column(align=True)
            display_name = format_name_for_display(item.name, "", is_multigraph)
            col_name.label(text=display_name)
            
            # Colonna Descrizione + Visibilità
            desc_vis_split = name_split.column(align=True).split(factor=0.97)
        
        # Descrizione
        col_desc = desc_vis_split.column(align=True)
        col_desc.label(text=item.description)
        
        # Visibilità toggle
        col_vis = desc_vis_split.column(align=True)
        col_vis.enabled = is_in_scene
        if hasattr(item, "is_visible"):
            vis_icon = 'HIDE_OFF' if item.is_visible else 'HIDE_ON'
            op = col_vis.operator("em.strat_toggle_visibility", text="", icon=vis_icon, emboss=False)
            if op:
                op.index = index

class EM_PROPERTIES_UL_List_Enhanced(UIList):
    """
    UIList potenziata per proprietà con supporto multigraph
    """
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        from .name_conversion_utils import (
            format_name_for_display, 
            format_graph_code_for_display, 
            should_show_multigraph,
            get_active_graph_code
        )
        
        scene = context.scene
        is_multigraph = should_show_multigraph(context)
        
        row = layout.row(align=True)
        
        # Icona proprietà (3%)
        icon_split = row.split(factor=0.03)
        col_icon = icon_split.column(align=True)
        col_icon.label(text="", icon=item.icon_db if hasattr(item, 'icon_db') else 'PROPERTIES')
        
        remaining = icon_split.column(align=True)
        
        if is_multigraph:
            # Nome (25%) + Codice Grafo (10%) + Descrizione (65%)
            name_split = remaining.split(factor=0.25)
            
            col_name = name_split.column(align=True)
            display_name = format_name_for_display(item.name, "", is_multigraph)
            col_name.label(text=display_name, icon=item.icon if hasattr(item, 'icon') else 'NONE')
            
            remaining2 = name_split.column(align=True)
            graph_split = remaining2.split(factor=0.133)  # 10% del rimanente 75%
            
            # Codice Grafo
            col_graph = graph_split.column(align=True)
            graph_code = format_graph_code_for_display(item.name, get_active_graph_code(context))
            
            if graph_code and graph_code != "UNKNOWN":
                graph_box = col_graph.box()
                graph_row = graph_box.row(align=True)
                graph_row.scale_y = 0.7
                graph_row.alert = True  # Evidenzia il box
                graph_row.label(text=graph_code)
            else:
                col_graph.label(text="--")
            
            # Descrizione
            col_desc = graph_split.column(align=True)
            col_desc.label(text=item.description if hasattr(item, 'description') else "")
            
        else:
            # Modalità singolo grafo: Nome (30%) + Descrizione (70%)
            name_split = remaining.split(factor=0.30)
            
            col_name = name_split.column(align=True)
            display_name = format_name_for_display(item.name, "", is_multigraph)
            col_name.label(text=display_name, icon=item.icon if hasattr(item, 'icon') else 'NONE')
            
            col_desc = name_split.column(align=True)
            col_desc.label(text=item.description if hasattr(item, 'description') else "")

class EM_DOCUMENTS_UL_List_Enhanced(UIList):
    """
    UIList potenziata per documenti con supporto multigraph
    """
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        from .name_conversion_utils import (
            format_name_for_display, 
            format_graph_code_for_display, 
            should_show_multigraph,
            get_active_graph_code
        )
        
        scene = context.scene
        is_multigraph = should_show_multigraph(context)
        
        row = layout.row(align=True)
        
        if is_multigraph:
            # Icona (3%) + Nome (22%) + Codice Grafo (8%) + Descrizione (67%)
            icon_split = row.split(factor=0.03)
            col_icon = icon_split.column(align=True)
            col_icon.label(text="", icon='FILE_TEXT')
            
            remaining = icon_split.column(align=True)
            name_split = remaining.split(factor=0.227)  # 22% del rimanente 97%
            
            col_name = name_split.column(align=True)
            display_name = format_name_for_display(item.name, "", is_multigraph)
            col_name.label(text=display_name)
            
            remaining2 = name_split.column(align=True)
            graph_split = remaining2.split(factor=0.103)  # 8% del rimanente 75%
            
            # Codice Grafo
            col_graph = graph_split.column(align=True)
            graph_code = format_graph_code_for_display(item.name, get_active_graph_code(context))
            
            if graph_code and graph_code != "UNKNOWN":
                col_graph.label(text=f"[{graph_code}]")
            else:
                col_graph.label(text="[--]")
            
            # Descrizione
            col_desc = graph_split.column(align=True)
            col_desc.label(text=item.description if hasattr(item, 'description') else "")
            
        else:
            # Modalità singolo grafo: Icona (3%) + Nome (25%) + Descrizione (72%)
            icon_split = row.split(factor=0.03)
            col_icon = icon_split.column(align=True)
            col_icon.label(text="", icon='FILE_TEXT')
            
            remaining = icon_split.column(align=True)
            name_split = remaining.split(factor=0.257)  # 25% del rimanente 97%
            
            col_name = name_split.column(align=True)
            display_name = format_name_for_display(item.name, "", is_multigraph)
            col_name.label(text=display_name)
            
            col_desc = name_split.column(align=True)
            col_desc.label(text=item.description if hasattr(item, 'description') else "")

# Operatore per toggle modalità multigraph
class EM_OT_ToggleMultigraph(bpy.types.Operator):
    """Toggle multigraph display mode"""
    bl_idname = "em.toggle_multigraph"
    bl_label = "Toggle Multigraph Mode"
    bl_description = "Switch between single graph and multigraph display modes"

    def execute(self, context):
        scene = context.scene
        
        # Toggle della proprietà
        current_state = getattr(scene, 'show_all_graphs', False)
        scene.show_all_graphs = not current_state
        
        # Forza il refresh delle liste
        self.refresh_all_lists(context)
        
        mode_text = "multigraph" if scene.show_all_graphs else "single graph"
        self.report({'INFO'}, f"Switched to {mode_text} mode")
        
        return {'FINISHED'}
    
    def refresh_all_lists(self, context):
        """Forza il refresh di tutte le liste UI"""
        # Forza il redraw di tutte le aree
        for area in context.screen.areas:
            area.tag_redraw()

# Header per i pannelli che mostra la modalità attiva
def draw_multigraph_header(layout, context):
    """
    Disegna un header che mostra la modalità attiva
    """
    from .name_conversion_utils import should_show_multigraph, get_active_graph_code
    
    is_multigraph = should_show_multigraph(context)
    
    if is_multigraph:
        box = layout.box()
        row = box.row(align=True)
        row.alert = True
        row.label(text="MODALITÀ MULTIGRAPH", icon='OUTLINER_DATA_GREASEPENCIL')
        
        # Pulsante per tornare a modalità singola
        op = row.operator("em.toggle_multigraph", text="", icon='X')
        
    else:
        active_code = get_active_graph_code(context)
        if active_code and active_code != "UNKNOWN":
            box = layout.box()
            row = box.row(align=True)
            row.label(text=f"Grafo: {active_code}", icon='OUTLINER_OB_GROUP_INSTANCE')
            
            # Pulsante per attivare modalità multigraph
            op = row.operator("em.toggle_multigraph", text="Multi", icon='OUTLINER_DATA_GREASEPENCIL')

def register():
    """Registra le classi UI potenziate"""
    classes = [
        EM_STRAT_UL_List_Enhanced,
        EM_PROPERTIES_UL_List_Enhanced,
        EM_DOCUMENTS_UL_List_Enhanced,
        EM_OT_ToggleMultigraph,
    ]
    
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    """Disregistra le classi UI potenziate"""
    classes = [
        EM_OT_ToggleMultigraph,
        EM_DOCUMENTS_UL_List_Enhanced,
        EM_PROPERTIES_UL_List_Enhanced,
        EM_STRAT_UL_List_Enhanced,
    ]
    
    for cls in classes:
        bpy.utils.unregister_class(cls)