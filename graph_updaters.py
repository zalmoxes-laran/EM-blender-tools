import bpy # type: ignore
from s3dgraphy import get_graph, get_all_graph_ids
from s3dgraphy.nodes.semantic_shape_node import SemanticShapeNode
from s3dgraphy.nodes.representation_node import RepresentationModelNode, RepresentationModelDocNode
from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
from s3dgraphy.nodes.document_node import DocumentNode
import os
import uuid
import math

def update_graph_with_scene_data(graph_id=None, update_all_graphs=False, context=None):
    """
    Updates the graph(s) with current scene data.
    Considera solo i grafi pubblicabili se update_all_graphs è True.
    
    Args:
        graph_id (str, optional): ID of specific graph to update
        update_all_graphs (bool): If True, updates all publishable loaded graphs
        context: Blender context (needed for checking publishable status)
        
    Returns:
        bool: True if update was successful
    """
    if update_all_graphs:
        # Aggiorna tutti i grafi pubblicabili
        try:
            if context:
                # Usa la lista di EM_setup per verificare quali sono pubblicabili
                em_tools = context.scene.em_tools
                published_graph_ids = []
                
                for graphml_item in em_tools.graphml_files:
                    is_publishable = getattr(graphml_item, 'is_publishable', True)
                    if is_publishable:
                        published_graph_ids.append(graphml_item.name)
                
                print(f"Updating {len(published_graph_ids)} publishable graphs with scene data")
            else:
                # Fallback: aggiorna tutti i grafi se context non disponibile
                published_graph_ids = get_all_graph_ids()
                print(f"Updating {len(published_graph_ids)} graphs with scene data (context unavailable)")
            
            if not published_graph_ids:
                print("No publishable graphs available to update")
                return False
            
            updated_count = 0
            for gid in published_graph_ids:
                graph = get_graph(gid)
                if graph:
                    try:
                        update_semantic_shapes(graph)
                        update_representation_models(graph)
                        update_representation_model_docs(graph)
                        updated_count += 1
                        print(f"Updated graph: {gid}")
                    except Exception as e:
                        print(f"Error updating graph {gid}: {e}")
                else:
                    print(f"Could not retrieve graph: {gid}")
            
            print(f"Successfully updated {updated_count}/{len(published_graph_ids)} publishable graphs")
            return updated_count > 0
            
        except Exception as e:
            print(f"Error updating graphs: {e}")
            return False
    else:
        # Comportamento originale per un grafo specifico
        try:
            graph = get_graph(graph_id)
            if not graph:
                print("No graph available to update")
                return False
                
            update_semantic_shapes(graph)
            update_representation_models(graph)
            update_representation_model_docs(graph)
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
        # Try exact match first
        matching_proxy = next((obj for obj in mesh_objects
                             if obj.name == strat_node.name), None)

        # If not found, try finding object with name ending with ".{stratigraphic_name}"
        # This handles cases where proxy has graph prefix (e.g., "DEMO25.US02")
        if not matching_proxy:
            suffix = f".{strat_node.name}"
            matching_proxy = next((obj for obj in mesh_objects
                                 if obj.name.endswith(suffix)), None)

        if matching_proxy:
            shape_node_name = f"{strat_node.name}_shape"
            shape_node = graph.find_node_by_id(shape_node_name)
            print(f'Try to create node semantic {shape_node_name} for proxy {matching_proxy.name}')
            if not shape_node:
                # Use stratigraphic name (without prefix) for the GLB filename
                shape_node = SemanticShapeNode(
                    node_id= shape_node_name,
                    name=f"Shape for {strat_node.name}",
                    type="proxy",
                    url=f"proxies/{strat_node.name}.glb"  # Use strat name, not proxy name
                )
                print(f'Created node semantic {shape_node_name}')
                graph.add_node(shape_node)
                nodes_added += 1
            else:
                # Update URL to use stratigraphic name (without prefix)
                shape_node.url = f"proxies/{strat_node.name}.glb"
                shape_node.set_url(f"proxies/{strat_node.name}.glb")
            
            #edge_id = str(uuid.uuid4())#f"{strat_node.node_id}_has_shape_{shape_node_name}"
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

    # Cerca sia oggetti mesh che oggetti vuoti con tileset_path
    objects_to_check = [
        obj for obj in bpy.data.objects
        if (obj.type == 'MESH' and len(obj.EM_ep_belong_ob) > 0) or
           ("tileset_path" in obj and obj.get("tileset_path"))
    ]

    # ✅ OPTIMIZATION: Pre-build epoch lookup dict to avoid O(n²) nested loop
    # Build once: O(n), then lookup is O(1) per RM object
    epoch_nodes_by_name = {}
    for node in graph.indices.nodes_by_type.get('EpochNode', []):
        if hasattr(node, 'name'):
            epoch_nodes_by_name[node.name] = node

    nodes_added = 0
    edges_added = 0

    for obj in objects_to_check:
        print(f'Object RM is {obj.name}')
        #model_node_id = str(uuid.uuid4())#f"{obj.name}_model"
        model_node_id = f"{obj.name}_model"
        model_node = graph.find_node_by_id(model_node_id)
        
        # Determina il tipo di URL e il tipo di rappresentazione
        if "tileset_path" in obj:
            # Per i tilesets
            tileset_filename = os.path.basename(obj["tileset_path"])
            tileset_name = os.path.splitext(tileset_filename)[0]
            url = f"tilesets/{tileset_name}/tileset.json"
            model_type = "RM"
            is_tileset = True
        else:
            # Per le mesh normali
            url = f"models/{obj.name}.gltf"
            model_type = "RM"
            is_tileset = False
        
        if not model_node:
            model_node = RepresentationModelNode(
                node_id=model_node_id,
                name=f"Model for {obj.name}",
                type=model_type,
                #url=url
            )
            
            # Aggiungi attributi per i tilesets
            model_node.attributes['is_tileset'] = is_tileset
            if is_tileset:
                model_node.attributes['tileset_path'] = obj["tileset_path"]
            
            graph.add_node(model_node)
            nodes_added += 1
        
        # Gestisci le epoche usando pre-built lookup dict
        for ep in obj.EM_ep_belong_ob:
            if ep.epoch != "no_epoch":
                # ✅ OPTIMIZATION: O(1) dict lookup instead of O(n) iteration
                epoch_node = epoch_nodes_by_name.get(ep.epoch)

                if epoch_node:
                    edge_id = f"{epoch_node.node_id}_has_representation_model_{model_node_id}"
                    if not graph.find_edge_by_id(edge_id):
                        graph.add_edge(
                            edge_id=edge_id,
                            #edge_source=model_node_id,
                            #edge_target=epoch_node.node_id,
                            edge_source=epoch_node.node_id,
                            edge_target=model_node_id,
                            edge_type="has_representation_model"
                        )
                        edges_added += 1
                else:
                    print(f"Warning: No epoch node found for {ep.epoch}")
    
    print(f"Added {nodes_added} representation model nodes")
    print(f"Added {edges_added} representation model edges")


def update_representation_model_docs(graph):
    """
    Updates representation model doc nodes in the graph based on scene objects.

    Looks for Blender plane objects or empties that represent documents in 3D space.
    These are identified by a custom property 'em_doc_node_id' pointing to a DocumentNode.

    For each matching object, creates or updates a RepresentationModelDocNode with:
    - Transform (position, rotation, scale) from the Blender object
    - Quad dimensions (width, height) from the mesh bounding box
    - Whether dimensions are real or symbolic
    - Camera reference if a child camera exists
    """
    print("\n--- Updating Representation Model Docs ---")

    document_nodes = [node for node in graph.nodes
                      if isinstance(node, DocumentNode)]

    if not document_nodes:
        print("No document nodes in graph, skipping RM doc update")
        return

    # Find scene objects tagged as document representations
    doc_objects = [obj for obj in bpy.data.objects
                   if obj.get('em_doc_node_id')]

    nodes_added = 0
    nodes_updated = 0
    edges_added = 0

    for obj in doc_objects:
        doc_node_id = obj.get('em_doc_node_id')
        doc_node = graph.find_node_by_id(doc_node_id)
        if not doc_node or not isinstance(doc_node, DocumentNode):
            print(f"Warning: Object '{obj.name}' references unknown document node '{doc_node_id}'")
            continue

        rm_doc_id = f"{doc_node_id}_rm_doc"
        rm_doc_node = graph.find_node_by_id(rm_doc_id)

        # Extract transform from Blender object
        loc = obj.location
        rot = obj.rotation_euler
        scale = obj.scale
        transform = {
            "position": [str(loc.x), str(loc.y), str(loc.z)],
            "rotation": [str(rot.x), str(rot.y), str(rot.z)],
            "scale": [str(scale.x), str(scale.y), str(scale.z)],
        }

        # Extract quad dimensions from bounding box
        if obj.type == 'MESH' and obj.data:
            bb = obj.bound_box
            # Compute width and height from bounding box in local space
            xs = [v[0] for v in bb]
            ys = [v[1] for v in bb]
            zs = [v[2] for v in bb]
            quad_width = (max(xs) - min(xs)) * scale.x
            quad_height = (max(ys) - min(ys)) * scale.y
            if quad_height < 0.001:
                # Try Z axis if Y is flat (vertical plane)
                quad_height = (max(zs) - min(zs)) * scale.z
        else:
            quad_width = 1.0
            quad_height = 1.0

        dimensions_type = obj.get('em_dimensions_type', 'symbolic')

        # Find associated camera (child camera or named camera)
        camera_name = obj.get('em_camera_name', '')
        if not camera_name:
            # Look for a child camera
            for child in obj.children:
                if child.type == 'CAMERA':
                    camera_name = child.name
                    break

        # Determine representation type
        rm_type = "spatialized_image" if camera_name else "RM"

        if not rm_doc_node:
            rm_doc_node = RepresentationModelDocNode(
                node_id=rm_doc_id,
                name=f"RM Doc for {doc_node.name}",
                type=rm_type,
                transform=transform,
                description=f"Document representation: {doc_node.name}"
            )
            # Store extended spatial metadata in data dict
            rm_doc_node.data['quad_width'] = quad_width
            rm_doc_node.data['quad_height'] = quad_height
            rm_doc_node.data['dimensions_type'] = dimensions_type
            rm_doc_node.data['camera_name'] = camera_name
            rm_doc_node.data['blender_object'] = obj.name

            graph.add_node(rm_doc_node)
            nodes_added += 1
        else:
            # Update existing node
            rm_doc_node.transform = transform
            rm_doc_node.data['quad_width'] = quad_width
            rm_doc_node.data['quad_height'] = quad_height
            rm_doc_node.data['dimensions_type'] = dimensions_type
            rm_doc_node.data['camera_name'] = camera_name
            rm_doc_node.data['blender_object'] = obj.name
            nodes_updated += 1

        # Create edge: document -> rm_doc
        edge_id = f"{doc_node_id}_has_rm_doc_{rm_doc_id}"
        if not graph.find_edge_by_id(edge_id):
            try:
                graph.add_edge(
                    edge_id=edge_id,
                    edge_source=doc_node_id,
                    edge_target=rm_doc_id,
                    edge_type="has_representation_model_doc"
                )
                edges_added += 1
            except Exception as e:
                print(f"Error creating RM doc edge: {e}")

    print(f"RM Docs: added {nodes_added}, updated {nodes_updated}, edges added {edges_added}")