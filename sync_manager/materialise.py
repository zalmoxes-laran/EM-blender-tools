"""DP-76, the consuming half: the geometry the room describes, IN THIS SCENE.

Until now the two halves were uneven. A model could go UP — export the mesh,
publish the bytes into the room's store, record the genesis (`promote_model`,
STEP 2) — but nothing came DOWN: joining a room adopted the document and left
the 3D behind, which the adopt operator said out loud and this module is the
answer to.

What it does is deliberately small: **it consumes what the graph already
references.** It creates no RM, hats nothing, invents no epoch. The graph
already says "this epoch has a model, and the model's bytes are that sha256";
this fetches those bytes and puts them in the scene, bound the way the graph
says. Authoring geometry is a different act with its own verbs
(`create_proxy_for_unit`, `import_geometry`) — and mixing the two would make
"look at what the room has" capable of changing the room.

Three rules, and each is a line somebody could have crossed:

* **resident only.** The list comes from `s3dgraphy.api.store_backed_geometry`,
  which excludes `reference` resources: their bytes are on somebody's NAS,
  outside em-server, and a path from another machine is not something to hand a
  mesh importer. They are left exactly as they are, and counted in the report so
  the number on screen is not silently the smaller half;
* **the gate is the server's, and a refusal is a SENTENCE.** An embargoed asset
  answers 403 to a viewer. That is not an error to raise through the operator: it
  is one row skipped with a reason, the rest of the batch materialised, and a
  scene that is whole either way;
* **content-addressed, so re-running is free.** An object already carrying a
  digest is that digest's object. Nothing is re-downloaded and nothing is
  duplicated — the same reason the store deduplicates on the way up.

Blender-only steps (the import operator, the object properties) are isolated
behind `importer` / `fetch` parameters so the logic can be measured headless;
the rest of the module is plain Python.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Callable, Dict, List, Optional

#: Where a materialised object records the bytes it came from. THE cache key:
#: the scene is content-addressed the same way the store is, so "is this already
#: here?" is a digest comparison and never a name comparison (a name is
#: somebody's choice and changes; a digest is the file).
PROP_DIGEST = "em_asset_sha256"
#: …and the graph nodes it belongs to, so a later pass can find them again.
PROP_RESOURCE = "em_resource_id"
PROP_CARRIER = "em_rm_node_id"
PROP_BIND = "em_bound_to"

#: media type → the extension the importer dispatches on. The bytes arrive with
#: no name at all (they are addressed by their content), so the suffix of the
#: temporary file is what tells Blender which importer to use.
_SUFFIX_BY_MEDIA = {
    "model/gltf-binary": ".glb",
    "model/gltf+json": ".gltf",
    "model/obj": ".obj",
    "model/stl": ".stl",
    "application/x-ply": ".ply",
}


def _suffix_for(record: Dict[str, Any]) -> str:
    """The extension to give the downloaded bytes.

    The media type first (it is what the uploader declared), then the url's own
    suffix, then `.glb` — the canonical published form, and the one a room's
    store is overwhelmingly full of.
    """
    media = str(record.get("media_type") or "").split(";")[0].strip().lower()
    if media in _SUFFIX_BY_MEDIA:
        return _SUFFIX_BY_MEDIA[media]
    for source in (record.get("url"), record.get("name")):
        text = str(source or "")
        if "." in text.rsplit("/", 1)[-1]:
            suffix = "." + text.rsplit(".", 1)[-1].split("?")[0].lower()
            if 2 <= len(suffix) <= 6:
                return suffix
    return ".glb"


def plan(graph: Any) -> Dict[str, Any]:
    """What could be materialised, and what could not — read only.

    Straight from the library (`geometry_summary`): the resident records with
    their binds, plus the geometry that lives elsewhere. A panel shows both
    numbers, because "3 models" when the study describes seven is a true
    sentence that misleads.
    """
    from s3dgraphy.api import geometry_summary

    return geometry_summary(graph)


def scene_digests(objects: Any = None) -> Dict[str, Any]:
    """Digest → the first object in the scene carrying it.

    The cache, read from the scene itself rather than kept in a side table: a
    .blend that was saved and reopened must still know what it holds, and a
    remembered map would not survive the file.
    """
    if objects is None:                     # pragma: no cover — needs bpy
        import bpy  # type: ignore
        objects = bpy.data.objects
    out: Dict[str, Any] = {}
    for obj in objects:
        try:
            digest = obj.get(PROP_DIGEST)
        except Exception:                   # noqa: BLE001 — an odd object is not a cache hit
            continue
        if digest and digest not in out:
            out[str(digest)] = obj
    return out


def _default_fetch(checksum: str):
    from . import room as room_cfg
    return room_cfg.get_asset(checksum)


def _default_importer(path: str):
    from ..shelf_tool.operators import _import_mesh
    return _import_mesh(path)


def _bind_objects(objects: List[Any], record: Dict[str, Any]) -> List[str]:
    """Give the imported objects the graph's own bindings, on the object side.

    Epochs go into `EM_ep_belong_ob` — the RM Manager / epoch manager convention
    the rest of the addon reads, so a materialised model behaves like one that
    was hatted by hand. Everything else (a unit, a document) is recorded as a
    property rather than acted on: renaming an imported mesh to a unit's proxy
    name would make it look like a PROXY, which is a different thing —
    geometry-without-material authored in this scene, not a published model.
    """
    epochs = [b for b in record.get("bind") or []
              if str(b.get("node_type") or "") in ("EpochNode", "epoch")]
    others = [b for b in record.get("bind") or [] if b not in epochs]
    names = [str(b.get("name") or b.get("id")) for b in epochs]
    written: List[str] = []
    for obj in objects:
        try:
            obj[PROP_DIGEST] = record["checksum"]
            obj[PROP_RESOURCE] = record["resource_id"]
            obj[PROP_CARRIER] = record["node_id"]
            if others:
                obj[PROP_BIND] = ",".join(str(b.get("id")) for b in others)
            if names and hasattr(obj, "EM_ep_belong_ob"):
                obj.EM_ep_belong_ob.clear()
                for name in names:
                    obj.EM_ep_belong_ob.add().epoch = name
                written = list(names)
        except Exception as exc:            # noqa: BLE001 — a binding that fails is SAID
            print(f"[em] could not bind {getattr(obj, 'name', '?')}: {exc}")
    # What is REPORTED is what was written, not what was intended. Measured in a
    # background Blender with the addon unregistered: `EM_ep_belong_ob` does not
    # exist there, so the epochs were named in the report while nothing on the
    # object carried them — a small lie, and exactly the kind that makes somebody
    # trust a binding that is not there.
    if names and not written:
        print(f"[em] epoch binding unavailable on this build "
              f"(EM_ep_belong_ob absent): {', '.join(names)} recorded in the "
              f"graph, not on the object")
    return written


def materialise(graph: Any, *,
                records: Optional[List[Dict[str, Any]]] = None,
                fetch: Optional[Callable[[str], Any]] = None,
                importer: Optional[Callable[[str], List[Any]]] = None,
                objects: Any = None,
                limit: Optional[int] = None) -> Dict[str, Any]:
    """Fetch and import the store-backed geometry of `graph`.

    Returns a report — never raises for one bad row, because a batch that stops
    at the first embargoed file leaves a half-materialised scene and no idea
    which half:

    ``materialised`` ``[{checksum, node_id, objects, epochs}]`` — arrived now
    ``reused``       already in the scene under that digest (nothing fetched)
    ``skipped``      ``[{checksum, node_id, reason}]`` — the honest ones: an
                     embargo (403), an asset the room does not have (404), a
                     format Blender has no importer for
    ``failed``       everything else, with the sentence the room gave
    ``elsewhere``    the count of geometry that is NOT in the store (reference)

    `fetch` / `importer` / `objects` exist so this can be measured headless: the
    Blender-only steps are the two boundaries, and the logic between them is
    plain Python.
    """
    fetch = fetch or _default_fetch
    importer = importer or _default_importer
    summary = plan(graph)
    todo = records if records is not None else summary["resident"]
    if limit is not None:
        todo = todo[:limit]
    known = scene_digests(objects)

    report: Dict[str, Any] = {
        "materialised": [], "reused": [], "skipped": [], "failed": [],
        "elsewhere": summary["counts"]["elsewhere"],
        "considered": len(todo),
    }

    for record in todo:
        checksum = str(record.get("checksum") or "")
        if not checksum:
            report["skipped"].append({**_row(record),
                                      "reason": "no checksum: nothing to fetch by"})
            continue
        hit = known.get(checksum)
        if hit is not None:
            # THE CACHE. Content-addressed, so this is not an optimisation with a
            # correctness risk: the bytes are the same bytes, by definition.
            report["reused"].append({**_row(record),
                                     "object": getattr(hit, "name", str(hit))})
            continue
        try:
            data, media = fetch(checksum)
        except Exception as exc:            # noqa: BLE001 — a refusal is a row, not a crash
            status = getattr(exc, "status", None)
            reason = _refusal(status, exc)
            bucket = "skipped" if status in (401, 403, 404) else "failed"
            report[bucket].append({**_row(record), "reason": reason})
            continue

        path = None
        try:
            suffix = _suffix_for({**record, "media_type": media or record.get("media_type")})
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                handle.write(data)
                path = handle.name
            objects_made = importer(path) or []
        except Exception as exc:            # noqa: BLE001
            report["failed"].append({**_row(record),
                                     "reason": f"import failed: {exc}"})
            continue
        finally:
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass                    # a temp file that stays is not a failure

        if not objects_made:
            report["skipped"].append({
                **_row(record),
                "reason": "Blender has no importer for these bytes "
                          f"({media or record.get('media_type') or 'unknown type'})"})
            continue

        epochs = _bind_objects(objects_made, record)
        known[checksum] = objects_made[0]   # a second row with the same bytes reuses
        intended = [str(b.get("name") or b.get("id")) for b in record.get("bind") or []
                    if str(b.get("node_type") or "") in ("EpochNode", "epoch")]
        report["materialised"].append({
            **_row(record),
            "objects": [getattr(o, "name", str(o)) for o in objects_made],
            "epochs": epochs,
            # said apart, because "the graph binds it to Fase I" and "the object
            # now carries Fase I" are two different facts
            **({"epochs_not_written": intended} if intended and not epochs else {}),
        })

    return report


def _row(record: Dict[str, Any]) -> Dict[str, Any]:
    return {"checksum": str(record.get("checksum") or ""),
            "node_id": str(record.get("node_id") or ""),
            "name": str(record.get("name") or ""),
            "kind": str(record.get("kind") or "")}


def _refusal(status: Optional[int], exc: Exception) -> str:
    """The room said no — in words, and with the right word.

    403 is the one that matters: it is not a failure, it is the **embargo gate**
    doing its job (em-server serves an embargoed asset to editor+ only). Saying
    "could not fetch" there would send somebody looking for a network problem
    that does not exist.
    """
    if status == 403:
        return ("embargoed, or this token may not have it: the room served 403. "
                "An editor of the study can materialise it")
    if status == 401:
        return "the room did not accept the token (401) — join again"
    if status == 404:
        return "the room's store does not have these bytes (404)"
    return str(exc)


def summarise(report: Dict[str, Any]) -> str:
    """One line for the status bar. Counts first, and the skips are NOT hidden
    among them: a skipped row is the thing the user has to know about."""
    parts = [f"{len(report['materialised'])} materialised"]
    if report["reused"]:
        parts.append(f"{len(report['reused'])} already here")
    if report["skipped"]:
        parts.append(f"{len(report['skipped'])} skipped")
    if report["failed"]:
        parts.append(f"{len(report['failed'])} failed")
    if report.get("elsewhere"):
        parts.append(f"{report['elsewhere']} outside the store (not fetchable)")
    return " · ".join(parts)


# ── the operator ─────────────────────────────────────────────────────────────
#
# An ACTION, not a side effect of joining. Same principle as the command channel
# (`em_accept_commands`, off by default): something that changes your scene is
# something you ask for. The toggle below lets somebody who wants it at adoption
# time say so once — which is a decision they made, not one made for them.

def _operator_classes():
    import bpy  # type: ignore

    class EM_OT_materialise_geometry(bpy.types.Operator):
        """Fetch the room's geometry into this scene.

        Only what lives in the room's store (resident) and only what this token
        may have: an embargoed model is skipped with a reason, not half-imported.
        Running it twice changes nothing — an object already carrying a digest is
        that digest's object."""

        bl_idname = "em.materialise_geometry"
        bl_label = "Materialise geometry from the store"
        bl_options = {"REGISTER", "UNDO"}

        @classmethod
        def poll(cls, context):
            from .room_session import SESSION
            return bool(getattr(SESSION, "joined", False))

        def execute(self, context):
            from ..functions import is_graph_available

            ok, graph = is_graph_available(context)
            if not ok or graph is None:
                self.report({"ERROR"},
                            "no graph in this session: adopt the room's document first")
                return {"CANCELLED"}
            try:
                report = materialise(graph)
            except Exception as exc:        # noqa: BLE001 — the reason is the user's
                self.report({"ERROR"}, f"could not materialise: {exc}")
                return {"CANCELLED"}
            for row in report["skipped"]:
                self.report({"WARNING"}, f"{row['name'] or row['node_id']}: {row['reason']}")
            for row in report["failed"]:
                self.report({"WARNING"}, f"{row['name'] or row['node_id']}: {row['reason']}")
            self.report({"INFO"}, summarise(report))
            return {"FINISHED"}

    return (EM_OT_materialise_geometry,)


_CLASSES: tuple = ()


def register():
    import bpy  # type: ignore

    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    if not hasattr(bpy.types.Scene, "em_materialise_on_adopt"):
        bpy.types.Scene.em_materialise_on_adopt = bpy.props.BoolProperty(
            name="Materialise geometry on adopt",
            default=False,
            description=(
                "When joining a room, also fetch the models it describes into "
                "this scene. Off by default: adopting a document is reading, "
                "and downloading somebody's meshes into your file is more"))


def unregister():
    import bpy  # type: ignore

    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:                   # noqa: BLE001 — unregistering must not fail
            pass
    if hasattr(bpy.types.Scene, "em_materialise_on_adopt"):
        del bpy.types.Scene.em_materialise_on_adopt
