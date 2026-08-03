'''
Sync tra stato Blender (scene props / BGIS / 3DSC) e GeoPositionNode
del grafo attivo nel multigrafo.

Per design 1.6 il GeoPositionNode è specchio passivo dello stato scena:
si aggiorna in lettura al save/export JSON. L'utente non lo edita a mano.

**Dove vivono i valori, e perché conta (C1).** In s3Dgraphy il
GeoPositionNode tiene epsg / shift_x / shift_y / shift_z / rotation
dentro ``node.data``, e ``to_dict()`` serializza **esattamente**
``node.data``. Fino a questo fix ``push_to_geonode`` scriveva invece
*attributi di istanza* (``node.epsg = ...``): dentro la sessione tutto
sembrava funzionare — ``pull_from_geonode`` rileggeva gli stessi
attributi — ma all'export ``node.data`` era ancora ai default, quindi
la georeferenziazione fatta in Blender **non arrivava** né a
EMStudio né a Heriverse. Verificato prima/dopo: epsg 32633 e shift
291960.5/4640631.8 tornavano 4326 e 0/0 dopo un round-trip em.json.

Regola, adesso: **``node.data`` è la verità** (è il contratto di
s3Dgraphy, che è la single source of truth del linguaggio); gli attributi
di istanza vengono tenuti allineati solo per compatibilità con eventuali
lettori interni, mai come sorgente. I nomi dei campi sono quelli di
s3Dgraphy, ``rotation`` incluso (azimut in gradi, 0 = nord in alto).
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
    rotation: float = 0.0,
) -> bool:
    '''Scrive i valori correnti sul GeoPositionNode del grafo.

    Il GeoPositionNode è canonico nel JSON export ma è popolato in lettura
    dallo stato scena. Chiamato tipicamente al save e al Heriverse export.

    Scrive in ``node.data`` — l'unico posto che ``to_dict()`` serializza —
    e vi tiene allineati gli attributi di istanza. ``rotation`` è l'azimut
    di scena in gradi (0 = nord in alto), additivo: un chiamante che non lo
    passa lascia il valore che c'è, invece di azzerarlo.
    '''
    node = get_geo_node(graph)
    if node is None:
        return False
    try:
        data = getattr(node, 'data', None)
        if not isinstance(data, dict):
            # Un nodo costruito da un percorso che non popola `data` (o una
            # versione di s3dgraphy più vecchia): si crea, così l'export ha
            # comunque qualcosa da serializzare.
            data = {}
            node.data = data

        # EPSG resta INTERO come in s3Dgraphy (default 4326). Una stringa non
        # numerica — 'NotSet', vuota — lascia il valore precedente: è lo stato
        # "l'utente non ha ancora scelto un CRS", non un ordine di azzerare.
        if epsg and str(epsg).strip().isdigit():
            data['epsg'] = int(str(epsg).strip())
        elif 'epsg' not in data:
            data['epsg'] = 4326

        data['shift_x'] = float(shift_x)
        data['shift_y'] = float(shift_y)
        data['shift_z'] = float(shift_z)
        if rotation is not None:
            data['rotation'] = float(rotation)
        elif 'rotation' not in data:
            data['rotation'] = 0.0

        # Mirror sugli attributi di istanza: qualunque lettore interno che
        # facesse `node.epsg` continua a vedere lo stesso valore. Mai la
        # sorgente — solo un riflesso di `data`.
        for key in ('epsg', 'shift_x', 'shift_y', 'shift_z', 'rotation'):
            try:
                setattr(node, key, data[key])
            except Exception:
                pass
        return True
    except Exception:
        return False


def pull_from_geonode(graph):
    '''Legge epsg/shift/rotation dal GeoPositionNode del grafo attivo.

    Utile per il pulsante "Pull from graph" (disponibile ma non default).
    Legge ``node.data`` (la verità), con gli attributi di istanza come
    ripiego per un nodo scritto da una versione precedente di questo modulo.
    '''
    node = get_geo_node(graph)
    if node is None:
        return None
    data = getattr(node, 'data', None)
    if not isinstance(data, dict):
        data = {}

    def _read(key, default):
        value = data.get(key, None)
        if value is None:
            value = getattr(node, key, default)
        return default if value is None else value

    try:
        return {
            'epsg': str(_read('epsg', 4326)),
            'shift_x': float(_read('shift_x', 0.0)),
            'shift_y': float(_read('shift_y', 0.0)),
            'shift_z': float(_read('shift_z', 0.0)),
            'rotation': float(_read('rotation', 0.0)),
        }
    except Exception:
        return None
