"""NIGHT-TAGLI-E-NEUTRE (em_visual_rules 1.6.44) · the proxies drawn as their
TYPE asks, read from s3Dgraphy (`node_styles.<type>.style.threed`, rule in
`threed_style._comment`; reader `s3dgraphy.utils.utils.get_threed_style`):

* FACES — the type's material keeps its colour; its alpha is
  ``faces.opacity × scene.em_tools.proxy_display_alpha`` (the slider
  MULTIPLIES the type's opacity, it does not replace it); ``faces.show`` false
  (USNt) = alpha 0: the mesh stays — selectable, exported, measured — and no
  pixel of it is drawn.
* EDGES — for a type whose ``edges.show`` is true (USN solid, USNt dashed): a
  CURVE object ``<proxy>.EM_edges`` with a round bevel, child of the proxy, in
  the collection ``EM_threed_edges``. Its segments are the proxy's FEATURE
  edges (two faces at more than ``feature_angle_deg``, plus boundary edges:
  not the diagonals of a triangulation) cut by the style exactly as EMStudio
  cuts them (``frontend/src/threed-edges.ts``): dashes as fractions of the
  bounding-box diagonal starting at each corner, corners as two ticks of
  ``tick_ratio`` × the shortest side.

Why a curve object and not the alternatives (measured choice, report
2026-11-13): ``show_wire`` draws every triangle edge in the theme colour, no
dash, viewport only; Freestyle draws only in a render; a Wireframe modifier
draws every edge, cannot dash, and — like a Geometry Nodes modifier — is
APPLIED by the glTF exports (``export_apply=True``, Heriverse), so a USNt
would leave as tubes. A separate curve is drawn in the viewport AND in a
render, coloured by its material, dashed by construction, and no export of
the proxy carries it. Its visibility follows the proxy (``sync_edges_visibility``,
a depsgraph handler).

The pure part (no bpy) is tested by ``tests/test_threed_style.py``.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

EDGES_COLLECTION = "EM_threed_edges"
EDGES_SUFFIX = ".EM_edges"
EDGE_MATERIAL_PREFIX = "EM_edges_"

#: what every client drew before 1.6.44: used when the bundled s3dgraphy is
#: older than the rule (no get_threed_style)
_FALLBACK = {"feature_angle_deg": 20.0, "dashed": {"dash_ratio": 0.04, "gap_ratio": 0.025},
             "corners": {"tick_ratio": 0.34}, "world_width_ratio": 0.0025}


# ── the rule ────────────────────────────────────────────────────────────────

def threed_style_of(node_type: str) -> Optional[dict]:
    """The complete 3D style of a type, from s3Dgraphy; with an s3dgraphy that
    predates the rule, the style that reproduces what was drawn until then
    (faces as the material, no edges). None = the type has no material."""
    try:
        from s3dgraphy.utils.utils import get_threed_style
    except ImportError:
        get_threed_style = None
    if get_threed_style is not None:
        return get_threed_style(node_type)
    try:
        from s3dgraphy.utils.utils import get_material_color
        rgba = get_material_color(node_type)
    except ImportError:
        rgba = None
    if rgba is None:
        return None
    return {"type": node_type,
            "faces": {"show": True, "opacity": 1.0, "rgba_color": tuple(rgba)},
            "edges": {"show": False, "width": 1.0, "style": "solid", "rgba_color": tuple(rgba)},
            "geometry": None, **_FALLBACK}


def faces_alpha(style: Optional[dict], slider: float) -> float:
    """The alpha a type's faces are drawn with: type opacity × the slider;
    0 when the type has no faces. No style (not an EM type) → the slider."""
    if not style:
        return float(slider)
    faces = style.get("faces") or {}
    if not faces.get("show", True):
        return 0.0
    return float(faces.get("opacity", 1.0)) * float(slider)


# ── the geometry of the edges (pure) ────────────────────────────────────────

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(v):
    n = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-15 else (0.0, 0.0, 0.0)


def _normal(verts, poly):
    """Newell's normal of a polygon (any number of vertices)."""
    nx = ny = nz = 0.0
    for i, a in enumerate(poly):
        p, q = verts[a], verts[poly[(i + 1) % len(poly)]]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    return _norm((nx, ny, nz))


def feature_edges(verts: Sequence[Sequence[float]], polys: Iterable[Sequence[int]],
                  angle_deg: float = 20.0) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
    """The edges between two faces at more than ``angle_deg``, and the edges of
    one face only (boundary) — three.js EdgesGeometry's rule. Vertices that
    share a position are one (a glb splits them by normal/uv)."""
    key = lambda p: (round(p[0], 6), round(p[1], 6), round(p[2], 6))  # noqa: E731
    pos = [key(v) for v in verts]
    faces_of: Dict[tuple, List[tuple]] = {}
    for poly in polys:
        poly = list(poly)
        if len(poly) < 3:
            continue
        n = _normal(verts, poly)
        if n == (0.0, 0.0, 0.0):
            continue
        for i, a in enumerate(poly):
            b = poly[(i + 1) % len(poly)]
            pa, pb = pos[a], pos[b]
            if pa == pb:
                continue
            faces_of.setdefault(tuple(sorted((pa, pb))), []).append(n)
    cos_t = math.cos(math.radians(angle_deg))
    out = []
    for (pa, pb), normals in sorted(faces_of.items()):
        if len(normals) == 1:
            out.append((pa, pb))
            continue
        n0 = normals[0]
        if any(n0[0] * n[0] + n0[1] * n[1] + n0[2] * n[2] <= cos_t for n in normals[1:]):
            out.append((pa, pb))
    return out


def cut_edges(edges, style: str, size: Sequence[float], dash_ratio: float = 0.04,
              gap_ratio: float = 0.025, tick_ratio: float = 0.34):
    """The twin of EMStudio's ``cutEdges``: solid whole; dashed from each
    corner, dash/gap × the box diagonal; corners two ticks of tick_ratio × the
    shortest side, never more than half the edge."""
    diag = math.sqrt(sum(s * s for s in size)) or 1.0
    sides = [s for s in size if s > 1e-9]
    shortest = min(sides) if sides else diag
    out = []
    for a, b in edges:
        d = _sub(b, a)
        length = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
        if length < 1e-12:
            continue
        at = lambda t: (a[0] + d[0] * t / length, a[1] + d[1] * t / length, a[2] + d[2] * t / length)  # noqa: E731
        if style == "solid":
            out.append((at(0.0), at(length)))
        elif style == "corners":
            tick = min(tick_ratio * shortest, length / 2)
            out.append((at(0.0), at(tick)))
            out.append((at(length - tick), at(length)))
        else:
            dash = max(dash_ratio * diag, 1e-9)
            gap = max(gap_ratio * diag, 0.0)
            t = 0.0
            while t < length:
                out.append((at(t), at(min(t + dash, length))))
                t += dash + gap
    return out


def bbox_size(verts) -> Tuple[float, float, float]:
    if not verts:
        return (0.0, 0.0, 0.0)
    return tuple(max(v[i] for v in verts) - min(v[i] for v in verts) for i in range(3))  # type: ignore[return-value]


def edge_segments(verts, polys, style: dict):
    """The segments a type's edges draw on a mesh (local coordinates)."""
    e = style["edges"]
    feats = feature_edges(verts, polys, style.get("feature_angle_deg", 20.0))
    d, c = style.get("dashed") or {}, style.get("corners") or {}
    return cut_edges(feats, e.get("style", "solid"), bbox_size(verts),
                     d.get("dash_ratio", 0.04), d.get("gap_ratio", 0.025), c.get("tick_ratio", 0.34))


# ── Blender ─────────────────────────────────────────────────────────────────

def _edges_collection(scene):
    import bpy  # type: ignore
    coll = bpy.data.collections.get(EDGES_COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(EDGES_COLLECTION)
    if coll.name not in scene.collection.children:
        scene.collection.children.link(coll)
    return coll


def _edge_material(node_type: str, rgba):
    import bpy  # type: ignore
    name = f"{EDGE_MATERIAL_PREFIX}{node_type}"
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (rgba[0], rgba[1], rgba[2], 1.0)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (rgba[0], rgba[1], rgba[2], 1.0)
    bsdf.inputs["Roughness"].default_value = 0.8
    mat.node_tree.links.new(bsdf.outputs[0], out.inputs[0])
    return mat


def edges_object_name(proxy_name: str) -> str:
    return f"{proxy_name}{EDGES_SUFFIX}"


def remove_edges(proxy) -> bool:
    import bpy  # type: ignore
    ob = bpy.data.objects.get(edges_object_name(proxy.name))
    if ob is None:
        return False
    data = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    if data is not None and data.users == 0:
        bpy.data.curves.remove(data)
    return True


def build_edges(scene, proxy, node_type: str, style: dict):
    """(Re)build the curve of a proxy's type edges; returns the object."""
    import bpy  # type: ignore
    mesh = proxy.data
    verts = [tuple(v.co) for v in mesh.vertices]
    polys = [tuple(p.vertices) for p in mesh.polygons]
    segs = edge_segments(verts, polys, style)
    remove_edges(proxy)
    cu = bpy.data.curves.new(edges_object_name(proxy.name), "CURVE")
    cu.dimensions = "3D"
    size = bbox_size(verts)
    diag = math.sqrt(sum(s * s for s in size)) or 1.0
    width = float(style["edges"].get("width", 1.0))
    cu.bevel_depth = style.get("world_width_ratio", 0.0025) * width * diag
    cu.bevel_resolution = 1
    for a, b in segs:
        sp = cu.splines.new("POLY")
        sp.points.add(1)
        sp.points[0].co = (*a, 1.0)
        sp.points[1].co = (*b, 1.0)
    ob = bpy.data.objects.new(edges_object_name(proxy.name), cu)
    ob.data.materials.append(_edge_material(node_type, style["edges"]["rgba_color"]))
    _edges_collection(scene).objects.link(ob)
    ob.parent = proxy
    ob.matrix_parent_inverse.identity()
    ob.hide_select = True
    ob["em_threed_edges"] = node_type
    ob["em_threed_style"] = style["edges"].get("style", "solid")
    _follow(ob, proxy)
    return ob


def _follow(edges_ob, proxy) -> bool:
    changed = False
    try:
        h = proxy.hide_get()
        if edges_ob.hide_get() != h:
            edges_ob.hide_set(h)
            changed = True
    except RuntimeError:  # not in this view layer
        pass
    for attr in ("hide_viewport", "hide_render"):
        v = getattr(proxy, attr)
        if getattr(edges_ob, attr) != v:
            setattr(edges_ob, attr, v)
            changed = True
    return changed


def sync_edges_visibility(scene=None, _depsgraph=None) -> int:
    """The edges follow their proxy (eye, monitor, camera): how many changed."""
    import bpy  # type: ignore
    coll = bpy.data.collections.get(EDGES_COLLECTION)
    if coll is None:
        return 0
    n = 0
    for ob in coll.objects:
        if ob.parent is not None and _follow(ob, ob.parent):
            n += 1
    return n


def apply_threed(context, proxies_with_types) -> dict:
    """The faces' alpha and the edges of every proxy, by its type.
    ``proxies_with_types``: [(object, node_type)]. → {"edges": n, "removed": n,
    "faceless": n}."""
    scene = context.scene
    slider = float(getattr(scene.em_tools, "proxy_display_alpha", 1.0))
    done = {"edges": 0, "removed": 0, "faceless": 0}
    for ob, node_type in proxies_with_types:
        style = threed_style_of(node_type)
        if style and style["edges"].get("show"):
            build_edges(scene, ob, node_type, style)
            done["edges"] += 1
        elif remove_edges(ob):
            done["removed"] += 1
        if style and not style["faces"].get("show", True):
            done["faceless"] += 1
    return done


def remove_all_edges() -> int:
    """Every type-edge curve away (a display mode other than EM)."""
    import bpy  # type: ignore
    coll = bpy.data.collections.get(EDGES_COLLECTION)
    if coll is None:
        return 0
    n = 0
    for ob in list(coll.objects):
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if data is not None and data.users == 0:
            bpy.data.curves.remove(data)
        n += 1
    return n
