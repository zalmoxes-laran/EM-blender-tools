"""The digests of a resource that is more than one file — dtcstamp's, not ours.

E.D., 30 Sep 2026 (brain: *La risorsa e i suoi file*):

* the digest of a resource of several files is the **canonical list** of
  dtcstamp (``members_digest``: one ``role NUL path NUL sha256`` line per file,
  sorted by path, NFC);
* a tree (a tileset) has a ``content_digest`` that is **the same for the folder
  and for its .3tz**, whatever the archive's dates or compression.

Neither rule is written here. This module only finds dtcstamp: an installed one
that has the two functions, otherwise the copy in ``_vendor/`` (see its
README for why it is a copy). ``bpy``-free, so it is measured outside Blender.
"""

from __future__ import annotations

import json
import os
import posixpath
from typing import Any, Dict, List, Optional
from urllib.parse import unquote


def dtcstamp():
    """The dtcstamp module in use: installed if it can, vendored otherwise."""
    try:
        import dtcstamp as installed  # type: ignore
        if hasattr(installed, "content_digest") and hasattr(installed, "members_digest"):
            return installed
    except ImportError:
        pass
    try:
        from ._vendor import dtcstamp as vendored  # inside the addon package
    except ImportError:
        from _vendor import dtcstamp as vendored  # type: ignore  # tests: repo root on the path
    return vendored


def dtcstamp_origin() -> str:
    """Where the dtcstamp in use comes from, for a log line or a report."""
    module = dtcstamp()
    where = "vendored c05bb1f" if "_vendor" in (module.__name__ or "") else "installed"
    return f"dtcstamp {getattr(module, '__version__', '?')} ({where})"


def content_digest(path: str, *, entry_point: Optional[str] = "tileset.json") -> str:
    """``sha256:<hex>`` of the CONTENT of a tree — a folder or a ``.3tz``."""
    return dtcstamp().content_digest(path, entry_point=entry_point)


def tree_size(path: str, *, entry_point: Optional[str] = "tileset.json") -> int:
    """The bytes of the content (the sum of the members), not of the packing."""
    return sum(int(m.get("size_bytes") or 0)
               for m in dtcstamp().tree_members(path, entry_point=entry_point))


def members_digest(files: List[Dict[str, Any]]) -> str:
    """The identity of a resource of several files: dtcstamp's canonical list
    over ``[{role, path, checksum}]`` (the ``files`` of ``api.add_resource``)."""
    return dtcstamp().members_digest(
        [{"role": f.get("role") or "member", "path": f["path"],
          "digest": f["checksum"]} for f in files])


def gltf_members(gltf_path: str) -> List[Dict[str, str]]:
    """The files a ``.gltf`` names besides itself: ``[{path, file}]``.

    Read from the glTF's own ``buffers[].uri`` and ``images[].uri`` — what the
    file says it needs, not what lies next to it in the folder (two models
    exported into ``models/`` share the folder, and a texture used by both is a
    member of both). ``data:`` URIs are inside the file and are not members.
    ``path`` is relative to the ``.gltf``, posix, decoded; ``file`` is the
    absolute path on disk. A file that does not exist is still listed: the
    caller decides (a member that is not there is not something to hash).
    """
    with open(gltf_path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    base = os.path.dirname(os.path.abspath(gltf_path))
    out, seen = [], set()
    for section in ("buffers", "images"):
        for item in doc.get(section) or []:
            uri = str((item or {}).get("uri") or "")
            if not uri or uri.startswith("data:"):
                continue
            rel = posixpath.normpath(unquote(uri).replace("\\", "/"))
            if rel in seen:
                continue
            seen.add(rel)
            out.append({"path": rel,
                        "file": os.path.normpath(os.path.join(base, *rel.split("/")))})
    return out


# ── the tileset, in either form ─────────────────────────────────────────────

#: the media type of a 3D Tiles Archive (dtcstamp.MEDIA_TYPE_3TZ)
MEDIA_TYPE_3TZ = "application/vnd.maxar.archive.3tz+zip"
#: the 3tz index entry: never a member, never extracted
INDEX_NAME_3TZ = "@3dtilesIndex1@"


def is_3tz(path: str) -> bool:
    """A 3D Tiles Archive, by its extension (how the file is named and served)."""
    return str(path or "").lower().split("?")[0].endswith(".3tz")


def tileset_json(path: str) -> Optional[Dict[str, Any]]:
    """The parsed ``tileset.json`` of a tileset, whatever its form: a folder, the
    ``tileset.json`` itself, or a ``.3tz`` — read THROUGH the archive's index with
    s3Dgraphy's reader (`api.read_3tz_entry`), nothing extracted. None when there
    is none or it does not parse."""
    try:
        if os.path.isdir(path):
            path = os.path.join(path, "tileset.json")
        if is_3tz(path):
            from s3dgraphy import api
            raw = api.read_3tz_entry(path, "tileset.json")
            return json.loads(raw.decode("utf-8")) if raw else None
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None
