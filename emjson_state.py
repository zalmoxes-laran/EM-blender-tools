"""The em.json in memory against the em.json on disk (MICRO salva, 17 Oct 2026).

E.D. never saved an em.json from Blender: the button was an icon among four,
and nothing said the graph in memory had moved away from the file. Two things
live here, without bpy so they are tested without Blender:

* **the unsaved mark** — EM Tools kept no «changed» flag on a graph (measured:
  no dirty/modified state anywhere outside the icon and object caches). So the
  mark is a FINGERPRINT: the graph serialised the way the file is written
  (s3dgraphy's ``build_emjson``), hashed, taken when the file is loaded and
  when it is saved, and measured again while the panel is open. Beside the
  graphs, the scene's RM containers: a container is scene data until a save
  projects it into the graph, so a container not yet in the file, or changed
  since, is an unsaved change too;
* **the safety copy** — before an em.json is overwritten, the file as it was
  goes beside it as ``<name>.em.json.bak-<date-time>``, once per file per
  session (the first overwrite after Blender started).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import shutil
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

#: path → what the file held when last loaded or saved here
_SAVED: Dict[str, Dict[str, Any]] = {}
#: paths already copied aside in this session
_BACKED_UP: set = set()


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.expanduser(path or "")))


def graph_digest(graph: Any) -> str:
    """The graph as the file would carry it, hashed (~80 ms for Templu Mare's
    2,057 nodes: measured, so it is never taken on every redraw)."""
    from s3dgraphy.exporter.emjson_exporter import build_emjson
    section = build_emjson(graph)["graph"]
    blob = json.dumps(section, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


ContainerRow = Tuple[str, str, str, Tuple[str, ...]]


def containers_digest(rows: Iterable[ContainerRow]) -> str:
    """``rows``: ``(label, doc_node_id, group_node_id, mesh names)`` per
    container of the scene."""
    canon = sorted((str(a), str(b), str(c), sorted(str(m) for m in d))
                   for a, b, c, d in rows)
    return hashlib.sha256(json.dumps(canon).encode("utf-8")).hexdigest()


def _ungrouped(rows: Iterable[ContainerRow]) -> List[str]:
    return sorted(str(r[0]) for r in rows if not r[2] and r[3])


def mark_saved(path: str, graphs: Dict[str, Any],
               containers: Sequence[ContainerRow] = (), *,
               saved: bool = True) -> None:
    """The file at ``path`` now holds ``graphs`` (id → graph). ``saved=False``
    is a LOAD: the file was read, not written — a container the file does not
    carry is then still to be saved, while after a save a container left out
    (it concerns none of the file's graphs) is accepted as it is."""
    _SAVED[_norm(path)] = {
        "graphs": {gid: graph_digest(g) for gid, g in graphs.items() if g is not None},
        "containers": containers_digest(containers),
        "accepted": set(_ungrouped(containers)) if saved else set(),
    }


def note_deleted(path: str, graph_id: str) -> None:
    """A graph was DELETED from the file in the scene (not only taken off it):
    the file on disk still holds it until the next save, which is said."""
    state = _SAVED.get(_norm(path))
    if state is not None:
        state.setdefault("deleted", set()).add(graph_id)


def forget(path: str) -> None:
    _SAVED.pop(_norm(path), None)


def known(path: str) -> bool:
    return _norm(path) in _SAVED


def unsaved(path: str, graphs: Dict[str, Any],
            containers: Sequence[ContainerRow] = ()) -> List[str]:
    """Why the em.json at ``path`` is behind the scene, one sentence each;
    empty when it is not (or when this session never loaded nor saved it:
    then there is nothing to compare with)."""
    state = _SAVED.get(_norm(path))
    if state is None:
        return []
    said = []
    changed = new = 0
    for gid, graph in graphs.items():
        if graph is None:
            continue
        before = state["graphs"].get(gid)
        if before is None:
            new += 1
        elif graph_digest(graph) != before:
            changed += 1
    if changed:
        said.append("the graph changed" if changed == 1 and len(graphs) == 1
                    else f"{changed} graph(s) changed")
    if new:
        said.append(f"{new} graph(s) not in the file yet")
    gone = state.get("deleted") or set()
    if gone:
        said.append(f"{len(gone)} graph(s) deleted, still in the file "
                    f"({', '.join(sorted(gone))})")
    pending = [label for label in _ungrouped(containers)
               if label not in state["accepted"]]
    if pending:
        said.append(f"{len(pending)} RM container(s) not yet in the em.json "
                    f"({', '.join(pending)})")
    elif containers_digest(containers) != state["containers"]:
        said.append("RM containers changed")
    return said


def backup_name(path: str, when: Optional[_dt.datetime] = None) -> str:
    when = when or _dt.datetime.now()
    return f"{path}.bak-{when.strftime('%Y%m%d-%H%M%S')}"


def safety_copy(path: str, when: Optional[_dt.datetime] = None) -> Optional[str]:
    """Copy the em.json about to be overwritten beside itself, once per file per
    session. → the copy's path, or None (no file yet, or already copied)."""
    key = _norm(path)
    if key in _BACKED_UP or not os.path.isfile(path):
        return None
    target = backup_name(path, when)
    n = 2
    while os.path.exists(target):
        target = f"{backup_name(path, when)}-{n}"
        n += 1
    shutil.copy2(path, target)
    _BACKED_UP.add(key)
    return target


def reset_session() -> None:
    """For the tests: a new session, nothing loaded, nothing copied."""
    _SAVED.clear()
    _BACKED_UP.clear()
