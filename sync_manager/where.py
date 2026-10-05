"""Z1 · the four zones at the head of «Where you work», like EMStudio's bar.

**Where you work · Who you are · Message · Log**, top to bottom because in
Blender the panel is a column. Under them, only the commands the place makes
possible (`panel.py`). The words are those of EMStudio's Connection panel (On
this computer · With Blender · In a room — here «With EMStudio» and «In a
collaborative room»); the signs are the ones of the common list
(`em_state_symbols.json`), «⇄» among them since Q2 (`room.paired`).

`zones(state)` is pure: `state` is what `read_state(context)` collects, so the
four sentences of every place are measured by `tests/test_where_you_work.py`
without a Blender. One sentence per zone, the most recent useful one — the
explanations that used to fill half the panel are the tooltips of the commands.
"""

from typing import Any, Dict, Optional
from urllib.parse import urlsplit

PLACE_HERE = "here"
PLACE_EMSTUDIO = "emstudio"
PLACE_ROOM = "room"

#: what the three places are called, the same words in the panel, in
#: «Change…» and in EM ▸ Mode
PLACES = (
    (PLACE_HERE, "On this computer", "FILE_BLEND",
     "This Blender alone: the study is a file on this computer, no bridge, no room"),
    (PLACE_EMSTUDIO, "With EMStudio", "LINKED",
     "EMStudio and this Blender on the same computer, on the same study: one "
     "person, two screens (the bridge listens on 127.0.0.1 only)"),
    (PLACE_ROOM, "In a collaborative room", "COMMUNITY",
     "The study in a room of a StratiGraph node, with the people who take part"),
)


def host_of(base: Optional[str]) -> str:
    """`https://em.localhost:8443/em` → `em.localhost:8443/em`: the host and the
    port (and the path a node lives under), never «stratigraph-server» three
    times."""
    raw = str(base or "").strip().rstrip("/")
    if not raw:
        return ""
    parts = urlsplit(raw if "://" in raw else "http://" + raw)
    host = parts.hostname or raw
    port = f":{parts.port}" if parts.port else ""
    path = parts.path.rstrip("/")
    return f"{host}{port}{path}"


def _glyph(state: str, fallback: str) -> str:
    try:
        from ..state_symbols import glyph
    except ImportError:              # loaded by path (the suite)
        from state_symbols import glyph  # type: ignore
    try:
        return glyph(state) or fallback
    except Exception:  # noqa: BLE001 — no s3dgraphy list at hand
        return fallback


def zones(s: Dict[str, Any]) -> Dict[str, Any]:
    """`{place, who, message, log}`: each `(icon, text)`; the message also
    `{op, op_text, op_props}` when a gesture fixes it."""
    place = s.get("place") or PLACE_HERE
    host = host_of(s.get("node"))
    out: Dict[str, Any] = {}

    # ── WHERE YOU WORK ──────────────────────────────────────────────────────
    problem = False
    if place == PLACE_ROOM:
        title = s.get("room_title") or s.get("room_id") or "the room"
        if s.get("not_connected"):
            # V1 · a file reopened in its room: the room is where it works,
            # and this Blender is not in it yet — said, with Reconnect below
            out["place"] = ("UNLINKED", f"{_glyph('room.inside', '▣')} {title} · {host} · "
                                        f"not connected")
            problem = True
        elif s.get("offline"):
            out["place"] = ("UNLINKED", f"{_glyph('room.inside', '▣')} {title} · {host} · offline")
            problem = True
        else:
            n = int(s.get("members") or 0)
            out["place"] = ("COMMUNITY", f"{_glyph('room.inside', '▣')} {title} · {host} · "
                                         f"{n} present")
            problem = bool(s.get("refused"))
    elif place == PLACE_EMSTUDIO:
        n = int(s.get("clients") or 0)
        same = s.get("same_document")
        doc = ("same document ✓" if same is True else
               "≠ another document" if same is False else "no document declared yet")
        out["place"] = ("LINKED", f"{_glyph('room.paired', '⇄')} With EMStudio · {n} "
                                  f"client{'s' if n != 1 else ''} · {doc}")
        problem = same is False
    else:
        study = s.get("study_file") or "no study loaded"
        out["place"] = ("FILE_BLEND", f"{_glyph('room.outside', '□')} On this computer · {study}")
    out["healthy"] = not problem

    # ── WHO YOU ARE ─────────────────────────────────────────────────────────
    if place == PLACE_ROOM and s.get("not_connected"):
        who = s.get("user")
        out["who"] = ("USER", (f"{who} ✓ · " if who else "")
                      + "the role is said by the room at the entry")
    elif place == PLACE_ROOM:
        role = s.get("role") or ""
        rs = f"role.{role}" if role in ("owner", "editor", "viewer") else ""
        role_txt = f"{_glyph(rs, '')} {role}".strip() if role else "no role said"
        who = s.get("author")
        out["who"] = ("USER", f"{who} ✓ · {role_txt}" if who
                      else f"no identity in the access — edits dated, not signed · {role_txt}")
    elif s.get("signed_in_to"):
        who = f"{s['user']} ✓ on " if s.get("user") else "signed in to "
        out["who"] = ("USER", f"{who}{host_of(s['signed_in_to'])} — none needed here")
    else:
        out["who"] = ("USER", "not signed in to a node — none needed here")

    # ── MESSAGE: one sentence, the most recent useful one ───────────────────
    msg: Dict[str, Any] = {"icon": "INFO", "text": "", "op": "", "op_text": "",
                           "op_props": {}, "alert": False}
    declared = s.get("declared") or PLACE_HERE
    if s.get("signin_waiting"):
        msg.update(icon="TIME", text="Waiting for the browser…",
                   op="em.sign_in_cancel", op_text="Cancel")
    elif s.get("expired"):
        msg.update(icon="LOCKED", text=f"The access to {host_of(s['expired'])} has expired",
                   op="em.sign_in_again", op_text="Sign in again", alert=True)
    elif place == PLACE_ROOM and s.get("not_connected"):
        msg.update(icon="UNLINKED",
                   text=f"Not connected to {s.get('room_title') or s.get('room_id')}: "
                        f"edits wait here",
                   op="em.room_reconnect", op_text="Reconnect")
    elif place == PLACE_ROOM and s.get("can_write") is False:
        msg.update(icon="LOCKED", text=f"{_glyph('room.read_only', '⊘')} your role does not write")
    elif place == PLACE_ROOM and s.get("offline"):
        msg.update(icon="UNLINKED",
                   text=f"The connection to {s.get('room_title') or s.get('room_id')} dropped",
                   op="em.room_reconnect", op_text="Reconnect")
    elif s.get("transition_failed"):
        msg.update(icon="CANCEL", text=str(s["transition_failed"]), alert=True)
    elif declared == PLACE_EMSTUDIO and place == PLACE_HERE:
        msg.update(text="Last time this file worked with EMStudio",
                   op="em.set_mode", op_text="Reconnect", op_props={"mode": "sidecar"})
    elif declared == PLACE_ROOM and place == PLACE_HERE and s.get("declared_room"):
        msg.update(text=f"Last time this file worked in the room {s['declared_room']}",
                   op="em.room_reconnect", op_text="Reconnect")
    elif place == PLACE_EMSTUDIO and s.get("same_document") is False:
        msg.update(icon="ERROR", text="≠ EMStudio has another document open: a node id "
                                      "from there will not be found here")
    elif s.get("transition"):
        msg.update(text=str(s["transition"]))
    elif s.get("signin_line"):
        msg.update(text=str(s["signin_line"]))
    out["message"] = msg

    # ── LOG ─────────────────────────────────────────────────────────────────
    waiting = int(s.get("waiting") or 0)
    refused = int(s.get("refused") or 0)
    not_applied = int(s.get("not_applied") or 0)
    if place == PLACE_ROOM and s.get("not_connected") and not waiting:
        log = ("UNLINKED", "not connected · nothing sent since the file was opened")
    elif place == PLACE_ROOM:
        if waiting:
            log = ("TIME", f"{_glyph('sync.pending', '⋯')} {waiting} edit"
                           f"{'s' if waiting != 1 else ''} waiting to be sent")
        elif refused:
            log = ("ERROR", f"{_glyph('sync.conflict', '≠')} {refused} edit"
                            f"{'s' if refused != 1 else ''} not applied by the room")
        else:
            sent, answered = int(s.get("sent") or 0), int(s.get("answered") or 0)
            log = ("CHECKMARK", f"{_glyph('sync.aligned', '✓')} aligned · {sent} sent, "
                                f"{answered} answered")
    else:
        log = (("ERROR", f"✕ {not_applied} edit{'s' if not_applied != 1 else ''} not applied")
               if not_applied else ("CHECKMARK", "no refused edit"))
    if place != PLACE_ROOM and waiting:
        log = ("TIME", f"{_glyph('sync.pending', '⋯')} {waiting} edit"
                       f"{'s' if waiting != 1 else ''} waiting for their room")
    out["log"] = log
    return out


# ── Blender ─────────────────────────────────────────────────────────────────

def read_state(context) -> Dict[str, Any]:  # pragma: no cover — bpy
    """Everything `zones` needs, read off this Blender."""
    import os

    from . import operators as ops
    from . import room as room_cfg
    from . import room_session as _rs

    status = ops.room_status(context)
    mode = ops.session_mode(context)
    seated_offline = any(s.offline for _g, s in _rs.sessions())
    s: Dict[str, Any] = {}
    s["not_connected"] = bool(status.get("not_connected"))
    if mode == ops.MODE_HUB or seated_offline or s["not_connected"]:
        s["place"] = PLACE_ROOM
    elif mode == ops.MODE_SIDECAR:
        s["place"] = PLACE_EMSTUDIO
    else:
        s["place"] = PLACE_HERE
    declared = ops.modo_dichiarato(context)
    s["declared"] = {ops.MODE_HUB: PLACE_ROOM, ops.MODE_SIDECAR: PLACE_EMSTUDIO}.get(
        declared, PLACE_HERE)
    s["declared_room"] = str(getattr(context.scene, "em_room_id", "") or "")
    s["node"] = status.get("base_url") or getattr(context.scene, "em_room_url", "")
    s["connected"] = bool(status.get("connected"))
    s["room_id"] = status.get("room_id")
    s["room_title"] = ROOM_TITLES.get(str(status.get("room_id") or ""), "")
    s["members"] = status.get("members")
    s["role"] = status.get("role")
    # the name the person signed in with (the token's preferred_username, read
    # not verified: the node verifies), else the author the room stamps (ORCID)
    token = room_cfg._session.get("token")
    try:
        from .handoff import _who
        named = _who(token) if token else ""
    except Exception:  # noqa: BLE001
        named = ""
    s["author"] = named or status.get("author")
    s["user"] = named
    s["can_write"] = status.get("can_write")
    s["offline"] = bool(status.get("offline")) or (mode != ops.MODE_HUB and seated_offline)
    s["sent"], s["answered"] = status.get("sent"), status.get("answered")
    s["refused"] = status.get("refused")
    s["waiting"] = _rs.waiting_total()
    s["not_applied"] = len(ops.RIFIUTI)
    if mode == ops.MODE_SIDECAR:
        s["clients"] = ops.client_count()
        al = ops.disallineamento(context)
        declared_peer = bool(ops.dichiarazione_del_pari())
        s["same_document"] = (True if al.get("allineati") and declared_peer else
                              False if not al.get("allineati") else None)
    try:
        em_tools = context.scene.em_tools
        row = em_tools.graphml_files[em_tools.active_file_index]
        path = str(getattr(row, "graphml_path", "") or "")
        s["study_file"] = os.path.basename(path) if path else row.name
    except Exception:  # noqa: BLE001 — no graph listed
        s["study_file"] = ""
    held = room_cfg._session.get("token") and room_cfg._session.get("base_url")
    s["signed_in_to"] = room_cfg._session.get("base_url") if held else ""
    from . import access, signin_ui
    running = signin_ui.PENDING.get("signin")
    s["signin_waiting"] = bool(running is not None and running.state == "waiting")
    s["signin_line"] = signin_ui.PENDING.get("line") or ""
    s["expired"] = access.EXPIRED.get("base") or ""
    last = ops.ULTIMA_TRANSIZIONE
    if last.get("message"):
        if not last.get("ok", True):
            s["transition_failed"] = last["message"]
        elif last.get("mode") == mode:
            s["transition"] = last["message"]
    return s


#: room id → its title, as the node said it (the list, the creation): the
#: place line names the room the way people call it
ROOM_TITLES: Dict[str, str] = {}
