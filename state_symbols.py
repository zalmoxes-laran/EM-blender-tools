"""I1 · EMtools' drawing of the ONE list of states (s3Dgraphy
``JSON_config/em_state_symbols.json``, decided by E.D. 4 Oct 2026).

The SYMBOL and its MEANING are standard — the glyph and the sentence come from
the list; how it is drawn is ours: a Blender icon beside the glyph. Every state
of the list has its sign here, and there is no sign here that is not in the
list (``tests/test_state_symbols.py``).
"""

import json
import os
from typing import Any, Dict, Optional, Tuple

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
