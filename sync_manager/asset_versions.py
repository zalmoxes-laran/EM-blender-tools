"""A1–A3 · an asset and its versions in the scene: ONE object, the mesh changes.

MICRO-ASSET-VERSIONI, decided by E.D. on 3 October 2026:

* **the asset and its versions** live in the graph (s3dgraphy
  ``api.add_version`` / ``versions_of``): the master is the asset, each version
  (LOD1, LOD2…) a child resource made by a ``lod_generation`` step, with a
  level and a purpose. The RM, the epochs and the unit are on the asset; the
  versions inherit them. «Add version…» here writes exactly that — no layer to
  declare by hand;
* **one .blend library per asset**, holding the meshes of all its versions
  (``<cache>/<room>/<asset>.blend``, linked into the scene). The object in the
  scene stays ONE — its name, its graph bindings, its epochs — and changing
  LOD is changing the mesh datablock it uses («LOD ▸», per object or for the
  whole scene). Decorations and trials stay in the main file, «only here»;
* **the cache is checked mesh by mesh**: every mesh of a library carries the
  sha256 of the version it was made from (``em_asset_sha256``), so «Check the
  scene against the room» downloads only the versions whose mesh is missing or
  whose digest is not the one the graph cites now, and rebuilds that asset's
  library around them.

The decisions are pure (``plan_library``, ``step_level``, ``mesh_name``…),
measured by ``tests/test_asset_versions.py``; the Blender side (libraries,
import, the operators) sits below them.
"""

# NOT `from __future__ import annotations`: the operators are built inside a
# function with `bpy` imported lazily, and Blender evaluates their property
# annotations in this module's globals (the same note as scene_check).
import os
import re
from typing import Any, Callable, Dict, List, Optional

#: on the OBJECT: which asset it shows, and at which level now
PROP_ASSET = "em_asset_id"
PROP_LEVEL = "em_level"
#: on the MESH (and mirrored on the object for the level it shows): the digest
#: of the version's bytes, the version's resource, its level
PROP_DIGEST = "em_asset_sha256"
PROP_VERSION = "em_version_id"
#: where the cache lives, beside the .blend (relative, so a package travels)
CACHE_DIR = "em_cache"
#: the separator between the asset and the level in a library mesh's name
SEP = "@"

#: the last check of the libraries, for the panel (session state)
ULTIMO: Dict[str, Any] = {}
#: U1 · the last version «Prepare for a use…» made (session state)
PREPARED: Dict[str, Any] = {}


def _digest(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text and not text.startswith("sha256:"):
        text = "sha256:" + text
    return text


def safe(text: str) -> str:
    """A file-system-safe form of an id or a room name."""
    out = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text or "")).strip("._")
    return out or "asset"


def library_relpath(asset_id: str, room: Optional[str]) -> str:
    """`em_cache/<room>/<asset>.blend` — ONE library per asset, relative to the
    folder of the working .blend."""
    return "/".join((CACHE_DIR, safe(room or "local"), f"{safe(asset_id)}.blend"))


def mesh_name(base: str, level: str) -> str:
    """The name of a version's mesh inside its asset's library."""
    return f"{base}{SEP}{level}"


def level_of_mesh_name(name: str) -> Optional[str]:
    if SEP not in str(name or ""):
        return None
    return str(name).rsplit(SEP, 1)[1] or None


def level_key(level: Optional[str]):
    """Natural order of levels (LOD2 before LOD10; a level without a number
    after the numbered ones) — the same order s3dgraphy's versions_of uses."""
    text = str(level or "")
    if text == "master":
        # D1 · the master has no level and is the heaviest: it comes FIRST, as
        # in versions_of. Measured on Templu Mare: sorted after lod0, «LOD ▸»
        # on the master stayed put and «◂ LOD» went to the version
        return (-1, 0, text)
    m = re.search(r"(\d+)", text)
    return (0 if m else 1, int(m.group(1)) if m else 0, text)


def next_level(levels: List[str]) -> str:
    """The level «Add version…» proposes: one past the highest LODn."""
    numbers = [int(m.group(1)) for lv in levels or []
               for m in [re.match(r"^LOD(\d+)$", str(lv or ""))] if m]
    return f"LOD{(max(numbers) + 1) if numbers else 1}"


#: D1 · the uses a version can serve (s3dgraphy ``resources.versions.USES``),
#: with the words the dialog shows
USES = (("analysis", "Analysis", "Study and measure: autopsy of the units, sections, annotation"),
        ("realtime", "Real time", "An engine, desktop or HMD (Unreal, Unity, Godot, EMviq)"),
        ("web", "Web", "A browser (ATON, Heriverse, Voyager), streamed too"),
        ("mobile_ar", "Mobile / AR", "Augmented reality and mobile devices"),
        ("print", "Print", "3D printing, a physical replica"),
        ("render", "Render", "Plates, sections, reconstructive views, video"),
        ("preview", "Preview", "A light preview for catalogues and records"),
        # H4 (E.D., 5 Oct 2026) · a version made FOR a viewer: the package on
        # disk Heriverse or another ATON app opens (datamodel 1.6.26)
        ("heriverse", "Heriverse", "The package Heriverse opens, on disk or from "
                                   "the node: the model as it is"),
        ("aton", "ATON", "The same package, for another ATON app"))

#: H4 · the uses of a version made for a viewer: its glb is written by the glTF
#: writer of the old Heriverse exporter (`export_operators/heriverse/gltf.py`)
VIEWER_PACKAGE_USES = ("heriverse", "aton")


def version_measures(*, tris: int, area_m2: float, texture_count: int = 0,
                     texture_side_px: int = 0, uv_fraction: float = 0.0,
                     lod0_tris: Optional[int] = None) -> Dict[str, Any]:
    """D1 · the measures of a version, measured when it is born.

    * ``tris_per_m2`` — triangles per square metre (a measure, no target);
    * ``texel_density_dd`` — the texel SIDE in mm, in the form of the
      Demetrescu-D'Annibale formula: sqrt(area in mm² / (atlases × side² ×
      UV ratio)); reference 1.26 (Demetrescu et al. 2026, Eq. 1);
    * ``texture_count``, ``texture_side_px``, ``uv_ratio``;
    * ``reduction_from_lod0`` — triangles / triangles of LOD0, when LOD0 is known.

    A number that cannot be measured (no surface, no texture) is left out, not
    written as 0."""
    out: Dict[str, Any] = {}
    if area_m2 and area_m2 > 0 and tris:
        out["tris_per_m2"] = round(tris / area_m2, 3)
    if texture_count:
        out["texture_count"] = int(texture_count)
    if texture_side_px:
        out["texture_side_px"] = int(texture_side_px)
    if uv_fraction and uv_fraction > 0:
        # a UV layout that fills the atlas sums to 1 within float noise
        out["uv_ratio"] = round(min(float(uv_fraction), 1.0), 4)
    if area_m2 and area_m2 > 0 and texture_count and texture_side_px and out.get("uv_ratio"):
        useful = texture_count * texture_side_px ** 2 * out["uv_ratio"]
        out["texel_density_dd"] = round(((area_m2 * 1e6) / useful) ** 0.5, 3)
    if lod0_tris and tris:
        out["reduction_from_lod0"] = round(tris / lod0_tris, 4)
    return out


def resized_side(side: int, max_side: int) -> int:
    """U1 · the side a texture gets: `max_side` caps it, 0 keeps it."""
    side, max_side = int(side or 0), int(max_side or 0)
    return min(side, max_side) if max_side and side else side


def prepare_step(*, ratio: float, max_side: int, draco: bool,
                 resized: int, size_bytes: int) -> Dict[str, Any]:
    """U1 · the `lod_generation` step «Prepare for a use…» records in the DTC:
    its technique (what changed: the geometry, else the textures, else only
    the encoding) and its parameters, with the numbers measured."""
    if ratio < 1.0:
        technique = "decimation"
    elif resized:
        technique = "texture_reduction"
    else:
        technique = "compression"
    return {"technique": technique,
            "parameters": {"ratio": round(float(ratio), 4),
                           "max_texture_px": int(max_side or 0),
                           "textures_resized": int(resized),
                           "draco": bool(draco),
                           "size_bytes": int(size_bytes),
                           "tool": "EM Tools · Prepare for a use"}}


def step_level(levels: List[str], current: Optional[str], direction: int
               ) -> Optional[str]:
    """«LOD ▸» (direction +1, lighter) and «◂ LOD» (-1, heavier), clamped to
    the levels the library has. None when there is nothing to step to."""
    ordered = sorted({str(lv) for lv in levels or [] if lv}, key=level_key)
    if not ordered:
        return None
    if current not in ordered:
        return ordered[0]
    i = ordered.index(current) + (1 if direction > 0 else -1)
    i = max(0, min(len(ordered) - 1, i))
    return ordered[i]


#: U1 · the levels a model has BY NAME, the convention of the scenes made before
#: the versions: `ME_EST_fr_LOD0…LOD2` side by side in `RB/TempluMare_2021.blend`,
#: `ME_TM038_LOD0…LOD3` in `TM038_semented.blend` (measured on Templu Mare, 4
#: Oct 2026: 15 objects of the scene show a mesh named so, the 8 tiles and the
#: RMSF fragments). They were walked by two codes of their own (RM Manager and
#: Anastylosis); now by this one.
LOD_NAME = re.compile(r"^(.+)_LOD(\d+)$")


def split_lod_name(name: Optional[str]):
    """``("ME_TM038", 3)`` for ``ME_TM038_LOD3``; ``(None, None)`` otherwise."""
    m = LOD_NAME.match(str(name or ""))
    return (m.group(1), int(m.group(2))) if m else (None, None)


def level_number(level: Optional[str]) -> int:
    """The number of a level for the lists' LOD column (``LOD2`` → 2); 0 for
    the master or a level without a number."""
    m = re.search(r"(\d+)", str(level or ""))
    return int(m.group(1)) if m else 0


def resolve_level(levels: List[str], requested: str):
    """(the level to show, whether it is another than the one asked).

    The level asked when it is there; for a ``LODn`` that is not, the nearest
    heavier one there is (the highest ``LODk`` with k ≤ n), else the lightest
    numbered — the rule the two old codes had, kept so that «LOD 3» on a list
    of fragments that stop at LOD2 still shows something. ``(None, False)``
    when there is nothing to show."""
    have = [str(lv) for lv in levels or [] if lv]
    if requested in have:
        return requested, False
    m = re.match(r"^LOD(\d+)$", str(requested or ""), re.I)
    numbered = {int(mm.group(1)): lv for lv in have for mm in [re.match(r"^LOD(\d+)$", lv, re.I)] if mm}
    if not m or not numbered:
        return None, False
    n = int(m.group(1))
    lower = [k for k in numbered if k <= n]
    return numbered[max(lower) if lower else min(numbered)], True


def said_moves(moved: List[str], fallbacks: List[str]) -> List[tuple]:
    """The sentences of a change of level, the same from every panel:
    ``[(kind, text)]`` with kind INFO or WARNING."""
    out = []
    if fallbacks:
        out.append(("WARNING", "; ".join(fallbacks[:4]) + (" …" if len(fallbacks) > 4 else "")))
    out.append(("INFO", ("; ".join(moved[:6]) + (f" (and {len(moved) - 6} more)" if len(moved) > 6 else ""))
                if moved else "already at the end"))
    return out


def plan_library(versions: List[Dict[str, Any]], have: Dict[str, str]
                 ) -> Dict[str, List[Dict[str, Any]]]:
    """Pure: what to do with one asset's library.

    ``versions`` is ``api.versions_of`` (master first), ``have`` the levels the
    library holds now with the digest each mesh carries (``{level: digest}``).

    → ``here`` (same digest: nothing to fetch), ``fetch`` (each with ``why``:
    ``missing`` | ``changed``), ``local`` (a version with no digest — a master
    that lives as a datablock: kept as it is), ``external`` (a version whose
    bytes are not in the store: counted, left where they are).
    """
    out = {"here": [], "fetch": [], "local": [], "external": []}
    for entry in versions:
        level = entry.get("level") or ("master" if entry.get("master") else None)
        if not level:
            out["local"].append({**entry, "level": None,
                                 "why": "no level stated"})
            continue
        digest = _digest(entry.get("checksum"))
        row = {**entry, "level": level}
        if not digest:
            out["local"].append({**row, "why": "no digest"})
            continue
        if str(entry.get("residency") or "") == "reference":
            out["external"].append(row)
            continue
        held = _digest(have.get(level))
        if held and held == digest:
            out["here"].append(row)
        elif held:
            out["fetch"].append({**row, "why": "changed", "held": held})
        else:
            out["fetch"].append({**row, "why": "missing"})
    return out


def versioned_assets(records: List[Dict[str, Any]]) -> List[str]:
    """The assets with versions among the records of ``geometry_summary`` (the
    rows that carry ``asset_id``), in order of first appearance."""
    seen: List[str] = []
    for r in records or []:
        a = r.get("asset_id")
        if a and a not in seen:
            seen.append(str(a))
    return seen


def sentences(report: Dict[str, Any]) -> List[str]:
    """One line per fact, as the panel and the console say them."""
    out = [f"{report.get('assets', 0)} asset(s) with versions: "
           f"{report.get('here', 0)} mesh(es) already in their library"]
    if report.get("fetched") is not None:
        out.append(f"{report['fetched']} mesh(es) downloaded "
                   f"({report.get('missing', 0)} missing, "
                   f"{report.get('changed', 0)} changed)"
                   + (f", {report['not_fetched']} not ({report.get('why_not', '')})"
                      if report.get("not_fetched") else ""))
    else:
        out.append(f"{report.get('missing', 0)} missing, "
                   f"{report.get('changed', 0)} changed (not downloaded)")
    if report.get("objects_created"):
        out.append(f"{report['objects_created']} object(s) created, one per asset")
    return out


# ── Blender ──────────────────────────────────────────────────────────────────

#: Q4 · the versions added in THIS session and not yet written to a file,
#: {graph_id: ["ME_PODIO lod0", …]}. Measured on 4 Oct 2026: reloading GT16
#: went from 275 nodes back to 254 in silence — the library and the object's
#: properties stayed, the versions' nodes did not. A reload now asks first
#: (`import.em_graphml`, `import.em_emjson`), and saving the project as em.json
#: (`emjson_support.export_container_to_emjson`) clears the list.
UNSAVED: Dict[str, List[str]] = {}


def unsaved(graph_id: str) -> List[str]:
    return list(UNSAVED.get(str(graph_id or ""), []))


def mark_saved(graph_ids=None) -> None:
    if graph_ids is None:
        UNSAVED.clear()
        return
    for gid in graph_ids:
        UNSAVED.pop(str(gid), None)


def reload_warning(graph_id: str) -> str:
    """The sentence a reload says before dropping unsaved versions, or ''."""
    lost = unsaved(graph_id)
    if not lost:
        return ""
    shown = ", ".join(lost[:4]) + (f" +{len(lost) - 4}" if len(lost) > 4 else "")
    return (f"{len(lost)} version(s) added here are not in the file on disk "
            f"({shown}): reloading drops them from the graph — the meshes stay in "
            f"their libraries. Save the project as em.json first to keep them "
            f"(a GraphML does not carry the models they hang from).")


def _bpy():  # pragma: no cover — bpy
    import bpy  # type: ignore
    return bpy


def cache_folder() -> str:  # pragma: no cover — bpy
    """Beside the working .blend (so `//em_cache/…` is relative and travels in
    a package), or Blender's temp folder for a file never saved."""
    bpy = _bpy()
    if bpy.data.filepath:
        return os.path.dirname(bpy.data.filepath)
    return bpy.app.tempdir or os.path.expanduser("~")


def library_abspath(asset_id: str, room: Optional[str]) -> str:  # pragma: no cover
    return os.path.join(cache_folder(), *library_relpath(asset_id, room).split("/"))


def _same_file(a: str, b: str) -> bool:  # pragma: no cover — bpy
    bpy = _bpy()
    try:
        return os.path.normpath(bpy.path.abspath(a)) == os.path.normpath(bpy.path.abspath(b))
    except Exception:  # noqa: BLE001
        return False


def _library_block(path: str):  # pragma: no cover — bpy
    for lib in _bpy().data.libraries:
        if _same_file(lib.filepath, path):
            return lib
    return None


def linked_meshes(path: str) -> Dict[str, Any]:  # pragma: no cover — bpy
    """{level: linked mesh} of the library at ``path``, linking what is not
    linked yet. An absent file is an empty library."""
    bpy = _bpy()
    if not os.path.isfile(path):
        return {}
    lib = _library_block(path)
    present = {m.name for m in bpy.data.meshes if m.library is not None and lib is not None
               and m.library == lib}
    rel = path
    try:
        rel = bpy.path.relpath(path) if bpy.data.filepath else path
    except ValueError:
        pass
    with bpy.data.libraries.load(rel, link=True, relative=bool(bpy.data.filepath)) \
            as (src, dst):
        dst.meshes = [n for n in src.meshes if n not in present]
    lib = _library_block(path)
    out = {}
    for mesh in bpy.data.meshes:
        if lib is not None and mesh.library == lib:
            level = mesh.get(PROP_LEVEL) or level_of_mesh_name(mesh.name)
            if level:
                out[str(level)] = mesh
    return out


def write_library(path: str, new_meshes: Dict[str, Any],
                  base: str) -> Dict[str, Any]:  # pragma: no cover — bpy
    """(Re)write the asset's library: the meshes it holds now, with ``new_meshes``
    (``{level: local mesh}``) added or REPLACING the same level. The local
    meshes are moved into the library (removed from the main file once every
    user points at the linked one). → ``{level: linked mesh}``.

    Rewriting needs local copies of what stays: a linked datablock cannot be
    written, its ``copy()`` can (measured in 5.2), and the copies go as soon
    as the file is written.
    """
    bpy = _bpy()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    current = linked_meshes(path)
    keep = []
    for level, mesh in current.items():
        if level in new_meshes:
            continue
        clone = mesh.copy()
        clone.name = mesh_name(base, level)
        keep.append(clone)
    fresh = []
    for level, mesh in new_meshes.items():
        mesh.name = mesh_name(base, level)
        mesh[PROP_LEVEL] = level
        fresh.append(mesh)
    bpy.data.libraries.write(path, set(keep) | set(fresh), fake_user=True,
                             path_remap="ABSOLUTE")
    for clone in keep:
        bpy.data.meshes.remove(clone)
    lib = _library_block(path)
    if lib is not None:
        lib.reload()
    linked = linked_meshes(path)
    for level, mesh in new_meshes.items():
        target = linked.get(level)
        if target is None:
            continue
        for obj in [o for o in bpy.data.objects if o.data == mesh]:
            obj.data = target
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    return linked


def set_level(obj, level: str, meshes: Optional[Dict[str, Any]] = None
              ) -> bool:  # pragma: no cover — bpy
    """Show ``level`` on ``obj``: swap its mesh datablock. The object — its
    name, its properties, its place in the graph — does not change."""
    meshes = meshes if meshes is not None else levels_of(obj)
    mesh = meshes.get(level)
    if mesh is None:
        return False
    obj.data = mesh
    obj[PROP_LEVEL] = level
    if mesh.get(PROP_DIGEST):
        obj[PROP_DIGEST] = mesh[PROP_DIGEST]
    if mesh.get(PROP_VERSION):
        obj[PROP_VERSION] = mesh[PROP_VERSION]
    return True


#: Q1 · where the MASTER's mesh is when it lives in a library of its own (the
#: case of every real scene: `ME_PODIO_LOD0` in `RB/TempluMare_2021.blend`).
#: Written on the OBJECT — a linked mesh cannot carry a property — by «Add
#: version…», read by `levels_of`.
PROP_MASTER_MESH = "em_master_mesh"
PROP_MASTER_LIBRARY = "em_master_library"
PROP_MASTER_LEVEL = "em_master_level"


def _master_by_reference(obj) -> Dict[str, Any]:  # pragma: no cover — bpy
    """{level: the master's mesh} when it lives in a library of its own."""
    bpy = _bpy()
    name = obj.get(PROP_MASTER_MESH)
    if not name:
        return {}
    where = obj.get(PROP_MASTER_LIBRARY) or ""
    level = str(obj.get(PROP_MASTER_LEVEL) or "master")
    for mesh in bpy.data.meshes:
        if mesh.name != name:
            continue
        lib = mesh.library
        if (lib is None and not where) or (lib is not None and where
                                           and _same_file(lib.filepath, where)):
            return {level: mesh}
    if where and os.path.isfile(bpy.path.abspath(where)):
        # linked by the version's library before, not in this session yet
        with bpy.data.libraries.load(where, link=True) as (src, dst):
            dst.meshes = [n for n in src.meshes if n == name]
        return {level: dst.meshes[0]} if dst.meshes else {}
    return {}


def levels_of(obj) -> Dict[str, Any]:  # pragma: no cover — bpy
    """{level: mesh} of the object: the asset's library — found from the
    asset, not from the mesh shown, so the chain is walkable both ways — and
    the master where it lives, by reference.

    Measured on 4 Oct 2026: reading only the library of the CURRENT mesh,
    «LOD ▸» on ME_PODIO (master linked from `RB/TempluMare_2021.blend`, version
    in `em_cache/local/<asset>.blend`) found one level either way and said
    «already at the end»."""
    bpy = _bpy()
    out: Dict[str, Any] = {}
    asset = obj.get(PROP_ASSET)
    if asset:
        room = _room_id()
        for r in ([room, None] if room else [None]):
            path = library_abspath(str(asset), r)
            if os.path.isfile(path):
                out.update(linked_meshes(path))
                break
    data = getattr(obj, "data", None)
    lib = getattr(data, "library", None)
    if lib is not None and not out:
        out.update(linked_meshes(bpy.path.abspath(lib.filepath)))
    for level, mesh in _master_by_reference(obj).items():
        out.setdefault(level, mesh)
    return out


def asset_objects(objects=None) -> List[Any]:  # pragma: no cover — bpy
    objects = objects if objects is not None else _bpy().data.objects
    return [o for o in objects if o.get(PROP_ASSET) and o.type == "MESH"]


class NamedLevel:
    """U1 · a level known by its NAME only, linked when it is shown: a mesh of
    a library (``kind="lib"``) or, for scenes that keep each level as its own
    object, another object of the scene (``kind="object"``)."""

    __slots__ = ("kind", "name", "path")

    def __init__(self, kind: str, name: str, path: str = ""):
        self.kind, self.name, self.path = kind, name, path

    def get(self, _key, default=None):  # a mesh's .get, for callers that read properties
        return default

    def __repr__(self):  # pragma: no cover
        return f"NamedLevel({self.kind!r}, {self.name!r})"


#: the meshes' NAMES of each library, read without linking them (the LOD0 of a
#: tile is the heaviest mesh of the file): {abspath: (mtime, [names])}
_LIBRARY_NAMES: Dict[str, Any] = {}


def library_mesh_names(path: str) -> List[str]:  # pragma: no cover — bpy
    bpy = _bpy()
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return []
    got = _LIBRARY_NAMES.get(path)
    if got and got[0] == mtime:
        return got[1]
    with bpy.data.libraries.load(path, link=True) as (src, _dst):
        names = list(src.meshes)
    _LIBRARY_NAMES[path] = (mtime, names)
    return names


def named_levels(obj) -> Dict[str, Any]:  # pragma: no cover — bpy
    """{``LODn``: NamedLevel} of an object without versions whose levels follow
    the ``_LODn`` convention: the meshes of the SAME library with its base name
    (the tiles, the RMSF fragments), or the other objects of the scene with its
    base name."""
    bpy = _bpy()
    out: Dict[str, Any] = {}
    data = getattr(obj, "data", None)
    lib = getattr(data, "library", None) if data is not None else None
    base, _ = split_lod_name(getattr(data, "name", ""))
    if lib is not None and base:
        path = bpy.path.abspath(lib.filepath)
        for name in library_mesh_names(path):
            b, k = split_lod_name(name)
            if b == base:
                out[f"LOD{k}"] = NamedLevel("lib", name, path)
        return out
    base = split_lod_name(obj.name)[0] or base
    if not base:
        return out
    for other in bpy.data.objects:
        b, k = split_lod_name(other.name)
        if b == base and other.type == obj.type:
            out[f"LOD{k}"] = NamedLevel("object", other.name)
    return out if len(out) > 1 else {}


def has_levels(obj) -> bool:  # pragma: no cover — bpy
    """Cheap, for drawing: the object has versions or follows ``_LODn``."""
    if obj is None:
        return False
    if obj.get(PROP_ASSET):
        return True
    data = getattr(obj, "data", None)
    return bool(split_lod_name(obj.name)[0] or (data is not None and split_lod_name(data.name)[0]))


def all_levels(obj) -> Dict[str, Any]:  # pragma: no cover — bpy
    """THE levels of an object, for every panel: its versions (the asset's
    library and the master by reference, read through the graph's ids) when
    it has them, else the ones its names give."""
    if obj is None:
        return {}
    if obj.get(PROP_ASSET):
        return levels_of(obj)
    return named_levels(obj)


def current_level(obj) -> Optional[str]:  # pragma: no cover — bpy
    if obj is None:
        return None
    if obj.get(PROP_LEVEL):
        return str(obj[PROP_LEVEL])
    data = getattr(obj, "data", None)
    for name in (getattr(data, "name", ""), obj.name):
        _, k = split_lod_name(name)
        if k is not None:
            return f"LOD{k}"
    return None


def _linked_mesh(path: str, name: str):  # pragma: no cover — bpy
    bpy = _bpy()
    for mesh in bpy.data.meshes:
        if mesh.name == name and mesh.library is not None and _same_file(mesh.library.filepath, path):
            return mesh
    with bpy.data.libraries.load(path, link=True) as (src, dst):
        dst.meshes = [n for n in src.meshes if n == name]
    return dst.meshes[0] if dst.meshes else None


def show_level(obj, level: str, levels: Optional[Dict[str, Any]] = None):  # pragma: no cover — bpy
    """Show ``level`` on ``obj`` → the object that shows it now (the same one,
    with its name following the level when it carried ``_LODn``; another one
    for scenes that keep a level per object), or None."""
    levels = levels if levels is not None else all_levels(obj)
    ref = levels.get(level)
    if ref is None:
        return None
    if not isinstance(ref, NamedLevel):
        return obj if set_level(obj, level, levels) else None
    if ref.kind == "object":
        other = _bpy().data.objects.get(ref.name)
        if other is None:
            return None
        if other is not obj:
            obj.hide_viewport = obj.hide_render = True
            other.hide_viewport = other.hide_render = False
        return other
    if getattr(obj, "library", None) is not None:
        return None   # a linked object cannot take another mesh
    mesh = _linked_mesh(ref.path, ref.name)
    if mesh is None:
        return None
    obj.data = mesh
    base, _ = split_lod_name(obj.name)
    if base:
        obj.name = f"{base}_{level}"
    return obj


def after_switch(scene, old_name: str, shown, level: str) -> None:  # pragma: no cover — bpy
    """The lists that name the object follow it: RM Manager's, Anastylosis's,
    the RM containers' mesh names."""
    num = level_number(level)
    lists = [getattr(scene, "rm_list", None)]
    try:
        lists.append(scene.em_tools.anastylosis.list)
    except AttributeError:
        pass
    for coll in lists:
        for item in coll or []:
            if item.name == old_name:
                item.name = shown.name
                if hasattr(item, "active_lod"):
                    item.active_lod = num
                if hasattr(item, "object_exists"):
                    item.object_exists = True
    if old_name != shown.name:
        try:
            from ..rm_manager.containers import rename_mesh_in_containers
            rename_mesh_in_containers(scene, old_name, shown.name)
        except Exception:  # noqa: BLE001 — no containers here
            pass


def level_summary(obj):  # pragma: no cover — bpy
    """(how many levels, the number of the one shown) for the lists' LOD column."""
    levels = all_levels(obj)
    return len(levels), level_number(current_level(obj))


def switch(scene, obj, *, direction: int = 0, level: str = ""):  # pragma: no cover — bpy
    """ONE change of level, from any panel → (the move said, or "", the
    fallback said, or ""). ``direction`` steps («LOD ▸» +1, «◂ LOD» -1);
    ``level`` asks one (with the nearest-heavier fallback)."""
    levels = all_levels(obj)
    now = current_level(obj)
    fallback = ""
    if level:
        target, fell = resolve_level(list(levels), level)
        if target and fell:
            fallback = f"no {level} for {obj.name}: {target} shown"
    else:
        target = step_level(list(levels), now, direction)
    if not target or target == now:
        return "", fallback
    old = obj.name
    shown = show_level(obj, target, levels)
    if shown is None:
        return "", f"{old}: {target} could not be shown"
    after_switch(scene, old, shown, target)
    return f"{old} → {target}", fallback


def step_object(obj, direction: int) -> Optional[str]:  # pragma: no cover — bpy
    import bpy  # type: ignore
    said, _ = switch(bpy.context.scene, obj, direction=direction)
    return said.rsplit(" → ", 1)[1] if said else None


_PENDING_NAMES: set = set()


def _read_names_later(path: str) -> None:  # pragma: no cover — bpy
    """A library's names cannot be read while a panel draws (no writing to
    bpy.data there): read them in a timer, then redraw."""
    if path in _PENDING_NAMES:
        return
    _PENDING_NAMES.add(path)
    bpy = _bpy()

    def later():
        try:
            library_mesh_names(path)
        finally:
            _PENDING_NAMES.discard(path)
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                area.tag_redraw()
        return None

    bpy.app.timers.register(later, first_interval=0.05)


def levels_to_draw(obj) -> List[str]:  # pragma: no cover — bpy
    """The levels of ``obj`` as a panel may know them WITHOUT touching
    bpy.data: the meshes already linked, the names already read."""
    bpy = _bpy()
    out = set()
    data = getattr(obj, "data", None)
    if obj.get(PROP_ASSET):
        lib = getattr(data, "library", None)
        for mesh in bpy.data.meshes:
            if mesh.library is not None and mesh.get(PROP_ASSET) == obj.get(PROP_ASSET) or (
                    lib is not None and mesh.library == lib and level_of_mesh_name(mesh.name)):
                lv = mesh.get(PROP_LEVEL) or level_of_mesh_name(mesh.name)
                if lv:
                    out.add(str(lv))
        if obj.get(PROP_MASTER_MESH):
            out.add(str(obj.get(PROP_MASTER_LEVEL) or "master"))
        if obj.get(PROP_LEVEL):
            out.add(str(obj[PROP_LEVEL]))
        return sorted(out, key=level_key)
    lib = getattr(data, "library", None) if data is not None else None
    base, _ = split_lod_name(getattr(data, "name", ""))
    if lib is not None and base:
        path = bpy.path.abspath(lib.filepath)
        got = _LIBRARY_NAMES.get(path)
        if got is None:
            _read_names_later(path)
            names = [m.name for m in bpy.data.meshes if m.library == lib]
        else:
            names = got[1]
        for name in names:
            b, k = split_lod_name(name)
            if b == base:
                out.add(f"LOD{k}")
        return sorted(out, key=level_key)
    return sorted(named_levels(obj), key=level_key)


def draw_levels(layout, obj, *, scope: str = "", title: str = "Levels of detail") -> None:  # pragma: no cover — bpy
    """The same box in Asset versions, RM Manager and Anastylosis: the levels
    of ``obj`` (◂ LOD, LOD ▸, one button per level) and, with ``scope``, the
    same two arrows for the whole list."""
    if obj is not None and has_levels(obj):
        box = layout.box()
        box.label(text=f"{title} · {obj.name} · {current_level(obj) or '?'}", icon="MOD_DECIM")
        row = box.row(align=True)
        op = row.operator("em.asset_lod_step", text="◂ LOD")
        op.direction, op.scope, op.object_name = -1, "OBJECT", obj.name
        op = row.operator("em.asset_lod_step", text="LOD ▸")
        op.direction, op.scope, op.object_name = 1, "OBJECT", obj.name
        grid = box.row(align=True)
        now = current_level(obj)
        for lv in levels_to_draw(obj):
            op = grid.operator("em.asset_set_level", text=lv, depress=(lv == now))
            op.level, op.scope, op.object_name = lv, "OBJECT", obj.name
    if scope:
        row = layout.row(align=True)
        row.label(text="Whole list:" if scope != "SCENE" else "Whole scene:")
        op = row.operator("em.asset_lod_step", text="◂ LOD")
        op.direction, op.scope = -1, scope
        op = row.operator("em.asset_lod_step", text="LOD ▸")
        op.direction, op.scope = 1, scope


def mesh_from_file(path: str, importer: Optional[Callable] = None,
                   frame=None):  # pragma: no cover — bpy
    """Import a file and keep only its geometry, as ONE local mesh: several
    mesh objects are joined, the imported objects removed.

    The mesh is written in the frame of the asset's object (``frame``, its
    world matrix) so that every level sits where the others sit, whatever
    rotation the importer gave the objects it made; without a frame the
    importer's transform is baked in."""
    bpy = _bpy()
    if importer is None:
        from ..shelf_tool.operators import _import_mesh as importer
    made = [o for o in (importer(path) or []) if o.type == "MESH"]
    if not made:
        return None
    if len(made) > 1:
        with bpy.context.temp_override(active_object=made[0],
                                       selected_editable_objects=made,
                                       selected_objects=made):
            bpy.ops.object.join()
        made = [made[0]]
    obj = made[0]
    mesh = obj.data
    bpy.context.view_layer.update()
    placed = obj.matrix_world.copy()
    mesh.transform(frame.inverted() @ placed if frame is not None else placed)
    bpy.data.objects.remove(obj)
    return mesh


def measure_mesh(mesh) -> Dict[str, Any]:  # pragma: no cover — bpy
    """The raw numbers of a mesh for :func:`version_measures`: triangles,
    surface (scene units taken as metres), the share of UV space its islands
    fill per atlas, and the image atlases its materials use."""
    mesh.calc_loop_triangles()
    tris = len(mesh.loop_triangles)
    area = sum(p.area for p in mesh.polygons)
    images = {}
    for mat in getattr(mesh, "materials", []) or []:
        tree = getattr(mat, "node_tree", None) if mat is not None else None
        for node in (tree.nodes if tree is not None else []):
            img = getattr(node, "image", None)
            if img is not None:
                images[img.name] = max(img.size[0], img.size[1]) if img.size[0] else 0
    uv_area = 0.0
    uv = mesh.uv_layers.active
    if uv is not None:
        data = uv.data
        for tri in mesh.loop_triangles:
            (ax, ay), (bx, by), (cx, cy) = (tuple(data[i].uv) for i in tri.loops)
            uv_area += abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay)) / 2.0
    count = len(images)
    return {"tris": tris, "area_m2": area, "texture_count": count,
            "texture_side_px": max(images.values()) if images else 0,
            "uv_fraction": (uv_area / count) if count else 0.0,
            "vertices": len(mesh.vertices), "faces": len(mesh.polygons)}


def _stamp_mesh(mesh, *, asset_id: str, version_id: str, level: str,
                digest: str) -> None:  # pragma: no cover — bpy
    mesh[PROP_ASSET] = asset_id
    mesh[PROP_VERSION] = version_id
    mesh[PROP_LEVEL] = level
    if digest:
        mesh[PROP_DIGEST] = _digest(digest)


def _suffix(entry: Dict[str, Any], media: str = "") -> str:
    from .materialise import _suffix_for
    return _suffix_for({"media_type": media or entry.get("media_type"),
                        "url": entry.get("url"), "name": entry.get("name")})


def check_libraries(graph, *, room: Optional[str], download: bool,
                    fetch: Optional[Callable[[str], Any]] = None,
                    importer: Optional[Callable] = None,
                    summary: Optional[Dict[str, Any]] = None
                    ) -> Dict[str, Any]:  # pragma: no cover — bpy
    """A3 · the assets with versions, against their libraries, mesh by mesh.

    For each asset: the versions the graph cites now (``versions_of``), the
    meshes its library holds (each with the digest it was made from), and the
    plan — here / missing / changed. With ``download`` the missing and changed
    ones are fetched by digest, imported as meshes, and the library rewritten
    around them; the others are NOT fetched. An asset with no object in the
    scene gets ONE, named after its RM, showing the master's level.
    """
    import tempfile

    from s3dgraphy import api

    bpy = _bpy()
    if fetch is None:
        from .materialise import _default_fetch as fetch
    if summary is None:
        summary = api.geometry_summary(graph)
    report: Dict[str, Any] = {"assets": 0, "here": 0, "missing": 0, "changed": 0,
                              "fetched": 0 if download else None, "not_fetched": 0,
                              "why_not": "", "objects_created": 0,
                              "fetched_levels": [], "per_asset": []}
    reasons = set()
    records = summary.get("resident") or []
    for asset_id in versioned_assets(records):
        versions = api.versions_of(graph, asset_id)
        links = api.inherited_links(graph, asset_id)
        facet = (links.get("facets") or [{}])[0]
        base = _base_name(facet, versions[0])
        path = library_abspath(asset_id, room)
        have = {lv: str(m.get(PROP_DIGEST) or "")
                for lv, m in linked_meshes(path).items()}
        plan = plan_library(versions, have)
        report["assets"] += 1
        report["here"] += len(plan["here"])
        report["missing"] += sum(1 for r in plan["fetch"] if r["why"] == "missing")
        report["changed"] += sum(1 for r in plan["fetch"] if r["why"] == "changed")
        fresh: Dict[str, Any] = {}
        holder = next((o for o in asset_objects() if o.get(PROP_ASSET) == asset_id),
                      None)
        frame = holder.matrix_world.copy() if holder is not None else None
        if download:
            for row in plan["fetch"]:
                try:
                    data, media = fetch(row["checksum"])
                except Exception as exc:  # noqa: BLE001 — a refusal is a row
                    report["not_fetched"] += 1
                    reasons.add(str(exc)[:80])
                    continue
                handle = tempfile.NamedTemporaryFile(suffix=_suffix(row, media),
                                                     delete=False)
                try:
                    handle.write(data)
                    handle.close()
                    mesh = mesh_from_file(handle.name, importer, frame)
                finally:
                    try:
                        os.unlink(handle.name)
                    except OSError:
                        pass
                if mesh is None:
                    report["not_fetched"] += 1
                    reasons.add("no importer for these bytes")
                    continue
                _stamp_mesh(mesh, asset_id=asset_id, version_id=row["id"],
                            level=row["level"], digest=row["checksum"])
                fresh[row["level"]] = mesh
                report["fetched"] += 1
                report["fetched_levels"].append(f"{base}{SEP}{row['level']}")
            if fresh:
                write_library(path, fresh, base)
        meshes = linked_meshes(path)
        obj = next((o for o in asset_objects() if o.get(PROP_ASSET) == asset_id), None)
        if obj is None and meshes:
            obj = _object_for(asset_id, base, facet, links, meshes, versions)
            report["objects_created"] += 1
        elif obj is not None and obj.get(PROP_LEVEL) in meshes:
            # the same level, maybe new bytes: point at the mesh the library has now
            set_level(obj, obj[PROP_LEVEL], meshes)
        report["per_asset"].append({"asset_id": asset_id, "name": base,
                                    "library": path, "levels": sorted(meshes, key=level_key),
                                    "plan": {k: [r.get("level") for r in v]
                                             for k, v in plan.items()}})
    report["why_not"] = "; ".join(sorted(reasons))[:160]
    ULTIMO.clear()
    ULTIMO.update({"sentences": sentences(report)})
    return report


def _base_name(facet: Dict[str, Any], master: Dict[str, Any]) -> str:
    name = str(facet.get("name") or master.get("name") or "asset")
    return name[len("Model for "):] if name.startswith("Model for ") else name


def _object_for(asset_id, base, facet, links, meshes, versions):  # pragma: no cover
    """ONE object for an asset that has none in the scene yet: named after its
    RM, showing the master's level, bound like a materialised model."""
    bpy = _bpy()
    from .materialise import _bind_objects

    master_level = versions[0].get("level") or "master"
    level = master_level if master_level in meshes else sorted(meshes, key=level_key)[0]
    obj = bpy.data.objects.new(base, meshes[level])
    bpy.context.scene.collection.objects.link(obj)
    obj[PROP_ASSET] = asset_id
    set_level(obj, level, meshes)
    _bind_objects([obj], {"checksum": obj.get(PROP_DIGEST, ""),
                          "resource_id": asset_id,
                          "node_id": facet.get("id") or asset_id,
                          "bind": links.get("binds") or []})
    obj[PROP_DIGEST] = meshes[level].get(PROP_DIGEST, "")
    return obj


# ── «Add version…» ───────────────────────────────────────────────────────────

def master_of(graph, obj, scene=None) -> Optional[str]:  # pragma: no cover — bpy
    """The asset (master resource) of the object, read off what binds it:
    the asset it already shows, the resource it was materialised from, or the
    resource its RM links (the master if one is declared). None if nothing."""
    from s3dgraphy import api

    for prop in (PROP_ASSET, "em_resource_id"):
        rid = obj.get(prop)
        if rid and graph.find_node_by_id(str(rid)) is not None:
            return api.asset_of(graph, str(rid))
    from ..rm_manager.containers import resolve_rm_node_id
    rm_id = resolve_rm_node_id(graph, obj, scene=scene, migra=False)
    if not rm_id:
        return None
    linked = [graph.find_node_by_id(e.edge_target) for e in graph.edges
              if e.edge_type == "has_linked_resource" and e.edge_source == rm_id]
    linked = [n for n in linked if n is not None and n.node_type == "resource"]
    if not linked:
        return None
    masters = [n for n in linked if (n.data or {}).get("tier") == "master"]
    return api.asset_of(graph, (masters or linked)[0].node_id)


def add_version_from_mesh(graph, obj, mesh, *, level: str = "", purpose: str = "",
                          master_level: str = "", files: List[Dict[str, Any]],
                          room: Optional[str], technique: str = "",
                          parameters: Optional[Dict[str, Any]] = None,
                          use: Optional[List[str]] = None,
                          made_from: Optional[str] = None,
                          packaging: Optional[str] = None,
                          stamp: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
                          revise: bool = False
                          ) -> Dict[str, Any]:  # pragma: no cover — bpy
    """The gesture behind «Add version…», once the version's mesh and bytes are
    in hand: the version in the graph, the mesh in the asset's library, the
    object still ONE (showing the level it showed).

    R4 (E.D., 6 Oct 2026) · ``stamp`` writes the version's dtcstamp, called
    with ``{version_id, level, source_id, asset_id}`` BEFORE the version enters
    the graph; a result without ``ok`` cancels it (a version is not born
    without its stamp). The receipt goes on the version's node."""
    from s3dgraphy import api
    if not hasattr(api, "add_version"):
        raise RuntimeError("this Blender's s3dgraphy has no asset versions "
                           "(api.add_version): it needs 1.6.0.dev34 or later")
    scene = _bpy().context.scene
    warnings: List[str] = []
    # Q2 · the chain hangs off the model the object ALREADY has
    from ..rm_manager.containers import seat_model_of
    _rm, seated = seat_model_of(scene, graph, obj)
    if seated:
        warnings.append(seated)
    asset_id = master_of(graph, obj, scene)
    if asset_id is None:
        from ..rm_manager.containers import ensure_rm_and_internal_resource
        _rm, asset_id, more = ensure_rm_and_internal_resource(scene, graph, obj)
        warnings += more
        if not asset_id:
            raise RuntimeError("; ".join(warnings) or
                               "this object has no resource to be the master of")
    digest = next((f.get("checksum") for f in files if f.get("checksum")), "")
    # D1 · made from the version the object shows (lod0 → lod1…), else from the
    # master (→ lod0); the level, when not named, is the one the chain computes
    source = made_from if made_from and graph.find_node_by_id(made_from) is not None \
        else asset_id
    raw = measure_mesh(mesh)
    lod0 = next((e for e in api.versions_of(graph, asset_id)
                 if e.get("lod_level") == "lod0"), None)
    lod0_tris = ((lod0 or {}).get("primitives") or {}).get("triangles")
    measures = version_measures(tris=raw["tris"], area_m2=raw["area_m2"],
                                texture_count=raw["texture_count"],
                                texture_side_px=raw["texture_side_px"],
                                uv_fraction=raw["uv_fraction"], lod0_tris=lod0_tris)
    stamped = None
    more = {"revise": True} if revise else {}
    if stamp is not None:
        try:
            from s3dgraphy.resources.versions import planned_version
            plan = planned_version(graph, source, level=(level or "").strip() or None,
                                   files=files, revise=revise)
        except ImportError:         # a s3dgraphy before the revisions of a version
            from s3dgraphy.resources.versions import lod_steps, version_id_for
            lvl = (level or "").strip() or f"lod{lod_steps(graph, source)}"
            plan = {"version_id": version_id_for(source, lvl), "level": lvl,
                    "revises": None}
        stamped = stamp({"version_id": plan["version_id"], "level": plan["level"],
                         "source_id": source, "asset_id": asset_id,
                         "revises": plan.get("revises")})
        if not stamped.get("ok"):
            raise RuntimeError("the version is not born without its stamp: "
                               + str(stamped.get("why") or stamped.get("line") or "?"))
    out = api.add_version(graph, source, level=level or None, purpose=purpose,
                          use=list(use or []) or None, measures=measures,
                          master_level=master_level or None, packaging=packaging,
                          files=files, residency="resident",
                          primitives={"vertices": raw["vertices"], "faces": raw["faces"],
                                      "triangles": raw["tris"]},
                          technique=technique or None, parameters=parameters,
                          tool="EM Tools", **more)
    asset_id = out["asset_id"]
    vnode = graph.find_node_by_id(out["version_id"])
    #: a file set is identified by its members digest, not by its door's bytes
    digest = str(((vnode.data or {}) if vnode is not None else {}).get("checksum") or digest)
    if stamped is not None:
        from .. import version_stamp
        out["stamp"] = {"path": stamped.get("stamp_path", ""), "state": stamped.get("state"),
                        "receipt": version_stamp.record(graph, out["version_id"], stamped)}
    master = api.versions_of(graph, asset_id)[0]
    base = obj.name
    path = library_abspath(asset_id, room)
    fresh = {}
    if obj.data is not None and obj.data.library is None:
        # the first version: the master's own mesh moves into the library too
        mlevel = master_level or master.get("level") or "master"   # D1: no level
        _stamp_mesh(obj.data, asset_id=asset_id, version_id=master["id"],
                    level=mlevel, digest=master.get("checksum") or "")
        fresh[mlevel] = obj.data
        obj[PROP_LEVEL] = mlevel
    elif (obj.data is not None and obj.data.library is not None
          and not obj.get(PROP_LEVEL)
          and not _same_file(obj.data.library.filepath, path)):
        # Q1 · the master lives in a library of its own: it stays there, and the
        # object remembers where, so «LOD ▸» and «◂ LOD» walk both ways
        mlevel = master_level or master.get("level") or "master"
        obj[PROP_MASTER_MESH] = obj.data.name
        obj[PROP_MASTER_LIBRARY] = obj.data.library.filepath
        obj[PROP_MASTER_LEVEL] = mlevel
        obj[PROP_LEVEL] = mlevel
    _stamp_mesh(mesh, asset_id=asset_id, version_id=out["version_id"],
                level=out["level"], digest=digest)
    fresh[out["level"]] = mesh
    obj[PROP_ASSET] = asset_id
    meshes = write_library(path, fresh, base)
    current = obj.get(PROP_LEVEL)
    if obj.get(PROP_MASTER_MESH):
        meshes = levels_of(obj)
    if current in meshes:
        set_level(obj, current, meshes)
    gid = str(getattr(graph, "graph_id", "") or "")
    UNSAVED.setdefault(gid, []).append(f"{obj.name} {out['level']}")
    return {**out, "library": path, "levels": sorted(meshes, key=level_key),
            "warnings": list(warnings) + list(out.get("warnings") or [])}


def _measures_line(m: Dict[str, Any]) -> str:
    """The measures of a version in one line for a person."""
    parts = []
    if m.get("tris_per_m2") is not None:
        parts.append(f"{m['tris_per_m2']:.0f} tris/m²")
    if m.get("texel_density_dd") is not None:
        parts.append(f"texel {m['texel_density_dd']:.2f} mm (ref. 1.26)")
    if m.get("texture_count"):
        parts.append(f"{m['texture_count']}×{m.get('texture_side_px', '?')} px")
    if m.get("uv_ratio") is not None:
        parts.append(f"UV {m['uv_ratio']:.2f}")
    if m.get("reduction_from_lod0") is not None:
        parts.append(f"{m['reduction_from_lod0']:.2%} of LOD0")
    return " · ".join(parts)


def _shown_version(obj) -> Optional[str]:  # pragma: no cover — bpy
    """The version the object shows now (its mesh's resource), None for the
    master or an object without versions."""
    mesh = getattr(obj, "data", None)
    vid = mesh.get(PROP_VERSION) if mesh is not None else None
    asset = obj.get(PROP_ASSET) if obj is not None else None
    return str(vid) if vid and vid != asset else None


def _version_info(context, obj) -> Optional[Dict[str, Any]]:  # pragma: no cover — bpy
    try:
        from ..functions import is_graph_available
        from s3dgraphy.resources.versions import version_info
        ok, graph = is_graph_available(context)
        vid = _shown_version(obj) or obj.get(PROP_ASSET)
        if not ok or graph is None or not vid or graph.find_node_by_id(str(vid)) is None:
            return None
        return version_info(graph, str(vid))
    except Exception:  # noqa: BLE001 — the panel draws without it
        return None


def _export_glb(mesh, path: str, *, draco: bool = False, viewer: bool = False,
                obj=None, recipe: Optional[Dict[str, Any]] = None,
                gltf: bool = False) -> None:  # pragma: no cover — bpy
    """The version's bytes when the mesh was made here: a glb of that mesh
    (U1 · Draco-compressed when the use asks for it). ``viewer`` (H4, a version
    for Heriverse/ATON): written by the glTF writer of the old Heriverse
    exporter, with its settings — the same glTF Heriverse always received;
    ``gltf`` writes it separate (the .gltf with its .bin and textures beside).

    ``recipe`` (``version_recipe``): ``transform: world`` puts ``obj``'s
    placement in the glTF node, as the old export of RM and RMSF did;
    ``animations`` carries the object's action with it."""
    bpy = _bpy()
    recipe = recipe or {}
    tmp = bpy.data.objects.new("_em_version_export", mesh)
    if obj is not None and recipe.get("transform") == "world":
        tmp.matrix_world = obj.matrix_world.copy()
    if (obj is not None and recipe.get("animations", "none") != "none"
            and getattr(obj, "animation_data", None) is not None
            and obj.animation_data.action is not None):
        tmp.animation_data_create()
        tmp.animation_data.action = obj.animation_data.action
    bpy.context.scene.collection.objects.link(tmp)
    # Q3 · the selection and the active object come back as they were:
    # measured, after «Add version…» the master was no longer selected and
    # «LOD ▸» right after said «no object with versions here»
    layer = bpy.context.view_layer
    was_selected = [o for o in layer.objects if o.select_get()]
    was_active = layer.objects.active
    try:
        with bpy.context.temp_override(selected_objects=[tmp], active_object=tmp):
            for o in bpy.context.view_layer.objects:
                o.select_set(o == tmp)
            if viewer:
                from ..export_operators.heriverse import export_gltf_with_animation_support
                export_gltf_with_animation_support(
                    path, bpy.context.window_manager.export_vars, bpy.context.scene,
                    use_selection=True, format_file="GLTF_SEPARATE" if gltf else "GLB",
                    animations=recipe.get("animations") if recipe else None,
                    frame_range=recipe.get("frame_range") if recipe else None)
            else:
                bpy.ops.export_scene.gltf(filepath=path, use_selection=True,
                                          export_format="GLB",
                                          export_draco_mesh_compression_enable=bool(draco))
    finally:
        bpy.data.objects.remove(tmp)
        for o in was_selected:
            try:
                o.select_set(True)
            except ReferenceError:
                pass
        if was_active is not None:
            layer.objects.active = was_active


#: the image files of a glTF the recipe's JPEG quality applies to
_JPEG = (".jpg", ".jpeg")


def reencode_jpegs(paths: List[str], quality: int) -> Dict[str, Any]:
    """The old export's «Compress Textures» (``compress_paradata_textures``),
    on the textures of ONE version: each JPEG saved again at ``quality``. A PNG
    stays a PNG (the old code wrote JPEG bytes into a PNG without alpha: not
    carried over). ``{reencoded, before, after}`` in bytes, or ``{not_applied}``
    when Pillow is missing."""
    try:
        from PIL import Image
    except ImportError:
        return {"not_applied": "jpeg_quality: no Pillow in this Python"}
    n, before, after = 0, 0, 0
    for path in paths:
        if not path.lower().endswith(_JPEG) or not os.path.isfile(path):
            continue
        before += os.path.getsize(path)
        with Image.open(path) as img:
            img = img.convert("RGB") if img.mode != "RGB" else img.copy()
        img.save(path, "JPEG", quality=int(quality), optimize=True)
        after += os.path.getsize(path)
        n += 1
    return {"reencoded": n, "before": before, "after": after}


def files_of_entry(path: str) -> Dict[str, Any]:
    """The files of the bytes at ``path`` as ``api.add_version`` takes them,
    measured the way the stamp measures them (``dtcstamp.follow_references``:
    a .gltf with its .bin and images, an .obj with its .mtl and textures), the
    entry point first. ``{files, missing}``; one file when it calls nothing."""
    from ..resource_digest import dtcstamp
    entry = os.path.abspath(path)
    base = os.path.dirname(entry)
    found = dtcstamp().follow_references(entry)
    members = found.get("members") or []
    door = os.path.basename(entry)
    files = []
    for m in sorted(members, key=lambda m: (m.get("role") != "entry_point", m["path"])):
        spec = {"path": m["path"], "url": os.path.join(base, *m["path"].split("/")),
                "checksum": m["digest"], "size_bytes": int(m.get("size_bytes") or 0),
                "role": "entry_point" if m["path"] == door else "member"}
        if spec["role"] == "entry_point" and door.lower().endswith(".gltf"):
            spec["media_type"] = "model/gltf+json"
        files.append(spec)
    if len(files) <= 1:
        files = [{"path": door, "url": entry, "checksum": dtcstamp().file_digest(entry),
                  "size_bytes": os.path.getsize(entry)}]
    return {"files": files, "missing": list(found.get("missing") or [])}


def write_version(obj, mesh, recipe: Dict[str, Any], folder: str, base: str
                  ) -> Dict[str, Any]:  # pragma: no cover — bpy
    """The bytes of a version as its RECIPE says (``version_recipe``, E.D. 6 Oct
    2026). A glTF separate goes in a folder of its own named by its content
    (``<base>-<hex8>/<object>.gltf`` with its ``.bin`` and textures), so a
    version's files are never written over another's; a glb is one file.

    → ``{entry, files, applied, packaging}``: ``files`` as ``api.add_version``
    takes them (the entry point first), ``applied`` what was measured."""
    import shutil
    import uuid
    from .asset_upload import sha256_of_file
    gltf = recipe["format"] == "gltf_separate"
    applied: Dict[str, Any] = {}
    if not gltf:
        path = os.path.join(folder, f"{base}.glb")
        _export_glb(mesh, path, draco=recipe.get("draco", False),
                    viewer=recipe.get("viewer", False), obj=obj, recipe=recipe)
        size = os.path.getsize(path)
        applied["size_bytes"] = size
        return {"entry": path, "packaging": None, "applied": applied,
                "files": [{"path": os.path.basename(path), "url": path,
                           "checksum": _digest(sha256_of_file(path)), "size_bytes": size,
                           "media_type": "model/gltf-binary"}]}
    writing = os.path.join(folder, f".writing-{uuid.uuid4().hex[:8]}")
    os.makedirs(writing)
    try:
        stem = safe(getattr(obj, "name", "") or base)
        entry = os.path.join(writing, f"{stem}.gltf")
        _export_glb(mesh, entry, viewer=True, obj=obj, recipe=recipe, gltf=True)
        measured = files_of_entry(entry)
        if measured["missing"]:
            raise RuntimeError("the glTF names files that were not written: "
                               f"{measured['missing'][:3]}")
        if recipe.get("jpeg_quality"):
            applied.update(reencode_jpegs(
                [os.path.join(writing, *f["path"].split("/")) for f in measured["files"]],
                recipe["jpeg_quality"]))
            measured = files_of_entry(entry)       # the bytes changed: measured again
        from ..resource_digest import members_digest
        whole = members_digest(measured["files"])
        final = os.path.join(folder, f"{base}-{whole.split(':')[-1][:8]}")
        if os.path.isdir(final):
            shutil.rmtree(writing)          # the same bytes are there already
        else:
            os.replace(writing, final)
    except Exception:
        shutil.rmtree(writing, ignore_errors=True)
        raise
    files = files_of_entry(os.path.join(final, f"{stem}.gltf"))["files"]
    applied.update(files=len(files), size_bytes=sum(f["size_bytes"] for f in files),
                   textures=sum(1 for f in files[1:] if not f["path"].endswith(".bin")))
    return {"entry": files[0]["url"], "files": files, "applied": applied,
            "packaging": "file_set"}


def document_of(graph, obj) -> str:  # pragma: no cover — bpy
    """The document an RMDoc quad represents: its ``em_doc_node_id`` (the
    Document Manager's), else — the old exporter's convention — a document,
    extractor or combiner of the graph with the object's name. ``""``."""
    doc_id = str(obj.get("em_doc_node_id", "") or "")
    if doc_id or graph is None:
        return doc_id
    for kind in ("document", "extractor", "combiner"):
        for n in graph.indices.nodes_by_type.get(kind, []):
            if n.name == obj.name:
                return n.node_id
    return ""


def seat_representation(context, graph, obj, recipe: Dict[str, Any]
                        ) -> Dict[str, Any]:  # pragma: no cover — bpy
    """The representation node a version of ``obj`` hangs off, by category,
    and its placement when the recipe puts it on the node.

    * an **RMDoc** quad (``em_doc_node_id``): the ``<document>_rm_doc`` node
      (made from the scene by ``graph_updaters`` when missing), so its version
      is the RMDoc's, not an RM's;
    * an **RMSF** (the anastylosis list): its ``<object>_rmsf`` node, made as
      the old export made it when missing, tied to its special find;
    * an **RM**: the model it has (``seat_model_of``), as before.

    ``transform: node`` writes the object's location, rotation and scale on
    that node (``data.transform``), which Heriverse applies — the old «Preserve
    Transforms for each RMDoc». → ``{node_id, placement}``."""
    from .. import version_recipe as VR
    category = recipe.get("category", "rm")
    #: as the old export read it: the euler, or the quaternion as an XYZ euler
    rotation = (obj.rotation_euler if obj.rotation_mode != "QUATERNION"
                else obj.rotation_quaternion.to_euler("XYZ"))
    placement = (VR.placement(obj.location, rotation, obj.scale)
                 if recipe.get("transform") == "node" else None)
    node_id = ""
    if category == "rmdoc":
        doc_id = document_of(graph, obj)
        doc = graph.find_node_by_id(doc_id) if doc_id else None
        if doc is None:
            raise RuntimeError(f"{obj.name}: its document {doc_id or '?'} is not in this graph")
        node_id = f"{doc_id}_rm_doc"
        if graph.find_node_by_id(node_id) is None and obj.get("em_doc_node_id"):
            from ..graph_updaters import update_representation_model_docs
            update_representation_model_docs(graph)
        if graph.find_node_by_id(node_id) is None:
            #: the old convention (a mesh named as the document): the RMDoc
            #: node as the old exporter made it
            from s3dgraphy.nodes.representation_node import RepresentationModelDocNode
            graph.add_node(RepresentationModelDocNode(
                node_id=node_id, name=f"RM for {doc.name}", type="RM",
                transform=VR.placement(obj.location, rotation, obj.scale),
                description=f"Representation model for {doc.node_type} {doc.name}"))
            graph.add_edge(edge_id=f"{doc_id}_has_representation_model_doc_{node_id}",
                           edge_source=doc_id, edge_target=node_id,
                           edge_type="has_representation_model_doc")
    elif category == "rmsf":
        item = next((i for i in context.scene.em_tools.anastylosis.list
                     if i.name == obj.name), None)
        node_id = (getattr(item, "node_id", "") or f"{obj.name}_rmsf") if item else f"{obj.name}_rmsf"
        if graph.find_node_by_id(node_id) is None:
            from s3dgraphy.nodes.representation_node import RepresentationModelSpecialFindNode
            graph.add_node(RepresentationModelSpecialFindNode(
                node_id=node_id, name=f"RMSF for {obj.name}", type="RM",
                transform=VR.placement(obj.location, rotation, obj.scale),
                description=f"Representation model for "
                            f"{getattr(item, 'sf_node_name', '') or 'Special Find'}"))
            sf_id = str(getattr(item, "sf_node_id", "") or "")
            if sf_id and graph.find_node_by_id(sf_id) is not None:
                edge_id = f"{sf_id}_has_representation_model_{node_id}"
                if graph.find_edge_by_id(edge_id) is None:
                    graph.add_edge(edge_id=edge_id, edge_source=sf_id,
                                   edge_target=node_id, edge_type="has_representation_model")
    if node_id and obj.get("em_rm_node_id") != node_id:
        obj["em_rm_node_id"] = node_id          # the version hangs off THIS node
    if placement is not None:
        target = node_id
        if not target:
            from ..rm_manager.containers import resolve_rm_node_id
            target = resolve_rm_node_id(graph, obj, scene=context.scene, migra=False) or ""
        node = graph.find_node_by_id(target) if target else None
        if node is not None:
            node.data["transform"] = placement
            if hasattr(node, "transform"):
                node.transform = placement
    return {"node_id": node_id, "placement": placement}


def _stamper(graph, obj, files: List[Dict[str, Any]], technique: str,
             parameters: Dict[str, Any], *, label: str):  # pragma: no cover — bpy
    """R4 · the stamp of a version about to be born (`version_stamp`): its
    input is the version or master it is made from, its recipe the step's
    parameters, its expected digest the one the graph will register."""
    def stamp(info: Dict[str, Any]) -> Dict[str, Any]:
        from .. import birth_stamp as BS
        from .. import version_stamp as VS
        from ..resource_digest import members_digest
        master = BS.master_of(obj, graph=graph, scene=_bpy().context.scene)
        inputs = VS.inputs_for(graph, info["source_id"], master=master)
        expected = members_digest(files) if len(files) > 1 else str(files[0]["checksum"])
        operator, software = VS.operator_and_software()
        revision_of = None
        if info.get("revises"):
            old = graph.find_node_by_id(info["revises"])
            revision_of = {"resource_id": info["revises"],
                           "digest": str(((old.data or {}) if old is not None else {})
                                         .get("checksum") or "")}
        return VS.stamp_version(VS.entry_of(files), version_id=info["version_id"],
                                inputs=inputs, technique=technique,
                                parameters=parameters, label=label,
                                expected_digest=expected, operator=operator,
                                software=software, revision_of=revision_of)
    return stamp


def _room_id() -> Optional[str]:  # pragma: no cover — bpy
    try:
        from . import room
        return room.room().get("room_id")
    except Exception:  # noqa: BLE001
        return None


def _operator_classes():  # pragma: no cover — bpy
    import bpy  # type: ignore

    from .asset_upload import sha256_of_file

    def _graph(context):
        from ..functions import is_graph_available
        ok, graph = is_graph_available(context)
        return graph if ok else None

    class EM_OT_asset_add_version(bpy.types.Operator):
        """Add a version of the selected master: a child resource made from it
        (lod_generation) with a level and a purpose. Its mesh goes into the
        asset's library and the object stays one"""

        bl_idname = "em.asset_add_version"
        bl_label = "Add version…"
        bl_options = {"REGISTER", "UNDO"}

        level: bpy.props.StringProperty(  # type: ignore
            name="Name", default="",
            description=("The version's name. Empty: the level the chain gives "
                         "(lod0 from the master, lod1 from lod0…)"))
        use: bpy.props.EnumProperty(  # type: ignore
            name="Uses", options={"ENUM_FLAG"}, default={"web"},
            description="What this version is for — one or more",
            items=[(k, label, tip) for k, label, tip in USES])
        master_level: bpy.props.StringProperty(  # type: ignore
            name="Master is", default="",
            description="Legacy: the master has no level (D1)")
        computed: bpy.props.StringProperty(default="")  # type: ignore
        source: bpy.props.EnumProperty(  # type: ignore
            name="Geometry from", default="SELECTED",
            items=[("SELECTED", "The other selected object",
                    "Its mesh becomes the version; the object goes away"),
                   ("FILE", "A file", "An OBJ / glTF / PLY of this level"),
                   ("DECIMATE", "Decimate the master", "Made here, now")])
        filepath: bpy.props.StringProperty(  # type: ignore
            name="File", subtype="FILE_PATH", default="")
        ratio: bpy.props.FloatProperty(  # type: ignore
            name="Ratio", default=0.25, min=0.001, max=1.0)

        @classmethod
        def poll(cls, context):
            obj = context.active_object
            return obj is not None and obj.type == "MESH"

        def invoke(self, context, event):
            obj = context.active_object
            self.level = ""
            self.computed = ""
            graph = _graph(context)
            made_from = _shown_version(obj)
            if graph is not None:
                try:
                    from s3dgraphy.resources.versions import lod_steps
                    src = made_from or master_of(graph, obj, context.scene)
                    if src:
                        self.computed = f"lod{lod_steps(graph, src)}"
                except Exception:  # noqa: BLE001 — the dialog opens anyway
                    pass
            if len([o for o in context.selected_objects if o.type == "MESH"]) < 2:
                self.source = "FILE"
            return context.window_manager.invoke_props_dialog(self, width=420)

        def draw(self, context):
            col = self.layout.column()
            col.label(text=f"Level: {self.computed or 'computed from the chain'} "
                           f"(made from what the object shows)", icon="SORTSIZE")
            col.prop(self, "level")
            col.label(text="Uses")
            col.prop(self, "use")
            col.prop(self, "source")
            if self.source == "FILE":
                col.prop(self, "filepath")
            elif self.source == "DECIMATE":
                col.prop(self, "ratio")
            col.label(text="Measures (tris/m², texel side, atlases, UV) are taken "
                           "from the mesh.", icon="INFO")

        def execute(self, context):
            graph = _graph(context)
            if graph is None:
                self.report({"ERROR"}, "no graph loaded: a version is written "
                                       "into the graph of its asset")
                return {"CANCELLED"}
            obj = context.active_object
            room = _room_id()
            folder = os.path.join(cache_folder(), CACHE_DIR, safe(room or "local"),
                                  "versions")
            os.makedirs(folder, exist_ok=True)
            technique, parameters = "", {}
            try:
                if self.source == "FILE":
                    path = bpy.path.abspath(self.filepath)
                    if not os.path.isfile(path):
                        self.report({"ERROR"}, f"no file at {path}")
                        return {"CANCELLED"}
                    mesh = mesh_from_file(path, frame=obj.matrix_world.copy())
                    other = None
                    #: R4 · the file as the stamp measures it: an .obj with its
                    #: .mtl and textures is one resource of several files
                    files = files_of_entry(path)["files"]
                else:
                    if self.source == "SELECTED":
                        other = next((o for o in context.selected_objects
                                      if o != obj and o.type == "MESH"), None)
                        if other is None:
                            self.report({"ERROR"}, "select the version's object "
                                                   "too, with the master active")
                            return {"CANCELLED"}
                        mesh = other.data.copy()
                        mesh.transform(obj.matrix_world.inverted() @ other.matrix_world)
                    else:
                        mod = obj.modifiers.new("_em_decimate", "DECIMATE")
                        mod.ratio = self.ratio
                        deps = context.evaluated_depsgraph_get()
                        mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(deps))
                        obj.modifiers.remove(mod)
                        other = None
                        technique = "decimation"
                        parameters = {"ratio": self.ratio}
                    path = os.path.join(folder, f"{safe(obj.name)}{SEP}"
                                                f"{safe(self.level or self.computed or 'version')}.glb")
                    _export_glb(mesh, path)
                    files = [{"path": os.path.basename(path), "url": path,
                              "checksum": _digest(sha256_of_file(path)),
                              "size_bytes": os.path.getsize(path)}]
                if mesh is None:
                    self.report({"ERROR"}, "no geometry in that file")
                    return {"CANCELLED"}
                parameters = dict(parameters, source=self.source.lower(),
                                  tool="EM Tools · Add version")
                out = add_version_from_mesh(
                    graph, obj, mesh, level=self.level.strip(),
                    master_level=self.master_level, files=files, room=room,
                    technique=technique, parameters=parameters,
                    use=sorted(self.use), made_from=_shown_version(obj),
                    packaging="file_set" if len(files) > 1 else None,
                    stamp=_stamper(graph, obj, files, technique, parameters,
                                   label=f"{obj.name} {self.level.strip() or self.computed}"))
            except Exception as exc:  # noqa: BLE001 — the reason is the user's
                self.report({"ERROR"}, f"could not add the version: {exc}")
                return {"CANCELLED"}
            if self.source == "SELECTED" and other is not None:
                bpy.data.objects.remove(other)
            for w in out["warnings"]:
                self.report({"WARNING"}, w)
            self.report({"INFO"}, f"{obj.name}: version {out['level']} "
                                  f"= {out.get('lod_level') or '?'} "
                                  f"({', '.join(out.get('use') or []) or 'no use'}); "
                                  f"{_measures_line(out.get('measures') or {})}; levels "
                                  f"{', '.join(out['levels'])}")
            return {"FINISHED"}

    def _recipe_defaults(op, context):
        """The recipe's fields preset by the object's category and the uses
        (`version_recipe.defaults`): the old Heriverse export's for a viewer."""
        from .. import version_recipe as VR
        rec = VR.defaults(op.category, op.use, VR.scene_values(context.scene))
        op.format, op.transform = rec["format"], rec["transform"]
        op.max_texture, op.jpeg_quality = rec["max_texture_px"], rec["jpeg_quality"]
        op.animations, op.frame_range = rec["animations"], rec["frame_range"]
        op.draco, op.ratio = rec["draco"], rec["ratio"]
        op.recipe_ready = True

    def _detect_category(context, obj) -> str:
        from .. import version_recipe as VR
        if obj is None:
            return "rm"
        em = context.scene.em_tools
        names = {i.name for i in em.anastylosis.list} if hasattr(em, "anastylosis") else set()
        return VR.category_of(doc_node_id=document_of(_graph(context), obj),
                              in_anastylosis=obj.name in names)

    def _on_use(self, context):
        #: the uses may be set before anything else (a call with use=…): the
        #: category is read from the object first, then the recipe preset
        if not self.category_known:
            self.category = _detect_category(context, context.active_object)
        _recipe_defaults(self, context)

    def _on_category(self, context):
        self.category_known = True
        _recipe_defaults(self, context)

    def _on_field(self, context):
        self.recipe_ready = True

    from .. import version_recipe as _VR

    class EM_OT_asset_prepare_for_use(bpy.types.Operator):
        """Prepare a version of what the object shows for a use (web,
        realtime, Heriverse, ATON…): a distribution version with its use, its
        computed level, the numbers measured, and its RECIPE — how its bytes
        were written, preset by the object's category (RM, RMDoc, RMSF) —
        recorded in the DTC step and in the version's dtcstamp. For Heriverse
        and ATON it is a glTF with its textures, as the old exporter wrote it"""

        bl_idname = "em.asset_prepare_for_use"
        bl_label = "Prepare for a use…"
        bl_options = {"REGISTER", "UNDO"}

        use: bpy.props.EnumProperty(  # type: ignore
            name="For", options={"ENUM_FLAG"}, default={"web"},
            description="What this version is for — one or more",
            items=[(k, label, tip) for k, label, tip in USES],
            update=_on_use)
        category: bpy.props.EnumProperty(  # type: ignore
            name="Category", default="rm", items=list(_VR.CATEGORIES),
            options={"SKIP_SAVE"},
            description="What the object is: its recipe starts from the old "
                        "export's for that category",
            update=_on_category)
        format: bpy.props.EnumProperty(  # type: ignore
            name="Format", default="glb", items=list(_VR.FORMATS), update=_on_field)
        transform: bpy.props.EnumProperty(  # type: ignore
            name="Placement", default="local", items=list(_VR.TRANSFORMS),
            update=_on_field)
        ratio: bpy.props.FloatProperty(  # type: ignore
            name="Decimate to", default=1.0, min=0.001, max=1.0, update=_on_field,
            description="The share of the triangles kept (1: no decimation)")
        max_texture: bpy.props.IntProperty(  # type: ignore
            name="Largest texture side", default=2048, min=0, soft_max=8192,
            update=_on_field,
            description="Textures larger than this are scaled down, px (0: kept)")
        jpeg_quality: bpy.props.IntProperty(  # type: ignore
            name="JPEG quality", default=0, min=0, max=100, update=_on_field,
            description="The JPEG textures saved again at this quality (0: as they are)")
        animations: bpy.props.EnumProperty(  # type: ignore
            name="Animations", default="none", items=list(_VR.ANIMATIONS),
            update=_on_field)
        frame_range: bpy.props.BoolProperty(  # type: ignore
            name="Frame range only", default=True, update=_on_field)
        draco: bpy.props.BoolProperty(  # type: ignore
            name="Draco compression", default=True, update=_on_field,
            description="Compress the geometry of the glb (Draco); never for "
                        "Heriverse/ATON (Q5)")
        level: bpy.props.StringProperty(  # type: ignore
            name="Name", default="", options={"SKIP_SAVE"},
            description=("The version's name. Empty: the level the chain gives; "
                         "a version already there for the same use is REVISED "
                         "(made again with this recipe), one for other uses keeps "
                         "its level and this one is named after its uses"))
        #: SKIP_SAVE: Blender remembers an operator's last values, and a run
        #: without the dialog (the Deck, a script) must start from the
        #: object's category and level, not from the previous object's
        recipe_ready: bpy.props.BoolProperty(  # type: ignore
            default=False, options={"HIDDEN", "SKIP_SAVE"})
        category_known: bpy.props.BoolProperty(  # type: ignore
            default=False, options={"HIDDEN", "SKIP_SAVE"})
        computed: bpy.props.StringProperty(  # type: ignore
            default="", options={"HIDDEN", "SKIP_SAVE"})

        @classmethod
        def poll(cls, context):
            obj = context.active_object
            return obj is not None and obj.type == "MESH"

        def _level_and_revise(self, context, graph, obj):
            """The level this version takes and whether it revises the one
            there: same use → a revision (the recipe changed), other uses →
            the level named after the uses (``lod0-aton-heriverse``)."""
            from s3dgraphy import api
            lvl = self.level.strip() or self.computed or ""
            src = _shown_version(obj) or master_of(graph, obj, context.scene)
            if not lvl or not src:
                return lvl, False
            tag = "-".join(sorted(self.use))
            for _ in range(2):
                same = [e for e in api.versions_of(graph, api.asset_of(graph, src))
                        if not e["master"] and e["level"] == lvl]
                if not same:
                    return lvl, False
                if set(same[0].get("use") or []) & set(self.use):
                    return lvl, True
                lvl = f"{lvl}-{tag}"
            return lvl, False

        def _category_of(self, context, obj):
            return _detect_category(context, obj)

        def invoke(self, context, event):
            obj = context.active_object
            graph = _graph(context)
            self.computed = ""
            if graph is not None:
                try:
                    from s3dgraphy.resources.versions import lod_steps
                    src = _shown_version(obj) or master_of(graph, obj, context.scene)
                    #: D1 · a model with no version yet: its first is lod0
                    self.computed = f"lod{lod_steps(graph, src)}" if src else "lod0"
                except Exception:  # noqa: BLE001
                    pass
            self.category = self._category_of(context, obj)
            _recipe_defaults(self, context)
            return context.window_manager.invoke_props_dialog(self, width=440)

        def draw(self, context):
            col = self.layout.column()
            col.label(text=f"Level: {self.computed or 'computed from the chain'}, "
                           f"from what the object shows", icon="SORTSIZE")
            col.label(text="For")
            col.prop(self, "use")
            box = col.box()
            box.label(text="Recipe (written in the version and in its stamp)",
                      icon="PRESET")
            col.prop(self, "level")
            box.prop(self, "category")
            box.prop(self, "format")
            box.prop(self, "transform")
            box.prop(self, "ratio")
            row = box.row(align=True)
            row.prop(self, "max_texture")
            row.prop(self, "jpeg_quality")
            row = box.row(align=True)
            row.prop(self, "animations")
            if self.animations != "none":
                row.prop(self, "frame_range")
            viewer = _VR.is_viewer(self.use)
            sub = box.row()
            sub.enabled = not viewer
            sub.prop(self, "draco")
            if viewer:
                box.label(text="Heriverse/ATON: the model as it is, no Draco (Q5)",
                          icon="INFO")

        def recipe(self):
            return _VR.checked({"category": self.category, "format": self.format,
                                "transform": self.transform,
                                "max_texture_px": self.max_texture,
                                "jpeg_quality": self.jpeg_quality,
                                "animations": self.animations,
                                "frame_range": self.frame_range,
                                "draco": self.draco, "ratio": self.ratio}, self.use)

        def execute(self, context):
            graph = _graph(context)
            if graph is None:
                self.report({"ERROR"}, "no graph loaded: a version is written "
                                       "into the graph of its asset")
                return {"CANCELLED"}
            if not self.use:
                self.report({"ERROR"}, "say what the version is for")
                return {"CANCELLED"}
            obj = context.active_object
            if not self.recipe_ready:      # run without its dialog (a script, the Deck)
                if not self.category_known:
                    self.category = self._category_of(context, obj)
                _recipe_defaults(self, context)
            try:
                recipe = self.recipe()
            except ValueError as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            viewer = _VR.is_viewer(self.use)
            recipe["viewer"] = viewer
            try:
                #: first: an RMDoc / RMSF finds its node, and its level after it
                seated = seat_representation(context, graph, obj, recipe)
            except Exception as exc:  # noqa: BLE001 — the reason is the user's
                self.report({"ERROR"}, f"could not prepare the version: {exc}")
                return {"CANCELLED"}
            if not self.computed:          # run without its dialog (a script)
                try:
                    from s3dgraphy.resources.versions import lod_steps
                    src = _shown_version(obj) or master_of(graph, obj, context.scene)
                    #: D1 · a model with no version yet: its first is lod0
                    self.computed = f"lod{lod_steps(graph, src)}" if src else "lod0"
                except Exception:  # noqa: BLE001
                    pass
            room = _room_id()
            folder = os.path.join(cache_folder(), CACHE_DIR, safe(room or "local"),
                                  "versions")
            os.makedirs(folder, exist_ok=True)
            made = []          # the copies made here, removed if it fails
            try:
                deps = context.evaluated_depsgraph_get()
                mod = None
                if recipe["ratio"] < 1.0:
                    mod = obj.modifiers.new("_em_prepare", "DECIMATE")
                    mod.ratio = recipe["ratio"]
                    deps = context.evaluated_depsgraph_get()
                mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(deps))
                if mod is not None:
                    obj.modifiers.remove(mod)
                resized = 0
                if recipe["max_texture_px"]:
                    for i, mat in enumerate(list(mesh.materials)):
                        if mat is None or mat.node_tree is None:
                            continue
                        copy = mat.copy()
                        made.append(copy)
                        for node in copy.node_tree.nodes:
                            img = getattr(node, "image", None)
                            if img is None or not img.size[0]:
                                continue
                            side = max(img.size[0], img.size[1])
                            want = resized_side(side, recipe["max_texture_px"])
                            if want >= side:
                                continue
                            small = img.copy()
                            made.append(small)
                            k = want / float(side)
                            small.scale(max(1, int(img.size[0] * k)),
                                        max(1, int(img.size[1] * k)))
                            node.image = small
                            resized += 1
                        mesh.materials[i] = copy
                tag = "-".join(sorted(self.use))
                level, revise = self._level_and_revise(context, graph, obj)
                base = f"{safe(obj.name)}{SEP}{safe(level or self.computed or 'version')}"
                if tag not in base:
                    base = f"{base}-{safe(tag)}"
                written = write_version(obj, mesh, recipe, folder, base)
                applied = dict(written["applied"], textures_resized=resized)
                if seated.get("placement"):
                    applied["placement"] = seated["placement"]
                technique = _VR.technique_of(recipe, resized=resized,
                                             reencoded=applied.get("reencoded", 0))
                params = _VR.step_parameters(
                    {k: v for k, v in recipe.items() if k != "viewer"}, applied=applied)
                files = written["files"]
                out = add_version_from_mesh(
                    graph, obj, mesh, files=files, room=room,
                    technique=technique, parameters=params,
                    use=sorted(self.use), made_from=_shown_version(obj),
                    packaging=written["packaging"], level=level, revise=revise,
                    stamp=_stamper(graph, obj, files, technique, params,
                                   label=f"{obj.name} for {', '.join(sorted(self.use))}"))
            except Exception as exc:  # noqa: BLE001 — the reason is the user's
                for block in made:
                    try:
                        (bpy.data.images if hasattr(block, "pixels")
                         else bpy.data.materials).remove(block)
                    except Exception:  # noqa: BLE001
                        pass
                self.report({"ERROR"}, f"could not prepare the version: {exc}")
                return {"CANCELLED"}
            size = applied.get("size_bytes", 0)
            step = {"technique": technique, "parameters": params}
            PREPARED.clear()
            PREPARED.update({**out, "step": step, "glb": written["entry"],
                             "entry": written["entry"], "files": files,
                             "recipe": recipe, "seated": seated})
            for w in out["warnings"]:
                self.report({"WARNING"}, w)
            self.report({"INFO"}, f"{obj.name}: {out['level']} = {out.get('lod_level') or '?'} "
                                  f"for {', '.join(out.get('use') or [])} · "
                                  f"{_VR.said(recipe)} · {technique} · {len(files)} file(s), "
                                  f"{size // 1024} kB · stamped · "
                                  f"{_measures_line(out.get('measures') or {})}")
            return {"FINISHED"}

    #: U1 · where a change of level applies: one object (a list's row), the
    #: selection, every object of the scene with levels, or the objects of RM
    #: Manager's / Anastylosis's list
    SCOPES = [("SELECTED", "Selected", ""), ("OBJECT", "One object", ""),
              ("SCENE", "Whole scene", ""), ("RM_LIST", "RM list", ""),
              ("ANASTYLOSIS", "Anastylosis list", ""), ("ACTIVE", "Active object", "")]

    def _targets(context, scope, object_name):
        scene = context.scene
        objs = bpy.data.objects
        if scope == "OBJECT":
            o = objs.get(object_name)
            return [o] if o is not None else []
        if scope == "ACTIVE":
            o = context.active_object
            return [o] if o is not None else []
        if scope == "SCENE":
            return [o for o in scene.objects if has_levels(o)]
        if scope == "RM_LIST":
            names = [it.name for it in getattr(scene, "rm_list", [])]
        elif scope == "ANASTYLOSIS":
            names = [it.name for it in scene.em_tools.anastylosis.list]
        else:
            return [o for o in context.selected_objects if has_levels(o)]
        return [o for o in (objs.get(n) for n in names) if o is not None and has_levels(o)]

    def _say(op, moved, fallbacks):
        for kind, text in said_moves(moved, fallbacks):
            op.report({kind}, text)

    class EM_OT_asset_lod_step(bpy.types.Operator):
        """Show the next level of detail: the object stays, its mesh changes"""

        bl_idname = "em.asset_lod_step"
        bl_label = "LOD ▸"
        bl_options = {"REGISTER", "UNDO"}

        direction: bpy.props.IntProperty(default=1)  # type: ignore
        whole_scene: bpy.props.BoolProperty(default=False)  # type: ignore
        scope: bpy.props.EnumProperty(items=SCOPES, default="SELECTED")  # type: ignore
        object_name: bpy.props.StringProperty()  # type: ignore

        def execute(self, context):
            scope = "SCENE" if self.whole_scene else self.scope
            targets = _targets(context, scope, self.object_name)
            if not targets:
                self.report({"WARNING"}, "no object with levels here")
                return {"CANCELLED"}
            moved, fallbacks = [], []
            for o in targets:
                said, fell = switch(context.scene, o, direction=self.direction)
                if said:
                    moved.append(said)
                if fell:
                    fallbacks.append(fell)
            _say(self, moved, fallbacks)
            return {"FINISHED"}

    class EM_OT_asset_set_level(bpy.types.Operator):
        """Show this level of detail"""

        bl_idname = "em.asset_set_level"
        bl_label = "Show level"
        bl_options = {"REGISTER", "UNDO"}

        level: bpy.props.StringProperty()  # type: ignore
        scope: bpy.props.EnumProperty(items=SCOPES, default="ACTIVE")  # type: ignore
        object_name: bpy.props.StringProperty()  # type: ignore

        def execute(self, context):
            targets = _targets(context, self.scope, self.object_name)
            if not targets:
                self.report({"ERROR"}, f"no level {self.level} for this object")
                return {"CANCELLED"}
            moved, fallbacks, none = [], [], []
            for o in targets:
                if self.level not in all_levels(o) and resolve_level(list(all_levels(o)), self.level)[0] is None:
                    none.append(o.name)
                    continue
                said, fell = switch(context.scene, o, level=self.level)
                if said:
                    moved.append(said)
                if fell:
                    fallbacks.append(fell)
            if none and not moved and not fallbacks:
                self.report({"ERROR"}, f"no level {self.level} for {', '.join(none[:4])}")
                return {"CANCELLED"}
            _say(self, moved, fallbacks)
            return {"FINISHED"}

    class EM_OT_asset_level_menu(bpy.types.Operator):
        """The levels of this object, to show one"""

        bl_idname = "em.asset_level_menu"
        bl_label = "Levels of detail"
        bl_options = set()

        object_name: bpy.props.StringProperty()  # type: ignore

        def invoke(self, context, event):
            obj = bpy.data.objects.get(self.object_name)
            if obj is None:
                return {"CANCELLED"}
            levels = sorted(all_levels(obj), key=level_key)
            now = current_level(obj)
            name = obj.name

            def draw(menu, _context):
                if not levels:
                    menu.layout.label(text="no other level in its library")
                for lv in levels:
                    op = menu.layout.operator("em.asset_set_level", text=lv,
                                              icon="CHECKMARK" if lv == now else "NONE")
                    op.level, op.scope, op.object_name = lv, "OBJECT", name

            context.window_manager.popup_menu(draw, title=f"Levels of detail · {name}")
            return {"FINISHED"}

    class EM_MT_asset_levels_selected(bpy.types.Menu):
        """One level for every selected object that has it (the nearest heavier one otherwise)"""

        bl_idname = "EM_MT_asset_levels_selected"
        bl_label = "Level for the selection"

        def draw(self, context):
            for n in range(0, 5):
                op = self.layout.operator("em.asset_set_level", text=f"LOD{n}")
                op.level, op.scope = f"LOD{n}", "SELECTED"

    class VIEW3D_PT_em_asset_versions(bpy.types.Panel):
        bl_label = "Asset versions"
        bl_idname = "VIEW3D_PT_em_asset_versions"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "EM Scene"
        bl_parent_id = "EM_PT_scene_space"  # P3: EMStudio's Space
        bl_order = 2
        bl_options = {"DEFAULT_CLOSED"}

        def draw(self, context):
            layout = self.layout
            obj = context.active_object
            row = layout.row(align=True)
            row.operator("em.asset_add_version", icon="ADD")
            # U1 · beside it: a version prepared for a use (web, realtime…)
            row.operator("em.asset_prepare_for_use", icon="MOD_DECIM")
            if obj is not None and obj.get(PROP_ASSET):
                # D1 · what the shown version IS: computed level, uses, measures
                info = _version_info(context, obj)
                if info:
                    layout.label(text=f"Level {info.get('lod_level') or '— (master)'} · "
                                      f"uses: {', '.join(info.get('use') or []) or '—'}",
                                 icon="SORTSIZE")
                    line = _measures_line(info.get("measures") or {})
                    if line:
                        layout.label(text=line, icon="BLANK1")
            # U1 · the one box of the levels, the same in RM Manager and Anastylosis
            draw_levels(layout, obj, scope="SCENE")
            # D1 · where the version shown comes from: its DTC as a card
            if obj is not None:
                try:
                    from .. import provenance_card
                    from ..functions import check_active_graph
                    _ok, _g = check_active_graph(context, show_message=False)
                    if _ok and _g is not None:
                        provenance_card.draw(layout, context,
                                             provenance_card.resource_of_object(
                                                 _g, obj, context.scene))
                except Exception as exc:  # noqa: BLE001
                    print(f"[asset versions] where it comes from: {exc}")
            # F1 · the starting package is in «The .blend in the room…», with
            # the snapshots (`windows.EM_OT_room_blend`)

    return (EM_OT_asset_add_version, EM_OT_asset_prepare_for_use, EM_OT_asset_lod_step, EM_OT_asset_set_level,
            EM_OT_asset_level_menu, EM_MT_asset_levels_selected, VIEW3D_PT_em_asset_versions)


_CLASSES: tuple = ()


def register():  # pragma: no cover — bpy
    import bpy  # type: ignore
    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():  # pragma: no cover — bpy
    import bpy  # type: ignore
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
