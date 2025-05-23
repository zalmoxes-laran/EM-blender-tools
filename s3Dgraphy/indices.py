# Nuovo file: s3Dgraphy/indices.py

class GraphIndices:
    """Indexing system for efficient graph queries"""
    
    def __init__(self):
        self.clear()
    
    def clear(self):
        """Cleans all indexes"""
        # Nodi per tipo
        self.nodes_by_type = {}
        
        # Property nodes
        self.property_nodes_by_name = {}
        self.property_values_by_name = {}  # {prop_name: set(values)}
        
        # Relazioni stratigrafiche-proprietà
        self.strat_to_properties = {}  # {strat_id: {prop_name: value}}
        self.properties_to_strat = {}  # {prop_name: {value: [strat_ids]}}
        
        # Edges
        self.edges_by_type = {}
        self.edges_by_source = {}
        self.edges_by_target = {}
    
    def add_node_by_type(self, node_type, node):
        """Adds a node to the index by type"""
        if node_type not in self.nodes_by_type:
            self.nodes_by_type[node_type] = []
        self.nodes_by_type[node_type].append(node)
    
    def add_property_node(self, prop_name, node):
        """Adds a property node to the indexes"""
        if prop_name not in self.property_nodes_by_name:
            self.property_nodes_by_name[prop_name] = []
            self.property_values_by_name[prop_name] = set()
        
        self.property_nodes_by_name[prop_name].append(node)
        
        # Aggiungi il valore
        value = getattr(node, 'description', '')
        if value:
            self.property_values_by_name[prop_name].add(value)
    
    def add_edge(self, edge):
        """Adds an edge to indices"""
        # Per tipo
        if edge.edge_type not in self.edges_by_type:
            self.edges_by_type[edge.edge_type] = []
        self.edges_by_type[edge.edge_type].append(edge)
        
        # Per source
        if edge.edge_source not in self.edges_by_source:
            self.edges_by_source[edge.edge_source] = []
        self.edges_by_source[edge.edge_source].append(edge)
        
        # Per target
        if edge.edge_target not in self.edges_by_target:
            self.edges_by_target[edge.edge_target] = []
        self.edges_by_target[edge.edge_target].append(edge)
    
    def add_property_relation(self, prop_name, strat_id, value):
        """Adds a stratigraphic-property relationship"""
        # Strat -> Properties
        if strat_id not in self.strat_to_properties:
            self.strat_to_properties[strat_id] = {}
        self.strat_to_properties[strat_id][prop_name] = value
        
        # Properties -> Strat
        if prop_name not in self.properties_to_strat:
            self.properties_to_strat[prop_name] = {}
        if value not in self.properties_to_strat[prop_name]:
            self.properties_to_strat[prop_name][value] = []
        self.properties_to_strat[prop_name][value].append(strat_id)
    
    def get_property_names(self):
        """Returns all unique property names"""
        return sorted(self.property_nodes_by_name.keys())
    
    def get_property_values(self, prop_name):
        """Returns all unique values for a property"""
        values = set()
        
        # Valori esistenti
        values.update(self.property_values_by_name.get(prop_name, set()))
        
        # Aggiungi valori speciali se necessario
        if prop_name in self.property_nodes_by_name:
            # Controlla se ci sono nodi con valore vuoto
            for node in self.property_nodes_by_name[prop_name]:
                if not getattr(node, 'description', ''):
                    values.add(f"empty property {prop_name} node")
            
            # Controlla se ci sono nodi stratigrafici senza questa proprietà
            all_strat_with_prop = set()
            for strat_props in self.strat_to_properties.values():
                if prop_name in strat_props:
                    all_strat_with_prop.add(True)
            
            # Se ci sono nodi stratigrafici nel grafo che non hanno questa proprietà
            strat_nodes = self.nodes_by_type.get('US', []) + \
                         self.nodes_by_type.get('USVs', []) + \
                         self.nodes_by_type.get('USVn', []) + \
                         self.nodes_by_type.get('VSF', []) + \
                         self.nodes_by_type.get('SF', []) + \
                         self.nodes_by_type.get('USD', [])
            
            if len(strat_nodes) > len(all_strat_with_prop):
                values.add(f"no property {prop_name} node")
        
        return sorted(values)
    
    def get_strat_nodes_by_property_value(self, prop_name, value):
        """Returns the IDs of stratigraphic nodes with a given property value"""
        if value == f"empty property {prop_name} node":
            # Trova nodi con proprietà vuota
            result = []
            for node in self.property_nodes_by_name.get(prop_name, []):
                if not getattr(node, 'description', ''):
                    # Trova strat nodes collegati
                    for edge in self.edges_by_target.get(node.node_id, []):
                        if edge.edge_type == 'has_property':
                            result.append(edge.edge_source)
            return result
            
        elif value == f"no property {prop_name} node":
            # Trova nodi senza questa proprietà
            all_strat_ids = set()
            for node_type in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD']:
                for node in self.nodes_by_type.get(node_type, []):
                    all_strat_ids.add(node.node_id)
            
            # Rimuovi quelli che hanno la proprietà
            for strat_id, props in self.strat_to_properties.items():
                if prop_name in props:
                    all_strat_ids.discard(strat_id)
            
            return list(all_strat_ids)
        else:
            # Valore normale
            return self.properties_to_strat.get(prop_name, {}).get(value, [])