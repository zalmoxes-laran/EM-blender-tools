'''
Sync tra stato Blender (scene props / BGIS / 3DSC) e GeoPositionNode
del grafo attivo nel multigrafo.

Il GeoPositionNode si legge all'apertura del grafo e si scrive **a ogni
salvataggio** (decisione E.D. del 24 ott 2026, :func:`write_on_save`), oltre che
con «Push to GeoNode». Misurato il 24 ott: la scrittura automatica si era persa
il 5 ott 2026 con il commit ``43cfb52`` (H4), quando l'export Heriverse
(``EXPORT_OT_heriverse.execute``, il mirror DP-56 di ``json_export.py``) è
andato in ``_dead_code``; né «Save em.json» né «Save As…» l'avevano mai
chiamata.

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

**Lettura all'apertura (MICRO georiferimento dal grafo, 23 ott 2026).** Il
nodo non è più solo uno specchio: quando un grafo si apre e la scena non è
georiferita (EPSG vuoto e shift a 0), i suoi valori passano in
``scene.em_georef`` (:func:`adopt_on_open`) e da lì a BlenderGIS/3DSC con la
propagazione di sempre. Se la scena è già georiferita e i valori differiscono,
non si sovrascrive niente: il pannello mostra la discrepanza
(:func:`differences`) e offre «Pull from graph». ``push_to_geonode`` collega
il nodo al gruppo «Graph paradata» del grafo (:func:`ensure_in_graph_paradata`),
come autore, licenza ed embargo (decisione E.D. del 23 ott).

Regola, adesso: **``node.data`` è la verità** (è il contratto di
s3Dgraphy, che è la single source of truth del linguaggio); gli attributi
di istanza vengono tenuti allineati solo per compatibilità con eventuali
lettori interni, mai come sorgente. I nomi dei campi sono quelli di
s3Dgraphy, ``rotation`` incluso (azimut in gradi, 0 = nord in alto).
'''

from __future__ import annotations

import json
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

        # EPSG resta INTERO come in s3Dgraphy. Una stringa non numerica —
        # 'NotSet', vuota — lascia il valore precedente: è lo stato "l'utente
        # non ha ancora scelto un CRS", non un ordine di azzerare. Senza un
        # EPSG il nodo resta SENZA la chiave: per s3Dgraphy 1.6.0.dev29 (A6)
        # è così che un grafo dice «non georiferito», mai con 4326 a 0,0.
        if epsg and str(epsg).strip().isdigit():
            data['epsg'] = int(str(epsg).strip())

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
            if key not in data:
                continue
            try:
                setattr(node, key, data[key])
            except Exception:
                pass
        # Il nodo esposto nel gruppo «Graph paradata», come la licenza: un
        # errore qui non disfa la scrittura dei valori (che è riuscita).
        try:
            ensure_in_graph_paradata(graph, node)
        except Exception as exc:  # noqa: BLE001
            print(f"[georef] GeoPositionNode not linked to Graph paradata: {exc}")
        return True
    except Exception:
        return False


def pull_from_geonode(graph):
    '''Legge epsg/shift/rotation dal GeoPositionNode del grafo attivo.

    Usato all'apertura di un grafo (:func:`adopt_on_open`) e da «Pull from
    graph» (scelta esplicita quando scena e grafo differiscono).
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
            # None = non georiferito (s3Dgraphy dev29, A6): mai 4326 per difetto.
            'epsg': (None if _read('epsg', None) is None
                     else str(_read('epsg', None))),
            'shift_x': float(_read('shift_x', 0.0)),
            'shift_y': float(_read('shift_y', 0.0)),
            'shift_z': float(_read('shift_z', 0.0)),
            'rotation': float(_read('rotation', 0.0)),
        }
    except Exception:
        return None


# ── MICRO georiferimento dal grafo ───────────────────────────────────────────

#: Tolleranze per dire «uguali»: 1 mm per lo shift (come le spie del pannello),
#: un millesimo di grado per l'azimut.
SHIFT_TOLERANCE = 1e-3
ROTATION_TOLERANCE = 1e-3

_FIELDS = ('epsg', 'shift_x', 'shift_y', 'shift_z', 'rotation')


# ── lo shift esatto ──────────────────────────────────────────────────────────
#
# Misurato il 23 ott 2026 sul GT16: le FloatProperty di Blender sono a 32 bit.
# 327372.56 diventa 327372.5625 e 448682.65 diventa 448682.65625 (6 mm); a una
# northing UTM come 4640631.8 il passo è 0.5 m (diventa 4640632.0). Lo shift
# letto dal grafo e riscritto con «Push to GeoNode» spostava quindi l'ancora.
# I campi del pannello restano FloatProperty (si editano, si propagano); accanto
# c'è ``shift_exact`` (stringa JSON di tre double) scritto da chi conosce il
# valore esatto. Vale finché coincide, al float32, con il campo: se qualcuno
# edita il campo a mano, il campo vince.

def _f32(value: float) -> float:
    import struct
    return struct.unpack('f', struct.pack('f', float(value)))[0]


def set_shift(g, x: float, y: float, z: float) -> None:
    '''Scrive lo shift nei campi (float32, i callback propagano) e il valore
    esatto in ``g.shift_exact``.'''
    g.shift_x = float(x)
    g.shift_y = float(y)
    g.shift_z = float(z)
    try:
        g.shift_exact = json.dumps([float(x), float(y), float(z)])
    except Exception:  # noqa: BLE001 — una scena senza la proprietà
        pass


def exact_shift(g) -> tuple:
    '''(x, y, z) in doppia precisione: il valore esatto dove coincide con il
    campo, il campo altrimenti.'''
    fields = (float(getattr(g, 'shift_x', 0.0) or 0.0),
              float(getattr(g, 'shift_y', 0.0) or 0.0),
              float(getattr(g, 'shift_z', 0.0) or 0.0))
    try:
        exact = json.loads(getattr(g, 'shift_exact', '') or 'null')
    except Exception:  # noqa: BLE001
        exact = None
    if not (isinstance(exact, list) and len(exact) == 3):
        return fields
    return tuple(float(e) if _f32(e) == _f32(f) else f
                 for e, f in zip(exact, fields))


def scene_values(g) -> dict:
    '''I valori di ``scene.em_georef`` (o di qualunque oggetto con gli stessi
    campi) nella forma di :func:`pull_from_geonode`.'''
    raw = str(getattr(g, 'epsg', '') or '').strip()
    x, y, z = exact_shift(g)
    return {
        'epsg': raw if raw and raw.lower() != 'notset' else None,
        'shift_x': x,
        'shift_y': y,
        'shift_z': z,
        'rotation': float(getattr(g, 'rotation', 0.0) or 0.0),
    }


def is_georeferenced(values: Optional[dict]) -> bool:
    '''Georiferito = un EPSG dichiarato o uno shift diverso da zero. La scena
    «vuota» del MICRO è EPSG non impostato E shift a 0.'''
    if not values:
        return False
    if values.get('epsg'):
        return True
    return any(abs(float(values.get(k) or 0.0)) > SHIFT_TOLERANCE
               for k in ('shift_x', 'shift_y', 'shift_z'))


def differences(scene: dict, graph: Optional[dict]) -> list:
    '''I campi in cui scena e grafo dicono cose diverse:
    ``[(campo, valore_scena, valore_grafo), ...]``; vuota se coincidono o se
    il grafo non dice niente.'''
    if not graph:
        return []
    out = []
    se = str(scene.get('epsg') or '').strip()
    ge = str(graph.get('epsg') or '').strip()
    if se != ge:
        out.append(('epsg', se or None, ge or None))
    for key in ('shift_x', 'shift_y', 'shift_z'):
        a, b = float(scene.get(key) or 0.0), float(graph.get(key) or 0.0)
        if abs(a - b) > SHIFT_TOLERANCE:
            out.append((key, a, b))
    a, b = float(scene.get('rotation') or 0.0), float(graph.get('rotation') or 0.0)
    if abs(a - b) > ROTATION_TOLERANCE:
        out.append(('rotation', a, b))
    return out


def write_scene(g, values: dict) -> None:
    '''Scrive i valori del grafo in ``scene.em_georef``. In Blender ogni
    assegnazione fa scattare il callback che propaga a BlenderGIS e 3DSC (la
    propagazione esistente, idempotente). L'EPSG va per ultimo: così la
    propagazione finale porta già lo shift giusto con il CRS giusto.'''
    set_shift(g, float(values.get('shift_x') or 0.0),
              float(values.get('shift_y') or 0.0),
              float(values.get('shift_z') or 0.0))
    g.rotation = float(values.get('rotation') or 0.0)
    g.epsg = str(values['epsg']) if values.get('epsg') else ''


def adopt_on_open(g, graph) -> dict:
    '''Un grafo si è aperto: decide cosa fare del suo georiferimento.

    Ritorna ``{"outcome", "sentence", "differences"}`` con ``outcome`` in:

    - ``"adopted"``   — la scena non era georiferita, il grafo sì: i suoi
      valori sono passati in ``g``;
    - ``"same"``      — scena e grafo coincidono;
    - ``"differs"``   — la scena è già georiferita e il grafo dice altro:
      nessuna sovrascrittura, la discrepanza si mostra;
    - ``"graph-empty"`` — il grafo non è georiferito (o non ha il nodo).
    '''
    gv = pull_from_geonode(graph)
    gid = getattr(graph, 'graph_id', '?')
    if not is_georeferenced(gv):
        return {'outcome': 'graph-empty', 'differences': [],
                'sentence': f"Graph {gid} declares no georeferencing"}
    sv = scene_values(g)
    if not is_georeferenced(sv):
        write_scene(g, gv)
        return {'outcome': 'adopted', 'differences': [],
                'sentence': (f"Georeferencing read from graph {gid}: "
                             f"EPSG:{gv['epsg'] or '—'} · {gv['shift_x']:.3f}, "
                             f"{gv['shift_y']:.3f}, {gv['shift_z']:.3f}")}
    diff = differences(sv, gv)
    if not diff:
        return {'outcome': 'same', 'differences': [],
                'sentence': f"Scene and graph {gid} agree on the georeferencing"}
    return {'outcome': 'differs', 'differences': diff,
            'sentence': (f"Scene and graph {gid} differ on "
                         f"{', '.join(d[0] for d in diff)}: nothing overwritten")}


def _graph_root(graph):
    for n in getattr(graph, 'nodes', []):
        if getattr(n, 'node_type', None) == 'graph':
            return n
    return None


def _edge_exists(graph, source, target, edge_type) -> bool:
    for e in getattr(graph, 'edges', []):
        if (e.edge_type == edge_type and e.edge_source == source
                and e.edge_target == target):
            return True
    return False


def ensure_in_graph_paradata(graph, node=None) -> Optional[str]:
    '''Il GeoPositionNode nel gruppo «Graph paradata» del grafo, con
    ``is_in_paradata_nodegroup`` — come autore, licenza ed embargo (s3Dgraphy
    ``materialize_graph_scope``; decisione E.D. del 23 ott: il nodo esposto
    come la licenza). Stessi id di s3Dgraphy e di EMStudio:
    ``<geo>__is_in_paradata_nodegroup__<gruppo>``. Il GraphNode e il gruppo si
    creano se mancano (con gli id di ``materialize_graph_scope``). Idempotente.
    Ritorna l'id dell'arco (nuovo o già presente), None se non c'è un nodo.'''
    node = node or get_geo_node(graph)
    if graph is None or node is None:
        return None
    gid = graph.graph_id
    root = _graph_root(graph)
    if root is None:
        from s3dgraphy.nodes.graph_node import GraphNode
        root = GraphNode(node_id=f"{gid}_graphroot", name="Graph")
        graph.add_node(root)
    pdg = None
    for e in getattr(graph, 'edges', []):
        if e.edge_type == 'has_paradata_nodegroup' and e.edge_source == root.node_id:
            pdg = graph.find_node_by_id(e.edge_target)
            if pdg is not None:
                break
    if pdg is None:
        from s3dgraphy.nodes.group_node import ParadataNodeGroup
        pdg = ParadataNodeGroup(node_id=f"{gid}_graph_paradata", name="Graph paradata")
        graph.add_node(pdg)
        graph.add_edge(f"{root.node_id}__has_paradata_nodegroup__{pdg.node_id}",
                       root.node_id, pdg.node_id, "has_paradata_nodegroup")
    eid = f"{node.node_id}__is_in_paradata_nodegroup__{pdg.node_id}"
    if not _edge_exists(graph, node.node_id, pdg.node_id, 'is_in_paradata_nodegroup'):
        graph.add_edge(eid, node.node_id, pdg.node_id, "is_in_paradata_nodegroup")
    return eid


def on_graph_opened(scene, graph, log=None) -> Optional[dict]:
    '''Chiamata dagli importatori (em.json e GraphML) alla fine di un
    caricamento riuscito. G1: con più grafi nella scena il georiferimento
    della scena è quello del grafo di riferimento — un altro grafo non lo
    scrive mai (si allinea con «Align graphs to the scene»). La frase dell'esito
    resta in ``em_georef.graph_note`` (la riga del pannello) e va nel Log; un
    EPSG deprecato o con trasformazione ballpark si dice nel Log, con la
    proposta (la conversione è sempre un clic di chi lavora, mai silenziosa).'''
    g = getattr(scene, 'em_georef', None)
    if g is None or graph is None:
        return None
    log = log or (lambda msg, level="INFO": print(f"[georef] {msg}"))
    rows = list(getattr(getattr(scene, 'em_tools', None), 'graphml_files', ()) or ())
    ref = getattr(g, 'reference_graph', '') or ''
    if len(rows) > 1 and ref and graph.graph_id != ref:
        res = {'outcome': 'not-reference', 'differences': [],
               'sentence': (f"Graph {graph.graph_id} is not the scene's reference "
                            f"graph ({ref}): its georeferencing is not read into "
                            f"the scene")}
    else:
        res = adopt_on_open(g, graph)
        if res['outcome'] in ('adopted', 'same'):
            remember_agreement(g, graph)
    try:
        g.graph_note = res['sentence']
    except Exception:  # noqa: BLE001 — una scena senza la proprietà nuova
        pass
    log(f"[georef] {res['sentence']}",
        "WARNING" if res['outcome'] == 'differs' else "INFO")
    # EPSG deprecato / ballpark: detto una volta nel Log, con la proposta
    gv = pull_from_geonode(graph) or {}
    if gv.get('epsg'):
        try:
            from . import crs_check
            prop = crs_check.proposal(gv['epsg'], gv['shift_x'], gv['shift_y'])
        except Exception:  # noqa: BLE001
            prop = None
        if prop and prop.get('warn'):
            repl = prop.get('replacement')
            tail = (f" — proposed: convert to EPSG:{repl['epsg']} ({repl['name']}, "
                    f"{'same grid' if repl['same_grid'] else 'another grid'}) in the "
                    f"Georeferencing panel" if repl else "")
            log(f"[georef] {prop['reason']}{tail}", "WARNING")
            res['proposal'] = prop
    return res


# ── al salvataggio (MICRO georef al salvataggio, decisione E.D. 24 ott 2026) ─
#
# A ogni salvataggio dell'em.json (Save, Save As, «Save this file», «Save all»,
# il salvataggio dopo una creazione), nella stanza (come operazioni) e nel
# pacchetto Heriverse, i valori di ``scene.em_georef`` vanno nel GeoPositionNode
# del grafo della scena, collegato a «Graph paradata». Le regole:
#
# - scena non georiferita (EPSG vuoto e shift 0) → il nodo resta com'è;
# - scena e grafo d'accordo → i valori del nodo restano (sono già quelli; lo
#   shift del grafo non si riscrive con un float32), si assicura il gruppo;
# - grafo non georiferito, o grafo che dice ancora quello su cui scena e grafo
#   si erano accordati l'ultima volta (la scena è cambiata dopo) → si scrive;
# - altrimenti la discrepanza non è risolta (la scena non si è mai allineata a
#   QUESTI valori del grafo): niente scrittura senza una scelta — Push (la
#   scena nel grafo), Pull (il grafo nella scena) o Keep (il grafo com'è).
#
# «Accordati» = l'ultima volta che scena e grafo hanno detto la stessa cosa:
# all'apertura (letto o uguale), con Push, Pull, la conversione EPSG, un
# salvataggio. I valori del grafo di quel momento stanno in
# ``em_georef.graph_agreed`` (JSON ``{graph_id: valori}``).

CHOICES = ('ASK', 'PUSH', 'PULL', 'KEEP')


def scene_graph_id(scene) -> Optional[str]:
    '''Il grafo il cui georiferimento è quello della scena (G1): il grafo di
    riferimento con più grafi, l'unico con uno solo, se no il grafo attivo —
    la stessa regola di «Push to GeoNode».'''
    g = getattr(scene, 'em_georef', None)
    em_tools = getattr(scene, 'em_tools', None)
    rows = list(getattr(em_tools, 'graphml_files', ()) or ())
    ref = getattr(g, 'reference_graph', '') or ''
    if len(rows) > 1 and ref:
        return ref
    if len(rows) == 1:
        return rows[0].name
    idx = getattr(em_tools, 'active_file_index', -1)
    if idx is not None and 0 <= idx < len(rows):
        return rows[idx].name
    return None


def _agreed(g) -> dict:
    try:
        out = json.loads(getattr(g, 'graph_agreed', '') or '{}')
    except Exception:  # noqa: BLE001
        out = {}
    return out if isinstance(out, dict) else {}


def remember_agreement(g, graph) -> None:
    '''Scena e grafo ``graph`` dicono adesso la stessa cosa: si ricorda che
    cosa diceva il grafo.'''
    gv = pull_from_geonode(graph)
    if gv is None:
        return
    agreed = _agreed(g)
    agreed[graph.graph_id] = gv
    try:
        g.graph_agreed = json.dumps(agreed, sort_keys=True)
    except Exception:  # noqa: BLE001 — una scena senza la proprietà
        pass


def save_plan(g, graph) -> dict:
    '''Che cosa farà un salvataggio con il nodo di ``graph`` (il grafo della
    scena). ``{"outcome", "differences", "sentence"}``, ``outcome`` in
    ``scene-empty`` · ``same`` · ``write`` · ``conflict``.'''
    gid = getattr(graph, 'graph_id', '?')
    sv = scene_values(g)
    if not is_georeferenced(sv):
        return {'outcome': 'scene-empty', 'differences': [],
                'sentence': (f"The scene is not georeferenced: the "
                             f"GeoPositionNode of {gid} is left as it is")}
    gv = pull_from_geonode(graph)
    if not is_georeferenced(gv):
        return {'outcome': 'write', 'differences': [],
                'sentence': f"The scene's georeferencing is written into graph {gid}"}
    diff = differences(sv, gv)
    if not diff:
        return {'outcome': 'same', 'differences': [],
                'sentence': f"Scene and graph {gid} agree on the georeferencing"}
    base = _agreed(g).get(gid)
    if base and not differences(base, gv):
        return {'outcome': 'write', 'differences': diff,
                'sentence': (f"The scene's georeferencing changed since it agreed "
                             f"with graph {gid}: written into the graph")}
    return {'outcome': 'conflict', 'differences': diff,
            'sentence': (f"Scene and graph {gid} differ on "
                         f"{', '.join(d[0] for d in diff)} and the scene was never "
                         f"aligned to the graph: choose Push or Pull before saving")}


def save_conflict(scene, graph_ids, live) -> Optional[dict]:
    '''Il piano del grafo della scena se è fra ``graph_ids`` ed è in
    discrepanza non risolta, altrimenti None. ``live(graph_id)`` → il grafo.'''
    gid = scene_graph_id(scene)
    g = getattr(scene, 'em_georef', None)
    if g is None or not gid or gid not in list(graph_ids):
        return None
    graph = live(gid)
    if graph is None or get_geo_node(graph) is None:
        return None
    plan = save_plan(g, graph)
    if plan['outcome'] != 'conflict':
        return None
    plan['graph_id'] = gid
    return plan


def write_on_save(scene, graph_ids, live, choice: str = 'ASK',
                  log=None) -> Optional[dict]:
    '''Prima di scrivere i grafi ``graph_ids``: il georiferimento della scena
    nel nodo del grafo della scena, secondo le regole sopra. Un altro grafo
    (allineato, non di riferimento) non si tocca mai.

    ``choice`` dice che cosa fare di una discrepanza non risolta: ``PUSH``,
    ``PULL``, ``KEEP``; con ``ASK`` non si scrive niente e l'esito è
    ``conflict`` (il chiamante non salva e chiede). → il piano con l'esito
    finale (``written`` · ``pushed`` · ``pulled`` · ``kept`` · ``same`` ·
    ``scene-empty`` · ``conflict``) e ``graph_id``, None se nessuno dei grafi è
    quello della scena.'''
    log = log or (lambda msg, level="INFO": print(f"[georef] {msg}"))
    gid = scene_graph_id(scene)
    g = getattr(scene, 'em_georef', None)
    if g is None or not gid or gid not in list(graph_ids):
        return None
    graph = live(gid)
    if graph is None or get_geo_node(graph) is None:
        return None
    plan = save_plan(g, graph)
    plan['graph_id'] = gid
    outcome = plan['outcome']
    choice = (choice or 'ASK').upper()
    if outcome == 'scene-empty':
        return plan
    if outcome == 'same':
        try:
            ensure_in_graph_paradata(graph)
        except Exception as exc:  # noqa: BLE001
            log(f"GeoPositionNode not linked to Graph paradata: {exc}", "WARNING")
        remember_agreement(g, graph)
        return plan
    if outcome == 'conflict':
        if choice == 'PULL':
            write_scene(g, pull_from_geonode(graph))
            remember_agreement(g, graph)
            plan['outcome'] = 'pulled'
            plan['sentence'] = (f"Georeferencing pulled from graph {gid} before "
                                f"saving: the scene takes the graph's values")
        elif choice == 'KEEP':
            plan['outcome'] = 'kept'
            plan['sentence'] = (f"Scene and graph {gid} differ on "
                                f"{', '.join(d[0] for d in plan['differences'])}: "
                                f"the graph's georeferencing is kept, the scene's "
                                f"is not written")
        elif choice != 'PUSH':
            log(plan['sentence'], "WARNING")
            return plan
        if choice != 'PUSH':
            log(plan['sentence'], "WARNING" if choice == 'KEEP' else "INFO")
            return plan
    push_to_geonode(graph, g.epsg or None, *exact_shift(g), g.rotation)
    remember_agreement(g, graph)
    plan['outcome'] = 'pushed' if outcome == 'conflict' else 'written'
    if outcome == 'conflict':
        plan['sentence'] = (f"The scene's georeferencing pushed into graph {gid} "
                            f"before saving (it said "
                            f"{', '.join(d[0] for d in plan['differences'])} "
                            f"otherwise)")
    sv = scene_values(g)
    log(f"{plan['sentence']}: EPSG:{sv['epsg'] or '—'} · {sv['shift_x']:.3f}, "
        f"{sv['shift_y']:.3f}, {sv['shift_z']:.3f}")
    return plan
