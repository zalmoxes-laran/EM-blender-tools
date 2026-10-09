"""The recipe of a version: how its bytes were written, so it says how it was
made and can be made again.

E.D. (6 Oct 2026, MICRO «i parametri diventano la ricetta della versione»): for
Heriverse/ATON the version on disk is a **glTF with its textures beside it**,
and every parameter of the old Heriverse export (Separate Textures, Preserve
Transforms for each RMDoc, Compress Textures with Max Size and Quality, Export
Animations…) is kept — not as a setting of an exporter, but as a parameter of
the VERSION, written in the ``lod_generation`` step that made it (the DTC) and
in its stamp.

What the old export did BY CATEGORY, read in its code (``_dead_code/
export_operators/heriverse/operator.py``), is the default here:

* **RM** — a glTF separate (``GLTF_SEPARATE``, the textures beside it) of the
  object with its placement in the scene (``use_selection`` writes the
  object's world matrix in the glTF node); textures as they are (Q5: no
  optimisation of its own).
* **RMDoc** — the same glTF, but the quad at the origin and its placement
  (position, rotation, scale) written on the RMDoc node, which Heriverse
  applies (``Preserve Transforms for each RMDoc``); textures capped at 2048 px
  and re-encoded at JPEG quality 60 (``Compress Textures``, ``Max Size``,
  ``Quality``: the scene's ``heriverse_rmdoc_texture_*``, whose defaults these
  are).
* **RMSF** — as the RM: the object with its placement.

The parameters of the PACKAGE (proxies, DosCo, panorama, zip, tilesets) are not
here: they are the disk road of the Publication Deck (``publication_heriverse``).

``bpy``-free: the suite reads it without Blender.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

#: the categories of a representation model a version can be made for
CATEGORIES = (("rm", "RM", "A representation model of the scene"),
              ("rmdoc", "RMDoc", "A document placed in space (a quad with its image)"),
              ("rmsf", "RMSF", "A special find (anastylosis)"))

#: how the bytes are written: a glTF with its .bin and textures beside it, or
#: one glb
FORMATS = (("gltf_separate", "glTF + textures",
            "A .gltf with its .bin and its textures beside it (Heriverse, ATON)"),
           ("glb", "glb", "One binary file, textures inside"))

#: where the placement of the object goes
TRANSFORMS = (("world", "In the glTF",
               "The object's placement in the scene written in the glTF node "
               "(the old export of RM and RMSF)"),
              ("node", "On the node",
               "The glTF at the origin, the placement written on the representation "
               "node, which the viewer applies (the old «Preserve Transforms for "
               "each RMDoc»)"),
              ("local", "None",
               "The mesh in its own frame, as the versions of an asset are kept"))

#: which animations go with it (the old «Export Animations»: all / the active)
ANIMATIONS = (("none", "None", "No animation"),
              ("active", "The active one", "The object's active action"),
              ("all", "All", "Every action (NLA strips)"))

#: the uses whose version is a package for a viewer (`asset_versions.VIEWER_PACKAGE_USES`)
VIEWER_USES = ("heriverse", "aton")

#: the old export's RMDoc texture compression (`heriverse_rmdoc_texture_max_res`,
#: `heriverse_rmdoc_texture_quality`, defaults of their properties)
RMDOC_MAX_TEXTURE_PX = 2048
RMDOC_JPEG_QUALITY = 60

#: the keys of a recipe, in the order a person reads them
KEYS = ("category", "format", "transform", "max_texture_px", "jpeg_quality",
        "animations", "frame_range", "draco", "ratio")


def is_viewer(uses: Iterable[str]) -> bool:
    return bool(set(uses or ()) & set(VIEWER_USES))


#: the scene properties the old exporter read for the RMDoc textures (still
#: registered: a .blend keeps the values its author chose)
SCENE_RMDOC_KEYS = {"max_texture_px": "heriverse_rmdoc_texture_max_res",
                    "jpeg_quality": "heriverse_rmdoc_texture_quality",
                    "compress": "heriverse_paradata_texture_compression"}


def scene_values(scene: Any) -> Dict[str, Any]:
    """The old exporter's RMDoc settings as THIS scene holds them (measured on
    Templu Mare v2: max 1024 px, quality 60 — not the properties' defaults)."""
    out = {}
    for key, prop in SCENE_RMDOC_KEYS.items():
        if scene is not None and hasattr(scene, prop):
            out[key] = getattr(scene, prop)
    return out


def defaults(category: str, uses: Iterable[str],
             scene: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The recipe a version starts from: the old export's for its category when
    it is made for a viewer (heriverse/aton), else the one «Prepare for a
    use…» had (a glb in the asset's frame, textures capped at 2048, Draco).
    ``scene`` (:func:`scene_values`) are the old exporter's settings saved in
    the .blend: the RMDoc textures follow them, as the old export did."""
    category = category if category in {c for c, _l, _t in CATEGORIES} else "rm"
    if not is_viewer(uses):
        return {"category": category, "format": "glb", "transform": "local",
                "max_texture_px": 2048, "jpeg_quality": 0, "animations": "none",
                "frame_range": True, "draco": True, "ratio": 1.0}
    recipe = {"category": category, "format": "gltf_separate",
              "transform": "world", "max_texture_px": 0, "jpeg_quality": 0,
              "animations": "none", "frame_range": True, "draco": False,
              "ratio": 1.0}
    if category == "rmdoc":
        scene = scene or {}
        compress = scene.get("compress", True)
        recipe.update(transform="node",
                      max_texture_px=int(scene.get("max_texture_px", RMDOC_MAX_TEXTURE_PX)),
                      jpeg_quality=int(scene.get("jpeg_quality", RMDOC_JPEG_QUALITY)))
        if not compress:
            #: the old code compressed whatever the toggle said (it never read
            #: it): a scene that turned it off is heard here
            recipe.update(max_texture_px=0, jpeg_quality=0)
    return recipe


def checked(recipe: Dict[str, Any], uses: Iterable[str]) -> Dict[str, Any]:
    """A recipe as it will be applied: unknown values refused, and Draco off
    for a viewer's version (Q5, E.D. 5 Oct 2026: a version for Heriverse is the
    model as it is; a light one is a web version)."""
    out = dict(recipe)
    for key, choices in (("category", CATEGORIES), ("format", FORMATS),
                         ("transform", TRANSFORMS), ("animations", ANIMATIONS)):
        allowed = {c for c, _l, _t in choices}
        if out.get(key) not in allowed:
            raise ValueError(f"{key} must be one of {sorted(allowed)}, got {out.get(key)!r}")
    out["max_texture_px"] = max(0, int(out.get("max_texture_px") or 0))
    out["jpeg_quality"] = max(0, min(100, int(out.get("jpeg_quality") or 0)))
    out["ratio"] = float(out.get("ratio") if out.get("ratio") is not None else 1.0)
    out["frame_range"] = bool(out.get("frame_range"))
    out["draco"] = bool(out.get("draco")) and not is_viewer(uses)
    return out


def category_of(*, doc_node_id: str = "", in_anastylosis: bool = False) -> str:
    """The category of an object: an RMDoc quad carries ``em_doc_node_id``, an
    RMSF is in the anastylosis list, anything else is an RM."""
    if doc_node_id:
        return "rmdoc"
    if in_anastylosis:
        return "rmsf"
    return "rm"


def placement(location, rotation_euler, scale) -> Dict[str, list]:
    """The transform a representation node carries (strings, as the old export
    and ``graph_updaters`` write it)."""
    return {"position": [str(float(v)) for v in location],
            "rotation": [str(float(v)) for v in rotation_euler],
            "scale": [str(float(v)) for v in scale]}


def step_parameters(recipe: Dict[str, Any], *, applied: Dict[str, Any]) -> Dict[str, Any]:
    """The parameters of the ``lod_generation`` step: the recipe as asked, then
    what was MEASURED applying it (``textures_resized``, ``textures_reencoded``,
    ``size_bytes``, ``files``…), and the tool. A value asked and not applied
    (no Pillow for the JPEG quality) is said in ``not_applied``."""
    params = {k: recipe[k] for k in KEYS if k in recipe}
    for k, v in (applied or {}).items():
        params[k] = v
    params["tool"] = "EM Tools · Prepare for a use"
    return params


def technique_of(recipe: Dict[str, Any], *, resized: int, reencoded: int) -> str:
    """What changed, as the step's technique: the geometry, else the textures,
    else only the encoding — the word «Prepare for a use…» already wrote."""
    if float(recipe.get("ratio") or 1.0) < 1.0:
        return "decimation"
    if resized or reencoded:
        return "texture_reduction"
    return "compression" if recipe.get("draco") else "format_conversion"


def said(recipe: Dict[str, Any]) -> str:
    """The recipe in one line for a person."""
    fmt = dict((c, l) for c, l, _t in FORMATS).get(recipe.get("format"), recipe.get("format"))
    where = dict((c, l) for c, l, _t in TRANSFORMS).get(recipe.get("transform"), "")
    parts = [str(recipe.get("category", "")).upper(), fmt, f"placement: {where.lower()}"]
    if recipe.get("max_texture_px"):
        parts.append(f"textures ≤ {recipe['max_texture_px']} px")
    if recipe.get("jpeg_quality"):
        parts.append(f"JPEG {recipe['jpeg_quality']}")
    if recipe.get("animations") and recipe["animations"] != "none":
        parts.append(f"animations: {recipe['animations']}")
    if recipe.get("draco"):
        parts.append("Draco")
    if float(recipe.get("ratio") or 1.0) < 1.0:
        parts.append(f"decimated to {recipe['ratio']:.2f}")
    return " · ".join(p for p in parts if p)


def recipe_of_step(parameters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The recipe read back from a step's parameters (the keys it wrote)."""
    p = parameters or {}
    return {k: p[k] for k in KEYS if k in p}
