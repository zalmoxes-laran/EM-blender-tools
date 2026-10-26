"""Where each graph of the scene comes from, and where saving takes it back.

A Blender scene can hold several graphs, and they need not come from the same
place: two em.json files (each a container with its own graphs and shelf), a
GraphML, a room on a StratiGraph node. The list in the EM panel used to be flat
and «Save» wrote every graph into the one file of the active row, so the second
file's graph ended up inside the first file. Here the list becomes a tree,
**origin → graphs**, the same shape as EMStudio's EMTree, and saving a graph
writes its origin and nothing else:

* a **file** origin is rewritten with ITS graphs only — the ones open in the
  scene, plus the ones the file holds that are not open here («retained»,
  written back unchanged), with its own shelf, DTC corpus, header and layouts;
* a **room** origin is not a file: the room receives every edit as it is made
  (the active graph's room is the one the edits go to), so there is nothing to
  write and saving says so.

The origin of a row is recorded on the row (``origin_kind`` / ``origin_path`` /
``origin_room`` / ``origin_node``). A row written by an older EMtools has none:
its origin is its ``graphml_path``, which is exactly where it was loaded from —
that is the whole migration, and it happens when the row is read, so an old
.blend opens unchanged.

No ``bpy`` here: the rows are read duck-typed, and the tests drive this module
with plain objects.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

KIND_FILE = "FILE"
KIND_ROOM = "ROOM"
KIND_NONE = "NONE"


@dataclass(frozen=True)
class Origin:
    """One branch of the tree: a file or a room."""

    kind: str
    key: str
    label: str
    path: str = ""
    room_id: str = ""
    base_url: str = ""

    @property
    def is_file(self) -> bool:
        return self.kind == KIND_FILE

    @property
    def is_room(self) -> bool:
        return self.kind == KIND_ROOM

    @property
    def is_emjson(self) -> bool:
        return self.is_file and self.path.lower().endswith((".em.json", ".json"))


def _norm_path(path: str, abspath: Optional[Callable[[str], str]] = None) -> str:
    if not path:
        return ""
    p = abspath(path) if abspath else path
    return os.path.normpath(os.path.abspath(os.path.expanduser(p)))


def _host_of(base_url: str) -> str:
    rest = base_url.split("://", 1)[-1]
    return rest.split("/", 1)[0]


def file_origin(path: str, *, abspath=None) -> Origin:
    full = _norm_path(path, abspath)
    return Origin(KIND_FILE, "file:" + full, os.path.basename(full) or full,
                  path=full)


def room_origin(base_url: str, room_id: str) -> Origin:
    base = (base_url or "").rstrip("/")
    host = _host_of(base) if base else "?"
    return Origin(KIND_ROOM, f"room:{base}/{room_id}",
                  f"room {room_id} on {host}", room_id=room_id, base_url=base)


NO_ORIGIN = Origin(KIND_NONE, "none", "No file")


def file_path_of(entry: Any) -> str:
    """The file a row's graph comes from, as the row writes it: a slot relative
    to the .blend (``//…``) first, then the recorded ``origin_path``, then the
    slot as it is."""
    slot = str(getattr(entry, "graphml_path", "") or "")
    if slot.startswith("//"):
        return slot
    return str(getattr(entry, "origin_path", "") or "") or slot


def origin_of(entry: Any, *, abspath=None) -> Origin:
    """The origin of one row of ``em_tools.graphml_files``.

    Recorded fields win; a row without them (an older .blend) takes its origin
    from ``graphml_path`` — where it was loaded from.

    Except a slot relative to the .blend (``//../EM/x.em.json``): it travels
    with the folder, while ``origin_path`` is the absolute path recorded where
    the folder was when the graph was loaded. A folder handed on kept the old
    place as its origin — the tree, «Save» and the study pointed there, an
    older copy of the em.json, until «Load» recorded the new one (measured on
    Templu Mare v2, 6 Oct 2026). The relative slot is the origin.
    """
    kind = str(getattr(entry, "origin_kind", "") or "")
    if kind == KIND_ROOM:
        room_id = str(getattr(entry, "origin_room", "") or "")
        if room_id:
            return room_origin(str(getattr(entry, "origin_node", "") or ""),
                               room_id)
    path = file_path_of(entry)
    if path:
        return file_origin(path, abspath=abspath)
    return NO_ORIGIN


def tree(entries: Iterable[Any], *, abspath=None) -> List[Tuple[Origin, List[int]]]:
    """``[(origin, [row index, …]), …]`` in the order the origins first appear.

    The order of the rows inside a branch is the order of the list, so the
    first graph loaded stays first (G1 reads it as the scene's reference).
    """
    branches: Dict[str, Tuple[Origin, List[int]]] = {}
    for index, entry in enumerate(entries):
        origin = origin_of(entry, abspath=abspath)
        if origin.key not in branches:
            branches[origin.key] = (origin, [])
        branches[origin.key][1].append(index)
    return list(branches.values())


def members_of(entries: Iterable[Any], origin: Origin, *, abspath=None) -> List[str]:
    """The graph ids the scene assigns to ``origin``."""
    return [str(getattr(e, "name", "")) for e in entries
            if origin_of(e, abspath=abspath).key == origin.key]


# ── the files' own containers ────────────────────────────────────────────────
#
# A file holds more than the graphs the scene shows: its shelf, its DTC corpus,
# its header (visibility, title), the layouts EMStudio drew, its version, and
# graphs that were never opened here. Writing the file back from the scene's
# graphs alone would drop all of that. So each file's container is remembered
# as it was loaded, and saving starts from it.

_containers: Dict[str, Any] = {}


def remember(path: str, container: Any) -> None:
    """Keep the container a file was loaded as (key: the normalised path)."""
    _containers[_norm_path(path)] = container


def remembered(path: str) -> Any:
    return _containers.get(_norm_path(path))


def forget_all() -> None:
    _containers.clear()


def peek_graph_ids(path: str) -> List[str]:
    """The study-graph ids a file holds, without parsing the graphs.

    Shelf and corpus members are left out: every container has a member called
    ``shelf``, and two files each with a shelf are not a conflict.
    """
    from s3dgraphy.container import is_dtc_corpus_member, is_shelf_member

    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    graphs = doc.get("graphs") if isinstance(doc, dict) else None
    if isinstance(graphs, dict):
        out = []
        for member_id, section in graphs.items():
            if not isinstance(section, dict):
                continue
            if is_shelf_member(section) or is_dtc_corpus_member(section):
                continue
            out.append(str(section.get("graph_id") or member_id))
        return out
    graph = (doc or {}).get("graph") if isinstance(doc, dict) else None
    if isinstance(graph, dict) and graph.get("graph_id"):
        return [str(graph["graph_id"])]
    return []


#: `peek_graph_names` memo: normalised path → (mtime, size, {graph_id: (name, code)})
_names: Dict[str, Tuple[float, int, Dict[str, Tuple[str, str]]]] = {}


def _text(value: Any) -> str:
    """A name as an em.json keeps it: a string, or a dict by language."""
    if isinstance(value, dict):
        for key in ("en", "it"):
            if value.get(key):
                return str(value[key])
        return next((str(v) for v in value.values() if v), "")
    return str(value or "")


def peek_graph_names(path: str) -> Dict[str, Tuple[str, str]]:
    """`{graph_id: (name, code)}` of the graphs an em.json holds, read once per
    version of the file (mtime and size), without building the graphs.

    P2 (6 Oct 2026): the graphs of a file that are listed and not loaded showed
    their UUIDs in the EM Data Tree (A_sanpietro's two graphs); the name is in
    the file, a line away. A file that cannot be read gives `{}`."""
    key = _norm_path(path)
    try:
        st = os.stat(key)
    except OSError:
        return {}
    memo = _names.get(key)
    if memo and memo[0] == st.st_mtime and memo[1] == st.st_size:
        return memo[2]
    out: Dict[str, Tuple[str, str]] = {}
    try:
        with open(key, encoding="utf-8") as fh:
            doc = json.load(fh)
        graphs = doc.get("graphs") if isinstance(doc, dict) else None
        for member_id, section in (graphs or {}).items():
            if not isinstance(section, dict):
                continue
            # the study's code first (E.D., 11 Oct 2026), see graph_code.py
            code = _section_code(section)
            gid = str(section.get("graph_id") or member_id)
            out[gid] = (_text(section.get("name")), code)
    except (OSError, ValueError):
        out = {}
    _names[key] = (st.st_mtime, st.st_size, out)
    return out


def _section_code(section: Dict[str, Any]) -> str:
    """``graph_code.section_code``, also when this module is loaded alone (by
    file, as the tests do) and has no package to import it from."""
    try:
        from .graph_code import section_code
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_emtools_graph_code",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "graph_code.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        section_code = module.section_code
    return section_code(section)


def conflicts(incoming_ids: Iterable[str], entries: Iterable[Any],
              target: Origin, *, abspath=None) -> List[Tuple[str, Origin]]:
    """Graph ids that are already open from ANOTHER origin.

    The same graph cannot come from two files: the scene keeps one graph per
    id, and the second file would silently replace the first one's graph —
    which then gets saved into the wrong file. EMStudio refuses the same move
    («already holds a graph with this id»).
    """
    open_from: Dict[str, Origin] = {}
    for e in entries:
        open_from.setdefault(str(getattr(e, "name", "")),
                             origin_of(e, abspath=abspath))
    out = []
    for gid in incoming_ids:
        where = open_from.get(gid)
        if where is not None and where.key != target.key and where.kind != KIND_NONE:
            out.append((gid, where))
    return out


@dataclass
class SaveResult:
    path: str
    written: List[str] = field(default_factory=list)
    retained: List[str] = field(default_factory=list)
    shelf: bool = False
    corpus: bool = False
    #: the file as it was before this save, copied beside it (first overwrite
    #: of the session), or ""
    backup: str = ""

    def sentence(self) -> str:
        parts = [f"saved {os.path.basename(self.path)} — "
                 f"{len(self.written)} graph(s) from this scene"]
        if self.retained:
            parts.append(f"{len(self.retained)} kept unchanged (in the file, "
                         f"not open here)")
        if self.shelf:
            parts.append("its shelf")
        if self.corpus:
            parts.append("its DTC corpus")
        said = ", ".join(parts) + "; no other file touched"
        if self.backup:
            said += f" (the previous file kept as {os.path.basename(self.backup)})"
        return said


def _safety_copy(full: str) -> Optional[str]:
    """MICRO salva · the em.json about to be overwritten, copied beside itself
    once per session (``emjson_state.safety_copy``). A copy that fails never
    stops the save: it is said in the console."""
    try:
        from . import emjson_state
    except ImportError:          # loaded as a lone module (the tests)
        import emjson_state  # type: ignore
    try:
        return emjson_state.safety_copy(full)
    except OSError as exc:
        print(f"[em.json save] no safety copy of {full}: {exc}")
        return None


def save_file(path: str, graph_ids: Iterable[str],
              live: Callable[[str], Any], *,
              active_graph_id: Optional[str] = None,
              base: Any = None) -> SaveResult:
    """Write ONE file: its graphs from the scene, everything else it held as is.

    ``live(graph_id)`` returns the scene's graph object (the multigraph
    manager's), or None. ``base`` is the container the file was loaded as; by
    default the remembered one, else the file on disk, else nothing (a new
    file). The remembered container is updated, so the next save continues the
    file's version chain.
    """
    from s3dgraphy.container import (Container, load_container_file,
                                     save_container_file)

    full = _norm_path(path)
    if base is None:
        base = remembered(full)
    if base is None and os.path.exists(full):
        try:
            base, _warnings = load_container_file(full)
        except Exception:  # noqa: BLE001 — an unreadable file is replaced, not merged
            base = None
    wanted = [g for g in graph_ids if g]
    result = SaveResult(path=full)

    graphs: Dict[str, Any] = {}
    if base is not None:
        for gid, graph in base.graphs.items():
            now = live(gid) if gid in wanted else None
            if now is not None:
                graphs[gid] = now
                result.written.append(gid)
            else:
                graphs[gid] = graph
                result.retained.append(gid)
    for gid in wanted:
        if gid in graphs:
            continue
        now = live(gid)
        if now is not None:
            graphs[gid] = now
            result.written.append(gid)

    active = active_graph_id if active_graph_id in graphs else (
        getattr(base, "active_graph_id", None) if base is not None else None)
    container = Container(
        graphs=graphs,
        shelf=getattr(base, "shelf", None),
        corpus=getattr(base, "corpus", None),
        active_graph_id=active if active in graphs else next(iter(graphs), None),
        header=dict(getattr(base, "header", {}) or {}),
        layout=dict(getattr(base, "layout", {}) or {}),
        layouts={k: v for k, v in (getattr(base, "layouts", {}) or {}).items()
                 if k in graphs},
        version=getattr(base, "version", None),
    )
    # the shared measures of time travel with the file too (they were dropped
    # here: a container's periodizations did not survive a save from Blender)
    if getattr(base, "periodizations", None) is not None:
        container.periodizations = base.periodizations
    result.shelf = container.shelf is not None
    result.corpus = container.corpus is not None
    result.backup = _safety_copy(full) or ""
    save_container_file(container, full)
    remember(full, container)
    return result


# ── MICRO contenuti-workspace-elimina-grafo · a graph LEAVES its em.json ─────
#
# «Remove graph» (−) takes a row off the scene and the graph stays in its file
# (the next save writes it back from the remembered container). Deleting it
# from the file is another gesture, and s3Dgraphy's: `remove_graph` on the
# file's container as the scene would write it — the scene's graphs for the
# rows it has, the remembered ones for the rest — so the report (nodes, edges,
# the links of the other graphs, the shelf entries only it used, the files
# nobody else names) is the same one EMStudio shows. Applied, the graph is
# taken out of the remembered container too: the next save no longer writes
# it. Files on disk are never touched.

def _base_of(full: str) -> Any:
    from s3dgraphy.container import load_container_file
    base = remembered(full)
    if base is None and os.path.exists(full):
        base, _warnings = load_container_file(full)
        remember(full, base)
    return base


def file_view(path: str, graph_ids: Iterable[str],
              live: Callable[[str], Any]) -> Any:
    """The container a save of ``path`` would write, as objects: the scene's
    graph for each id of ``graph_ids`` it has, the remembered one otherwise."""
    from s3dgraphy.container import Container
    full = _norm_path(path)
    base = _base_of(full)
    wanted = [g for g in graph_ids if g]
    graphs: Dict[str, Any] = {}
    for gid, graph in (getattr(base, "graphs", {}) or {}).items():
        now = live(gid) if gid in wanted else None
        graphs[gid] = now if now is not None else graph
    for gid in wanted:
        if gid not in graphs and live(gid) is not None:
            graphs[gid] = live(gid)
    view = Container(
        graphs=graphs,
        shelf=getattr(base, "shelf", None),
        corpus=getattr(base, "corpus", None),
        active_graph_id=getattr(base, "active_graph_id", None),
        header=dict(getattr(base, "header", {}) or {}),
        layout=dict(getattr(base, "layout", {}) or {}),
        layouts=dict(getattr(base, "layouts", {}) or {}),
        version=getattr(base, "version", None),
    )
    if getattr(base, "periodizations", None) is not None:
        view.periodizations = base.periodizations
    return view


def removal_api():
    """s3Dgraphy's `remove_graph`, or None when the s3Dgraphy in use is older
    than the operation (the bundled wheel before it was bundled)."""
    try:
        from s3dgraphy.graph_removal import remove_graph
    except ImportError:
        return None
    return remove_graph


def remove_from_file(path: str, graph_id: str, graph_ids: Iterable[str],
                     live: Callable[[str], Any], *, links: str = "keep",
                     shelf: str = "keep", dry_run: bool = False) -> Dict[str, Any]:
    """s3Dgraphy's report on deleting ``graph_id`` from the em.json at ``path``
    (``dry_run``), or the deletion itself: the remembered container loses the
    graph (its layout too), the other graphs' links are kept marked or dropped,
    the shelf entries only it used stay or go. Raises ImportError when the
    s3Dgraphy in use has no `remove_graph`, its GraphRemovalError when the
    graph cannot be removed (the last one, the shelf…)."""
    remove_graph = removal_api()
    if remove_graph is None:
        raise ImportError("this s3Dgraphy has no graph_removal (newer than the "
                          "bundled one)")
    full = _norm_path(path)
    view = file_view(full, graph_ids, live)
    report = remove_graph(view, graph_id, links=links, shelf=shelf,
                          dry_run=dry_run)
    if dry_run:
        return report
    base = _base_of(full)
    if base is not None:
        base.graphs = {gid: g for gid, g in view.graphs.items()}
        base.layouts = dict(view.layouts)
        base.layout = dict(view.layout)
        base.active_graph_id = view.active_graph_id
        base.shelf = view.shelf
        remember(full, base)
    return report


def objects_of_graph(graph: Any, object_names: Iterable[str],
                     code: str = "") -> List[str]:
    """The Blender objects tied to ``graph`` by name: a node's name, or the
    name with the graph's code before it (``CODE.US12``) — proxies, RMs,
    documents. Given the scene's object names, so it needs no bpy."""
    names = set(object_names)
    out = []
    for node in getattr(graph, "nodes", []) or []:
        name = _text(getattr(node, "name", ""))
        if not name:
            continue
        for candidate in ((f"{code}.{name}", name) if code else (name,)):
            if candidate in names and candidate not in out:
                out.append(candidate)
    return sorted(out)

