"""P3 · «Bring into a room…» from Blender — the dialog around ONE engine.

MICRO-LA-BARRA-E-LE-STANZE, then MICRO-BRING-CHIAMA-IL-MOTORE (15 Oct 2026):
the gesture is s3Dgraphy's room importer (`s3dgraphy.room_import`, E.D.: «un
motore, tre porte» — the command, EMStudio, EM Tools). What stays HERE is what
only Blender has: the study as the scene holds it (`study.study_of`), the
dialog that collects the person's choices, the SCENE's models exported and
published (`commands.promote_model`), entering the room, and the people.

The order, the engine's: node + name → the room is created with you as its
owner, born with the study's sections (`engine.prepare`, before any question
about its files) → the PLAN: every resource and every file of a set, in five
groups (found here / already in the room / at home in another room / external
/ missing) → the person chooses (upload by default / leave as reference /
skip, per group, per batch, per item; «Move here»; the proposed lots) → the
files go up once (HEAD by sha256 first) and their resources become hosted
keeping their path → the scene's models are published (the engine's
`before_seed` hook: `residency: resident`, never an object «only here») → the
graph is seated, LAST, in one seeding → Blender ENTERS the room by itself
(D-B) → the report: uploaded N (size), references M, missing K, the room's
link. A `.blend` snapshot is OFFERED at the end (`em.blend_backup_archive`),
never taken silently.

**A second «Bring into a room» uploads nothing**: the HEAD says the room has
every file, and the engine's journal sends only the operations that changed.

**A file lives in one room (F1).** A file the node already keeps in ANOTHER
room is listed apart: the dialog names the rooms it would leave and the rooms
whose graphs cite it, and «Move here» happens only if the person ticks it.
Unticked, the engine's default (`elsewhere="host"`, measured on Templu Mare:
the Space loads only what is resident): hosted at THIS room's address, its
home unchanged — nobody moves anything without a yes.

**Lots are proposed (L1).** Photos of one session (same camera, EXIF times at
most 30 min apart, at least 5) are proposed as a lot; a D.nn document or the
DosCo never is. Only a ticked proposal becomes one acquisition.
"""

# NOT `from __future__ import annotations`: the PropertyGroup below is built
# inside a function, and Blender evaluates its annotations in the module's
# globals, where `bpy` is imported lazily — a string annotation would not
# resolve (measured: «name 'bpy' is not defined» at register).
import os
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional

from s3dgraphy.room_import import engine, inventory
from s3dgraphy.room_import import node as nodeio

from . import room as room_cfg

try:
    from ..functions import em_log
except Exception:  # noqa: BLE001 — outside the addon (tests)
    def em_log(message, *_a, **_k):
        print(message)

#: The last gesture, in memory, between the inventory dialog and the upload:
#: the engine's run (`run`), its rows, the proposed lots, the F1 views.
STATE: Dict[str, Any] = {}
#: The last report, for the panel.
ULTIMO_REFERTO: Dict[str, Any] = {}


def _active_entry(context):
    try:
        em_tools = context.scene.em_tools
        idx = em_tools.active_file_index
        if 0 <= idx < len(em_tools.graphml_files):
            return em_tools.graphml_files[idx]
    except Exception:  # noqa: BLE001
        pass
    return None


def base_dirs(context) -> List[str]:
    """Where a relative path of this project is looked for: the em.json/GraphML's
    folder, the DosCo folder, the .blend's folder. The em.json's folder first:
    a study's paths are relative to it (the engine's `base_dir`)."""
    import bpy  # type: ignore
    out = []
    entry = _active_entry(context)
    if entry is not None:
        for raw in (getattr(entry, "graphml_path", ""), getattr(entry, "dosco_dir", "")):
            if not raw:
                continue
            path = bpy.path.abspath(raw)
            out.append(path if os.path.isdir(path) else os.path.dirname(path))
        # the DosCo of the auxiliary files (where the legacy `dosco_dir` went)
        for aux in getattr(entry, "auxiliary_files", ()):
            if getattr(aux, "file_type", "") == "dosco" and aux.dosco_folder:
                out.append(bpy.path.abspath(aux.dosco_folder))
    if bpy.data.filepath:
        out.append(os.path.dirname(bpy.data.filepath))
    return list(dict.fromkeys(p for p in out if p))


def journal_path(study: Dict[str, Any]) -> str:
    """Where the engine keeps its journal (and writes its report): beside the
    study's em.json, as the command does; else beside the .blend; else in
    Blender's temporary folder."""
    folder = os.path.dirname(study.get("path") or "")
    if not folder:
        try:
            import bpy  # type: ignore
            folder = os.path.dirname(bpy.data.filepath or "") or bpy.app.tempdir
        except Exception:  # noqa: BLE001 — outside Blender
            folder = ""
    return os.path.join(folder or tempfile.gettempdir(), engine.JOURNAL_NAME)


def lot_thresholds(context) -> tuple:
    """D3 · (gap in seconds, minimum photos) of the photo lot, from the add-on
    preferences; the defaults (30 min, 5) when there are none."""
    try:
        pkg = __package__.rsplit(".", 1)[0]
        prefs = context.preferences.addons[pkg].preferences
        gap = int(getattr(prefs, "lot_gap_minutes", 30) or 30)
        least = int(getattr(prefs, "lot_min_photos", 5) or 5)
    except Exception:  # noqa: BLE001 — no prefs (tests, CLI): the defaults
        gap, least = 30, 5
    return float(max(gap, 1) * 60), max(least, 2)


def dosco_dirs(context) -> List[str]:
    """L1 · the DosCo folder of the active graph: documentation, never a lot."""
    import bpy  # type: ignore
    entry = _active_entry(context)
    raw = getattr(entry, "dosco_dir", "") if entry is not None else ""
    return [bpy.path.abspath(raw)] if raw else []


def container_of(study: Dict[str, Any]):
    """The study as the engine takes it: the scene's LIVE graphs (rewritten in
    place when their files are hosted), the file's shelf. The DTC corpus stays
    out, as in the engine: on a node the documentation register is the
    node's own."""
    from s3dgraphy.container import Container
    return Container(graphs=dict(study.get("graphs") or {}), shelf=study.get("shelf"),
                     active_graph_id=study.get("active") or None,
                     header=dict(study.get("header") or {}))


def prepare(context, graph, *, base: str, name: str, token: Optional[str]
            ) -> Dict[str, Any]:
    """The first half: the room, then the plan (`engine.prepare`). Nothing is
    uploaded yet.

    S1 · the room is built around the STUDY (`study.study_of`): born with all
    its sections, and the plan is of all its graphs, each row naming the graph
    it is in."""
    from . import exif_lite
    from . import study as study_mod
    the_study = study_mod.study_of(context, graph)
    room_id = nodeio.room_id_from_name(name)
    if not room_id:
        raise room_cfg.RoomError(f"«{name}» has no letters or digits to make a room "
                                 f"id from: choose another name")
    run = engine.prepare(container=container_of(the_study), base_dirs=base_dirs(context),
                         node=base, room=room_id, title=name, token=token,
                         journal_path=journal_path(the_study))
    where = dict(run["where"], title=run["title"])
    room_cfg.set_room(base, room_id, token)
    rows = run["plan"]["rows"]
    gap, least = lot_thresholds(context)
    lots = []
    for gid in the_study["graphs"]:
        for lot in inventory.propose_sessions([r for r in rows if r.get("graph_id") == gid],
                                              exif_of=exif_lite.photo_exif,
                                              dosco_dirs=dosco_dirs(context),
                                              gap_seconds=gap, min_photos=least):
            lot["graph_id"] = gid
            lot["source"] = "EMtools · bring into a room"
            lots.append(lot)
    # F1 · for every file at home elsewhere, the node's answer BEFORE the yes
    views = {r["id"]: nodeio.asset_home_view(base, room_id, r["sha256"], token)
             for r in rows if r["group"] == inventory.GROUP_ELSEWHERE and r.get("sha256")}
    STATE.clear()
    STATE.update({"base": base, "room_id": room_id, "where": where, "run": run,
                  "rows": rows, "lots": lots, "move_views": views,
                  "graph_id": str(getattr(graph, "graph_id", "")),
                  "study": the_study})
    return STATE


def graph_of_row(row: Dict[str, Any], default: Any) -> Any:
    """S1 · the graph of the study a row of the inventory is in."""
    study = STATE.get("study") or {}
    return (study.get("graphs") or {}).get(row.get("graph_id")) or default


def scene_models(context, graph) -> List[Dict[str, str]]:
    """The scene models linked to the graph: RMs (the RM list) and proxies.
    Never an object marked «only here». → `[{object, target}]`."""
    import bpy  # type: ignore
    from . import commands
    from .scene_check import PROP_ONLY_HERE

    out, seen = [], set()
    for item in getattr(context.scene, "rm_list", []) or []:
        obj = bpy.data.objects.get(item.name)
        node_id = getattr(item, "node_id", "") or ""
        if obj is None or not node_id or graph.find_node_by_id(node_id) is None:
            continue
        if obj.get(PROP_ONLY_HERE) or obj.name in seen:
            continue
        seen.add(obj.name)
        out.append({"object": obj.name, "target": node_id, "kind": "RM"})
    for unit_id in commands.scene_proxy_units(context, graph):
        node = graph.find_node_by_id(unit_id)
        obj = commands._proxy_object_for(node.name, context, graph) if node else None
        if obj is None or obj.get(PROP_ONLY_HERE) or obj.name in seen:
            continue
        seen.add(obj.name)
        out.append({"object": obj.name, "target": unit_id, "kind": "proxy"})
    return out


def _already_published(obj, graph) -> bool:
    """The object's bytes are already the resident resource the graph cites."""
    rid, digest = obj.get("em_resource_id"), obj.get("em_asset_sha256")
    node = graph.find_node_by_id(str(rid)) if rid else None
    data = getattr(node, "data", None) or {}
    return bool(digest and data.get("residency") == "resident"
                and str(data.get("checksum") or "") == str(digest))


def _fill_proxy_chain(graph, unit_id: str, info: Dict[str, Any]) -> Optional[str]:
    """G2 · a unit's proxy just published: its chain's resource
    (`proxies/<US>.glb`, a placeholder until the Heriverse export names a file)
    becomes those bytes in the room's store. Measured on 4 Oct 2026: the room
    born from Templu Mare listed the 66 placeholders as «missing» beside the 66
    proxies it had just published, and EMStudio's Models sheet read the
    placeholders. A resource that already has its bytes is not touched.
    → the resource's id when it was filled (no longer missing)."""
    try:
        from ..proxy_chain import glb_proxy
    except ImportError:
        return None
    _shape, resource = glb_proxy(graph, unit_id)
    data = getattr(resource, "data", None) if resource is not None else None
    if resource is None or (isinstance(data, dict) and data.get("checksum")):
        return None
    inventory.make_store_backed(resource, url=room_cfg.asset_url(info["ref"]),
                                sha256=info["ref"])
    return resource.node_id


def publish_scene(context, study_graphs: Dict[str, Any]) -> Dict[str, Any]:
    """The engine's `before_seed` hook: the SCENE's models (RM, proxy) exported
    and published into the room (`promote_model`, `residency: resident`), after
    the files are hosted and before the graph is seated — so they are in the
    one seeding. → the counts the engine adds to its report."""
    import bpy  # type: ignore
    from . import commands
    out: Dict[str, Any] = {"uploaded": 0, "bytes": 0, "already": 0, "failed": [],
                           "filled": [], "models": []}
    seen_objects = set()
    for member in study_graphs.values():
        for model in scene_models(context, member):
            obj = bpy.data.objects.get(model["object"])
            if obj is None or obj.name in seen_objects:
                continue
            seen_objects.add(obj.name)
            if _already_published(obj, member):
                out["already"] += 1
                continue
            try:
                result = commands.promote_model(
                    model["target"], {"object": obj.name, "residency": "resident"},
                    context, member)
            except Exception as exc:  # noqa: BLE001 — one model is one row, not the batch
                # measured on 15 Oct 2026 (GreatTemple_2026_v2.blend): «Object
                # 'Architrave_1_BAKE_SM_…' cannot be selected because it is not
                # in View Layer» stopped the whole gesture before the seeding
                result = {"ok": False, "error": str(exc)}
            if not result.get("ok"):
                out["failed"].append(f"{model['object']}: {result.get('error')}")
                continue
            info = result["info"]
            if model.get("kind") == "proxy":
                filled = _fill_proxy_chain(member, model["target"], info)
                if filled:
                    out["filled"].append(filled)
            if info.get("stored"):
                out["models"].append(info["object"])
                out["uploaded"] += 1
                out["bytes"] += int(info.get("size") or 0)
            else:
                # X2 · the node had these bytes: published, not uploaded
                out["already"] += 1
    return out


def upload_phrase(uploaded: int, size: int, already: int) -> str:
    """X2 · what travelled and what was already there, counted apart.

    Measured on 4 Oct 2026: «uploaded 66 (0 B)» for 66 models the node already
    held — nothing had been uploaded."""
    if not uploaded:
        return (f"{already} already on the node, nothing uploaded" if already
                else "nothing uploaded")
    said = f"uploaded {uploaded} ({inventory.human_size(size)})"
    return said + (f", {already} already on the node" if already else "")


def execute(context, graph, *, token: Optional[str], promote: bool = True,
            progress: Optional[Callable[[str, int, int], None]] = None
            ) -> Dict[str, Any]:
    """The second half (`engine.execute`, with the person's choices): upload,
    publish the scene models, seat the graph; then Blender enters the room."""
    from . import operators as ops

    run = STATE["run"]
    base, room_id, rows = STATE["base"], STATE["room_id"], STATE["rows"]
    where = STATE["where"]
    started = time.time()
    study_graphs = dict((STATE.get("study") or {}).get("graphs") or {}) or \
        {str(getattr(graph, "graph_id", "")): graph}
    plan = inventory.move_plan(rows, STATE.get("move_views") or {})
    move = [r["id"] for r in plan["movable"]] if STATE.get("move_yes") else []
    if STATE.get("move_yes"):
        for b in plan["blocked"]:
            em_log(f"[bring] {b['row']['name']} stays in {b['row'].get('home')}: {b['why']}")
    scene: Dict[str, Any] = {}

    def before_seed(_info):
        scene.update(publish_scene(context, study_graphs))
        # what the plan found missing and the scene has just given bytes to
        # (a proxy's chain resource, `proxies/<US>.glb`: `promote_model` writes
        # its digest itself) is no longer missing. Measured on 15 Oct 2026 on
        # Templu Mare: 66 proxies published, 0 «filled» by `_fill_proxy_chain`
        # (their resource already had its digest), 66 still said missing
        filled = set(scene.get("filled") or [])
        for row in rows:
            if row["group"] != inventory.GROUP_MISSING or row["id"] in filled:
                continue
            res = graph_of_row(row, graph).find_node_by_id(row["id"])
            data = getattr(res, "data", None) or {}
            if data.get("checksum") and data.get("residency") == "resident":
                filled.add(row["id"])
        scene["filled"] = sorted(filled)
        return scene

    visibility = (STATE.get("access") or {}).get("visibility") or "restricted"
    done = engine.execute(run, visibility=visibility, move=move,
                          lots=[lot for lot in STATE.get("lots") or [] if lot.get("confirmed")],
                          before_seed=before_seed if promote else None,
                          progress=progress)

    # D-B · Blender ENTERS the room by itself. Not adopting: the room's graph is
    # the one we just seated from this very session.
    from .room_session import SESSION
    joined = {"ok": SESSION.joined and SESSION.room_id == room_id,
              "message": "already in the room"}
    if not joined["ok"]:
        if SESSION.joined:
            ops.leave_room()
        joined = ops.join_room(context, base, room_id, token or "", adopt=False)
    born = list(where.get("born_with") or [])
    if joined.get("ok") and born:
        # S1 · ONE SESSION FOR THE STUDY: every graph of it is bound to this
        # room and named in the operations («Writing in: <graph>»)
        from .room_session import SESSION as _joined
        front = str(STATE.get("graph_id") or "")
        ids = sorted((g for g in study_graphs if g in born), key=lambda g: g != front)
        ops._lega_grafo_alla_stanza(
            context, _joined, {"graphs": {g: {"graph_id": g} for g in ids}},
            base, room_id, token)
    if joined.get("ok"):
        from . import study as study_mod
        study_mod.mark_room(STATE.get("study") or {}, base, room_id)
        from . import where as _where
        _where.ROOM_TITLES[room_id] = str(where.get("title") or room_id)

    others = 0
    try:
        others = sum(1 for r in context.scene.em_tools.graphml_files
                     if r.name not in study_graphs)
    except Exception:  # noqa: BLE001
        pass
    seeded = done.get("seeded") or {}
    moved = int((done.get("rewritten") or {}).get("moved_here") or 0)
    report = {
        "room_id": room_id, "link": done.get("link") or "", "created": where["created"],
        "uploaded": done["uploaded"]["files"], "uploaded_size": done["uploaded"]["bytes"],
        "already": done["already"]["files"], "moved": moved,
        "lots": done.get("lots") or [],
        "references": done["references"], "missing": done["plan"]["missing"],
        "models": scene.get("models") or [], "failed": list(done.get("failed") or []),
        "ops_applied": int(seeded.get("applied") or 0),
        "ops_refused": int(seeded.get("refused") or 0),
        # the graphs whose operations went this time (none, a second time)
        "seeded_graphs": list(seeded.get("graphs") or []),
        "study_graphs": list(study_graphs), "born_with": born,
        "joined": bool(joined.get("ok")), "join_message": joined.get("message"),
        "other_graphs": others, "seconds": round(time.time() - started, 1),
        "note": where.get("note") or "", "engine": done,
    }
    report["sentence"] = (
        upload_phrase(report["uploaded"], report["uploaded_size"], report["already"]) + ", "
        + (f"moved here {moved}, " if moved else "")
        + f"references {report['references']}, missing {report['missing']} — "
        + f"room {room_id}: {report['link']}")
    ULTIMO_REFERTO.clear()
    ULTIMO_REFERTO.update(report)
    print(f"[bring] {report['sentence']}")
    for line in inventory.sentences(inventory.summarise(rows)):
        print(f"[bring]   {line}")
    print(f"[bring]   the study: {len(born)} graph(s) in the room ({', '.join(born)}); "
          f"operations {seeded.get('sent', 0)} sent, {report['ops_applied']} applied, "
          f"{seeded.get('not_news', 0)} already there")
    if others:
        print(f"[bring]   {others} graph(s) of this scene belong to other studies "
              f"and stay here")
    for line in report["failed"]:
        print(f"[bring]   FAILED {line}")
    for path in done.get("report_files") or []:
        print(f"[bring]   report: {path}")
    return report


def apply_access(*, token: Optional[str]) -> Dict[str, Any]:
    """C1 · who takes part and who sees, on the room just made: the people by
    ORCID with their roles, the invitation link, the study's embargo (its
    visibility the engine set). → `{members, link, access, failed,
    sentences}`; one refusal of the node is one sentence, the rest still goes."""
    from . import handoff, room_access
    want = STATE.get("access") or {}
    base, room_id = STATE.get("base"), STATE.get("room_id")
    out: Dict[str, Any] = {"members": [], "link": "", "access": {}, "failed": [],
                           "sentences": []}
    if not (base and room_id):
        return out
    for person in want.get("people") or []:
        try:
            room_access.set_member(base, token, room_id, person["orcid"], person["role"])
            out["members"].append(person)
        except Exception as exc:  # noqa: BLE001
            out["failed"].append(f"{person['orcid']}: {exc}")
    if want.get("invite"):
        try:
            made = room_access.invite(base, token, room_id, want.get("invite_role", "editor"),
                                      days=want.get("invite_days", 0),
                                      uses=want.get("invite_uses", 0))
            doors = handoff.open_targets(base, room_id, token=token) or {}
            out["link"] = room_access.link_for(doors.get("web") or doors.get("scheme") or "",
                                               made.get("token") or "")
            out["invite"] = made
            try:
                from .windows import INVITED
                INVITED.append({"role": made.get("role"), "link": out["link"],
                                "token_id": made.get("token_id")})
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            out["failed"].append(f"invitation link: {exc}")
    visibility = want.get("visibility") or "restricted"
    embargo = want.get("embargo") or ""
    out["access"] = dict((ULTIMO_REFERTO.get("engine") or {}).get("access") or {})
    if embargo or not out["access"].get("visibility"):
        try:
            out["access"] = room_access.set_study_access(
                base, token, room_id, visibility=visibility, embargo=embargo)
        except Exception as exc:  # noqa: BLE001
            out["failed"].append(f"who sees: {exc}")
    if out["members"]:
        out["sentences"].append("invited: " + ", ".join(
            f"{m['orcid']} ({m['role']})" for m in out["members"]))
    if out["link"]:
        role = want.get("invite_role") or "editor"
        out["sentences"].append(f"{'an' if role[0] in 'aeiou' else 'a'} {role} link: "
                                f"{out['link']}")
    if out["access"]:
        out["sentences"].append(
            f"who sees: {out['access'].get('visibility')}"
            + (f", embargo until {out['access']['embargo']}" if out["access"].get("embargo") else ""))
    ULTIMO_REFERTO["access"] = out
    for line in out["sentences"] + out["failed"]:
        print(f"[bring]   {line}")
    return out


# ── the operators ────────────────────────────────────────────────────────────

def _operator_classes():  # pragma: no cover — bpy
    import bpy  # type: ignore

    choice_items = (
        (inventory.CHOICE_UPLOAD, "Upload", "Put the bytes in the room's storage"),
        (inventory.CHOICE_REFERENCE, "Leave as reference",
         "Do not upload: the graph keeps pointing where it points"),
        (inventory.CHOICE_SKIP, "Skip", "Leave it out of this gesture"),
    )

    class EM_PG_bring_row(bpy.types.PropertyGroup):
        res_id: bpy.props.StringProperty()  # type: ignore
        label: bpy.props.StringProperty()  # type: ignore
        group: bpy.props.StringProperty()  # type: ignore
        size: bpy.props.StringProperty()  # type: ignore
        batch: bpy.props.StringProperty()  # type: ignore
        choice: bpy.props.EnumProperty(items=choice_items,  # type: ignore
                                       default=inventory.CHOICE_UPLOAD)

    class EM_UL_bring_rows(bpy.types.UIList):
        def draw_item(self, context, layout, data, item, icon, active_data,
                      active_propname, index):
            row = layout.row(align=True)
            row.label(text=f"{item.label} · {item.size}"
                      + (f" · {item.batch}" if item.batch else ""))
            row.prop(item, "choice", text="")

    visibility_items = (
        ("restricted", "Restricted", "Only the room's people see the study (the default)"),
        ("public", "Public", "Anybody with its name reads the study"))
    link_role_items = (("editor", "Editor", "Whoever opens the link may edit"),
                       ("viewer", "Viewer", "Whoever opens the link may read"))

    class EM_OT_room_bring(bpy.types.Operator):
        """Create a collaborative room from this study: the em.json whole (its
        graphs, its shelf) goes into a NEW room on this node, with who takes
        part and who sees; you become its owner and Blender enters it. A study
        already written by a room is offered that room instead"""

        bl_idname = "em.room_bring"
        bl_label = "Create a collaborative room from this study"
        bl_description = ("Build a room around this study: name it, say who takes "
                          "part and who sees it; then its resources go up, the "
                          "scene's models are published, and you are in it")

        name: bpy.props.StringProperty(name="Name", default="",  # type: ignore
                                       options={"SKIP_SAVE"})
        people: bpy.props.StringProperty(  # type: ignore
            name="People", default="", options={"SKIP_SAVE"},
            description=("By ORCID with a role, separated by commas: "
                         "«0000-0002-1825-0097 editor, 0000-0001-5109-3700 viewer». "
                         "No role: viewer"))
        invite: bpy.props.BoolProperty(  # type: ignore
            name="And an invitation link", default=False, options={"SKIP_SAVE"})
        invite_role: bpy.props.EnumProperty(  # type: ignore
            name="Role", items=link_role_items, default="editor")
        invite_days: bpy.props.IntProperty(  # type: ignore
            name="Days", default=7, min=0, description="0: no expiry")
        invite_uses: bpy.props.IntProperty(  # type: ignore
            name="Uses", default=0, min=0, description="0: no limit")
        visibility: bpy.props.EnumProperty(  # type: ignore
            name="Who sees", items=visibility_items, default="restricted")
        embargo: bpy.props.StringProperty(  # type: ignore
            name="Embargo until", default="", options={"SKIP_SAVE"},
            description="YYYY-MM-DD; empty: no embargo")
        confirm: bpy.props.BoolProperty(default=False,  # type: ignore
                                        options={"HIDDEN", "SKIP_SAVE"})
        existing: bpy.props.StringProperty(default="",  # type: ignore
                                           options={"HIDDEN", "SKIP_SAVE"})

        def _study_room(self, context):
            from ..functions import is_graph_available
            from . import study as study_mod
            ok, graph = is_graph_available(context)
            if not ok:
                return None, None
            the_study = study_mod.study_of(context, graph)
            return the_study, study_mod.room_of_study(context, the_study)

        def invoke(self, context, event):
            from ..functions import is_graph_available
            ok, _graph = is_graph_available(context)
            if not ok:
                self.report({"ERROR"}, "no study loaded: load it in the EM Data Tree")
                return {"CANCELLED"}
            from .windows import need_node
            if not need_node(context, "create"):
                return {"FINISHED"}
            _study, there = self._study_room(context)
            self.existing = there["room_id"] if there else ""
            if there and there.get("node"):
                context.scene.em_room_url = there["node"]
            if not self.name and not there:
                try:
                    self.name = str(context.scene.em_tools.graphml_files[
                        context.scene.em_tools.active_file_index].name)[:40]
                except Exception:  # noqa: BLE001
                    pass
            return context.window_manager.invoke_props_dialog(
                self, width=520,
                confirm_text="Enter it" if there else "Create the room")

        def draw(self, context):
            col = self.layout.column()
            node = getattr(context.scene, "em_room_url", "")
            if self.existing:
                # I-2 · a study is written by one room only
                col.label(text=f"This study is written by the room {self.existing}",
                          icon="COMMUNITY")
                col.label(text=f"on {node}. A study lives in one room: enter it.",
                          icon="BLANK1")
                return
            col.label(text=f"Node: {node}", icon="WORLD")
            box = col.box()
            box.prop(self, "name")
            box.label(text=f"id: {nodeio.room_id_from_name(self.name) or '—'}",
                      icon="BLANK1")
            box = col.box()
            box.label(text="Who takes part", icon="USER")
            box.prop(self, "people", text="By ORCID")
            row = box.row(align=True)
            row.prop(self, "invite")
            sub = row.row(align=True)
            sub.enabled = self.invite
            sub.prop(self, "invite_role", text="")
            sub.prop(self, "invite_days")
            sub.prop(self, "invite_uses")
            box = col.box()
            box.label(text="Who sees", icon="HIDE_OFF")
            box.row().prop(self, "visibility", expand=True)
            box.prop(self, "embargo")

        def execute(self, context):
            from ..functions import is_graph_available
            from .rooms_ui import _access_for, _keep_access

            ok, graph = is_graph_available(context)
            if not ok:
                self.report({"ERROR"}, "no study loaded: load it in the EM Data Tree")
                return {"CANCELLED"}
            _study, there = self._study_room(context)
            if there:
                # I-2 · not a second room: the one that writes it
                context.scene.em_room_id = there["room_id"]
                if there.get("node"):
                    context.scene.em_room_url = there["node"]
                self.report({"INFO"}, f"this study is written by the room "
                                      f"{there['room_id']}: entering it")
                return bpy.ops.em.room_reconnect()
            base = str(getattr(context.scene, "em_room_url", "") or "").strip().rstrip("/")
            if not base:
                self.report({"ERROR"}, "choose the node first")
                return {"CANCELLED"}
            from . import room_access
            try:
                people = room_access.parse_people(self.people)
                if self.embargo.strip():
                    import datetime
                    datetime.date.fromisoformat(self.embargo.strip()[:10])
            except ValueError as exc:
                self.report({"ERROR"}, str(exc) if "ORCID" in str(exc) or "role" in str(exc)
                            else f"the embargo «{self.embargo}» is not a date (YYYY-MM-DD)")
                return {"CANCELLED"}
            from .signin_ui import Waiting
            args = {k: getattr(self, k) for k in (
                "name", "people", "invite", "invite_role", "invite_days",
                "invite_uses", "visibility", "embargo", "confirm")}
            try:
                token, _how = _access_for(
                    base, "", resume=lambda: bpy.ops.em.room_bring(**args))
                _keep_access(base, token)
                prepare(context, graph, base=base, name=self.name, token=token)
            except Waiting as exc:
                self.report({"INFO"}, str(exc))
                return {"FINISHED"}
            except Exception as exc:  # noqa: BLE001 — the node's sentence
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            STATE["access"] = {"people": people, "invite": bool(self.invite),
                               "invite_role": self.invite_role,
                               "invite_days": int(self.invite_days),
                               "invite_uses": int(self.invite_uses),
                               "visibility": self.visibility,
                               "embargo": self.embargo.strip()}
            _fill_rows(context)
            for line in inventory.sentences(inventory.summarise(STATE["rows"])):
                print(f"[bring] inventory: {line}")
            if self.confirm:
                return bpy.ops.em.room_bring_go()
            return bpy.ops.em.room_bring_go("INVOKE_DEFAULT")

    class EM_OT_room_bring_go(bpy.types.Operator):
        """The inventory, and the choices: then everything chosen goes up."""

        bl_idname = "em.room_bring_go"
        bl_label = "Bring into the room"
        bl_description = "Upload what you chose, publish the models, seat the graph, enter"

        found_choice: bpy.props.EnumProperty(  # type: ignore
            name="Found on this disk", items=choice_items,
            default=inventory.CHOICE_UPLOAD)
        promote: bpy.props.BoolProperty(  # type: ignore
            name="Publish the scene's models (RM, proxy)", default=True)
        offer_blend: bpy.props.BoolProperty(  # type: ignore
            name="Then offer a .blend snapshot", default=True)
        move_here: bpy.props.BoolProperty(  # type: ignore
            name="Move here the files kept in another room",
            description="Their home and rights become this room's; no byte is "
                        "sent. Off: their home stays where it is, and this room "
                        "hosts them at its own address (the node already has them)",
            default=False)
        confirm_lots: bpy.props.BoolProperty(  # type: ignore
            name="Make each proposed session one lot",
            description="One acquisition per session of photos (same camera, "
                        "contiguous EXIF times). Off: the photos stay files",
            default=False)

        def invoke(self, context, event):
            return context.window_manager.invoke_props_dialog(self, width=560)

        def draw(self, context):
            layout = self.layout
            layout.label(text=f"Room {STATE.get('room_id')} — "
                              f"{STATE.get('where', {}).get('note') or 'yours'}",
                         icon="COMMUNITY")
            for line in inventory.sentences(inventory.summarise(STATE.get("rows") or [])):
                layout.label(text=line, icon="BLANK1")
            layout.prop(self, "found_choice")
            layout.template_list("EM_UL_bring_rows", "", context.window_manager,
                                 "em_bring_rows", context.window_manager,
                                 "em_bring_index", rows=6)
            layout.label(text="Rights come from each resource or its batch; with "
                              "no licence, only the room sees it.", icon="LOCKED")
            lots = STATE.get("lots") or []
            if lots:
                box = layout.box()
                for lot in lots:
                    box.label(text=f"Proposed lot: {lot['name']} · {len(lot['ids'])} photos",
                              icon="IMAGE_DATA")
                box.prop(self, "confirm_lots")
            plan = inventory.move_plan(STATE.get("rows") or [], STATE.get("move_views") or {})
            if plan["movable"] or plan["blocked"]:
                # F1 · the listing BEFORE the yes
                box = layout.box()
                box.label(text=f"{len(plan['movable']) + len(plan['blocked'])} file(s) "
                               f"are kept in another room", icon="FILE_REFRESH")
                if plan["movable"]:
                    box.label(text=f"They leave: {', '.join(plan['leave'])}", icon="BLANK1")
                    box.label(text=("Cited by the graphs of: " + ", ".join(plan["references"])
                                    + " (there they become a reference)")
                              if plan["references"] else "No other room's graph cites them",
                              icon="BLANK1")
                    box.label(text="Whoever has no access to this room will not see them",
                              icon="BLANK1")
                    box.prop(self, "move_here")
                for b in plan["blocked"]:
                    box.label(text=f"{b['row']['name']} stays: {b['why']}"[:110], icon="LOCKED")
            layout.prop(self, "promote")
            layout.prop(self, "offer_blend")

        def execute(self, context):
            from ..functions import is_graph_available
            if "run" not in STATE:
                self.report({"ERROR"}, "no inventory: start from «Bring into a room…»")
                return {"CANCELLED"}
            ok, graph = is_graph_available(context)
            if not ok:
                self.report({"ERROR"}, "no graph loaded")
                return {"CANCELLED"}
            per_item = {r.res_id: r.choice for r in context.window_manager.em_bring_rows
                        if r.choice != self.found_choice}
            engine.apply_choices(STATE["run"],
                                 per_group={inventory.GROUP_FOUND: self.found_choice},
                                 per_item=per_item)
            STATE["move_yes"] = bool(self.move_here)
            for lot in STATE.get("lots") or []:
                lot["confirmed"] = bool(self.confirm_lots)
            wm = context.window_manager
            wm.progress_begin(0, 100)
            try:
                report = execute(
                    context, graph, token=room_cfg._session.get("token"),
                    promote=self.promote,
                    progress=lambda _n, a, b: wm.progress_update(
                        int(100 * a / b) if b else 100))
            except Exception as exc:  # noqa: BLE001
                self.report({"ERROR"}, f"could not bring the graph: {exc}")
                return {"CANCELLED"}
            finally:
                wm.progress_end()
            access = apply_access(token=room_cfg._session.get("token"))
            report["access"] = access
            for line in report["failed"] + access["failed"]:
                self.report({"WARNING"}, line)
            self.report({"INFO"}, report["sentence"])
            for line in access["sentences"]:
                self.report({"INFO"}, line)
            if self.offer_blend and not bpy.app.background:
                bpy.ops.em.blend_backup_archive("INVOKE_DEFAULT")
            return {"FINISHED"}

    return (EM_PG_bring_row, EM_UL_bring_rows, EM_OT_room_bring, EM_OT_room_bring_go)


def _fill_rows(context) -> None:  # pragma: no cover — bpy
    """The FOUND rows in the dialog's list, one per item — the batch named on
    each so a choice per photo is possible, and the group choice covers all."""
    rows = context.window_manager.em_bring_rows
    rows.clear()
    for row in STATE.get("rows") or []:
        if row["group"] != inventory.GROUP_FOUND:
            continue
        item = rows.add()
        item.res_id = row["id"]
        item.label = row["name"]
        item.group = row["group"]
        item.size = inventory.human_size(row.get("size") or 0)
        item.batch = row.get("batch_name") or ""
        item.choice = row["choice"]


_CLASSES: tuple = ()


def register():  # pragma: no cover — bpy
    import bpy  # type: ignore
    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.em_bring_rows = bpy.props.CollectionProperty(
        type=_CLASSES[0])
    bpy.types.WindowManager.em_bring_index = bpy.props.IntProperty(default=-1)


def unregister():  # pragma: no cover — bpy
    import bpy  # type: ignore
    for name in ("em_bring_index", "em_bring_rows"):
        if hasattr(bpy.types.WindowManager, name):
            delattr(bpy.types.WindowManager, name)
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass


def draw(layout, context) -> None:  # pragma: no cover — bpy
    """The «Bring into a room…» button and the last report."""
    box = layout.box()
    box.operator("em.room_bring", text="Create a collaborative room from this study…",
                 icon="ADD")
    if ULTIMO_REFERTO.get("sentence"):
        box.label(text=ULTIMO_REFERTO["sentence"][:90], icon="CHECKMARK")
