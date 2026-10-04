"""P3 · «Bring into a room…» from Blender — one gesture, the same as EMStudio's.

MICRO-LA-BARRA-E-LE-STANZE. Node + name → the room is created with you as its
owner → the RESOURCE INVENTORY of the graph in four groups (`inventory.py`) →
the person chooses (upload by default / leave as reference / skip, per group,
per batch, per item) → the chosen files go up (`asset_upload.upload_asset`, HEAD
first) and their resource nodes become store-backed keeping their path → the
scene models linked to the graph (RM, proxy) are published (`promote_model`,
`residency: resident`) — never an object «only here» → the graph is seated in
the room → Blender ENTERS the room by itself (D-B: each tool enters directly,
not behind EMStudio) → the report: uploaded N (size), references M, missing K,
the room's link. A `.blend` snapshot is OFFERED at the end
(`em.blend_backup_archive`), never taken silently.

**Why the graph is seated LAST, not first.** The proposal lists «the graph goes
up» as step 1; here it goes up after the uploads, in the same gesture, so the
room receives the resource nodes already store-backed — one seeding, instead of
a seeding followed by a second wave of updates for every uploaded file.

**How the graph is seated: operations**, the five idempotent verbs, through the
node's connector door (`POST /v1/rooms/{id}/ops`, applied and kept under the
room's lock). The same ops EMStudio's `seedOpsForContainer` sends over the
socket — no seeding endpoint that writes past the merge.

**A second «Bring into a room» uploads nothing**: every file it finds, the HEAD
says the room already has; the seeding is all idempotent refusals.

**One room, one graph (D-A)**: the ACTIVE graph is brought. Other graphs of the
project stay here, and the report says so.

**A file lives in one room (F1).** A file the node already keeps in ANOTHER
room is listed apart («at home in another room»): the dialog names the rooms
it would leave and the rooms whose graphs cite it (there it becomes a
reference), and «Move here» happens only if the person ticks it — then the
node changes its home, no byte is sent. Unticked, the resource points at the
file where it lives, as a reference.

**Lots are proposed (L1).** Photos of one session (same camera, EXIF times at
most 30 min apart, at least 5) are proposed as a lot; a D.nn document or the
DosCo never is. Only a ticked proposal becomes one acquisition.
"""

# NOT `from __future__ import annotations`: the PropertyGroup below is built
# inside a function, and Blender evaluates its annotations in the module's
# globals, where `bpy` is imported lazily — a string annotation would not
# resolve (measured: «name 'bpy' is not defined» at register).
import os
import time
from typing import Any, Callable, Dict, List, Optional

from . import asset_upload, inventory, rooms_list
from . import room as room_cfg

try:
    from ..functions import em_log
except Exception:  # noqa: BLE001 — outside the addon (tests)
    def em_log(message, *_a, **_k):
        print(message)

#: The last gesture, in memory, between the inventory dialog and the upload.
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
    """Where a relative path of this project is looked for: the DosCo folder,
    the em.json/GraphML's folder, the .blend's folder."""
    import bpy  # type: ignore
    out = []
    entry = _active_entry(context)
    if entry is not None:
        for raw in (getattr(entry, "dosco_dir", ""), getattr(entry, "graphml_path", "")):
            if not raw:
                continue
            path = bpy.path.abspath(raw)
            out.append(path if os.path.isdir(path) else os.path.dirname(path))
    if bpy.data.filepath:
        out.append(os.path.dirname(bpy.data.filepath))
    return [p for p in out if p]


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


def open_room(base: str, token: Optional[str], name: str) -> Dict[str, Any]:
    """Create the room; or, if it exists and you may write in it, use it.

    → `{room_id, created, role, seedable, note}`. A NEW room that already holds
    a graph (an implicit room somebody used without declaring it) is not
    seeded: writing our file over somebody's undeclared work is the one mistake
    this gesture must not make — the same rule as EMStudio's.
    """
    room_id = rooms_list.room_id_from_name(name)
    try:
        created = rooms_list.create_room(base, token, name)
        missing = created.get("missing_refs") or []
        refs = created.get("container_refs") or [room_id]
        empty = all(ref in missing for ref in refs)
        return {"room_id": created["room_id"], "created": True,
                "role": created.get("your_role") or "owner", "seedable": empty,
                "note": "" if empty else
                f"the room {room_id} already holds a graph: not seeded"}
    except room_cfg.RoomError as exc:
        if exc.status != 409:
            raise
    info = rooms_list.room_info(base, token, room_id)
    role = str(info.get("your_role") or "")
    if role not in ("owner", "admin", "editor"):
        raise room_cfg.RoomError(
            f"the room {room_id} exists and you are {role or 'not a member'} "
            f"there: choose another name")
    return {"room_id": room_id, "created": False, "role": role, "seedable": True,
            "note": f"the room {room_id} already exists ({role}): what is "
                    f"brought merges into it"}


def prepare(context, graph, *, base: str, name: str, token: Optional[str]
            ) -> Dict[str, Any]:
    """Step 1 and 2: the room, then the inventory. Nothing is uploaded yet."""
    where = open_room(base, token, name)
    room_cfg.set_room(base, where["room_id"], token)
    rows = inventory.classify(
        inventory.resource_entries(graph), base_dirs=base_dirs(context),
        asset_home=lambda hexd: asset_upload.asset_head(base, where["room_id"],
                                                        hexd, token),
        room_id=where["room_id"], hasher=asset_upload.sha256_of_file)
    from . import exif_lite
    gap, least = lot_thresholds(context)
    lots = inventory.propose_sessions(rows, exif_of=exif_lite.photo_exif,
                                      dosco_dirs=dosco_dirs(context),
                                      gap_seconds=gap, min_photos=least)
    # F1 · for every file at home elsewhere, the node's answer BEFORE the yes
    views = {r["id"]: asset_upload.asset_home_view(base, where["room_id"],
                                                   r["sha256"], token)
             for r in rows if r["group"] == inventory.GROUP_ELSEWHERE and r.get("sha256")}
    STATE.clear()
    STATE.update({"base": base, "room_id": where["room_id"], "where": where,
                  "rows": rows, "lots": lots, "move_views": views,
                  "graph_id": str(getattr(graph, "graph_id", ""))})
    return STATE


def move_here(graph, *, token: Optional[str], yes: bool) -> Dict[str, Any]:
    """F1 · the files at home in another room: moved here on the person's yes,
    else (or when the node refuses) left as references to where they live.
    → `{moved, references, failed: [sentence]}`."""
    base, room_id, rows = STATE["base"], STATE["room_id"], STATE["rows"]
    plan = inventory.move_plan(rows, STATE.get("move_views") or {})
    done = {"moved": 0, "references": 0, "failed": []}
    moved_ids = set()
    if yes:
        for row in plan["movable"]:
            view = STATE["move_views"][row["id"]]
            try:
                answer = asset_upload.move_asset_home(base, room_id, row["sha256"],
                                                      view.get("home"), token)
            except Exception as exc:  # noqa: BLE001 — one file, one sentence
                done["failed"].append(f"{row['name']}: {exc}")
                continue
            if answer.get("home") != room_id:
                done["failed"].append(f"{row['name']}: the node kept it in "
                                      f"{answer.get('home')}")
                continue
            moved_ids.add(row["id"])
            node = graph.find_node_by_id(row["id"])
            if node is not None:
                inventory.make_store_backed(
                    node, url=asset_upload.asset_url(base, room_id, row["sha256"]),
                    sha256=row["sha256"])
            done["moved"] += 1
            em_log(f"[bring] {row['name']} moved here from {view.get('home')}; "
                   f"references now in {', '.join(view.get('references') or []) or 'no other room'}")
    for b in plan["blocked"]:
        em_log(f"[bring] {b['row']['name']} stays in {b['row'].get('home')}: {b['why']}")
    for row in rows:
        if row["group"] != inventory.GROUP_ELSEWHERE or row["id"] in moved_ids:
            continue
        node = graph.find_node_by_id(row["id"])
        if node is not None and row.get("home") and row.get("sha256"):
            inventory.make_store_backed(
                node, url=asset_upload.asset_url(base, row["home"], row["sha256"]),
                sha256=row["sha256"], residency="reference")
        done["references"] += 1
    return done


def bucket_confirmed_lots(graph, lots: List[Dict[str, Any]]) -> List[str]:
    """L1 · each CONFIRMED session becomes one acquisition in the graph (the
    serial node, s3dgraphy `bucket_acquisition`); a proposal not confirmed
    leaves its photos as files. → the acquisition ids."""
    from s3dgraphy import api
    made = []
    for lot in lots or []:
        if not lot.get("confirmed"):
            continue
        out = api.bucket_acquisition(
            graph, lot["ids"], name=f"Photos · {lot['name']}",
            metadata={"camera": lot["camera"], "taken_from": lot["from"],
                      "taken_to": lot["to"],
                      "source": "EMtools · bring into a room"})
        made.append(str(out.get("acquisition_id") or out.get("id") or ""))
    return made


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


def execute(context, graph, *, token: Optional[str], promote: bool = True,
            progress: Optional[Callable[[str, int, int], None]] = None
            ) -> Dict[str, Any]:
    """Steps 3–6: upload, publish the scene models, seat the graph, enter."""
    import bpy  # type: ignore
    from . import commands
    from . import operators as ops

    base, room_id, rows = STATE["base"], STATE["room_id"], STATE["rows"]
    started = time.time()
    uploaded = {"count": 0, "size": 0, "already": 0}
    failed: List[str] = []
    moves = move_here(graph, token=token, yes=bool(STATE.get("move_yes")))
    failed.extend(moves["failed"])
    todo = [r for r in rows if r["group"] == inventory.GROUP_FOUND
            and r["choice"] == inventory.CHOICE_UPLOAD]
    total = sum(int(r.get("size") or 0) for r in todo)
    done = [0]
    for row in todo:
        def tick(sent, _size, before=done[0]):
            if progress:
                progress(row["name"], before + sent, total)
        try:
            info = asset_upload.upload_asset(
                base, room_id, row["path"], row.get("sha256") or None,
                inventory.media_type_for(row["path"]), token, tick)
        except Exception as exc:  # noqa: BLE001 — one file is one row, not the batch
            failed.append(f"{row['name']}: {exc}")
            continue
        done[0] += int(row.get("size") or 0)
        node = graph.find_node_by_id(row["id"])
        if node is not None:
            inventory.make_store_backed(node, url=info["url"], sha256=info["sha256"])
        if info.get("already"):
            uploaded["already"] += 1
        else:
            uploaded["count"] += 1
            uploaded["size"] += int(row.get("size") or 0)

    published, published_size, published_skip = [], 0, 0
    if promote:
        for model in scene_models(context, graph):
            obj = bpy.data.objects.get(model["object"])
            if obj is None:
                continue
            if _already_published(obj, graph):
                published_skip += 1
                continue
            result = commands.promote_model(
                model["target"], {"object": obj.name, "residency": "resident"},
                context, graph)
            if result.get("ok"):
                info = result["info"]
                published.append(info["object"])
                if info.get("stored"):
                    published_size += int(info.get("size") or 0)
            else:
                failed.append(f"{model['object']}: {result.get('error')}")

    acquisitions = bucket_confirmed_lots(graph, STATE.get("lots") or [])
    seeded = {"applied": 0, "refused": [], "requests": 0}
    if STATE["where"].get("seedable"):
        from ..emjson_support import graph_to_emjson_dict
        section = graph_to_emjson_dict(graph).get("graph") or {}
        seeded = rooms_list.send_ops(base, token, room_id,
                                     inventory.seed_ops(graph, section))

    # D-B · Blender ENTERS the room by itself. Not adopting: the room's graph is
    # the one we just seated from this very session.
    from .room_session import SESSION
    joined = {"ok": SESSION.joined and SESSION.room_id == room_id,
              "message": "already in the room"}
    if not joined["ok"]:
        if SESSION.joined:
            ops.leave_room()
        joined = ops.join_room(context, base, room_id, token or "", adopt=False)

    from . import handoff
    targets = handoff.open_targets(base, room_id, token=token) or {}
    link = targets.get("web") or targets.get("scheme") or ""

    summary = inventory.summarise(rows)
    refs = summary["groups"][inventory.GROUP_EXTERNAL]["count"] + sum(
        1 for r in rows if r["group"] == inventory.GROUP_FOUND
        and r["choice"] == inventory.CHOICE_REFERENCE)
    missing = summary["groups"][inventory.GROUP_MISSING]["count"]
    others = 0
    try:
        others = max(0, len(context.scene.em_tools.graphml_files) - 1)
    except Exception:  # noqa: BLE001
        pass
    size_up = uploaded["size"] + published_size
    report = {
        "room_id": room_id, "link": link, "created": STATE["where"]["created"],
        "uploaded": uploaded["count"] + len(published),
        "moved": moves["moved"], "lots": acquisitions,
        "uploaded_size": size_up,
        "already": uploaded["already"] + published_skip,
        "references": refs, "missing": missing,
        "models": published, "failed": failed,
        "ops_applied": seeded["applied"], "ops_refused": len(seeded["refused"]),
        "joined": bool(joined.get("ok")), "join_message": joined.get("message"),
        "other_graphs": others, "seconds": round(time.time() - started, 1),
        "note": STATE["where"].get("note") or "",
    }
    refs += moves["references"]
    report["references"] = refs
    report["sentence"] = (
        f"uploaded {report['uploaded']} ({inventory.human_size(size_up)}), "
        + (f"moved here {moves['moved']}, " if moves["moved"] else "")
        + f"references {refs}, missing {missing} — room {room_id}: {link}")
    ULTIMO_REFERTO.clear()
    ULTIMO_REFERTO.update(report)
    print(f"[bring] {report['sentence']}")
    for line in inventory.sentences(summary):
        print(f"[bring]   {line}")
    if report["already"]:
        print(f"[bring]   {report['already']} already in the room: not sent again")
    if others:
        print(f"[bring]   one room, one graph: {others} other graph(s) of this "
              f"project stay here")
    for line in failed:
        print(f"[bring]   FAILED {line}")
    return report


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

    class EM_OT_room_bring(bpy.types.Operator):
        """Bring the active graph into a NEW room on this node, with its
        resources: you become the owner, Blender enters the room."""

        bl_idname = "em.room_bring"
        bl_label = "Bring into a room…"
        bl_description = ("Create a room on this node (you are its owner), see "
                          "where the graph's resources are, upload them, publish "
                          "the scene's models, and enter the room")

        name: bpy.props.StringProperty(name="Room name", default="",  # type: ignore
                                       options={"SKIP_SAVE"})
        confirm: bpy.props.BoolProperty(default=False,  # type: ignore
                                        options={"HIDDEN", "SKIP_SAVE"})

        def invoke(self, context, event):
            return context.window_manager.invoke_props_dialog(self, width=420)

        def draw(self, context):
            col = self.layout.column()
            col.label(text=f"Node: {getattr(context.scene, 'em_room_url', '')}",
                      icon="WORLD")
            col.prop(self, "name")
            col.label(text=f"id: {rooms_list.room_id_from_name(self.name) or '—'}",
                      icon="INFO")

        def execute(self, context):
            from ..functions import is_graph_available
            from .rooms_ui import _access_for, _keep_access

            ok, graph = is_graph_available(context)
            if not ok:
                self.report({"ERROR"}, "no graph loaded: load it from the EM panel")
                return {"CANCELLED"}
            base = str(getattr(context.scene, "em_room_url", "") or "").strip().rstrip("/")
            if not base:
                self.report({"ERROR"}, "set the node address first")
                return {"CANCELLED"}
            try:
                token, _how = _access_for(base, "")
                _keep_access(base, token)
                prepare(context, graph, base=base, name=self.name, token=token)
            except Exception as exc:  # noqa: BLE001 — the node's sentence
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
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
                        "sent. Off: they stay where they are, as references",
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
            if "rows" not in STATE:
                self.report({"ERROR"}, "no inventory: start from «Bring into a room…»")
                return {"CANCELLED"}
            ok, graph = is_graph_available(context)
            if not ok:
                self.report({"ERROR"}, "no graph loaded")
                return {"CANCELLED"}
            per_item = {r.res_id: r.choice for r in context.window_manager.em_bring_rows
                        if r.choice != self.found_choice}
            inventory.apply_choices(STATE["rows"],
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
            for line in report["failed"]:
                self.report({"WARNING"}, line)
            self.report({"INFO"}, report["sentence"])
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
    box.operator("em.room_bring", icon="EXPORT")
    if ULTIMO_REFERTO.get("sentence"):
        box.label(text=ULTIMO_REFERTO["sentence"][:90], icon="CHECKMARK")
