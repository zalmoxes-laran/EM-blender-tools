"""
Node types for Graph Editor
Lightweight wrappers around s3dgraphy nodes for visualization.
"""

import bpy
from bpy.types import Node
from bpy.props import StringProperty, FloatProperty, FloatVectorProperty, BoolProperty
from s3dgraphy import get_graph

# ============================================================================
# BASE NODE WRAPPER
# ============================================================================

class EMGraphNodeBase(Node):
    """
    Wrapper base per nodi s3dgraphy.
    Non duplica i dati, ma fornisce una vista sul nodo originale.
    """
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'EMGraphNodeTreeType'
    
    # Solo ID come riferimento al nodo s3dgraphy
    node_id: StringProperty(
        name="Node ID",
        description="ID del nodo s3dgraphy originale",
        default=""
    )
    
    # Nome per visualizzazione veloce (cache)
    original_name: StringProperty(
        name="Name",
        default=""
    )
    
    # Colore personalizzabile per questo nodo specifico
    custom_node_color: FloatVectorProperty(
        name="Node Color",
        subtype='COLOR',
        default=(0.5, 0.5, 0.5),
        min=0.0,
        max=1.0
    )
    
    use_custom_node_color: BoolProperty(
        name="Use Custom Color",
        default=False
    )
    
    def get_s3d_node(self, context):
        """Recupera il nodo s3dgraphy originale dal grafo"""
        tree = self.id_data  # Il NodeTree a cui appartiene questo nodo
        if tree and hasattr(tree, 'graph_id') and tree.graph_id:
            graph = get_graph(tree.graph_id)
            if graph:
                # Cerca il nodo per ID
                for node in graph.nodes:
                    if node.node_id == self.node_id:
                        return node
        return None
    
    def draw_buttons(self, context, layout):
        """Disegna info dal nodo s3dgraphy"""
        s3d_node = self.get_s3d_node(context)
        
        if s3d_node:
            col = layout.column(align=True)
            
            # Nome del nodo
            if hasattr(s3d_node, 'name') and s3d_node.name:
                col.label(text=s3d_node.name[:25])
            
            # Colore personalizzabile
            if self.use_custom_node_color:
                row = col.row()
                row.prop(self, "custom_node_color", text="")
        else:
            layout.label(text="[Node not found]", icon='ERROR')
    
    def draw_buttons_ext(self, context, layout):
        """Disegna proprietà estese nel pannello laterale"""
        s3d_node = self.get_s3d_node(context)
        
        if not s3d_node:
            layout.label(text="S3D Node not found", icon='ERROR')
            return
        
        # Sezione Info Base
        box = layout.box()
        box.label(text="Node Info", icon='INFO')
        box.prop(self, "node_id", text="ID")
        box.label(text=f"Type: {s3d_node.node_type}")
        box.label(text=f"Name: {s3d_node.name}")
        
        if hasattr(s3d_node, 'description') and s3d_node.description:
            desc_box = box.box()
            desc_box.label(text="Description:")
            # Split long descriptions
            desc_lines = s3d_node.description.split('\n')
            for line in desc_lines[:5]:  # Max 5 linee
                desc_box.label(text=line[:50])
        
        # Sezione Colore
        color_box = layout.box()
        color_box.label(text="Appearance", icon='COLOR')
        color_box.prop(self, "use_custom_node_color", text="Custom Color")
        if self.use_custom_node_color:
            color_box.prop(self, "custom_node_color", text="")
        
        # Sezione Attributes
        if hasattr(s3d_node, 'attributes') and s3d_node.attributes:
            attrs_box = layout.box()
            attrs_box.label(text="Attributes", icon='PROPERTIES')
            for key, value in list(s3d_node.attributes.items())[:10]:  # Max 10 attributi
                row = attrs_box.row()
                row.label(text=f"{key}:")
                row.label(text=str(value)[:30])

# ============================================================================
# STRATIGRAPHIC NODES
# ============================================================================

class EMGraphStratigraphicNode(EMGraphNodeBase):
    """Wrapper per nodi stratigrafici"""
    bl_idname = 'EMGraphStratigraphicNodeType'
    bl_label = 'Stratigraphic Unit'
    bl_icon = 'MESH_CUBE'
    
    def init(self, context):
        # Input per relazioni stratigrafiche
        self.inputs.new('EMGraphSocketType', "is_after")
        self.inputs.new('EMGraphSocketType', "is_contemporary")
        self.inputs.new('EMGraphSocketType', "is_filled_by")
        self.inputs.new('EMGraphSocketType', "is_cut_by")
        
        # Output per relazioni stratigrafiche
        self.outputs.new('EMGraphSocketType', "is_before")
        self.outputs.new('EMGraphSocketType', "fills")
        self.outputs.new('EMGraphSocketType', "cuts")
        self.outputs.new('EMGraphSocketType', "covers")
        
        # Socket per epoche
        self.inputs.new('EMGraphSocketType', "epoch")

class EMGraphUSNode(EMGraphStratigraphicNode):
    """Wrapper per US"""
    bl_idname = 'EMGraphUSNodeType'
    bl_label = 'US'
    
    def init(self, context):
        super().init(context)
        self.use_custom_color = True
        self.color = (0.608, 0.608, 0.608)

class EMGraphUSVsNode(EMGraphStratigraphicNode):
    """Wrapper per USVs"""
    bl_idname = 'EMGraphUSVsNodeType'
    bl_label = 'USVs'
    
    def init(self, context):
        super().init(context)
        self.use_custom_color = True
        self.color = (0.4, 0.6, 0.8)

class EMGraphUSVnNode(EMGraphStratigraphicNode):
    """Wrapper per USVn"""
    bl_idname = 'EMGraphUSVnNodeType'
    bl_label = 'USVn'
    
    def init(self, context):
        super().init(context)
        self.use_custom_color = True
        self.color = (0.8, 0.6, 0.4)

class EMGraphSFNode(EMGraphStratigraphicNode):
    """Wrapper per SF"""
    bl_idname = 'EMGraphSFNodeType'
    bl_label = 'SF'
    
    def init(self, context):
        super().init(context)
        self.use_custom_color = True
        self.color = (0.8, 0.4, 0.4)

class EMGraphVSFNode(EMGraphStratigraphicNode):
    """Wrapper per VSF"""
    bl_idname = 'EMGraphVSFNodeType'
    bl_label = 'VSF'
    
    def init(self, context):
        super().init(context)
        self.use_custom_color = True
        self.color = (0.9, 0.5, 0.5)

class EMGraphUSDNode(EMGraphStratigraphicNode):
    """Wrapper per USD"""
    bl_idname = 'EMGraphUSDNodeType'
    bl_label = 'USD'
    
    def init(self, context):
        super().init(context)
        self.use_custom_color = True
        self.color = (0.6, 0.8, 0.6)

# ============================================================================
# EPOCH NODE
# ============================================================================

class EMGraphEpochNode(EMGraphNodeBase):
    """Wrapper per epoche temporali"""
    bl_idname = 'EMGraphEpochNodeType'
    bl_label = 'Epoch'
    bl_icon = 'TIME'
    
    # Cache per visualizzazione veloce
    start_time: FloatProperty(name="Start Time", default=0.0)
    end_time: FloatProperty(name="End Time", default=0.0)
    
    def init(self, context):
        self.outputs.new('EMGraphSocketType', "contains")
        self.inputs.new('EMGraphSocketType', "previous")
        self.outputs.new('EMGraphSocketType', "next")
        self.use_custom_color = True
        self.color = (0.3, 0.5, 0.7)
    
    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)
        
        if s3d_node:
            col = layout.column(align=True)
            col.label(text="Epoch", icon='TIME')
            
            if self.use_custom_node_color:
                row = col.row()
                row.prop(self, "custom_node_color", text="")
            
            if self.original_name:
                col.label(text=self.original_name[:20])
            
            # Mostra range temporale
            if hasattr(s3d_node, 'start_time') and hasattr(s3d_node, 'end_time'):
                col.label(text=f"{s3d_node.start_time:.0f} - {s3d_node.end_time:.0f}")

# ============================================================================
# PARADATA NODE
# ============================================================================

class EMGraphParadataNode(EMGraphNodeBase):
    """Wrapper per paradata (property, extractor, combiner)"""
    bl_idname = 'EMGraphParadataNodeType'
    bl_label = 'Paradata'
    bl_icon = 'FILE_TEXT'
    
    def init(self, context):
        self.inputs.new('EMGraphSocketType', "source")
        self.outputs.new('EMGraphSocketType', "provides")
        self.use_custom_color = True
        self.color = (0.6, 0.3, 0.8)
    
    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)
        
        if s3d_node:
            col = layout.column(align=True)
            
            # Mostra tipo specifico
            node_type = s3d_node.node_type.upper()
            col.label(text=node_type, icon='FILE_TEXT')
            
            if self.original_name:
                col.label(text=self.original_name[:20])

# ============================================================================
# DOCUMENT NODE
# ============================================================================

class EMGraphDocumentNode(EMGraphNodeBase):
    """Wrapper per documenti"""
    bl_idname = 'EMGraphDocumentNodeType'
    bl_label = 'Document'
    bl_icon = 'FILE'
    
    def init(self, context):
        self.inputs.new('EMGraphSocketType', "documents")
        self.outputs.new('EMGraphSocketType', "link")
        self.use_custom_color = True
        self.color = (0.8, 0.8, 0.4)
    
    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)
        
        if s3d_node:
            col = layout.column(align=True)
            col.label(text="Document", icon='FILE')
            
            if self.original_name:
                col.label(text=self.original_name[:20])
            
            # Mostra URL se presente
            if hasattr(s3d_node, 'url') and s3d_node.url:
                col.label(text=s3d_node.url[:25], icon='URL')

# ============================================================================
# GROUP NODE
# ============================================================================

class EMGraphGroupNode(EMGraphNodeBase):
    """Wrapper per gruppi (Activity, Paradata Group, Time Branch)"""
    bl_idname = 'EMGraphGroupNodeType'
    bl_label = 'Group'
    bl_icon = 'OUTLINER_COLLECTION'
    
    def init(self, context):
        self.inputs.new('EMGraphSocketType', "members")
        self.outputs.new('EMGraphSocketType', "group")
        self.use_custom_color = True
        self.color = (0.5, 0.7, 0.5)
    
    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)
        
        if s3d_node:
            col = layout.column(align=True)
            
            # Mostra tipo specifico
            if 'activity' in s3d_node.node_type.lower():
                col.label(text="Activity", icon='OUTLINER_COLLECTION')
            elif 'paradata' in s3d_node.node_type.lower():
                col.label(text="Paradata Group", icon='FILE_TEXT')
            elif 'time_branch' in s3d_node.node_type.lower():
                col.label(text="Time Branch", icon='TIME')
            else:
                col.label(text="Group", icon='OUTLINER_COLLECTION')
            
            if self.original_name:
                col.label(text=self.original_name[:20])

# ============================================================================
# REPRESENTATION NODE
# ============================================================================

class EMGraphRepresentationNode(EMGraphNodeBase):
    """Wrapper per rappresentazioni 3D"""
    bl_idname = 'EMGraphRepresentationNodeType'
    bl_label = 'Representation'
    bl_icon = 'MESH_DATA'
    
    def init(self, context):
        self.inputs.new('EMGraphSocketType', "represents")
        self.outputs.new('EMGraphSocketType', "model")
        self.use_custom_color = True
        self.color = (0.4, 0.8, 0.6)
    
    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)
        
        if s3d_node:
            col = layout.column(align=True)
            col.label(text="3D Model", icon='MESH_DATA')
            
            if self.original_name:
                col.label(text=self.original_name[:20])

# ============================================================================
# LINK NODE
# ============================================================================

class EMGraphLinkNode(EMGraphNodeBase):
    """Wrapper per link esterni"""
    bl_idname = 'EMGraphLinkNodeType'
    bl_label = 'Link'
    bl_icon = 'URL'
    
    def init(self, context):
        self.inputs.new('EMGraphSocketType', "source")
        self.outputs.new('EMGraphSocketType', "url")
        self.use_custom_color = True
        self.color = (0.7, 0.7, 0.3)
    
    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)
        
        if s3d_node:
            col = layout.column(align=True)
            col.label(text="Link", icon='URL')
            
            if hasattr(s3d_node, 'url') and s3d_node.url:
                col.label(text=s3d_node.url[:25])

# ============================================================================
# REGISTRATION
# ============================================================================

classes = (
    # Base wrapper
    #EMGraphNodeBase,
    
    # Stratigraphic nodes
    #EMGraphStratigraphicNode,
    EMGraphUSNode,
    EMGraphUSVsNode,
    EMGraphUSVnNode,
    EMGraphSFNode,
    EMGraphVSFNode,
    EMGraphUSDNode,
    
    # Other nodes
    EMGraphEpochNode,
    EMGraphParadataNode,
    EMGraphDocumentNode,
    EMGraphGroupNode,
    EMGraphRepresentationNode,
    EMGraphLinkNode,
)

def register_nodes():
    """Register all node classes"""
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass

def unregister_nodes():
    """Unregister all node classes"""
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass