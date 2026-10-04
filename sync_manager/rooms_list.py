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

**The id is derived from the name, never typed twice.** `room_id_from_name` is
the SAME rule as the node's front door (`app/rooms_ui/rooms.js::createRoom`) and
EMStudio's `rooms.ts::roomIdFromName`, and the parity vector the server's
`tests/test_room_id_parity.py` pins is asserted here too — a third door that
derived it differently would turn one name into two rooms.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .room import RoomError


def _urlopen(request, timeout=None):
    """Every call to a node verifies TLS against what this computer trusts
    (`trust.py`: the dev node behind Caddy included)."""
    try:
        from .trust import urlopen
    except ImportError:          # loaded by path, outside the package (the suite)
        import urllib.request
        return urllib.request.urlopen(request, timeout=timeout)
    return urlopen(request, timeout=timeout)

#: The roles a room can give, from `GET /v1/rooms` (`your_role`). The order is
#: the one a list shows them in.
ROLES = ("owner", "admin", "editor", "viewer")

#: The two groups of the list, and what decides them: ownership, nothing else.
GROUP_MINE = "mine"
GROUP_SHARED = "shared"


def room_id_from_name(name: str) -> str:
    """The room id a NAME produces — the shared rule, character for character.

    `trim → lower → runs of [^a-z0-9] become "-" → one leading/trailing "-" off →
    first 60`. The trim happens BEFORE the cut, so a 60-char cut can leave a
    trailing dash: a quirk the other two doors have too, pinned on purpose (see
    the parity vector). Empty when the name has nothing usable — the caller
    refuses then, as EMStudio does, instead of inventing `room-<timestamp>`.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower())
    slug = re.sub(r"^-|-$", "", slug)
    return slug[:60]


def _url(base: str, path: str) -> str:
    base = (base or "").strip().rstrip("/")
    if not base:
        raise RoomError("no node address: set the server first")
    if "://" not in base:
        base = "http://" + base
    return f"{base}{path}"


def _headers(token: Optional[str], *, json_body: bool = False) -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _call(request: urllib.request.Request, timeout: float) -> Any:
    """One JSON call, with the node's own sentence on a refusal.

    TLS is verified with the default context (a token must never travel over a
    connection anybody can read). A node with a private CA — the dev stack's
    Caddy — is trusted the standard way: `SSL_CERT_FILE` pointing at its root
    (`dev-stack/fcn-trust-ca.sh --export-only` writes `~/caddy-em-root.crt`).
    """
    try:
        with _urlopen(request, timeout=timeout) as answer:
            body = answer.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = str(json.loads(exc.read().decode("utf-8")).get("detail") or "")
        except Exception:  # noqa: BLE001 — a refusal without a JSON body
            pass
        if exc.code == 401:
            message = ("the node did not accept the access (401): sign in again"
                       + (f" — {detail}" if detail else ""))
        else:
            message = f"the node refused ({exc.code})" + (f": {detail}" if detail else "")
        raise RoomError(message, status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise RoomError(f"could not reach the node: {exc.reason}") from exc
    return json.loads(body.decode("utf-8")) if body else None


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


def create_room(base: str, token: Optional[str], name: str, *,
                timeout: float = 15.0) -> Dict[str, Any]:
    """`POST {node}/v1/rooms {room_id, title}` — you become its owner.

    The collision is the NODE's to refuse (409, with its sentence): asking
    first and creating second would be two answers where one is
    authoritative.
    """
    room_id = room_id_from_name(name)
    if not room_id:
        raise RoomError(f"«{name}» has no letters or digits to make a room id "
                        f"from: choose another name")
    body = json.dumps({"room_id": room_id, "title": (name or "").strip()}).encode("utf-8")
    request = urllib.request.Request(_url(base, "/v1/rooms"), data=body,
                                     method="POST",
                                     headers=_headers(token, json_body=True))
    answer = _call(request, timeout)
    if not isinstance(answer, dict):
        raise RoomError("the node created the room but did not describe it")
    return answer


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


def room_info(base: str, token: Optional[str], room_id: str, *,
              timeout: float = 15.0) -> Dict[str, Any]:
    """`GET {node}/v1/rooms/{id}` — the room as THIS identity sees it (role)."""
    request = urllib.request.Request(
        _url(base, f"/v1/rooms/{urllib.parse.quote(room_id, safe='')}"),
        method="GET", headers=_headers(token))
    answer = _call(request, timeout)
    if not isinstance(answer, dict):
        raise RoomError("the node did not describe the room")
    return answer


#: Below the node's `OPS_BATCH_MAX` (1000): the batch is applied under the
#: room's lock, and a shorter one freezes the room for less time.
OPS_PER_REQUEST = 500


def send_ops(base: str, token: Optional[str], room_id: str,
             ops: List[Dict[str, Any]], *, timeout: float = 120.0
             ) -> Dict[str, Any]:
    """`POST {node}/v1/rooms/{id}/ops` in parts → `{applied, refused, requests}`.

    The connector door of the node: the same five idempotent verbs the
    WebSocket relay takes (EMStudio seeds with them), applied AND KEPT under
    the room's lock — so a seeded room survives a restart without a separate
    `request_save`. A refusal (stale, idempotent) is not an error: it is the
    convergent answer, and a second seeding of the same graph is all refusals.
    """
    applied, refused, requests = 0, [], 0
    url = _url(base, f"/v1/rooms/{urllib.parse.quote(room_id, safe='')}/ops")
    for start in range(0, len(ops), OPS_PER_REQUEST):
        body = json.dumps({"ops": ops[start:start + OPS_PER_REQUEST]},
                          ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=body, method="POST",
                                         headers=_headers(token, json_body=True))
        answer = _call(request, timeout) or {}
        applied += int(answer.get("applied") or 0)
        refused += list(answer.get("refused") or [])
        requests += 1
    return {"applied": applied, "refused": refused, "requests": requests}
