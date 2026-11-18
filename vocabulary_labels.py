"""MICRO-U-VOCABOLARI-COME-FONT (E.D., 18 Nov 2026) · a controlled value as EM Tools shows it.

A value taken from a vocabulary is kept twice on its PropertyNode
(``data.concept``: the code of the term, the label written with its language,
the vocabulary and its version — ``s3dgraphy.terms``). EM Tools reads the
vocabularies installed on this machine from the SAME folder every EM tool
shares (``s3dgraphy.authorities.packages.vocab_dir``) and shows:

* the label in Blender's language from the installed vocabulary,
* else the label saved with the value,
* and says «vocabulary missing» when it is not installed here;
* a value that is only text in a field that takes a vocabulary's values is
  marked «not controlled».

Installing and removing vocabularies is EMStudio's (Tools ▸ Vocabularies…).
No bpy here: the language is handed in (:func:`blender_lang` turns Blender's
locale into a tag), so the tests run without Blender. With an older bundled
s3dgraphy that has no ``terms``, the saved label is shown and nothing is said
missing.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

SIGN_LINKED = "◆"
SIGN_MISSING = "◆?"
SIGN_UNCONTROLLED = "◇"


def _data(node: Any) -> Dict[str, Any]:
    if isinstance(node, dict):
        return node.get("data") or {}
    d = getattr(node, "data", None)
    return d if isinstance(d, dict) else {}


def term_of(node: Any) -> Optional[Dict[str, Any]]:
    try:
        from s3dgraphy.terms import term_of as _t
        return _t(node)
    except Exception:  # an older bundled s3dgraphy: read the shape here
        raw = _data(node).get("concept")
        if isinstance(raw, dict) and raw.get("concept"):
            return {"concept": str(raw["concept"]), "label": str(raw.get("label") or ""),
                    "lang": str(raw.get("lang") or "")}
        return None


def value_code_of(node: Any) -> Optional[str]:
    """The code (URI) of a property node's value, or None (text only)."""
    t = term_of(node)
    return t["concept"] if t else None


def blender_lang(locale: Optional[str]) -> str:
    """``it_IT`` → ``it``, ``zh_HANS`` → ``zh-hans``; empty → ``en``."""
    loc = (locale or "").strip()
    if not loc or loc.upper() in ("DEFAULT", "C"):
        return "en"
    head, _, tail = loc.partition("_")
    if tail and tail.isalpha() and len(tail) > 2:
        return f"{head.lower()}-{tail.lower()}"
    return head.lower()


def display(node: Any, lang: str) -> Tuple[str, str]:
    """``(text, state)`` of a property's value: state ``linked``, ``missing``
    (its vocabulary is not installed here), ``uncontrolled`` (text where the
    field takes a vocabulary's values) or ``free``."""
    value = getattr(node, "value", None) if not isinstance(node, dict) else _data(node).get("value")
    text = "" if value is None or isinstance(value, (dict, list)) else str(value)
    try:
        from s3dgraphy import terms as T
    except Exception:
        T = None
    if T is None:
        t = term_of(node)
        return ((t.get("label") or text), "linked") if t else (text, "free")
    lab = T.value_label(node, lang)
    if lab["concept"]:
        return lab["text"], "missing" if lab["missing_vocabulary"] else "linked"
    return text, ("uncontrolled" if T.is_controlled(node) and text.strip() else "free")


def list_text(node: Any, lang: str) -> str:
    """What a list row shows: the value with its sign."""
    text, state = display(node, lang)
    sign = {"linked": SIGN_LINKED, "missing": SIGN_MISSING, "uncontrolled": SIGN_UNCONTROLLED}.get(state)
    return f"{sign} {text}" if sign else text
