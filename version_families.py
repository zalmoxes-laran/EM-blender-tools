"""The versions of an asset in two families: the author's levels and the
versions derived by the recipe (MICRO salva, 17 Oct 2026).

Measured on Templu Mare v3.2: every version of the dataset is made by a
``lod_generation`` step, the author's too — the survey's LOD0/LOD1/LOD2 OBJ
are steps of tool «Blender» («OBJ export of the LOD0 mesh…», «decimation and
texture baking…, Blender 2.92 (2021)»). The kind of the step is therefore NOT
the sign. The sign is what «Prepare for a use…» writes in the step's
parameters: ``tool = "EM Tools · Prepare for a use"`` (``version_recipe
.RECIPE_TOOL``) — 196 of the 230 steps, all of them dated 6 Oct 00:08, none of
the author's.

* survey: the author's LOD0, LOD1, LOD2; the recipe's lod3 (a compression of
  LOD2) and lod4 (a decimation) are derived versions;
* reconstruction: no level of the author — the model is WHOLE; its lod0 (the
  whole model, re-encoded) and lod1 (a decimation) are derived versions.

The names of the files and the ``lod_level`` written stay as they are: this
module only reads. No bpy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from .version_recipe import RECIPE_TOOL
except ImportError:  # loaded as a lone module (the tests)
    from version_recipe import RECIPE_TOOL  # type: ignore

#: what the panel says of a model the author did not split into levels
WHOLE = "Whole: the author made no levels of detail"


def _data(node: Any) -> Dict[str, Any]:
    return dict(getattr(node, "data", None) or {})


def is_derived(step_data: Optional[Dict[str, Any]]) -> bool:
    """Whether a ``lod_generation`` step is the recipe's («Prepare for a
    use…»). ``step_data`` is the step node's ``data``."""
    params = (step_data or {}).get("parameters") or {}
    return isinstance(params, dict) and params.get("tool") == RECIPE_TOOL


def families(graph: Any, asset_id: str) -> Dict[str, Any]:
    """``{master, author, derived, whole}`` for the asset of ``asset_id``:
    s3dgraphy's ``versions_of`` split by the sign of the step that made each
    version. ``whole``: no level of the author."""
    from s3dgraphy.resources.versions import versions_of
    entries = versions_of(graph, asset_id)
    master = entries[0] if entries and entries[0].get("master") else None
    author: List[Dict[str, Any]] = []
    derived: List[Dict[str, Any]] = []
    for entry in entries:
        if entry.get("master"):
            continue
        step = graph.find_node_by_id(entry.get("process_id") or "")
        data = _data(step) if step is not None else {}
        entry = dict(entry, technique=str(data.get("technique") or ""),
                     ratio=(data.get("parameters") or {}).get("ratio"))
        (derived if is_derived(data) else author).append(entry)
    return {"master": master, "author": author, "derived": derived,
            "whole": not author}


def _uses(entry: Dict[str, Any]) -> str:
    return ", ".join(entry.get("use") or []) or "no use"


def author_label(entry: Dict[str, Any]) -> str:
    """An author's level: its level, as written (``LOD1 · analysis``)."""
    level = str(entry.get("level") or entry.get("lod_level") or "?").upper()
    return f"{level} · {_uses(entry)}"


def derived_label(entry: Dict[str, Any]) -> str:
    """A version of the recipe: never a level of the author — «Derived version
    · uses», then what the recipe did."""
    said = f"Derived version · {_uses(entry)}"
    technique = entry.get("technique") or ""
    ratio = entry.get("ratio")
    if technique == "decimation" and ratio not in (None, 1, 1.0):
        said += f" · decimated to {float(ratio):.2f}"
    elif technique:
        said += f" · {technique.replace('_', ' ')}"
    return said


def lines(graph: Any, asset_id: str) -> List[tuple]:
    """What the panel draws, in order: ``(kind, text, version id)`` with kind
    ``head`` / ``author`` / ``whole`` / ``derived``."""
    fam = families(graph, asset_id)
    out = [("head", "Author's levels", "")]
    if fam["whole"]:
        out.append(("whole", WHOLE, ""))
    out += [("author", author_label(e), e["id"]) for e in fam["author"]]
    if fam["derived"]:
        out.append(("head", "Derived versions (the recipe's)", ""))
        out += [("derived", derived_label(e), e["id"]) for e in fam["derived"]]
    return out


def is_derived_info(graph: Any, info: Optional[Dict[str, Any]]) -> bool:
    """Whether the version ``info`` (s3dgraphy's ``version_info``) was made by
    the recipe."""
    if not info or info.get("master"):
        return False
    step = graph.find_node_by_id(info.get("process_id") or "")
    return step is not None and is_derived(_data(step))
