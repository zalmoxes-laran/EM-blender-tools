'''
Sync tra stato Blender (scene props / BGIS / 3DSC) e GeoPositionNode
del grafo attivo nel multigrafo.

Per design 1.6 il GeoPositionNode è specchio passivo dello stato scena:
si aggiorna in lettura al save/export JSON. L'utente non lo edita a mano.
'''

from __future__ import annotations

from typing import Optional


def get_active_graph():
    '''Ritorna il Graph attivo dal multigrafo, o None.'''
    import bpy
    try:
        em_tools = bpy.context.scene.em_tools
    except Exception:
        return None
    idx = getattr(em_tools, 'active_file_index', -1)
    if idx is None or idx < 0:
        return None
    try:
        graph_info = em_tools.graphml_files[idx]
    except (IndexError, AttributeError):
        return None
    try:
        from s3dgraphy import get_graph
        return get_graph(graph_info.name)
    except Exception:
        return None


def get_geo_node(graph):
    '''Trova il GeoPositionNode del grafo (autocreato con id geo_{graph_id}).'''
    if graph is None:
        return None
    geo_id = f"geo_{graph.graph_id}"
    node = None
    try:
        node = graph.find_node_by_id(geo_id)
    except Exception:
        node = None
    if node is not None:
        return node
    for n in getattr(graph, 'nodes', []):
        if getattr(n, 'node_type', None) == 'geo_position':
            return n
    return None


def push_to_geonode(
    graph,
    epsg: Optional[str],
    shift_x: float,
    shift_y: float,
    shift_z: float,
) -> bool:
    '''Scrive i valori correnti sul GeoPositionNode del grafo.

    Il GeoPositionNode è canonico nel JSON export ma oggi è popolato
    in lettura dallo stato scena. Chiamato tipicamente al save e al
    Heriverse export.
    '''
    node = get_geo_node(graph)
    if node is None:
        return False
    try:
        if epsg:
            node.epsg = int(epsg) if str(epsg).isdigit() else node.epsg
        node.shift_x = float(shift_x)
        node.shift_y = float(shift_y)
        node.shift_z = float(shift_z)
        return True
    except Exception:
        return False


def pull_from_geonode(graph):
    '''Legge epsg/shift dal GeoPositionNode del grafo attivo.

    Utile per il pulsante "Pull from graph" (disponibile ma non default).
    '''
    node = get_geo_node(graph)
    if node is None:
        return None
    try:
        return {
            'epsg': str(getattr(node, 'epsg', 4326)),
            'shift_x': float(getattr(node, 'shift_x', 0.0)),
            'shift_y': float(getattr(node, 'shift_y', 0.0)),
            'shift_z': float(getattr(node, 'shift_z', 0.0)),
        }
    except Exception:
        return None
