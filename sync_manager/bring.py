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
        # the DosCo of the auxiliary files (where the legacy `dosco_dir` went)
        for aux in getattr(entry, "auxiliary_files", ()):
            if getattr(aux, "file_type", "") == "dosco" and aux.dosco_folder:
                out.append(bpy.path.abspath(aux.dosco_folder))
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


def open_room(base: str, token: Optional[str], name: str, *,
              sections: Optional[List[Dict[str, Any]]] = None,
              active_graph_id: Optional[str] = None) -> Dict[str, Any]:
    """Create the room; or, if it exists and you may write in it, use it.

    → `{room_id, created, role, seedable, note}`. A NEW room that already holds
    a graph (an implicit room somebody used without declaring it) is not
    seeded: writing our file over somebody's undeclared work is the one mistake
    this gesture must not make — the same rule as EMStudio's.
    """
    room_id = rooms_list.room_id_from_name(name)
    try:
        created = rooms_list.create_room(base, token, name, graphs=sections,
                                         active_graph_id=active_graph_id)
        missing = created.get("missing_refs") or []
        refs = created.get("container_refs") or [room_id]
        empty = all(ref in missing for ref in refs)
        return {"room_id": created["room_id"], "created": True,
                "role": created.get("your_role") or "owner", "seedable": empty,
                # S1 · the sections the room was born with (a node before G2
                # answers none: then the active graph alone, as before)
                "born_with": list(created.get("born_with") or []),
                "title": str(created.get("title") or name),
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
            "born_with": [], "title": str(info.get("title") or name),
            "note": f"the room {room_id} already exists ({role}): what is "
                    f"brought merges into it"}


def prepare(context, graph, *, base: str, name: str, token: Optional[str]
            ) -> Dict[str, Any]:
    """Step 1 and 2: the room, then the inventory. Nothing is uploaded yet.

    S1 · the room is built around the STUDY (`study.study_of`): born with all
    its sections, and the inventory is of all its graphs, each row naming the
    graph it is in."""
    from . import study as study_mod
    the_study = study_mod.study_of(context, graph)
    where = open_room(base, token, name,
                      sections=study_mod.birth_sections(the_study),
                      active_graph_id=the_study.get("active") or None)
    room_cfg.set_room(base, where["room_id"], token)
    from . import exif_lite
    gap, least = lot_thresholds(context)
    rows, lots = [], []
    for gid, member in the_study["graphs"].items():
        part = inventory.classify(
            inventory.resource_entries(member), base_dirs=base_dirs(context),
            asset_home=lambda hexd: asset_upload.asset_head(base, where["room_id"],
                                                            hexd, token),
            room_id=where["room_id"], hasher=asset_upload.sha256_of_file)
        for row in part:
            row["graph_id"] = gid
        rows.extend(part)
        for lot in inventory.propose_sessions(part, exif_of=exif_lite.photo_exif,
                                              dosco_dirs=dosco_dirs(context),
                                              gap_seconds=gap, min_photos=least):
            lot["graph_id"] = gid
            lots.append(lot)
    # F1 · for every file at home elsewhere, the node's answer BEFORE the yes
    views = {r["id"]: asset_upload.asset_home_view(base, where["room_id"],
                                                   r["sha256"], token)
             for r in rows if r["group"] == inventory.GROUP_ELSEWHERE and r.get("sha256")}
    STATE.clear()
    STATE.update({"base": base, "room_id": where["room_id"], "where": where,
                  "rows": rows, "lots": lots, "move_views": views,
                  "graph_id": str(getattr(graph, "graph_id", "")),
                  "study": the_study})
    return STATE


def graph_of_row(row: Dict[str, Any], default: Any) -> Any:
    """S1 · the graph of the study a row of the inventory is in."""
    study = STATE.get("study") or {}
    return (study.get("graphs") or {}).get(row.get("graph_id")) or default


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
            node = graph_of_row(row, graph).find_node_by_id(row["id"])
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
        node = graph_of_row(row, graph).find_node_by_id(row["id"])
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
            graph_of_row(lot, graph), lot["ids"], name=f"Photos · {lot['name']}",
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


def _fill_proxy_chain(graph, unit_id: str, info: Dict[str, Any],
                      rows: List[Dict[str, Any]]) -> bool:
    """G2 · a unit's proxy just published: its chain's resource
    (`proxies/<US>.glb`, a placeholder until the Heriverse export names a file)
    becomes those bytes in the room's store. Measured on 4 Oct 2026: the room
    born from Templu Mare listed the 66 placeholders as «missing» beside the 66
    proxies it had just published, and EMStudio's Models sheet read the
    placeholders. A resource that already has its bytes is not touched."""
    try:
        from ..proxy_chain import glb_proxy
    except ImportError:
        return False
    _shape, resource = glb_proxy(graph, unit_id)
    data = getattr(resource, "data", None) if resource is not None else None
    if resource is None or (isinstance(data, dict) and data.get("checksum")):
        return False
    inventory.make_store_backed(resource, url=room_cfg.asset_url(info["ref"]),
                                sha256=info["ref"])
    for row in rows:
        if row.get("id") == resource.node_id and row["group"] == inventory.GROUP_MISSING:
            row["group"] = inventory.GROUP_STORED
    return True


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
        node = graph_of_row(row, graph).find_node_by_id(row["id"])
        if node is not None:
            inventory.make_store_backed(node, url=info["url"], sha256=info["sha256"])
        if info.get("already"):
            uploaded["already"] += 1
        else:
            uploaded["count"] += 1
            uploaded["size"] += int(row.get("size") or 0)

    study_graphs = dict((STATE.get("study") or {}).get("graphs") or {}) or \
        {str(getattr(graph, "graph_id", "")): graph}
    published, published_size, published_skip = [], 0, 0
    if promote:
        seen_objects = set()
        for member in study_graphs.values():
            for model in scene_models(context, member):
                obj = bpy.data.objects.get(model["object"])
                if obj is None or obj.name in seen_objects:
                    continue
                seen_objects.add(obj.name)
                if _already_published(obj, member):
                    published_skip += 1
                    continue
                result = commands.promote_model(
                    model["target"], {"object": obj.name, "residency": "resident"},
                    context, member)
                if result.get("ok"):
                    info = result["info"]
                    if model.get("kind") == "proxy":
                        _fill_proxy_chain(member, model["target"], info, rows)
                    if info.get("stored"):
                        published.append(info["object"])
                        published_size += int(info.get("size") or 0)
                    else:
                        # X2 · the node had these bytes: published, not uploaded
                        published_skip += 1
                else:
                    failed.append(f"{model['object']}: {result.get('error')}")

    acquisitions = bucket_confirmed_lots(graph, STATE.get("lots") or [])
    seeded = {"applied": 0, "refused": [], "requests": 0}
    born = list(STATE["where"].get("born_with") or [])
    seeded_graphs: List[str] = []
    if STATE["where"].get("seedable") and born:
        # S1 · the study WHOLE: every section the room was born with, seeded
        # with operations that name their graph
        from . import study as study_mod
        for gid, member, section in study_mod.seed_plan(STATE["study"]):
            if gid not in born:
                continue
            part = rooms_list.send_ops(base, token, room_id,
                                       inventory.seed_ops(member, section),
                                       graph_id=gid)
            seeded["applied"] += part["applied"]
            seeded["refused"] += part["refused"]
            seeded["requests"] += part["requests"]
            seeded_graphs.append(gid)
    elif STATE["where"].get("seedable"):
        # a node that does not take a study's sections: the active graph, as
        # before (D-A), and the report says so
        from ..emjson_support import graph_to_emjson_dict
        section = graph_to_emjson_dict(graph).get("graph") or {}
        seeded = rooms_list.send_ops(base, token, room_id,
                                     inventory.seed_ops(graph, section))
        seeded_graphs = [str(getattr(graph, "graph_id", ""))]

    # D-B · Blender ENTERS the room by itself. Not adopting: the room's graph is
    # the one we just seated from this very session.
    from .room_session import SESSION
    joined = {"ok": SESSION.joined and SESSION.room_id == room_id,
              "message": "already in the room"}
    if not joined["ok"]:
        if SESSION.joined:
            ops.leave_room()
        joined = ops.join_room(context, base, room_id, token or "", adopt=False)
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
        _where.ROOM_TITLES[room_id] = str(STATE["where"].get("title") or room_id)

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
        others = sum(1 for r in context.scene.em_tools.graphml_files
                     if r.name not in study_graphs)
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
        "seeded_graphs": seeded_graphs, "study_graphs": list(study_graphs),
        "joined": bool(joined.get("ok")), "join_message": joined.get("message"),
        "other_graphs": others, "seconds": round(time.time() - started, 1),
        "note": STATE["where"].get("note") or "",
    }
    refs += moves["references"]
    report["references"] = refs
    report["sentence"] = (
        upload_phrase(report["uploaded"], size_up, report["already"]) + ", "
        + (f"moved here {moves['moved']}, " if moves["moved"] else "")
        + f"references {refs}, missing {missing} — room {room_id}: {link}")
    ULTIMO_REFERTO.clear()
    ULTIMO_REFERTO.update(report)
    print(f"[bring] {report['sentence']}")
    for line in inventory.sentences(summary):
        print(f"[bring]   {line}")
    print(f"[bring]   the study: {len(seeded_graphs)} graph(s) seeded "
          f"({', '.join(seeded_graphs)})" + ("" if born else
          " — the node took no sections: the active graph only (D-A)"))
    if others:
        print(f"[bring]   {others} graph(s) of this scene belong to other studies "
              f"and stay here")
    for line in failed:
        print(f"[bring]   FAILED {line}")
    return report


def apply_access(*, token: Optional[str]) -> Dict[str, Any]:
    """C1 · who takes part and who sees, on the room just made: the people by
    ORCID with their roles, the invitation link, the study's visibility and
    embargo. → `{members, link, access, failed, sentences}`; one refusal of the
    node is one sentence, the rest still goes."""
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
            box.label(text=f"id: {rooms_list.room_id_from_name(self.name) or '—'}",
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
