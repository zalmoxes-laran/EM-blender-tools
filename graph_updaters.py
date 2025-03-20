import bpy
from .s3Dgraphy import get_graph
from .s3Dgraphy.nodes.semantic_shape_node import SemanticShapeNode
from .s3Dgraphy.nodes.representation_model_node import RepresentationModelNode
from .s3Dgraphy.nodes.stratigraphic_node import StratigraphicNode


def update_graph_with_scene_data(graph_id=None):
    """
    Updates the graph with current scene data.
    
    Args:
        graph_id (str, optional): ID of the graph to update. 
            If None and only one graph exists, uses that graph.
            If None and multiple graphs exist, raises an error.
    
    Returns:
        bool: True if update was successful
        
    Raises:
        ValueError: If no graph_id is provided and multiple graphs exist
    """
    try:
        graph = get_graph(graph_id)
        if not graph:
            print("No graph available to update")
            return False
            
        update_semantic_shapes(graph)
        update_representation_models(graph)
        return True
        
    except ValueError as e:
        print(f"Error getting graph: {e}")
        return False

def update_semantic_shapes(graph):
    """Updates semantic shape nodes in the graph based on scene proxies."""
    print("\n--- Updating Semantic Shapes ---")
    
    stratigraphic_nodes = [node for node in graph.nodes 
                          if isinstance(node, StratigraphicNode)]
    mesh_objects = [obj for obj in bpy.data.objects 
                   if obj.type == 'MESH']
    
    nodes_added = 0
    edges_added = 0
    
    for strat_node in stratigraphic_nodes:
        matching_proxy = next((obj for obj in mesh_objects 
                             if obj.name == strat_node.name), None)
        
        if matching_proxy:
            shape_node_name = f"{strat_node.name}_shape"
            shape_node = graph.find_node_by_id(shape_node_name)
            print(f'Try to create node semantic {shape_node_name}')
            if not shape_node:
                shape_node = SemanticShapeNode(
                    node_id=shape_node_name,
                    name=f"Shape for {strat_node.name}",
                    type="proxy",
                    url=f"proxies/{matching_proxy.name}.glb"
                )
                print(f'Created node semantic {shape_node_name}')
                graph.add_node(shape_node)
                nodes_added += 1
            else:
                shape_node.url = f"proxies/{matching_proxy.name}.glb"
            
            edge_id = f"{strat_node.node_id}_has_shape_{shape_node_name}"
            if not graph.find_edge_by_id(edge_id):
                graph.add_edge(
                    edge_id=edge_id,
                    edge_source=strat_node.node_id,
                    edge_target=shape_node_name,
                    edge_type="has_semantic_shape"
                )
                edges_added += 1
    
    print(f"Added {nodes_added} semantic shape nodes and {edges_added} edges")

def update_representation_models(graph):
    """Updates representation model nodes in the graph based on scene objects."""
    print("\n--- Updating Representation Models ---")
    
    mesh_objects = [obj for obj in bpy.data.objects 
                   if obj.type == 'MESH' and len(obj.EM_ep_belong_ob) > 0]
    
    nodes_added = 0
    edges_added = 0
    
    for obj in mesh_objects:
        print(f'Mesh object RM is {obj.name}')
        model_node_id = f"{obj.name}_model"
        model_node = graph.find_node_by_id(model_node_id)
        
        if not model_node:
            model_node = RepresentationModelNode(
                node_id=model_node_id,
                name=f"Model for {obj.name}",
                type="RM",
                url=f"models/{obj.name}.gltf"
            )
            # Aggiungi l'attributo is_publishable come default
            model_node.attributes['is_publishable'] = True
            graph.add_node(model_node)
            nodes_added += 1
        else:
            model_node.url = f"models/{obj.name}.gltf"
            # Assicurati che ci sia l'attributo is_publishable
            if 'is_publishable' not in model_node.attributes:
                model_node.attributes['is_publishable'] = True
        
        for epoch_prop in obj.EM_ep_belong_ob:
            # Salta le entry "no_epoch" per gli edges (le manteniamo solo come marker)
            if epoch_prop.epoch == "no_epoch":
                continue
                
            epoch_node = next((node for node in graph.nodes 
                             if node.node_type == "epoch" and 
                             node.name == epoch_prop.epoch), None)
            
            if epoch_node:
                edge_id = f"{model_node_id}_has_representation_model_{epoch_node.node_id}"
                if not graph.find_edge_by_id(edge_id):
                    graph.add_edge(
                        edge_id=edge_id,
                        edge_source=model_node_id,
                        edge_target=epoch_node.node_id,
                        edge_type="has_representation_model"
                    )
                    edges_added += 1
    
    print(f"Added {nodes_added} representation model nodes and {edges_added} edges")


