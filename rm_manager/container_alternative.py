"""The container's alternative, chosen without a path written by hand.

MICRO EM Tools «l'alternativa del contenitore» (E.D., 17 Oct 2026). In the RM
Containers panel a container says «Alternative: —» and offers «Choose…»: a
tileset of the graph, a file or a folder from the disk, or a file dropped on
the panel. Before the declaration a coverage check says what the tileset holds
against what the container holds — an aid, never a lock: the declaration is the
person's (decision of 17 Oct 2026).

What is here, without ``bpy`` (measured by pytest):

* :func:`tileset_assets` — the tilesets of the graph, recognised the way
  s3Dgraphy recognises one (``resources.alternatives.is_tileset``: a 3tz media
  type, ``packaging: directory``, a locator ending in ``.3tz`` or
  ``tileset.json``; an archive is one when a version of its asset is);
* :func:`inspect_tileset` — a folder, a ``.3tz`` or a ``.zip`` read WITHOUT
  loading a tile: the ``tileset.json`` (and the external ones it calls), the
  proposed name, the boxes of the leaf tiles;
* :func:`coverage` — those boxes against the boxes of the container's models
  and of the models no container holds;
* :func:`storage_plan` / :func:`measure` — where the bytes go in the project's
  standard tree and the fingerprint they carry;
* :func:`write_alternative` / :func:`remove_alternative` /
  :func:`alternative_of` — the graph, through s3Dgraphy (``declare_alternative``,
  ``add_resource``, ``add_version``): the container is the hat;
* :func:`propose_document` — the document the container's models say.

WHY THE LEAF TILES, AND NOT THE ROOT
------------------------------------
Measured on Templu Mare (``RB/cesium/TempluMare``, 17 Oct 2026): the root of
``tileset.json`` declares a cube of 98 m, and against it the 4 EST models gave
an overlap of 0.01 this morning. The tiles carry a ``content.boundingVolume``
tight around what they hold: the 5,476 leaves (through the six external
``Data/cNN/tileset.json``) lie on the survey meshes, their union
[-38.1, -47.2, 490.1]–[12.5, 16.9, 498.3] against the 11 RB meshes'
[-37.8, -47.1, 490.1]–[11.9, 16.4, 498.3]. The b3dm of Metashape carry no node
names (``BATCH_LENGTH 0``, glTF nodes without a name): models cannot be
recognised by name, only by place. When an external ``tileset.json`` cannot be
read, the tile that calls it stands with its own box (the coarser level), and
the answer says so.

HOW A MODEL IS «IN» THE TILESET
-------------------------------
By its FOOTPRINT: the model's box is sampled on a 10×10 grid in plan; a sample
is covered when a leaf tile's box holds it in plan and meets the model's height.
The share of covered samples ≥ :data:`COVERED_SHARE` → the tileset holds the
model. Not the share of the box's VOLUME: a survey is a skin, its box mostly
air, and the volume share gave 0.20 to the meadow (PRATO) that the tileset
certainly holds. On Templu Mare the 10 survey meshes have 0.75–1.00, TEMPLUM
1.00, a reconstruction column standing on the podium 1.00 too: the place cannot
tell a survey from a reconstruction standing on it. That is why the models of
ANOTHER container are not listed as «more»: they are counted apart.
"""

from __future__ import annotations

import json
import math
import os
import posixpath
import shutil
import struct
import zipfile
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

#: the share of a model's footprint the leaf tiles must cover for the tileset
#: to hold it (Templu Mare: the survey meshes 0.75–1.00, models elsewhere 0)
COVERED_SHARE = 0.5

#: metres: a leaf tile's box grown by this much in plan and in height
TOLERANCE_M = 0.25

#: the uses a new alternative declares unless the person changes them
DEFAULT_USES = ("web", "realtime")

#: what the file browser and the drop accept
TILESET_EXTENSIONS = (".3tz", ".zip")
MEDIA_3TZ = "application/vnd.maxar.archive.3tz+zip"

#: where a tileset from outside the project lands in the standard tree (C1:
#: «RM — representation models (and their tiles, .3tz)»)
STORAGE_DIR = ("RM", "tilesets")

Box = Tuple[List[float], List[float]]


# ── the tilesets of the graph ────────────────────────────────────────────────

def _data(node) -> Dict[str, Any]:
    return getattr(node, "data", None) or {}


def _size(node) -> int:
    d = _data(node)
    v = d.get("size_bytes")
    if v is None:
        v = (d.get("measures") or {}).get("size_bytes")
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def tileset_assets(graph) -> List[Dict[str, Any]]:
    """The tileset assets of ``graph``: ``[{asset_id, name, uses, size_bytes,
    url, hats, hat_names, versions}]`` sorted by name.

    An asset is a tileset when one of its resources declares it (s3Dgraphy's
    ``is_tileset``): the zip received for Templu Mare is not one by itself, its
    asset is, through the ``tileset.json`` folder that is its lod0. ``uses`` are
    the uses its versions declare; ``size_bytes`` the heaviest tileset form;
    ``hats`` who holds it today (an RM or a container)."""
    if graph is None:
        return []
    from s3dgraphy.resources.alternatives import hats_of, is_tileset
    from s3dgraphy.resources.versions import asset_of, versions_of
    by_id = {n.node_id: n for n in graph.nodes}
    seen, out = set(), []
    for node in list(graph.nodes):
        if getattr(node, "node_type", "") != "resource" or not is_tileset(_data(node)):
            continue
        try:
            asset = asset_of(graph, node.node_id)
        except ValueError:
            continue
        if asset in seen:
            continue
        seen.add(asset)
        try:
            entries = versions_of(graph, asset)
        except ValueError:
            entries = [{"id": asset, "master": True, "use": []}]
        uses: List[str] = []
        size, url = 0, ""
        for e in entries:
            for u in e.get("use") or []:
                if u not in uses:
                    uses.append(u)
            n = by_id.get(e["id"])
            if n is not None and is_tileset(_data(n)) and _size(n) >= size:
                size, url = _size(n), str(_data(n).get("url") or "")
        hats = hats_of(graph, asset)
        master = by_id.get(asset)
        out.append({"asset_id": asset, "name": getattr(master, "name", "") or asset,
                    "uses": uses, "size_bytes": size, "url": url, "hats": hats,
                    "hat_names": [getattr(by_id.get(h), "name", "") or h for h in hats],
                    "versions": [e["id"] for e in entries]})
    return sorted(out, key=lambda a: (str(a["name"]).lower(), a["asset_id"]))


def human_size(n: int) -> str:
    if not n:
        return "size unknown"
    for unit, k in (("GB", 1e9), ("MB", 1e6), ("kB", 1e3)):
        if n >= k:
            return f"{n / k:.1f} {unit}"
    return f"{n} B"


# ── reading a tileset without loading a tile ────────────────────────────────

_I = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]


def _mul(a: Sequence[float], b: Sequence[float]) -> List[float]:
    """4×4 column-major, as 3D Tiles writes ``transform``."""
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4))
            for c in range(4) for r in range(4)]


def _obb_aabb(m: Sequence[float], box: Sequence[float]) -> Box:
    """The axis-aligned box of a 3D Tiles ``box`` (centre + three half axes)
    placed by ``m``."""
    c = [m[0] * box[0] + m[4] * box[1] + m[8] * box[2] + m[12],
         m[1] * box[0] + m[5] * box[1] + m[9] * box[2] + m[13],
         m[2] * box[0] + m[6] * box[1] + m[10] * box[2] + m[14]]
    half = [0.0, 0.0, 0.0]
    for a in (box[3:6], box[6:9], box[9:12]):
        v = [m[0] * a[0] + m[4] * a[1] + m[8] * a[2],
             m[1] * a[0] + m[5] * a[1] + m[9] * a[2],
             m[2] * a[0] + m[6] * a[1] + m[10] * a[2]]
        for i in range(3):
            half[i] += abs(v[i])
    return ([c[i] - half[i] for i in range(3)], [c[i] + half[i] for i in range(3)])


def _volume_aabb(m: Sequence[float], bv: Dict[str, Any]) -> Optional[Box]:
    if not isinstance(bv, dict):
        return None
    if isinstance(bv.get("box"), list) and len(bv["box"]) == 12:
        return _obb_aabb(m, bv["box"])
    if isinstance(bv.get("sphere"), list) and len(bv["sphere"]) == 4:
        x, y, z, r = bv["sphere"]
        return _obb_aabb(m, [x, y, z, r, 0, 0, 0, r, 0, 0, 0, r])
    return None        # a `region` is geographic: not in the model's frame


class _Source:
    """A tileset to read: a folder, a .3tz or a .zip. ``read(rel)`` gives the
    bytes of a member by its path inside the tileset (``/`` separated)."""

    def __init__(self, path: str):
        self.path = os.path.abspath(os.path.expanduser(path))
        self.zip: Optional[zipfile.ZipFile] = None
        self.prefix = ""
        if os.path.isdir(self.path):
            self.kind = "directory"
            if not os.path.isfile(os.path.join(self.path, "tileset.json")):
                raise ValueError(f"no tileset.json in the folder {self.path}")
        elif os.path.isfile(self.path) and os.path.basename(self.path).lower() == "tileset.json":
            self.kind = "directory"
            self.path = os.path.dirname(self.path)
        elif os.path.isfile(self.path) and self.path.lower().endswith(TILESET_EXTENSIONS):
            self.kind = "3tz" if self.path.lower().endswith(".3tz") else "zip"
            try:
                self.zip = zipfile.ZipFile(self.path)
            except zipfile.BadZipFile as exc:
                raise ValueError(f"{os.path.basename(self.path)} is not a readable archive: {exc}")
            names = [n for n in self.zip.namelist() if n.endswith("tileset.json")]
            if not names:
                raise ValueError(f"no tileset.json in {os.path.basename(self.path)}")
            entry = min(names, key=lambda n: (n.count("/"), len(n)))
            self.prefix = entry[: -len("tileset.json")]
        else:
            raise ValueError(f"{path!r} is neither a folder with tileset.json, nor a .3tz or .zip")

    def read(self, rel: str) -> bytes:
        rel = posixpath.normpath(rel).lstrip("/")
        if self.zip is not None:
            return self.zip.read(self.prefix + rel)
        with open(os.path.join(self.path, *rel.split("/")), "rb") as fh:
            return fh.read()

    def close(self):
        if self.zip is not None:
            self.zip.close()


def proposed_name(path: str, asset: Optional[Dict[str, Any]] = None) -> str:
    """The name the dialog proposes: the ``asset`` of ``tileset.json`` when it
    names the tileset (``extras.name`` / ``extras.title``, or a ``name`` /
    ``title`` some writers put beside ``version``), else the file or folder's
    name without its extension. 3D Tiles' ``asset`` has no name field of its
    own: Templu Mare's says ``{"version": "1.0"}`` and its name is the file's."""
    a = asset or {}
    for holder in (a.get("extras") or {}, a):
        for key in ("name", "title"):
            v = holder.get(key) if isinstance(holder, dict) else None
            if isinstance(v, str) and v.strip():
                return v.strip()
    p = os.path.abspath(os.path.expanduser(path)).rstrip(os.sep)
    if os.path.basename(p).lower() == "tileset.json":
        p = os.path.dirname(p)
    base = os.path.basename(p)
    stem, ext = os.path.splitext(base)
    return stem if ext.lower() in TILESET_EXTENSIONS else base


def inspect_tileset(path: str) -> Dict[str, Any]:
    """What a tileset holds, read from its ``tileset.json`` and the external
    ones it calls — never a tile. → ``{kind, path, name, asset, leaves,
    tiles, external, unread, level, envelope}``: ``leaves`` the axis-aligned
    boxes (in the tileset's frame, ``transform`` applied) of the tiles with
    content and no children; ``unread`` the external tilesets that could not
    be read (their calling tile stands with its own box, ``level`` then says
    ``coarse``). Raises ValueError for something that is not a tileset."""
    src = _Source(path)
    try:
        root_doc = json.loads(src.read("tileset.json"))
        leaves: List[Box] = []
        unread: List[str] = []
        external = [0]
        counted = [0]

        def walk_doc(doc: Dict[str, Any], base: str, m: Sequence[float], depth: int):
            walk(doc.get("root") or {}, base, m, depth)

        def walk(tile: Dict[str, Any], base: str, m: Sequence[float], depth: int):
            counted[0] += 1
            t = _mul(m, tile["transform"]) if isinstance(tile.get("transform"), list) \
                and len(tile["transform"]) == 16 else list(m)
            content = tile.get("content") or {}
            uri = content.get("uri") or content.get("url") or ""
            kids = tile.get("children") or []
            if uri.lower().split("?")[0].endswith(".json") and depth < 16:
                rel = posixpath.normpath(posixpath.join(base, uri))
                try:
                    sub = json.loads(src.read(rel))
                except (KeyError, OSError, ValueError):
                    unread.append(rel)
                    b = _volume_aabb(t, content.get("boundingVolume") or tile.get("boundingVolume"))
                    if b:
                        leaves.append(b)
                    return
                external[0] += 1
                walk_doc(sub, posixpath.dirname(rel), t, depth + 1)
                return
            if kids:
                for k in kids:
                    walk(k, base, t, depth + 1)
                return
            if uri:
                b = _volume_aabb(t, content.get("boundingVolume") or tile.get("boundingVolume"))
                if b:
                    leaves.append(b)

        walk_doc(root_doc, "", _I, 0)
    finally:
        src.close()
    env = None
    if leaves:
        env = ([min(b[0][i] for b in leaves) for i in range(3)],
               [max(b[1][i] for b in leaves) for i in range(3)])
    asset = root_doc.get("asset") if isinstance(root_doc.get("asset"), dict) else {}
    return {"kind": src.kind, "path": src.path, "name": proposed_name(path, asset),
            "asset": asset, "leaves": leaves, "tiles": counted[0],
            "external": external[0], "unread": unread,
            "level": "coarse" if unread else "leaves", "envelope": env}


# ── coverage ─────────────────────────────────────────────────────────────────

class _Index:
    """The leaf boxes on a grid in plan, for the footprint test."""

    def __init__(self, leaves: Sequence[Box], tol: float = TOLERANCE_M):
        self.leaves = list(leaves)
        self.tol = tol
        sides = sorted(max(b[1][0] - b[0][0], b[1][1] - b[0][1]) for b in self.leaves) or [1.0]
        self.cell = min(50.0, max(0.25, sides[len(sides) // 2]))
        self.grid: Dict[Tuple[int, int], List[int]] = {}
        c = self.cell
        for k, (lo, hi) in enumerate(self.leaves):
            for x in range(math.floor((lo[0] - tol) / c), math.floor((hi[0] + tol) / c) + 1):
                for y in range(math.floor((lo[1] - tol) / c), math.floor((hi[1] + tol) / c) + 1):
                    self.grid.setdefault((x, y), []).append(k)

    def footprint(self, box: Box, n: int = 10) -> float:
        (x0, y0, z0), (x1, y1, z1) = box
        tol, c, hit = self.tol, self.cell, 0
        for i in range(n):
            x = x0 + (x1 - x0) * (i + 0.5) / n
            for j in range(n):
                y = y0 + (y1 - y0) * (j + 0.5) / n
                for k in self.grid.get((math.floor(x / c), math.floor(y / c)), ()):
                    lo, hi = self.leaves[k]
                    if lo[0] - tol <= x <= hi[0] + tol and lo[1] - tol <= y <= hi[1] + tol \
                            and lo[2] - tol <= z1 and hi[2] + tol >= z0:
                        hit += 1
                        break
        return hit / float(n * n)


#: two boxes are the same model seen twice when their IoU reaches this (a mesh
#: of the scene and an RM of the graph it never got linked to: Templu Mare,
#: ME_EST_L_LOD2 and SM_OB_EST_L_LOD1 have the same box to the millimetre)
SAME_PLACE_IOU = 0.9


def box_iou(a: Optional[Box], b: Optional[Box]) -> float:
    if not a or not b:
        return 0.0
    lo = [max(a[0][i], b[0][i]) for i in range(3)]
    hi = [min(a[1][i], b[1][i]) for i in range(3)]

    def vol(l, h):
        return max(0.0, h[0] - l[0]) * max(0.0, h[1] - l[1]) * max(0.0, h[2] - l[2])
    inter = vol(lo, hi)
    union = vol(*a) + vol(*b) - inter
    return inter / union if union > 0 else 0.0


def twins(members: Dict[str, Optional[Box]], others: Dict[str, Optional[Box]],
          threshold: float = SAME_PLACE_IOU) -> Dict[str, str]:
    """``{other: member}`` for the models of ``others`` whose box is a member's
    (IoU ≥ ``threshold``): the same model, not linked by id."""
    out = {}
    for o, ob in (others or {}).items():
        best, score = None, threshold
        for m, mb in (members or {}).items():
            v = box_iou(ob, mb)
            if v >= score:
                best, score = m, v
        if best is not None:
            out[o] = best
    return out


def coverage(inspection: Dict[str, Any], members: Dict[str, Optional[Box]],
             candidates: Optional[Dict[str, Optional[Box]]] = None,
             elsewhere: Optional[Dict[str, Optional[Box]]] = None,
             share: float = COVERED_SHARE) -> Dict[str, Any]:
    """The tileset against the container.

    ``members`` the container's models by name with their box (in the scene's
    frame; None when it cannot be measured); ``candidates`` the models no
    container holds; ``elsewhere`` the models of the OTHER containers (only
    counted). → ``{n_tileset, m_container, covered, missing, extra,
    unmeasured, elsewhere_inside, shares, level, tiles, leaves, unread,
    method, same}``: ``extra`` the candidates the tileset holds («more»),
    ``missing`` the members it does not, ``same`` True when neither."""
    idx = _Index(inspection.get("leaves") or [])
    shares: Dict[str, float] = {}

    def held(boxes: Dict[str, Optional[Box]]):
        yes, no, blind = [], [], []
        for name, box in sorted((boxes or {}).items()):
            if box is None:
                blind.append(name)
                continue
            s = idx.footprint(box) if idx.leaves else 0.0
            shares[name] = round(s, 2)
            (yes if s >= share else no).append(name)
        return yes, no, blind

    covered, missing, blind_m = held(members)
    # a model of the graph with a member's box IS that member, seen by place
    # (its mesh carries no id of it): not «more», and said
    same = twins(members, candidates or {})
    extra, _, blind_c = held({k: v for k, v in (candidates or {}).items() if k not in same})
    inside_elsewhere, _, _ = held(elsewhere or {})
    return {"n_tileset": len(covered) + len(extra), "m_container": len(members),
            "covered": covered, "missing": missing, "extra": extra, "twins": same,
            "unmeasured": blind_m + blind_c, "elsewhere_inside": inside_elsewhere,
            "shares": shares, "level": inspection.get("level"),
            "tiles": inspection.get("tiles"), "leaves": len(inspection.get("leaves") or []),
            "unread": list(inspection.get("unread") or []),
            "method": (f"footprint of each model's box on the {len(inspection.get('leaves') or [])} "
                       f"leaf tiles' boxes (share ≥ {share})"),
            "same": not missing and not extra}


def coverage_lines(cov: Dict[str, Any], limit: int = 8) -> List[str]:
    """The box of the dialog, line by line (English, as the panel)."""
    out = [f"The tileset holds {cov['n_tileset']} model(s), the container {cov['m_container']}"]

    def names(xs):
        return ", ".join(xs[:limit]) + (f", … (+{len(xs) - limit})" if len(xs) > limit else "")
    if cov["extra"]:
        out.append(f"More in the tileset ({len(cov['extra'])}): {names(cov['extra'])}")
    if cov["missing"]:
        out.append(f"Missing from the tileset ({len(cov['missing'])}): {names(cov['missing'])}")
    if cov.get("twins"):
        out.append(f"{len(cov['twins'])} model(s) of the graph have the box of a mesh of the "
                   f"container: the same, not counted twice")
    if cov["unmeasured"]:
        out.append(f"Not measured, no box ({len(cov['unmeasured'])}): {names(cov['unmeasured'])}")
    if cov["elsewhere_inside"]:
        out.append(f"{len(cov['elsewhere_inside'])} model(s) of other containers stand "
                   f"in the same place (not counted)")
    if cov.get("unread"):
        out.append(f"{len(cov['unread'])} external tileset(s) unreadable: their tiles "
                   f"measured with the coarser box")
    if cov["same"]:
        out.append("Same models: nothing more, nothing missing")
    return out


def note_of(cov: Dict[str, Any]) -> str:
    """The warning a «Confirm anyway» leaves on the row ('' when the same)."""
    parts = []
    if cov.get("extra"):
        parts.append(f"{len(cov['extra'])} more")
    if cov.get("missing"):
        parts.append(f"{len(cov['missing'])} missing")
    return ("confirmed with " + ", ".join(parts)) if parts else ""


# ── the boxes of models outside the scene ───────────────────────────────────

def glb_box(path: str) -> Optional[Box]:
    """The box of a .glb or .gltf in Blender's frame (Z up), from the POSITION
    accessors' min/max and the nodes' transforms — no vertex read. None when it
    cannot be read. Measured on Templu Mare: TEMPLUM's web glb gives the box of
    its OBJ to the centimetre."""
    try:
        if path.lower().endswith(".glb"):
            with open(path, "rb") as fh:
                head = fh.read(12)
                if head[:4] != b"glTF":
                    return None
                length, kind = struct.unpack("<II", fh.read(8))
                doc = json.loads(fh.read(length))
        else:
            with open(path, "rb") as fh:
                doc = json.loads(fh.read())
    except (OSError, ValueError, struct.error):
        return None
    nodes = doc.get("nodes") or []
    acc = doc.get("accessors") or []
    pts: List[List[float]] = []

    def local(n):
        if isinstance(n.get("matrix"), list):
            return n["matrix"]
        t = n.get("translation") or [0, 0, 0]
        x, y, z, w = n.get("rotation") or [0, 0, 0, 1]
        s = n.get("scale") or [1, 1, 1]
        r = [1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w), 0,
             2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w), 0,
             2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y), 0,
             t[0], t[1], t[2], 1]
        for c in range(3):
            for k in range(3):
                r[c * 4 + k] *= s[c]
        return r

    def walk(i, m, depth=0):
        if i >= len(nodes) or depth > 64:
            return
        n = nodes[i]
        mm = _mul(m, local(n))
        if "mesh" in n:
            for p in (doc.get("meshes") or [])[n["mesh"]].get("primitives") or []:
                a = acc[p.get("attributes", {}).get("POSITION", -1)] \
                    if p.get("attributes", {}).get("POSITION") is not None else None
                if not a or "min" not in a or "max" not in a:
                    continue
                lo, hi = a["min"], a["max"]
                for cx in (lo[0], hi[0]):
                    for cy in (lo[1], hi[1]):
                        for cz in (lo[2], hi[2]):
                            pts.append([mm[0] * cx + mm[4] * cy + mm[8] * cz + mm[12],
                                        mm[1] * cx + mm[5] * cy + mm[9] * cz + mm[13],
                                        mm[2] * cx + mm[6] * cy + mm[10] * cz + mm[14]])
        for c in n.get("children") or []:
            walk(c, mm, depth + 1)

    scenes = doc.get("scenes") or []
    roots = scenes[doc.get("scene", 0)].get("nodes", []) if scenes else range(len(nodes))
    for i in roots:
        walk(i, _I)
    if not pts:
        return None
    zup = [[p[0], -p[2], p[1]] for p in pts]          # glTF Y up → Blender Z up
    return ([min(p[k] for p in zup) for k in range(3)], [max(p[k] for p in zup) for k in range(3)])


def graph_model_boxes(graph, rm_ids: Iterable[str], resolve: Callable[[str], Optional[str]]
                      ) -> Dict[str, Tuple[str, Optional[Box]]]:
    """``{rm_id: (name, box)}`` for models that have no object in the scene:
    the box of the lightest .glb/.gltf among their versions (``resolve`` turns
    a locator into a path on this disk, or None). An OBJ is not read: its up
    axis is the exporter's choice, not the format's."""
    from s3dgraphy.resources.versions import asset_of, versions_of
    by_id = {n.node_id: n for n in graph.nodes}
    out: Dict[str, Tuple[str, Optional[Box]]] = {}
    for rm in rm_ids:
        node = by_id.get(rm)
        name = getattr(node, "name", "") or rm
        box = None
        targets = [e.edge_target for e in graph.edges
                   if e.edge_source == rm and e.edge_type == "has_linked_resource"]
        files = []
        for t in targets:
            try:
                for v in versions_of(graph, asset_of(graph, t)):
                    n = by_id.get(v["id"])
                    url = str(_data(n).get("url") or "")
                    if url.lower().endswith((".glb", ".gltf")):
                        files.append((_size(n) or 1 << 40, url))
            except ValueError:
                continue
        for _, url in sorted(files):
            path = resolve(url)
            if path and os.path.isfile(path):
                box = glb_box(path)
                if box:
                    break
        out[rm] = (name, box)
    return out


# ── the storage ──────────────────────────────────────────────────────────────

def _inside(path: str, folder: str) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(folder)]) \
            == os.path.abspath(folder)
    except ValueError:
        return False


def locator_for(path: str, emjson_dir: str) -> str:
    """The locator written in the graph: relative to the em.json's folder, ``/``
    separated (Templu Mare: ``../RB/cesium/TempluMare.zip``), so moving the
    project moves nothing. Absolute only when there is no em.json folder or no
    relative way (another drive)."""
    if not emjson_dir:
        return os.path.abspath(path)
    try:
        rel = os.path.relpath(os.path.abspath(path), os.path.abspath(emjson_dir))
    except ValueError:
        return os.path.abspath(path)
    return rel.replace(os.sep, "/")


def storage_plan(src: str, project_root: Optional[str], emjson_dir: str) -> Dict[str, Any]:
    """Where the tileset's bytes live once chosen. → ``{source, dest, copy,
    folder, unpack, locator, note}``.

    * already inside the project (the standard tree of C1, found from the
      em.json or the .blend) → it stays where it is;
    * from outside → copied into ``<project>/RM/tilesets/`` (the tree's place
      for «representation models and their tiles»); with no project tree,
      beside the em.json in ``tilesets/``;
    * a .zip is unpacked beside itself (``<name>/``): the folder with
      ``tileset.json`` is the version served, the zip the master as received —
      the shape of Templu Mare's tileset (``TempluMare.zip`` + ``TempluMare/``).
    """
    src = os.path.abspath(os.path.expanduser(src)).rstrip(os.sep)
    if os.path.basename(src).lower() == "tileset.json":
        src = os.path.dirname(src)
    note = ""
    if project_root and _inside(src, project_root):
        dest, copy = src, False
    elif project_root:
        dest, copy = os.path.join(project_root, *STORAGE_DIR, os.path.basename(src)), True
    elif emjson_dir:
        dest, copy = os.path.join(emjson_dir, "tilesets", os.path.basename(src)), True
        note = "no project tree (no EM/ folder): copied beside the em.json"
    else:
        dest, copy = src, False
        note = "no em.json saved yet: the locator stays absolute"
    unpack = ""
    if src.lower().endswith(".zip"):
        unpack = os.path.splitext(dest)[0]
    base = emjson_dir or os.path.dirname(dest)
    return {"source": src, "dest": dest, "copy": copy, "unpack": unpack, "base": base,
            "locator": locator_for(dest, base), "note": note,
            "unpack_locator": locator_for(os.path.join(unpack, "tileset.json"), base) if unpack else ""}


def apply_storage(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Copy (and unpack) as the plan says. A destination that exists with other
    bytes gets a ``-2``, ``-3``… suffix rather than being written over: a file
    of the project is never replaced in silence; the same bytes already there
    are not copied again. → the plan, with ``dest`` / ``locator`` updated and
    ``copied`` / ``unpacked``."""
    out = dict(plan)
    out["copied"] = out["unpacked"] = False
    src, dest = plan["source"], plan["dest"]
    if plan["copy"]:
        stem, ext = os.path.splitext(dest)
        k = 2
        while os.path.exists(dest) and not _quick_same(src, dest):
            dest = f"{stem}-{k}{ext}"
            k += 1
        if not os.path.exists(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if os.path.isdir(src):
                shutil.copytree(src, dest)
            else:
                shutil.copy2(src, dest)
            out["copied"] = True
        out["dest"] = dest
        out["locator"] = locator_for(dest, plan["base"])
        if plan["unpack"]:
            out["unpack"] = os.path.splitext(dest)[0]
            out["unpack_locator"] = locator_for(os.path.join(out["unpack"], "tileset.json"),
                                                plan["base"])
    if out["unpack"] and not os.path.isfile(os.path.join(out["unpack"], "tileset.json")):
        with zipfile.ZipFile(out["dest"]) as z:
            names = [n for n in z.namelist() if n.endswith("tileset.json")]
            prefix = min(names, key=lambda n: (n.count("/"), len(n)))[: -len("tileset.json")]
            for info in z.infolist():
                if info.is_dir() or not info.filename.startswith(prefix):
                    continue
                rel = info.filename[len(prefix):]
                target = os.path.normpath(os.path.join(out["unpack"], *rel.split("/")))
                if not _inside(target, out["unpack"]):
                    continue                       # a member that climbs out: refused
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with z.open(info) as r, open(target, "wb") as w:
                    shutil.copyfileobj(r, w)
        out["unpacked"] = True
    return out


def _quick_same(a: str, b: str) -> bool:
    """The same bytes already at the destination (the size for a file, the
    list of files and sizes for a folder)."""
    if os.path.isfile(a) and os.path.isfile(b):
        return os.path.getsize(a) == os.path.getsize(b)
    if os.path.isdir(a) and os.path.isdir(b):
        def listing(root):
            return sorted((os.path.relpath(os.path.join(d, f), root), os.path.getsize(os.path.join(d, f)))
                          for d, _, fs in os.walk(root) for f in fs)
        return listing(a) == listing(b)
    return False


def measure(path: str, locator: str) -> Dict[str, Any]:
    """The fingerprint and the size of the bytes at ``path`` as the resource
    carries them, measured with dtcstamp like every other file of the project:

    * a folder → ``url`` its ``tileset.json``, ``checksum`` of that file
      (``checksum_of: entry-point``), the tree's ``content_digest`` (the same
      for the folder and its .3tz), ``packaging: directory``, the size of the
      content — the form of Templu Mare's lod0;
    * a .3tz → the file's sha256, its ``content_digest``, ``archive``, 3tz type;
    * a .zip → the file's sha256, ``archive``, ``application/zip``.

    → ``{file: {url, checksum, size_bytes, media_type}, packaging, data}``."""
    try:
        from .. import resource_digest as rd  # inside the add-on
    except ImportError:                       # pytest: the repo root on the path
        import resource_digest as rd          # type: ignore
    dtc = rd.dtcstamp()
    if os.path.isdir(path):
        entry = os.path.join(path, "tileset.json")
        members = dtc.tree_members(path, entry_point="tileset.json")
        url = locator if locator.endswith("tileset.json") else posixpath.join(locator, "tileset.json")
        return {"file": {"url": url, "checksum": dtc.file_digest(entry),
                         "size_bytes": sum(int(m.get("size_bytes") or 0) for m in members),
                         "media_type": "application/json"},
                "packaging": "directory",
                "data": {"checksum_of": "entry-point",
                         "content_digest": {"digest": dtc.content_digest(path),
                                            "files": len(members)}}}
    if path.lower().endswith(".3tz"):
        return {"file": {"url": locator, "checksum": dtc.file_digest(path),
                         "size_bytes": os.path.getsize(path), "media_type": MEDIA_3TZ},
                "packaging": "archive",
                "data": {"content_digest": {"digest": dtc.content_digest(path)}}}
    return {"file": {"url": locator, "checksum": dtc.file_digest(path),
                     "size_bytes": os.path.getsize(path), "media_type": "application/zip"},
            "packaging": "archive", "data": {}}


# ── the graph: the container is the hat ─────────────────────────────────────

def _tileset_versions(graph, asset: str) -> List[str]:
    from s3dgraphy.resources.alternatives import is_tileset
    from s3dgraphy.resources.versions import versions_of
    out = []
    for e in versions_of(graph, asset):
        n = graph.find_node_by_id(e["id"])
        if not e.get("master") and n is not None and is_tileset(_data(n)):
            out.append(e["id"])
    return out


def set_uses(graph, asset: str, uses: Sequence[str]) -> List[str]:
    """``data.use`` of the asset's tileset versions (its served forms) becomes
    ``uses``; an asset whose only tileset form is the master gets a version
    with the master's bytes to carry them (s3Dgraphy reads the uses on the
    versions, never on the master). → the ids written."""
    from s3dgraphy.resources.versions import add_version, check_use
    clean = check_use(list(uses)) or []
    ids = _tileset_versions(graph, asset)
    if not ids:
        master = graph.find_node_by_id(asset)
        d = _data(master)
        spec = {k: d[k] for k in ("url", "checksum", "media_type") if d.get(k)}
        if _size(master):
            spec["size_bytes"] = _size(master)
        out = add_version(graph, asset, level="lod0", use=clean, files=[spec] if spec else (),
                          packaging=d.get("packaging"), tool="EM Tools · container alternative")
        node = graph.find_node_by_id(out["version_id"])
        for k in ("content_digest", "checksum_of"):
            if d.get(k):
                node.data[k] = d[k]
        ids = [out["version_id"]]
    for vid in ids:
        graph.find_node_by_id(vid).data["use"] = list(clean)
    return ids


def new_tileset_asset(graph, name: str, master: Dict[str, Any],
                      served: Optional[Dict[str, Any]], uses: Sequence[str]) -> Dict[str, Any]:
    """A tileset that comes from the disk enters the graph as an asset: the
    MASTER (the bytes as received: the .3tz, the .zip or the folder) and its
    ``lod0`` (the bytes served: the folder unpacked from a zip, else the same
    bytes), with the uses on the lod0. ``master`` / ``served`` as :func:`measure`
    gives them. → ``{asset_id, version_id}``."""
    from s3dgraphy.resources.files import add_resource
    from s3dgraphy.resources.versions import add_version
    node = add_resource(graph, name=name, kind="3d_model", files=[master["file"]],
                        packaging=master["packaging"], tier="master", residency="resident",
                        data=dict(master.get("data") or {}))
    srv = served or master
    out = add_version(graph, node.node_id, level="lod0", use=list(uses),
                      files=[srv["file"]], packaging=srv["packaging"], residency="resident",
                      tool="EM Tools · container alternative")
    vnode = graph.find_node_by_id(out["version_id"])
    for k, v in (srv.get("data") or {}).items():
        vnode.data[k] = v
    return {"asset_id": node.node_id, "version_id": out["version_id"]}


def find_by_checksum(graph, checksum: str) -> Optional[str]:
    """The asset of a resource with these bytes, when the graph has it already
    (the same tileset chosen twice is one resource, not two)."""
    if not checksum:
        return None
    from s3dgraphy.resources.versions import asset_of
    for n in graph.nodes:
        if getattr(n, "node_type", "") == "resource" and _data(n).get("checksum") == checksum:
            try:
                return asset_of(graph, n.node_id)
            except ValueError:
                return n.node_id
    return None


def write_alternative(graph, group_id: str, asset_id: str, *, uses: Sequence[str] = DEFAULT_USES,
                      name: str = "", scene_rm_ids: Iterable[str] = ()) -> Dict[str, Any]:
    """The container ``group_id`` becomes the hat of the tileset ``asset_id``
    (s3Dgraphy's ``declare_alternative``: the hats it had lose it, never two).
    The RM that held it goes with its edges only when no object of the scene
    stands for it (``scene_rm_ids``). The uses are written on its versions;
    ``name`` renames the master when given. → s3Dgraphy's answer plus
    ``uses_on``."""
    from s3dgraphy.resources.alternatives import declare_alternative, hats_of
    if graph is None or graph.find_node_by_id(group_id) is None:
        raise ValueError(f"{group_id!r} is not in the graph: project the container first")
    if graph.find_node_by_id(asset_id) is None:
        raise ValueError(f"{asset_id!r} is not in the graph")
    keep = set(scene_rm_ids or ())
    drop = not any(h in keep for h in hats_of(graph, asset_id))
    res = declare_alternative(graph, asset_id, group_id, drop_rm=drop)
    res["uses_on"] = set_uses(graph, res["assets"][0], uses)
    if name:
        master = graph.find_node_by_id(res["assets"][0])
        if master is not None and name != master.name:
            master.name = name
    return res


def alternative_of(graph, group_id: str) -> Optional[Dict[str, Any]]:
    """The container's alternative: ``{asset_id, name, uses, size_bytes, url}``
    of the 3D asset it hats, or None."""
    if graph is None or not group_id:
        return None
    from s3dgraphy.resources.versions import asset_of
    for e in graph.edges:
        if e.edge_type == "has_linked_resource" and e.edge_source == group_id:
            try:
                asset = asset_of(graph, e.edge_target)
            except ValueError:
                asset = e.edge_target
            for a in tileset_assets(graph):
                if a["asset_id"] == asset:
                    return a
            n = graph.find_node_by_id(asset)
            return {"asset_id": asset, "name": getattr(n, "name", "") or asset,
                    "uses": [], "size_bytes": _size(n), "url": str(_data(n).get("url") or ""),
                    "hats": [group_id], "hat_names": [], "versions": [asset]}
    return None


def remove_alternative(graph, group_id: str) -> List[str]:
    """«Remove the alternative»: the container's hat edges go; the resource,
    its versions and its file stay. → the assets it held."""
    out = []
    for e in list(graph.edges):
        if e.edge_type == "has_linked_resource" and e.edge_source == group_id:
            graph.remove_edge(e.edge_id)
            out.append(e.edge_target)
    return out


# ── the container's document ────────────────────────────────────────────────

def propose_document(graph, rm_ids: Sequence[str]) -> Dict[str, Any]:
    """Which document the container's models say: the documents reaching them
    with ``has_representation_model``, by how many. → ``{proposal, name,
    count, of, ranking}``: ``proposal`` is a document only when it reaches
    EVERY model that a document reaches and it is the only one that does
    (Templu Mare: D.01 → the 12 RMs of XX sec, D.09 → the 87 of II A.D.);
    otherwise None and the ranking says why."""
    ids = [r for r in rm_ids if r]
    if graph is None or not ids:
        return {"proposal": None, "name": "", "count": 0, "of": 0, "ranking": []}
    want = set(ids)
    by_doc: Dict[str, set] = {}
    for e in graph.edges:
        if e.edge_type == "has_representation_model" and e.edge_target in want:
            src = graph.find_node_by_id(e.edge_source)
            if src is not None and getattr(src, "node_type", "") == "document":
                by_doc.setdefault(e.edge_source, set()).add(e.edge_target)
    reached = set().union(*by_doc.values()) if by_doc else set()
    ranking = sorted(((d, getattr(graph.find_node_by_id(d), "name", "") or d, len(s))
                      for d, s in by_doc.items()), key=lambda t: (-t[2], t[1]))
    proposal = None
    if ranking and ranking[0][2] == len(reached) and (len(ranking) == 1 or ranking[1][2] < ranking[0][2]):
        proposal = ranking[0][0]
    return {"proposal": proposal, "name": ranking[0][1] if proposal else "",
            "count": ranking[0][2] if ranking else 0, "of": len(ids), "ranking": ranking}
