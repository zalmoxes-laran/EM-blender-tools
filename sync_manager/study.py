"""S1 · the STUDY of this scene, as a room holds it (invariants of 5 Oct 2026).

I-1: an em.json is a study. I-2: a room writes one study, and a study is written
by one room only. So «Create a collaborative room from this study…» takes the
em.json WHOLE — its graphs (the ones open here and the ones the file holds that
are not), its shelf, its DTC corpus — and not the active graph alone (D-A, which
the invariants replace now that EM Tools names the graph in every operation).

This module says what the study is (`study_of`), how a room is born with it
(`birth_sections`: the sections, EMPTY — the node's G2 — their content coming
afterwards as operations naming the graph, `seed_plan`), and where it already
lives (`room_of_study`): a study in a room is offered that room, never a second
one.

Where a study lives is remembered twice, because a file outlives a session: on
the rows of the EM Data Tree (`origin_kind = ROOM`, as before), and in the
study's own header (`header.room = {node, room_id}`), which the next Save
writes into the em.json.
"""

from typing import Any, Dict, List, Optional

ROOM_KEY = "room"


def _abspath(path: str) -> str:
    try:
        import bpy  # type: ignore
        return bpy.path.abspath(path)
    except Exception:  # noqa: BLE001 — outside Blender
        return path


def study_of(context, graph) -> Dict[str, Any]:
    """`{origin, graphs: {id: Graph}, shelf, corpus, header, active, path}`.

    From the active row of the EM Data Tree: a file origin gives its graphs in
    the scene plus the ones the file holds and the scene does not show, with
    the file's shelf, corpus and header; any other origin is the graph alone."""
    from s3dgraphy import get_graph
    from .. import graph_origins as go

    em_tools = getattr(context.scene, "em_tools", None)
    entries = list(getattr(em_tools, "graphml_files", ()) or ())
    entry = None
    if em_tools is not None and 0 <= em_tools.active_file_index < len(entries):
        entry = entries[em_tools.active_file_index]
    gid = str(getattr(graph, "graph_id", "") or "")
    out: Dict[str, Any] = {"graphs": {gid: graph} if gid else {}, "shelf": None,
                           "corpus": None, "header": {}, "active": gid, "path": "",
                           "origin": go.NO_ORIGIN}
    if entry is None:
        return out
    origin = go.origin_of(entry, abspath=_abspath)
    out["origin"] = origin
    # the FILE of the study, also when its rows now say «room» (they keep the
    # path they were loaded from)
    path = go.file_path_of(entry)
    file_origin = go.file_origin(path, abspath=_abspath) if path else None
    if file_origin is None or not file_origin.is_emjson:
        return out
    out["path"] = file_origin.path
    ids = [str(getattr(e, "name", "")) for e in entries
           if go.file_path_of(e)
           and go.file_origin(go.file_path_of(e), abspath=_abspath).key == file_origin.key]
    base = go.remembered(file_origin.path)
    if base is None:
        try:
            from s3dgraphy.container import load_container_file
            import os
            if os.path.exists(file_origin.path):
                base, _w = load_container_file(file_origin.path)
                go.remember(file_origin.path, base)
        except Exception:  # noqa: BLE001 — the scene's graphs are still the study
            base = None
    graphs: Dict[str, Any] = {}
    for g in ids:
        live = get_graph(g)
        if live is not None:
            graphs[g] = live
    if base is not None:
        for g, member in base.graphs.items():
            graphs.setdefault(g, member)          # in the file, not open here
        out["shelf"] = getattr(base, "shelf", None)
        out["corpus"] = getattr(base, "corpus", None)
        out["header"] = dict(getattr(base, "header", {}) or {})
    out["graphs"] = graphs or out["graphs"]
    return out


def room_of_study(context, study: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Where this study is written, if it is: `{node, room_id}` or None.

    The rows of its graphs first (a room origin), then the study's header."""
    em_tools = getattr(context.scene, "em_tools", None)
    for e in list(getattr(em_tools, "graphml_files", ()) or ()):
        if str(getattr(e, "name", "")) in study["graphs"] and \
                str(getattr(e, "origin_kind", "")) == "ROOM" and getattr(e, "origin_room", ""):
            return {"node": str(getattr(e, "origin_node", "") or ""),
                    "room_id": str(e.origin_room)}
    marked = (study.get("header") or {}).get(ROOM_KEY)
    if isinstance(marked, dict) and marked.get("room_id"):
        return {"node": str(marked.get("node") or ""), "room_id": str(marked["room_id"])}
    return None


def mark_room(study: Dict[str, Any], node: str, room_id: str) -> None:
    """Write in the study's header (the remembered container of its file) that
    a room writes it: the next Save puts it in the em.json."""
    from .. import graph_origins as go
    if not study.get("path"):
        return
    base = go.remembered(study["path"])
    if base is not None and isinstance(getattr(base, "header", None), dict):
        base.header[ROOM_KEY] = {"node": (node or "").rstrip("/"), "room_id": room_id}
    study.setdefault("header", {})[ROOM_KEY] = {"node": (node or "").rstrip("/"),
                                                "room_id": room_id}


def _section(graph) -> Dict[str, Any]:
    from s3dgraphy.exporter.emjson_exporter import build_emjson
    return build_emjson(graph)["graph"]


def members(study: Dict[str, Any]) -> List[Any]:
    """`[(graph_id, Graph)]`: the study's graphs, then its shelf and corpus."""
    out = [(g, graph) for g, graph in study["graphs"].items()]
    for key in ("shelf", "corpus"):
        member = study.get(key)
        if member is not None:
            out.append((str(getattr(member, "graph_id", "") or key), member))
    return out


def birth_sections(study: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The sections a room is born with: `{graph_id, name, data}`, EMPTY."""
    out = []
    for gid, graph in members(study):
        section = _section(graph)
        item: Dict[str, Any] = {"graph_id": gid,
                                "name": str(section.get("name") or getattr(graph, "name", "")
                                            or gid)}
        if isinstance(section.get("data"), dict):
            item["data"] = dict(section["data"])
        out.append(item)
    return out


def seed_plan(study: Dict[str, Any]) -> List[Any]:
    """`[(graph_id, graph, section)]`: what is seeded, graph by graph."""
    return [(gid, graph, _section(graph)) for gid, graph in members(study)]
