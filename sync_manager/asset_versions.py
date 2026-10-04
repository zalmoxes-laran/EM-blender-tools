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
        ("preview", "Preview", "A light preview for catalogues and records"))


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
                          made_from: Optional[str] = None
                          ) -> Dict[str, Any]:  # pragma: no cover — bpy
    """The gesture behind «Add version…», once the version's mesh and bytes are
    in hand: the version in the graph, the mesh in the asset's library, the
    object still ONE (showing the level it showed)."""
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
    out = api.add_version(graph, source, level=level or None, purpose=purpose,
                          use=list(use or []) or None, measures=measures,
                          master_level=master_level or None,
                          files=files, residency="resident",
                          primitives={"vertices": raw["vertices"], "faces": raw["faces"],
                                      "triangles": raw["tris"]},
                          technique=technique or None, parameters=parameters,
                          tool="EM Tools")
    asset_id = out["asset_id"]
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


def _export_glb(mesh, path: str) -> None:  # pragma: no cover — bpy
    """The version's bytes when the mesh was made here: a glb of that mesh."""
    bpy = _bpy()
    tmp = bpy.data.objects.new("_em_version_export", mesh)
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
            bpy.ops.export_scene.gltf(filepath=path, use_selection=True,
                                      export_format="GLB")
    finally:
        bpy.data.objects.remove(tmp)
        for o in was_selected:
            try:
                o.select_set(True)
            except ReferenceError:
                pass
        if was_active is not None:
            layer.objects.active = was_active


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
                if mesh is None:
                    self.report({"ERROR"}, "no geometry in that file")
                    return {"CANCELLED"}
                files = [{"path": os.path.basename(path), "url": path,
                          "checksum": _digest(sha256_of_file(path)),
                          "size_bytes": os.path.getsize(path)}]
                out = add_version_from_mesh(
                    graph, obj, mesh, level=self.level.strip(),
                    master_level=self.master_level, files=files, room=room,
                    technique=technique, parameters=parameters,
                    use=sorted(self.use), made_from=_shown_version(obj))
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
        bl_category = "EM Bridge"
        bl_order = 5
        bl_options = {"DEFAULT_CLOSED"}

        def draw(self, context):
            layout = self.layout
            obj = context.active_object
            row = layout.row(align=True)
            row.operator("em.asset_add_version", icon="ADD")
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
            from . import scene_package
            scene_package.draw(layout)

    return (EM_OT_asset_add_version, EM_OT_asset_lod_step, EM_OT_asset_set_level,
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
