"""MICRO-BLEND-OFFICINA-2 · who has the .blend open, in the room (E.D.'s
answers of 31 Oct 2026, D7 and D8): EM Tools' half.

A Blender with its interface that opens a .blend of the project while it is
in a room TAKES the file's lease («aperto da ‹persona› su ‹computer› dalle
‹ora›», visible to everyone in the room, EMStudio included); it renews it
every :data:`RENEW_S` from the presence timer; the room lets it lapse after
15 minutes without a sign; it is released when another file is opened, when
Blender closes, or by hand («Release…», with a confirmation — the holder, or
the room's owner, ``force``).

Whoever opens a file somebody else holds works READ-ONLY, and their save
becomes a NEW VERSION bearing their name, never a save over the held file
(``blend_room.readonly_save_name``: ``versions/<stem>@manual-YYYY-MM-DD[-n]-
<person>.blend``). How, in Blender, where a save cannot be refused from a
handler (``save_pre`` cannot cancel) — two things, chosen together:

1. **Ctrl/Cmd+S** is taken by an add-on keymap item (``em.blend_save_guard``):
   read-only, it saves AS the version file; otherwise it is the plain save;
2. at the **first unsaved change** made read-only (the presence timer sees
   ``is_dirty``, every 10 s) the session is saved as the version file at once
   (``save_as_mainfile``, ``copy=False``): from then on EVERY save — the menu,
   the autosave, a script — goes to the version, never to the held file.

What is left: a File ▸ Save from the menu in the ≤ 10 s between the first
change and the timer. Said in the panel and in the report.

Without a room that keeps leases (an older server: ``host_info`` without
``holds``) the local presence (``~/.stratigraph/blender-sessions``) is all
there is, and the panel says «la stanza non tiene ancora le prenotazioni».

The decisions are s3Dgraphy's (``resources.blend_room``, ≥ 1.6.0.dev79).
"""

import os
import platform
import time
from typing import Any, Dict, List, Optional

#: how often a held lease is renewed (blend_room.LEASE_RENEW_S when present)
RENEW_S = 60.0
NO_ROOM_LEASES = "la stanza non tiene ancora le prenotazioni (solo la presenza su questo computer)"
NEEDS_DEV79 = ("the leases of the room need s3dgraphy ≥ 1.6.0.dev79 (the next bundle of EM Tools)")

#: this Blender's view of the open .blend's lease
STATE: Dict[str, Any] = {"key": "", "path": "", "sent": 0.0, "mine": False, "mode": "", "say": "",
                         "lease": None, "switched": "", "person": ""}


def br():
    try:
        from s3dgraphy.resources import blend_room
        return blend_room
    except ImportError:
        return None


# ── pure ─────────────────────────────────────────────────────────────────────

def decide(*, leases: List[Dict[str, Any]], key: str, person: str, host: str, supported: bool,
           joined: bool, now: Optional[float] = None) -> Dict[str, Any]:
    """What this Blender does with the open .blend's lease → ``{mode, say,
    lease, send}``: ``send`` the frame to send (``take`` / ``renew`` / None),
    ``mode`` as ``blend_room.may_write`` (``free``, ``mine``,
    ``mine_elsewhere``, ``readonly``) or ``local`` (no room keeps leases)."""
    B = br()
    if B is None:
        return {"mode": "local", "say": NEEDS_DEV79, "lease": None, "send": None}
    if not joined or not key:
        return {"mode": "local", "say": "", "lease": None, "send": None}
    if not supported:
        return {"mode": "local", "say": NO_ROOM_LEASES, "lease": None, "send": None}
    lease = B.lease_for(leases, key, now)
    got = B.may_write(lease, person=person, host=host, now=now)
    send = None
    if got["mode"] == "free":
        send = "take"
    elif got["mode"] == "mine":
        send = "renew"
    say = got["say"]
    if lease is not None and got["mode"] in ("mine", "readonly", "mine_elsewhere"):
        say = B.lease_label(lease) + ("" if got["mode"] == "mine" else
                                      " — sola lettura: salvare crea una nuova versione col tuo nome")
    return {"mode": got["mode"], "say": say, "lease": lease, "send": send}


# ── Blender ──────────────────────────────────────────────────────────────────

def _bpy():  # pragma: no cover — bpy
    import bpy
    return bpy


def _session():  # pragma: no cover — bpy
    """The joined room session (the active graph's), or None."""
    try:
        from . import room_session as RS
        s = RS.SESSION
        if s is not None and s.joined:
            return s
        for s in RS.sessions():
            if getattr(s, "joined", False):
                return s
    except Exception:  # noqa: BLE001
        pass
    return None


def key_of(context, path: str) -> str:  # pragma: no cover — bpy
    B = br()
    if B is None or not path:
        return ""
    try:
        from .blend_officina import project_root_for
        from .project_files import active_emjson
        root = project_root_for(context, active_emjson(context))
    except Exception:  # noqa: BLE001
        root = os.path.dirname(os.path.dirname(path))
    return B.file_key(path, root)


def tick(context=None, *, headless: bool = False) -> Dict[str, Any]:  # pragma: no cover — bpy
    """Called by the presence timer: take / renew the lease, decide the mode,
    and — read-only with a first change — move the session to its version.
    A background Blender never holds a lease (``headless`` only for a smoke)."""
    bpy = _bpy()
    context = context or bpy.context
    path = bpy.data.filepath
    if bpy.app.background and not headless:
        return STATE
    s = _session()
    if STATE["path"] and STATE["path"] != path:
        release(reason="another file")
    key = key_of(context, path) if path else ""
    person = str(getattr(s, "author", "") or "") if s else ""
    got = decide(leases=list(getattr(s, "leases", []) or []), key=key, person=person,
                 host=platform.node(), supported=bool(getattr(s, "holds_supported", False)),
                 joined=s is not None)
    now = time.time()
    STATE.update(key=key, path=path, mode=got["mode"], say=got["say"], lease=got["lease"], person=person)
    if s is not None and got["send"] == "take" and now - STATE["sent"] > 5:
        if s.send_hold("take", key, host=platform.node()):
            STATE.update(sent=now, mine=True)
    elif s is not None and got["send"] == "renew" and now - STATE["sent"] >= RENEW_S:
        if s.send_hold("renew", key, host=platform.node()):
            STATE.update(sent=now, mine=True)
    if got["mode"] in ("readonly", "mine_elsewhere") and bpy.data.is_dirty and path and not STATE["switched"]:
        try:
            save_as_version(context)
        except Exception as exc:  # noqa: BLE001
            print(f"[lease] read-only save not moved to a version: {exc}")
    return STATE


def release(*, reason: str = "", force: bool = False) -> bool:  # pragma: no cover — bpy
    s = _session()
    key = STATE.get("key") or ""
    ok = False
    if s is not None and key and (STATE.get("mine") or force):
        try:
            import platform as _pl
            ok = s.send_hold("release", key, host=_pl.node(), force=force)
        except Exception:  # noqa: BLE001
            ok = False
    if not force:
        STATE.update(key="", path="", mine=False, sent=0.0, mode="", say="", lease=None)
    return ok


def version_target(context) -> Dict[str, Any]:  # pragma: no cover — bpy
    bpy = _bpy()
    B = br()
    if B is None:
        raise RuntimeError(NEEDS_DEV79)
    path = STATE.get("switched") or bpy.data.filepath
    held = STATE.get("path") or path
    folder = os.path.join(os.path.dirname(held), "versions")
    try:
        existing = os.listdir(folder)
    except OSError:
        existing = []
    return B.readonly_save_name(held, person=STATE.get("person") or os.environ.get("USER", "someone"),
                                existing=existing)


def save_as_version(context) -> str:  # pragma: no cover — bpy
    """The read-only session saved AS a new version with the person's name;
    from now on every save goes there."""
    bpy = _bpy()
    t = version_target(context)
    os.makedirs(t["folder"], exist_ok=True)
    win = getattr(context, "window", None) or (bpy.context.window_manager.windows[0]
                                               if bpy.context.window_manager.windows else None)
    kw = {"filepath": t["path"], "copy": False, "relative_remap": True}
    if win is not None:
        with bpy.context.temp_override(window=win):
            bpy.ops.wm.save_as_mainfile(**kw)
    else:
        bpy.ops.wm.save_as_mainfile(**kw)
    STATE["switched"] = t["path"]
    print(f"[lease] read-only: saved as the version {t['path']}")
    return t["path"]


def _operator_classes():  # pragma: no cover — bpy
    bpy = _bpy()
    from bpy.props import BoolProperty

    class EM_OT_blend_save_guard(bpy.types.Operator):
        """Save: read-only (somebody else has this .blend open in the room), a new version with
        your name; otherwise the plain save"""
        bl_idname = "em.blend_save_guard"
        bl_label = "Save (lease aware)"

        def execute(self, context):
            if STATE.get("mode") in ("readonly", "mine_elsewhere") and not STATE.get("switched"):
                try:
                    p = save_as_version(context)
                except Exception as exc:  # noqa: BLE001
                    self.report({"ERROR"}, f"not saved: {exc}")
                    return {"CANCELLED"}
                self.report({"INFO"}, f"Read-only: saved as a new version {os.path.basename(p)}")
                return {"FINISHED"}
            if not bpy.data.filepath:
                return bpy.ops.wm.save_as_mainfile("INVOKE_DEFAULT")
            return bpy.ops.wm.save_mainfile()

    class EM_OT_blend_lease_release(bpy.types.Operator):
        """Release the lease of this .blend in the room (the holder, or the room's owner)"""
        bl_idname = "em.blend_lease_release"
        bl_label = "Release…"
        force: BoolProperty(default=False)  # type: ignore

        def invoke(self, context, event):
            return context.window_manager.invoke_confirm(
                self, event, title="Release the .blend?",
                message=("The others will be able to open it to change it. "
                         + ("You are not the holder: only the room's owner may." if self.force else "")))

        def execute(self, context):
            B = br()
            lease = STATE.get("lease")
            s = _session()
            if B is not None and self.force and not B.may_release(lease, person=STATE.get("person") or "",
                                                                   role=str(getattr(s, "role", "") or "")):
                self.report({"WARNING"}, "Only the holder or the room's owner may release it")
                return {"CANCELLED"}
            ok = release(reason="by hand", force=self.force)
            self.report({"INFO"} if ok else {"WARNING"}, "Released" if ok else "Nothing to release")
            return {"FINISHED"}

    return (EM_OT_blend_save_guard, EM_OT_blend_lease_release)


def draw(layout, context) -> None:  # pragma: no cover — bpy
    """The line of the open .blend's lease (in «Asset versions» and the
    room's panel)."""
    mode = STATE.get("mode")
    say = STATE.get("say")
    if not say and not STATE.get("switched"):
        return
    box = layout.box()
    icon = {"mine": "LOCKED", "readonly": "LOCKVIEW_ON", "mine_elsewhere": "LOCKVIEW_ON"}.get(mode, "INFO")
    if say:
        box.label(text=say, icon=icon)
    if STATE.get("switched"):
        box.label(text=f"saving into {os.path.basename(STATE['switched'])}", icon="FILE_TICK")
    if mode == "mine":
        box.operator("em.blend_lease_release", icon="UNLOCKED", text="Release…")
    elif mode == "readonly":
        s = _session()
        if str(getattr(s, "role", "") or "") in ("owner", "manager"):
            op = box.operator("em.blend_lease_release", icon="UNLOCKED", text="Release (owner)…")
            op.force = True


_CLASSES: tuple = ()
_KEYMAPS: list = []


def register():  # pragma: no cover — bpy
    bpy = _bpy()
    import atexit
    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    kc = bpy.context.window_manager.keyconfigs.addon if not bpy.app.background else None
    if kc is not None:
        km = kc.keymaps.new(name="Window", space_type="EMPTY")
        for mod in ({"oskey": True}, {"ctrl": True}):
            kmi = km.keymap_items.new("em.blend_save_guard", "S", "PRESS", **mod)
            _KEYMAPS.append((km, kmi))
    atexit.register(lambda: release(reason="exit"))


def unregister():  # pragma: no cover — bpy
    bpy = _bpy()
    for km, kmi in _KEYMAPS:
        try:
            km.keymap_items.remove(kmi)
        except Exception:  # noqa: BLE001
            pass
    _KEYMAPS.clear()
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
