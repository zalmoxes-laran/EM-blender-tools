# EMtools/graph2geometry.py
import bpy # type: ignore
#from .graph_manager import graph_instance
from .external_modules_install import check_external_modules, install_modules
import logging

from .S3Dgraphy.multigraph import load_graph, get_graph

log = logging.getLogger(__name__)

def create_geometry_from_graph(graph, context):
    """
    Crea geometrie in Blender a partire dal grafo dato.
    Crea sfere per ciascun nodo e linee rosse per ciascun arco.
    
    :param graph: Un'istanza della classe Graph contenente nodi e archi.
    :param context: Il contesto di Blender.
    """
    # Importa generate_layout solo se networkx è disponibile
    from .S3Dgraphy.visual_layout import generate_layout

    # Genera il layout per i nodi del grafo
    layout = generate_layout(graph)
    
    # Scala per aumentare la distanza tra i nodi
    scale_factor = 10.0
    layout = {node_id: (x * scale_factor, y * scale_factor) for node_id, (x, y) in layout.items()}

    # Crea una collection chiamata "visual_graph" per contenere tutti gli oggetti
    collection_name = "visual_graph"
    if collection_name in bpy.data.collections:
        collection = bpy.data.collections[collection_name]
    else:
        collection = bpy.data.collections.new(collection_name)
        context.scene.collection.children.link(collection)
    
    # Dizionario per tenere traccia degli oggetti sfera creati per ciascun nodo
    node_objects = {}
    
    # Crea una sfera per ogni nodo
    for node_id, (x, y) in layout.items():
        node = graph.find_node_by_id(node_id)
        if node:
            # Aggiungi una sfera nella posizione specificata
            with context.temp_override(area=context.area):
                bpy.ops.mesh.primitive_uv_sphere_add(radius=0.005, location=(x, y, 0))
                sphere = bpy.context.object
                sphere.name = "node_" + node.name
                collection.objects.link(sphere)
                node_objects[node_id] = sphere
    
    # Crea una linea rossa per ogni arco
    for edge in graph.edges:
        source_node = node_objects.get(edge.edge_source)
        target_node = node_objects.get(edge.edge_target)
        if source_node and target_node:
            # Crea una mesh per rappresentare la linea
            curve_data = bpy.data.curves.new(name=f"Curve_{edge.edge_id}", type='CURVE')
            curve_data.dimensions = '3D'
            
            polyline = curve_data.splines.new('POLY')
            polyline.points.add(1)
            polyline.points[0].co = (*source_node.location, 1)
            polyline.points[1].co = (*target_node.location, 1)
            
            curve_obj = bpy.data.objects.new(f"Edge_{edge.edge_id}", curve_data)
            collection.objects.link(curve_obj)
            
            # Imposta il materiale rosso per la linea
            mat = bpy.data.materials.new(name="Red_Material")
            mat.diffuse_color = (1, 0, 0, 1)  # Rosso
            curve_obj.data.materials.append(mat)


# Operatore per Blender
class OBJECT_OT_CreateGraphGeometry(bpy.types.Operator):
    bl_idname = "object.create_graph_geometry"
    bl_label = "Crea Geometrie dal Grafo"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        is_active_button = False
        prefs = context.preferences.addons.get(__package__, None)
        return prefs.preferences.is_external_module

    def execute(self, context):
        graph_instance = get_graph()

        if graph_instance is None:
            self.report({'ERROR'}, "Nessun grafo caricato. Carica un grafo prima di eseguire l'operatore.")
            return {'CANCELLED'}
        
        # Assicurati che il contesto sia VIEW_3D per l'esecuzione dell'operatore
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                with context.temp_override(area=area):
                    create_geometry_from_graph(graph_instance, context)
                    return {'FINISHED'}
        
        self.report({'ERROR'}, "Nessuna area VIEW_3D disponibile per creare la geometria.")
        return {'CANCELLED'}

# Registra l'operatore in Blender
def register():
    bpy.utils.register_class(OBJECT_OT_CreateGraphGeometry)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_CreateGraphGeometry)

if __name__ == "__main__":
    register()