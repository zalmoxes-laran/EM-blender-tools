"""Panel for the EMStudio live-sync bridge (tab "EM")."""

from __future__ import annotations

import bpy  # type: ignore

from . import operators as ops


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

        row = layout.row()
        row.prop(context.scene, "em_sync_port", text="Port")
        row.enabled = not running

        layout.operator(
            "em.sync_toggle",
            text="Stop Sync" if running else "Start Sync",
            icon="RADIOBUT_ON" if running else "RADIOBUT_OFF",
            depress=running,
        )

        # MODES1 · the mirror of EMStudio's control: what THIS side does on the
        # channel. Only while running — a control over a channel that is not
        # there is furniture.
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
            box.prop(context.scene, "em_accept_commands", text="Accept commands from EMStudio")
            if context.scene.em_accept_commands:
                box.label(text="EMStudio may model proxies / import geometry here.",
                          icon="CHECKMARK")
            else:
                box.label(text="Commands are refused (and EMStudio is told).",
                          icon="LOCKED")

        box = layout.box()
        if running:
            box.label(text=f"Listening on ws://localhost:{context.scene.em_sync_port}",
                      icon="URL")
            box.label(text=f"Clients connected: {ops.client_count()}", icon="LINKED")
        else:
            box.label(text="Server off — EMStudio can't connect", icon="UNLINKED")

        # P4.4 · the other role: this Blender as a CLIENT of a room. Separate
        # box because it is a different question — the one above is "who may
        # connect to me", this one is "where do I go".
        status = ops.room_status(context)
        room_box = layout.box()
        room_box.label(text="Room (em-server)", icon="WORLD")
        col = room_box.column(align=True)
        col.enabled = not status["joined"]
        col.prop(context.scene, "em_room_url", text="Server")
        col.prop(context.scene, "em_room_id", text="Room")
        room_box.operator(
            "em.room_join",
            text="Leave room" if status["joined"] else "Join room…",
            icon="UNLINKED" if status["joined"] else "LINKED",
            depress=status["joined"])
        if status["joined"]:
            room_box.label(text=f"In {status['room_id']} · "
                                f"{status['members']} present", icon="COMMUNITY")
            if status.get("author"):
                room_box.label(text=f"Publishing as {status['author']}", icon="USER")
            else:
                room_box.label(text="No identity in the token: edits are dated, "
                                    "not signed", icon="INFO")
        if status.get("error"):
            room_box.label(text=str(status["error"])[:60], icon="ERROR")


def register():
    bpy.utils.register_class(VIEW3D_PT_em_sync)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_em_sync)
