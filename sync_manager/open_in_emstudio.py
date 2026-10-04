"""U7 · «Open in EMStudio»: from a read-only view of Blender (the paradata of
a unit) to the place where it is edited.

Measured on 4 Oct 2026: EMStudio has no link that names a NODE —
`stratigraph://open?server=&room=` opens a room (frontend/src/handoff.ts) and
the desktop's file association is `.emj` only — but the Sidecar does: the
`select` envelope EMtools already sends when an object is selected lands on the
node in EMStudio. So, in this order:

1. the Sidecar is on → EMStudio selects the unit;
2. this Blender is in a room → the room opens in EMStudio (the unit is to be
   picked there: the link cannot name it);
3. otherwise → EMStudio is started, and the sentence says how to land on the
   unit (open the graph's file, start the Sidecar).
"""

import json
import subprocess
import sys
import urllib.parse
from typing import Dict, Optional


def plan(*, sidecar_running: bool, room: Dict[str, Optional[str]], unit_name: str,
         graph_path: str = "") -> Dict[str, str]:
    """Pure: ``{way, url, sentence}`` — what «Open in EMStudio» does now."""
    if sidecar_running:
        return {"way": "sidecar", "url": "",
                "sentence": f"EMStudio selects {unit_name} (Sidecar): edit its paradata there"}
    if room.get("base_url") and room.get("room_id"):
        q = urllib.parse.urlencode({"server": room["base_url"], "room": room["room_id"]})
        return {"way": "room", "url": f"stratigraph://open?{q}",
                "sentence": f"the room {room['room_id']} opens in EMStudio: pick {unit_name} there "
                            f"(the link cannot name a unit yet)"}
    tail = f" and open {graph_path}" if graph_path else ""
    return {"way": "app", "url": "",
            "sentence": f"EMStudio starts{tail}; to land on {unit_name} by itself, "
                        f"turn the Sidecar on (EM Stanza ▸ Stanza)"}


def _operator_classes():  # pragma: no cover — bpy
    import bpy  # type: ignore

    class EM_OT_open_in_emstudio(bpy.types.Operator):
        """Edit this in EMStudio: it selects the unit (Sidecar), opens the room,
        or starts — Blender only reads the paradata"""
        bl_idname = "em.open_in_emstudio"
        bl_label = "Open in EMStudio"
        bl_options = {'REGISTER'}

        node_id: bpy.props.StringProperty()  # type: ignore
        unit_name: bpy.props.StringProperty()  # type: ignore

        def execute(self, context):
            from . import operators as sync
            from . import room as room_cfg
            em = context.scene.em_tools
            entry = em.graphml_files[em.active_file_index] if len(em.graphml_files) else None
            path = bpy.path.abspath(entry.graphml_path) if entry is not None and entry.graphml_path else ""
            p = plan(sidecar_running=sync.is_running(), room=room_cfg.room(),
                     unit_name=self.unit_name or self.node_id, graph_path=path)
            try:
                if p["way"] == "sidecar":
                    sync._server.broadcast(json.dumps(sync.envelope("select", {"node_id": self.node_id},
                                                                    source=sync._SOURCE)))
                elif p["way"] == "room":
                    bpy.ops.wm.url_open(url=p["url"])
                elif sys.platform == "darwin" and not bpy.app.background:
                    subprocess.Popen(["open", "-a", "EMStudio"])
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
