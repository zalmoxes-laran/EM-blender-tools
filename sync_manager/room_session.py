"""P4.4 · Blender JOINS a room — the second role, beside being a host.

Until now EMtools was only a host: it opened a socket and EMStudio connected to
it, which means the study lived in somebody's Blender and everybody else had to
wait for that laptop. A **room** (StratiGraph Server) inverts it — the study is in a place
several people reach at once — and this module is Blender taking a seat there.

The wire is the one that already exists (ADR-002): the room speaks `host_info`,
`snapshot`, `presence`, `op`, `select`. Nothing new was invented for this, which
is the whole point of P4.2 having made the relay "just another host".

Three things are decided here, and only here:

* **the join** — connect, then read the three frames the room always sends
  (`host_info`, `snapshot`, `presence`) before anything else. Knowing the shape
  of the arrival is what lets a client say "I am in" instead of guessing.
* **the rebase** — the room announces `gc_watermark`, the point up to which its
  history has been compacted and forgotten. A client whose own base is OLDER
  cannot replay: what it would re-assert has already been settled. It re-syncs
  from the snapshot instead. This is `planRejoin` in EMStudio's `hub.ts`, and
  the two implementations must agree, so the rule is written the same way.
* **the ack** — "I have applied everything up to here". It is what makes the
  room's compaction safe: a client that never acks holds the GC back, which is
  the failure direction we want.

No `bpy` here: this decides and queues, the caller applies on the main thread.
The token lives in `room.py`, in memory only, and is passed as a header — never
written anywhere, never included in what this module can print.
"""

from __future__ import annotations

import json
import queue
import threading
from typing import Any, Callable, Dict, List, Optional

from . import room
from ..sync_bridge.wire import WIRE, WireError, envelope, read
from ..sync_bridge.ws_client import WsClient, WsClientError

#: The wire version lives in `sync_bridge/wire.py` — one definition for both
#: roles of this addon (the server it runs and this client), so a bump cannot be
#: half-applied.

#: What this client calls itself on the room's roster…
CLIENT_TOOL = "EMtools (Blender)"
#: …and on the wire, which is the tag the echo guard compares.
CLIENT_SOURCE = "emtools"


#: C3 · i tre esiti possibili di un `select` che arriva da una stanza.
SELECT_COMANDO = "command"
SELECT_ECO = "echo"
SELECT_AWARENESS = "awareness"


def classifica_select(payload: Optional[Dict[str, Any]],
                      mio_connection_id: Optional[str]) -> str:
    """C3 · di chi è questa selezione, e quindi cosa farne.

    Fino a stanotte i tre casi erano scartati insieme: `operators._drain_inbox`
    buttava via OGNI `select` che portasse un `connection_id`. Non era
    arbitrario — il commento citava un difetto misurato in P4.3, «la selezione
    altrui non deve muovere la tua» — ma era una rete a maglie troppo larghe,
    perché sotto c'erano tre fatti diversi:

    * **comando** — nessun `connection_id`: nessuno lo ha marcato come
      awareness di qualcuno, quindi è un ordine diretto (il sidecar parla
      così) e deve passare;
    * **eco** — il `connection_id` è il MIO: è la mia stessa selezione che
      torna indietro, e applicarla sarebbe un giro a vuoto;
    * **awareness** — il `connection_id` è di un altro: è dove sta guardando
      lui, e non deve muovere il mio viewport.

    Il `connection_id` non va inventato: `stratigraph-server/app/ws.py:466` lo
    conia al join e `:474` lo rimanda, e `RoomSession._absorb` lo conserva già.

    MISURATO, e cambia cosa ci si deve aspettare: il server **salta il
    mittente** nel fanout (`_fanout(..., skip=member.connection_id)`), quindi
    da una stanza il caso «eco» non arriva mai davvero. Resta scritto lo stesso,
    e non per simmetria: è l'unica riga che rende la regola leggibile senza
    conoscere il fanout del server, e un relay che smettesse di saltare il
    mittente troverebbe qui la guardia invece di un viewport che sobbalza.
    """
    chi = str((payload or {}).get("connection_id") or "")
    if not chi:
        return SELECT_COMANDO
    if mio_connection_id and chi == str(mio_connection_id):
        return SELECT_ECO
    return SELECT_AWARENESS


def stamp_for_resend(pending: List[Dict[str, Any]], now: str) -> List[Dict[str, Any]]:
    """P1 · the unconfirmed work, re-stamped for a re-send after a re-sync.

    `stampForResend` of EMStudio's `hub.ts`, written the same way: everything
    that had not been answered comes back, **the emptyings included** — the
    clock is refreshed (the room settled everything before its compaction
    point, so an old stamp would simply lose) and `remove: true` is carried
    through untouched, because it is what makes an emptying an act and not an
    absence the merge may overrule.
    """
    out = []
    for entry in pending:
        op = dict(entry.get("op") or {})
        op["ts"] = now
        out.append({**entry, "op": op})
    return out


def plan_rejoin(base: Optional[str], gc_watermark: Optional[str]) -> str:
    """`resume` or `resync` — the one rule, written the same way on both ends.

    A base at or after the watermark can carry on: the room still remembers
    everything since. A base BEFORE it cannot — the room has compacted past that
    point, so the client's unsent history refers to a world nobody keeps any
    more, and replaying it would re-assert settled facts. Having no base at all
    is a first join, which is a resync by definition.
    """
    if not base:
        return "resync"
    if not gc_watermark:
        return "resume"
    return "resume" if str(base) >= str(gc_watermark) else "resync"


def _op_key(op: Dict[str, Any]) -> tuple:
    """What identifies an operation across its trip (the room adds the author
    and the access mode, never changes these)."""
    return (op.get("op"), op.get("id") or op.get("node_id"), op.get("field"),
            op.get("source"), op.get("target"), op.get("edge_type"))


class RoomSession:
    """One membership in one room, for the length of this Blender session."""

    def __init__(self, on_message: Optional[Callable[[str], None]] = None) -> None:
        self.client: Optional[WsClient] = None
        self.inbox: "queue.Queue[str]" = queue.Queue()
        self._on_message = on_message
        self._lock = threading.Lock()

        # what the room told us on arrival
        self.room_id: Optional[str] = None
        self.connection_id: Optional[str] = None
        self.author: Optional[str] = None
        self.host_tool: Optional[str] = None
        self.gc_watermark: Optional[str] = None
        self.members: List[Dict[str, Any]] = []
        self.last_applied: Optional[str] = None
        self.error: Optional[str] = None
        #: P5 · what this client MAY DO here, as the room resolved it at the
        #: door (owner/admin/editor/viewer). Believed rather than assumed: a
        #: panel that offers editing which the server refuses reads as a broken
        #: addon instead of as a study somebody let you read.
        self.role: Optional[str] = None
        self.can_write: bool = True
        #: G1 (5 Oct 2026, I-2) · THE GRAPHS OF THE ROOM'S STUDY, as its
        #: document holds them (set when the room's graphs are adopted), and the
        #: one the edits are for (`activate`). An operation names its graph
        #: only when the room has it: a room seeded from this scene holds one
        #: graph under its own id, and naming the local id there would be
        #: refused, where today the op lands on the room's graph.
        self.room_graphs: set = set()
        self.writing_graph: Optional[str] = None
        #: I1 · the sync, counted off the room's answers: every operation sent
        #: gets one `op_result` (or a `denied`). Counted per membership.
        self.sent_ops: int = 0
        self.answered_ops: int = 0
        self.refused_ops: int = 0
        #: P1 · THE WORK THE ROOM HAS NOT CONFIRMED, in the order it was done:
        #: `{op, graph_id, sent}`. An operation enters when it is made and
        #: leaves when the room answers it (`op_result`, or a `denied` that is
        #: not a lapsed token) — so a connection that drops loses nothing: what
        #: was not sent and what was sent without an answer go back at the
        #: re-entry (`resend_unconfirmed`). Before P1 `send_op` returned False
        #: on a closed socket and nobody counted it: the edit was lost for the
        #: room, and the panel said nothing.
        self.unconfirmed: List[Dict[str, Any]] = []
        #: P1 · in a room until LEFT: a connection that drops keeps the seat,
        #: and the edits made meanwhile wait in `unconfirmed` for the re-entry.
        self.seated: bool = False
        self.base_url: Optional[str] = None

    # ── joining ──────────────────────────────────────────────────────────────

    @property
    def joined(self) -> bool:
        return self.client is not None and self.client.connected

    def join(self, *, since: Optional[str] = None, timeout: float = 10.0
             ) -> Dict[str, Any]:
        """Connect and read the arrival. Returns `{host_info, snapshot, plan}`.

        `since` is this client's own base — the timestamp it has applied up to.
        It is sent so the room can replay what was missed, and compared with the
        room's watermark to decide whether replaying is even meaningful.
        """
        if self.joined:
            raise WsClientError("already in a room — leave it first")
        url = room.ws_url("ws")
        if since:
            url += f"?since={since}"
        headers = {}
        token = room._session.get("token")        # never stored, never printed
        try:
            from . import access                  # X1 · renewed, not stale
            token = access.fresh(token)
        except ImportError:                       # loaded by path (the suite)
            pass
        if token:
            headers["Authorization"] = f"Bearer {token}"
        client = WsClient(url, headers=headers, on_message=self._receive)
        client.connect(timeout=timeout)
        self.sent_ops = self.answered_ops = self.refused_ops = 0
        # P1 · what was sent before the drop and never answered is NOT
        # answered by this connection: it goes back with the rest
        for entry in self.unconfirmed:
            entry["sent"] = False
        self.client = client
        self.seated = True
        here = room.room()
        self.base_url = here.get("base_url")
        self.room_id = self.room_id or here.get("room_id")
        # ONE queue, the client's: two would mean two answers to "what has
        # arrived", and the drain would race the join
        self.inbox = client.inbox

        arrival: Dict[str, Any] = {}
        # the room always sends three frames on join, in this order; reading them
        # here is what makes "I am in" a fact rather than an assumption
        for _ in range(3):
            try:
                raw = self.inbox.get(timeout=timeout)
            except queue.Empty:
                self.leave()
                raise WsClientError("the room accepted the connection but never "
                                    "sent its snapshot")
            message = self._parse(raw)
            kind = str(message.get("type") or "")
            arrival[kind] = message
            if kind == "snapshot":
                body = message.get("payload") or {}
                self.gc_watermark = body.get("gc_watermark") or self.gc_watermark
        plan = plan_rejoin(since, self.gc_watermark)
        return {"host_info": arrival.get("host_info"),
                "snapshot": arrival.get("snapshot"),
                "presence": arrival.get("presence"),
                "plan": plan}

    def leave(self) -> None:
        client, self.client = self.client, None
        if client is not None:
            client.close()
        # P1 · leaving is not dropping: the seat goes. What the room had not
        # confirmed stays on this object for the caller to keep (`park`).
        self.seated = False
        self.connection_id = None
        self.members = []
        self.role = None
        self.can_write = True
        self.sent_ops = self.answered_ops = self.refused_ops = 0

    # ── traffic ──────────────────────────────────────────────────────────────

    def send(self, kind: str, payload: Optional[Dict[str, Any]] = None,
             **routing: Any) -> bool:
        """One message: an envelope with the body nested inside it (WIRE 2)."""
        client = self.client
        if client is None or not client.connected:
            return False
        message = envelope(kind, payload or {}, source=CLIENT_SOURCE, **routing)
        return client.send(json.dumps(message, ensure_ascii=False))

    @property
    def offline(self) -> bool:
        """P1 · in a room whose connection has dropped: the edits wait."""
        return self.seated and not self.joined

    def waiting(self) -> int:
        """P1 · how many edits the room has not confirmed yet."""
        return len(self.unconfirmed)

    def send_op(self, op: Dict[str, Any]) -> bool:
        """Send one operation. The AUTHOR is not ours to declare.

        Whatever this client writes in `author`, the relay replaces it with the
        token's identity — so it is not sent at all. An author a client can name
        is an author anybody can borrow (P4.1b: the stamp is what the merge
        trusts).
        """
        # The author is dropped, not renamed: whatever this client writes there,
        # the relay replaces it with the token's identity. `source`/`target` are
        # NOT touched — in an edge op they are the endpoints, and since WIRE 2
        # they live in the payload where no envelope word can reach them.
        body = {k: v for k, v in op.items() if k not in ("author", "type")}
        # G1 · the graph in the ENVELOPE, the wire's word (the server reads it,
        # `ws.py`): the room holds the study, the op says which graph
        graph = self.writing_graph if self.writing_graph in self.room_graphs else None
        # P1 · it is the room's work until the room answers it, sent or not
        entry = {"op": body, "graph_id": graph, "sent": False}
        self.unconfirmed.append(entry)
        return self._send_entry(entry)

    def _send_entry(self, entry: Dict[str, Any]) -> bool:
        sent = self.send("op", entry["op"], graph_id=entry.get("graph_id"))
        if sent:
            entry["sent"] = True
            self.sent_ops += 1
        return sent

    def resend_unconfirmed(self, plan: str, now: str) -> int:
        """P1 · send again what the room has not confirmed. → how many went.

        `resume`: as it was — the room still remembers everything since our
        base, so the original clock is the true one (and an op it had already
        applied comes back as idempotent, not as news). `resync`: re-stamped
        (`stamp_for_resend`), the emptyings kept. The entries stay in
        `unconfirmed` until their answers arrive.
        """
        if plan == "resync":
            self.unconfirmed = stamp_for_resend(self.unconfirmed, now)
        went = 0
        for entry in self.unconfirmed:
            entry["sent"] = False
            if self._send_entry(entry):
                went += 1
        return went

    def _confirm(self, body: Dict[str, Any], *, lapsed: bool = False) -> None:
        """P1 · the room answered the oldest operation sent and not answered.

        One socket answers in order (`ws.py` handles a member's frames one at a
        time), so the oldest sent entry is the one answered; the op the room
        echoes is used to check it when it can. A token that lapsed is not an
        answer: the op goes back to waiting and is sent at the re-entry.
        """
        sent = [e for e in self.unconfirmed if e.get("sent")]
        if not sent:
            return
        echoed = body.get("op") if isinstance(body.get("op"), dict) else None
        entry = sent[0]
        if echoed:
            key = _op_key(echoed)
            entry = next((e for e in sent if _op_key(e["op"]) == key), sent[0])
        if lapsed:
            entry["sent"] = False
            return
        self.unconfirmed.remove(entry)

    def send_select(self, node_ids: List[str], active: Optional[str] = None) -> bool:
        """Awareness, never a lock: the others see where you are looking."""
        return self.send("select", {"node_ids": list(node_ids),
                                    "node_id": active})

    def request_snapshot(self) -> bool:
        return self.send("request_snapshot")

    def ack(self, ts: Optional[str] = None) -> bool:
        """Tell the room how far we have applied — what makes its GC safe."""
        stamp = ts or self.last_applied
        return self.send("ack", {"ts": stamp}) if stamp else False

    # ── inbound ──────────────────────────────────────────────────────────────

    def _parse(self, raw: str) -> Dict[str, Any]:
        """The message as it arrived, with the envelope CHECKED.

        A frame from another protocol version becomes an `error` this session
        can show, not a half-read message: a client that guesses at a version it
        does not speak is how an edge arrives without its endpoints.
        """
        try:
            message = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        if not isinstance(message, dict):
            return {}
        try:
            read(message)
        except WireError as exc:
            self.error = str(exc)
            return {}
        self._absorb(message)
        return message

    def _absorb(self, message: Dict[str, Any]) -> None:
        """Keep the few facts about the ROOM that the session owns."""
        kind = str(message.get("type") or "")
        body = message.get("payload") or {}
        if kind == "host_info":
            self.room_id = body.get("room") or self.room_id
            self.connection_id = body.get("connection_id")
            self.author = body.get("author")
            self.host_tool = body.get("tool")
            self.role = body.get("role") or self.role
            # a host that says nothing is writable: every EMtools pairing, where
            # the question does not arise
            self.can_write = bool(body.get("can_write", True))
            self.gc_watermark = body.get("gc_watermark") or self.gc_watermark
        elif kind == "presence":
            members = body.get("members")
            self.members = list(members) if isinstance(members, list) else []
        elif kind == "op":
            ts = body.get("ts")
            if ts and (self.last_applied is None or str(ts) > str(self.last_applied)):
                self.last_applied = str(ts)
        elif kind == "op_result":
            # I1 · the room's answer to one of OUR operations
            self._confirm(body)
            self.answered_ops += 1
            # P1 · an op of ours the room APPLIED is part of what we have
            # applied: the base moves with it. Without this a Blender that only
            # writes never had a base (the room does not echo the sender), and
            # every re-entry was a re-sync with every edit re-stamped.
            mine = body.get("op") if isinstance(body.get("op"), dict) else {}
            ts = mine.get("ts")
            if body.get("applied") and ts and (self.last_applied is None
                                               or str(ts) > str(self.last_applied)):
                self.last_applied = str(ts)
            if not body.get("applied"):
                from s3dgraphy.crdt import refusal_is_news
                if refusal_is_news(str(body.get("reason") or "")):
                    self.refused_ops += 1
        elif kind == "denied" and body.get("verb") == "op":
            self._confirm(body, lapsed="expired" in str(body.get("reason") or ""))
            self.answered_ops += 1
            self.refused_ops += 1
        elif kind == "error":
            self.error = str(body.get("detail") or "")

    def _receive(self, raw: str) -> None:
        """Reader-thread callback: queue and notify. Touches no bpy."""
        if self._on_message is not None:
            try:
                self._on_message(raw)
            except Exception:  # noqa: BLE001 — a callback must not kill the reader
                pass

    def drain(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Everything received since the last drain, parsed. MAIN thread.

        Bounded on purpose: a client that has been away for a long time gets a
        long replay, and blocking Blender's UI while applying all of it at once
        is how a sync feature earns the reputation of freezing the program.
        """
        out: List[Dict[str, Any]] = []
        for _ in range(limit):
            try:
                raw = self.inbox.get_nowait()
            except queue.Empty:
                break
            message = self._parse(raw)
            if message:
                out.append(message)
        return out


#: The session of the ACTIVE graph — the room the edits go to.
#:
#: M2 · a scene can hold several graphs, and with «one room = one graph» (D-A)
#: each can live in its own room: Tempio Grande in one, the temple beside it in
#: another. An operation does not name its graph, so the rule that keeps that
#: honest is ONE SESSION PER GRAPH: what arrives from a room applies to that
#: room's graph, and what is edited goes to the room of the graph being edited.
#: `SESSION` stays the name every caller already reads (always through
#: `from .room_session import SESSION` inside a function, so rebinding it here
#: is seen at the next call); `activate()` points it at the active graph's room.
SESSION = RoomSession()

#: graph_id → its session, and where that room is (the token in memory only,
#: like `room._session`: never in a Scene property, never in the .blend).
_by_graph: Dict[str, RoomSession] = {}
_where: Dict[str, Dict[str, Optional[str]]] = {}


def bind(graph_id: str, session: RoomSession, base_url: Optional[str],
         room_id: Optional[str], token: Optional[str] = None) -> None:
    """This graph lives in this room, through this session."""
    if not graph_id:
        return
    _by_graph[graph_id] = session
    _where[graph_id] = {"base_url": (base_url or "").rstrip("/") or None,
                        "room_id": room_id or None, "token": token}


def graph_of_message(session: RoomSession, message: Dict[str, Any]) -> Optional[str]:
    """G1 · the graph an operation from the room is for: the one its envelope
    names, when it is a graph of the room's study; None otherwise (a frame from
    a peer that does not name graphs, or a room seeded from this scene), and
    then the caller keeps the graph the session is bound to (D-A)."""
    named = message.get("graph_id")
    return str(named) if named and str(named) in session.room_graphs else None


def unbind_session(session: RoomSession) -> List[str]:
    """Forget the graphs a session served (it left its room). Returns them."""
    gone = [g for g, s in _by_graph.items() if s is session]
    for g in gone:
        _by_graph.pop(g, None)
        _where.pop(g, None)
    return gone


def session_of(graph_id: Optional[str]) -> Optional[RoomSession]:
    return _by_graph.get(graph_id or "")


def where_of(graph_id: Optional[str]) -> Dict[str, Optional[str]]:
    """`{base_url, room_id}` of a graph's room — without the token."""
    w = _where.get(graph_id or "") or {}
    return {"base_url": w.get("base_url"), "room_id": w.get("room_id")}


def sessions() -> List[Any]:
    """`[(graph_id or None, session)]`: every bound session once, and the active
    one if it is not bound (a room joined before its graph arrived)."""
    out: List[Any] = []
    seen = set()
    for gid, s in _by_graph.items():
        if id(s) not in seen:
            seen.add(id(s))
            out.append((gid, s))
    if id(SESSION) not in seen:
        out.append((None, SESSION))
    return out


def any_joined() -> bool:
    return any(s.joined for _g, s in sessions())


def fresh_for_join() -> RoomSession:
    """The session a NEW join should use. The active one if it is free;
    otherwise a new one, so the room already joined (another graph's) stays."""
    global SESSION
    if SESSION.joined:
        SESSION = RoomSession(on_message=SESSION._on_message)
    return SESSION


def activate(graph_id: Optional[str]) -> RoomSession:
    """Make `graph_id`'s room the one the edits go to.

    A graph in a room: its session becomes `SESSION` and the REST address
    (`room._session`) points at its room, token included. A graph in no room:
    `SESSION` becomes a session in no room — its edits must not reach another
    graph's room — and the REST address is left as it was (the room list and
    «Find a server» read it). A joined session that is bound to no graph is
    never orphaned: it stays active.
    """
    global SESSION
    if SESSION.joined and SESSION not in _by_graph.values():
        return SESSION
    target = _by_graph.get(graph_id or "")
    if target is not None:
        SESSION = target
        target.writing_graph = graph_id
        w = _where.get(graph_id or "") or {}
        room.set_room(w.get("base_url"), w.get("room_id"), w.get("token"))
    elif SESSION in _by_graph.values():
        SESSION = RoomSession(on_message=SESSION._on_message)
    return SESSION


# ── P1 · the work waiting for a room this Blender is not in ─────────────────
#
# A session holds its own unconfirmed edits while it is seated, connected or
# not. When it LEAVES (or the file is saved), they are parked here by room, with
# the base the session had applied up to, and saved in the .blend
# (`operators._save_unconfirmed`): the next entry into the same room takes them
# back and sends them — as they were if the room still remembers our base, re-
# stamped if it has compacted past it (`plan_rejoin`).

_parked: Dict[str, Dict[str, Any]] = {}


def room_key(base_url: Optional[str], room_id: Optional[str]) -> str:
    return f"{(base_url or '').rstrip('/')}|{room_id or ''}"


def park(session: RoomSession) -> int:
    """Keep what `session` had not got confirmed, for its room. → how many."""
    if not session.unconfirmed or not session.room_id:
        return 0
    key = room_key(session.base_url, session.room_id)
    kept = _parked.setdefault(key, {"base": session.last_applied, "ops": []})
    kept["ops"].extend({**e, "sent": False} for e in session.unconfirmed)
    if session.last_applied and (not kept.get("base")
                                 or str(session.last_applied) > str(kept["base"])):
        kept["base"] = session.last_applied
    count = len(session.unconfirmed)
    session.unconfirmed = []
    return count


def take_parked(base_url: Optional[str], room_id: Optional[str]
                ) -> Dict[str, Any]:
    """The work parked for this room, removed from the park (`{base, ops}`)."""
    return _parked.pop(room_key(base_url, room_id), None) or {"base": None,
                                                              "ops": []}


def parked_for(base_url: Optional[str], room_id: Optional[str]) -> int:
    return len((_parked.get(room_key(base_url, room_id)) or {}).get("ops") or [])


def unconfirmed_state() -> Dict[str, Dict[str, Any]]:
    """Everything waiting, by room — the parked AND every seated session's —
    in the shape the .blend keeps (`{key: {base, ops}}`)."""
    state = {k: {"base": v.get("base"), "ops": [dict(e) for e in v["ops"]]}
             for k, v in _parked.items() if v.get("ops")}
    for _gid, s in sessions():
        if s.unconfirmed and s.room_id:
            key = room_key(s.base_url, s.room_id)
            kept = state.setdefault(key, {"base": s.last_applied, "ops": []})
            kept["ops"].extend({**e, "sent": False} for e in s.unconfirmed)
            kept["base"] = kept.get("base") or s.last_applied
    return state


def restore_unconfirmed(state: Any) -> int:
    """Put back what a .blend kept (`unconfirmed_state`'s shape). → how many."""
    _parked.clear()
    count = 0
    if not isinstance(state, dict):
        return 0
    for key, kept in state.items():
        ops = [e for e in (kept or {}).get("ops") or []
               if isinstance(e, dict) and isinstance(e.get("op"), dict)]
        if ops:
            _parked[str(key)] = {"base": (kept or {}).get("base"),
                                 "ops": [{**e, "sent": False} for e in ops]}
            count += len(ops)
    return count


def waiting_total() -> int:
    """P1 · every edit no room has confirmed yet, parked or seated."""
    return (sum(len(v.get("ops") or []) for v in _parked.values())
            + sum(s.waiting() for _g, s in sessions()))
