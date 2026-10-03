"""S1 · the scene as a LOCAL CACHE of the graph — and the gesture that checks it.

MICRO-LA-BARRA-E-LE-STANZE, decided by E.D. on 3 October 2026: «la scena di
Blender è una cache locale del grafo, con un sync che la verifica». The shared
truth is graph + asset store; the .blend is the personal workbench. So the
check compares the 3D resources the graph cites with what is in the scene, and
says it in five groups, one sentence each:

* **here** — the bytes the graph cites are in the scene (an object carries
  their digest: `em_asset_sha256`, the key `materialise` writes and
  `promote_model` now writes too);
* **missing** — cited, resident in the store, not in the scene → DOWNLOADED, by
  `materialise` itself (same rules: embargo skipped with a reason, nothing
  duplicated);
* **changed** — an object holds an OLDER version of a resource: it is bound to
  the resource (`em_resource_id`) but its digest is not the one the graph cites
  now. Flagged, not overwritten: which one is right is a person's call;
* **external** — geometry the graph cites outside the store (`reference`, NAS,
  URL): counted, left where it is;
* **only here** — objects NOT linked to the graph (decorations, tests,
  non-semantic objects): marked `em_only_here = True`, listed, and NEVER
  uploaded — «Bring into a room…» promotes only graph-linked models.

What «linked to the graph» means, read off the scene and never guessed: in the
RM list (`scene.rm_list`), a proxy (its name resolves to a node of the graph
through the addon's own naming rule), or an object carrying one of the graph
bindings `materialise`/`promote_model` write. Cameras, lights and empties are
not content and are not listed.

The decision is pure (`classify_scene`), measured by `tests/test_scene_check.py`;
the Blender reading and the download sit behind `check_scene`.
"""

# NOT `from __future__ import annotations`: the operator below is built inside
# a function with `bpy` imported lazily, and Blender evaluates its property
# annotations in this module's globals (measured: «download» unrecognised).
from typing import Any, Callable, Dict, List, Optional

PROP_ONLY_HERE = "em_only_here"
#: the properties that bind an object to the graph (materialise / promote_model)
_BINDING_PROPS = ("em_asset_sha256", "em_resource_id", "em_rm_node_id",
                  "em_bound_to", "em_asset_ref", "em_asset_id")
#: object types that are CONTENT (geometry somebody could mean to publish)
GEOMETRY_TYPES = ("MESH", "CURVE", "SURFACE", "META", "FONT", "POINTCLOUD",
                  "VOLUME", "CURVES", "GREASEPENCIL", "GPENCIL")

#: The last check, for the panel. Session state, not document state.
ULTIMA_VERIFICA: Dict[str, Any] = {}


def _digest(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text and not text.startswith("sha256:"):
        text = "sha256:" + text
    return text


def classify_scene(summary: Dict[str, Any],
                   objects: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Pure: `summary` is `geometry_summary(graph)`, `objects` a list of
    `{name, type, digest, resource_id, linked}`. → the five groups."""
    by_digest: Dict[str, str] = {}
    by_resource: Dict[str, List[Dict[str, Any]]] = {}
    for obj in objects:
        if obj.get("digest"):
            by_digest.setdefault(_digest(obj["digest"]), obj["name"])
        if obj.get("resource_id"):
            by_resource.setdefault(str(obj["resource_id"]), []).append(obj)
    here, missing, changed = [], [], []
    seen = set()
    for record in summary.get("resident") or []:
        digest = _digest(record.get("checksum"))
        key = (record.get("node_id"), digest)
        if key in seen:
            continue
        seen.add(key)
        if digest and digest in by_digest:
            here.append({**record, "object": by_digest[digest]})
            continue
        older = [o for o in by_resource.get(str(record.get("resource_id")), [])
                 if o.get("digest") and _digest(o["digest"]) != digest]
        if older:
            changed.append({**record, "objects": [o["name"] for o in older],
                            "scene_digest": _digest(older[0]["digest"])})
            continue
        missing.append(record)
    only_here = sorted(o["name"] for o in objects
                       if not o.get("linked") and o.get("type") in GEOMETRY_TYPES)
    return {"here": here, "missing": missing, "changed": changed,
            "external": list(summary.get("elsewhere") or []),
            "only_here": only_here}


def sentences(report: Dict[str, Any]) -> List[str]:
    """One sentence per group — the panel and the console say the same."""
    out = [f"{len(report['here'])} model(s) of the graph are in the scene"]
    got = report.get("downloaded")
    if got is not None:
        out.append(f"{len(report['missing'])} missing: {got} downloaded"
                   + (f", {report.get('not_downloaded', 0)} not "
                      f"({report.get('why_not', '')})"
                      if report.get("not_downloaded") else ""))
    else:
        out.append(f"{len(report['missing'])} missing from the scene "
                   f"(not downloaded: check with the room to fetch them)")
    out.append(f"{len(report['changed'])} changed: the scene holds an older "
               f"version than the graph cites")
    out.append(f"{len(report['external'])} external reference(s), left where "
               f"they are")
    out.append(f"{len(report['only_here'])} object(s) only here — local, never "
               f"uploaded")
    return out


# ── Blender ──────────────────────────────────────────────────────────────────

def scene_objects(context, graph) -> List[Dict[str, Any]]:  # pragma: no cover — bpy
    """The scene read as the pure function wants it, with `linked` decided."""
    import bpy  # type: ignore
    from ..operators.addon_prefix_helpers import proxy_name_to_node_name

    rm_names = set()
    try:
        rm_names = {item.name for item in context.scene.rm_list}
    except Exception:  # noqa: BLE001 — no RM list on this scene
        pass
    finder = getattr(graph, "find_node_by_name", None)
    out = []
    for obj in bpy.data.objects:
        bound = any(obj.get(p) for p in _BINDING_PROPS)
        proxy = False
        if not bound and obj.name not in rm_names and callable(finder):
            try:
                proxy = finder(proxy_name_to_node_name(obj.name)) is not None
            except Exception:  # noqa: BLE001
                proxy = False
        out.append({"name": obj.name, "type": obj.type,
                    "digest": str(obj.get("em_asset_sha256") or ""),
                    "resource_id": str(obj.get("em_resource_id") or ""),
                    "linked": bound or proxy or obj.name in rm_names})
    return out


def mark_only_here(names: List[str]) -> None:  # pragma: no cover — bpy
    """The flag follows the fact: set on the local ones, removed from an object
    that has since become linked."""
    import bpy  # type: ignore
    wanted = set(names)
    for obj in bpy.data.objects:
        if obj.name in wanted:
            obj[PROP_ONLY_HERE] = True
        elif PROP_ONLY_HERE in obj.keys():
            del obj[PROP_ONLY_HERE]


def check_scene(context, graph, *, download: bool,
                materialise_fn: Optional[Callable[..., Dict[str, Any]]] = None,
                fetch_fn: Optional[Callable[[str], Any]] = None
                ) -> Dict[str, Any]:  # pragma: no cover — bpy
    """Read the scene, decide, mark, and (if asked and in a room) download."""
    from .materialise import materialise, plan

    summary = plan(graph)
    # A3 · an asset with versions is checked MESH BY MESH against its library
    # (asset_versions): its rows leave the per-object classification below
    versioned = [r for r in summary.get("resident") or [] if r.get("asset_id")]
    libraries = None
    if versioned:
        from . import asset_versions
        from . import room as room_cfg
        libraries = asset_versions.check_libraries(
            graph, room=room_cfg.room().get("room_id"), download=download,
            fetch=fetch_fn, summary=summary)
        summary = {**summary, "resident": [r for r in summary["resident"]
                                           if not r.get("asset_id")]}
    report = classify_scene(summary, scene_objects(context, graph))
    report["libraries"] = libraries
    mark_only_here(report["only_here"])
    if download and report["missing"]:
        fetched = (materialise_fn or materialise)(graph, records=report["missing"])
        report["downloaded"] = len(fetched["materialised"]) + len(fetched["reused"])
        skipped = fetched["skipped"] + fetched["failed"]
        report["not_downloaded"] = len(skipped)
        report["why_not"] = "; ".join(sorted({r["reason"] for r in skipped}))[:120]
        report["fetch"] = fetched
    ULTIMA_VERIFICA.clear()
    lines = sentences(report)
    if libraries is not None:
        from . import asset_versions
        lines = asset_versions.sentences(libraries) + lines
    ULTIMA_VERIFICA.update({"sentences": lines,
                            "only_here": list(report["only_here"]),
                            "changed": [r.get("name") for r in report["changed"]]})
    for line in ULTIMA_VERIFICA["sentences"]:
        print(f"[scene check] {line}")
    return report


def _operator_classes():  # pragma: no cover — bpy
    import bpy  # type: ignore

    class EM_OT_scene_check(bpy.types.Operator):
        """Check this scene against the room: download the models the graph cites
        that are not here, flag the ones that changed, count the external ones,
        and mark the objects that are only here (never uploaded)."""

        bl_idname = "em.scene_check"
        bl_label = "Check the scene against the room"
        bl_options = {"REGISTER", "UNDO"}

        download: bpy.props.BoolProperty(  # type: ignore
            name="Download what is missing", default=True,
            description="Fetch the store-backed models the graph cites and the "
                        "scene does not have (needs a room)")

        def execute(self, context):
            from ..functions import is_graph_available
            from .room_session import SESSION

            ok, graph = is_graph_available(context)
            if not ok or graph is None:
                self.report({"ERROR"}, "no graph loaded: nothing to check the "
                                       "scene against")
                return {"CANCELLED"}
            try:
                check_scene(context, graph,
                            download=bool(self.download and SESSION.joined))
            except Exception as exc:  # noqa: BLE001 — the reason is the user's
                self.report({"ERROR"}, f"could not check the scene: {exc}")
                return {"CANCELLED"}
            for line in ULTIMA_VERIFICA["sentences"]:
                self.report({"INFO"}, line)
            return {"FINISHED"}

    return (EM_OT_scene_check,)


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


def draw(layout) -> None:  # pragma: no cover — bpy
    """The block in the room section of the Sync panel."""
    box = layout.box()
    box.operator("em.scene_check", icon="VIEWZOOM")
    for line in ULTIMA_VERIFICA.get("sentences") or []:
        box.label(text=line[:90], icon="BLANK1")
    names = ULTIMA_VERIFICA.get("only_here") or []
    if names:
        box.label(text="Only here: " + ", ".join(names[:6])
                  + (f" … +{len(names) - 6}" if len(names) > 6 else ""),
                  icon="HIDE_OFF")
