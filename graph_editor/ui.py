"""
UI components for Graph Editor
Contains panels and UI elements for the node editor interface.
"""

import bpy
from bpy.types import Panel, UIList

class GRAPHEDIT_UL_edge_filters(UIList):
    """UIList per i filtri edge types"""
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "enabled", text="")
            row.label(text=item.label, icon='ARROW_LEFTRIGHT')
            
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.prop(item, "enabled", text="", emboss=False, icon='CHECKMARK')


class GRAPHEDIT_PT_main_panel(Panel):
    """Pannello principale nel Node Editor"""
    bl_label = "EMGraph Tools"
    bl_idname = "GRAPHEDIT_PT_main_panel"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "EM"  # ✅ Stesso category di EMTools
    
    @classmethod
    def poll(cls, context):
        return (context.space_data.type == 'NODE_EDITOR' and
                context.space_data.tree_type == 'EMGraphNodeTreeType')
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.graph_editor_settings
        
        # Quick Load Section
        box = layout.box()
        box.label(text="Quick Load", icon='NODETREE')
        
        col = box.column(align=True)
        
        # All Nodes
        op = col.operator("graphedit.draw_graph", icon='FILE_REFRESH', text="All Nodes")
        op.filter_mode = 'ALL'
        
        col.separator()
        
        # Stratigraphic filters
        row = col.row(align=True)
        op = row.operator("graphedit.draw_graph", icon='MESH_CUBE', text="Stratigraphic")
        op.filter_mode = 'STRATIGRAPHIC'
        
        op = row.operator("graphedit.draw_graph", icon='CUBE', text="US Only")
        op.filter_mode = 'US_ONLY'
        
        col.separator()
        
        # From UI List
        op = col.operator("graphedit.draw_graph", icon='PRESET', text="From UI List")
        op.filter_mode = 'FROM_UILIST'
        
        layout.separator()
        
        # Neighborhood Section
        neighbor_box = layout.box()
        neighbor_box.label(text="Neighborhood View", icon='SNAP_FACE')
        
        col = neighbor_box.column(align=True)
        col.label(text="1. Select node (3D/UI/Graph)")
        col.label(text="2. Choose depth:")
        
        row = col.row(align=True)
        for depth in [1, 2, 3]:
            op = row.operator("graphedit.draw_neighborhood", text=f"Lvl {depth}")
            op.depth = depth
        
        col.separator(factor=0.5)
        col.label(text="Shortcut: Shift+Alt+N", icon='KEYINGSET')
        
        layout.separator()
        
        # Node + Context Section
        context_box = layout.box()
        context_box.label(text="Node + Context", icon='LINK_BLEND')
        
        col = context_box.column(align=True)
        col.label(text="Show selected node with:")
        
        row = col.row(align=True)
        row.prop(settings, "show_stratigraphic_context", text="", icon='MOD_ARRAY')
        row.label(text="Stratigraphic")
        
        row = col.row(align=True)
        row.prop(settings, "show_paradata_context", text="", icon='FILE_TEXT')
        row.label(text="Paradata")
        
        row = col.row(align=True)
        row.prop(settings, "show_model_context", text="", icon='MESH_DATA')
        row.label(text="3D Models")
        
        col.separator(factor=0.5)
        op = col.operator("graphedit.draw_graph", text="Load Context View")
        op.filter_mode = 'NODE_CONTEXT'
        
        layout.separator()
        
        # Sync Section
        sync_box = layout.box()
        sync_box.label(text="Synchronization", icon='LINKED')
        
        col = sync_box.column(align=True)
        col.operator("graphedit.sync_selection", icon='UV_SYNC_SELECT', text="Sync Selection")
        
        col.separator(factor=0.5)
        col.label(text="Shortcut: Shift+Alt+F", icon='KEYINGSET')
        
        layout.separator()
        
        # Actions
        col = layout.column(align=True)
        col.operator("graphedit.clear_editor", icon='X', text="Clear Graph")
        
        layout.separator()
        
        # Graph Info
        tree = context.space_data.node_tree
        if tree:
            info_box = layout.box()
            info_box.label(text="Current Graph", icon='INFO')
            
            col = info_box.column(align=True)
            col.label(text=f"Nodes: {tree.node_count}")
            col.label(text=f"Edges: {tree.edge_count}")


class GRAPHEDIT_PT_edge_filters(Panel):
    """Pannello per filtraggio avanzato per edge types"""
    bl_label = "Edge Type Filters"
    bl_idname = "GRAPHEDIT_PT_edge_filters"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "EM"
    bl_parent_id = "GRAPHEDIT_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return (context.space_data.type == 'NODE_EDITOR' and
                context.space_data.tree_type == 'EMGraphNodeTreeType')
    
    def draw_header(self, context):
        settings = context.scene.graph_editor_settings
        self.layout.prop(settings, "show_edge_filter_panel", text="")
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.graph_editor_settings
        
        if not settings.show_edge_filter_panel:
            return
        
        # Initialize button se non ci sono filtri
        if len(settings.edge_filters) == 0:
            box = layout.box()
            box.label(text="Edge filters not initialized", icon='ERROR')
            box.operator("graphedit.initialize_edge_filters", icon='FILE_REFRESH')
            return
        
        # Quick toggles
        box = layout.box()
        box.label(text="Quick Toggle", icon='PREFERENCES')
        
        row = box.row(align=True)
        row.operator("graphedit.toggle_edge_category", text="All").category = 'ALL'
        row.operator("graphedit.toggle_edge_category", text="None").category = 'NONE'
        
        layout.separator()
        
        # Filters by category
        categories = {
            'STRATIGRAPHIC': ("Stratigraphic", 'MOD_ARRAY'),
            'TEMPORAL': ("Temporal", 'TIME'),
            'PARADATA': ("Paradata", 'FILE_TEXT'),
            'MODEL': ("3D Models", 'MESH_DATA'),
            'OTHER': ("Other", 'DOT'),
        }
        
        for cat_id, (cat_label, cat_icon) in categories.items():
            # Filtra edge types per categoria
            cat_filters = [ef for ef in settings.edge_filters if ef.category == cat_id]
            
            if not cat_filters:
                continue
            
            box = layout.box()
            
            # Header con toggle categoria
            row = box.row(align=True)
            row.label(text=cat_label, icon=cat_icon)
            op = row.operator("graphedit.toggle_edge_category", text="", icon='CHECKBOX_HLT')
            op.category = cat_id
            
            # Lista edge types
            col = box.column(align=True)
            for ef in cat_filters:
                row = col.row(align=True)
                row.prop(ef, "enabled", text="")
                row.label(text=ef.label)
        
        layout.separator()
        
        # Apply filter button
        box = layout.box()
        op = box.operator("graphedit.draw_graph", text="Apply Edge Filter", icon='FILTER')
        op.filter_mode = 'EDGE_FILTERED'


class GRAPHEDIT_PT_appearance(Panel):
    """Pannello colori"""
    bl_label = "Appearance"
    bl_idname = "GRAPHEDIT_PT_appearance"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "EM"
    bl_parent_id = "GRAPHEDIT_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return (context.space_data.type == 'NODE_EDITOR' and
                context.space_data.tree_type == 'EMGraphNodeTreeType')
    
    def draw(self, context):
        layout = self.layout
        
        box = layout.box()
        box.label(text="Color Schemes", icon='COLOR')
        
        row = box.row(align=True)
        op = row.operator("graphedit.apply_color_scheme", text="Default")
        op.scheme = 'DEFAULT'
        
        op = row.operator("graphedit.apply_color_scheme", text="Pastel")
        op.scheme = 'PASTEL'
        
        row = box.row(align=True)
        op = row.operator("graphedit.apply_color_scheme", text="Vibrant")
        op.scheme = 'VIBRANT'
        
        op = row.operator("graphedit.apply_color_scheme", text="Gray")
        op.scheme = 'GRAYSCALE'


class GRAPHEDIT_PT_node_info(Panel):
    """Info nodo selezionato"""
    bl_label = "Selected Node"
    bl_idname = "GRAPHEDIT_PT_node_info"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "EM"
    bl_parent_id = "GRAPHEDIT_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return (context.space_data.type == 'NODE_EDITOR' and
                context.space_data.tree_type == 'EMGraphNodeTreeType' and
                context.active_node is not None)
    
    def draw(self, context):
        layout = self.layout
        node = context.active_node
        
        box = layout.box()
        box.label(text=node.bl_label, icon='NODE_SEL')
        
        col = box.column(align=True)
        
        if hasattr(node, 'node_id') and node.node_id:
            col.label(text=f"ID: {node.node_id[:20]}...")
        
        if hasattr(node, 'original_name') and node.original_name:
            col.label(text=f"Name: {node.original_name[:20]}")
        
        col.separator()
        col.label(text=f"Inputs: {len(node.inputs)}")
        col.label(text=f"Outputs: {len(node.outputs)}")
        
        # Actions
        layout.separator()
        
        col = layout.column(align=True)
        col.operator("graphedit.sync_selection", icon='UV_SYNC_SELECT', text="Sync to 3D")
        
        # Show neighborhood
        layout.separator()
        
        box = layout.box()
        box.label(text="Show Neighborhood", icon='SNAP_FACE')
        
        row = box.row(align=True)
        for depth in [1, 2, 3]:
            op = row.operator("graphedit.draw_neighborhood", text=str(depth))
            op.depth = depth
        
        # Context view
        layout.separator()
        
        op = layout.operator("graphedit.draw_graph", text="Show Full Context", icon='LINK_BLEND')
        op.filter_mode = 'NODE_CONTEXT'


class VIEW3D_PT_graphedit_sync(Panel):
    """Pannello nella 3D View per sincronizzazione veloce"""
    bl_label = "Graph Sync"
    bl_idname = "VIEW3D_PT_graphedit_sync"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM"
    
    def draw(self, context):
        layout = self.layout
        
        box = layout.box()
        box.label(text="Graph Editor", icon='LINKED')
        
        col = box.column(align=True)
        col.operator("graphedit.sync_selection", icon='UV_SYNC_SELECT', text="Sync to Graph")
        col.label(text="Shortcut: Shift+Alt+F", icon='KEYINGSET')
        
        layout.separator()
        
        # Neighborhood from 3D
        neighbor_box = layout.box()
        neighbor_box.label(text="Show in Graph", icon='SNAP_FACE')
        
        col = neighbor_box.column(align=True)
        col.label(text="Neighborhood:")
        
        row = col.row(align=True)
        for depth in [1, 2, 3]:
            op = row.operator("graphedit.draw_neighborhood", text=str(depth))
            op.depth = depth
        
        col.separator()
        
        op = col.operator("graphedit.draw_graph", text="Full Context", icon='LINK_BLEND')
        op.filter_mode = 'NODE_CONTEXT'
        
        # Info oggetto selezionato
        if context.active_object:
            obj = context.active_object
            
            # ✅ NON chiamare find_node_id_from_proxy qui (troppo pesante)
            # Mostra solo info base
            
            layout.separator()
            info_box = layout.box()
            info_box.label(text="Selected Object", icon='OBJECT_DATA')
            
            col = info_box.column(align=True)
            col.label(text=f"Name: {obj.name[:20]}")
            
            # ✅ Controlla solo se ha il prefisso del grafo
            em_tools = context.scene.em_tools
            if em_tools.active_file_index >= 0 and em_tools.graphml_files:
                graphml = em_tools.graphml_files[em_tools.active_file_index]
                graph_code = graphml.graph_code if hasattr(graphml, 'graph_code') else None
                
                if graph_code and obj.name.startswith(f"{graph_code}."):
                    # ✅ Estrai human name SENZA chiamare funzioni pesanti
                    human_name = obj.name[len(graph_code) + 1:]
                    col.label(text=f"Node: {human_name[:16]}")
                else:
                    col.label(text="Not a graph node", icon='INFO')
            
        else:
            layout.separator()
            layout.label(text="No object selected", icon='INFO')


class GRAPHEDIT_OT_toggle_edge_category(bpy.types.Operator):
    """Toggle tutti gli edge di una categoria"""
    bl_idname = "graphedit.toggle_edge_category"
    bl_label = "Toggle Category"
    bl_description = "Enable/disable all edges in category"
    
    category: bpy.props.EnumProperty(
        items=[
            ('ALL', "All", ""),
            ('NONE', "None", ""),
            ('STRATIGRAPHIC', "Stratigraphic", ""),
            ('TEMPORAL', "Temporal", ""),
            ('PARADATA', "Paradata", ""),
            ('MODEL', "Model", ""),
            ('OTHER', "Other", ""),
        ]
    )
    
    def execute(self, context):
        settings = context.scene.graph_editor_settings
        
        if self.category == 'ALL':
            for ef in settings.edge_filters:
                ef.enabled = True
        elif self.category == 'NONE':
            for ef in settings.edge_filters:
                ef.enabled = False
        else:
            # Toggle categoria specifica
            for ef in settings.edge_filters:
                if ef.category == self.category:
                    ef.enabled = not ef.enabled
        
        return {'FINISHED'}


class GRAPHEDIT_OT_apply_color_scheme(bpy.types.Operator):
    """Applica schema colori"""
    bl_idname = "graphedit.apply_color_scheme"
    bl_label = "Apply Color Scheme"
    
    scheme: bpy.props.EnumProperty(
        items=[
            ('DEFAULT', "Default", ""),
            ('PASTEL', "Pastel", ""),
            ('VIBRANT', "Vibrant", ""),
            ('GRAYSCALE', "Grayscale", ""),
        ]
    )
    
    def execute(self, context):
        tree = context.space_data.node_tree
        if not tree or tree.bl_idname != 'EMGraphNodeTreeType':
            return {'CANCELLED'}
        
        schemes = {
            'DEFAULT': {
                'US': (0.608, 0.608, 0.608),
                'USVs': (0.4, 0.6, 0.8),
                'USVn': (0.8, 0.6, 0.4),
                'SF': (0.8, 0.4, 0.4),
            },
            'PASTEL': {
                'US': (0.8, 0.8, 0.9),
                'USVs': (0.7, 0.8, 0.9),
                'USVn': (0.9, 0.8, 0.7),
                'SF': (0.9, 0.7, 0.7),
            },
            'VIBRANT': {
                'US': (0.3, 0.3, 0.9),
                'USVs': (0.2, 0.6, 1.0),
                'USVn': (1.0, 0.6, 0.2),
                'SF': (1.0, 0.2, 0.2),
            },
            'GRAYSCALE': {
                'US': (0.7, 0.7, 0.7),
                'USVs': (0.6, 0.6, 0.6),
                'USVn': (0.5, 0.5, 0.5),
                'SF': (0.4, 0.4, 0.4),
            }
        }
        
        scheme = schemes[self.scheme]
        count = 0
        
        for node in tree.nodes:
            if hasattr(node, 'custom_node_color'):
                node_type = None
                if 'US' in node.bl_label:
                    node_type = 'US'
                elif 'SF' in node.bl_label:
                    node_type = 'SF'
                
                if node_type and node_type in scheme:
                    color = scheme[node_type]
                    node.custom_node_color = color
                    node.use_custom_node_color = True
                    node.use_custom_color = True
                    node.color = color
                    count += 1
        
        self.report({'INFO'}, f"Applied {self.scheme} to {count} nodes")
        return {'FINISHED'}


# ============================================================================
# REGISTRATION
# ============================================================================

classes = (
    GRAPHEDIT_UL_edge_filters,
    GRAPHEDIT_PT_main_panel,
    GRAPHEDIT_PT_edge_filters,
    GRAPHEDIT_PT_appearance,
    GRAPHEDIT_PT_node_info,
    VIEW3D_PT_graphedit_sync,
    GRAPHEDIT_OT_toggle_edge_category,
    GRAPHEDIT_OT_apply_color_scheme,
)

def register_ui():
    """Register all UI classes"""
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass

def unregister_ui():
    """Unregister all UI classes"""
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass