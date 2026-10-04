"""G1 · a GraphML comes in once, and from then on the graph is an em.json.

Decision of E.D. (4 Oct 2026, `progetti/stratigraph/decisioni/
graphml-solo-in-entrata`): the GraphML is deprecated. It is read for a one-time
import; the graph then lives in an em.json saved beside it, under a name the
person confirms, and nothing writes a GraphML again.

So loading a GraphML slot (`import.em_graphml`) ends here:

1. the scene's models go into the graph (`containers.seat_scene_models`) and so
   do the proxies (`graph_updaters.update_semantic_shapes`) — a GraphML carries
   neither, the scene does, and an em.json keeps them;
2. the graph is written to the em.json (`graph_origins.save_file`, never over
   an existing file);
3. the slot becomes that em.json: its path, its format, its origin. The reload
   button of the row is then `import.em_emjson`, and «Save» writes the em.json.

The GraphML on disk is not touched.
"""

from __future__ import annotations

import os
from typing import Any, Dict

EMJSON_SUFFIX = ".em.json"


def proposed_emjson_path(graphml_path: str) -> str:
    """`<folder>/<stem>.em.json` beside the GraphML, or `<stem>-2.em.json`, …
    when that name is taken: the proposal never names an existing file."""
    folder = os.path.dirname(graphml_path)
    stem = os.path.basename(graphml_path)
    for ext in (".graphml", ".xml"):
        if stem.lower().endswith(ext):
            stem = stem[: -len(ext)]
            break
    candidate = os.path.join(folder, stem + EMJSON_SUFFIX)
    n = 2
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{stem}-{n}{EMJSON_SUFFIX}")
        n += 1
    return candidate


def normalised_emjson_path(path: str) -> str:
    """Exactly one `.em.json` at the end of what was typed."""
    root = path.strip()
    low = root.lower()
    if low.endswith(EMJSON_SUFFIX):
        return root
    if low.endswith(".json"):
        root = root[:-5]
    elif low.endswith(".graphml"):
        root = root[:-8]
    return root + EMJSON_SUFFIX


def count_proxies(graph) -> int:
    return sum(1 for n in graph.nodes
               if getattr(n, "node_type", None) == "semantic_shape")


def convert(context, index: int, emjson_path: str) -> Dict[str, Any]:
    """The loaded GraphML of row `index` → an em.json at `emjson_path`, and the
    row rebound to it. → `{path, models, proxies, sentence}`. Raises
    `FileExistsError` for a path that is already a file."""
    import bpy  # type: ignore
    from s3dgraphy import get_graph

    from .. import graph_origins
    from ..graph_updaters import update_semantic_shapes
    from ..rm_manager.containers import seat_scene_models

    em_tools = context.scene.em_tools
    row = em_tools.graphml_files[index]
    graph = get_graph(row.name)
    if graph is None:
        raise RuntimeError(f"the graph {row.name} is not loaded")
    out = os.path.abspath(bpy.path.abspath(normalised_emjson_path(emjson_path)))
    if os.path.exists(out):
        raise FileExistsError(
            f"{os.path.basename(out)} already exists: choose another name "
            f"(an em.json is never overwritten by an import)")
    graphml = row.graphml_path

    models = seat_scene_models(context.scene, graph)
    before = count_proxies(graph)
    update_semantic_shapes(graph)
    proxies = count_proxies(graph) - before

    result = graph_origins.save_file(out, [graph.graph_id], get_graph,
                                     active_graph_id=graph.graph_id)
    row.graphml_path = result.path
    if hasattr(row, "file_format"):
        row.file_format = "EMJSON"
    if hasattr(row, "origin_kind"):
        row.origin_kind = "FILE"
        row.origin_path = result.path
    try:
        from ..sync_manager.asset_versions import mark_saved
        mark_saved([row.name])
    except Exception:  # noqa: BLE001 — nothing pending is fine
        pass
    sentence = (
        f"GraphML read once into {os.path.basename(result.path)} — the graph "
        f"lives there now: {models['seated']} model(s) of the scene seated"
        + (f" ({models['present']} already in it)" if models["present"] else "")
        + f", {proxies} proxy(ies) added; "
        f"{os.path.basename(bpy.path.abspath(graphml))} is not written again")
    print(f"[GraphML → em.json] {sentence} · models {models}")
    return {"path": result.path, "models": models, "proxies": proxies,
            "sentence": sentence}
