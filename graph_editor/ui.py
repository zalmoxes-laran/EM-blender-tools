"""
UI components for Graph Editor
Contains panels and UI elements for the node editor interface.
"""

import bpy
from bpy.types import Panel, Menu

class GRAPHEDIT_PT_main_panel(Panel):
    """Pannello principale nel Node Editor"""
    bl_label = "EMGraph Tools"
    bl_idname = "GRAPHEDIT_PT_main_panel"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "EMGraph"
    
    @classmethod
    def poll(cls, context):
        return (context.space_data.type == 'NODE_EDITOR' and
                context.space_data.tree_type == 'EMGraphNodeTreeType')
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Pulsante principale "Draw Graph"
        box = layout.box()
        box.label(text="Graph Operations", icon='NODETREE')
        
        col = box.column(align=True)
        col.operator("graphedit.draw_graph", icon='FILE_REFRESH', text="Draw Active Graph")
        col.operator("graphedit.clear_editor", icon='X', text="Clear Graph")
        
        layout.separator()
        
        # Info sul grafo corrente
        tree = context.space_data.node_tree
        if tree:
            info_box = layout.box()
            info_box.label(text="Current Graph", icon='INFO')
            
            col = info_box.column(align=True)
            col.label(text=f"Name: {tree.graph_name}")
            col.label(text=f"Nodes: {tree.node_count}")
            col.label(text=f"Edges: {tree.edge_count}")
            
            if tree.graph_id:
                col.label(text=f"ID: {tree.graph_id[:16]}...")
        
        layout.separator()
        
        # Opzioni
        options_box = layout.box()
        options_box.label(text="Options", icon='SETTINGS')
        options_box.prop(scene, "graph_editor_auto_layout", text="Auto Layout")
        options_box.prop(scene, "graph_editor_show_labels", text="Show Labels")

class GRAPHEDIT_PT_appearance(Panel):
    """Pannello per colori e aspetto"""
    bl_label = "Appearance"
    bl_idname = "GRAPHEDIT_PT_appearance"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "EMGraph"
    bl_parent_id = "GRAPHEDIT_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return (context.space_data.type == 'NODE_EDITOR' and
                context.space_data.tree_type == 'EMGraphNodeTreeType')
    
    def draw(self, context):
        layout = self.layout
        tree = context.space_data.node_tree
        
        if not tree:
            return
        
        # Schema colori predefiniti
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
        
        op = row.operator("graphedit.apply_color_scheme", text="Grayscale")
        op.scheme = 'GRAYSCALE'
        
        layout.separator()
        
        # Colori globali di default
        colors_box = layout.box()
        colors_box.label(text="Default Colors", icon='COLORSET_01_VEC')
        
        col = colors_box.column(align=True)
        col.prop(tree, "default_us_color", text="US")
        col.prop(tree, "default_usvs_color", text="USVs")
        col.prop(tree, "default_usvn_color", text="USVn")
        col.prop(tree, "default_epoch_color", text="Epoch")
        col.prop(tree, "default_document_color", text="Document")
        col.prop(tree, "default_paradata_color", text="Paradata")

class GRAPHEDIT_PT_node_info(Panel):
    """Pannello info nodo selezionato"""
    bl_label = "Node Info"
    bl_idname = "GRAPHEDIT_PT_node_info"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "EMGraph"
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
        box.label(text="Selected Node", icon='NODE_SEL')
        
        col = box.column(align=True)
        col.label(text=f"Type: {node.bl_label}")
        
        if hasattr(node, 'node_id') and node.node_id:
            col.label(text=f"ID: {node.node_id[:20]}...")
        
        if hasattr(node, 'original_name') and node.original_name:
            col.label(text=f"Name: {node.original_name}")
        
        # Connessioni
        col.separator()
        col.label(text=f"Inputs: {len(node.inputs)}")
        col.label(text=f"Outputs: {len(node.outputs)}")
        
        # Operatori su nodo
        layout.separator()
        
        col = layout.column(align=True)
        col.operator("graphedit.refresh_node", icon='FILE_REFRESH')
        
        # Colore personalizzato
        if hasattr(node, 'use_custom_node_color'):
            color_box = layout.box()
            color_box.label(text="Node Color", icon='COLOR')
            color_box.prop(node, "use_custom_node_color", text="Custom Color")
            if node.use_custom_node_color:
                color_box.prop(node, "custom_node_color", text="")

# ============================================================================
# REGISTRATION
# ============================================================================

classes = (
    GRAPHEDIT_PT_main_panel,
    GRAPHEDIT_PT_appearance,
    GRAPHEDIT_PT_node_info,
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