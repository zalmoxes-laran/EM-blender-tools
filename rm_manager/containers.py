"""RM container logic (DP-47 extension / DP-07 wrapper).

An **RM container** groups several mesh objects under a single
DocumentNode. The Document is the graph-side wrapper; the container
is the EMTools-side PropertyGroup on ``scene.rm_containers`` that
tracks which Blender mesh objects belong to it. A mesh can belong to
at most **one** container at a time (user decision, Q_C).

Ownership:
- Authoritative mesh list → ``RMContainerItem.mesh_names``.
- Mesh custom property ``em_rm_container_doc_id`` is a reverse-lookup
  convenience; ``mesh_names`` wins if they disagree.
- Blender Collections are NOT source of truth — users are free to
  keep meshes in any collection they prefer.

This module exposes:

- :func:`sync_rm_containers` — validates mesh existence, removes
  missing entries, raises sanitisation warnings, and on first open
  bundles un-linked legacy RMs into an automatic "Legacy RMs" container.
- :func:`find_container_for_mesh` — reverse lookup.
- :func:`add_mesh_to_container` / :func:`remove_mesh_from_container` —
  mutate both the PropertyGroup list and the scene graph
  (``has_representation_model`` edge from Document to RM node).
- :func:`unregister_container` — drops the container + removes all
  ``has_representation_model`` edges from the linked Document to the
  contained meshes' RM nodes (the DocumentNode itself stays).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import bpy  # type: ignore
import mathutils  # type: ignore — R5: il bounding box in coordinate di mondo


# EM16-RMNG: la proiezione del container nel grafo. In un modulo suo e senza
# `bpy` — la stessa ragione che `epoch_edges.py` dà per sé: così la logica sul
# grafo si misura fuori da Blender.
from . import group_nodes as _gn

LEGACY_CONTAINER_LABEL = "Legacy RMs"
UNASSIGNED_CONTAINER_LABEL = "Unassigned RMs"


def is_rm_candidate(obj) -> bool:
    """Return True when ``obj`` is a valid RM candidate: either a
    MESH, a CURVE, or an EMPTY that is NOT a collection-instance
    proxy. Cesium tilesets are stored on plain empties with a
    ``tileset_path`` custom property, so the EMPTY case is required.
    Matches the filter used by ``rm.promote_to_rm`` so a container
    can hold exactly the same object types the existing RM pipeline
    already handles.
    """
    if obj is None:
        return False
    if obj.type in ('MESH', 'CURVE'):
        return True
    if obj.type == 'EMPTY' and obj.instance_type != 'COLLECTION':
        return True
    return False


def _active_graph(context):
    """Return (graph_info, graph) tuple, or (None, None) when there is
    no active graph (no graphml loaded).
    """
    em_tools = context.scene.em_tools
    if em_tools.active_file_index < 0 \
            or em_tools.active_file_index >= len(em_tools.graphml_files):
        return None, None
    try:
        from s3dgraphy import get_graph
        gi = em_tools.graphml_files[em_tools.active_file_index]
        return gi, get_graph(gi.name)
    except Exception:
        return None, None


def _resolve_doc_name(graph, doc_node_id: str) -> str:
    """Return the DocumentNode's display name (e.g. ``D.01``) or empty
    string if the node is missing.
    """
    if not doc_node_id or graph is None:
        return ""
    try:
        n = graph.find_node_by_id(doc_node_id)
        return (getattr(n, "name", "") or "") if n is not None else ""
    except Exception:
        return ""


def find_container_for_mesh(scene, mesh_name: str) -> Optional[int]:
    """Return the index of the container that holds ``mesh_name``, or
    ``None`` when the mesh is not in any container.
    """
    if not mesh_name:
        return None
    for idx, container in enumerate(scene.rm_containers):
        for entry in container.mesh_names:
            if entry.name == mesh_name:
                return idx
    return None


def rename_mesh_in_containers(scene, old_name: str, new_name: str) -> int:
    """Rename ``old_name`` to ``new_name`` in every container's
    ``mesh_names`` entry. Returns the number of entries updated.

    Used after a LOD switch renames the underlying object so the
    container's stored mesh name keeps tracking the live object.
    Without this, the rm_list filter (which compares item.name to
    container.mesh_names) would lose the entry on the next redraw.
    """
    if not old_name or old_name == new_name:
        return 0
    updated = 0
    for container in scene.rm_containers:
        for entry in container.mesh_names:
            if entry.name == old_name:
                entry.name = new_name
                updated += 1
    return updated


# ══════════════════════════════════════════════════════════════════════
# NIGHT-RIM/A4 · UN SOLO IDENTIFICATORE PER L'RM
# ══════════════════════════════════════════════════════════════════════
#
# Decisione di E.D.: **l'identificatore è l'UUID sulla custom property
# `em_rm_node_id`. Il nome dell'oggetto è un'etichetta.**
#
# Prima ne convivevano quattro: `f"{obj.name}_model"` (in nove punti fra
# `graph_updaters`, `rm_manager/operators`, `heriverse/operator`,
# `shelf_tool/operators`), l'UUID in `em_rm_node_id`, un terzo UUID in
# `surface_areale/postprocess`, e il ritorno dal grafo alla scena **per
# stringa**, con match su sottostringa. Quattro identità dello stesso oggetto
# significa che due qualsiasi di esse possono divergere senza che nulla lo
# dica.
#
# ## LA MIGRAZIONE È PIGRA, E NON C'È UN PASSAGGIO IN BLOCCO
#
# Un oggetto senza la property la ottiene **al primo gesto che lo riguarda**,
# risalendo per nome UNA VOLTA SOLA e scrivendo la prop. Niente riscrittura
# all'apertura del file, niente passata su tutta la scena: sono i due modi in
# cui una migrazione tocca dati che non doveva toccare.
#
# Se il nome non risolve, si lascia com'è e si torna `None`: **mai inventare
# un id.** Un id inventato qui sarebbe un nodo RM fantasma nel grafo.
ID_MODEL_LEGACY = "_model"


def resolve_rm_node_id(graph, mesh_obj, *, scene=None, migra=True):
    """L'id del nodo RM di questa mesh, o `None`. NON crea nodi.

    Ordine di risoluzione, dal più autorevole al più debole:

    1. `em_rm_node_id` sulla mesh, **se quell'id esiste ancora nel grafo**
       (una prop che punta al vuoto non è autorevole: il nodo può essere
       stato rimosso da un'altra parte);
    2. la voce corrispondente in `scene.rm_list`, che il vecchio RM Manager
       teneva per mesh;
    3. l'**eredità** `f"{nome}_model"`, ma solo se quel nodo c'è davvero nel
       grafo — ed è qui che avviene la migrazione pigra: l'id trovato per
       nome viene scritto nella property, una volta sola.

    `migra=False` per i chiamanti che non devono scrivere niente (una
    diagnosi, un pannello in sola lettura): risolve e non tocca la mesh.
    """
    if graph is None or mesh_obj is None:
        return None

    def esiste(nid):
        if not nid:
            return False
        try:
            return graph.find_node_by_id(nid) is not None
        except Exception:                           # noqa: BLE001
            return False

    # 1 · la property, se punta a qualcosa
    existing = mesh_obj.get("em_rm_node_id", "")
    if esiste(existing):
        return existing

    # 2 · rm_list
    if scene is not None:
        try:
            for rm_item in scene.rm_list:
                if rm_item.name == mesh_obj.name and esiste(rm_item.node_id):
                    if migra:
                        mesh_obj["em_rm_node_id"] = rm_item.node_id
                    return rm_item.node_id
        except Exception:                           # noqa: BLE001
            pass

    # 3 · l'eredità per nome, e la migrazione pigra
    eredita = f"{mesh_obj.name}{ID_MODEL_LEGACY}"
    if esiste(eredita):
        if migra:
            mesh_obj["em_rm_node_id"] = eredita
        return eredita

    # …e basta. Nessun id inventato.
    return None


# ══════════════════════════════════════════════════════════════════════
# NIGHT-RIM2/B2 · LA PROMOZIONE CREA IL NODO, E LA RISORSA INTERNA
# ══════════════════════════════════════════════════════════════════════
#
# Decisione di E.D.: `rm.promote_to_rm` deve creare il nodo RM nel grafo,
# **subito**. Prima non lo creava: il `representation_model` compariva solo
# dopo l'export, perché lo fabbricava `update_graph_with_scene_data` —
# misurato la notte scorsa, l'oggetto risultava promosso e nel grafo non
# c'era niente.
#
# Insieme al nodo nasce la RISORSA INTERNA, con locator `blend://` e l'arco
# `has_linked_resource` dall'RM. Il pattern è quello di
# `s3Dgraphy/shelf/core.py::_hat_facet`: riusa-o-crea, e l'arco si mette solo
# se non c'è già — così richiamarla è idempotente, che è la condizione perché
# l'export possa ripassarci sopra senza fare doppioni.
#
# DUE NODI, NON DUE INDIRIZZI (decisione 2 di E.D.): la risorsa interna e
# quella pubblicata sono nodi distinti, legati da una derivazione. Un solo
# nodo con un url che a volte è `blend://` romperebbe Heriverse, che si
# aspetta un url di formato adeguato.

#: Il suffisso dell'id della risorsa interna. Derivato dall'id dell'RM, come
#: ogni altro id di questa notte: così il secondo passaggio la TROVA.
SUFFISSO_RISORSA_INTERNA = "_res_blend"


def blend_locator_per(obj) -> str:
    """Il locator `blend://` di questo oggetto, o `""` se non è formabile.

    Il locator cita il file dove il datablock **vive davvero** (decisione 5):
    per un oggetto linkato da una libreria è il file della libreria — un
    rilievo resta `rilievo2015.blend`, non lo studio aperto che lo linka.

    PERCORSO RELATIVO O ASSOLUTO è una questione **non decisa** (elenco delle
    questioni aperte, voce B). Qui c'è il minimo che non la pregiudica:
    relativo al .blend corrente quando si può, assoluto altrimenti, e la
    scelta sta in questa funzione sola — cambiarla resta una modifica sola.

    Torna `""` quando il file non è mai stato salvato: **non** si inventa un
    percorso temporaneo. Chi chiama lo sa e lo dice.
    """
    import bpy
    import os
    try:
        from s3dgraphy.resources.resolver import make_blend_locator
    except ImportError as e:
        # NON un ripiego muto. Questo `except` ha già nascosto una volta la
        # sua stessa causa: la s3Dgraphy caricata da Blender è la copia del
        # WHEEL, che non ha `make_blend_locator` finché il wheel non viene
        # ricostruito (`python scripts/rebundle_s3dgraphy.py`) o la libreria
        # di sviluppo vendorizzata (`./em.sh s3d`). Tornavo "" e il locator
        # risultava «non formabile» come se il file non fosse salvato — due
        # diagnosi opposte con lo stesso sintomo, che è esattamente il difetto
        # che questa notte esiste per togliere di mezzo.
        print("[EM WARNING] blend:// non disponibile in questa s3Dgraphy "
              f"({e}). Ricostruisci il wheel o vendorizza la libreria di "
              "sviluppo: il locator interno resta non risolvibile.")
        return ""

    # DOVE VIVE DAVVERO IL DATABLOCK, in ordine di precisione. NIGHT-RES/R2:
    # per un RM esportato da un'istanza il master **non sta nel file aperto**,
    # e le tre forme del linking sono diverse:
    #
    #   * `obj.library`            — l'oggetto intero è linkato;
    #   * `obj.data.library`       — l'oggetto è locale ma la MESH è linkata
    #                                (il modo comune: linka il rilievo,
    #                                istanzialo qui);
    #   * `instance_collection`    — un empty che istanzia una collection
    #                                linkata.
    #
    # Lo studio aperto è CONTESTO, non indirizzo. Se il file linkato si sposta
    # il master diventa irrisolvibile: è un'informazione, non un guasto, e
    # l'audit la conta fra le irrisolvibili.
    dati = getattr(obj, "data", None)
    collezione = getattr(obj, "instance_collection", None)
    sorgente = ""
    for candidata in (getattr(obj, "library", None),
                      getattr(dati, "library", None),
                      getattr(collezione, "library", None)):
        percorso_lib = getattr(candidata, "filepath", "") if candidata else ""
        if percorso_lib:
            sorgente = percorso_lib
            break
    if not sorgente:
        sorgente = bpy.data.filepath
    if not sorgente:
        return ""
    assoluto = bpy.path.abspath(sorgente)

    corrente = bpy.data.filepath
    percorso = assoluto
    if corrente:
        try:
            base = os.path.dirname(bpy.path.abspath(corrente))
            relativo = os.path.relpath(assoluto, base)
            #: relativo solo se non esce dal volume e non è un labirinto di
            #: `..`: un relativo peggiore dell'assoluto non è un vantaggio
            if not relativo.startswith(".." + os.sep + ".."):
                percorso = relativo
        except ValueError:
            #: volumi diversi su Windows: `relpath` solleva, l'assoluto regge
            percorso = assoluto

    return make_blend_locator(percorso, "Object", obj.name)


def _misure_da_mesh(mesh, oggetto) -> dict:
    """Conteggi, ingombro in coordinate di mondo e materiali, da una mesh e
    dall'oggetto che le dà la trasformazione. Una funzione sola perché le due
    strade — base e valutata — devono misurare **le stesse cose**: se
    divergessero, confrontare due impronte non vorrebbe dire più niente."""
    misure = {}
    vertici = getattr(mesh, "vertices", None)
    poligoni = getattr(mesh, "polygons", None)
    if vertici is not None:
        misure["v"] = len(vertici)
    if poligoni is not None:
        misure["f"] = len(poligoni)
    # L'INGOMBRO SOLO SE ABBIAMO MISURATO DELLA GEOMETRIA.
    #
    # Un empty ha un `bound_box` di otto zeri, che trasformato dà otto volte
    # la sua posizione: non solleva, quindi il vecchio `try/except` non lo
    # prendeva e il commento accanto — «un empty non ha un ingombro: assente,
    # non zero» — diceva una cosa che il codice non faceva. Misurato
    # (NIGHT-FIN/T2): un empty usciva con `bb=0,0,0,0,0,0`.
    #
    # Adesso è vero: senza conteggi non c'è geometria, e senza geometria un
    # ingombro è un numero su niente. L'impronta di un empty resta vuota, che
    # vuol dire «non so» — e per un tileset esterno è la risposta giusta: la
    # sua sorgente non è in questo file.
    if misure:
        try:
            matrice = oggetto.matrix_world
            angoli = [matrice @ mathutils.Vector(c) for c in oggetto.bound_box]
            misure["bb"] = [
                min(a.x for a in angoli), min(a.y for a in angoli),
                min(a.z for a in angoli), max(a.x for a in angoli),
                max(a.y for a in angoli), max(a.z for a in angoli)]
        except (AttributeError, TypeError):
            pass
    nomi = sorted(str(m.name) for m in (getattr(mesh, "materials", None) or [])
                  if m is not None)
    if nomi:
        misure["mat"] = "|".join(nomi)
    return misure


def misura_oggetto(obj) -> dict:
    """Le misure STRUTTURALI di un oggetto — e su QUALE mesh, che è la
    domanda che NIGHT-FIN/T2 ha chiuso.

    Conteggi, gli otto vertici del bounding box portati in coordinate di
    mondo, i nomi dei materiali. Niente viene serializzato.

    **DUE STRADE, e la scelta è il numero di modificatori.**

    Senza modificatori la mesh base *è* quella valutata, quindi valutarla
    sarebbe pagare per niente. Con almeno un modificatore no: NIGHT-RES aveva
    misurato un falso negativo — alzare il livello di una subdivision cambia
    ciò che l'export scrive e l'impronta non se ne accorgeva — e nella
    pubblicazione un falso negativo costa più di un falso positivo: un «è
    aggiornato» sbagliato pubblica roba vecchia credendola fresca, mentre un
    «rifai il bake» di troppo costa un bottone.

    **I costi, misurati** (14-09-2026, per oggetto, media su molti giri):

    ====================================  ========  ==========
    scena                                 base      valutata
    ====================================  ========  ==========
    10 cubi, nessun modificatore          5,31 µs   7,80 µs
    10 cubi + subsurf 2 (96 facce)        5,13 µs   13,35 µs
    20 mesh da 3750 facce, nessun mod.    5,00 µs   8,27 µs
    …le stesse + subsurf 1 (15k facce)    5,25 µs   217,12 µs
    ====================================  ========  ==========

    Il costo della valutata cresce con la mesh RISULTANTE, non con quella
    base: 217 µs su 15 000 facce valutate sono 0,2 s su mille oggetti, e si
    pagano **solo dove i modificatori ci sono**. Sono anche una frazione di
    ciò che l'export sta già spendendo su quegli stessi oggetti, visto che per
    scrivere il glTF la mesh valutata gli serve comunque.

    **`ev=1` viaggia nelle misure** quando la strada è stata la seconda. Due
    impronte prese su mesh diverse non sono confrontabili come se fossero la
    stessa cosa, ed è la regola che già distingue `struct:` da `mtime:`.
    Effetto laterale voluto: aggiungere un modificatore che non cambia niente
    rende la derivata stantia. È un falso positivo, cioè il verso giusto.

    **LIMITE CHE RESTA** (e sta anche in `resource_levels.impronta_strutturale`,
    perché è lì che qualcuno potrebbe credere il contrario): l'impronta **non è
    crittografica**. Spostare un vertice dentro il bounding box senza cambiare
    conteggi né materiali dà la stessa impronta — misurato. Il suo mestiere è
    spegnere il rumore, non dimostrare l'identità; per quella c'è lo sha256
    dei byte prodotti, che il verbale scrive già.

    Torna `{}` quando non c'è niente da misurare: chi legge distingue «non so»
    da «diverso».
    """
    if obj is None:
        return {}
    if not getattr(obj, "modifiers", None):
        return _misure_da_mesh(getattr(obj, "data", None), obj)

    # ── la strada della mesh VALUTATA ──────────────────────────────────────
    valutato = None
    try:
        grafo = bpy.context.evaluated_depsgraph_get()
        valutato = obj.evaluated_get(grafo)
        mesh = valutato.to_mesh()
    except (AttributeError, RuntimeError) as exc:
        # DETTO, non ingoiato: senza un depsgraph (un contesto che non ce
        # l'ha, un oggetto che non sa produrre una mesh) si ripiega sulla
        # base, che è la misura di prima — ma allora il falso negativo del
        # modificatore torna, e chi legge deve saperlo.
        print(f"[EM WARNING] {getattr(obj, 'name', '?')}: mesh valutata non "
              f"disponibile ({exc}); impronta sulla mesh base, un cambio di "
              f"modificatore non si vedrà")
        return _misure_da_mesh(getattr(obj, "data", None), obj)
    try:
        misure = _misure_da_mesh(mesh, valutato)
        misure["ev"] = 1
        return misure
    finally:
        try:
            valutato.to_mesh_clear()
        except (AttributeError, RuntimeError):
            pass


def impronta_di(obj) -> str:
    """L'impronta strutturale di un oggetto — misura + forma canonica."""
    from .. import resource_levels as _rl
    return _rl.impronta_strutturale(misura_oggetto(obj))


def percorso_del_grezzo(res_node) -> str:
    """Il percorso ASSOLUTO del file che contiene il grezzo, o `""`.

    NIGHT-RIM3/B4 · serve a impronta­re la sorgente al momento del bake. Il
    locator `blend://` porta un percorso che può essere **relativo** al
    .blend corrente (è la scelta di B1), e un'impronta presa su un percorso
    relativo dipenderebbe dalla cartella di lavoro: qui si risolve una volta
    sola, contro il file aperto.

    Per una risorsa che non è `blend://` si torna il suo url se è un percorso
    locale: anche un rilievo `.obj` su disco è un grezzo impronta­bile.
    """
    import bpy
    import os
    if res_node is None:
        return ""
    url = str((getattr(res_node, "data", None) or {}).get("url") or "")
    if not url:
        return ""
    try:
        from s3dgraphy.resources.resolver import parse_blend_locator
    except ImportError as e:
        #: decisione 14: niente `except Exception` che maschera un ImportError
        print("[EM WARNING] parse_blend_locator non disponibile "
              f"({e}): impronta del grezzo non calcolabile")
        return ""
    pezzi = parse_blend_locator(url)
    percorso = pezzi[0] if pezzi else url
    if not percorso:
        return ""
    if os.path.isabs(percorso):
        return percorso
    corrente = bpy.data.filepath
    if not corrente:
        return ""
    return os.path.normpath(
        os.path.join(os.path.dirname(bpy.path.abspath(corrente)), percorso))


def basi_dei_locator(context=None) -> list:
    """Le cartelle rispetto a cui un locator relativo può essere scritto.

    D5 · Accanto a :func:`percorso_del_grezzo`, che risolve un `blend://`, e
    per lo stesso motivo: **un percorso relativo non dipende dalla cartella di
    lavoro del processo**, dipende da dove il modello dice che sta. Qui si
    raccolgono le basi che esistono davvero, nell'ordine in cui hanno più
    probabilità di essere quella giusta:

    1. la cartella **DosCo** del grafo attivo — i documenti ci vivono dentro e
       il loro url è relativo a lei (`functions.py`);
    2. la cartella del **progetto esportato** — le derivate portano
       `dosco/…`, `proxies/…`, `tilesets/…`, relativi a lei;
    3. la cartella dell'**export**, un gradino sopra la precedente;
    4. la cartella del **.blend** aperto, che è la base di riferimento di
       Blender per tutto il resto.

    Lista vuota = nessuna base nota, e chi chiama deve dire «non ho potuto
    guardare», non «non ci sono».
    """
    import bpy
    import os
    ctx = context or bpy.context
    scene = getattr(ctx, "scene", None)
    basi = []

    em_tools = getattr(scene, "em_tools", None) if scene else None
    voce = None
    if em_tools is not None and getattr(em_tools, "graphml_files", None):
        indice = getattr(em_tools, "active_file_index", -1)
        if 0 <= indice < len(em_tools.graphml_files):
            voce = em_tools.graphml_files[indice]
    if voce is not None:
        try:
            from ..em_setup.resource_utils import resolve_dosco_dir
            basi.append(resolve_dosco_dir(voce) or "")
        except ImportError as exc:
            #: decisione 14: un ImportError si dichiara, non si ingoia
            print(f"[EM WARNING] resolve_dosco_dir non disponibile ({exc}): "
                  f"i locator relativi ai documenti non si risolvono")
            basi.append(bpy.path.abspath(getattr(voce, "dosco_dir", "") or "")
                        if getattr(voce, "dosco_dir", "") else "")

    export = getattr(scene, "heriverse_export_path", "") if scene else ""
    if export:
        radice = os.path.normpath(bpy.path.abspath(export))
        nome = (getattr(scene, "heriverse_project_name", "")
                or os.path.splitext(os.path.basename(bpy.data.filepath))[0])
        if nome:
            basi.append(os.path.join(radice, f"{nome}_multigraph"))
        basi.append(radice)

    if bpy.data.filepath:
        basi.append(os.path.dirname(bpy.path.abspath(bpy.data.filepath)))

    fuori = []
    for b in basi:
        b = str(b or "")
        if b and b not in fuori and os.path.isdir(b):
            fuori.append(b)
    return fuori


def ensure_rm_and_internal_resource(scene, graph, obj):
    """Il nodo RM di questa mesh e la sua risorsa interna.

    Torna `(rm_id, res_id, avvisi)`. `res_id` è `None` quando la risorsa non
    si è potuta formare; `avvisi` è una lista di stringhe da mostrare in UNA
    riga, mai in un popup.

    Idempotente: chiamarla due volte non crea doppioni, perché gli id sono
    derivati e si cercano prima di creare.
    """
    avvisi = []
    if graph is None or obj is None:
        return None, None, avvisi

    try:
        from s3dgraphy.nodes.representation_node import RepresentationModelNode
        from s3dgraphy.nodes.resource_node import ResourceNode
    except Exception as e:                          # noqa: BLE001
        return None, None, [f"s3Dgraphy non disponibile: {e}"]

    # ── il nodo RM ────────────────────────────────────────────────────
    rm_id = resolve_rm_node_id(graph, obj, scene=scene)
    if not rm_id:
        rm_id = f"{obj.name}{ID_MODEL_LEGACY}"
    rm_node = graph.find_node_by_id(rm_id)
    if rm_node is None:
        rm_node = RepresentationModelNode(
            node_id=rm_id,
            name=f"Model for {obj.name}",
            type="RM",
            description="",
        )
        graph.add_node(rm_node)
    #: l'identificatore è la property, e qui è «il primo gesto che riguarda
    #: l'oggetto». Si scrive solo se cambia: toccarla marca il .blend come
    #: modificato.
    if obj.get("em_rm_node_id", "") != rm_id:
        obj["em_rm_node_id"] = rm_id

    # ── la risorsa interna ────────────────────────────────────────────
    res_id = f"{rm_id}{SUFFISSO_RISORSA_INTERNA}"
    locator = blend_locator_per(obj)
    res_node = graph.find_node_by_id(res_id)
    if res_node is None:
        res_node = ResourceNode(
            node_id=res_id,
            name=f"Blend datablock for {obj.name}",
            url=locator,
            url_type="3d_model",
            description=f"The mesh as it lives inside the .blend ({obj.name})",
        )
        graph.add_node(res_node)
    elif locator and res_node.data.get("url") != locator:
        #: il file è stato salvato dopo, o rinominato: il locator si fissa
        #: adesso, e l'id NON cambia
        res_node.data["url"] = locator

    if not locator:
        #: NON si inventa un percorso temporaneo. La risorsa esiste, e dice
        #: di non essere ancora risolvibile.
        res_node.data["unresolved"] = True
        avvisi.append("Save the .blend to fix the internal resource locator")
    else:
        res_node.data.pop("unresolved", None)

    # ── l'arco, solo se non c'è ───────────────────────────────────────
    if not _has_edge(graph, rm_id, res_id, "has_linked_resource"):
        graph.add_edge(
            edge_id=f"{rm_id}_has_linked_resource_{res_id}",
            edge_source=rm_id,
            edge_target=res_id,
            edge_type="has_linked_resource",
        )
    return rm_id, res_id, avvisi


def _ensure_rm_node_for_mesh(scene, graph, mesh_obj) -> Optional[str]:
    """Return the node_id of the RepresentationModelNode that
    represents this mesh in the graph. Resolution order:

    1. The mesh's ``em_rm_node_id`` custom property (if still valid).
    2. The matching entry in ``scene.rm_list`` (legacy RM Manager
       already tracks an RM node_id per mesh).
    3. Create a fresh RepresentationModelNode.

    The resolved id is written back to the mesh's ``em_rm_node_id`` so
    subsequent calls hit case 1.
    """
    if graph is None or mesh_obj is None:
        return None
    # NIGHT-RIM/A4 · i primi tre casi (property, rm_list, eredità per nome
    # con migrazione pigra) sono `resolve_rm_node_id`: erano scritti qui e
    # sono diventati la risoluzione unica che usano tutti i percorsi.
    risolto = resolve_rm_node_id(graph, mesh_obj, scene=scene)
    if risolto:
        return risolto
    # Case 3: create a fresh RepresentationModelNode.
    try:
        from s3dgraphy.exporter.graphml.utils import generate_uuid
        from s3dgraphy.nodes.representation_node import RepresentationModelNode
    except Exception:
        return None
    rm_id = generate_uuid()
    rm_node = RepresentationModelNode(
        node_id=rm_id,
        name=mesh_obj.name,
        type="RM",
        description="",
    )
    graph.add_node(rm_node)
    mesh_obj["em_rm_node_id"] = rm_id
    return rm_id


def _has_edge(graph, source_id: str, target_id: str,
               edge_type: str) -> bool:
    for e in graph.edges:
        if (e.edge_source == source_id
                and e.edge_target == target_id
                and e.edge_type == edge_type):
            return True
    return False


def add_mesh_to_container(context, container, mesh_obj) -> Tuple[bool, str]:
    """Add ``mesh_obj`` to ``container``. Returns ``(ok, reason)``.

    Creates the RepresentationModelNode for the mesh if needed, adds
    the ``has_representation_model`` edge from the linked Document to
    the RM node, sets the mesh's reverse-lookup custom property, and
    appends the mesh name to the container's list.

    Skips (with reason) when the mesh is already in another container
    (Q_C: a mesh belongs to at most one container).
    """
    if not is_rm_candidate(mesh_obj):
        return False, (
            f"Object {getattr(mesh_obj, 'name', '?')!r} is not an RM "
            f"candidate (need MESH / CURVE / plain EMPTY)")
    scene = context.scene
    existing_idx = find_container_for_mesh(scene, mesh_obj.name)
    if existing_idx is not None:
        existing = scene.rm_containers[existing_idx]
        if existing == container:
            return False, f"Mesh {mesh_obj.name!r} already in this container"
        return False, (
            f"Mesh {mesh_obj.name!r} already belongs to container "
            f"{existing.label!r} — remove it from there first")
    # Graph side (only when the container is linked to a Document).
    _graph_info, graph = _active_graph(context)
    if graph is not None and container.doc_node_id:
        rm_id = _ensure_rm_node_for_mesh(scene, graph, mesh_obj)
        if rm_id and not _has_edge(
                graph, container.doc_node_id, rm_id,
                "has_representation_model"):
            try:
                graph.add_edge(
                    edge_id=(f"{container.doc_node_id}_"
                             f"has_representation_model_{rm_id}"),
                    edge_source=container.doc_node_id,
                    edge_target=rm_id,
                    edge_type="has_representation_model",
                )
            except Exception as e:
                return False, f"Failed to add edge: {e}"
        mesh_obj["em_rm_container_doc_id"] = container.doc_node_id
    # Property-group side.
    entry = container.mesh_names.add()
    entry.name = mesh_obj.name
    # EM16-RMNG · group side, IN ADDITION to everything above and never
    # instead of it. Only when the projection already exists: creating it here
    # would mean writing a new node into the graph as a side effect of adding
    # a mesh, and the projection is an explicit act (see `rmcontainer.project`).
    if graph is not None and container.group_node_id:
        rm_id = mesh_obj.get("em_rm_node_id", "")
        if rm_id:
            _gn.add_member(graph, container.group_node_id, rm_id)
    return True, ""


def remove_mesh_from_container(context, container, mesh_name: str,
                                 drop_edge: bool = True) -> bool:
    """Remove ``mesh_name`` from ``container``. When ``drop_edge`` is
    True and the container is linked to a Document, also remove the
    ``has_representation_model`` edge from the Document to the mesh's
    RM node. Returns True on success.
    """
    # Property-group side.
    hit_idx = None
    for i, entry in enumerate(container.mesh_names):
        if entry.name == mesh_name:
            hit_idx = i
            break
    if hit_idx is None:
        return False
    container.mesh_names.remove(hit_idx)
    # Graph side.
    if drop_edge and container.doc_node_id:
        _graph_info, graph = _active_graph(context)
        mesh_obj = bpy.data.objects.get(mesh_name)
        rm_id = mesh_obj.get("em_rm_node_id", "") if mesh_obj else ""
        if graph is not None and rm_id:
            edge_id = (f"{container.doc_node_id}_"
                       f"has_representation_model_{rm_id}")
            for i, e in enumerate(list(graph.edges)):
                if (e.edge_id == edge_id
                        or (e.edge_source == container.doc_node_id
                            and e.edge_target == rm_id
                            and e.edge_type == "has_representation_model")):
                    try:
                        graph.remove_edge(e.edge_id)
                    except Exception:
                        pass
                    break
        if mesh_obj is not None \
                and mesh_obj.get("em_rm_container_doc_id", "") \
                == container.doc_node_id:
            try:
                del mesh_obj["em_rm_container_doc_id"]
            except KeyError:
                pass
    # EM16-RMNG · the membership edge goes, and NOTHING else: the model keeps
    # its epoch edges and the Document keeps its direct edge to it. Outside the
    # `drop_edge` guard on purpose — membership mirrors `mesh_names`, which
    # changed regardless of whether the caller wanted the documentary edge
    # touched.
    if container.group_node_id:
        _graph_info2, graph2 = _active_graph(context)
        mesh_obj2 = bpy.data.objects.get(mesh_name)
        rm_id2 = mesh_obj2.get("em_rm_node_id", "") if mesh_obj2 else ""
        if graph2 is not None and rm_id2:
            _gn.remove_member(graph2, container.group_node_id, rm_id2)
    return True


def unregister_container(context, container_index: int) -> bool:
    """Drop a container from ``scene.rm_containers``. Also removes all
    ``has_representation_model`` edges from the linked Document to the
    mesh RM nodes contained here (Q_B). The DocumentNode itself stays.
    """
    scene = context.scene
    if container_index < 0 or container_index >= len(scene.rm_containers):
        return False
    container = scene.rm_containers[container_index]
    # Rip out each mesh's edge + custom prop first.
    mesh_names = [e.name for e in container.mesh_names]
    for mn in mesh_names:
        remove_mesh_from_container(context, container, mn, drop_edge=True)
    # EM16-RMNG · and the group node with them. What goes is the group, its
    # membership edges and the Document→GROUP edge; what stays is the
    # DocumentNode itself and the Document→MODEL direct edges — the behaviour
    # this function already had (Q_B), preserved to the letter.
    if container.group_node_id:
        _graph_info, graph = _active_graph(context)
        if graph is not None:
            _gn.remove_group(graph, container.group_node_id)
    scene.rm_containers.remove(container_index)
    if scene.rm_containers_index >= len(scene.rm_containers):
        scene.rm_containers_index = max(0, len(scene.rm_containers) - 1)
    return True


def _add_warning(scene, container_label: str, mesh_name: str):
    w = scene.rm_container_warnings.add()
    w.container_label = container_label
    w.mesh_name = mesh_name


def bootstrap_legacy_container_if_needed(context) -> None:
    """Cheap one-time guard run on panel draw.

    When ``scene.rm_containers`` is empty AND there is pre-existing
    content in ``scene.rm_list``, bundle every still-existing RM
    entry into a single unlinked "Legacy RMs" container so the
    two-level UI always has at least one container to show.

    This is O(1) in the common case: once any container exists, the
    first check short-circuits and no mesh iteration happens — safe
    to call on every draw.
    """
    scene = context.scene
    if len(scene.rm_containers) != 0:
        return
    if len(scene.rm_list) == 0:
        return
    legacy = scene.rm_containers.add()
    legacy.label = LEGACY_CONTAINER_LABEL
    legacy.doc_node_id = ""
    legacy.doc_name = ""
    for rm in scene.rm_list:
        if rm.name and rm.name in bpy.data.objects:
            entry = legacy.mesh_names.add()
            entry.name = rm.name
    scene.rm_containers_index = 0


def sync_rm_containers(context) -> None:
    """Full sanitisation pass — explicitly user-triggered via the
    ``rmcontainer.sync`` operator. NOT called on panel draw (it walks
    every mesh in every container and would slow the UI down).

    - For each container, drop mesh entries whose Blender object has
      been deleted. Each drop emits a :class:`RMContainerWarning` so
      the user is told which mesh went missing.
    - Refresh cached ``doc_name`` for each container from the graph.
    - Runs :func:`bootstrap_legacy_container_if_needed` at the end so
      a manual sync also seeds the Legacy container when nothing has
      been imported yet.
    """
    scene = context.scene
    _graph_info, graph = _active_graph(context)

    # 1. Validate & refresh existing containers.
    for container in scene.rm_containers:
        # Drop missing meshes
        i = len(container.mesh_names) - 1
        while i >= 0:
            mn = container.mesh_names[i].name
            if mn and mn not in bpy.data.objects:
                _add_warning(scene, container.label or container.doc_name
                             or "<unnamed>", mn)
                container.mesh_names.remove(i)
            i -= 1
        # Refresh doc_name cache
        if container.doc_node_id:
            fresh = _resolve_doc_name(graph, container.doc_node_id)
            if fresh:
                container.doc_name = fresh

    # 2. Legacy bootstrap (no-op when containers already exist).
    bootstrap_legacy_container_if_needed(context)

    # 3. EM16-RMNG · reconcile the graph projection with the containers.
    #
    # HERE and not on load, and the distinction is the requirement: this
    # function is reached ONLY from the `rmcontainer.sync` operator — a button
    # — never from a panel draw and never from a file load. Opening a .blend
    # therefore never rewrites the graph.
    #
    # `project_containers` is what creates the MISSING groups, and it is a
    # second, separate button (`rmcontainer.project`): a sync on a project
    # that has no projection yet must not decide to make one. So sync only
    # reconciles what already exists, and reports divergences.
    reconcile_container_groups(context, create_missing=False)


def reconcile_container_groups(context, create_missing: bool = False) -> dict:
    """Make the graph's RM groups agree with ``scene.rm_containers``.

    ``mesh_names`` is the input and the graph is the output — never the other
    way round. Returns a summary the operators turn into a report line.

    ``create_missing=False`` (what sync does) touches only containers that
    already carry a ``group_node_id``: a project with no projection stays
    without one until somebody asks for it.
    ``create_missing=True`` (what the projection button does) is the migration
    of an existing .blend.

    NOTHING IS DELETED IN SILENCE: every divergence the reconciliation cannot
    resolve becomes an :class:`RMContainerWarning`, with the same mechanism
    already used for a mesh that vanished from the scene.
    """
    scene = context.scene
    _graph_info, graph = _active_graph(context)
    esito = {"created": 0, "added": 0, "removed": 0, "refused": 0,
             "unknown": 0, "unknown_containers": 0, "skipped_no_graph": 0}
    if graph is None:
        esito["skipped_no_graph"] = len(scene.rm_containers)
        return esito

    for container in scene.rm_containers:
        gid = container.group_node_id
        if not gid:
            if not create_missing:
                continue
            gid = _gn.group_node_id_for(container.label, container.doc_node_id)
            container.group_node_id = gid

        # The model node ids of this container's meshes, in mesh_names order.
        model_ids = []
        for entry in container.mesh_names:
            obj = bpy.data.objects.get(entry.name)
            if obj is None:
                continue            # already reported by the pass above
            rm_id = obj.get("em_rm_node_id", "")
            if rm_id:
                model_ids.append(rm_id)

        rapporto = _gn.reconcile_container(
            graph, gid,
            label=container.label or container.doc_name or gid,
            model_node_ids=model_ids,
            doc_node_id=container.doc_node_id,
        )
        esito["created"] += 1 if rapporto["created"] else 0
        esito["added"] += len(rapporto["added"])
        esito["removed"] += len(rapporto["removed"])
        esito["refused"] += len(rapporto["refused"])
        esito["unknown"] += len(rapporto.get("unknown") or [])
        # A model the graph says belongs to ANOTHER group: reported, not
        # resolved. Resolving it would mean choosing which of two user
        # intentions to discard.
        for rm_id in rapporto["refused"]:
            _add_warning(scene,
                         container.label or container.doc_name or "<unnamed>",
                         f"{rm_id} (già in un altro gruppo nel grafo)")
        # …e i modelli che il grafo non conosce.
        #
        # EM16-UX/E · UN messaggio, non N. Misurato sul file di lavoro di E.D.
        # il 10-09-2026: 98 mesh su 99 portano un `em_rm_node_id` che non
        # risolve in nessuno dei due grafi caricati, perché quel grafo viene da
        # un import GraphML e `graphml_patcher.INTERNAL_NODE_TYPES` esclude i
        # `representation_model` dal GraphML — per disegno, non per guasto.
        #
        # Un warning per mesh darebbe 98 righe che dicono la stessa cosa, e
        # novantotto volte la stessa frase non è informazione: è rumore che
        # nasconde le altre. Quindi si contano e si dice una volta, con il
        # comando da eseguire prima. NESSUNA creazione implicita di nodi.
        ignoti = rapporto.get("unknown") or []
        if ignoti:
            esito["unknown_containers"] += 1
            esito.setdefault("_ignoti_per_container", []).append(
                (container.label or container.doc_name or "<unnamed>",
                 len(ignoti)))
    return esito


def active_container(scene):
    """Return the currently-active :class:`RMContainerItem` or None."""
    if not scene.rm_containers:
        return None
    idx = scene.rm_containers_index
    if idx < 0 or idx >= len(scene.rm_containers):
        return None
    return scene.rm_containers[idx]


def mesh_names_of_active_container(scene) -> List[str]:
    """Convenience: list of mesh names in the active container, or an
    empty list when no container is active.
    """
    ac = active_container(scene)
    if ac is None:
        return []
    return [entry.name for entry in ac.mesh_names]


def _lod_base_name(name: str) -> str:
    """LOD-stripped form of ``name`` (``Foo_LOD2`` → ``Foo``).

    Mirrors ``ui._base_name`` so orphan detection matches the very
    comparison the UIList filter performs. Imported lazily to keep
    this module free of import cycles with ``operators``.
    """
    try:
        from .operators import _split_lod_name
        base, _ = _split_lod_name(name or "")
        return base or name
    except Exception:
        return name


def unassigned_rm_names(scene) -> List[str]:
    """Return the names of ``rm_list`` entries that belong to no
    container — the RMs the UI cannot reach.

    ``RM_UL_List`` filters strictly by the active container's
    ``mesh_names``, and every per-row editor (epoch sub-list, tileset
    path, publish flag) keys off ``scene.rm_list_index``. An RM in no
    container therefore has no selectable row: it cannot be edited,
    re-assigned to another epoch, or even inspected.

    Orphans appear when an object joins ``rm_list`` outside the
    container flow (e.g. a Cesium tileset added by ``rm.add_tileset``
    before EM 1.5.x) or when the container that held it was
    unregistered. Only reported once at least one container exists —
    with zero containers the filter falls back to showing everything
    and the Legacy bootstrap is the right answer instead.
    """
    if not scene.rm_containers:
        return []
    assigned = set()
    for container in scene.rm_containers:
        for entry in container.mesh_names:
            assigned.add(_lod_base_name(entry.name))
    orphans = []
    for rm in scene.rm_list:
        if not rm.name or rm.name not in bpy.data.objects:
            continue
        if _lod_base_name(rm.name) not in assigned:
            orphans.append(rm.name)
    return orphans
