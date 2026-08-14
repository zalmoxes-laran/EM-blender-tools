"""The wire ENVELOPE — and why the body travels nested inside it.

The same file as `em-server/app/wire.py` and `EMStudio/src/wire.ts`. Three
speakers, one rule, kept small enough to state three times: a shared module
across three repositories would be a fourth dependency for a hundred lines of
agreement, and the day the three disagree is the day a test says so.

ADR-002 gave the ecosystem one protocol; every message used to be one flat
object: `{v, type, source, …the body's fields…}`. That is a **shared namespace**
between two vocabularies that have nothing to do with each other, and it bites
exactly where you cannot see it:

    {"v": 1, "type": "op", "source": "emstudio",
     "op": "add_edge", "source": "reg-1", "target": "US1"}
                        ↑ the WIRE's "who sent this"
                        ↑ …and the EDGE's "where it starts"

The relay stripped `source` (correct: the origin tag is its own business) and an
edge arrived with `source: None`. It applied, it was broadcast, and the only
trace was a load warning about an edge whose ends do not exist — much later, and
somewhere else. A per-verb exception in `ws.py` cured that symptom; **this cures
the cause**.

From WIRE 2 the envelope carries only what the TRANSPORT owns:

    {"v": 2, "type": "op", "source": "emstudio", "payload": {…the body…}}

and the payload is **opaque to the relay**: it is forwarded verbatim, and no
field inside it can ever collide with a word the wire uses. A new verb with a
field called `type`, `v` or `source` is now simply a field.

**Version handling is a refusal, not a guess.** A speaker on WIRE 1 is told so;
it is not half-understood. There are no external clients, so nobody has to
migrate — but the day somebody's old build connects, it gets a sentence instead
of an edge with no ends.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

#: The protocol version. Bumped 1 → 2 when the body moved inside `payload`.
WIRE = 2

#: The keys the ENVELOPE owns. Everything else about a message lives in
#: `payload`, and this tuple is the whole boundary between the two vocabularies.
ENVELOPE_KEYS = ("v", "type", "source", "room_id", "graph_id", "payload")


class WireError(ValueError):
    """A message this speaker cannot read, with a sentence saying why."""


def envelope(kind: str, payload: Optional[Dict[str, Any]] = None, *,
             source: str, **routing: Any) -> Dict[str, Any]:
    """Build one wire message.

    `routing` is for the few things the transport itself needs to look at
    (`graph_id`: which section of the container an op belongs to). They stay
    OUTSIDE the payload on purpose — the relay reads them, so they are the
    wire's words, not the body's.
    """
    message: Dict[str, Any] = {"v": WIRE, "type": kind, "source": source}
    for key, value in routing.items():
        if value is not None:
            message[key] = value
    message["payload"] = dict(payload or {})
    return message


def read(message: Any) -> Tuple[str, Dict[str, Any]]:
    """`(type, payload)` from a message, or raise :class:`WireError`.

    The version check happens HERE, once, for every speaker in this process:
    a message from another version is refused by name rather than partially
    understood.
    """
    if not isinstance(message, dict):
        raise WireError("a wire message must be a JSON object")
    version = message.get("v")
    if version != WIRE:
        raise WireError(
            f"this speaker talks wire v{WIRE} and the message says v{version!r}. "
            f"From v2 the body of a message travels nested under `payload` "
            f"instead of spread across the envelope — update the client.")
    kind = str(message.get("type") or "")
    if not kind:
        raise WireError("a wire message must say its `type`")
    payload = message.get("payload")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise WireError(f"the payload of a {kind!r} message must be an object")
    return kind, payload
