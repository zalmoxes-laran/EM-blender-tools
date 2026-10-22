"""Removing versions of an asset: what goes, from the graph and from the disk
(E.D., 22 Oct 2026 — «devo poter aggiungere ma anche rimuovere le versioni»;
the removal takes the file on disk with it, after a confirmation, and the
dtcstamp beside it, and the node in the graph).

A version is removed WHOLE:

* its chain of revisions (a version made again with another recipe is the
  same version), each with the ``lod_generation`` step that made it and the
  file nodes only it holds;
* the versions made FROM it (a lod1 decimated from the lod0 removed): they
  would hang off nothing, so they go too, and the confirmation says so;
* the master never: it is the asset, not one of its versions.

On disk: the files the removed resources name (a glTF with its .bin and
textures, a glb), the stamp beside each (``<file>.stamp.json``, its hints and
the previous stamps kept at a revision), and the folder of a glTF when it is
left empty. A file another resource of the graph still names is kept. The
files are split between the ones EM Tools wrote in its cache (``em_cache/``)
and the ones outside it (an OBJ the author imported with «Add a level of
detail…»): the operator deletes the first after the confirmation, the second
only when asked.

This module decides and does the graph and the disk; the library meshes and
the objects are the Blender side's (``sync_manager.asset_versions``). No bpy.
"""

from __future__ import annotations

import glob
import os
from typing import Any, Callable, Dict, Iterable, List, Optional

EDGE_HAD_INPUT = "dtc_had_input"
EDGE_HAD_OUTPUT = "dtc_had_output"
EDGE_HAS_FILE = "has_file"
EDGE_REVISION_OF = "was_revision_of"
EDGE_DERIVED_FROM = "dtc_derived_from"
LOD_KIND = "lod_generation"
#: the edges that are the version's own chain, not a citation of it
CHAIN_EDGES = {EDGE_HAD_INPUT, EDGE_HAD_OUTPUT, EDGE_HAS_FILE, EDGE_REVISION_OF,
               EDGE_DERIVED_FROM}

STAMP_SUFFIX = ".stamp.json"
HINTS_SUFFIX = ".hints.json"
FROM_HINTS_SUFFIX = ".from.hints.json"
PREVIOUS_INFIX = ".prev-"


def _data(node: Any) -> Dict[str, Any]:
    return getattr(node, "data", None) or {}


def _kind(node: Any) -> str:
    return str(getattr(node, "node_type", "") or "")


def _chain(graph, res_id: str) -> List[str]:
    """The revisions of ``res_id``, oldest first, the newer ones included."""
    out = [res_id]
    seen = {res_id}
    changed = True
    while changed:
        changed = False
        for e in graph.edges:
            if e.edge_type != EDGE_REVISION_OF:
                continue
            # newer ──was_revision_of──▶ older
            for a, b in ((e.edge_source, e.edge_target), (e.edge_target, e.edge_source)):
                if b in seen and a not in seen:
                    seen.add(a)
                    out.append(a)
                    changed = True
    return out


def _made_from(graph, res_ids: Iterable[str]) -> List[str]:
    """The resources a ``lod_generation`` step made from any of ``res_ids``."""
    wanted = set(res_ids)
    procs = {e.edge_source for e in graph.edges
             if e.edge_type == EDGE_HAD_INPUT and e.edge_target in wanted}
    out = []
    for e in graph.edges:
        if e.edge_type != EDGE_HAD_OUTPUT or e.edge_source not in procs:
            continue
        proc = graph.find_node_by_id(e.edge_source)
        if proc is None or _data(proc).get("dtc_kind") != LOD_KIND:
            continue
        child = graph.find_node_by_id(e.edge_target)
        if child is not None and _kind(child) == "resource" and e.edge_target not in wanted:
            out.append(e.edge_target)
    return out


def _is_master(graph, res_id: str) -> bool:
    """A resource no ``lod_generation`` step made: the asset itself."""
    for e in graph.edges:
        if e.edge_type == EDGE_HAD_OUTPUT and e.edge_target == res_id:
            proc = graph.find_node_by_id(e.edge_source)
            if proc is not None and _data(proc).get("dtc_kind") == LOD_KIND:
                return False
    return True


def _urls(graph, res_id: str) -> List[str]:
    """The locations a resource names: its own url, its file nodes' urls."""
    node = graph.find_node_by_id(res_id)
    out = []
    url = str(_data(node).get("url") or getattr(node, "url", "") or "") if node is not None else ""
    if url:
        out.append(url)
    for e in graph.edges:
        if e.edge_type == EDGE_HAS_FILE and e.edge_source == res_id:
            f = graph.find_node_by_id(e.edge_target)
            furl = str(_data(f).get("url") or getattr(f, "url", "") or "") if f is not None else ""
            if furl:
                out.append(furl)
    return out


def _local(url: str) -> bool:
    return bool(url) and "://" not in url


def _absolute(url: str, base: Optional[str]) -> str:
    path = url
    if path.startswith("//") and base:             # Blender's relative form
        path = os.path.join(base, path[2:])
    elif not os.path.isabs(path) and base:
        path = os.path.join(base, path)
    return os.path.normpath(path)


def stamp_files(path: str, stamp_path_for: Optional[Callable[[str], str]] = None
                ) -> List[str]:
    """The stamp beside ``path`` and what goes with it: its hints, the hints
    of its parents, the previous stamps a revision kept — the ones on disk."""
    stamp = stamp_path_for(path) if stamp_path_for else path + STAMP_SUFFIX
    stem = stamp[:-len(STAMP_SUFFIX)] if stamp.endswith(STAMP_SUFFIX) else stamp
    found = [stamp, stem + HINTS_SUFFIX, stem + FROM_HINTS_SUFFIX]
    found += sorted(glob.glob(glob.escape(stem) + PREVIOUS_INFIX + "*" + STAMP_SUFFIX))
    return [p for p in found if os.path.isfile(p)]


def removal_plan(graph, version_ids: Iterable[str], *, cache_root: str = "",
                 base: Optional[str] = None,
                 stamp_path_for: Optional[Callable[[str], str]] = None
                 ) -> Dict[str, Any]:
    """What removing ``version_ids`` takes away. → ``{resources, file_nodes,
    processes, removed (all node ids), versions [{id, name, level, why}],
    refused [{id, why}], files_cache, files_outside, stamps_cache,
    stamps_outside, kept_shared,
    cited_by [{id, name, source}]}``. Reads only.

    ``cache_root``: the folder EM Tools writes its versions in (``em_cache``);
    ``base``: the folder relative urls are read from (the .blend's)."""
    resources: List[str] = []
    versions: List[Dict[str, Any]] = []
    refused: List[Dict[str, Any]] = []
    asked = [str(v) for v in version_ids if v]
    for vid in asked:
        if graph.find_node_by_id(vid) is None:
            refused.append({"id": vid, "why": "not in this graph"})
            continue
        if vid in resources:
            continue
        chain = _chain(graph, vid)
        if any(_is_master(graph, r) for r in chain):
            refused.append({"id": vid, "why": "the master is the asset, not a version"})
            continue
        todo = [(chain, "asked")]
        while todo:
            ids, why = todo.pop(0)
            fresh = [r for r in ids if r not in resources]
            if not fresh:
                continue
            resources += fresh
            head = graph.find_node_by_id(ids[-1])
            versions.append({"id": ids[-1], "name": getattr(head, "name", "") or ids[-1],
                             "level": _level_of(graph, ids), "why": why,
                             "revisions": len(ids)})
            for child in _made_from(graph, ids):
                todo.append((_chain(graph, child),
                             f"made from {getattr(head, 'name', '') or ids[-1]}"))
    gone = set(resources)
    file_nodes = sorted({e.edge_target for e in graph.edges
                         if e.edge_type == EDGE_HAS_FILE and e.edge_source in gone}
                        - {e.edge_target for e in graph.edges
                           if e.edge_type == EDGE_HAS_FILE and e.edge_source not in gone})
    processes = []
    for e in graph.edges:
        if e.edge_type != EDGE_HAD_OUTPUT or e.edge_target not in gone:
            continue
        proc = graph.find_node_by_id(e.edge_source)
        if proc is None or _data(proc).get("dtc_kind") != LOD_KIND:
            continue
        outs = {o.edge_target for o in graph.edges
                if o.edge_type == EDGE_HAD_OUTPUT and o.edge_source == proc.node_id}
        if outs <= gone and proc.node_id not in processes:
            processes.append(proc.node_id)
    removed = set(resources) | set(file_nodes) | set(processes)
    # the files: those only the removed resources name
    named_by_others = set()
    for node in graph.nodes:
        if node.node_id in removed:
            continue
        if _kind(node) in ("resource", "resource_file") or _data(node).get("url"):
            for url in _urls(graph, node.node_id):
                if _local(url):
                    named_by_others.add(_absolute(url, base))
    files_cache, files_outside, kept_shared = [], [], []
    stamps_cache, stamps_outside = [], []
    cache = os.path.normpath(cache_root) + os.sep if cache_root else ""
    for rid in resources:
        for url in _urls(graph, rid):
            if not _local(url):
                continue
            path = _absolute(url, base)
            if path in named_by_others:
                kept_shared.append(path)
                continue
            if not os.path.isfile(path):
                continue
            inside = bool(cache) and path.startswith(cache)
            bucket = files_cache if inside else files_outside
            if path not in bucket:
                bucket.append(path)
            sidecars = stamps_cache if inside else stamps_outside
            for s in stamp_files(path, stamp_path_for):
                if s not in sidecars:
                    sidecars.append(s)
    cited = []
    for e in graph.edges:
        if e.edge_target in gone and e.edge_source not in removed \
                and e.edge_type not in CHAIN_EDGES:
            src = graph.find_node_by_id(e.edge_source)
            cited.append({"id": e.edge_target, "source": e.edge_source,
                          "name": getattr(src, "name", "") or e.edge_source,
                          "edge_type": e.edge_type})
    return {"resources": resources, "file_nodes": file_nodes, "processes": processes,
            "removed": sorted(removed), "versions": versions, "refused": refused,
            "files_cache": files_cache, "files_outside": files_outside,
            "stamps_cache": stamps_cache, "stamps_outside": stamps_outside,
            "kept_shared": sorted(set(kept_shared)),
            "cited_by": cited}


def _level_of(graph, chain: List[str]) -> str:
    """The level the step that made the version gave it (its parameters)."""
    gone = set(chain)
    for e in graph.edges:
        if e.edge_type == EDGE_HAD_OUTPUT and e.edge_target in gone:
            proc = graph.find_node_by_id(e.edge_source)
            level = ((_data(proc).get("parameters") or {}) if proc is not None else {}).get("level")
            if level:
                return str(level)
    return ""


def remove_from_graph(graph, plan: Dict[str, Any]) -> int:
    """The plan's nodes out of the graph, with every edge that touches them.
    → how many nodes went."""
    n = 0
    for nid in plan.get("removed") or []:
        if graph.find_node_by_id(nid) is not None:
            graph.remove_node(nid)
            n += 1
    return n


def delete_files(paths: Iterable[str]) -> Dict[str, List[str]]:
    """Delete ``paths`` (files only) and then the folders they leave empty
    (the folder of a glTF with its textures). → ``{deleted, failed}``."""
    deleted, failed, folders = [], [], []
    for path in paths:
        try:
            if os.path.isfile(path):
                os.remove(path)
                deleted.append(path)
                folders.append(os.path.dirname(path))
        except OSError as exc:
            failed.append(f"{path}: {exc}")
    for folder in sorted(set(folders), key=len, reverse=True):
        try:
            while folder and os.path.isdir(folder) and not os.listdir(folder) \
                    and os.path.basename(folder) != "versions":
                os.rmdir(folder)
                folder = os.path.dirname(folder)
        except OSError:
            pass
    return {"deleted": deleted, "failed": failed}


def paths_to_delete(plan: Dict[str, Any], *, outside: bool = False) -> List[str]:
    """The files and stamps the removal deletes: the cache's, and the ones
    outside it when ``outside``."""
    out = list(plan.get("files_cache") or []) + list(plan.get("stamps_cache") or [])
    if outside:
        out += list(plan.get("files_outside") or []) + list(plan.get("stamps_outside") or [])
    return out


def merge(plans: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Several plans as one (the selection's assets): lists joined, no repeats."""
    out: Dict[str, Any] = {}
    for p in plans:
        for k, v in p.items():
            if not isinstance(v, list):
                continue
            have = out.setdefault(k, [])
            for item in v:
                if item not in have:
                    have.append(item)
    return out


def summary_lines(plan: Dict[str, Any], *, with_files: bool = True,
                  outside: bool = False, limit: int = 6) -> List[str]:
    """What the confirmation says, one line each."""
    out = []
    vs = plan.get("versions") or []
    for v in vs[:limit]:
        level = f"{v['level']} · " if v.get("level") else ""
        made = "" if v["why"] == "asked" else f"  ({v['why']})"
        out.append(f"{level}{v['name']}{made}")
    if len(vs) > limit:
        out.append(f"… and {len(vs) - limit} more")
    nc, no = len(plan.get("files_cache") or []), len(plan.get("files_outside") or [])
    ns = len(plan.get("stamps_cache") or []) + (len(plan.get("stamps_outside") or [])
                                               if outside else 0)
    if with_files:
        out.append(f"Files deleted from disk: {nc + (no if outside else 0)}"
                   f" · dtcstamps: {ns}")
    if no and not outside:
        out.append(f"{no} file(s) outside the cache stay on disk")
    if plan.get("kept_shared"):
        out.append(f"{len(plan['kept_shared'])} file(s) stay: other resources name them")
    for r in (plan.get("refused") or [])[:3]:
        out.append(f"not removed: {r['id']} — {r['why']}")
    return out
