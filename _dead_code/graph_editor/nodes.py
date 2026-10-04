"""
Node types for Graph Viewer
Lightweight wrappers around s3dgraphy nodes for visualization.
"""

import bpy
from bpy.types import Node
from bpy.props import StringProperty, FloatProperty, FloatVectorProperty, BoolProperty
from s3dgraphy import get_graph
from .socket_generator import generate_sockets, get_node_color_from_datamodel

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
    """Wrapper per nodi stratigrafici - Base class"""
    bl_idname = 'EMGraphStratigraphicNodeType'
    bl_label = 'Stratigraphic Unit'
    bl_icon = 'MESH_CUBE'

    def init(self, context):
        # ✅ Usa il sistema dinamico di socket basato su StratigraphicNode
        generate_sockets(self, "StratigraphicNode")

class EMGraphUSNode(EMGraphStratigraphicNode):
    """Wrapper per US (Stratigraphic Unit)"""
    bl_idname = 'EMGraphUSNodeType'
    bl_label = 'US'

    def init(self, context):
        super().init(context)
        # Colore da datamodel: white rectangle
        color = get_node_color_from_datamodel('US') or (0.9, 0.9, 0.9)
        self.use_custom_color = True
        self.color = color

class EMGraphUSVsNode(EMGraphStratigraphicNode):
    """Wrapper per USVs (Structural Virtual SU)"""
    bl_idname = 'EMGraphUSVsNodeType'
    bl_label = 'USVs'

    def init(self, context):
        super().init(context)
        color = get_node_color_from_datamodel('USVs') or (0.2, 0.3, 0.5)
        self.use_custom_color = True
        self.color = color

class EMGraphUSVnNode(EMGraphStratigraphicNode):
    """Wrapper per USVn (Non-Structural Virtual SU)"""
    bl_idname = 'EMGraphUSVnNodeType'
    bl_label = 'USVn'

    def init(self, context):
        super().init(context)
        color = get_node_color_from_datamodel('USVn') or (0.2, 0.5, 0.3)
        self.use_custom_color = True
        self.color = color

class EMGraphSFNode(EMGraphStratigraphicNode):
    """Wrapper per SF (Special Find)"""
    bl_idname = 'EMGraphSFNodeType'
    bl_label = 'SF'

    def init(self, context):
        super().init(context)
        color = get_node_color_from_datamodel('SF') or (0.95, 0.85, 0.3)
        self.use_custom_color = True
        self.color = color

class EMGraphVSFNode(EMGraphStratigraphicNode):
    """Wrapper per VSF (Virtual Special Find)"""
    bl_idname = 'EMGraphVSFNodeType'
    bl_label = 'VSF'

    def init(self, context):
        super().init(context)
        color = get_node_color_from_datamodel('VSF') or (0.7, 0.6, 0.2)
        self.use_custom_color = True
        self.color = color

class EMGraphUSDNode(EMGraphStratigraphicNode):
    """Wrapper per USD (Documentary SU)"""
    bl_idname = 'EMGraphUSDNodeType'
    bl_label = 'USD'

    def init(self, context):
        super().init(context)
        color = get_node_color_from_datamodel('USD') or (0.9, 0.7, 0.5)
        self.use_custom_color = True
        self.color = color

# ============================================================================
# STRATIGRAPHIC NODES - NEW TYPES
# ============================================================================

class EMGraphSerSUNode(EMGraphStratigraphicNode):
    """Wrapper per serSU (Series of SU)"""
    bl_idname = 'EMGraphSerSUNodeType'
    bl_label = 'serSU'

    def init(self, context):
        super().init(context)
        color = get_node_color_from_datamodel('serSU') or (0.85, 0.85, 0.85)
        self.use_custom_color = True
        self.color = color

class EMGraphSerUSDNode(EMGraphStratigraphicNode):
    """Wrapper per serUSD (Series of Documentary SU)"""
    bl_idname = 'EMGraphSerUSDNodeType'
    bl_label = 'serUSD'

    def init(self, context):
        super().init(context)
        color = get_node_color_from_datamodel('serUSD') or (0.85, 0.5, 0.0)
        self.use_custom_color = True
        self.color = color

class EMGraphSerUSVsNode(EMGraphStratigraphicNode):
    """Wrapper per serUSVs (Series of Structural Virtual SU)"""
    bl_idname = 'EMGraphSerUSVsNodeType'
    bl_label = 'serUSVs'

    def init(self, context):
        super().init(context)
        color = get_node_color_from_datamodel('serUSVs') or (0.3, 0.4, 0.6)
        self.use_custom_color = True
        self.color = color

class EMGraphSerUSVnNode(EMGraphStratigraphicNode):
    """Wrapper per serUSVn (Series of Non-Structural Virtual SU)"""
    bl_idname = 'EMGraphSerUSVnNodeType'
    bl_label = 'serUSVn'

    def init(self, context):
        super().init(context)
        color = get_node_color_from_datamodel('serUSVn') or (0.3, 0.6, 0.4)
        self.use_custom_color = True
        self.color = color

class EMGraphTSUNode(EMGraphStratigraphicNode):
    """Wrapper per TSU (Transformation SU)"""
    bl_idname = 'EMGraphTSUNodeType'
    bl_label = 'TSU'

    def init(self, context):
        super().init(context)
        color = get_node_color_from_datamodel('TSU') or (0.9, 0.6, 0.6)
        self.use_custom_color = True
        self.color = color

class EMGraphULNode(EMGraphStratigraphicNode):
    """Wrapper per UL (Working Unit)"""
    bl_idname = 'EMGraphULNodeType'
    bl_label = 'UL'

    def init(self, context):
        super().init(context)
        color = get_node_color_from_datamodel('UL') or (0.9, 0.6, 0.2)
        self.use_custom_color = True
        self.color = color

class EMGraphBRNode(EMGraphStratigraphicNode):
    """Wrapper per BR (Continuity Node)"""
    bl_idname = 'EMGraphBRNodeType'
    bl_label = 'BR'

    def init(self, context):
        super().init(context)
        color = get_node_color_from_datamodel('BR') or (0.3, 0.3, 0.3)
        self.use_custom_color = True
        self.color = color

class EMGraphSENode(EMGraphStratigraphicNode):
    """Wrapper per SE (Stratigraphic Event)"""
    bl_idname = 'EMGraphSENodeType'
    bl_label = 'SE'

    def init(self, context):
        super().init(context)
        color = get_node_color_from_datamodel('SE') or (0.7, 0.5, 0.7)
        self.use_custom_color = True
        self.color = color

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
        # ✅ Socket dinamici per EpochNode
        generate_sockets(self, "EpochNode")

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
# PARADATA NODES
# ============================================================================

class EMGraphPropertyNode(EMGraphNodeBase):
    """Wrapper per PropertyNode"""
    bl_idname = 'EMGraphPropertyNodeType'
    bl_label = 'Property'
    bl_icon = 'PROPERTIES'

    def init(self, context):
        # ✅ Socket dinamici per PropertyNode
        generate_sockets(self, "PropertyNode")
        self.use_custom_color = True
        self.color = (0.5, 0.8, 0.5)  # Verde chiaro

    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)

        if s3d_node:
            col = layout.column(align=True)
            col.label(text="Property", icon='PROPERTIES')

            if self.original_name:
                col.label(text=self.original_name[:20])

class EMGraphExtractorNode(EMGraphNodeBase):
    """Wrapper per ExtractorNode"""
    bl_idname = 'EMGraphExtractorNodeType'
    bl_label = 'Extractor'
    bl_icon = 'EXPORT'

    def init(self, context):
        # ✅ Socket dinamici per ExtractorNode
        generate_sockets(self, "ExtractorNode")
        self.use_custom_color = True
        self.color = (0.9, 0.6, 0.3)  # Arancione

    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)

        if s3d_node:
            col = layout.column(align=True)
            col.label(text="Extractor", icon='EXPORT')

            if self.original_name:
                col.label(text=self.original_name[:20])

class EMGraphCombinerNode(EMGraphNodeBase):
    """Wrapper per CombinerNode"""
    bl_idname = 'EMGraphCombinerNodeType'
    bl_label = 'Combiner'
    bl_icon = 'SORT_DESC'

    def init(self, context):
        # ✅ Socket dinamici per CombinerNode
        generate_sockets(self, "CombinerNode")
        self.use_custom_color = True
        self.color = (0.7, 0.4, 0.8)  # Viola
    
    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)

        if s3d_node:
            col = layout.column(align=True)
            col.label(text="Combiner", icon='SORT_DESC')

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
        # ✅ Socket dinamici per DocumentNode
        generate_sockets(self, "DocumentNode")
        self.use_custom_color = True
        self.color = (0.3, 0.4, 0.7)  # Blu scuro
    
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
# GROUP NODES
# ============================================================================

class EMGraphActivityNodeGroup(EMGraphNodeBase):
    """Wrapper per ActivityNodeGroup"""
    bl_idname = 'EMGraphActivityNodeType'
    bl_label = 'Activity'
    bl_icon = 'OUTLINER_COLLECTION'

    def init(self, context):
        # ✅ Socket dinamici per ActivityNodeGroup
        generate_sockets(self, "ActivityNodeGroup")
        self.use_custom_color = True
        self.color = (0.5, 0.7, 0.5)  # Verde

    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)

        if s3d_node:
            col = layout.column(align=True)
            col.label(text="Activity", icon='OUTLINER_COLLECTION')

            if self.original_name:
                col.label(text=self.original_name[:20])

class EMGraphParadataGroupNode(EMGraphNodeBase):
    """Wrapper per ParadataNodeGroup"""
    bl_idname = 'EMGraphParadataGroupNodeType'
    bl_label = 'Paradata Group'
    bl_icon = 'FILE_TEXT'

    def init(self, context):
        # ✅ Socket dinamici per ParadataNodeGroup
        generate_sockets(self, "ParadataNodeGroup")
        self.use_custom_color = True
        self.color = (0.6, 0.5, 0.7)  # Viola chiaro

    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)

        if s3d_node:
            col = layout.column(align=True)
            col.label(text="Paradata Group", icon='FILE_TEXT')

            if self.original_name:
                col.label(text=self.original_name[:20])

class EMGraphTimeBranchNode(EMGraphNodeBase):
    """Wrapper per TimeBranchNodeGroup"""
    bl_idname = 'EMGraphTimeBranchNodeType'
    bl_label = 'Time Branch'
    bl_icon = 'TIME'

    def init(self, context):
        # ✅ Socket dinamici per TimeBranchNodeGroup
        generate_sockets(self, "TimeBranchNodeGroup")
        self.use_custom_color = True
        self.color = (0.4, 0.6, 0.7)  # Azzurro

    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)

        if s3d_node:
            col = layout.column(align=True)
            col.label(text="Time Branch", icon='TIME')

            if self.original_name:
                col.label(text=self.original_name[:20])

# ============================================================================
# VISUALIZATION NODES
# ============================================================================

class EMGraphRepresentationNode(EMGraphNodeBase):
    """Wrapper per RepresentationModelNode"""
    bl_idname = 'EMGraphRepresentationNodeType'
    bl_label = 'Representation Model'
    bl_icon = 'MESH_DATA'

    def init(self, context):
        # ✅ Socket dinamici per RepresentationModelNode
        generate_sockets(self, "RepresentationModelNode")
        self.use_custom_color = True
        self.color = (0.4, 0.8, 0.6)  # Verde acqua

    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)

        if s3d_node:
            col = layout.column(align=True)
            col.label(text="3D Model", icon='MESH_DATA')

            if self.original_name:
                col.label(text=self.original_name[:20])

class EMGraphRepresentationDocNode(EMGraphNodeBase):
    """Wrapper per RepresentationModelDocNode"""
    bl_idname = 'EMGraphRepresentationDocNodeType'
    bl_label = 'Representation Doc'
    bl_icon = 'FILE_3D'

    def init(self, context):
        # ✅ Socket dinamici per RepresentationModelDocNode
        generate_sockets(self, "RepresentationModelDocNode")
        self.use_custom_color = True
        self.color = (0.5, 0.7, 0.8)  # Azzurro chiaro

    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)

        if s3d_node:
            col = layout.column(align=True)
            col.label(text="Doc Model", icon='FILE_3D')

            if self.original_name:
                col.label(text=self.original_name[:20])

class EMGraphRepresentationSFNode(EMGraphNodeBase):
    """Wrapper per RepresentationModelSpecialFindNode"""
    bl_idname = 'EMGraphRepresentationSFNodeType'
    bl_label = 'Representation SF'
    bl_icon = 'MESH_ICOSPHERE'

    def init(self, context):
        # ✅ Socket dinamici per RepresentationModelSpecialFindNode
        generate_sockets(self, "RepresentationModelSpecialFindNode")
        self.use_custom_color = True
        self.color = (0.8, 0.7, 0.4)  # Oro

    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)

        if s3d_node:
            col = layout.column(align=True)
            col.label(text="SF Model", icon='MESH_ICOSPHERE')

            if self.original_name:
                col.label(text=self.original_name[:20])

class EMGraphSemanticShapeNode(EMGraphNodeBase):
    """Wrapper per SemanticShapeNode"""
    bl_idname = 'EMGraphSemanticShapeNodeType'
    bl_label = 'Semantic Shape'
    bl_icon = 'MESH_CUBE'

    def init(self, context):
        # ✅ Socket dinamici per SemanticShapeNode
        generate_sockets(self, "SemanticShapeNode")
        self.use_custom_color = True
        self.color = (0.7, 0.5, 0.9)  # Viola chiaro

    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)

        if s3d_node:
            col = layout.column(align=True)
            col.label(text="Semantic Shape", icon='MESH_CUBE')

            if self.original_name:
                col.label(text=self.original_name[:20])

# ============================================================================
# REFERENCE NODES
# ============================================================================

class EMGraphGeoPositionNode(EMGraphNodeBase):
    """Wrapper per GeoPositionNode"""
    bl_idname = 'EMGraphGeoPositionNodeType'
    bl_label = 'Geo Position'
    bl_icon = 'WORLD'

    def init(self, context):
        # ✅ Socket dinamici per GeoPositionNode
        generate_sockets(self, "GeoPositionNode")
        self.use_custom_color = True
        self.color = (0.3, 0.7, 0.4)  # Verde terra

    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)

        if s3d_node:
            col = layout.column(align=True)
            col.label(text="Geo Position", icon='WORLD')

            if self.original_name:
                col.label(text=self.original_name[:20])

class EMGraphLinkNode(EMGraphNodeBase):
    """Wrapper per LinkNode"""
    bl_idname = 'EMGraphLinkNodeType'
    bl_label = 'Link'
    bl_icon = 'URL'

    def init(self, context):
        # ✅ Socket dinamici per LinkNode
        generate_sockets(self, "LinkNode")
        self.use_custom_color = True
        self.color = (0.7, 0.7, 0.3)  # Giallo

    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)

        if s3d_node:
            col = layout.column(align=True)
            col.label(text="Link", icon='URL')

            if hasattr(s3d_node, 'url') and s3d_node.url:
                col.label(text=s3d_node.url[:25])

# ============================================================================
# RIGHTS NODES
# ============================================================================

class EMGraphAuthorNode(EMGraphNodeBase):
    """Wrapper per AuthorNode"""
    bl_idname = 'EMGraphAuthorNodeType'
    bl_label = 'Author'
    bl_icon = 'USER'

    def init(self, context):
        # ✅ Socket dinamici per AuthorNode
        generate_sockets(self, "AuthorNode")
        self.use_custom_color = True
        self.color = (0.8, 0.5, 0.3)  # Arancione scuro

    def draw_buttons(self, context, layout):
        s3d_node = self.get_s3d_node(context)

        if s3d_node:
            col = layout.column(align=True)
            col.label(text="Author", icon='USER')

            if self.original_name:
                col.label(text=self.original_name[:20])

# ============================================================================
# REGISTRATION
# ============================================================================

classes = (
    # Stratigraphic nodes - Base types
    EMGraphUSNode,
    EMGraphUSVsNode,
    EMGraphUSVnNode,
    EMGraphSFNode,
    EMGraphVSFNode,
    EMGraphUSDNode,

    # Stratigraphic nodes - Series and special types
    EMGraphSerSUNode,
    EMGraphSerUSDNode,
    EMGraphSerUSVsNode,
    EMGraphSerUSVnNode,
    EMGraphTSUNode,
    EMGraphULNode,
    EMGraphBRNode,
    EMGraphSENode,

    # Temporal nodes
    EMGraphEpochNode,

    # Paradata nodes
    EMGraphPropertyNode,
    EMGraphExtractorNode,
    EMGraphCombinerNode,
    EMGraphDocumentNode,

    # Group nodes
    EMGraphActivityNodeGroup,
    EMGraphParadataGroupNode,
    EMGraphTimeBranchNode,

    # Visualization nodes
    EMGraphRepresentationNode,
    EMGraphRepresentationDocNode,
    EMGraphRepresentationSFNode,
    EMGraphSemanticShapeNode,

    # Reference nodes
    EMGraphGeoPositionNode,
    EMGraphLinkNode,

    # Rights nodes
    EMGraphAuthorNode,
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