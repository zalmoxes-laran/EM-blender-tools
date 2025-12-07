"""
Data structures for Graph Viewer
Contains Node Tree, Socket types, and property groups.
"""

import bpy
from bpy.types import NodeTree, NodeSocket
from bpy.props import StringProperty, FloatProperty, FloatVectorProperty, IntProperty

# ============================================================================
# SOCKET TYPES
# ============================================================================

class EMGraphSocket(NodeSocket):
    """Socket personalizzato per connessioni tra nodi del grafo"""
    bl_idname = 'EMGraphSocketType'
    bl_label = 'EMGraph Socket'
    
    # Colore personalizzabile per il socket
    socket_color: FloatVectorProperty(
        name="Socket Color",
        subtype='COLOR',
        default=(0.5, 0.5, 0.5, 1.0),
        size=4,
        min=0.0,
        max=1.0
    )
    
    # Tipo di edge rappresentato
    edge_type: StringProperty(
        name="Edge Type",
        default=""
    )
    
    def draw(self, context, layout, node, text):
        layout.label(text=text)
    
    def draw_color(self, context, node):
        """Ritorna il colore del socket basato sul tipo di edge"""
        if self.socket_color[3] > 0:  # Se ha un colore personalizzato
            return tuple(self.socket_color)
        
        # Altrimenti usa colori di default basati sul nome
        socket_name = self.name.lower()
        
        if "stratigraphic" in socket_name or "before" in socket_name or "after" in socket_name:
            return (0.8, 0.4, 0.2, 1.0)  # Arancione per relazioni stratigrafiche
        elif "EpochNode" in socket_name or "survive" in socket_name:
            return (0.3, 0.6, 0.9, 1.0)  # Blu per epoche
        elif "paradata" in socket_name or "property" in socket_name:
            return (0.6, 0.3, 0.8, 1.0)  # Viola per paradata
        elif "document" in socket_name or "link" in socket_name:
            return (0.8, 0.8, 0.4, 1.0)  # Giallo per documenti
        elif "representation" in socket_name or "model" in socket_name:
            return (0.4, 0.8, 0.6, 1.0)  # Verde per rappresentazioni
        elif "group" in socket_name or "member" in socket_name:
            return (0.5, 0.7, 0.5, 1.0)  # Verde chiaro per gruppi
        else:
            return (0.5, 0.5, 0.5, 1.0)  # Grigio di default

# ============================================================================
# NODE TREE
# ============================================================================

class EMGraphNodeTree(NodeTree):
    """Node tree per EMGraph editor"""
    bl_idname = 'EMGraphNodeTreeType'
    bl_label = 'EMGraph'
    bl_icon = 'OUTLINER_OB_MESH'
    
    # Proprietà per tracking del grafo
    graph_id: StringProperty(
        name="Graph ID",
        description="ID del grafo s3dgraphy rappresentato",
        default=""
    )
    
    graph_name: StringProperty(
        name="Graph Name",
        description="Nome del grafo",
        default=""
    )
    
    last_update: FloatProperty(
        name="Last Update",
        description="Timestamp dell'ultimo aggiornamento",
        default=0.0
    )
    
    node_count: IntProperty(
        name="Node Count",
        description="Numero di nodi nel grafo",
        default=0
    )
    
    edge_count: IntProperty(
        name="Edge Count",
        description="Numero di collegamenti nel grafo",
        default=0
    )
    
    # Colori globali personalizzabili
    default_us_color: FloatVectorProperty(
        name="US Color",
        subtype='COLOR',
        default=(0.608, 0.608, 0.608),
        min=0.0,
        max=1.0
    )
    
    default_usvs_color: FloatVectorProperty(
        name="USVs Color",
        subtype='COLOR',
        default=(0.4, 0.6, 0.8),
        min=0.0,
        max=1.0
    )
    
    default_usvn_color: FloatVectorProperty(
        name="USVn Color",
        subtype='COLOR',
        default=(0.8, 0.6, 0.4),
        min=0.0,
        max=1.0
    )
    
    default_epoch_color: FloatVectorProperty(
        name="Epoch Color",
        subtype='COLOR',
        default=(0.3, 0.5, 0.7),
        min=0.0,
        max=1.0
    )
    
    default_document_color: FloatVectorProperty(
        name="Document Color",
        subtype='COLOR',
        default=(0.8, 0.8, 0.4),
        min=0.0,
        max=1.0
    )
    
    default_paradata_color: FloatVectorProperty(
        name="Paradata Color",
        subtype='COLOR',
        default=(0.6, 0.3, 0.8),
        min=0.0,
        max=1.0
    )

# ============================================================================
# REGISTRATION
# ============================================================================

classes = (
    EMGraphSocket,
    EMGraphNodeTree,
)

def register_data():
    """Register data classes"""
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Already registered
            pass

def unregister_data():
    """Unregister data classes"""
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            # Not registered
            pass