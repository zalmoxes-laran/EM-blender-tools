"""U7 · «Open in EMStudio»: from a read-only view of Blender (the paradata of
a unit) to the place where it is edited — landing ON the unit, or not at all.

E4 (decisions of E.D., 4 Oct 2026): `stratigraph://open` carries the node,
`&node=<id>`, and EMStudio lands on it — the unit selected, in the Inspector,
the view centred. So there are two ways that open the unit, in this order:

1. the Sidecar is on and EMStudio is connected to it → the `select` envelope;
2. this Blender is in a room → `stratigraph://open?server=…&room=…&node=…`.

Otherwise no way of reaching EMStudio opens the unit (a file association
opens a file, not a node), so the button stays grey and its sentence says how
to turn it on.
"""

import json
import urllib.parse
from typing import Dict, Optional

#: why the button is grey, and what turns it on
OFF = ("EMStudio opens a unit through the Sidecar or a room: turn the Sidecar on "
       "(EM ▸ Where you work ▸ Work with EMStudio) and connect EMStudio to it, "
       "or work in a collaborative room")


def plan(*, sidecar_clients: int, room: Dict[str, Optional[str]], unit_name: str,
         node_id: str = "") -> Dict[str, str]:
    """Pure: ``{way, url, sentence}`` — what «Edit in EMStudio» does now.
    ``way`` is ``sidecar``, ``room`` or ``off`` (the button is grey)."""
    if sidecar_clients > 0:
        return {"way": "sidecar", "url": "",
                "sentence": f"EMStudio selects {unit_name} (Sidecar): edit its paradata there"}
    if room.get("base_url") and room.get("room_id"):
        q = {"server": room["base_url"], "room": room["room_id"]}
        if node_id:
            q["node"] = node_id
        return {"way": "room", "url": f"stratigraph://open?{urllib.parse.urlencode(q)}",
                "sentence": f"EMStudio opens the room {room['room_id']} on {unit_name}"}
    return {"way": "off", "url": "", "sentence": OFF}


def _operator_classes():  # pragma: no cover — bpy
    import bpy  # type: ignore

    class EM_OT_open_in_emstudio(bpy.types.Operator):
        """Edit this unit in EMStudio, landing on it: through the Sidecar, or the
        room's link with its node — Blender only reads the paradata"""
        bl_idname = "em.open_in_emstudio"
        bl_label = "Open in EMStudio"
        bl_options = {'REGISTER'}

        node_id: bpy.props.StringProperty()  # type: ignore
        unit_name: bpy.props.StringProperty()  # type: ignore

        @staticmethod
        def _plan(unit_name="", node_id=""):
            from . import operators as sync
            from . import room as room_cfg
            clients = sync.client_count() if sync.is_running() else 0
            return plan(sidecar_clients=clients, room=room_cfg.room(),
                        unit_name=unit_name, node_id=node_id)

        @classmethod
        def poll(cls, context):
            if cls._plan()["way"] == "off":
                cls.poll_message_set(OFF)
                return False
            return True

        def execute(self, context):
            from . import operators as sync
            p = self._plan(self.unit_name or self.node_id, self.node_id)
            #: the link, for whoever asks what was opened (the smoke T-E4)
            context.window_manager["em_last_emstudio_link"] = p["url"]
            try:
                if p["way"] == "sidecar":
                    sync._server.broadcast(json.dumps(sync.envelope("select", {"node_id": self.node_id},
                                                                    source=sync._SOURCE)))
                elif p["way"] == "room":
                    if not bpy.app.background:
                        bpy.ops.wm.url_open(url=p["url"])
                else:
                    self.report({'ERROR'}, p["sentence"])
                    return {'CANCELLED'}
            except Exception as exc:  # noqa: BLE001
                self.report({'ERROR'}, f"EMStudio not reached: {exc}")
                return {'CANCELLED'}
            self.report({'INFO'}, p["sentence"])
            return {'FINISHED'}

    return (EM_OT_open_in_emstudio,)


_CLASSES: tuple = ()


def register():  # pragma: no cover — bpy
    import bpy  # type: ignore
    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():  # pragma: no cover — bpy
    import bpy  # type: ignore
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
