"""EM ▸ Export (T1, E.D. 5 Oct 2026): the exporters as dialogs of the header menu.

Exports are rare gestures, and a file's: they left the tabs. The providers of
the registry stay the engine — each one still owns its `poll` and its `draw` —
and a dialog draws ONE of them, where the «Export Manager» panel drew them all
(that panel is in `_dead_code/export_manager/panel.py`).

The menu offers Tabular, RDF and PyArchInit (and Export statistics, from
`em_statistics/dialog.py`). Heriverse is not here: nothing is re-exported for
it (H4) — the Publication Deck says what it will find, on the node or in the
package on disk it writes.
"""

import bpy
from bpy.types import Menu, Operator

from .registry import get_providers

#: the providers EM ▸ Export offers, in this order (Heriverse: the Deck, H4)
MENU_PROVIDERS = ("tabular", "rdf", "pyarchinit")


def _provider(provider_id):
    return next((p for p in get_providers() if p.id == provider_id), None)


class EM_OT_export_dialog(Operator):
    """Open one exporter as a dialog"""

    bl_idname = "em.export_dialog"
    bl_label = "Export"
    bl_options = {'REGISTER'}

    provider: bpy.props.StringProperty(default="")  # type: ignore

    @classmethod
    def description(cls, context, properties):
        p = _provider(properties.provider)
        return (p.help_text if p and p.help_text else "Open this exporter")

    def invoke(self, context, event):
        if _provider(self.provider) is None:
            self.report({'ERROR'}, f"no exporter '{self.provider}'")
            return {'CANCELLED'}
        return context.window_manager.invoke_popup(self, width=460)

    def draw(self, context):
        layout = self.layout
        p = _provider(self.provider)
        if p is None:
            return
        if context.mode != 'OBJECT':
            from ..ui_helpers import draw_objectmode_required_box
            draw_objectmode_required_box(layout)
            return
        head = layout.row()
        head.label(text=p.label, icon=p.icon)
        if p.help_url:
            help_op = head.operator("em.help_popup", text="", icon='QUESTION')
            help_op.title = p.help_title or "Help"
            help_op.text = p.help_text or ""
            help_op.url = p.help_url
            help_op.project = 'em_tools'
        if not p.poll(context):
            layout.label(text="Not available for what is loaded now.", icon='INFO')
            return
        p.draw(layout.box(), context)

    def execute(self, context):
        return {'FINISHED'}


class EM_MT_export(Menu):
    """EM ▸ Export — the exporters, each as a dialog."""

    bl_idname = "EM_MT_export"
    bl_label = "Export"
    bl_description = "Export the study to a file: tables, RDF, PyArchInit, statistics"

    def draw(self, context):
        layout = self.layout
        for pid in MENU_PROVIDERS:
            p = _provider(pid)
            if p is None:
                continue
            op = layout.operator("em.export_dialog", text=f"{p.label}…", icon=p.icon)
            op.provider = pid
        layout.separator()
        layout.operator("em.export_statistics_dialog", text="Export statistics…",
                        icon='MESH_DATA')


classes = (EM_OT_export_dialog, EM_MT_export)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
