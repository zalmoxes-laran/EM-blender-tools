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
        """Initialize the context section with default time periods."""
        return {
            "absolute_time_periods": {
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
                "embargo_until": graph.data.get('embargo_until')
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
            "stratigraphic": {"US": {}, "USVs": {}, "SF": {}, "USVn": {}, "USD": {}},
            "epochs": {},
            "groups": {},
            "properties": {},
            "documents": {},
            "extractors": {},
            "combiners": {},
            "links": {},
            "geo": {}
        }
        
        for node in graph.nodes:
            node_data = {
                "type": node.node_type,
                "name": node.name,
                "description": node.description,
                "data": node.attributes.copy()
            }
            
            # Add node to appropriate category
            if node.node_type == "author":
                nodes["authors"][node.node_id] = node_data
            elif node.node_type in ["US", "USVs", "SF", "USVn", "USD"]:
                nodes["stratigraphic"][node.node_type][node.node_id] = node_data
            elif node.node_type == "epoch":
                node_data = {
                    "type": node.node_type,
                    "name": node.name,
                    "description": node.description,
                    "data": {
                        "start_time": node.start_time,  # Aggiungo il valore start_time
                        "end_time": node.end_time,      # Aggiungo il valore end_time
                        "color": node.color if hasattr(node, 'color') else None,
                        "min_y": node.min_y if hasattr(node, 'min_y') else None,
                        "max_y": node.max_y if hasattr(node, 'max_y') else None
                    }
                }
                nodes["epochs"][node.node_id] = node_data
            elif node.node_type in ["ActivityNodeGroup", "TimeBranchNodeGroup", "ParadataNodeGroup"]:
                nodes["groups"][node.node_id] = node_data
            elif node.node_type == "property":
                nodes["properties"][node.node_id] = node_data
            elif node.node_type == "document":
                nodes["documents"][node.node_id] = node_data
            elif node.node_type == "extractor":
                nodes["extractors"][node.node_id] = node_data
            elif node.node_type == "combiner":
                nodes["combiners"][node.node_id] = node_data
            elif node.node_type == "link":
                nodes["links"][node.node_id] = node_data
            elif node.node_type == "geo_position":
                nodes["geo"][node.node_id] = node_data
                
        return nodes
        
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
            "has_activity": [],
            "has_property": [],
            "has_timebranch": [],
            "has_linked_resource": [],
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
