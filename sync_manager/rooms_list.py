"""R1 · the rooms of a node, as a LIST — instead of a field to type a name into.

MICRO-LA-BARRA-E-LE-STANZE. Every tool asks the same place, `GET /v1/rooms`, with
its own access and its own node, and shows the same three things: «Your rooms»
(you are the owner), «Shared with you» (with the role you have there), and
«+ New room». Measured on the dev node before writing a line (3 Oct 2026): the
answer is a JSON list of `{room_id, title, owner, members, your_role, implicit,
archived_at, container_refs, missing_refs}`, and `your_role` is one of
owner/admin/editor/viewer — so the node already distinguishes owner and role,
and nothing here has to guess it.

No `bpy`: the fetch, the grouping and the id rule are plain Python, measured by
`tests/test_rooms_list.py` against a real node in dev mode; the panel and the
operators (`operators.py`) only draw and dispatch.

**The id is derived from the name, never typed twice.** `room_id_from_name`
(now in s3Dgraphy's `room_import.node`, with `create_room`, `room_info`,
`send_ops`) is
the SAME rule as the node's front door (`app/rooms_ui/rooms.js::createRoom`) and
EMStudio's `rooms.ts::roomIdFromName`, and the parity vector the server's
`tests/test_room_id_parity.py` pins is asserted here too — a third door that
derived it differently would turn one name into two rooms.
"""

from __future__ import annotations

import urllib.request
from typing import Any, Dict, List, Optional

# The room's record and its operations are the room importer's (s3Dgraphy,
# `room_import.node`, moved there on 15 Oct 2026): imported here, so the
# callers of `rooms_list.create_room` & co. reach the one implementation.
from s3dgraphy.room_import.node import (OPS_PER_REQUEST, _call, _url,  # noqa: F401
                                        create_room, room_id_from_name,
                                        room_info, send_ops)
from s3dgraphy.room_import.node import _json_headers as _headers

from .room import RoomError


#: The roles a room can give, from `GET /v1/rooms` (`your_role`). The order is
#: the one a list shows them in.
ROLES = ("owner", "admin", "editor", "viewer")

#: The two groups of the list, and what decides them: ownership, nothing else.
GROUP_MINE = "mine"
GROUP_SHARED = "shared"


def list_rooms(base: str, token: Optional[str], *,
               timeout: float = 15.0) -> List[Dict[str, Any]]:
    """`GET {node}/v1/rooms` with this access — the rooms THIS identity can see."""
    request = urllib.request.Request(_url(base, "/v1/rooms"), method="GET",
                                     headers=_headers(token))
    answer = _call(request, timeout)
    if not isinstance(answer, list):
        raise RoomError("the node's room list is not a list — is this a "
                        "StratiGraph Server?")
    return [r for r in answer if isinstance(r, dict) and r.get("room_id")]


def group_of(room: Dict[str, Any]) -> str:
    """«Your rooms» are the ones you OWN; every other role is shared with you."""
    return GROUP_MINE if str(room.get("your_role") or "") == "owner" else GROUP_SHARED


def matches(room: Dict[str, Any], text: str) -> bool:
    """The filter: the words typed, in the id or the title, case-insensitive."""
    words = (text or "").strip().lower().split()
    if not words:
        return True
    haystack = f"{room.get('room_id') or ''} {room.get('title') or ''}".lower()
    return all(word in haystack for word in words)


def group_rooms(rooms: List[Dict[str, Any]], *, filter_text: str = "",
                include_archived: bool = False) -> Dict[str, List[Dict[str, Any]]]:
    """`{mine: […], shared: […]}`, each sorted by title then id.

    Archived rooms are left out unless asked: an archived room is not a place
    to go and work, and 361 rooms on the dev node are noisy enough already.
    """
    out: Dict[str, List[Dict[str, Any]]] = {GROUP_MINE: [], GROUP_SHARED: []}
    for room in rooms:
        if room.get("archived_at") and not include_archived:
            continue
        if not matches(room, filter_text):
            continue
        out[group_of(room)].append(room)
    for bucket in out.values():
        bucket.sort(key=lambda r: (str(r.get("title") or r.get("room_id")).lower(),
                                   str(r.get("room_id"))))
    return out


def summary(groups: Dict[str, List[Dict[str, Any]]]) -> str:
    """One line: how many in each group."""
    return (f"{len(groups.get(GROUP_MINE) or [])} yours · "
            f"{len(groups.get(GROUP_SHARED) or [])} shared with you")
