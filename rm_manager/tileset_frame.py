"""A tileset that is seen: the container's own epochs, Automatic, the frame.

MICRO tileset, shift e epoche (E.D., 25 Oct 2026). Two things went wrong with
E.D.'s first tileset of the whole Basilica Iulia:

1. **The container had no mesh yet.** «tls» held 0 models and the tileset as
   its alternative; its epoch, «Epoch 1», was said by the Document wrapping it
   (D.1 ``has_first_epoch`` → Epoch 1, D.1 ``has_representation_model`` →
   the group). The epochs of a container's alternative were its members' —
   none — so it lay in no epoch. s3Dgraphy now says it (em_visual_rules
   1.6.40, ``alternatives.container_epochs``): a container whose members have
   no epoch takes its OWN (``resources.alternatives.container_own_epochs``),
   and a container with an alternative and no member lights the alternative
   (``choose_alternative``). Here: :func:`container_epochs` and
   :func:`effective_mode`, calling s3Dgraphy when it has the rule; with an
   older s3Dgraphy (the bundled wheel before it) the same reading is done here
   from the same edges, and the scene's «Epochs of this set» close the chain.

2. **The coordinates were shifted.** RealityScan wrote E − 291407,
   N − 4640813 declared as EPSG:6708: the root's transform put the Basilica on
   the equator. ``data.frame`` on the tileset's resource (s3Dgraphy nodes
   datamodel 1.6.38, ``geometry.frame``) says «the coordinates of this file
   are CRS X minus shift S»; here: :func:`read_frame`, :func:`make_frame`,
   :func:`write_frame` (s3Dgraphy's ``set_frame``, or the same write on an
   older s3Dgraphy), :func:`study_frame` (the graph's ``geo_position`` or the
   scene's georeferencing) and :func:`placement_target` (where the box of the
   alternative lands in the Blender scene).

No ``bpy`` here: measured by pytest (``tests/test_tileset_frame.py``).
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

#: the rule's data as em_visual_rules 1.6.40 writes it, for an s3Dgraphy that
#: has not got it yet (``alternatives.container_epochs``)
_FALLBACK_RULE = {
    "epoch_edge": "has_representation_model",
    "epoch_types": ["EpochNode"],
    "member_edge": "is_in_representation_model_group",
    "container_epochs": {"wrapper_edge": "has_representation_model",
                         "wrapper_types": ["document"],
                         "epoch_edges": ["has_first_epoch", "survive_in_epoch"]},
}

FRAME_KEY = "frame"
SOURCES = ("manual", "graph", "file")


# ── the epochs of a container ────────────────────────────────────────────────

def has_container_rule() -> bool:
    """The installed s3Dgraphy has the container's own epochs (1.6.40)."""
    try:
        from s3dgraphy.resources.alternatives import container_own_epochs  # noqa: F401
        return True
    except ImportError:
        return False


def _node(graph, node_id):
    try:
        return graph.find_node_by_id(node_id)
    except Exception:  # noqa: BLE001
        return None


def _type(node) -> str:
    return str(getattr(node, "node_type", "") or "")


def _rule() -> Dict[str, Any]:
    try:
        from s3dgraphy.resources.alternatives import alternatives_rule
        r = dict(alternatives_rule() or {})
    except Exception:  # noqa: BLE001
        r = {}
    for k, v in _FALLBACK_RULE.items():
        r.setdefault(k, v)
    return r


def _epochs_reaching(graph, ids: Iterable[str], rule: Dict[str, Any]) -> List[str]:
    want = set(ids)
    types = set(rule.get("epoch_types") or ())
    out = set()
    for e in graph.edges:
        if e.edge_type == rule.get("epoch_edge") and e.edge_target in want \
                and _type(_node(graph, e.edge_source)) in types:
            out.add(e.edge_source)
    return sorted(out)


def _members_deep(graph, group_id: str, rule: Dict[str, Any]) -> List[str]:
    try:
        from s3dgraphy.resources.alternatives import members_of
        return members_of(graph, group_id, deep=True)
    except ImportError:
        pass
    out, stack, seen = [], [group_id], {group_id}
    while stack:
        g = stack.pop()
        for e in graph.edges:
            if e.edge_type == rule.get("member_edge") and e.edge_target == g:
                m = e.edge_source
                if _type(_node(graph, m)) == "RepresentationModelNodeGroup":
                    if m not in seen:
                        seen.add(m)
                        stack.append(m)
                elif m not in out:
                    out.append(m)
    return out


def own_epochs_local(graph, group_id: str, rule: Optional[Dict[str, Any]] = None) -> List[str]:
    """The container's OWN epochs read here, as s3Dgraphy 1.6.40's
    ``container_own_epochs`` reads them: an epoch reaching the group, and the
    epochs of the Document that wraps it. For an s3Dgraphy without the rule."""
    r = rule or _rule()
    ce = r.get("container_epochs") or _FALLBACK_RULE["container_epochs"]
    out = set(_epochs_reaching(graph, [group_id], r))
    types = set(r.get("epoch_types") or ())
    wtypes = set(ce.get("wrapper_types") or ())
    wrappers = {e.edge_source for e in graph.edges
                if e.edge_type == ce.get("wrapper_edge") and e.edge_target == group_id
                and _type(_node(graph, e.edge_source)) in wtypes}
    for e in graph.edges:
        if e.edge_source in wrappers and e.edge_type in (ce.get("epoch_edges") or ()) \
                and _type(_node(graph, e.edge_target)) in types:
            out.add(e.edge_target)
    return sorted(out)


def container_epochs(graph, group_id: str,
                     scene_epochs: Sequence[str] = ()) -> Dict[str, Any]:
    """The epochs a container lies in → ``{ids, names, source}``.

    Its members' epochs; when they have none (or it has no member), its own —
    s3Dgraphy's ``container_own_epochs`` when the installed s3Dgraphy has it
    (``source: "own"``), else the same reading done here (``"own (local)"``);
    when the graph says nothing, the scene's «Epochs of this set»
    (``scene_epochs``, names: ``"scene"``). ``source`` is ``"members"`` when
    the members say them, ``"none"`` when nobody does."""
    ids: List[str] = []
    source = "none"
    if graph is not None and group_id and _node(graph, group_id) is not None:
        rule = _rule()
        ids = _epochs_reaching(graph, _members_deep(graph, group_id, rule), rule)
        if ids:
            source = "members"
        else:
            if has_container_rule():
                from s3dgraphy.resources.alternatives import container_own_epochs
                ids = list(container_own_epochs(graph, group_id))
                source = "own" if ids else "none"
            else:
                ids = own_epochs_local(graph, group_id, rule)
                source = "own (local)" if ids else "none"
    names = []
    for i in ids:
        n = _node(graph, i)
        nm = str(getattr(n, "name", "") or i)
        if nm not in names:
            names.append(nm)
    if not names and scene_epochs:
        names = [str(x) for x in scene_epochs if x]
        source = "scene" if names else "none"
    return {"ids": ids, "names": names, "source": source}


def effective_mode(mode: str, has_alternative: bool, member_count: int,
                   aset: Optional[Dict[str, Any]] = None) -> str:
    """What the scene shows of a container: ``MODELS`` or ``TILESET``.

    Models / Tileset are the person's choice. Automatic: Blender has no
    distance to switch on, so it is the models (no use declared: s3Dgraphy's
    ``choose_alternative`` with no use) — except a container with an
    alternative and NO member, which lights its alternative (s3Dgraphy
    1.6.40). ``aset`` is the container's set of ``alternative_sets``: when the
    installed s3Dgraphy has the rule, its ``choose_alternative`` decides; the
    count of members (the scene's and the graph's) decides otherwise."""
    if not has_alternative:
        return "MODELS"
    if mode in ("MODELS", "TILESET"):
        return mode
    if aset is not None and has_container_rule():
        try:
            from s3dgraphy.resources.alternatives import choose_alternative
            ch = choose_alternative(aset, [])
            if ch is not None:
                return "TILESET" if ch.get("level") == "container" else "MODELS"
        except Exception:  # noqa: BLE001 — the count below says the same
            pass
    return "TILESET" if member_count == 0 else "MODELS"


def box_visible(shown: bool, sync_by_epoch: bool, active_epoch: str,
                epoch_names: Sequence[str]) -> bool:
    """The alternative's box in the viewport: its eye, and — when the RM
    visibility follows the active epoch — the container's epochs."""
    if not shown:
        return False
    if not sync_by_epoch or not active_epoch:
        return True
    return active_epoch in set(epoch_names or ())


# ── the frame ────────────────────────────────────────────────────────────────

def _num(v: Any) -> Optional[float]:
    try:
        f = float(str(v).strip().replace(",", ".")) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def parse_number(text: Any) -> float:
    """A shift as typed: «291407», «291407,5», « 4640813.0 » → float;
    empty → 0. Raises ValueError for anything else."""
    if text is None or str(text).strip() == "":
        return 0.0
    v = _num(text)
    if v is None:
        raise ValueError(f"{text!r} is not a number")
    return v


def normalise_crs(crs: Any) -> Optional[str]:
    try:
        from s3dgraphy.geometry.frame import normalise_crs as _n
        return _n(crs)
    except ImportError:
        pass
    if crs is None or crs == "":
        return None
    if isinstance(crs, (int, float)) and not isinstance(crs, bool):
        return f"EPSG:{int(crs)}"
    s = str(crs).strip()
    if s.isdigit():
        return f"EPSG:{int(s)}"
    if ":" in s:
        auth, code = s.split(":", 1)
        return f"{auth.strip().upper()}:{code.strip().lstrip(':')}"
    return s


def make_frame(crs: Any, shift: Sequence[Any], note: str = "",
               source: str = "") -> Dict[str, Any]:
    """A frame as s3Dgraphy writes it (``geometry.frame.make_frame``)."""
    try:
        from s3dgraphy.geometry.frame import make_frame as _m
        return _m(crs, shift, note, source)
    except ImportError:
        pass
    sh = [(_num(v) or 0.0) for v in list(shift or [])[:3]]
    sh += [0.0] * (3 - len(sh))
    out: Dict[str, Any] = {"crs": normalise_crs(crs), "shift": sh}
    if note:
        out["note"] = str(note)
    if source:
        if source not in SOURCES:
            raise ValueError(f"frame.source is one of {SOURCES}, not {source!r}")
        out["source"] = source
    return out


def read_frame(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """``data.frame`` normalised, or None (s3Dgraphy's ``read_frame``)."""
    try:
        from s3dgraphy.geometry.frame import read_frame as _r
        return _r(data)
    except ImportError:
        pass
    f = (data or {}).get(FRAME_KEY)
    if not isinstance(f, dict):
        return None
    sh = f.get("shift")
    if isinstance(sh, dict):
        sh = [sh.get("x"), sh.get("y"), sh.get("z")]
    elif not isinstance(sh, (list, tuple)):
        sh = [f.get("shift_x"), f.get("shift_y"), f.get("shift_z")]
    nums = [(_num(v) or 0.0) for v in list(sh)[:3]]
    nums += [0.0] * (3 - len(nums))
    crs = normalise_crs(f.get("crs") or f.get("epsg"))
    if crs is None and not any(nums):
        return None
    out: Dict[str, Any] = {"crs": crs, "shift": nums}
    for k in ("note", "source"):
        if f.get(k):
            out[k] = str(f[k])
    return out


def frame_node(graph, node_id: str) -> Optional[str]:
    """Where a tileset's frame is written: its resource's ASSET (a version
    inherits it). For an RM (a Cesium tileset added to an epoch) its linked
    3D asset when it has one, else the RM itself (the datamodel accepts
    ``data.frame`` on both)."""
    if graph is None or not node_id or _node(graph, node_id) is None:
        return None
    node = _node(graph, node_id)
    if _type(node) == "resource":
        try:
            from s3dgraphy.resources.versions import asset_of
            return asset_of(graph, node_id) or node_id
        except Exception:  # noqa: BLE001
            return node_id
    for e in graph.edges:
        if e.edge_type == "has_linked_resource" and e.edge_source == node_id \
                and _type(_node(graph, e.edge_target)) == "resource":
            return frame_node(graph, e.edge_target)
    return node_id


def frame_for(graph, node_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """``(frame, where)`` for a tileset's node: s3Dgraphy's ``frame_of``
    (the node, its asset, its hats) when it has it, else the node and the
    node :func:`frame_node` names."""
    if graph is None or not node_id or _node(graph, node_id) is None:
        return None, None
    try:
        from s3dgraphy.geometry.frame import frame_of
        return frame_of(graph, node_id)
    except ImportError:
        pass
    for i in dict.fromkeys([node_id, frame_node(graph, node_id)]):
        n = _node(graph, i) if i else None
        f = read_frame(getattr(n, "data", None)) if n is not None else None
        if f:
            return f, i
    return None, None


def write_frame(graph, node_id: str, frame: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Write (None: remove) ``data.frame`` on ``node_id``; the old frame back.
    s3Dgraphy's ``set_frame``, or the same write on an older s3Dgraphy."""
    try:
        from s3dgraphy.geometry.frame import set_frame
        return set_frame(graph, node_id, frame)
    except ImportError:
        pass
    node = _node(graph, node_id)
    if node is None:
        raise KeyError(node_id)
    data = getattr(node, "data", None)
    if data is None:
        node.data = data = {}
    old = read_frame(data)
    f = read_frame({FRAME_KEY: frame}) if frame is not None else None
    if f is None:
        data.pop(FRAME_KEY, None)
    else:
        data[FRAME_KEY] = f
    return old


def dumps(frame: Optional[Dict[str, Any]]) -> str:
    """The panel's copy of a frame (a JSON string; empty for none)."""
    return json.dumps(frame, sort_keys=True) if frame else ""


def loads(text: str) -> Optional[Dict[str, Any]]:
    try:
        f = json.loads(text) if text else None
    except ValueError:
        return None
    return read_frame({FRAME_KEY: f}) if isinstance(f, dict) else None


def _fmt(v: float) -> str:
    return (f"{v:.3f}".rstrip("0").rstrip(".")) if v else "0"


def frame_line(frame: Optional[Dict[str, Any]]) -> str:
    """«EPSG:6708 − (291407, 4640813, 0)» — or «no frame: the coordinates are
    taken as written»."""
    if not frame:
        return "No frame: the coordinates are taken as written"
    sh = frame.get("shift") or [0, 0, 0]
    return f"{frame.get('crs') or 'no CRS'} − ({', '.join(_fmt(float(x)) for x in sh)})"


# ── the study's frame and where the box lands ───────────────────────────────

def study_frame(values: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The georeferencing of a graph's ``geo_position`` (or of the scene),
    as EM Tools' georef manager reads it (``{epsg, shift_x, shift_y,
    shift_z}``) → ``{"crs", "shift"}``, or None when it says nothing (no EPSG
    and the shift at 0: «not georeferenced»)."""
    if not values:
        return None
    crs = normalise_crs(values.get("epsg"))
    if crs and crs.upper() == "NOTSET":
        crs = None
    shift = [float(values.get(k) or 0.0) for k in ("shift_x", "shift_y", "shift_z")]
    if not crs and not any(abs(x) > 1e-3 for x in shift):
        return None
    return {"crs": crs, "shift": shift}


def frame_from_study(study: Optional[Dict[str, Any]], note: str = "",
                     source: str = "graph") -> Optional[Dict[str, Any]]:
    """«Use the graph's shift»: the study's CRS and shift as the file's frame."""
    if not study:
        return None
    return make_frame(study.get("crs"), study.get("shift") or [0, 0, 0], note, source)


def placement_target(frame: Optional[Dict[str, Any]], *studies: Optional[Dict[str, Any]]
                     ) -> Tuple[Optional[Dict[str, Any]], str]:
    """Where a tileset with ``frame`` lands in the Blender scene →
    ``(target, said)``. The first study that says something (the graph's
    ``geo_position``, then the scene's georeferencing): its CRS (the frame's
    when it says none) minus its shift — the frame the models of the EM are
    in. No study: the frame's own CRS minus its own shift, i.e. the file's
    shifted grid coordinates, which is the scene's frame when the scene was
    built on the same shift. ``(None, "")`` without a frame."""
    if not frame or not frame.get("crs"):
        return None, ""
    for s in studies:
        if s:
            crs = s.get("crs") or frame["crs"]
            return ({"crs": crs, "shift": list(s.get("shift") or [0, 0, 0])},
                    f"the study's frame ({crs} − ({', '.join(_fmt(float(x)) for x in s.get('shift') or [0, 0, 0])}))")
    return ({"crs": frame["crs"], "shift": list(frame.get("shift") or [0, 0, 0])},
            "the file's shifted grid (no shift in the graph)")


def placement_line(relocation: Optional[Dict[str, Any]], said: str = "") -> str:
    """One line for the panel: where the box went and the fit's residual."""
    if not relocation:
        return ""
    if not relocation.get("ok"):
        return f"Not relocated: {relocation.get('error') or 'unknown reason'}"
    rms = float(relocation.get("residual_rms_m") or 0.0)
    mx = float(relocation.get("residual_max_m") or 0.0)
    unit = (lambda m: f"{m * 1000:.1f} mm") if mx < 0.1 else (lambda m: f"{m:.3f} m")
    where = f" in {said}" if said else ""
    return f"Relocated by the frame{where}: residual {unit(rms)} rms, {unit(mx)} max"
