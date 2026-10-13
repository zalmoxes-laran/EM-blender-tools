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


def host_port(base: Optional[str]) -> str:
    """`https://em.localhost:8443/em` → `em.localhost:8443`: the node as a
    person says it, on the line of who you are (MICRO tre pannelli)."""
    raw = str(base or "").strip().rstrip("/")
    if not raw:
        return ""
    parts = urlsplit(raw if "://" in raw else "http://" + raw)
    return f"{parts.hostname or raw}{f':{parts.port}' if parts.port else ''}"


def claims_of(token: Optional[str]) -> Dict[str, Any]:
    """The claims of an access token, read and not verified (the node
    verifies): where the name a person goes by is (`name`, «Editor Due»)."""
    import base64
    import json
    try:
        part = str(token or "").split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except Exception:  # noqa: BLE001 — an opaque token: no name to say
        return {}
    return claims if isinstance(claims, dict) else {}


def name_in(token: Optional[str]) -> str:
    """The name to say for this Blender's person: «Editor Due», else the
    username they signed in with."""
    c = claims_of(token)
    return str(c.get("name") or c.get("preferred_username") or "")


def wrap(text: str, width: int) -> list:
    """Words over lines of at most `width` characters: a room's name goes on
    a new line instead of being cut in the middle («Tavolo · prova m…»)."""
    lines, line = [], ""
    for word in str(text or "").split():
        if line and len(line) + 1 + len(word) > max(8, width):
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return lines or [""]


def room_state(s: Dict[str, Any]) -> Dict[str, Any]:
    """The room in ONE state (MICRO tre pannelli, 13 Oct 2026: «aligned · 4
    sent, 4 answered» and «The scene · aligned» were two alignments):
    «● Aligned», «● Sending 3…», «● Offline — 5 waiting», «● 2 changed here»,
    «● 3 to download». `{icon, text, alert, op, op_text, op_props, numbers}`:
    the gesture that fixes it, when there is one; the numbers for the Log."""
    waiting = int(s.get("waiting") or 0)
    refused = int(s.get("refused") or 0)
    tally = s.get("tally") or {}
    _icon, _word, numbers = scene_status(tally)
    st: Dict[str, Any] = {"icon": "CHECKMARK", "text": "● Aligned", "alert": False,
                          "op": "", "op_text": "", "op_props": {},
                          "numbers": " · ".join(b for b in (
                              f"{int(s.get('sent') or 0)} sent, "
                              f"{int(s.get('answered') or 0)} answered", numbers) if b)}
    rest = f" — {waiting} waiting" if waiting else ""
    missing = max(0, int(tally.get("missing") or 0))
    changed = int(tally.get("changed") or 0)
    if s.get("not_connected"):
        st.update(icon="UNLINKED", text=f"● Not connected{rest}", alert=True,
                  op="em.room_reconnect", op_text="Reconnect")
    elif s.get("offline"):
        st.update(icon="UNLINKED", text=f"● Offline{rest}", alert=True,
                  op="em.room_reconnect", op_text="Reconnect")
    elif waiting:
        st.update(icon="TIME", text=f"● Sending {waiting}…")
    elif refused:
        st.update(icon="ERROR", text=f"● {refused} not applied by the room", alert=True)
    elif changed:
        st.update(icon="ERROR", text=f"● {changed} changed here, not sent")
    elif missing:
        st.update(icon="IMPORT", text=f"● {missing} to download")
        if s.get("offer_download"):
            st.update(op="em.scene_check", op_text="Download now",
                      op_props={"download": True})
    return st


def _glyph(state: str, fallback: str) -> str:
    try:
        from ..state_symbols import glyph
    except ImportError:              # loaded by path (the suite)
        from state_symbols import glyph  # type: ignore
    try:
        return glyph(state) or fallback
    except Exception:  # noqa: BLE001 — no s3dgraphy list at hand
        return fallback


def _looks_like_orcid(text: str) -> bool:
    import re
    return bool(re.search(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b", str(text or "")))


def quiet(message: str) -> bool:
    """A transition that changed nothing («already standalone»): not a message."""
    return message.startswith("already ")


def scene_status(tally: Optional[Dict[str, int]]) -> tuple:
    """P1 · the scene in a room in one word: `(icon, word, numbers)`.

    «✓ aligned», «✕ N to download», «≠ N changed» (both when both are true);
    `numbers` is the long line of the counts, for the tooltip and Log…. No
    tally (the scene not checked yet) → `("", "", "")`."""
    if not tally:
        return ("", "", "")
    missing = max(0, int(tally.get("missing") or 0))
    changed = int(tally.get("changed") or 0)
    numbers = (f"◉ {int(tally.get('here') or 0)} here · ✕ {missing} missing · "
               f"≠ {changed} changed · ↗ {int(tally.get('external') or 0)} references · "
               f"◆ {int(tally.get('only_here') or 0)} only here")
    if tally.get("at"):
        numbers += f" · checked {tally['at']}"
    words = []
    if missing:
        words.append(f"{_glyph('file.missing', '✕')} {missing} to download")
    if changed:
        words.append(f"{_glyph('sync.conflict', '≠')} {changed} changed")
    if not words:
        return ("CHECKMARK", f"{_glyph('sync.aligned', '✓')} aligned", numbers)
    return ("IMPORT" if missing else "ERROR", " · ".join(words), numbers)


def zones(s: Dict[str, Any]) -> Dict[str, Any]:
    """`{place, who, message, log}`: each `(icon, text)`; the message also
    `{op, op_text, op_props}` when a gesture fixes it; in a room, `state`
    (`room_state`) in place of the log."""
    place = s.get("place") or PLACE_HERE
    out: Dict[str, Any] = {}

    # ── WHERE YOU WORK ──────────────────────────────────────────────────────
    problem = False
    if place == PLACE_ROOM:
        title = s.get("room_title") or s.get("room_id") or "the room"
        # 13 Oct 2026 · «Tavolo · prova mul…cal:8000 · 2 present»: one line
        # cut in the middle of the room's name. The name whole (the panel
        # wraps it), with its people; the node is said once, on the line of
        # who you are
        out["place_detail"] = ("", "")
        if s.get("not_connected"):
            # V1 · a file reopened in its room: the room is where it works,
            # and this Blender is not in it yet — said, with Reconnect below
            out["place"] = ("UNLINKED", f"{_glyph('room.inside', '▣')} {title} · not connected")
            problem = True
        elif s.get("offline"):
            out["place"] = ("UNLINKED", f"{_glyph('room.inside', '▣')} {title} · offline")
            problem = True
        else:
            n = int(s.get("members") or 0)
            out["place"] = ("COMMUNITY", f"{_glyph('room.inside', '▣')} {title} · {n} present")
            problem = bool(s.get("refused"))
    elif place == PLACE_EMSTUDIO:
        n = int(s.get("clients") or 0)
        same = s.get("same_document")
        doc = ("same document ✓" if same is True else
               "≠ another document" if same is False else "no document declared yet")
        out["place"] = ("LINKED", f"{_glyph('room.paired', '⇄')} With EMStudio · {n} "
                                  f"client{'s' if n != 1 else ''} · {doc}")
        # a different document on the two ends is LEGITIMATE (one models, the
        # other writes the narrative; the alignment module says so too): it is
        # said, in words, but it is not a fault, so it does not turn the zone red
        problem = False
    else:
        study = s.get("study_file") or "no study loaded"
        out["place"] = ("FILE_BLEND", f"{_glyph('room.outside', '□')} On this computer · {study}")
    out["healthy"] = not problem

    # ── WHO YOU ARE ─────────────────────────────────────────────────────────
    if place == PLACE_ROOM:
        # MICRO tre pannelli · once: «Editor Due · editor · em.localhost:8443»
        # (the name from the token, the role, the node without its scheme)
        who = s.get("author") or s.get("user") or ""
        if who and _looks_like_orcid(who):
            who = ""                       # a code is not a name: Details only
        role = "" if s.get("not_connected") else (s.get("role") or "")
        bits = [who or "not signed", role, host_port(s.get("node"))]
        out["who"] = ("USER", " · ".join(b for b in bits if b))
    elif s.get("signed_in_to"):
        who = f"{s['user']} ✓ on " if s.get("user") else "signed in to "
        out["who"] = ("USER", f"{who}{host_of(s['signed_in_to'])} — none needed here")
    else:
        # P1 (6 Oct 2026) · outside a room and signed in nowhere there is
        # nothing to say about who you are: the zone is empty, not drawn
        out["who"] = ("USER", "")

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
    elif place == PLACE_ROOM and (s.get("not_connected") or s.get("offline")):
        pass                               # said by the room's state, with Reconnect
    elif place == PLACE_ROOM and s.get("can_write") is False:
        msg.update(icon="LOCKED", text=f"{_glyph('room.read_only', '⊘')} your role does not write")
    elif s.get("transition_failed"):
        msg.update(icon="CANCEL", text=str(s["transition_failed"]), alert=True)
    elif declared == PLACE_EMSTUDIO and place == PLACE_HERE:
        msg.update(text="Last time this file worked with EMStudio",
                   op="em.set_mode", op_text="Reconnect", op_props={"mode": "sidecar"})
    elif declared == PLACE_ROOM and place == PLACE_HERE and s.get("declared_room"):
        msg.update(text=f"Last time this file worked in the room {s['declared_room']}",
                   op="em.room_reconnect", op_text="Reconnect")
    elif place == PLACE_EMSTUDIO and s.get("same_document") is False:
        msg.update(icon="INFO", text="≠ EMStudio has another document open: a node id "
                                     "from there will not be found here")
    elif s.get("transition") and not quiet(str(s["transition"])):
        msg.update(text=str(s["transition"]))
    elif s.get("signin_line") and place != PLACE_ROOM:
        # in a room who you are is said once, on its line
        msg.update(text=str(s["signin_line"]))
    out["message"] = msg

    # ── LOG ─────────────────────────────────────────────────────────────────
    waiting = int(s.get("waiting") or 0)
    not_applied = int(s.get("not_applied") or 0)
    if place == PLACE_ROOM:
        # MICRO tre pannelli · in a room the log is the ONE state of the room
        out["state"] = room_state(s)
        log = ("TEXT", "")
    else:
        # P1 · «no refused edit» said nothing: an empty log is not drawn
        log = (("ERROR", f"✕ {not_applied} edit{'s' if not_applied != 1 else ''} not applied")
               if not_applied else ("CHECKMARK", ""))
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
    # the name the person goes by («Editor Due», the token's `name`), else
    # the username; the ORCID the room stamps is never said here
    s["author"] = name_in(token) or named or status.get("author")
    s["user"] = named
    s["can_write"] = status.get("can_write")
    s["offline"] = bool(status.get("offline")) or (mode != ops.MODE_HUB and seated_offline)
    s["sent"], s["answered"] = status.get("sent"), status.get("answered")
    s["refused"] = status.get("refused")
    s["waiting"] = _rs.waiting_total()
    s["not_applied"] = len(ops.RIFIUTI)
    from . import scene_check
    s["tally"] = scene_check.ULTIMA_VERIFICA.get("tally") or {}
    s["offer_download"] = bool(int(scene_check.ULTIMA_VERIFICA.get("missing_left") or 0)
                               and not ops._preferenza("materialise_on_adopt", False))
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
