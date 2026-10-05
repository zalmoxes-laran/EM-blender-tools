"""D1 (MICRO-DOVE-LAVORI, 5 Oct 2026) · two operators nobody drew.

`em.sync_toggle` (was in `sync_manager/operators.py`) and `em.mode_explain`
(was in `sync_manager/panel.py`): registered, called by no panel, menu, script
or test (measured by grep over EM-blender-tools and EMStudio on 5 Oct 2026).
The mode is changed by the gestures of «Where you work» and by EM ▸ Mode
(`em.set_mode`), which is what the toggle had become a shortcut for.
"""

import bpy  # type: ignore

from ...sync_manager.operators import (MODE_SIDECAR, MODE_STANDALONE,  # noqa: F401
                                       _dichiara, applica_modo, is_running)


class EM_OT_sync_toggle(bpy.types.Operator):
    bl_idname = "em.sync_toggle"
    bl_label = "Toggle the Room sync"
    bl_description = "Start/stop the WebSocket server EMStudio connects to for live selection sync"

    def execute(self, context):
        # C4 · UNA SOLA STRADA. Questo bottone c'era prima della dichiarazione
        # del modo, e lasciarlo accendere il ponte per conto suo vorrebbe dire
        # due meccanismi per lo stesso fatto — cioè la coabitazione con la
        # stanza che C4 esiste per togliere. Adesso è una scorciatoia per la
        # stessa regola, e la regola annuncia, spegne l'altra metà e dichiara.
        verso = MODE_STANDALONE if is_running() else MODE_SIDECAR
        esito = applica_modo(context, verso)
        if not esito["ok"]:
            self.report({"ERROR"}, esito["message"])
            return {"CANCELLED"}
        _dichiara(context, esito["mode"])
        self.report({"INFO"}, esito["message"])
        return {"FINISHED"}



class EM_OT_mode_explain(bpy.types.Operator):
    """C4 · Restava da quando i chip erano un REFERTO: adesso sono premibili e
    chiamano `em.set_mode`. Tenuto registrato perché la frase che diceva è
    diventata la descrizione di quell'operatore, e perché un `bl_idname` che
    sparisce rompe un keymap di chi l'aveva legato."""

    bl_idname = "em.mode_explain"
    bl_label = "What this mode means"
    bl_description = ("Standalone / Sidecar / Room — choosing one DOES it: "
                      "Sidecar starts the bridge, Standalone stops it, Room "
                      "needs a room you have already joined.")

    mode: bpy.props.StringProperty(default="")  # type: ignore

    def execute(self, context):
        tip = next((m[3] for m in _MODES if m[0] == self.mode), "")
        self.report({"INFO"}, tip or self.bl_description)
        return {"FINISHED"}


