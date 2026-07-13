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

        box = layout.box()
        if running:
            box.label(text=f"Listening on ws://localhost:{context.scene.em_sync_port}",
                      icon="URL")
            box.label(text=f"Clients connected: {ops.client_count()}", icon="LINKED")
        else:
            box.label(text="Server off — EMStudio can't connect", icon="UNLINKED")


def register():
    bpy.utils.register_class(VIEW3D_PT_em_sync)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_em_sync)
