"""I1 · EMtools' drawing of the ONE list of states (s3Dgraphy
``JSON_config/em_state_symbols.json``, decided by E.D. 4 Oct 2026).

The SYMBOL and its MEANING are standard — the glyph and the sentence come from
the list; how it is drawn is ours: a Blender icon beside the glyph. Every state
of the list has its sign here, and there is no sign here that is not in the
list (``tests/test_state_symbols.py``).
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

#: state id → the Blender icon EMtools draws it with
ICONS: Dict[str, str] = {
    "file.on_disk": "DISK_DRIVE",
    "file.on_node": "WORLD_DATA",
    "file.both": "LINKED",
    "file.reference_only": "URL",
    "file.missing": "CANCEL",
    "file.empty_copy": "GHOST_DISABLED",
    "node.reachable": "CHECKBOX_HLT",
    "node.unreachable": "CHECKBOX_DEHLT",
    "node.global": "WORLD",
    "node.local_only": "HOME",
    "room.inside": "COMMUNITY",
    "room.outside": "FILE_BLEND",
    "room.paired": "LINKED",
    "room.read_only": "LOCKED",
    "sync.aligned": "CHECKMARK",
    "sync.pending": "TIME",
    "sync.conflict": "ERROR",
    "role.owner": "SOLO_ON",
    "role.editor": "GREASEPENCIL",
    "role.viewer": "HIDE_OFF",
    "scene.only_here": "PINNED",
}

_DOC: Dict[str, Any] = {}


def symbols() -> Dict[str, Any]:
    """The list as s3dgraphy ships it (read once)."""
    if not _DOC:
        import s3dgraphy
        path = os.path.join(os.path.dirname(s3dgraphy.__file__), "JSON_config",
                            "em_state_symbols.json")
        with open(path, encoding="utf-8") as fh:
            _DOC.update(json.load(fh))
    return _DOC


def sign(state: str, lang: str = "en") -> Tuple[str, str, str]:
    """``(icon, "<glyph> <label>", meaning)`` of a state id (``file.on_disk``)."""
    entry: Optional[Dict[str, Any]] = (symbols().get("states") or {}).get(state)
    if entry is None:
        return "QUESTION", f"? {state}", ""
    label = entry["label"].get(lang) or entry["label"]["en"]
    return ICONS.get(state, "QUESTION"), f"{entry['glyph']} {label}", \
        entry["meaning"].get(lang) or entry["meaning"]["en"]


def glyph(state: str) -> str:
    """The glyph alone (``●``), or "" for a state the list does not have."""
    entry = (symbols().get("states") or {}).get(state)
    return entry["glyph"] if entry else ""


# ── I1 · which state of the list a room, a role, a sync is in ───────────────
# The same reading EMStudio does (`connection.ts` roomStateId / roleStateId,
# `main.ts` roomSyncState): a state the list does not have (the role «admin»)
# keeps its word and gets no sign — none is invented here.

def room_state(joined: bool, can_write: bool = True) -> str:
    """``room.inside``, ``room.read_only`` (inside, the role does not write) or
    ``room.outside``."""
    if not joined:
        return "room.outside"
    return "room.inside" if can_write else "room.read_only"


def role_state(role: Optional[str]) -> Optional[str]:
    """``role.owner`` / ``role.editor`` / ``role.viewer``, or None."""
    state = f"role.{role or ''}"
    return state if role and state in (symbols().get("states") or {}) else None


def sync_state(sent: int, answered: int, refused: int) -> str:
    """Where this Blender's edits are with the room, read off the room's own
    answers: every operation sent gets one (`op_result`, or `denied`).

    * ``sync.conflict`` — the room did not apply an edit of ours this session
      (a refusal that is news, `crdt.refusal_is_news`, or a `denied`): what is
      here is not what the room has;
    * ``sync.pending`` — edits sent and not answered yet;
    * ``sync.aligned`` — every edit sent was applied (or there were none).
    """
    if refused > 0:
        return "sync.conflict"
    if sent > answered:
        return "sync.pending"
    return "sync.aligned"


def room_signs(status: Dict[str, Any]) -> List[Tuple[str, str]]:
    """``(icon, text)`` of the room, the role and the sync for the Sync panel,
    each with its sign — `status` is `operators.room_status()`."""
    joined = bool(status.get("joined"))
    can_write = status.get("can_write") is not False
    room = room_state(joined, can_write)
    lines = []
    if joined:
        where = f"In {status.get('room_id')} · {status.get('members', 0)} present"
        if room == "room.read_only":
            where += " · read only"
        lines.append((ICONS[room], f"{glyph(room)} {where}"))
    else:
        lines.append((ICONS[room], f"{glyph(room)} No room: the graph is a file on this computer"))
        return lines
    role = status.get("role")
    rs = role_state(role)
    if rs:
        lines.append((ICONS[rs], f"{glyph(rs)} Role: {role}"))
    elif role:
        lines.append(("BLANK1", f"Role: {role}"))
    sent = int(status.get("sent") or 0)
    answered = int(status.get("answered") or 0)
    refused = int(status.get("refused") or 0)
    st = sync_state(sent, answered, refused)
    if st == "sync.conflict":
        text = (f"In conflict: {refused} edit(s) the room did not apply — "
                f"what is here is not what the room has")
    elif st == "sync.pending":
        text = f"Pending: {sent - answered} edit(s) sent, not yet confirmed"
    else:
        text = (f"Aligned: the room answered the {sent} edit(s) sent" if sent
                else "Aligned: no edit sent from here yet")
    lines.append((ICONS[st], f"{glyph(st)} {text}"))
    return lines
