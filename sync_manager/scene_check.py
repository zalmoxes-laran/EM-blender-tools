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


def keep_resident_from_before(summary: Dict[str, Any],
                              objects: List[Dict[str, Any]]) -> int:
    """Pure: the reality-based records that R1 sends to a library but whose
    bytes the scene already holds as a resident object stay resident. → how
    many."""
    held = {_digest(o["digest"]) for o in objects if o.get("digest")}
    by_res = {str(o.get("resource_id")) for o in objects if o.get("resource_id")}
    kept = 0
    for row in summary.get("resident") or []:
        if row.get("residence") != "library" or row.get("origin") != "reality_based":
            continue
        if row.get("asset_id") != row.get("resource_id"):
            continue                    # a real asset with versions: its library
        if _digest(row.get("checksum")) in held or str(row.get("resource_id")) in by_res:
            row.pop("asset_id", None)
            row["residence"] = "resident"
            row["kept_resident"] = True
            kept += 1
    return kept


def sentences(report: Dict[str, Any]) -> List[str]:
    """One sentence per group — the panel and the console say the same."""
    # Q9 · said for what it MEASURES: the models whose file the graph cites (a
    # resident resource with its sha256), matched by digest. Measured on Templu
    # Mare: «0 model(s) of the graph are in the scene» with 99 RMs in the list
    # and the containers full — none of them had a published file yet.
    out = [f"{len(report['here'])} model(s) with a file in the graph are in the "
           f"scene (matched by sha256)"]
    rm = report.get("rm")
    if rm:
        out.append(f"RMs: {rm['in_scene']} in the scene, {rm['in_graph']} in the graph"
                   + (f" ({rm['in_scene'] - rm['bound']} not in it — a GraphML "
                      f"carries no models)" if rm["in_scene"] > rm["bound"] else ""))
    got = report.get("downloaded")
    if got is not None:
        out.append(f"{len(report['missing'])} missing: {got} downloaded"
                   + (f", {report.get('not_downloaded', 0)} not "
                      f"({report.get('why_not', '')})"
                      if report.get("not_downloaded") else ""))
    elif not report.get("missing"):
        out.append("nothing missing from the scene")
    else:
        # V1 · never «not downloaded» without why: the reason is the room's
        out.append(f"{len(report['missing'])} missing from the scene "
                   f"(not downloaded: "
                   f"{report.get('no_room') or 'Sync downloads them in a room'})")
    out.append(f"{len(report['changed'])} changed: the scene holds an older "
               f"version than the graph cites")
    out.append(f"{len(report['external'])} external reference(s), left where "
               f"they are")
    out.append(f"{len(report['only_here'])} object(s) only here — local, never "
               f"uploaded")
    return out


def only_here_line(names: List[str]) -> Optional[tuple]:
    """I1 · ``(icon, text)`` of the objects only here, with the sign of the
    one list (``scene.only_here`` ◆), or None when there are none."""
    if not names:
        return None
    try:
        from ..state_symbols import ICONS, glyph
    except ImportError:          # loaded by path, outside the package (the suite)
        from state_symbols import ICONS, glyph  # type: ignore
    return (ICONS["scene.only_here"],
            f"{glyph('scene.only_here')} Only here: " + ", ".join(names[:6])
            + (f" … +{len(names) - 6}" if len(names) > 6 else ""))


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


def count_rms(context, graph) -> Dict[str, int]:  # pragma: no cover — bpy
    """Q9 · the RMs counted apart: in the scene (the RM list, or an
    `em_rm_node_id`), in the graph, and how many of the scene's the graph has."""
    import bpy  # type: ignore
    ids = {str(n.node_id) for n in getattr(graph, "nodes", [])
           if getattr(n, "node_type", "") == "representation_model"}
    names = set()
    try:
        names = {item.name for item in context.scene.rm_list}
    except Exception:  # noqa: BLE001
        pass
    scene = [o for o in bpy.data.objects
             if o.name in names or o.get("em_rm_node_id")]
    bound = sum(1 for o in scene if str(o.get("em_rm_node_id") or "") in ids)
    return {"in_scene": len(scene), "in_graph": len(ids), "bound": bound}


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


def ensure_room(context) -> tuple:  # pragma: no cover — bpy
    """V1 · Sync outside the room reconnects by itself. → `(joined, why)`:
    `why` is the one sentence that says why nothing was downloaded."""
    import bpy  # type: ignore
    from . import operators as ops
    session = ops.current_session(context)
    if session.joined:
        return True, ""
    saved = ops.saved_room(context)
    room_id = saved.get("room_id") or (session.room_id if session.seated else "")
    if not room_id:
        return False, ("this study is in no room on this computer: the models "
                       "the graph cites come with a room")
    try:
        bpy.ops.em.room_reconnect()
    except Exception as exc:  # noqa: BLE001 — said below
        print(f"[sync] reconnecting to {room_id} failed: {exc}")
    if ops.current_session(context).joined:
        return True, ""
    from . import signin_ui
    running = signin_ui.PENDING.get("signin")
    if running is not None and running.state == "waiting":
        return False, (f"not connected to {room_id} yet: sign in in the browser, "
                       f"then Sync again")
    return False, (f"not connected to {room_id}, and reconnecting did not "
                   f"succeed: Reconnect, then Sync downloads them")


def check_scene(context, graph, *, download: bool,
                materialise_fn: Optional[Callable[..., Dict[str, Any]]] = None,
                fetch_fn: Optional[Callable[[str], Any]] = None,
                no_room: str = ""
                ) -> Dict[str, Any]:  # pragma: no cover — bpy
    """Read the scene, decide, mark, and (if asked and in a room) download.
    `no_room` is why nothing could be downloaded (V1), said in the sentences."""
    from .materialise import materialise, plan

    summary = plan(graph)
    # R1 · a reality-based model already RESIDENT here from before is left as
    # it is (turning somebody's object into a link is not a check's to do):
    # counted and said; the next one that arrives goes into a library
    kept = keep_resident_from_before(summary, scene_objects(context, graph))
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
    report["rm"] = count_rms(context, graph)
    report["no_room"] = no_room
    mark_only_here(report["only_here"])
    if download and report["missing"]:
        fetched = (materialise_fn or materialise)(graph, records=report["missing"])
        report["downloaded"] = len(fetched["materialised"]) + len(fetched["reused"])
        skipped = fetched["skipped"] + fetched["failed"]
        report["not_downloaded"] = len(skipped)
        report["why_not"] = "; ".join(sorted({r["reason"] for r in skipped}))[:120]
        report["fetch"] = fetched
    ULTIMA_VERIFICA.clear()
    # V3 · what the node holds and this scene does not, after this check: the
    # panel offers «Download the geometry now» while it is more than zero
    ULTIMA_VERIFICA["missing_left"] = (len(report.get("missing") or [])
                                       - int(report.get("downloaded") or 0))
    lines = sentences(report)
    from .residence import sentence as origin_sentence
    said = origin_sentence(summary.get("origins") or {})
    if said:
        lines.append(said + (f" · {kept} reality-based resident from before, left "
                             f"as they are" if kept else ""))
    report["origins"] = summary.get("origins") or {}
    report["kept_resident"] = kept
    # R1 · the files of the graph through the ONE resolver: the same states
    # EMStudio and StratiField give for the same files
    try:
        from . import file_states
        lines.append(file_states.sentence(file_states.resolve_active(context, graph)))
    except Exception as exc:  # noqa: BLE001 — the check stands without it
        lines.append(f"Files: not resolved ({exc})")
    if libraries is not None:
        from . import asset_versions
        lines = asset_versions.sentences(libraries) + lines
    ULTIMA_VERIFICA.update({"sentences": lines,
                            "only_here": list(report["only_here"]),
                            "changed": [r.get("name") for r in report["changed"]]})
    for line in ULTIMA_VERIFICA["sentences"]:
        print(f"[scene check] {line}")
    return report


def counts_line(report: Dict[str, Any], at: str = "") -> str:
    """P2 · the scene's counts in one line, with the signs of the one list:
    «◉ N here · ✕ missing · ≠ changed · ↗ references · ◆ only here · checked
    hh:mm». `changed` counts both directions: older here than the graph, and
    edited here and not yet sent."""
    edited = int(report.get("edited") or 0)
    # what Sync just downloaded is here now (measured: «◉ 0 here» after 66
    # had arrived)
    here = len(report.get('here') or []) + int(report.get("downloaded") or 0)
    parts = [f"◉ {here} here",
             f"✕ {len(report.get('missing') or []) - int(report.get('downloaded') or 0)} missing",
             f"≠ {len(report.get('changed') or []) + edited} changed",
             f"↗ {len(report.get('external') or [])} references",
             f"◆ {len(report.get('only_here') or [])} only here"]
    return " · ".join(parts) + (f" · checked {at}" if at else "")


def tally_of(report: Dict[str, Any], at: str = "") -> Dict[str, Any]:
    """P1 · the same counts as numbers, for the one word of «Where you work»
    (`where.scene_status`): what `counts_line` writes, before it is a line."""
    downloaded = int(report.get("downloaded") or 0)
    return {"here": len(report.get("here") or []) + downloaded,
            "missing": len(report.get("missing") or []) - downloaded,
            "changed": len(report.get("changed") or []) + int(report.get("edited") or 0),
            "external": len(report.get("external") or []),
            "only_here": len(report.get("only_here") or []),
            "at": at}


def _operator_classes():  # pragma: no cover — bpy
    import bpy  # type: ignore

    class EM_PG_sync_row(bpy.types.PropertyGroup):
        """P2 · one model the scene could send: ticked = it goes."""
        object: bpy.props.StringProperty()  # type: ignore
        target: bpy.props.StringProperty()  # type: ignore
        kind: bpy.props.StringProperty()  # type: ignore
        state: bpy.props.StringProperty()  # type: ignore
        size: bpy.props.IntProperty()  # type: ignore
        send: bpy.props.BoolProperty(name="Send", default=False)  # type: ignore

    class EM_OT_scene_check(bpy.types.Operator):
        """Sync the scene with the room: download the proxies and the models
        the graph cites that are not here (what «Materialise geometry» did),
        check the files, and offer to send the models linked to the graph that
        changed here or are new (a changed one goes as a new revision of its
        resource). Outside the room it reconnects first. Objects only here
        never go"""

        bl_idname = "em.scene_check"
        bl_label = "Sync the scene…"
        bl_options = {"REGISTER", "UNDO"}

        download: bpy.props.BoolProperty(  # type: ignore
            name="Download what is missing", default=True,
            description="Fetch the store-backed models the graph cites and the "
                        "scene does not have (needs a room)")
        send: bpy.props.EnumProperty(  # type: ignore
            name="Send",
            items=(("ASK", "Ask", "Tick the models to send in the dialog"),
                   ("CHANGED", "The changed ones",
                    "Send the models changed here (what the dialog ticks for you)"),
                   ("CHANGED_AND_NEW", "Changed and new",
                    "Send the changed models and the new ones"),
                   ("NONE", "Nothing", "Only check and download")),
            default="NONE",
            description="Without the dialog, nothing is sent unless you say so")

        def _graph(self, context):
            from ..functions import is_graph_available
            ok, graph = is_graph_available(context)
            return graph if ok else None

        def _check(self, context, graph):
            from . import operators as ops
            from . import scene_sync
            import time
            joined, why = (True, "")
            if self.download:
                joined, why = ensure_room(context)
            SESSION = ops.current_session(context)
            report = check_scene(context, graph,
                                 download=bool(self.download and joined),
                                 no_room=why)
            if why:
                ULTIMA_VERIFICA["no_room"] = why
            groups = scene_sync.candidates(context, graph) if SESSION.seated else {
                "changed": [], "new": [], "baseline": [], "skipped": []}
            report["edited"] = len(groups["changed"])
            ULTIMA_VERIFICA["counts"] = counts_line(report, time.strftime("%H:%M"))
            ULTIMA_VERIFICA["tally"] = tally_of(report, time.strftime("%H:%M"))
            ULTIMA_VERIFICA["baseline"] = len(groups["baseline"])
            return report, groups

        def _fill(self, context, groups):
            rows = context.window_manager.em_sync_rows
            rows.clear()
            for state in ("changed", "new"):
                for m in groups[state]:
                    row = rows.add()
                    row.object, row.target = m["object"], m["target"]
                    row.kind, row.state = str(m.get("kind") or ""), m["state"]
                    row.size = int(m.get("size") or 0)
                    row.send = state == "changed"
            return rows

        def _graph_or_say(self, context):
            """V1 · a file reopened in its room has no graph until the room
            is entered: Sync reconnects first, and says why when it cannot."""
            why = ""
            if self.download:
                _joined, why = ensure_room(context)
            graph = self._graph(context)
            if graph is None:
                self.report({"ERROR"}, "no graph loaded: nothing to sync the scene with"
                            + (f" ({why})" if why else ""))
                if why:
                    ULTIMA_VERIFICA.clear()
                    ULTIMA_VERIFICA["sentences"] = [f"nothing synced: {why}"]
                    ULTIMA_VERIFICA["no_room"] = why
            return graph

        def invoke(self, context, event):
            graph = self._graph_or_say(context)
            if graph is None:
                return {"CANCELLED"}
            try:
                _report, groups = self._check(context, graph)
            except Exception as exc:  # noqa: BLE001 — the reason is the user's
                self.report({"ERROR"}, f"could not check the scene: {exc}")
                return {"CANCELLED"}
            rows = self._fill(context, groups)
            if not len(rows):
                for line in ULTIMA_VERIFICA.get("sentences") or []:
                    self.report({"INFO"}, line)
                self.report({"INFO"}, "nothing here to send to the room")
                return {"FINISHED"}
            self.send = "ASK"
            return context.window_manager.invoke_props_dialog(self, width=560)

        def draw(self, context):
            layout = self.layout
            layout.label(text=ULTIMA_VERIFICA.get("counts") or "", icon="VIEWZOOM")
            # V3 · where «Materialise geometry» went: said where it is done
            layout.label(text="The proxies and models missing here were downloaded "
                              "from the room.", icon="IMPORT")
            rows = context.window_manager.em_sync_rows
            from .scene_sync import human_size
            layout.label(text="Linked to the graph, not yet in the room as they are here:")
            col = layout.column(align=True)
            for row in rows:
                line = col.row(align=True)
                line.prop(row, "send", text="")
                sign = "≠" if row.state == "changed" else "+"
                what = ("changed here — goes as a new revision"
                        if row.state == "changed" else "new")
                line.label(text=f"{sign} {row.object} ({row.kind}) · ≈ "
                                f"{human_size(row.size)} · {what}")
            layout.label(text="Objects only here never go.", icon="INFO")

        def execute(self, context):
            from . import scene_sync
            graph = (self._graph(context) if self.send == "ASK"
                     else self._graph_or_say(context))
            if graph is None:
                if self.send == "ASK":
                    self.report({"ERROR"}, "no graph loaded: nothing to sync the scene with")
                return {"CANCELLED"}
            if self.send == "ASK":
                rows = context.window_manager.em_sync_rows
                chosen = [{"object": r.object, "target": r.target, "kind": r.kind,
                           "state": r.state} for r in rows if r.send]
            else:
                try:
                    _report, groups = self._check(context, graph)
                except Exception as exc:  # noqa: BLE001
                    self.report({"ERROR"}, f"could not check the scene: {exc}")
                    return {"CANCELLED"}
                self._fill(context, groups)
                chosen = (groups["changed"] if self.send in ("CHANGED", "CHANGED_AND_NEW")
                          else []) + (groups["new"] if self.send == "CHANGED_AND_NEW" else [])
            if chosen:
                from . import operators as ops
                if not ops.current_session(context).seated:
                    self.report({"ERROR"}, "not in a room: there is nowhere to send to")
                    return {"CANCELLED"}
                done = scene_sync.send(context, graph, chosen)
                self.report({"INFO"}, (f"sent {len(done['sent'])} model(s), "
                                       f"{scene_sync.human_size(done['size'])}, "
                                       f"{done['ops']} change(s) to the room")
                            + (f" · {len(done['failed'])} not: {done['failed'][0]}"
                               if done["failed"] else ""))
                # …and the scene checked again, so the counts are the new ones
                self.download = False
                try:
                    self._check(context, graph)
                except Exception as exc:  # noqa: BLE001
                    print(f"[sync] the check after sending did not run: {exc}")
                ULTIMA_VERIFICA["sent"] = done
            for line in ULTIMA_VERIFICA.get("sentences") or []:
                self.report({"INFO"}, line)
            if ULTIMA_VERIFICA.get("counts"):
                self.report({"INFO"}, ULTIMA_VERIFICA["counts"])
            return {"FINISHED"}

    return (EM_PG_sync_row, EM_OT_scene_check)


_CLASSES: tuple = ()


def register():  # pragma: no cover — bpy
    import bpy  # type: ignore
    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.em_sync_rows = bpy.props.CollectionProperty(
        type=_CLASSES[0])


def unregister():  # pragma: no cover — bpy
    import bpy  # type: ignore
    if hasattr(bpy.types.WindowManager, "em_sync_rows"):
        del bpy.types.WindowManager.em_sync_rows
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass


def draw(layout) -> None:  # pragma: no cover — bpy
    """In a room: the scene's counts, and Sync the scene…"""
    if ULTIMA_VERIFICA.get("counts"):
        layout.label(text=ULTIMA_VERIFICA["counts"])
    layout.operator("em.scene_check", text="Sync the scene…", icon="FILE_REFRESH")
