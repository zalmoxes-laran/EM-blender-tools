"""EMtools ⇄ EMStudio live-sync — operators + EVENT-DRIVEN dispatch (ADR-002
phase 1 selection + phase 2 op-log). EMtools is the HOST: it runs the
WebSocket server (sync_bridge.ws_server) and holds the live s3dgraphy graph;
EMStudio connects as a client.

No polling timer. Two directions, both event-driven:

  * OUTBOUND (Blender → EMStudio): a ``bpy.msgbus`` subscription on the active
    object fires ``_on_selection_changed`` on the MAIN thread whenever the
    selection changes → broadcast the node id. Zero polling.
  * INBOUND (EMStudio → Blender): the server thread's ``on_message`` callback
    schedules a ONE-SHOT ``bpy.app.timers.register(_drain_inbox,
    first_interval=0)`` (returns ``None`` → self-unregisters). It fires only
    when a message actually arrives, drains the queue on the MAIN thread and
    applies each message (select / op). ``timers.register`` is the one
    Blender API that is safe to call from a non-main thread.

The server thread only touches the socket + thread-safe queue and schedules
the one-shot; every ``bpy`` access happens on the main thread.

Known limitation: ``bpy.msgbus`` subscriptions are dropped when a new .blend
is loaded — start Sync AFTER opening the project (re-subscribe on load_post
is a later refinement).
"""

from __future__ import annotations

import json
import threading

import bpy  # type: ignore

from ..sync_bridge.ws_server import WsServer
from ..sync_bridge.wire import WIRE, WireError, envelope, read
from ..functions import is_graph_available, select_3D_obj
from ..operators.addon_prefix_helpers import (
    proxy_name_to_node_name,
    node_name_to_proxy_name,
)

_SOURCE = "emtools"

# Module-level session state (a single server per Blender instance).
_server: WsServer | None = None
_last_active_name: str | None = None
_last_selection: frozenset = frozenset()  # node_ids last selected (echo guard)
_pending_repop = False  # a structural op needs a list rebuild (batched per drain)

# msgbus subscription owner (opaque token; clear_by_owner removes the sub).
_msgbus_owner = object()

# One-shot inbound-drain scheduling guard. The flag is cleared at the START of
# every drain, so any message arriving during a drain re-schedules another
# drain — no lost wake-ups; at worst one redundant empty drain.
_drain_lock = threading.Lock()
_drain_scheduled = False


# --------------------------------------------------------------------------- #
# C2 · UN CANCELLO SOLO, E STA DA CHI RICEVE
# --------------------------------------------------------------------------- #
#
# Era una DIREZIONE a quattro stati (`off`/`send`/`receive`/`both`) e chiudeva
# in tutti e due i versi. La decisione del 12-09-2026 (§6) la riduce a una sola
# politica, **di ingresso**, e l'argomento non è il consenso ma
# l'**osservabilità**:
#
#   In sidecar i due strumenti sono PARI — un utente solo su due schermi, o due
#   che si parlano — quindi non c'è nessuno che subisce. Ma un cancello in
#   USCITA è invisibile all'altro capo: chi non riceve non distingue «non ha
#   mandato» da «si è perso», ed è il terzo dei silenzi indistinguibili che
#   questa notte esiste per separare. Un cancello in ENTRATA lo dichiara sempre
#   chi lo chiude — lo vede nel proprio pannello, e la riga «Last inbound» gli
#   dice che sta scartando.
#
# Tre valori e non quattro, perché sull'INGRESSO «send» e «off» erano lo stesso
# fatto (non accetto niente) mentre selezione e operazione sono due cose diverse
# in natura: una selezione altrui muove il mio viewport, un'operazione altrui
# **cambia il mio grafo**. Metterle nella stessa casella era una conseguenza
# del vocabolario vecchio, non una scelta.
#
#   nothing     non entra niente
#   selection   entra la selezione, NON le modifiche al grafo
#   everything  entra tutto — il comportamento di sempre, e il default
#
# `request_snapshot`, `request_save`, `client_info` e `command` NON sono
# governati da qui: i primi tre sono domande, non echi, e il quarto ha il suo
# consenso (`em_accept_commands`), che è una domanda più forte e separata.

SYNC_ACCEPT = (
    ("nothing", "Nothing", "Refuse the echo: nothing from EMStudio lands here"),
    ("selection", "Selection", "EMStudio's selection lands here; its graph edits do not"),
    ("everything", "Everything", "Selection and graph edits both land here"),
)

#: Il valore che vale quanto il comportamento di prima di questo controllo.
#: Deve restare il default: un utente che non ha scelto niente non deve
#: accorgersi che qualcuno ha cambiato le regole.
ACCETTA_TUTTO = "everything"


def _preferenza(nome: str, ripiego):
    """C5 · una preferenza dell'add-on, col ripiego dichiarato.

    `get_addon_preferences()` vive nel pacchetto RADICE perché è l'unico posto
    in cui `__package__` è la radice sia da add-on sia da estensione — vedi la
    sua docstring. Torna `None` invece di sollevare, e il ripiego giusto qui è
    sempre «comportati come prima».
    """
    try:
        from .. import get_addon_preferences
    except ImportError as exc:      # DICHIARATO, mai ingoiato (decisione 14)
        print(f"[sync] preferences unreachable ({exc}): using {nome}={ripiego}")
        return ripiego
    prefs = get_addon_preferences()
    if prefs is None:
        return ripiego
    return getattr(prefs, nome, ripiego)


def porta_sidecar() -> int:
    """La porta su cui questo Blender serve il ponte. C5 · è una PREFERENZA
    dell'installazione: dipende da cosa gira su questa macchina, non da quale
    scavo si sta studiando."""
    try:
        return int(_preferenza("sync_port", 8788))
    except (TypeError, ValueError):
        return 8788


def _accept() -> str:
    """Cosa questo Blender accetta in ingresso.

    NOTA MISURATA (12-09-2026), perché il codice non lo lascia vedere: una
    property RNA registrata su `bpy.types.Scene` **non compare mai** in
    `scene.keys()`, nemmeno dopo essere stata scritta — sta nello strato RNA e
    non fra le custom property dell'ID. Quindi il valore che un .blend
    conservava sotto il vecchio `em_sync_direction` non è leggibile da qui, e
    una migrazione di sola lettura è impossibile: chi aveva scelto `off` o
    `send` si ritrova il default. È il verso giusto in cui perdere (il default
    È il comportamento storico), ma va detto.
    """
    try:
        return str(getattr(bpy.context.scene, "em_sync_accept", ACCETTA_TUTTO)
                   or ACCETTA_TUTTO)
    except Exception:  # noqa: BLE001 — nessuna scena (import headless)
        return ACCETTA_TUTTO


def _accetta_selezione() -> bool:
    return _accept() in ("selection", "everything")


def _accetta_operazioni() -> bool:
    return _accept() == "everything"


def _on_accept_commands_changed(self, context):
    """Consent changed → tell the client at once.

    The affordance on the other side is drawn from `host_info`; without this it
    would stay greyed out until the next reconnection, and the user who just
    ticked the box would think the box does nothing.
    """
    try:
        ok, graph = is_graph_available(context)
        _send_host_info(context, graph if ok else None)
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] could not announce the consent change: {exc}")


def _on_accept_changed(self, context):
    """C2 · la politica di ingresso è cambiata → dillo subito all'altro capo.

    Stessa ragione del consenso ai comandi: senza questa riga l'altro capo
    saprebbe cosa rifiuto solo alla riconnessione, e nel frattempo vedrebbe
    sparire i propri messaggi senza sapere perché — cioè esattamente il difetto
    che spostare il cancello in ingresso doveva togliere di mezzo.
    """
    try:
        ok, graph = is_graph_available(context)
        _send_host_info(context, graph if ok else None)
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] could not announce the accept policy: {exc}")


def _accepts_commands() -> bool:
    """CMD1 · does this host let EMStudio act on the scene?

    A separate switch from the sync direction, and OFF by default. Mirroring a
    selection is a reflection; executing a command MODELS IN YOUR SCENE, and the
    stronger act gets the explicit consent — nobody models in somebody else's
    Blender because a socket was open.
    """
    try:
        return bool(getattr(bpy.context.scene, "em_accept_commands", False))
    except Exception:  # noqa: BLE001
        return False


def is_running() -> bool:
    return _server is not None and _server.running


def client_count() -> int:
    return _server.client_count() if _server else 0


# --------------------------------------------------------------------------- #
# helpers (main thread)
# --------------------------------------------------------------------------- #

def _node_id_for_object(obj, graph) -> str | None:
    """Blender object → its graph node's UUID, or None if it is not an EM
    proxy. Name-based (obj name = '<graph_code>.<node.name>')."""
    if obj is None or graph is None:
        return None
    node_name = proxy_name_to_node_name(obj.name)
    finder = getattr(graph, "find_node_by_name", None)
    node = finder(node_name) if callable(finder) else None
    return getattr(node, "node_id", None) if node else None


def _frame_selected():
    """Best-effort 'view selected' in the first 3D viewport."""
    try:
        win = bpy.context.window
        for area in (win.screen.areas if win and win.screen else []):
            if area.type == "VIEW_3D":
                region = next((r for r in area.regions if r.type == "WINDOW"), None)
                if region:
                    with bpy.context.temp_override(area=area, region=region):
                        bpy.ops.view3d.view_selected()
                break
    except Exception:
        pass


def _redraw():
    try:
        for area in bpy.context.screen.areas:
            area.tag_redraw()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════
# NIGHT-RIM/C1 · PRIMA FARLO PARLARE
# ══════════════════════════════════════════════════════════════════════
#
# Il difetto noto: in sidecar, selezionando un proxy in Blender si seleziona
# il nodo in EM Studio, ma non il contrario. La catena in ingresso esiste
# tutta e il trasporto è stato provato in isolamento — quindi il messaggio
# ARRIVA e qualcosa lo scarta. `_handle_message` aveva **quattro** punti in
# cui scarta senza dire niente, e con quattro sospetti muti la diagnosi è
# indovinare.
#
# Quindi prima si fa parlare, poi si cura. Questo diario tiene l'ultimo
# messaggio e il suo esito, e il pannello lo mostra: la diagnosi diventa
# visibile a chi usa e non solo a chi ha la console aperta.
#
# Un dizionario di modulo e non una property di scena: è informazione di
# sessione, non di documento, e non deve finire nel .blend.
ULTIMO_MESSAGGIO = {
    "tipo": "", "esito": "", "ora": "", "chiavi": "", "dettaglio": "",
}


#: C1 · quello che l'ALTRO CAPO ha dichiarato di avere aperto, per questa
#: sessione. Un dizionario di modulo come `ULTIMO_MESSAGGIO` e per la stessa
#: ragione: è informazione di sessione e non di documento, e non deve finire
#: nel .blend di nessuno.
PARI = {}


def dichiarazione_del_pari() -> dict:
    """Cosa ha detto l'altro capo di avere aperto. Vuoto = non ha detto niente,
    che NON è la stessa cosa di «ha detto qualcosa di diverso»."""
    return dict(PARI)


def disallineamento(context=None, graph=None) -> dict:
    """C1 · i due documenti a confronto, per il pannello e per il log.

    Ritorna l'esito di `alignment.confronta`; con nessun pari che ha parlato
    ritorna un esito `noto: False`, cioè «non si conclude niente» — che è
    diverso da «siamo allineati» e va detto diversamente.
    """
    from . import alignment

    if context is None:
        context = bpy.context
    if graph is None:
        ok, graph = is_graph_available(context)
        graph = graph if ok else None
    return alignment.confronta(_documento(context, graph), PARI)


def _annota(tipo, esito, chiavi=(), dettaglio=""):
    """Registra l'esito di un messaggio in ingresso, e lo stampa."""
    import time
    ULTIMO_MESSAGGIO.update({
        "tipo": tipo or "?",
        "esito": esito,
        "ora": time.strftime("%H:%M:%S"),
        "chiavi": ",".join(sorted(chiavi)) if chiavi else "",
        "dettaglio": dettaglio,
    })
    # `print` e non `em_log`: è una diagnosi che qualcuno sta guardando adesso
    # perché qualcosa non funziona, e `em_log` a livello INFO è filtrato.
    coda = f" [{ULTIMO_MESSAGGIO['chiavi']}]" if ULTIMO_MESSAGGIO["chiavi"] else ""
    extra = f" — {dettaglio}" if dettaglio else ""
    print(f"[sync in] {tipo or '?'}: {esito}{coda}{extra}")


def _apply_incoming_select(node_id: str, context, graph) -> bool:
    """Select + frame the object for an incoming node id. Returns True if a
    matching object was selected."""
    finder = getattr(graph, "find_node_by_id", None)
    node = finder(node_id) if callable(finder) else None
    if not node:
        # SCARTO 4 · il nodo non è in questo grafo. Era un `return False`
        # muto, e chi guardava non poteva distinguere «non è arrivato
        # niente» da «è arrivato un id che qui non esiste» — che sono due
        # diagnosi opposte.
        # C1 · …e DOVE ha cercato. «Non c'è» e «stai guardando altrove» sono
        # due diagnosi opposte, e senza il nome del grafo producevano la stessa
        # riga. Se il pari ha dichiarato un documento diverso, la frase lo dice
        # qui — dove il sintomo si manifesta — invece di lasciarlo al pannello.
        dove = _etichetta_del_grafo(graph)
        esito = disallineamento(context, graph)
        coda = f" — {esito['frase']}" if not esito["allineati"] else ""
        _annota("select", f"node_id non trovato in {dove}{coda}",
                dettaglio=str(node_id))
        return False
    select_3D_obj(node.name, context=context, graph=graph)
    _frame_selected()
    return True


def _apply_incoming_select_many(node_ids, active_id, context, graph) -> bool:
    """Select ALL proxies for a peer's multi-selection (mirrors Blender's
    active/selected model): the active node reuses select_3D_obj (deselects
    all, handles visibility, sets it active), the others are added on top."""
    finder = getattr(graph, "find_node_by_id", None)
    if not callable(finder):
        return False
    active_node = finder(active_id) if active_id else None
    #: quanti degli id in arrivo questo grafo conosce davvero. Serve a non
    #: raccontare «select applicato» per una selezione che non ha toccato
    #: niente: con documenti diversi ai due capi è il caso NORMALE, non
    #: l'eccezione, e dirlo bene è metà di C1.
    trovati = 0
    if active_node is not None:
        select_3D_obj(active_node.name, context=context, graph=graph)
        trovati += 1
    else:
        try:
            bpy.ops.object.select_all(action="DESELECT")
        except Exception:
            pass
    for nid in node_ids:
        if nid == active_id:
            continue
        node = finder(nid)
        if node is None:
            continue
        trovati += 1
        obj = bpy.data.objects.get(
            node_name_to_proxy_name(node.name, context=context, graph=graph))
        if obj is not None:
            try:
                obj.select_set(True)
            except Exception:
                pass
    if not trovati:
        dove = _etichetta_del_grafo(graph)
        esito = disallineamento(context, graph)
        coda = f" — {esito['frase']}" if not esito["allineati"] else ""
        _annota("select", f"nessuno dei {len(node_ids)} node_id è in {dove}{coda}",
                dettaglio=str(active_id or ""))
        return False
    _frame_selected()
    return True


def _reflect_in_em_list(context, node, patch: dict):
    """Mirror a node patch onto its EMListItem so the EM panel updates.

    EMListItems are keyed by NAME (the node_id field is frequently empty on
    populated items), so we match name first and fall back to node_id. A
    targeted patch keeps the current selection; a full repopulate
    (populate_blender_lists_from_graph) is the tool for STRUCTURAL ops
    (add/delete) — the lists are a projection of the graph, the s3dgraphy
    multigraph in memory is the source of truth."""
    try:
        units = context.scene.em_tools.stratigraphy.units
    except Exception:
        return
    nid = getattr(node, "node_id", None)
    for item in units:
        if item.name == node.name or (nid and getattr(item, "node_id", "") == nid):
            if "description" in patch:
                item.description = patch["description"]
            return


def _node_from_payload(payload: dict):
    """Build an s3dgraphy Node from an EMStudio node op payload, reusing the
    emjson importer's type-resolving instantiator (degrades to a base Node on
    unknown types)."""
    try:
        from s3dgraphy.importer.emjson_importer import _instantiate
        node = _instantiate(payload.get("node_type", ""), payload, [])
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] node instantiate failed: {exc}")
        return None
    if node is not None and "description" in payload:
        try:
            node.description = payload["description"]
        except Exception:
            pass
    return node


def _repopulate(context, graph):
    """Full rebuild of the Blender EM lists from the graph — the correct tool
    for STRUCTURAL ops (add/delete node/edge); the lists are a projection.

    MUST clear first: populate_blender_lists_from_graph APPENDS (no internal
    clear), so without this repeated calls duplicate every row."""
    try:
        from ..populate_lists import (
            populate_blender_lists_from_graph,
            clear_lists,
        )
        clear_lists(context)
        populate_blender_lists_from_graph(context, graph)
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] repopulate failed: {exc}")


def _apply_op(msg: dict, context, graph):
    """Apply an op-log operation from EMStudio to the live s3dgraphy graph
    (ADR-002 phase 2). Handles update_node (targeted) + structural
    add/delete of nodes and edges (full list repopulate).

    `msg` is the op's BODY (WIRE 2's `payload`), so `msg["source"]` here — if a
    verb ever has one — is the op's own field and nothing else's.""" 
    op = msg.get("op")
    if graph is None:
        return

    if op == "update_node":
        node_id = msg.get("node_id")
        patch = msg.get("patch") or {}
        finder = getattr(graph, "find_node_by_id", None)
        node = finder(node_id) if callable(finder) else None
        if not node or "description" not in patch:
            return
        node.description = patch["description"]
        _reflect_in_em_list(context, node, patch)
        _redraw()
        return

    changed = False
    try:
        if op == "add_node":
            nd = msg.get("node") or {}
            nid = nd.get("id")
            if nid and not graph.find_node_by_id(nid):
                node = _node_from_payload(nd)
                if node is not None:
                    graph.add_node(node, overwrite=True)
                    changed = True
        elif op == "delete_node":
            nid = msg.get("node_id")
            if nid and graph.find_node_by_id(nid):
                graph.remove_node(nid)
                changed = True
        elif op == "add_edge":
            ed = msg.get("edge") or {}
            if ed.get("id") and ed.get("source") and ed.get("target"):
                graph.add_edge(
                    ed["id"], ed["source"], ed["target"],
                    ed.get("edge_type") or "generic_connection")
                changed = True
        elif op == "delete_edge":
            ed = msg.get("edge") or {}
            if ed.get("id"):
                graph.remove_edge(ed["id"])
                changed = True
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] _apply_op {op} failed: {exc}")
        return

    if changed:
        # batched: the actual list rebuild + redraw happen once at the end of
        # the inbox drain (a group op is add_node + N add_edges → 1 rebuild)
        global _pending_repop
        _pending_repop = True


def emit_op(op: dict):
    """Emit a local (Blender-side) graph mutation to connected clients
    (ADR-002 phase 2, reverse direction). No-op when the sync server is off.
    `op` is the BODY of the operation — `{"op": "update_node", "node_id": …,
    "patch": …}`. WIRE 2 puts it inside `payload`, so a field of the op can
    never collide with a word of the envelope (an `add_edge` carries
    `source`/`target` as its endpoints; the wire's `source` is who sent it).

    P4.4 · the same operation goes to the ROOM when we are in one.

    C2 · NOTHING IS HELD BACK HERE ANY MORE. There used to be a `_sends()` gate,
    and it was the wrong place: what this Blender does not send is invisible to
    whoever is waiting for it, and «has not sent» looks exactly like «got lost».
    Whoever does not want this traffic refuses it on arrival, where refusing is
    something they can see themselves doing.
    """
    from .room_session import SESSION

    srv = _server
    if srv is not None and srv.running:
        body = {k: v for k, v in op.items() if k != "type"}
        try:
            srv.broadcast(json.dumps(envelope("op", body, source=_SOURCE)))
        except Exception as exc:  # noqa: BLE001
            print(f"[sync] emit_op failed: {exc}")
    if SESSION.joined:
        try:
            SESSION.send_op(op)
        except Exception as exc:  # noqa: BLE001
            print(f"[room] emit_op failed: {exc}")


def _host_info(context, graph):
    """Describe what this host (Blender/EMtools) is editing so the EMStudio
    client can show it in the footer sidecar badge: tool · document · database.
    All fields optional — a field is omitted when unknown."""
    # CMD1 · the client cannot guess whether commands will be executed, and an
    # affordance that is offered and then refused is worse than one that is
    # greyed out. So the host DECLARES it, and EMStudio reads it.
    # C2 · `accept` è dichiarato accanto agli altri: un cancello in ingresso è
    # meglio di uno in uscita SOLO se l'altro capo può venirne a sapere,
    # altrimenti «ho chiuso» e «il filo è rotto» si somigliano di nuovo.
    info = {"tool": "Blender · EMtools", "accepts_commands": _accepts_commands(),
            "accept": _accept(),
            # C4 · e IN CHE MODO sta lavorando. Quello REALE, non quello
            # dichiarato: all'altro capo serve sapere cosa c'è, non cosa
            # qualcuno ha chiesto.
            "mode": session_mode(context)}
    # CONNECTOR · and the DESCRIPTOR: what this host is, how it can be reached,
    # what it speaks and what it can do — declared before anything happens, so
    # EMStudio's registry can accept it (or refuse it with a reason) instead of
    # discovering at the first write that the two do not understand each other.
    # Same frame as `tool` and `accepts_commands`, which were the first two
    # answers to the same question.
    try:
        from .connector import descriptor as _connector_descriptor
        info["connector"] = _connector_descriptor(
            accepts_commands=info["accepts_commands"])
    except Exception as exc:  # noqa: BLE001
        # A host that cannot describe itself still pairs: the client falls back to
        # what it DOES declare (older peers sent no descriptor at all). Said, not
        # swallowed — a silent absence here would look like a stale EMStudio.
        print(f"[connector] descriptor unavailable: {exc}")
    try:
        em_tools = context.scene.em_tools
        idx = em_tools.active_file_index
        if 0 <= idx < len(em_tools.graphml_files):
            entry = em_tools.graphml_files[idx]
            if getattr(entry, "graphml_path", ""):
                info["file"] = bpy.path.basename(entry.graphml_path)
            emdb = getattr(entry, "emdb_filepath", "")
            if emdb:
                info["database"] = bpy.path.basename(emdb)
    except Exception:  # noqa: BLE001
        pass
    if "file" not in info and graph is not None:
        # no file entry known → fall back to the graph name/id as a label
        label = getattr(graph, "name", None) or getattr(graph, "graph_id", "")
        if label:
            info["label"] = str(label)
    # C1 · WHICH DOCUMENT, said as an ID and not as a file name.
    #
    # `file` above is a basename, and a basename identifies nothing: two people
    # can each have a `TempluMare.em.json` on their own disk and not be on the
    # same document, and a graph that arrived over a socket has no file at all.
    # So the descriptor carries the graph's id — which is what a `node_id`
    # belongs to — and the name stays as the LABEL a human reads.
    info.update(_documento(context, graph))
    return info


def _etichetta_del_grafo(graph) -> str:
    """Come si chiama, per un umano, il grafo in cui abbiamo cercato."""
    from . import alignment
    if graph is None:
        return "no graph loaded here"
    return alignment.etichetta(str(getattr(graph, "graph_id", "") or ""),
                               str(getattr(graph, "name", "") or "")) or "this graph"


def _documento(context, graph) -> dict:
    """What this Blender has open, in the three keys `alignment` compares.

    `graph_ids` is the list of everything loaded, because Blender is
    multigraph: "your document is in my second tab" and "I do not have your
    document at all" are two different situations with two different cures,
    and a single id could not tell them apart.
    """
    from . import alignment

    detto = {}
    ident = str(getattr(graph, "graph_id", "") or "") if graph is not None else ""
    nome = str(getattr(graph, "name", "") or "") if graph is not None else ""
    if ident:
        detto[alignment.CHIAVE_ID] = ident
    if nome:
        detto[alignment.CHIAVE_NOME] = nome
    tutti = []
    try:
        from s3dgraphy import get_graph
        for entry in context.scene.em_tools.graphml_files:
            altro = get_graph(entry.name)
            altro_id = str(getattr(altro, "graph_id", "") or "") if altro else ""
            if altro_id and altro_id not in tutti:
                tutti.append(altro_id)
    except ImportError as exc:
        # DICHIARATO e non ingoiato (decisione 14): senza la libreria l'elenco
        # è vuoto, e un elenco vuoto qui significherebbe «non ho nient'altro» —
        # che è una risposta, non un'assenza di risposta.
        print(f"[sync] s3dgraphy non importabile, elenco dei grafi omesso: {exc}")
        return detto
    except AttributeError:
        return detto            # nessuna scena / nessun em_tools: headless
    if tutti:
        detto[alignment.CHIAVE_TUTTI] = tutti
    return detto


def _send_host_info(context, graph):
    """Push a standalone host_info message (e.g. when the active graph
    changes). EMStudio also accepts `host` piggy-backed on the snapshot."""
    srv = _server
    if srv is None or not srv.running:
        return
    srv.broadcast(json.dumps(
        envelope("host_info", _host_info(context, graph), source=_SOURCE)))


def _send_snapshot(graph, context=None):
    """Host → client: send the active graph as an .em.json doc (ADR-002
    snapshot-READ). Triggered by a client's ``request_snapshot`` on connect —
    this is what makes 'sync mode = see Blender's data'. The host metadata
    (tool/file/database) rides along as `host` for the sidecar badge."""
    srv = _server
    if srv is None or not srv.running or graph is None:
        return
    try:
        from ..emjson_support import graph_to_emjson_dict
        doc = graph_to_emjson_dict(graph)
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] snapshot build failed: {exc}")
        return
    srv.broadcast(json.dumps(envelope(
        "snapshot",
        {"doc": doc, "host": _host_info(context or bpy.context, graph)},
        source=_SOURCE)))


def _handle_message(raw: str, context, graph, ok: bool):
    """Dispatch one inbound message (main thread).

    WIRE 2: the envelope says WHO and WHAT KIND, the payload holds the body. A
    message from another protocol version is refused with a line in the console
    rather than half-read — half-reading a frame is how an edge lost its
    endpoints.
    """
    global _last_active_name, _last_selection
    try:
        msg = json.loads(raw)
    except (ValueError, TypeError):
        return
    if msg.get("source") == _SOURCE:
        # SCARTO 1 · il nostro stesso eco. Giusto scartarlo, ma va detto:
        # se EM Studio spedisse `source: "emtools"` per un suo messaggio,
        # tutto sparirebbe qui e sembrerebbe che non arrivi niente.
        _annota(msg.get("type", "?"), "scartato: source == emtools (eco)",
                chiavi=tuple(msg.keys()))
        return
    try:
        mtype, payload = read(msg)
    except WireError as exc:
        print(f"[sync] refused a message: {exc}")
        return
    # C2 · IL CANCELLO, e sta solo qui. Selezione e operazione sono separate
    # perché sono diverse in natura: una muove il mio viewport, l'altra cambia
    # il mio grafo.
    if ((mtype == "select" and not _accetta_selezione())
            or (mtype == "op" and not _accetta_operazioni())):
        # SCARTO 2 · detto per esteso, col valore vero: «non riceve» non
        # bastava a sapere quale delle due cose stavo rifiutando.
        _annota(mtype, f"scartato: em_sync_accept = {_accept()}",
                chiavi=tuple(payload.keys()))
        return
    if mtype == "select" and ok and (payload.get("node_id") or payload.get("node_ids")):
        node_ids = payload.get("node_ids")
        active_id = payload.get("node_id")
        applicato = False
        if node_ids:
            applicato = _apply_incoming_select_many(node_ids, active_id, context, graph)
            _last_selection = frozenset(node_ids)
        elif active_id:
            applicato = _apply_incoming_select(active_id, context, graph)
            _last_selection = frozenset([active_id])
        # suppress the echo the outbound msgbus callback would otherwise send
        active = getattr(context.view_layer.objects, "active", None)
        _last_active_name = active.name if active else _last_active_name
        # C1 · …e SOLO SE È ANDATA. Questa riga era incondizionata, e riscriveva
        # sopra la diagnosi che `_apply_incoming_select` aveva appena scritto:
        # un id che il grafo non conosce finiva annotato «select applicato».
        # Trovato misurando, non leggendo — è esattamente il caso per cui la
        # strumentazione della prima notte era stata messa, e la strumentazione
        # si cancellava da sola.
        if applicato:
            _annota(mtype, "select applicato", chiavi=tuple(payload.keys()),
                    dettaglio=str(active_id or node_ids))
    elif mtype == "op" and ok:
        _apply_op(payload, context, graph)
    elif mtype == "request_snapshot" and ok:
        _send_snapshot(graph, context)
    elif mtype == "request_save":
        _save_emjson_on_host()
    elif mtype == "command":
        _handle_command(payload, context, graph if ok else None)
        _annota(mtype, "command gestito", chiavi=tuple(payload.keys()))
    elif mtype == "client_info":
        # C1 · L'ALTRA METÀ DELLA STRETTA DI MANO. `host_info` è come questo
        # capo si descrive; `client_info` è come si descrive chi si è
        # collegato — il verbo esiste già nel vocabolario dell'ecosistema
        # (`stratigraph-server/app/ws.py`), quindi non si conia un messaggio
        # nuovo per una domanda che ne aveva già uno.
        #
        # NON è governato dalla politica di ingresso: sapere cosa guarda
        # l'altro non è un eco del suo lavoro, ed è proprio la frase che serve
        # a chi ha chiuso il cancello per capire perché non arriva niente.
        PARI.clear()
        PARI.update({k: v for k, v in payload.items() if v not in (None, "")})
        esito = disallineamento(context, graph if ok else None)
        _annota(mtype,
                esito["frase"] if not esito["allineati"]
                else ("stesso documento" if esito["noto"]
                      else "il pari non dichiara un documento"),
                chiavi=tuple(payload.keys()))
        _redraw()
    elif mtype == "select":
        # SCARTO 3 · era un `select` e non è entrato nel ramo sopra. Le due
        # ragioni possibili sono diversissime e prima erano indistinguibili,
        # perché il messaggio cadeva fuori da tutti gli `elif` senza una
        # riga: o non c'è un grafo caricato, o il payload non porta le
        # chiavi che il ramo pretende (`node_id` / `node_ids`) — una
        # `nodeId` in camelCase finirebbe esattamente qui.
        if not ok:
            _annota(mtype, "scartato: nessun grafo caricato",
                    chiavi=tuple(payload.keys()))
        else:
            _annota(mtype, "scartato: payload senza node_id/node_ids",
                    chiavi=tuple(payload.keys()))
    else:
        _annota(mtype, "nessun ramo lo gestisce",
                chiavi=tuple(payload.keys()))


def _handle_command(msg, context, graph):
    """CMD1 · execute a command from EMStudio (MAIN thread) and answer.

    NOT gated by the sync direction: a command is an explicit act by a person at
    the other end, not an echo, so turning the selection mirror off must not
    silently disable the 3D arm. It is gated by CONSENT, which is a different
    question and has its own switch.

    A refusal is ANSWERED, not swallowed: the client is waiting, and a command
    that vanishes looks exactly like a command that failed.
    """
    from . import commands as cmds

    cmd_id = str(msg.get("cmd_id") or "")
    if not _accepts_commands():
        print(f"[sync] command refused ({msg.get('verb')}): consent is off "
              f"(EM Server ▸ Accept commands from EMStudio)")
        _send_command_result({
            "ok": False, "cmd_id": cmd_id,
            "error": "this host does not accept commands (the Blender user has "
                     "not enabled 'Accept commands from EMStudio')"})
        return
    result = cmds.execute(msg, context, graph)
    _send_command_result(result)
    if result.get("ok"):
        # a command changed the graph: the lists must show it
        global _pending_repop
        _pending_repop = True


def _send_command_result(result):
    srv = _server
    if srv is None or not srv.running:
        return
    try:
        srv.broadcast(json.dumps(
            envelope("command_result", result, source=_SOURCE)))
    except Exception as exc:  # noqa: BLE001
        print(f"[sync] command_result failed: {exc}")


def _save_emjson_on_host():
    """A Sidecar client (EMStudio) is leaving sync and asked us — the host — to
    persist the canonical graph (ADR-002 §4). Save the active graph's em.json
    in place via export.em_save (falls back to a Save-As dialog if the entry
    has no em.json path yet)."""
    try:
        import bpy
        res = bpy.ops.export.em_save()
        print(f"[EMStudio sync] request_save → export.em_save {res}")
    except Exception as exc:  # pragma: no cover — surface in the console
        print(f"[EMStudio sync] request_save failed: {exc}")


# --------------------------------------------------------------------------- #
# INBOUND — one-shot drain (scheduled from the server thread)
# --------------------------------------------------------------------------- #

def _sicuro(raw, context, graph, ok):
    """`_handle_message` che non uccide il ciclo.

    NIGHT-RIM/C1 · `_drain_inbox` è un callback di `bpy.app.timers`, e
    `select_3D_obj` chiama `bpy.ops` e può aprire un popup
    (`functions.py:758,793`). Dentro un timer un'eccezione non finisce a
    video: Blender de-registra il timer e il ciclo in ingresso muore in
    silenzio — dopodiché NESSUN messaggio arriva più, e il sintomo è
    indistinguibile da «il trasporto non funziona».
    """
    try:
        _handle_message(raw, context, graph, ok)
    except Exception as exc:                        # noqa: BLE001
        import traceback
        _annota("?", f"ECCEZIONE: {type(exc).__name__}: {exc}")
        traceback.print_exc()


def _drain_inbox():
    """One-shot timer callback (MAIN thread): drain + apply every queued
    message, then unregister (return None).

    Two sources feed the same drain: the clients connected TO us (the server's
    inbox) and the room we are connected to (P4.4). Deliberately one drain and
    not two — a message is a message, `_handle_message` already dispatches by
    type, and two timers would mean two orders in which the same op could land.
    """
    global _drain_scheduled, _pending_repop
    with _drain_lock:
        _drain_scheduled = False  # cleared first: messages arriving now re-arm
    from . import room_session as _rs
    from .room_session import SESSION
    srv = _server
    if srv is None and not SESSION.joined:
        return None
    context = bpy.context
    ok, graph = is_graph_available(context)
    # C1 · la cintura: è cambiato il documento da quando l'abbiamo detto?
    _forse_annuncia_documento(context)
    _pending_repop = False
    while srv is not None:
        try:
            raw = srv.inbox.get_nowait()
        except Exception:
            break
        _sicuro(raw, context, graph, ok)
    for message in SESSION.drain():
        # C3 · I TRE CASI, adesso distinti invece che scartati insieme.
        #
        # Qui c'era un `continue` su OGNI `select` con un `connection_id`. Non
        # era arbitrario (citava un difetto misurato in P4.3: la selezione
        # altrui non deve muovere la tua) ma buttava via anche il comando
        # diretto. Lo scarto se ne va adesso, e non prima, perché prima la
        # distinzione non esisteva — `room_session.classifica_select` la fa, e
        # il `connection_id` che le serve la stanza lo manda dal join.
        if message.get("type") == "select":
            caso = _rs.classifica_select(message.get("payload"),
                                         SESSION.connection_id)
            if caso != _rs.SELECT_COMANDO:
                _annota("select", f"stanza: {caso} (non muove il viewport)",
                        chiavi=tuple((message.get("payload") or {}).keys()),
                        dettaglio=str((message.get("payload") or {})
                                      .get("connection_id") or ""))
                continue
        _sicuro(json.dumps(message), context, graph, ok)
    if SESSION.joined:
        SESSION.ack()
    if _pending_repop:  # batch: one list rebuild for the whole drained burst
        _repopulate(context, graph)
        _redraw()
        _pending_repop = False
    return None  # one-shot


def _schedule_drain(_payload=None):
    """WsServer on_message callback — runs on the SERVER thread. Only touches
    the guard + bpy.app.timers.register (thread-safe)."""
    global _drain_scheduled
    with _drain_lock:
        if _drain_scheduled:
            return
        _drain_scheduled = True
    try:
        bpy.app.timers.register(_drain_inbox, first_interval=0.0)
    except Exception:
        with _drain_lock:
            _drain_scheduled = False


# --------------------------------------------------------------------------- #
# OUTBOUND — msgbus selection subscription (main thread)
# --------------------------------------------------------------------------- #

def _on_selection_changed(*_args):
    """msgbus notify (MAIN thread): the active object changed → broadcast the
    FULL current selection (active + others), mirroring Blender's model, unless
    it matches what we just applied from an inbound message (echo guard)."""
    global _last_active_name, _last_selection
    srv = _server
    if srv is None or not srv.running:
        return
    # C2 · nessun cancello in uscita: vedi `emit_op`. La selezione parte sempre,
    # e chi non la vuole la rifiuta all'arrivo — dove il rifiuto si vede.
    context = bpy.context
    _forse_annuncia_documento(context)      # C1 · la cintura, l'altro momento
    ok, graph = is_graph_available(context)
    if not ok:
        return
    sel_ids = []
    for obj in getattr(context, "selected_objects", []) or []:
        nid = _node_id_for_object(obj, graph)
        if nid and nid not in sel_ids:
            sel_ids.append(nid)
    sel_set = frozenset(sel_ids)
    if sel_set == _last_selection:
        return  # unchanged — nothing to broadcast (also suppresses our echo)
    _last_selection = sel_set
    active = getattr(context.view_layer.objects, "active", None)
    _last_active_name = active.name if (active and active.select_get()) else None
    active_id = (
        _node_id_for_object(active, graph)
        if (active and active.select_get())
        else (sel_ids[0] if sel_ids else None)
    )
    if not sel_ids and not active_id:
        return
    body = {"node_id": active_id}
    if len(sel_ids) > 1:
        body["node_ids"] = sel_ids
    srv.broadcast(json.dumps(envelope("select", body, source=_SOURCE)))


def _subscribe_selection():
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.LayerObjects, "active"),
        owner=_msgbus_owner,
        args=(),
        notify=_on_selection_changed,
    )


def _unsubscribe_selection():
    try:
        bpy.msgbus.clear_by_owner(_msgbus_owner)
    except Exception:
        pass


#: L'ultimo documento ANNUNCIATO, per non ripetere lo stesso `host_info`.
_documento_annunciato = None


def _forse_annuncia_documento(context=None) -> bool:
    """C1 · se il documento attivo è cambiato da quando l'abbiamo detto, ridillo.

    LA CINTURA, e serve. La strada principale è la sottoscrizione `msgbus` su
    `active_file_index`, ma msgbus è una notifica che Blender **pubblica quando
    gli pare**: in una istanza `-b` non c'è ciclo di UI che la spurghi, e
    misurato è esattamente lì che non arriva. Un avviso di disallineamento che
    dipende da una notifica che può non arrivare è un avviso che a volte non
    c'è — cioè peggio di nessuno, perché il suo silenzio verrebbe letto come
    «siamo allineati».

    Quindi si guarda anche qui, dove il costo è un confronto fra stringhe:
    ogni volta che arriva qualcosa dal pari, e ogni volta che la selezione si
    muove. Sono i due momenti in cui uno dei due capi sta facendo qualcosa, e
    quindi i due momenti in cui sapere di guardare altrove serve davvero.
    """
    global _documento_annunciato
    srv = _server
    if srv is None or not srv.running:
        _documento_annunciato = None
        return False
    context = context or bpy.context
    try:
        ok, graph = is_graph_available(context)
        detto = _documento(context, graph if ok else None)
    except Exception as exc:  # noqa: BLE001 — una nota non ferma il ciclo
        print(f"[sync] could not read the active document: {exc}")
        return False
    impronta = json.dumps(detto, sort_keys=True)
    if impronta == _documento_annunciato:
        return False
    _documento_annunciato = impronta
    _send_host_info(context, graph if ok else None)
    return True


def _on_documento_changed(*_args):
    """C1 · il documento attivo è cambiato → ridillo, subito.

    Senza questa riga il descrittore veniva spedito solo alla connessione (e
    quando cambiava il consenso), quindi cambiare scheda in Blender rendeva la
    barra di stato di EM Studio una fotografia vecchia — e il confronto di C1
    avrebbe confrontato con quella. Un avviso che si basa su un dato stantìo è
    peggio di nessun avviso.
    """
    srv = _server
    if srv is None or not srv.running:
        return
    # La stessa funzione della cintura: due strade, un solo posto che decide,
    # e l'impronta condivisa fa sì che chi arriva secondo non ripeta.
    _forse_annuncia_documento(bpy.context)


def _subscribe_documento():
    """msgbus sull'indice del documento attivo. Sottoscritto solo mentre il
    ponte è servito: fuori da lì non c'è nessuno a cui dirlo."""
    try:
        from ..em_props import EM_Tools
        bpy.msgbus.subscribe_rna(
            key=(EM_Tools, "active_file_index"),
            owner=_msgbus_owner,          # lo stesso proprietario: `_stop` le
            args=(),                      # toglie entrambe con una chiamata
            notify=_on_documento_changed,
        )
    except Exception as exc:  # noqa: BLE001
        # DETTO: senza questa sottoscrizione C1 funziona lo stesso alla
        # connessione, e smette di aggiornarsi quando si cambia scheda. È una
        # degradazione, non un guasto, e va saputa.
        print(f"[sync] no subscription on the active document ({exc}): "
              f"the declared document will only refresh on connect")


# --------------------------------------------------------------------------- #
# lifecycle
# --------------------------------------------------------------------------- #

def _start(port: int):
    global _server, _last_active_name, _last_selection, _drain_scheduled
    global _documento_annunciato
    if is_running():
        return
    _last_active_name = None
    _last_selection = frozenset()
    PARI.clear()              # C1 · una sessione nuova, nessuna dichiarazione
    _documento_annunciato = None
    with _drain_lock:
        _drain_scheduled = False
    srv = WsServer(port=port, on_message=_schedule_drain)
    srv.start()
    _server = srv
    _subscribe_selection()
    _subscribe_documento()


def _stop():
    global _server, _drain_scheduled
    _unsubscribe_selection()
    # C1 · quello che il pari aveva dichiarato vale finché il pari è lì. Un
    # avviso di disallineamento che sopravvive alla disconnessione parlerebbe
    # di una sessione che non esiste più.
    PARI.clear()
    if bpy.app.timers.is_registered(_drain_inbox):
        try:
            bpy.app.timers.unregister(_drain_inbox)
        except ValueError:
            pass
    with _drain_lock:
        _drain_scheduled = False
    if _server:
        _server.stop()
        _server = None


# --------------------------------------------------------------------------- #
# P4.4 · the ROOM (Blender as a client, not only as a host)
# --------------------------------------------------------------------------- #

def room_status(context=None) -> dict:
    """What to show about the room: joined, who else is there, which room."""
    from . import room as room_cfg
    from .room_session import SESSION

    info = room_cfg.room()
    info.update({"joined": SESSION.joined,
                 "room_id": SESSION.room_id or info.get("room_id"),
                 "members": len(SESSION.members),
                 "host": SESSION.host_tool,
                 "author": SESSION.author,
                 "role": SESSION.role,
                 "can_write": SESSION.can_write,
                 "error": SESSION.error})
    return info


#: The three states a session can be in, with the names EMStudio uses. One
#: vocabulary across the two apps: somebody switching between them should not
#: have to learn that "Room" here is "Hub" there.
MODE_STANDALONE = "standalone"
MODE_SIDECAR = "sidecar"
MODE_HUB = "hub"


def session_mode(context=None) -> str:
    """Which mode this Blender is ACTUALLY in — read off reality, every time.

    C4 changes what sits beside this, not this: the mode is now **declared**
    (`em_session_mode`) and the declaration **commands**. But the declaration is
    an order, not a fact, and an order can fail — a room can drop, a port can be
    taken. So this function keeps reading the world, and where the two disagree
    the panel says so instead of one of them quietly winning.

    The order is the precedence, and it is the honest one: being in a room is a
    stronger fact than serving a bridge. After C4 the two are EXCLUSIVE anyway,
    so the precedence only ever decides a moment of transition.
    """
    from .room_session import SESSION

    if SESSION.joined:
        return MODE_HUB
    if is_running():
        return MODE_SIDECAR
    return MODE_STANDALONE


# --------------------------------------------------------------------------- #
# C4 · IL MODO SI DICHIARA E COMANDA
# --------------------------------------------------------------------------- #
#
# `session_mode()` sopra DERIVA il modo, e i tre chip del pannello erano
# disegnati disabilitati: un referto, non un interruttore. Funzionava finché
# c'era un solo modo alla volta per caso — e non c'era: Hub non spegneva il
# sidecar, e i due drenavano la stessa coda.
#
# Adesso il modo è uno stato dichiarato che ESEGUE: scegliere Sidecar accende il
# ponte, Standalone lo spegne, Hub richiede una stanza. I chip continuano a
# mostrare il modo attivo — cioè `session_mode()`, la realtà — ma adesso dicono
# la verità perché la verità è stata dichiarata da qualcuno.
#
# **La transizione è annunciata.** Chi era collegato in sidecar riceve un
# ultimo `host_info` che dice dove sta andando questo Blender, prima che la
# presa si chiuda: staccarsi in silenzio è indistinguibile da un crash, ed è il
# quarto dei silenzi che questa notte esiste per separare.
#
# **QUESTIONE APERTA, e non la decido io** (`questioni-NON-decise.md` §E: «cosa
# succede esattamente a chi era connesso in sidecar quando si passa a Room»).
# Qui c'è il minimo che non la pregiudica: l'altro capo viene AVVISATO, con il
# nome della stanza, e cosa farne — riconnettersi alla stanza, restare
# standalone, aspettare — resta una decisione di E.D. e una riga di EMStudio.

#: Guardia contro la ricorsione: l'`update` di una property che in certi casi
#: riscrive la property stessa (il rifiuto) rientrerebbe qui.
_modo_in_corso = False

SESSION_MODES = (
    (MODE_STANDALONE, "Standalone", "This Blender alone: no bridge, no room"),
    (MODE_SIDECAR, "Sidecar", "Serve the local bridge EMStudio connects to"),
    (MODE_HUB, "Hub", "Work in a room on an StratiGraph Server"),
)


def modo_dichiarato(context=None) -> str:
    """Il modo che qualcuno ha CHIESTO. Diverso da `session_mode()`, che è
    quello che c'è davvero."""
    try:
        sc = (context or bpy.context).scene
        return str(getattr(sc, "em_session_mode", MODE_STANDALONE)
                   or MODE_STANDALONE)
    except Exception:  # noqa: BLE001 — nessuna scena
        return MODE_STANDALONE


def divergenza(context=None) -> str:
    """Una frase quando dichiarato e reale non coincidono, "" quando coincidono.

    Non si "ripara" scrivendo la dichiarazione da un `draw`: una property
    scritta mentre si disegna è un file che diventa sporco da solo, e
    soprattutto cancellerebbe la prova che qualcosa è andato storto. Si dice.
    """
    detto, vero = modo_dichiarato(context), session_mode(context)
    if detto == vero:
        return ""
    return f"declared {detto}, actually {vero}"


def _annuncia_transizione(verso: str, perche: str) -> int:
    """Ultimo `host_info` prima che la presa si chiuda. → quanti erano collegati.

    Riusa il frame che c'è, con una riga in più (`mode`): non si conia un
    messaggio per una notizia che quel descrittore già esiste per dare.

    `broadcast` scrive con `sendall`, quindi il frame è nel buffer del kernel
    prima che `stop()` chiuda: su localhost una close (non un abort) lo
    consegna. Non è una garanzia del protocollo e va detto — ma il caso in cui
    si perde è quello in cui il socket era già morto, dove non c'era niente da
    annunciare.
    """
    srv = _server
    if srv is None or not srv.running:
        return 0
    quanti = srv.client_count()
    if not quanti:
        return 0
    try:
        info = _host_info(bpy.context, None)
        info["mode"] = verso
        info["label"] = perche
        srv.broadcast(json.dumps(envelope("host_info", info, source=_SOURCE)))
    except Exception as exc:  # noqa: BLE001 — l'annuncio non blocca l'uscita
        print(f"[sync] could not announce the transition: {exc}")
    return quanti


def applica_modo(context, richiesto: str) -> dict:
    """C4 · ESEGUE la dichiarazione. → `{'ok', 'message', 'mode'}`.

    Fuori dall'`update` callback perché sia provabile e perché un operatore
    possa chiamarla e riportare la frase. **Non** apre dialoghi: entrare in una
    stanza vuole un token e un indirizzo, e quello resta `em.room_join`.
    """
    from .room_session import SESSION

    vero = session_mode(context)
    if richiesto == vero:
        return {"ok": True, "message": f"already {vero}", "mode": vero}

    if richiesto == MODE_STANDALONE:
        detto = []
        if is_running():
            quanti = _annuncia_transizione(MODE_STANDALONE,
                                           "the host is going standalone")
            _stop()
            detto.append(f"bridge stopped ({quanti} client(s) told)")
        if SESSION.joined:
            leave_room()
            detto.append("left the room")
        return {"ok": True, "message": "; ".join(detto) or "already standalone",
                "mode": MODE_STANDALONE}

    if richiesto == MODE_SIDECAR:
        # ESCLUSIVITÀ · la stanza se ne va prima che il ponte si accenda.
        # Prima i due convivevano e drenavano la stessa coda, il che voleva
        # dire che lo stesso `op` poteva arrivare per due strade con due
        # ordini diversi.
        lasciata = ""
        if SESSION.joined:
            lasciata = str(SESSION.room_id or "the room")
            leave_room()
        port = porta_sidecar()
        try:
            _start(port)
        except OSError as exc:
            return {"ok": False, "mode": session_mode(context),
                    "message": (f"port {port} is not free ({exc}) — "
                                f"choose another one and try again")}
        coda = f" (left {lasciata})" if lasciata else ""
        return {"ok": True, "mode": MODE_SIDECAR,
                "message": f"serving the bridge on {port}{coda}"}

    if richiesto == MODE_HUB:
        if not SESSION.joined:
            # RICHIEDE UNA STANZA, e lo dice invece di fingere. Una
            # dichiarazione che non si può eseguire non si accetta: sarebbe di
            # nuovo un modo che mente, che è esattamente ciò che C4 toglie.
            return {"ok": False, "mode": vero,
                    "message": ("Hub means being in a room: join one first "
                                "(EM Bridge ▸ Open room from link…, or Join a "
                                "room)")}
        if is_running():
            quanti = _annuncia_transizione(
                MODE_HUB, f"the host is moving into the room "
                          f"{SESSION.room_id or ''}".strip())
            _stop()
            return {"ok": True, "mode": MODE_HUB,
                    "message": f"in the room; bridge stopped "
                               f"({quanti} client(s) told)"}
        return {"ok": True, "mode": MODE_HUB, "message": "in the room"}

    return {"ok": False, "mode": vero, "message": f"unknown mode {richiesto!r}"}


def _dichiara(context, modo: str) -> None:
    """Allinea la property dichiarata a un modo che è GIÀ successo.

    Con la guardia alzata, perché qui la transizione l'ha già fatta chi chiama:
    lasciare che l'`update` la rifaccia vorrebbe dire spegnere il ponte che si
    è appena acceso.
    """
    global _modo_in_corso
    _modo_in_corso = True
    try:
        (context or bpy.context).scene.em_session_mode = modo
    except Exception as exc:  # noqa: BLE001 — nessuna scena, o property assente
        print(f"[sync] could not record the declared mode: {exc}")
    finally:
        _modo_in_corso = False


def _on_modo_changed(self, context):
    """`update` della property dichiarata: esegue, e RIFIUTA rimettendo a posto.

    Il rifiuto riscrive la property, quindi rientrerebbe qui: la guardia di
    modulo è il motivo per cui non lo fa.
    """
    global _modo_in_corso
    if _modo_in_corso:
        return
    richiesto = str(getattr(self, "em_session_mode", MODE_STANDALONE))
    _modo_in_corso = True
    try:
        esito = applica_modo(context, richiesto)
        if not esito["ok"]:
            self.em_session_mode = esito["mode"]
        print(f"[sync] mode {richiesto}: {esito['message']}")
        ULTIMA_TRANSIZIONE.update({"ok": esito["ok"],
                                   "message": esito["message"]})
    finally:
        _modo_in_corso = False
    _redraw()


#: L'esito dell'ultima transizione, per il pannello: un `report` da un `update`
#: callback non ha un operatore in cui atterrare, quindi la frase finirebbe solo
#: in console — cioè invisibile a chi ha appena cliccato.
ULTIMA_TRANSIZIONE = {"ok": True, "message": ""}


def _list_adopted_graphs(context) -> list:
    """Give every adopted graph a row in the EM Data Tree, and return the NEW ones.

    The manager holds the graphs; `em_tools.graphml_files` is what the panel
    lists and what `is_graph_available` reads — a row per graph, keyed by
    `graph_id`, because that name is what `get_graph()` is asked for. Without a
    row the session is in the state this function exists to end: loaded and
    invisible.

    The same act the em.json importer performs (`importer_emjson.py`), minus the
    file: a room's document arrives over a socket, so there is no path to
    remember and `graphml_path` stays empty. That is not a gap to fill with the
    temporary file this adoption wrote — it is deleted a few lines later, and a
    row pointing at it would offer a reload that cannot work.

    Idempotent by `graph_id`: re-joining a room must not grow the list.
    """
    em_tools = getattr(context.scene, "em_tools", None)
    if em_tools is None or not hasattr(em_tools, "graphml_files"):
        return []
    from s3dgraphy import get_graph
    from s3dgraphy.container import is_shelf_member
    from s3dgraphy.multigraph.multigraph import multi_graph_manager

    added = []
    for graph_id, graph in multi_graph_manager.graphs.items():
        # The shelf is a graph of LinkNodes, not a project: it has no place in a
        # list of things you can draw.
        if is_shelf_member(graph):
            continue
        if any(row.name == graph_id for row in em_tools.graphml_files):
            continue
        row = em_tools.graphml_files.add()
        row.name = graph_id
        row.graphml_path = ""
        if hasattr(row, "file_format"):
            row.file_format = "EMJSON"
        attrs = getattr(graph, "attributes", {}) or {}
        if "graph_code" in attrs and hasattr(row, "graph_code"):
            row.graph_code = attrs["graph_code"]
        added.append(graph_id)

    # An index pointing nowhere is the same failure as an empty list, and a
    # session that had rows already may be pointing at one of them — so only
    # move it when it is not currently on something that resolves.
    index = getattr(em_tools, "active_file_index", -1)
    rows = em_tools.graphml_files
    if not (0 <= index < len(rows) and get_graph(rows[index].name) is not None):
        for i, row in enumerate(rows):
            if get_graph(row.name) is not None:
                em_tools.active_file_index = i
                break
    return added


def _count_for_active_row(context, graph) -> None:
    """Refresh the row's cached counters (US/USV · Epochs · Properties · Documents).

    The panel reads those numbers off the row, not off the graph, and the
    importer fills them at import. Without this the tree lists the graph and its
    units and then heads the panel with four zeros — which is the same wrong
    answer the empty tree gave, in smaller type.
    """
    em_tools = getattr(context.scene, "em_tools", None)
    if em_tools is None:
        return
    index = getattr(em_tools, "active_file_index", -1)
    if not (0 <= index < len(em_tools.graphml_files)):
        return
    try:
        from ..populate_lists import update_graph_statistics
        update_graph_statistics(context, graph, em_tools.graphml_files[index])
    except Exception as exc:  # noqa: BLE001 — a count is not worth an adoption
        print(f"[sync] could not refresh the graph statistics: {exc}")


def _adoption_note(graph, listed: list, overwritten: int, warnings: int) -> str:
    """What the adoption actually did, in the words of what changed.

    The old message said "N node(s) merged", where N counted only the nodes
    OVERWRITTEN by UUID — so a room whose six units were all new reported
    "0 node(s) merged" over a successful adoption. It was true and it read as a
    failure, which is the worst kind of accurate.
    """
    what = []
    if graph is not None:
        name = getattr(graph, "graph_id", "?")
        what.append(f"«{name}»: {len(getattr(graph, 'nodes', []) or [])} node(s), "
                    f"{len(getattr(graph, 'edges', []) or [])} edge(s)")
    if listed:
        what.append(f"{len(listed)} graph(s) added to the EM Data Tree")
    what.append(f"{overwritten} node(s) overwritten by UUID")
    what.append(f"{warnings} warning(s)")
    return "adopted the room's document — " + " · ".join(what)


def _adopt_snapshot(doc: dict, context) -> str:
    """Take the room's document into this Blender — or say why we did not.

    A room snapshot is a **container** (several graphs + the shelf), and it is
    merged, never substituted: merging is the offline "integrate later" and the
    less expensive mistake, while replacing a populated session would throw away
    work that is only in this .blend.

    **The geometry.** Adoption reads the document; the models the document
    describes are fetched by their own act — `em.materialise_geometry`, the
    consuming half of DP-76 (`materialise.py`). It is an action and not a
    consequence, for the same reason the command channel is opt-in: downloading
    somebody's meshes into your file is more than reading their graph. Whoever
    wants it at adoption time says so once, with
    the add-on preference `materialise_on_adopt`, and this honours it — with the
    same rules as the manual action (resident only, embargo skipped with a
    reason, content-addressed so it never duplicates).

    **Declared limit.** The merge lands in the multigraph manager, which is what
    the lists and the 3D scene are drawn from; a session that already holds
    graphs therefore has to be repopulated.
    """
    import json as _json
    import tempfile

    if not isinstance(doc, dict) or not doc:
        return "the room sent no document"
    path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".em.json", delete=False,
                                         encoding="utf-8") as handle:
            _json.dump(doc, handle, ensure_ascii=False)
            path = handle.name
        from ..emjson_support import merge_container_from_emjson
        report, warnings = merge_container_from_emjson(path)
        # `merged_nodes` is a COUNT in the library we run against (measured:
        # s3dgraphy 1.6.0.dev14 returns 14, an int) and was a list of ids in
        # earlier ones. `len()` on the int raised inside this try, so the whole
        # adoption reported "could not adopt the room's document: object of type
        # 'int' has no len()" — after the merge had already succeeded. Read both
        # shapes: a number in a message is not worth failing an adoption for.
        merged = getattr(report, "merged_nodes", 0)
        overwritten = merged if isinstance(merged, int) else len(merged or [])
        # THE MERGE IS NOT THE ARRIVAL. `merge_container_from_emjson` writes into
        # the multigraph manager; the EM Data Tree is drawn from
        # `em_tools.graphml_files`, and `is_graph_available` asks THAT list. In a
        # Blender that was empty the list has no rows, so the check said no, the
        # repopulate never ran, and the panel offered "Add graph" over six units
        # that were already loaded. Registering the graphs is what makes the
        # adoption visible — and it is the same act the importer performs.
        listed = _list_adopted_graphs(context)
        ok, graph = is_graph_available(context)
        if ok:
            _repopulate(context, graph)
            _count_for_active_row(context, graph)
            _redraw()
        note = _adoption_note(graph if ok else None, listed, overwritten,
                              len(warnings))
        # …and, only if somebody asked for it, the geometry (DP-76). A failure
        # here must not undo an adoption that worked: the document IS adopted,
        # and the meshes are a second act reported beside it.
        if ok and bool(_preferenza("materialise_on_adopt", False)):
            try:
                from .materialise import materialise, summarise
                note += " · geometry: " + summarise(materialise(graph))
            except Exception as exc:  # noqa: BLE001 — said, never fatal
                note += f" · geometry not materialised: {exc}"
        return note
    except Exception as exc:  # noqa: BLE001 — a failed adoption must be SAID
        return f"could not adopt the room's document: {exc}"
    finally:
        if path:
            try:
                import os
                os.remove(path)
            except OSError:
                pass


def join_room(context, base_url: str, room_id: str, token: str,
              adopt: bool = True) -> dict:
    """Enter a room: connect, read the arrival, optionally adopt the document.

    Returns `{ok, message, plan, …}`. The token is handed to `room.py`, which
    keeps it in memory for this session and never writes it anywhere.
    """
    from . import room as room_cfg
    from .room_session import SESSION

    room_cfg.set_room(base_url, room_id, token)
    try:
        arrival = SESSION.join(since=SESSION.last_applied)
    except Exception as exc:  # noqa: BLE001 — the reason belongs to the user
        return {"ok": False, "message": str(exc)}
    # C4 · ESCLUSIVITÀ, e DOPO che la stanza ha risposto: spegnere il ponte
    # prima significherebbe che un join fallito lascia questo Blender senza
    # niente — staccato dal sidecar E fuori dalla stanza, per un indirizzo
    # sbagliato. Chi era collegato viene avvisato con la stanza per nome prima
    # che la presa si chiuda.
    #
    # Cosa EM Studio debba FARE di quell'avviso è la questione aperta §E e non
    # la decido io: qui c'è il minimo che non la pregiudica, cioè che lo sappia.
    congedati = 0
    if is_running():
        congedati = _annuncia_transizione(
            MODE_HUB, f"the host is moving into the room {room_id}")
        _stop()
    _schedule_drain()
    SESSION.client._on_message = lambda _raw: _schedule_drain()

    note = ""
    if adopt and arrival.get("snapshot"):
        note = _adopt_snapshot(
            (arrival["snapshot"].get("payload") or {}).get("doc") or {}, context)
    plan = arrival.get("plan")
    if plan == "resync" and SESSION.last_applied:
        # a REBASE, not a first arrival: the two look the same to `plan_rejoin`
        # (no base and an old base both mean "take the document"), but only one
        # of them is worth telling the user about
        # the room has compacted past our base: replaying our history would
        # re-assert facts that were already settled and forgotten
        note = (note + " · " if note else "") + \
            "re-synced from the room's document (our base was older than its " \
            "compaction point)"
    if congedati:
        note = (note + " · " if note else "") + \
            f"the bridge stopped and {congedati} sidecar client(s) were told"
    _dichiara(context, MODE_HUB)
    return {"ok": True, "plan": plan, "room": SESSION.room_id,
            "members": len(SESSION.members), "host": SESSION.host_tool,
            "message": note or "joined"}


def join_manual(context, base: str, room_id: str, token: str, *,
                adopt: bool = True, sign_in_with=None) -> dict:
    """The "…or by hand" door — which now signs in by itself.

    The LAST place a person saw a token. The link door has done its own OIDC for
    a while (`handoff.sign_in`, loopback + PKCE, stdlib only); this one still
    asked for a pasted one, so the credential a person had to find, copy and
    carry existed purely because two doors into the same room were wired
    differently.

    The rule, and the order matters:

    * a token PASTED wins. It is the declared fallback for a node in a trench
      with no browser, and signing in over the top of somebody's deliberate
      paste would be the tool overruling them;
    * empty + the server has OIDC → sign in, and join with what comes back;
    * empty + no OIDC → join without one, which is what an open node expects.
      Reported rather than silent: an open node and a sign-in that never ran
      are indistinguishable from the outside, and "it worked on my laptop" is
      what that ambiguity produces.

    Returns `join_room`'s dict plus `signed_in` — how the token was obtained, so
    the operator can say it and a test can assert it. `sign_in_with` is the seam
    the suite uses; the default is the real round trip, which needs a browser and
    a person.
    """
    pasted = str(token or "").strip()
    signed_in = "pasted" if pasted else None
    if not pasted:
        from . import handoff

        try:
            got = (sign_in_with or handoff.sign_in)(base)
        except Exception as exc:  # noqa: BLE001 — the realm, the network, a timeout
            return {"ok": False, "signed_in": "failed",
                    "message": f"sign-in did not complete: {exc}"}
        if got:
            pasted, signed_in = got, "signed-in"
        else:
            # No OIDC on that node: not an error, and SAID by the caller.
            signed_in = "open-node"

    result = join_room(context, base, room_id, pasted, adopt=adopt)
    result["signed_in"] = signed_in
    return result


def leave_room() -> None:
    from . import room as room_cfg
    from .room_session import SESSION

    SESSION.leave()
    room_cfg.forget_token()      # the credential goes when the membership does
    # C4 · e la dichiarazione segue il fatto. Senza questa riga il pannello
    # direbbe «declared hub, actually standalone» per una stanza che abbiamo
    # lasciato noi — una divergenza vera segnalata per un motivo falso, che è
    # il modo più rapido di rendere inutile la segnalazione.
    _dichiara(None, session_mode())


class EM_OT_server_probe(bpy.types.Operator):
    """Ask the address in the field what it is — before trying to join it.

    A URL somebody typed is a hope; `/v1/health` turns it into a fact, and the
    failures are the useful half (refused, no such host, a TLS the OS does not
    trust). Reported, never raised: "check this address" must be a thing you can
    do twice."""

    bl_idname = "em.server_probe"
    bl_label = "Probe this server"

    def execute(self, context):
        from . import servers

        answer = servers.probe(getattr(context.scene, "em_room_url", ""))
        if answer.get("ok"):
            self.report({"INFO"},
                        f"{answer['url']} — {answer.get('service')} "
                        f"{answer.get('version')} · auth: {answer.get('auth')} · "
                        f"{answer.get('rooms')} room(s)")
            servers.remember(answer["url"], answer.get("service") or "")
        else:
            self.report({"WARNING"},
                        f"{answer.get('url')}: {answer.get('error')}")
        return {"FINISHED"}


class EM_OT_server_discover(bpy.types.Operator):
    """Find an StratiGraph Server on this network — by asking, not by browsing.

    Blender's Python has no `zeroconf`, so there is no mDNS browsing here and
    none is simulated. What this does is probe the addresses that are worth
    trying (this machine, this machine's Bonjour name) and remember whatever
    answers. The other Mac is reached as `<name>.local`, which the operating
    system resolves without any library."""

    bl_idname = "em.server_discover"
    bl_label = "Find a server"

    def execute(self, context):
        from . import servers

        result = servers.discover()
        for found in result["found"]:
            servers.remember(found["url"], found.get("service") or "")
        if result["found"]:
            context.scene.em_room_url = result["found"][0]["url"]
            self.report({"INFO"},
                        f"found {len(result['found'])}: "
                        + ", ".join(f["url"] for f in result["found"]))
        else:
            self.report({"WARNING"},
                        "nothing answered on this machine or its Bonjour name — "
                        "type the address of the server you were given")
        if result.get("browsing_unavailable"):
            print("[em] " + result["browsing_unavailable"])
        return {"FINISHED"}


class EM_OT_server_use(bpy.types.Operator):
    """Put a saved server in the field."""

    bl_idname = "em.server_use"
    bl_label = "Use this server"

    url: bpy.props.StringProperty(default="")  # type: ignore

    def execute(self, context):
        context.scene.em_room_url = self.url
        return {"FINISHED"}


class EM_OT_server_forget(bpy.types.Operator):
    """Take a server off the saved list. The list is this installation's, not
    the .blend's, so this does not touch anybody's project."""

    bl_idname = "em.server_forget"
    bl_label = "Forget this server"

    url: bpy.props.StringProperty(default="")  # type: ignore

    def execute(self, context):
        from . import servers

        servers.forget(self.url)
        return {"FINISHED"}


class EM_OT_room_join(bpy.types.Operator):
    bl_idname = "em.room_join"
    bl_label = "Join / leave an EM room"
    bl_description = ("Connect this Blender to an StratiGraph Server room: adopt its "
                      "document, send and receive edits, publish models into "
                      "its store")

    token: bpy.props.StringProperty(
        name="Token", default="", subtype="PASSWORD",
        description=("Leave EMPTY to sign in through your browser — that is the "
                     "ordinary way now. Fill it in only when this machine has no "
                     "browser to sign in with. Either way it is kept in memory "
                     "for this session and never written to the .blend or to disk"))
    adopt: bpy.props.BoolProperty(
        name="Adopt the room's document", default=True,
        description=("Merge what the room holds into this session (additive — "
                     "nothing here is replaced)"))

    def invoke(self, context, event):
        from .room_session import SESSION
        if SESSION.joined:
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from .room_session import SESSION
        if SESSION.joined:
            leave_room()
            self.report({"INFO"}, "left the room (token forgotten)")
            return {"FINISHED"}
        base = str(getattr(context.scene, "em_room_url", "") or "").strip()
        room_id = str(getattr(context.scene, "em_room_id", "") or "").strip()
        if not base or not room_id:
            self.report({"ERROR"}, "set the room address and id first")
            return {"CANCELLED"}
        # An empty token no longer means "no identity": it means "sign me in".
        # See `join_manual` for why a pasted one still wins.
        result = join_manual(context, base, room_id, self.token,
                             adopt=self.adopt)
        self.token = ""          # not even in the operator's own memory
        if not result["ok"]:
            self.report({"ERROR"}, result["message"])
            return {"CANCELLED"}
        if result.get("signed_in") == "open-node":
            # said, because an open node and a sign-in that never ran look the
            # same from here — the same sentence the link door reports
            self.report({"INFO"},
                        f"{base} has no sign-in configured (running open) — "
                        f"joined without a token")
        self.report({"INFO"}, f"room {result['room']}: {result['message']}")
        return {"FINISHED"}


class EM_OT_room_open_link(bpy.types.Operator):
    """Open a room from a HANDOFF LINK — the fourth consumer of one contract.

    `stratigraph://open?server=<addr>&room=<id>`, produced by the room browser on
    a StratiGraph Server (and by the Catalog for a study). It kills the manual
    configuration: no address to type, no room name, and above all no token to
    paste — the link carries a PLACE and never a permission, and this signs in
    against that server itself (`handoff.py`, PKCE, token in memory).

    **Nothing new is built here.** The link supplies `{server, room}`, the
    sign-in supplies the token, and `join_room` does exactly what it always did.

    The manual fields stay, and are the declared fallback: a node in a trench with
    no browser signs in with neither this nor a realm, and taking that away to
    make a point would break the honest case.
    """

    bl_idname = "em.room_open_link"
    bl_label = "Open room from link"
    bl_description = ("Paste a stratigraph:// handoff link: EMtools reads the "
                      "server and the room from it, signs you in, and joins — "
                      "no address, no room name, no token to type")

    link: bpy.props.StringProperty(
        name="Link", default="",
        description="stratigraph://open?server=…&room=… (it carries no token)")
    adopt: bpy.props.BoolProperty(
        name="Adopt the room's document", default=True,
        description=("Merge what the room holds into this session (additive — "
                     "nothing here is replaced)"))

    def invoke(self, context, event):
        if not self.link:
            # a link is usually on the clipboard: that is how it arrived
            try:
                pasted = str(context.window_manager.clipboard or "").strip()
            except Exception:  # noqa: BLE001 — no clipboard on some builds
                pasted = ""
            if pasted.startswith("stratigraph://"):
                self.link = pasted
        return context.window_manager.invoke_props_dialog(self, width=520)

    def execute(self, context):
        from . import handoff

        try:
            where = handoff.resolve(self.link)
        except handoff.HandoffError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        except Exception as exc:  # noqa: BLE001 — the network, the realm
            self.report({"ERROR"}, f"sign-in did not complete: {exc}")
            return {"CANCELLED"}

        # …and the panel now SHOWS where we are, so the fallback fields and the
        # live session never disagree about which room this is
        context.scene.em_room_url = where["server"]
        context.scene.em_room_id = where["room"]
        token = where.get("token") or ""
        if not token:
            # a node running open: not an error, but SAID — otherwise a working
            # laptop is indistinguishable from a token flow that never ran
            self.report({"INFO"},
                        f"{where['server']} has no sign-in configured "
                        f"(running open) — joining without a token")
        result = join_room(context, where["server"], where["room"], token,
                           adopt=self.adopt)
        self.link = ""            # not even in the operator's own memory
        if not result["ok"]:
            self.report({"ERROR"}, result["message"])
            return {"CANCELLED"}
        self.report({"INFO"}, f"room {result['room']}: {result['message']}")
        return {"FINISHED"}


class EM_OT_room_open_elsewhere(bpy.types.Operator):
    """Hand THIS room to EMStudio — the round-trip, emit half.

    Not an export and not a transfer: the graph lives in the room, so opening it
    in EMStudio is another client joining the same room. Whatever is on screen
    here is already there.

    **Emit-only, and that is a decision rather than an omission.** Receiving a
    link INSIDE Blender is a job of its own — Blender is not a URL-scheme
    handler, so it needs a registered launcher or the `ws_server` this addon
    already exposes — and half of it, offered as if it worked, would be the
    worse half.

    The link is asked for, never assembled: `GET /v1/rooms/{id}/open`, one
    grammar on the server. It carries no token; EMStudio signs itself in.
    """

    bl_idname = "em.room_open_elsewhere"
    bl_label = "Open room in EMStudio"
    bl_description = ("Open the SAME room in EMStudio — the graph is the "
                      "room's, so nothing is transferred and nothing is saved")

    @classmethod
    def poll(cls, context):
        from .room_session import SESSION
        return bool(SESSION.joined)

    def execute(self, context):
        import webbrowser

        from . import handoff
        from . import room as room_cfg

        state = room_cfg.room()
        base, room_id = state.get("base_url"), state.get("room_id")
        if not base or not room_id:
            self.report({"ERROR"}, "not in a room: there is nothing to open elsewhere")
            return {"CANCELLED"}

        targets = handoff.open_targets(base, room_id,
                                       token=room_cfg._session.get("token"))
        if targets is None:
            self.report({"ERROR"},
                        "could not reach the node to ask how this room opens")
            return {"CANCELLED"}
        if targets.get("detail"):
            self.report({"ERROR"}, str(targets["detail"]))
            return {"CANCELLED"}
        try:
            door = handoff.emstudio_link(targets)
        except handoff.HandoffError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        if not door["link"]:
            self.report({"ERROR"},
                        "this node does not say how to open EMStudio")
            return {"CANCELLED"}

        # `webbrowser` for BOTH doors: it is what hands a `stratigraph://` URL to
        # the OS handler as well as an https one to a tab. Blender's own Python
        # has nothing better, and this keeps the two paths one line.
        webbrowser.open(door["link"])
        where = ("EMStudio for the web" if door["kind"] == "browser"
                 else "EMStudio on this machine")
        self.report({"INFO"}, f"opening room {room_id} in {where} — "
                              f"same room, nothing transferred")
        return {"FINISHED"}


class EM_OT_sync_toggle(bpy.types.Operator):
    bl_idname = "em.sync_toggle"
    bl_label = "Toggle EMStudio Sync"
    bl_description = "Start/stop the WebSocket server EMStudio connects to for live selection sync"

    def execute(self, context):
        # C4 · UNA SOLA STRADA. Questo bottone c'era prima della dichiarazione
        # del modo, e lasciarlo accendere il ponte per conto suo vorrebbe dire
        # due meccanismi per lo stesso fatto — cioè la coabitazione con la
        # stanza che C4 esiste per togliere. Adesso è una scorciatoia per la
        # stessa regola, e la regola annuncia, spegne l'altra metà e dichiara.
        verso = MODE_STANDALONE if is_running() else MODE_SIDECAR
        esito = applica_modo(context, verso)
        if not esito["ok"]:
            self.report({"ERROR"}, esito["message"])
            return {"CANCELLED"}
        _dichiara(context, esito["mode"])
        self.report({"INFO"}, esito["message"])
        return {"FINISHED"}


class EM_OT_set_mode(bpy.types.Operator):
    """C4 · dichiara il modo, da un menu.

    Un operatore e non `layout.prop` nel menu: la property ha un `update` che
    può RIFIUTARE (Hub senza stanza), e un rifiuto ha bisogno di un posto dove
    atterrare. `layout.prop` non ne ha uno — la frase finirebbe in console,
    cioè invisibile a chi ha appena scelto — mentre un operatore ha `report`.
    """

    bl_idname = "em.set_mode"
    bl_label = "Set the session mode"
    bl_description = ("Standalone, Sidecar or Hub. Choosing one DOES it: "
                      "Sidecar starts the bridge, Standalone stops it, Hub "
                      "needs a room you have already joined")

    mode: bpy.props.StringProperty(default="")  # type: ignore

    def execute(self, context):
        esito = applica_modo(context, self.mode)
        if not esito["ok"]:
            self.report({"WARNING"}, esito["message"])
            ULTIMA_TRANSIZIONE.update(esito)
            return {"CANCELLED"}
        _dichiara(context, esito["mode"])
        ULTIMA_TRANSIZIONE.update(esito)
        self.report({"INFO"}, esito["message"])
        return {"FINISHED"}


def register():
    # C4 · il modo DICHIARATO. Non è una fotografia dello stato — quella la dà
    # `session_mode()` — ma l'ordine che qualcuno ha dato, e che `_on_modo_changed`
    # esegue. Sta sulla scena e non nelle preferenze perché «in che modo sto
    # lavorando su questo progetto» è una proprietà della sessione su QUESTO
    # documento, non dell'installazione.
    if not hasattr(bpy.types.Scene, "em_session_mode"):
        bpy.types.Scene.em_session_mode = bpy.props.EnumProperty(
            name="Mode",
            items=SESSION_MODES,
            default=MODE_STANDALONE,
            description=("Standalone, Sidecar or Hub. Choosing one DOES it: "
                         "Sidecar starts the bridge, Standalone stops it, Hub "
                         "needs a room you have already joined"),
            update=_on_modo_changed)
    if not hasattr(bpy.types.Scene, "em_sync_accept"):
        bpy.types.Scene.em_sync_accept = bpy.props.EnumProperty(
            name="Accept from EMStudio",
            items=SYNC_ACCEPT,
            default=ACCETTA_TUTTO,
            description=(
                "What EMStudio is allowed to land in THIS Blender. Nothing "
                "leaves this side gated any more: what you do not send is "
                "invisible to whoever is waiting for it, and refusing on "
                "arrival is something you can see yourself doing"),
            update=_on_accept_changed)
    if not hasattr(bpy.types.Scene, "em_accept_commands"):
        bpy.types.Scene.em_accept_commands = bpy.props.BoolProperty(
            name="Accept commands from EMStudio",
            default=False,
            description=(
                "Let EMStudio act on THIS scene (model a proxy, import a "
                "geometry). Off by default: a command changes your scene, which "
                "is more than mirroring a selection"),
            update=_on_accept_commands_changed)
    # P4.4 · the room. The address and the id are saved with the project (they
    # are not secrets and re-typing them every session is friction); the TOKEN
    # is not a property at all — it lives in memory in `room.py`, because a
    # credential saved in a .blend travels with every copy of that .blend.
    if not hasattr(bpy.types.Scene, "em_room_url"):
        bpy.types.Scene.em_room_url = bpy.props.StringProperty(
            name="Room server", default="",
            description="Address of the StratiGraph Server holding the room "
                        "(e.g. https://em.example.org)")
    if not hasattr(bpy.types.Scene, "em_room_id"):
        bpy.types.Scene.em_room_id = bpy.props.StringProperty(
            name="Room", default="",
            description="Which room on that server")
    bpy.utils.register_class(EM_OT_sync_toggle)
    bpy.utils.register_class(EM_OT_set_mode)
    bpy.utils.register_class(EM_OT_room_join)
    bpy.utils.register_class(EM_OT_room_open_link)
    bpy.utils.register_class(EM_OT_room_open_elsewhere)
    bpy.utils.register_class(EM_OT_server_probe)
    bpy.utils.register_class(EM_OT_server_discover)
    bpy.utils.register_class(EM_OT_server_use)
    bpy.utils.register_class(EM_OT_server_forget)


def unregister():
    _stop()
    try:
        leave_room()
    except Exception:  # noqa: BLE001 — unregistering must not fail on a socket
        pass
    for cls in (EM_OT_server_forget, EM_OT_server_use, EM_OT_server_discover,
                EM_OT_server_probe):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001 — unregistering must not fail
            pass
    bpy.utils.unregister_class(EM_OT_room_open_elsewhere)
    bpy.utils.unregister_class(EM_OT_room_open_link)
    bpy.utils.unregister_class(EM_OT_room_join)
    bpy.utils.unregister_class(EM_OT_sync_toggle)
    try:
        bpy.utils.unregister_class(EM_OT_set_mode)
    except Exception:  # noqa: BLE001 — unregistering must not fail
        pass
    if hasattr(bpy.types.Scene, "em_room_url"):
        del bpy.types.Scene.em_room_url
    if hasattr(bpy.types.Scene, "em_room_id"):
        del bpy.types.Scene.em_room_id
    if hasattr(bpy.types.Scene, "em_session_mode"):
        del bpy.types.Scene.em_session_mode
    if hasattr(bpy.types.Scene, "em_sync_accept"):
        del bpy.types.Scene.em_sync_accept
    if hasattr(bpy.types.Scene, "em_accept_commands"):
        del bpy.types.Scene.em_accept_commands
