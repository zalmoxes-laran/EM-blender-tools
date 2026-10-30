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

MICRO una verità (13 Oct 2026): this is THE «Open in EMStudio» — of the Room
panel too, where `em.room_open_elsewhere` (the link asked of the node, always
through `webbrowser`) was a second one. In a room it opens the desktop EMStudio
when this computer has it (an app that answers ``stratigraph://``), and the
web EMStudio the node offers otherwise.
"""

import json
import os
import sys
import urllib.parse
from typing import Dict, Optional

#: why the button is grey, and what turns it on
OFF = ("EMStudio opens a unit through the Sidecar or a room: turn the Sidecar on "
       "(EM ▸ Mode ▸ With EMStudio) and connect EMStudio to it, "
       "or work in a collaborative room")


def plan(*, sidecar_clients: int, room: Dict[str, Optional[str]], unit_name: str = "",
         node_id: str = "", desktop: bool = True, web: str = "") -> Dict[str, str]:
    """Pure: ``{way, url, sentence}`` — what «Open in EMStudio» does now.
    ``way`` is ``sidecar``, ``room`` (the desktop app, ``stratigraph://``),
    ``web`` (the node's web EMStudio, `web` its link) or ``off`` (grey)."""
    if sidecar_clients > 0:
        return {"way": "sidecar", "url": "",
                "sentence": f"EMStudio selects {unit_name} (Sidecar): edit its paradata there"}
    if room.get("base_url") and room.get("room_id"):
        on = f" on {unit_name}" if unit_name else ""
        if not desktop and web:
            return {"way": "web", "url": web,
                    "sentence": f"EMStudio for the web opens the room {room['room_id']}{on}"}
        q = {"server": room["base_url"], "room": room["room_id"]}
        if node_id:
            q["node"] = node_id
        return {"way": "room", "url": f"stratigraph://open?{urllib.parse.urlencode(q)}",
                "sentence": f"EMStudio opens the room {room['room_id']}{on}"}
    return {"way": "off", "url": "", "sentence": OFF}


def desktop_present() -> bool:  # pragma: no cover — reads this computer
    """Does this computer have an EMStudio that answers ``stratigraph://``?
    macOS: the app in an Applications folder; Windows: the scheme in the
    registry; Linux: a handler xdg knows. Not sure → yes (the scheme is the
    door that names the node)."""
    try:
        if sys.platform == "darwin":
            return any(os.path.isdir(os.path.join(d, "EMStudio.app"))
                       for d in ("/Applications", os.path.expanduser("~/Applications")))
        if sys.platform.startswith("win"):
            import winreg  # type: ignore
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "stratigraph"))
            return True
        import subprocess
        out = subprocess.run(["xdg-mime", "query", "default", "x-scheme-handler/stratigraph"],
                             capture_output=True, text=True, timeout=3)
        return bool(out.stdout.strip())
    except FileNotFoundError:
        return True
    except Exception:  # noqa: BLE001 — a registry without the key: no app
        return False


def web_link() -> str:  # pragma: no cover — asks the node
    """The web EMStudio of the room, as the node says it opens (never a link
    assembled here): `handoff.open_targets` → its browser door. Empty if the
    node offers none."""
    try:
        from . import handoff
        from . import room as room_cfg
        state = room_cfg.room()
        targets = handoff.open_targets(state.get("base_url"), state.get("room_id"),
                                       token=room_cfg._session.get("token"))
        card = ((targets or {}).get("tools") or {}).get("emstudio") or {}
        return str(card.get("browser") or "")
    except Exception:  # noqa: BLE001
        return ""


def _operator_classes():  # pragma: no cover — bpy
    import bpy  # type: ignore

    class EM_OT_open_in_emstudio(bpy.types.Operator):
        """Open in EMStudio — the room, or this unit in it: through the Sidecar,
        the desktop EMStudio if this computer has it, the web one otherwise.
        Nothing is transferred: it is the same room"""
        bl_idname = "em.open_in_emstudio"
        bl_label = "Open in EMStudio"
        bl_options = {'REGISTER'}

        node_id: bpy.props.StringProperty()  # type: ignore
        unit_name: bpy.props.StringProperty()  # type: ignore

        @staticmethod
        def _plan(unit_name="", node_id="", *, ask_web=False):
            from . import operators as sync
            from . import room as room_cfg
            clients = sync.client_count() if sync.is_running() else 0
            desktop = desktop_present()
            return plan(sidecar_clients=clients, room=room_cfg.room(),
                        unit_name=unit_name, node_id=node_id, desktop=desktop,
                        web=web_link() if ask_web and not desktop else "")

        @classmethod
        def poll(cls, context):
            if cls._plan()["way"] == "off":
                cls.poll_message_set(OFF)
                return False
            return True

        def execute(self, context):
            from . import operators as sync
            p = self._plan(self.unit_name or self.node_id, self.node_id, ask_web=True)
            #: the link, for whoever asks what was opened (the smoke T-E4)
            context.window_manager["em_last_emstudio_link"] = p["url"]
            try:
                if p["way"] == "sidecar":
                    sync._server.broadcast(json.dumps(sync.envelope("select", {"node_id": self.node_id},
                                                                    source=sync._SOURCE)))
                elif p["way"] in ("room", "web"):
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
