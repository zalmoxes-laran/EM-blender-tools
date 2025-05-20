import json
import os
from typing import List, Dict, Any, Optional
from ..graph import Graph
from ..multigraph.multigraph import get_all_graph_ids, get_graph

class JSONExporter:
    """
    Export s3Dgraphy graphs to JSON format.
    Supports exporting single graphs or multiple graphs with context.
    """
    
    def __init__(self, output_path: str):
        """
        Initialize the JSON exporter.
        
        Args:
            output_path (str): Path where the JSON file will be saved
        """
        self.output_path = output_path
        self.context = self._init_context()
        
    def _init_context(self) -> Dict[str, Any]:
        """Initialize the context section with default time Epochs."""
        return {
            "absolute_time_Epochs": {
                "roman_kingdom": {
                    "name": "Epoca regia romana",
                    "start": -753,
                    "end": -509,
                    "color": "#FFD700"
                },
                "roman_republic": {
                    "name": "Epoca repubblicana romana",
                    "start": -509,
                    "end": -27,
                    "color": "#CD5C5C"
                },
                "roman_empire": {
                    "name": "Epoca imperiale romana",
                    "start": -27,
                    "end": 476,
                    "color": "#800020"
                },
                "early_middle_ages": {
                    "name": "Alto Medioevo",
                    "start": 476,
                    "end": 1000,
                    "color": "#4B0082"
                }
            }
        }



    def export_graphs(self, graph_ids: Optional[List[str]] = None) -> None:
        """
        Export specified graphs to JSON. If no graph_ids provided, exports all graphs.
        
        Args:
            graph_ids (List[str], optional): List of graph IDs to export. Defaults to None.
        """
        if graph_ids is None:
            graph_ids = get_all_graph_ids()
                
        export_data = {
            "version": "1.5",
            "graphs": {}
        }
            
        for graph_id in graph_ids:
            graph = get_graph(graph_id)
            if graph and hasattr(graph, 'graph_id'):
                # Usa l'ID effettivo del grafo come chiave
                actual_id = graph.graph_id  # 
                print(f"Exporting graph with ID: {actual_id}")
                export_data["graphs"][actual_id] = self._process_graph(graph)
                
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=4, ensure_ascii=False)

    def _process_graph(self, graph: Graph) -> Dict[str, Any]:
        """Process a single graph into its JSON representation."""
        
        print(f"\nProcessing graph for JSON export:")
        print(f"Graph name: {graph.name}")
        print(f"Graph description: {graph.description}")
        print(f"Graph data: {graph.data}")

        # Raccogli gli ID degli autori dal grafo
        authors = graph.data.get('authors', [])
        if not authors:
            # Se non ci sono autori in graph.data, cerca negli edges
            for edge in graph.edges:
                if edge.edge_type in ['has_author', 'generic_connection']:
                    if edge.edge_target == graph.graph_id:
                        author_node = graph.find_node_by_id(edge.edge_source)
                        if author_node and author_node.node_type == 'author':
                            authors.append(edge.edge_source)
                            print(f"Found author from edge: {edge.edge_source}")

        result = {
            "name": graph.name.get('default', ''),
            "description": graph.description.get('default', ''),
            "defaults": {
                "license": graph.data.get('license', 'CC-BY-NC-ND'),
                "authors": authors,
                "embargo_until": graph.data.get('embargo_until'),
                "panorama": graph.data.get('panorama', 'panorama/defsky.jpg')
            },
            "nodes": self._process_nodes(graph),
            "edges": self._process_edges(graph)
        }
        
        print(f"\nJSON output for graph metadata:")
        print(f"Name: {result['name']}")
        print(f"Description: {result['description']}")
        print(f"Defaults: {result['defaults']}")
        
        return result

        
    def _process_nodes(self, graph: Graph) -> Dict[str, Dict[str, Any]]:
        """Process all nodes in the graph, organizing them by type."""
        nodes = {
            "authors": {},
            "stratigraphic": {"US": {}, "USVs": {}, "SF": {}, "VSF": {},"USVn": {}, "USD": {}, "serSU": {}, "serUSVn": {}, "serUSVs": {}, "TSU": {}, "SE": {}, "unknown": {}},
            "epochs": {},
            "groups": {},
            "properties": {},
            "documents": {},
            "extractors": {},
            "combiners": {},
            "links": {},
            "geo": {},
            "semantic_shapes": {},      
            "representation_models": {},
            "representation_model_doc": {},
            "representation_model_sf": {}
        }
        
        # Prima fase: elabora tutti i nodi ed edge del grafo
        rm_links = {}  # Dizionario per memorizzare relazioni RM -> Link
        
        # Raccogli prima tutte le relazioni has_linked_resource
        for edge in graph.edges:
            if edge.edge_type == "has_linked_resource":
                source_node = graph.find_node_by_id(edge.edge_source)
                target_node = graph.find_node_by_id(edge.edge_target)
                
                if source_node and target_node and target_node.node_type == "link":
                    if source_node.node_id not in rm_links:
                        rm_links[source_node.node_id] = []
                    
                    rm_links[source_node.node_id].append({
                        "link_id": target_node.node_id,
                        "url": target_node.data.get("url", "") if hasattr(target_node, "data") else "",
                        "url_type": target_node.data.get("url_type", "") if hasattr(target_node, "data") else ""
                    })
                    print(f"Found link relationship: {source_node.node_id} -> {target_node.node_id}")
        
        # Ora elabora tutti i nodi
        for node in graph.nodes:
            # Gestisci ogni tipo di nodo in modo specifico
            if node.node_type == "author":
                node_data = self._prepare_node_data(node)
                nodes["authors"][node.node_id] = node_data
                
            elif node.node_type in ["US", "USVs", "SF", "USVn", "USD", "VSF", "serSU", "serUSVn", "serUSVs", "TSU", "SE", "unknown"]:
                node_data = self._prepare_node_data(node)
                nodes["stratigraphic"][node.node_type][node.node_id] = node_data
                
            elif node.node_type == "epoch":
                node_data = {
                    "type": node.node_type,
                    "name": node.name,
                    "description": node.description,
                    "data": {
                        "start_time": node.start_time if hasattr(node, 'start_time') else None,
                        "end_time": node.end_time if hasattr(node, 'end_time') else None,
                        "color": node.color if hasattr(node, 'color') else None,
                        "min_y": node.min_y if hasattr(node, 'min_y') else None,
                        "max_y": node.max_y if hasattr(node, 'max_y') else None
                    }
                }
                nodes["epochs"][node.node_id] = node_data
                
            elif node.node_type in ["ActivityNodeGroup", "TimeBranchNodeGroup", "ParadataNodeGroup"]:
                node_data = self._prepare_node_data(node)
                nodes["groups"][node.node_id] = node_data
                
            elif node.node_type == "property":
                node_data = self._prepare_node_data(node)
                nodes["properties"][node.node_id] = node_data
                
            elif node.node_type == "document":
                node_data = self._prepare_node_data(node)
                nodes["documents"][node.node_id] = node_data
                
            elif node.node_type == "extractor":
                node_data = self._prepare_node_data(node)
                nodes["extractors"][node.node_id] = node_data
                
            elif node.node_type == "combiner":
                node_data = self._prepare_node_data(node)
                nodes["combiners"][node.node_id] = node_data
                
            elif node.node_type == "link":
                node_data = self._prepare_node_data(node)
                nodes["links"][node.node_id] = node_data
                print(f"Added link node to JSON: {node.node_id}")
                
            elif node.node_type == "geo_position":
                node_data = self._prepare_node_data(node)
                nodes["geo"][node.node_id] = node_data
                
            elif node.node_type == "semantic_shape":
                node_data = self._prepare_node_data(node)
                nodes["semantic_shapes"][node.node_id] = node_data
                
            elif node.node_type == "representation_model":
                # Prepara i dati del nodo senza includere l'URL
                node_data = {
                    "type": node.node_type,
                    "name": node.name,
                    "description": node.description,
                    "data": {}
                }
                
                # Copia tutti gli attributi tranne URL
                if hasattr(node, 'data') and isinstance(node.data, dict):
                    for key, value in node.data.items():
                        if key != 'url':  # Escludiamo url
                            node_data['data'][key] = value
                
                nodes["representation_models"][node.node_id] = node_data

            elif node.node_type == "representation_model_doc":
                # Prepare the node data similar to other types
                node_data = self._prepare_node_data(node)
                
                # Add the node to the collection
                nodes["representation_model_doc"][node.node_id] = node_data

            elif node.node_type == "representation_model_sf":
                # Prepare the node data similar to other types
                node_data = self._prepare_node_data(node)
                
                # Add the node to the collection
                nodes["representation_model_sf"][node.node_id] = node_data

        return nodes

    def _prepare_node_data(self, node):
        """Helper method to prepare standard node data."""
        node_data = {
            "type": node.node_type,
            "name": node.name,
            "description": node.description,
            "data": node.data.copy() if hasattr(node, 'data') else {}
        }
        return node_data
        
    def _process_edges(self, graph: Graph) -> Dict[str, List[Dict[str, Any]]]:
        """Process all edges in the graph, organizing them by type."""
        edges = {
            "is_before": [],
            "has_same_time": [],
            "changed_from": [],
            "has_data_provenance": [],
            "has_author": [],
            "contrasts_with": [],
            "has_first_epoch": [],
            "survive_in_epoch": [],
            "is_in_activity": [],
            "has_property": [],
            "has_timebranch": [],
            "is_in_timebranch": [],
            "extracted_from": [],
            "combines": [],
            "has_linked_resource": [],
            "is_in_paradata_nodegroup": [],
            "has_paradata_nodegroup": [],
            "has_semantic_shape": [],
            "has_representation_model": [],
            "generic_connection": []            
        }
        
        for edge in graph.edges:
            edge_data = {
                "id": edge.edge_id,
                "from": edge.edge_source,
                "to": edge.edge_target
            }
            
            # Add edge to appropriate category
            if edge.edge_type in edges:
                edges[edge.edge_type].append(edge_data)
            else:
                edges["generic_connection"].append(edge_data)
                
        return edges


def export_to_json(output_path: str, graph_ids: Optional[List[str]] = None) -> None:
    """
    Convenience function to export graphs to JSON.
    
    Args:
        output_path (str): Path where to save the JSON file
        graph_ids (List[str], optional): List of graph IDs to export. If None, exports all graphs.
    """
    exporter = JSONExporter(output_path)
    exporter.export_graphs(graph_ids)
