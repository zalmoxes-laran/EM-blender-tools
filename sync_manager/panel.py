"""Panel for the live-sync bridge and the room (tab "EM").

**One control, three states, and the state is DERIVED.**

EMStudio has had this for a while: a session is Standalone, Sidecar or Hub, and
those are exclusive — one thing at a time, shown as one thing. Here there used
to be two boxes that did not know about each other ("EMStudio Sync" with a
Start/Stop, "Room" with a Join) and no way to say "neither", which is the state
Blender is in most of the time.

The design turn behind the change (`EM_design_room-come-workspace` §3): the
**room is the primitive**, the mode **follows from belonging**, and the EM Data
Tree becomes the room's container. So the panel does not offer a mode to pick —
it *reports* the one the session is in, and the buttons underneath are the acts
that change it (serve the bridge; join a room). Join a room and the mode becomes
Hub by itself; leave and it goes back to Standalone. A mode you can set
independently of what is true is a mode that will eventually lie.

**The names are EMStudio's**: Standalone · Sidecar · Hub. One vocabulary across
the two applications — somebody switching between them should not have to learn
that "Room" here is "Hub" there. The *place* stays a room ("in {room} · N
present"), the *mode* is Hub: the room is where the work is, the hub is the
service that holds it.
"""

from __future__ import annotations

import bpy  # type: ignore

from . import operators as ops

#: label · icon · what it means, in the words the tooltip uses.
_MODES = (
    (ops.MODE_STANDALONE, "Standalone", "MESH_CIRCLE",
     "This Blender alone: no bridge served, no room joined."),
    (ops.MODE_SIDECAR, "Sidecar", "LINKED",
     "Paired with EMStudio over the local bridge — two screens, one person."),
    (ops.MODE_HUB, "Hub", "WORLD",
     "In a room on an StratiGraph Server: the EM Data Tree is that room's container."),
)


class VIEW3D_PT_em_sync(bpy.types.Panel):
    bl_label = "EMStudio Sync"
    bl_idname = "VIEW3D_PT_em_sync"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        running = ops.is_running()
        status = ops.room_status(context)
        mode = ops.session_mode(context)

        # ── the three states, at the top ────────────────────────────────────
        # Drawn as a segmented row of the three, with the current one pressed.
        # They are NOT buttons that set the mode: the mode is derived, and a
        # control that pretended otherwise would let somebody choose "Hub"
        # without being in a room.
        row = layout.row(align=True)
        for value, label, icon, _tip in _MODES:
            cell = row.row(align=True)
            cell.enabled = False          # a report, not a switch
            cell.operator("em.mode_explain", text=label, icon=icon,
                          depress=(value == mode)).mode = value
        current = next(m for m in _MODES if m[0] == mode)
        layout.label(text=current[3], icon="INFO")

        # ── in a room: what the tree is showing, and what you may do ────────
        if mode == ops.MODE_HUB:
            box = layout.box()
            box.label(text=f"In {status['room_id']} · "
                           f"{status['members']} present", icon="COMMUNITY")
            if status.get("author"):
                box.label(text=f"As {status['author']}", icon="USER")
            else:
                box.label(text="No identity in the token: edits are dated, "
                               "not signed", icon="INFO")
            # THE ROLE, believed rather than assumed. A panel that offered
            # editing the server refuses would read as a broken addon instead of
            # as a study somebody let you read (same rule as EMStudio's badge).
            role = status.get("role")
            if status.get("can_write") is False:
                box.label(text=f"Read-only here ({role or 'viewer'}): the room "
                               f"refuses edits from this Blender", icon="LOCKED")
            elif role:
                box.label(text=f"Role: {role}", icon="CHECKMARK")
            box.label(text="The EM Data Tree is this room's container.",
                      icon="OUTLINER")
            # DP-76, consuming half. An ACTION and not a consequence of joining:
            # adopting a document is reading, downloading somebody's meshes into
            # your file is more. The toggle beside it is for whoever wants it at
            # adoption time — a decision they made, not one made for them.
            geo = box.column(align=True)
            geo.operator("em.materialise_geometry",
                         text="Materialise geometry from the store",
                         icon="IMPORT")
            geo.prop(context.scene, "em_materialise_on_adopt",
                     text="…also when adopting")
            geo.label(text="Only what lives in the store; an embargoed model is "
                           "skipped with a reason.", icon="INFO")

            # ── the .blend safety archive ───────────────────────────────────
            #
            # The other direction, and a different KIND of thing: the block
            # above publishes an asset of record, this keeps an opaque copy of
            # the workshop. Drawn in the room block because it goes through the
            # room's auth, and folded into its own box because it is not part of
            # the study — nothing here is citable.
            safe = box.box()
            safe.label(text="Blend backups (safety, opaque)", icon="FILE_BACKUP")
            head = safe.row(align=True)
            head.operator("em.blend_backup_archive",
                          text="Archive this .blend", icon="EXPORT")
            head.operator("em.blend_backup_list", text="", icon="FILE_REFRESH")
            if bpy.data.is_dirty:
                safe.label(text="Unsaved changes: a snapshot keeps the file on "
                                "disk.", icon="ERROR")
            try:
                from . import backups as _backups
                snapshots, why = _backups.listing(), _backups.note()
            except Exception:  # noqa: BLE001 — a list that will not read is empty
                snapshots, why = [], ""
            if why:
                safe.label(text=why, icon="ERROR")
            for snap in snapshots[:8]:
                line = safe.row(align=True)
                sha = str(snap.get("sha256") or "")
                name = str(snap.get("label") or snap.get("filename") or "")
                line.label(text=f"{(name or sha[:12])[:28]} · "
                                f"{str(snap.get('created_at') or '')[:10]}")
                line.operator("em.blend_backup_restore", text="",
                              icon="IMPORT").sha256 = sha
            if snapshots:
                safe.label(text="Restore lands BESIDE this file — it never "
                                "replaces what you are working in.", icon="INFO")
            else:
                safe.label(text="Yours only: a room-mate's working file is not "
                                "yours to read.", icon="INFO")

        # ── the acts that change the mode ──────────────────────────────────
        acts = layout.box()
        acts.label(text="Where this Blender is", icon="PREFERENCES")

        row = acts.row()
        row.prop(context.scene, "em_sync_port", text="Port")
        row.enabled = not running
        acts.operator(
            "em.sync_toggle",
            text="Stop serving the bridge" if running else "Serve the bridge (Sidecar)",
            icon="RADIOBUT_ON" if running else "RADIOBUT_OFF",
            depress=running,
        )
        if running:
            acts.label(text=f"ws://localhost:{context.scene.em_sync_port} · "
                            f"{ops.client_count()} client(s)", icon="URL")

        # THE LINK FIRST, because it is the way in that needs nothing typed:
        # `stratigraph://open?server=&room=` carries the place, EMtools signs in
        # for itself, and the fields below become the fallback rather than the
        # route. Offered above them deliberately — a panel that showed three
        # fields first would teach people to fill them.
        if not status["joined"]:
            acts.operator("em.room_open_link", text="Open room from link…",
                          icon="URL")

        col = acts.column(align=True)
        col.enabled = not status["joined"]
        col.label(text="…or by hand:", icon="GREASEPENCIL")
        col.prop(context.scene, "em_room_url", text="Server")
        # WHERE IS IT · a saved list (this installation's, not the .blend's) and
        # a probe. A URL somebody typed is a hope; `/v1/health` makes it a fact,
        # and the failures are the useful half. mDNS browsing is absent and NOT
        # simulated — Blender's Python has no `zeroconf` — so what is offered is
        # a direct probe of the addresses worth trying, and the Bonjour name of
        # the other machine, which the OS resolves on its own.
        find = col.row(align=True)
        find.operator("em.server_discover", text="Find", icon="VIEWZOOM")
        find.operator("em.server_probe", text="Probe", icon="CHECKMARK")
        try:
            from . import servers as _servers
            known = _servers.saved()
        except Exception:  # noqa: BLE001 — a list that will not read is empty
            known = []
        for entry in known[:6]:
            line = col.row(align=True)
            line.operator("em.server_use", text=entry.get("label") or entry["url"],
                          icon="WORLD").url = entry["url"]
            line.operator("em.server_forget", text="", icon="X").url = entry["url"]
        col.prop(context.scene, "em_room_id", text="Room")
        acts.operator(
            "em.room_join",
            text="Leave the room" if status["joined"] else "Join a room (Hub)…",
            icon="UNLINKED" if status["joined"] else "LINKED",
            depress=status["joined"])
        # ROUND-TRIP (emit-only): the same room, in EMStudio. Only while joined —
        # off a room it would open nothing.
        if status["joined"]:
            acts.operator("em.room_open_elsewhere",
                          text="Open room in EMStudio", icon="WINDOW")
        if status.get("error"):
            acts.label(text=str(status["error"])[:60], icon="ERROR")

        # ── what THIS side does on the channel (MODES1) ────────────────────
        # Only while there is a channel to govern: a control over a channel that
        # is not there is furniture.
        if running:
            col = layout.column(align=True)
            col.label(text="Sync direction")
            col.prop(context.scene, "em_sync_direction", expand=True)
            col.label(text="Alone on two screens: Both.", icon="INFO")
            col.label(text="Someone else working too: Off or one way.")

            # CMD1 · consent for the command channel — a separate, stronger
            # permission than the selection mirror: this one lets EMStudio
            # MODEL IN THIS SCENE. Off by default, and never implied by the
            # connection being up.
            box = layout.box()
            box.prop(context.scene, "em_accept_commands",
                     text="Accept commands from EMStudio")
            if context.scene.em_accept_commands:
                box.label(text="EMStudio may model proxies / import geometry here.",
                          icon="CHECKMARK")
            else:
                box.label(text="Commands are refused (and EMStudio is told).",
                          icon="LOCKED")


class EM_OT_mode_explain(bpy.types.Operator):
    """The mode chips are a REPORT, and this is what they would say if they
    could be pressed. Registered because a disabled `operator()` still needs
    something to point at — and because the sentence belongs somewhere a user
    can reach rather than only in a comment."""

    bl_idname = "em.mode_explain"
    bl_label = "What this mode means"
    bl_description = ("Standalone / Sidecar / Hub — the mode follows what is "
                      "true: serve the bridge to be a Sidecar, join a room to "
                      "be in Hub. It is not a switch.")

    mode: bpy.props.StringProperty(default="")  # type: ignore

    def execute(self, context):
        tip = next((m[3] for m in _MODES if m[0] == self.mode), "")
        self.report({"INFO"}, tip or self.bl_description)
        return {"FINISHED"}


def register():
    bpy.utils.register_class(EM_OT_mode_explain)
    bpy.utils.register_class(VIEW3D_PT_em_sync)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_em_sync)
    bpy.utils.unregister_class(EM_OT_mode_explain)
