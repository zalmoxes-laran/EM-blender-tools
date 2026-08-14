"""P4.4 · Blender JOINS a room — the second role, beside being a host.

Until now EMtools was only a host: it opened a socket and EMStudio connected to
it, which means the study lived in somebody's Blender and everybody else had to
wait for that laptop. A **room** (em-server) inverts it — the study is in a place
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
        if token:
            headers["Authorization"] = f"Bearer {token}"
        client = WsClient(url, headers=headers, on_message=self._receive)
        client.connect(timeout=timeout)
        self.client = client
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
        self.connection_id = None
        self.members = []

    # ── traffic ──────────────────────────────────────────────────────────────

    def send(self, kind: str, payload: Optional[Dict[str, Any]] = None,
             **routing: Any) -> bool:
        """One message: an envelope with the body nested inside it (WIRE 2)."""
        client = self.client
        if client is None or not client.connected:
            return False
        message = envelope(kind, payload or {}, source=CLIENT_SOURCE, **routing)
        return client.send(json.dumps(message, ensure_ascii=False))

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
        return self.send("op", body)

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
            self.gc_watermark = body.get("gc_watermark") or self.gc_watermark
        elif kind == "presence":
            members = body.get("members")
            self.members = list(members) if isinstance(members, list) else []
        elif kind == "op":
            ts = body.get("ts")
            if ts and (self.last_applied is None or str(ts) > str(self.last_applied)):
                self.last_applied = str(ts)
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


#: The session of THIS Blender. One room at a time, deliberately: a client in two
#: rooms would have to say which one every operation belongs to, and nobody has
#: asked for that yet.
SESSION = RoomSession()
