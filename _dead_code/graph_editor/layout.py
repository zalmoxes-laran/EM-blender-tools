"""
Hierarchical layout algorithm for EMGraph nodes
Arranges nodes in layers based on connectivity, avoiding overlaps.
"""

def calculate_hierarchical_layout(node_map, graph, filtered_node_ids):
    """
    Calcola un layout gerarchico per i nodi.

    Args:
        node_map: Dict {node_id: blender_node}
        graph: s3dgraphy Graph object
        filtered_node_ids: Set di node_id da considerare

    Returns:
        Dict {node_id: (x, y)} con le posizioni calcolate
    """

    # 1. Costruisci il grafo delle dipendenze (solo nodi filtrati)
    dependencies = {}  # {target_id: [source_ids]}
    reverse_deps = {}  # {source_id: [target_ids]}

    for edge in graph.edges:
        if edge.edge_source in filtered_node_ids and edge.edge_target in filtered_node_ids:
            # Target dipende da Source (Source -> Target)
            if edge.edge_target not in dependencies:
                dependencies[edge.edge_target] = []
            dependencies[edge.edge_target].append(edge.edge_source)

            # Reverse per calcolare i livelli
            if edge.edge_source not in reverse_deps:
                reverse_deps[edge.edge_source] = []
            reverse_deps[edge.edge_source].append(edge.edge_target)

    # 2. Calcola i livelli (layer) di ogni nodo usando BFS
    layers = {}  # {node_id: layer_number}

    # Trova i nodi radice (senza dipendenze in ingresso)
    root_nodes = [nid for nid in filtered_node_ids if nid not in dependencies or len(dependencies[nid]) == 0]

    # Se non ci sono radici, usa tutti i nodi come radici (grafo ciclico)
    if not root_nodes:
        root_nodes = list(filtered_node_ids)

    # Assegna livello 0 alle radici
    for node_id in root_nodes:
        layers[node_id] = 0

    # BFS per assegnare livelli
    queue = root_nodes[:]
    visited = set(root_nodes)

    while queue:
        current_id = queue.pop(0)
        current_layer = layers[current_id]

        # Espandi ai nodi dipendenti
        if current_id in reverse_deps:
            for target_id in reverse_deps[current_id]:
                if target_id not in visited:
                    layers[target_id] = current_layer + 1
                    visited.add(target_id)
                    queue.append(target_id)
                else:
                    # Se già visitato, aggiorna il livello se necessario
                    layers[target_id] = max(layers[target_id], current_layer + 1)

    # Nodi non raggiunti (isolati o cicli)
    for node_id in filtered_node_ids:
        if node_id not in layers:
            layers[node_id] = 0

    # 3. Raggruppa nodi per layer
    nodes_by_layer = {}
    for node_id, layer in layers.items():
        if layer not in nodes_by_layer:
            nodes_by_layer[layer] = []
        nodes_by_layer[layer].append(node_id)

    # 4. Calcola posizioni
    positions = {}

    # Parametri layout
    LAYER_SPACING_X = 400  # Spaziatura tra layer (colonne)
    NODE_SPACING_Y = 250   # Spaziatura tra nodi nello stesso layer
    START_X = 0
    START_Y = 0

    max_layer = max(nodes_by_layer.keys()) if nodes_by_layer else 0

    for layer_num in range(max_layer + 1):
        if layer_num not in nodes_by_layer:
            continue

        layer_nodes = nodes_by_layer[layer_num]
        num_nodes = len(layer_nodes)

        # Calcola X per questo layer
        x = START_X + (layer_num * LAYER_SPACING_X)

        # Ordina i nodi nel layer per minimizzare incroci
        # Usa euristica: ordina per numero medio di connessioni ai layer precedenti
        if layer_num > 0:
            layer_nodes = sort_layer_by_connections(layer_nodes, dependencies, layers, layer_num)

        # Calcola Y per centrare verticalmente
        total_height = (num_nodes - 1) * NODE_SPACING_Y
        start_y = START_Y - (total_height / 2)

        for i, node_id in enumerate(layer_nodes):
            y = start_y + (i * NODE_SPACING_Y)
            positions[node_id] = (x, y)

    return positions


def sort_layer_by_connections(layer_nodes, dependencies, layers, current_layer):
    """
    Ordina i nodi in un layer per minimizzare gli incroci con il layer precedente.
    Euristica: ordina per posizione media delle dipendenze.
    """

    # Calcola score per ogni nodo (posizione media delle sue dipendenze)
    node_scores = []

    for node_id in layer_nodes:
        if node_id in dependencies:
            # Trova le dipendenze nel layer precedente
            deps = dependencies[node_id]
            prev_layer_deps = [d for d in deps if d in layers and layers[d] == current_layer - 1]

            if prev_layer_deps:
                # Score = indice medio delle dipendenze
                avg_index = sum(layer_nodes.index(d) if d in layer_nodes else 0 for d in prev_layer_deps) / len(prev_layer_deps)
                node_scores.append((node_id, avg_index))
            else:
                node_scores.append((node_id, len(layer_nodes)))  # Metti alla fine
        else:
            node_scores.append((node_id, len(layer_nodes)))  # Nodi senza dipendenze alla fine

    # Ordina per score
    node_scores.sort(key=lambda x: x[1])

    return [node_id for node_id, _ in node_scores]


def apply_layout_to_nodes(node_map, positions):
    """
    Applica le posizioni calcolate ai nodi Blender.

    Args:
        node_map: Dict {node_id: blender_node}
        positions: Dict {node_id: (x, y)}
    """
    for node_id, (x, y) in positions.items():
        if node_id in node_map:
            bl_node = node_map[node_id]
            bl_node.location = (x, y)
            print(f"   Positioned {bl_node.label[:20]}: ({x:.0f}, {y:.0f})")
