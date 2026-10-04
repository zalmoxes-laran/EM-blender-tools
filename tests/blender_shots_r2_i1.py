"""GUI screenshots: R2 (the sign beside each model of «EM Scene», the file rows
named by the file and its document) and I1 (room, role, sync and «only here»
in the EMStudio Sync panel with the signs of the common list), on a LIVE node.

NOT headless (the panels must be drawn to be photographed), and no user data:
a COPY of the fixture em.json in a temporary folder, three cubes (the RM of
`M_model`, the RM of `T_model`, a «Decoration» linked to nothing).

    cd ~/Documents/GitHub/stratigraph-server/dev-stack
    EM_DEV_TOKEN=$(./token.sh) EM_VIEWER_TOKEN=$(./token.sh --user viewer) \\
    EM_NODE=http://localhost:8000 PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" --python-use-system-env \\
        --enable-event-simulate --python ~/Documents/GitHub/EM-blender-tools/tests/blender_shots_r2_i1.py \\
        -- <out_dir> <phase>

As `dev` (owner): «Bring into a room…» a new room, «Check files», then
`emtools_r2_<phase>_models.png` (EM Scene: the RM list), `emtools_r2_<phase>_files.png`
(the Files section of Resources & Shelf)
and `emtools_i1_<phase>_sync_owner.png` (EM Bridge: the Sync panel in the room,
the scene check with the decoration «only here»). As `viewer` (made a viewer
of that room by its owner) who tries one edit: `emtools_i1_<phase>_sync_viewer.png`
(read-only, the refused edit). Out of the room: `emtools_i1_<phase>_sync_outside.png`.
`<phase>` is `before` or `after`. Exits non-zero if a check fails.
"""
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else tempfile.mkdtemp()
PHASE = ARGS[1] if len(ARGS) > 1 else "after"
os.makedirs(OUT, exist_ok=True)
NODE = os.environ.get("EM_NODE", "http://localhost:8000")
TOKEN = os.environ.get("EM_DEV_TOKEN", "")
VIEWER = os.environ.get("EM_VIEWER_TOKEN", "")
HERE = os.path.dirname(os.path.abspath(__file__))
FAILURES = []
RESULT = {"phase": PHASE}
STATE = {"step": 0}


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def mod(suffix):
    names = [n for n in sys.modules if n.endswith("." + suffix) and n.startswith("bl_ext.")]
    return sys.modules[names[0]]


def orcid_of(jwt):
    import base64
    payload = jwt.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload))
    return claims.get("orcid") or claims.get("preferred_username") or claims.get("sub")


def view3d():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == 'VIEW_3D'),
               key=lambda a: a.width * a.height)
    return win, area


def popup(panel, units):
    """Draw `panel` as a popup at the top left of the viewport, `units` wide.
    The sidebar is not used: `Region.active_panel_category` is accepted and
    read back in this build, but the region keeps drawing the tab it had
    (measured), so the panel is called where it can be photographed whole."""
    win, area = view3d()
    cls = getattr(bpy.types, panel)
    if getattr(cls, "bl_ui_units_x", None) != units:
        bpy.utils.unregister_class(cls)
        cls.bl_ui_units_x = units
        bpy.utils.register_class(cls)
    region = next(r for r in area.regions if r.type == 'WINDOW')
    with bpy.context.temp_override(window=win, area=area, region=region):
        bpy.ops.wm.call_panel(name=panel, keep_open=True)


def mouse_top_left():
    """Event coordinates are in pixels (measured): 2 per point on this Mac."""
    win, area = view3d()
    region = next(r for r in area.regions if r.type == 'WINDOW')
    win.event_simulate(type='MOUSEMOVE', value='NOTHING',
                       x=region.x + 140, y=region.y + region.height - 100)


def close_popup():
    win, _area = view3d()
    win.event_simulate(type='ESC', value='PRESS')


def shot(name):
    win, area = view3d()
    path = os.path.join(OUT, name)
    with bpy.context.temp_override(window=win, area=area):
        bpy.ops.screen.screenshot_area(filepath=path)
    check(f"screenshot {name}", os.path.isfile(path), path)


def setup():
    from s3dgraphy.nodes.resource_node import ResourceNode  # noqa: F401
    work = tempfile.mkdtemp(prefix="em-r2i1-")
    RESULT["work"] = work
    copy = os.path.join(work, "r2i1.em.json")
    shutil.copyfile(os.path.join(HERE, "fixtures", "emtools_cb25e71_dev23.em.json"), copy)
    os.makedirs(os.path.join(work, "DosCo"))
    with open(os.path.join(work, "DosCo", "D.01.jpg"), "wb") as fh:
        fh.write(os.urandom(4000))
    with open(os.path.join(work, "out.glb"), "wb") as fh:
        fh.write(os.urandom(9000))
    scene = bpy.context.scene
    em = scene.em_tools
    em.mode_em_advanced = True
    while len(em.graphml_files):
        em.graphml_files.remove(0)
    esito = getattr(bpy.ops, "import").em_emjson(filepath=copy)
    check("the fixture graph loads", esito == {"FINISHED"}, repr(esito))
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene.rm_list.clear()
    for name, node_id, x in (("M_rm_object", "M_model", 0), ("T_rm_object", "T_model", 2)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, 0))
        obj = bpy.context.active_object
        obj.name = name
        item = scene.rm_list.add()
        item.name = obj.name
        item.node_id = node_id
        item.object_exists = True
    bpy.ops.mesh.primitive_cube_add(size=0.3, location=(4, 0, 0))
    bpy.context.active_object.name = "Decoration"


def no_backup_prompt():
    """The .blend backup is offered after a bring in a dialog: not in a shot."""
    cls = bpy.types.EM_OT_room_bring_go
    bpy.utils.unregister_class(cls)
    cls.__annotations__["offer_blend"] = bpy.props.BoolProperty(default=False)
    bpy.utils.register_class(cls)


#: (file, panel, width in UI units) — photographed in this order, as the owner
SHOTS_OWNER = (("emtools_r2_{}_models.png", "VIEW3D_PT_RM_Manager", 26),
               ("emtools_r2_{}_files.png", "EM_PT_resources", 26),
               ("emtools_i1_{}_sync_owner.png", "EMSHOT_PT_sync_room", 26))


def room_part_panel():
    """The Sync panel in a room is about as tall as the screen, and a popup
    taller than the window does not open (measured). So the room shots draw
    the SAME methods of the Sync panel from the mode to the room section — the
    refusals, the room, the scene check — and leave out «Where this Blender
    is»."""
    base = bpy.types.VIEW3D_PT_em_sync

    class EMSHOT_PT_sync_room(base):
        bl_idname = "EMSHOT_PT_sync_room"
        bl_label = "EMStudio Sync (room)"
        bl_ui_units_x = 26

        def draw(self, context):
            ops = mod("sync_manager.operators")
            mode = ops.session_mode(context)
            self._modo(self.layout, context, mode, ops.is_running())
            self._rifiuti(self.layout)
            if mode == ops.MODE_HUB:
                self._in_stanza(self.layout, context, ops.room_status(context))

    class EMSHOT_PT_sync_full(base):
        bl_idname = "EMSHOT_PT_sync_full"
        bl_label = "EMStudio Sync"
        bl_ui_units_x = 26

        def draw(self, context):
            base.draw(self, context)

    bpy.utils.register_class(EMSHOT_PT_sync_room)
    bpy.utils.register_class(EMSHOT_PT_sync_full)


def as_viewer():
    """The owner makes `viewer` a viewer of the room; Blender comes back in as
    `viewer` and tries one edit, which the room refuses."""
    win, area = view3d()
    room_id = RESULT["room_id"]
    req = urllib.request.Request(
        f"{NODE}/v1/rooms/{room_id}/members/{orcid_of(VIEWER)}",
        data=json.dumps({"role": "viewer"}).encode(), method="PUT",
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as answer:
        check("viewer added to the room", answer.status == 200, str(answer.status))
    ops = mod("sync_manager.operators")
    ops.leave_room()
    mod("sync_manager.room").set_room(NODE, room_id, VIEWER)
    bpy.context.scene.em_room_id = room_id
    with bpy.context.temp_override(window=win, area=area):
        esito = bpy.ops.em.room_join()
    sess = mod("sync_manager.room_session").SESSION
    check("viewer joined", sess.joined, repr(esito))
    RESULT["viewer_role"] = sess.role
    RESULT["viewer_can_write"] = sess.can_write
    if os.environ.get("R2I1_TRY_EDIT", "1") == "1":
        ops.emit_op({"op": "update_field", "node_id": "doc-1",
                     "field": "description", "value": "tried by a viewer"})


def step():
    win, area = view3d()
    s = STATE["step"]
    STATE["step"] += 1
    try:
        if s == 0:
            with bpy.context.temp_override(window=win, area=area):
                bpy.ops.screen.screen_full_area()
            return 0.5
        if s == 1:
            win, area = view3d()
            area.spaces.active.overlay.show_overlays = False
            close_popup()                       # the splash, if any
            setup()
            room_cfg = mod("sync_manager.room")
            bpy.context.scene.em_room_url = NODE
            room_cfg.set_room(NODE, None, TOKEN)
            no_backup_prompt()
            room_part_panel()
            name = f"T-R2I1 {PHASE} {int(time.time())}"
            with bpy.context.temp_override(window=win, area=area):
                esito = bpy.ops.em.room_bring(name=name, confirm=True)
            check("bring: FINISHED", esito == {"FINISHED"}, repr(esito))
            sess = mod("sync_manager.room_session").SESSION
            RESULT["room_id"] = sess.room_id
            check("in the room as its owner", sess.joined, repr(sess.role))
            # one edit as the owner: the sync line counts the room's answer
            mod("sync_manager.operators").emit_op(
                {"op": "update_field", "node_id": "doc-1", "field": "description",
                 "value": "an edit from Blender"})
            bpy.ops.em.files_check()
            fs = mod("sync_manager.file_states")
            RESULT["files"] = [{k: r.get(k) for k in ("id", "name", "state")}
                               for r in fs.ULTIMI["results"]]
            STATE["queue"] = [(f.format(PHASE), p, u) for f, p, u in SHOTS_OWNER]
            if VIEWER:
                STATE["queue"] += [("viewer", None, 0),
                                   (f"emtools_i1_{PHASE}_sync_viewer.png",
                                    "EMSHOT_PT_sync_room", 26)]
            STATE["queue"] += [("leave", None, 0),
                               (f"emtools_i1_{PHASE}_sync_outside.png",
                                "EMSHOT_PT_sync_full", 26)]
            return 1.0
        # the queue: move the mouse, call the panel, photograph, close
        queue = STATE["queue"]
        if not queue:
            finish()
        name, panel, units = queue[0]
        phase = STATE.get("phase", "move")
        if panel is None:
            queue.pop(0)
            if name == "leave":
                mod("sync_manager.operators").leave_room()
                return 1.5
            as_viewer()
            return 3.0
        if phase == "move" and name.startswith("emtools_i1_"):
            sess = mod("sync_manager.room_session").SESSION
            RESULT[name] = {"sent": sess.sent_ops, "answered": sess.answered_ops,
                            "refused": sess.refused_ops}
        if phase == "move":
            mouse_top_left()
            STATE["phase"] = "call"
            return 0.4
        if phase == "call":
            popup(panel, units)
            STATE["phase"] = "shot"
            return 1.2
        shot(name)
        close_popup()
        queue.pop(0)
        STATE["phase"] = "move"
        return 0.6
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check(f"step {s}", False, repr(exc))
        finish()
    return None


def finish():
    try:
        mod("sync_manager.operators").leave_room()
    except Exception:  # noqa: BLE001
        pass
    RESULT["failures"] = FAILURES
    with open(os.path.join(OUT, f"r2i1_{PHASE}.json"), "w") as fh:
        json.dump(RESULT, fh, indent=1, default=str)
    print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
    sys.stdout.flush()
    os._exit(1 if FAILURES else 0)


if not TOKEN:
    print("[SMOKE] aborting: set EM_DEV_TOKEN (dev-stack/token.sh)")
    sys.exit(1)
bpy.app.timers.register(step, first_interval=1.5)
