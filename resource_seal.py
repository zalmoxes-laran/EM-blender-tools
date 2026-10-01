"""The seal of a stamped resource: its words, its check, its technical details.

E.D. (1 Oct 2026): «codice sì, ma nascosto in maniera elegante sotto una pelle
esteticamente bella». EMStudio closes a stamp with a wax seal that presses
itself (``frontend/src/seal.ts``); Blender does not animate, but a panel can
keep the same order of things — the seal and the words first, the code under
a closed triangle. This module is that order, without ``bpy``:

* :func:`find_stamp` — the ``.stamp.json`` beside a file, a folder or the door
  of a file set (dtcstamp's rule, ``<asset>.stamp.json``);
* :func:`words` — what was stamped, where it comes from, who, when, with what;
* :func:`verify` — whether the bytes on disk are the stamped ones. **A file set
  is checked member by member** (``dtcstamp.verify_members``), never by the
  sha256 of its entry point: that was the defect EMStudio fixed in the
  NIGHT-CAMPAGNA, a door unchanged while a texture behind it changed;
* :func:`canonical_lines` — dtcstamp's canonical list of the members, for a
  reader (``role ␀ path ␀ digest``, in its order), never re-hashed here.

Nothing of the stamp's identity is computed here: the digests are the stamp's,
and every check is dtcstamp's.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

#: the visible mark of each verification state, beside the seal
MARK = {"ok": "✓", "differs": "▲", "missing": "▲", "unverifiable": "·", "unreadable": "▲"}


def _dtcstamp():
    try:
        from . import resource_digest  # inside the addon package
    except ImportError:
        import resource_digest  # type: ignore  # tests: repo root on the path
    return resource_digest.dtcstamp()


def stamp_path_for(path: str) -> str:
    """``<path>.stamp.json``, beside it — for a file, a folder, or a door."""
    path = os.path.abspath(path.rstrip("/\\"))
    return os.path.join(os.path.dirname(path),
                        _dtcstamp().stamp_filename({}, asset=os.path.basename(path)))


def find_stamp(path: Optional[str]) -> Optional[str]:
    """The sidecar of ``path`` if there is one on disk, else None."""
    if not path:
        return None
    candidate = stamp_path_for(path)
    return candidate if os.path.isfile(candidate) else None


def load(stamp_path: str) -> Tuple[Dict[str, Any], str]:
    """``(stamp, raw text)``: validated by dtcstamp, and the file as it is —
    «Copy JSON» copies the real ``.stamp.json``, not a re-serialisation."""
    with open(stamp_path, "r", encoding="utf-8") as handle:
        raw = handle.read()
    return _dtcstamp().parse_stamp(raw), raw


# ── the words ────────────────────────────────────────────────────────────────

def words(stamp: Dict[str, Any]) -> Dict[str, str]:
    """``{what, origin, who, when, with_what}`` from the stamp alone.

    The same sentences as EMStudio's ``sealWords``: «One resource, 3 files:
    model.obj and the files it calls (…)», a folder, an archive, a file."""
    dtc = _dtcstamp()
    itself = stamp.get("self") or {}
    members = itself.get("members") or []
    door = next((m.get("path") for m in members if m.get("role") == "entry_point"), "")
    label = dtc.stamp_title(stamp) or door or str(itself.get("resource_id") or "")
    packaging = itself.get("packaging")
    tree_files = (itself.get("content_digest") or {}).get("files") \
        or (itself.get("measures") or {}).get("files") or ""
    if packaging == "file_set" and len(members) > 1:
        others = [str(m.get("path", "")).rsplit("/", 1)[-1]
                  for m in members if m.get("role") != "entry_point"]
        what = (f"One resource, {len(members)} files: {label} and the files "
                f"it calls ({', '.join(others)}).")
    elif packaging == "directory":
        what = f"One resource: the folder {label}, {tree_files} files of a tileset."
    elif packaging == "archive":
        what = (f"One resource: the archive {label}, {tree_files} files of a "
                f"tileset inside.")
    elif packaging == "datablock":
        what = f"One object inside a .blend: {label}."
    else:
        what = f"One file: {label}."

    how = stamp.get("how") or {}
    kind = str(how.get("dtc_kind") or "")
    parents = [str(p.get("label") or p.get("resource_id") or "")
               for p in stamp.get("from") or [] if isinstance(p, dict)]
    parents = [p for p in parents if p]
    if parents:
        origin = f"Comes from {', '.join(parents)}" + (f" — {kind}" if kind else "")
    else:
        campaign = (how.get("acquisition") or {}).get("name") or kind or "—"
        origin = f"Origin: {campaign}"

    by = stamp.get("by") or {}
    op = by.get("operator") or {}
    orcid = str(op.get("id") or "").replace("https://orcid.org/", "").replace(
        "http://orcid.org/", "")
    name = str(op.get("label") or "")
    who = f"{name} · {orcid}" if name and orcid else (name or orcid or "no operator named")
    software = [" ".join(str(x) for x in (s.get("name"), s.get("version")) if x)
                for s in how.get("software") or [] if isinstance(s, dict)]
    return {"what": what, "origin": origin, "who": who,
            "when": str(by.get("at") or ""),
            "with_what": ", ".join(s for s in software if s)}


def canonical_lines(stamp: Dict[str, Any]) -> List[str]:
    """dtcstamp's canonical list of ``self.members``, one line each, for the eye:
    ``role ␀ path ␀ digest`` in dtcstamp's order (the UTF-8 bytes of the NFC
    path). Shown, never hashed here."""
    members = (stamp.get("self") or {}).get("members") or []
    if not members:
        return []
    rows = _dtcstamp().canonical_members(members)
    return [f"{m['role']} ␀ {m['path']} ␀ {m['digest']}" for m in rows]


def technical(stamp: Dict[str, Any]) -> List[Tuple[str, str]]:
    """The key/value lines of «Technical details», in order."""
    itself = stamp.get("self") or {}
    out = [("digest", str(itself.get("digest") or "—")),
           ("digest_covers", str(itself.get("digest_covers") or "—")),
           ("packaging", str(itself.get("packaging") or "file"))]
    block = itself.get("content_digest") or {}
    if block.get("digest"):
        out.append(("content_digest", f"{block['digest']} · {block.get('files', '')} files"))
    return out


# ── the check ────────────────────────────────────────────────────────────────

def verify(stamp: Dict[str, Any], path: str) -> Dict[str, Any]:
    """``{state, line, missing, changed, extra}`` — do the bytes match the stamp?

    ``state``: ``ok``, ``differs``, ``missing`` (nothing at ``path``) or
    ``unverifiable`` (a datablock, a structural digest: comparable, never
    verifiable from bytes). Which check is dtcstamp's: members for a file set,
    the content digest for a tree, the file's sha256 for a file."""
    dtc = _dtcstamp()
    itself = stamp.get("self") or {}
    packaging = itself.get("packaging") or "file"
    out = {"state": "ok", "line": "", "missing": [], "changed": [], "extra": []}
    if packaging == "datablock" or not dtc.is_verifiable_stamp(stamp):
        out.update(state="unverifiable",
                   line="Not verifiable from bytes (a structural identity)")
        return out
    if not os.path.exists(path):
        out.update(state="missing", line=f"Nothing at {path}")
        return out
    if packaging == "file_set" or (itself.get("digest_covers") == "members"
                                   and itself.get("members")):
        res = dtc.verify_members(stamp, path)
        out.update(missing=res["missing"], changed=res["changed"], extra=res["extra"])
        if res["ok"]:
            out["line"] = f"The bytes match the stamp, all {len(itself.get('members') or [])} members"
        else:
            out["state"] = "differs"
            parts = []
            for word, items in (("changed", res["changed"]), ("missing", res["missing"]),
                                ("not in the stamp", res["extra"])):
                if items:
                    parts.append(f"{len(items)} {word}: {', '.join(items)}")
            if not res["list_consistent"]:
                parts.append("the list in the stamp does not hash to its digest")
            out["line"] = "; ".join(parts)
        return out
    if packaging in ("directory", "archive"):
        res = dtc.verify_tree(stamp, path)
        if res["ok"]:
            out["line"] = "The content matches the stamp"
        else:
            out["state"] = "differs"
            out["line"] = ("The content differs from the stamp" if not res["content"]
                           else "The archive's bytes differ (same content)")
        return out
    if dtc.file_digest(path) == itself.get("digest"):
        out["line"] = "The bytes match the stamp"
    else:
        out.update(state="differs", line="The bytes differ from the stamp",
                   changed=[os.path.basename(path)])
    return out


#: (stamp path, signature) → result. A check hashes files, and a panel redraws
#: many times a second: the result is kept until a file it read changes.
_CACHE: Dict[Tuple[str, Any], Dict[str, Any]] = {}


def _signature(stamp: Dict[str, Any], stamp_path: str, path: str) -> Any:
    def stat(p):
        try:
            s = os.stat(p)
            return (p, s.st_mtime_ns, s.st_size)
        except OSError:
            return (p, None, None)
    base = os.path.dirname(os.path.abspath(path))
    members = (stamp.get("self") or {}).get("members") or []
    files = [stat(path), stat(stamp_path)]
    files += [stat(os.path.join(base, *str(m.get("path", "")).split("/"))) for m in members]
    return tuple(files)


def verify_cached(stamp: Dict[str, Any], stamp_path: str, path: str) -> Dict[str, Any]:
    key = (stamp_path, _signature(stamp, stamp_path, path))
    if key not in _CACHE:
        _CACHE[key] = verify(stamp, path)
    return _CACHE[key]


def forget() -> None:
    """«Verify again»: drop every kept result."""
    _CACHE.clear()


def seal_of(path: Optional[str]) -> Optional[Dict[str, Any]]:
    """Everything the panel draws for ``path``, or None when it has no stamp:
    ``{stamp_path, stamp, raw, words, check, technical, canonical}``; a stamp
    that does not read gives ``{stamp_path, error}``."""
    stamp_path = find_stamp(path)
    if not stamp_path:
        return None
    try:
        stamp, raw = load(stamp_path)
    except (OSError, ValueError) as exc:
        return {"stamp_path": stamp_path, "error": str(exc)}
    return {"stamp_path": stamp_path, "stamp": stamp, "raw": raw,
            "words": words(stamp), "check": verify_cached(stamp, stamp_path, path),
            "technical": technical(stamp), "canonical": canonical_lines(stamp)}
