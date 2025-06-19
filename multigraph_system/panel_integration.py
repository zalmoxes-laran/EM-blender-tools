# panel_integration.py
"""
Modifiche ai pannelli esistenti per integrazione sistema multigraph
"""

import bpy
from bpy.types import Panel

# Esempio di modifica al tuo stratigraphy_manager/ui.py
class VIEW3D_PT_ToolsPanel_Enhanced(Panel):
    """
    Pannello potenziato per Stratigraphy Manager con supporto multigraph
    """
    bl_label = "Stratigraphy Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ToolsPanel_Enhanced"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.object
        
        # Importa le funzioni di supporto
        from .enhanced_uilist import draw_multigraph_header
        from .name_conversion_utils import should_show_multigraph
        
        # Header multigraph
        draw_multigraph_header(layout, context)
        
        # Controlli modalità (se necessario)
        self.draw_mode_controls(layout, context)
        
        # Lista principale con UIList potenziata
        row = layout.row()
        
        # Usa la UIList potenziata invece di quella standard
        row.template_list(
            "EM_STRAT_UL_List_Enhanced",  # Nuova classe UIList
            "", 
            scene, 
            "em_list", 
            scene, 
            "em_list_index"
        )
        
        # Dettagli dell'elemento selezionato
        if scene.em_list and len(scene.em_list) > scene.em_list_index >= 0:
            self.draw_selected_item_details(layout, context)
    
    def draw_mode_controls(self, layout, context):
        """Disegna i controlli per la modalità multigraph"""
        scene = context.scene
        
        box = layout.box()
        row = box.row(align=True)
        
        # Toggle multigraph
        icon = 'OUTLINER_DATA_GREASEPENCIL' if getattr(scene, 'show_all_graphs', False) else 'OUTLINER_OB_GROUP_INSTANCE'
        row.prop(scene, "show_all_graphs", text="Multigraph", icon=icon)
        
        # Controlli aggiuntivi se necessario
        if hasattr(scene, 'show_viewport_graph_info'):
            row.prop(scene, "show_viewport_graph_info", text="Viewport Info", icon='VIEW3D')
    
    def draw_selected_item_details(self, layout, context):
        """Disegna i dettagli dell'elemento selezionato"""
        scene = context.scene
        item = scene.em_list[scene.em_list_index]
        
        from .name_conversion_utils import (
            format_name_for_display, 
            format_graph_code_for_display,
            get_active_graph_code,
            should_show_multigraph
        )
        
        box = layout.box()
        row = box.row(align=True)
        
        # Nome (convertito per display)
        display_name = format_name_for_display(item.name, "", should_show_multigraph(context))
        row.prop(item, "name", text="")
        
        # Mostra codice grafo se siamo in modalità multigraph
        if should_show_multigraph(context):
            graph_code = format_graph_code_for_display(item.name, get_active_graph_code(context))
            if graph_code and graph_code != "UNKNOWN":
                split = row.split()
                col = split.column()
                col.label(text=f"Grafo: {graph_code}")
        
        # Tipo nodo
        split = row.split()
        col = split.column()
        row.label(text=f"Type: {item.node_type}")
        
        # Pulsanti operazioni (aggiornati per gestire nomi proxy)
        split = row.split()
        col = split.column()
        op = col.operator("listitem.toobj", icon="LINK_BLEND", text='')
        if op:
            op.list_type = "em_list"
            # Qui dovresti passare il nome completo per il proxy, non quello display
            op.item_name = item.name  # Questo dovrebbe essere già il nome completo
        
        split = row.split()
        col = split.column()
        col.operator("select.listitem", text="", icon="RESTRICT_SELECT_OFF")
        
        # Descrizione
        row = box.row()
        row.prop(item, "description", text="", slider=True, emboss=True)

# Esempio per Properties Manager
class VIEW3D_PT_PropertiesPanel_Enhanced(Panel):
    """
    Pannello proprietà potenziato
    """
    bl_label = "Properties Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_PropertiesPanel_Enhanced"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        from .enhanced_uilist import draw_multigraph_header
        
        # Header multigraph
        draw_multigraph_header(layout, context)
        
        # Lista proprietà con UIList potenziata
        row = layout.row()
        row.template_list(
            "EM_PROPERTIES_UL_List_Enhanced",
            "", 
            scene, 
            "em_properties_list", 
            scene, 
            "em_properties_list_index"
        )

# Operatori aggiornati per gestire i nomi proxy
class EM_OT_SelectFromListItem_Enhanced(bpy.types.Operator):
    """
    Operatore potenziato per selezione da lista con gestione nomi proxy
    """
    bl_idname = "select.fromlistitem_enhanced"
    bl_label = "Select from List Item"
    bl_description = "Select object in 3D view from list item"
    
    list_type: bpy.props.StringProperty()
    specific_item: bpy.props.StringProperty()

    def execute(self, context):
        from .name_conversion_utils import get_active_graph_code, get_proxy_name
        
        scene = context.scene
        
        # Se il nome non ha già il prefisso, aggiungilo
        if "." not in self.specific_item:
            graph_code = get_active_graph_code(context)
            proxy_name = get_proxy_name(self.specific_item, graph_code)
        else:
            proxy_name = self.specific_item
        
        # Cerca l'oggetto nella scena
        if proxy_name in bpy.data.objects:
            obj = bpy.data.objects[proxy_name]
            
            # Deseleziona tutto
            bpy.ops.object.select_all(action='DESELECT')
            
            # Seleziona l'oggetto
            obj.select_set(True)
            context.view_layer.objects.active = obj
            
            self.report({'INFO'}, f"Selected {proxy_name}")
        else:
            self.report({'WARNING'}, f"Object {proxy_name} not found in scene")
        
        return {'FINISHED'}

class EM_OT_LinkListItemToObj_Enhanced(bpy.types.Operator):
    """
    Operatore potenziato per linking lista->oggetto con gestione nomi proxy
    """
    bl_idname = "listitem.toobj_enhanced"
    bl_label = "Link List Item to Object"
    bl_description = "Create/link object from list item"
    
    list_type: bpy.props.StringProperty()
    item_name: bpy.props.StringProperty()

    def execute(self, context):
        from .name_conversion_utils import get_active_graph_code, get_proxy_name
        
        # Se il nome non ha già il prefisso, aggiungilo
        if "." not in self.item_name:
            graph_code = get_active_graph_code(context)
            proxy_name = get_proxy_name(self.item_name, graph_code)
        else:
            proxy_name = self.item_name
        
        # Logica per creare/linkare l'oggetto proxy
        # (qui dovresti usare la tua logica esistente, ma con proxy_name)
        
        if proxy_name not in bpy.data.objects:
            # Crea il proxy se non esiste
            mesh = bpy.data.meshes.new(proxy_name)
            obj = bpy.data.objects.new(proxy_name, mesh)
            context.collection.objects.link(obj)
            
            self.report({'INFO'}, f"Created proxy {proxy_name}")
        else:
            self.report({'INFO'}, f"Proxy {proxy_name} already exists")
        
        return {'FINISHED'}

# Funzione per aggiornare gli operatori esistenti
def update_existing_operators():
    """
    Aggiorna gli operatori esistenti per usare le versioni potenziate
    """
    # Questa funzione può essere usata per sostituire gli operatori esistenti
    # con le versioni potenziate, se necessario
    pass

# Sistema di conversione per populate_lists
def populate_blender_lists_from_graph_enhanced(context, graph):
    """
    Versione potenziata della funzione populate_blender_lists_from_graph
    che gestisce i nomi con conversione al volo
    """
    scene = context.scene
    
    # Ottieni il codice del grafo
    graph_code = graph.attributes.get('graph_code', 'UNKNOWN')
    
    from .name_conversion_utils import should_show_multigraph
    is_multigraph = should_show_multigraph(context)
    
    # Clear existing lists se non siamo in modalità multigraph
    if not is_multigraph:
        scene.em_list.clear()
        scene.em_properties_list.clear()
        # ... altre liste
    
    # Il resto della logica rimane uguale, ma ora i nomi sono gestiti
    # automaticamente dalle UIList enhanced e dalle funzioni di conversione
    
    # Esempio per unità stratigrafiche
    stratigraphic_nodes = [n for n in graph.nodes if hasattr(n, 'node_type') and 
                          n.node_type in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD']]
    
    for node in stratigraphic_nodes:
        item = scene.em_list.add()
        
        # Memorizza sempre il nome completo (con prefisso)
        # Le UIList si occuperanno della conversione per display
        if "." not in node.name:
            item.name = f"{graph_code}.{node.name}"
        else:
            item.name = node.name
            
        item.description = getattr(node, 'description', '')
        item.node_type = getattr(node, 'node_type', 'US')
        # ... altri attributi

def register():
    """Registra le classi potenziate"""
    classes = [
        VIEW3D_PT_ToolsPanel_Enhanced,
        VIEW3D_PT_PropertiesPanel_Enhanced,
        EM_OT_SelectFromListItem_Enhanced,
        EM_OT_LinkListItemToObj_Enhanced,
    ]
    
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    """Disregistra le classi potenziate"""
    classes = [
        EM_OT_LinkListItemToObj_Enhanced,
        EM_OT_SelectFromListItem_Enhanced,
        VIEW3D_PT_PropertiesPanel_Enhanced,
        VIEW3D_PT_ToolsPanel_Enhanced,
    ]
    
    for cls in classes:
        bpy.utils.unregister_class(cls)