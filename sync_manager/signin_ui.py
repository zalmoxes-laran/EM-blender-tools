"""Signing in from a panel without freezing Blender — and with a Cancel.

Measured on 4 Oct 2026: every door into a node (the room list, «New room»,
«Enter this room», «Bring into a room…», the join and the link) called
`handoff.sign_in`, which waited for the browser on the thread that draws
Blender. A realm that refused the return address left Blender frozen until the
timeout; the only way out was to call the loopback port by hand.

Now a door that needs a token asks `access_or_wait`:

* a pasted token, or the one this session already holds for that node, is
  returned at once — as before;
* a node without OIDC returns `(None, "open-node")` — as before;
* otherwise a `handoff.SignIn` starts (its listener and the code exchange run in
  a daemon thread), a timer polls it, the Sync panel shows «Waiting for the
  browser…» with **Cancel**, and the door raises `Waiting`: the operator says the
  sentence and ends. When the browser comes back the token is kept in memory
  (`room.set_room`, never on disk) and the door is opened again by itself — the
  `resume` the operator passed.

In a background Blender (the smokes) there is nobody to press anything and no
timer runs: the sign-in waits, as `handoff.sign_in` always did.
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

from . import handoff
from . import room as room_cfg

#: the sign-in in flight, for the timer and the panel (session state)
PENDING = {"signin": None, "base": "", "resume": None, "line": ""}

POLL = 0.25


class Waiting(Exception):
    """A sign-in has started in the browser; the door opens again by itself."""


def _held(base: str) -> Optional[str]:
    """The session's access for that node, renewed when it is about to run out;
    None when it ran out for good (the door then signs in again)."""
    held = room_cfg._session.get("token")
    held_base = room_cfg._session.get("base_url")
    if held and (not held_base or held_base == base.rstrip("/")):
        try:
            from . import access
            return access.fresh(held)
        except ImportError:      # loaded by path, outside the package (the suite)
            return held
        except room_cfg.RoomError as exc:
            print(f"[EM sign-in] {exc}")
            room_cfg._session["token"] = None
            return None
    return None


def access_or_wait(base: str, typed: str = "",
                   resume: Optional[Callable[[], None]] = None
                   ) -> Tuple[Optional[str], str]:
    """→ (token or None, how). Raises `Waiting` when the browser has to answer,
    `handoff.HandoffError` when the node's sign-in cannot work (said before the
    browser opens)."""
    typed = (typed or "").strip()
    if typed:
        return typed, "pasted"
    held = _held(base)
    if held:
        return held, "session"
    import bpy
    if bpy.app.background:
        got = handoff.sign_in(base)       # kept with its refresh token
        return (got, "signed-in") if got else (None, "open-node")
    running = PENDING.get("signin")
    if running is not None and running.state == "waiting":
        raise Waiting("a sign-in is already waiting for the browser — finish it, "
                      "or press Cancel in the Sync panel")
    started = handoff.start_sign_in(base)
    if started is None:
        return None, "open-node"
    PENDING.update({"signin": started, "base": base.rstrip("/"), "resume": resume,
                    "line": "Waiting for the browser…"})
    bpy.app.timers.register(_poll, first_interval=POLL)
    _redraw()
    raise Waiting(f"sign in to {base} in the browser that just opened — Blender "
                  f"carries on by itself (Cancel in the Sync panel)")


def _redraw() -> None:
    try:
        import bpy
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
    except Exception:  # noqa: BLE001 — no UI
        pass


def _in_a_window(fn: Callable[[], None]) -> None:
    """Run an operator call from a timer, where there is no window in context."""
    import bpy
    wm = bpy.context.window_manager
    window = wm.windows[0] if wm.windows else None
    if window is None:
        fn()
        return
    area = next((a for a in window.screen.areas if a.type == "VIEW_3D"),
                window.screen.areas[0])
    with bpy.context.temp_override(window=window, area=area, screen=window.screen):
        fn()


def _poll():
    running = PENDING.get("signin")
    if running is None:
        return None
    if running.state == "waiting":
        return POLL
    resume = PENDING.get("resume")
    PENDING.update({"signin": None, "resume": None})
    if running.state == "done":
        handoff.keep(running)
        room_cfg.set_room(PENDING["base"], room_cfg._session.get("room_id"),
                          running.token)
        PENDING["line"] = (f"signed in to {PENDING['base']}"
                           + (f" as {running.who}" if running.who else ""))
        print(f"[EM sign-in] {PENDING['line']}")
        if resume is not None:
            try:
                _in_a_window(resume)
            except Exception as exc:  # noqa: BLE001 — the access stays; say it
                PENDING["line"] += f" — press the button again ({exc})"
    else:
        PENDING["line"] = running.error or "the sign-in did not complete"
        print(f"[EM sign-in] {PENDING['line']}")
    _redraw()
    return None


def cancel() -> bool:
    running = PENDING.get("signin")
    if running is None or running.state != "waiting":
        return False
    running.cancel()
    return True


def draw(layout) -> None:  # pragma: no cover — bpy
    """One row in the Sync panel: the wait with its Cancel, or the last outcome."""
    running = PENDING.get("signin")
    line = PENDING.get("line") or ""
    if running is not None and running.state == "waiting":
        row = layout.row(align=True)
        row.label(text=line, icon="TIME")
        row.operator("em.sign_in_cancel", text="Cancel", icon="CANCEL")
        return
    from . import access
    if access.EXPIRED.get("base"):
        # X1 · the access ran out and could not be renewed: say it, and the
        # one gesture that fixes it, beside it
        col = layout.column(align=True)
        col.alert = True
        col.label(text=f"The access to {access.EXPIRED['base']} has expired",
                  icon="LOCKED")
        col.operator("em.sign_in_again", text="Sign in again", icon="USER")
    elif line:
        layout.label(text=line, icon="INFO")


def sign_in_again() -> str:
    """Forget the expired access and sign in to that node again → the sentence."""
    from . import access
    base = access.EXPIRED.get("base") or room_cfg._session.get("base_url") or ""
    if not base:
        return "no node to sign in to"
    if (room_cfg._session.get("base_url") or "") == base:
        room_cfg._session["token"] = None
    access.forget(base)
    access.EXPIRED.update({"base": "", "line": ""})
    try:
        token, how = access_or_wait(base)
    except Waiting as exc:
        return str(exc)
    if token:
        room_cfg.set_room(base, room_cfg._session.get("room_id"), token)
        return f"signed in to {base} again: press the button again"
    return f"{base} asks for no sign-in ({how})"


def _operator_classes():  # pragma: no cover — bpy
    import bpy

    class EM_OT_sign_in_cancel(bpy.types.Operator):
        """Stop waiting for the browser: nothing is signed in."""

        bl_idname = "em.sign_in_cancel"
        bl_label = "Cancel sign-in"

        def execute(self, context):
            if cancel():
                self.report({"INFO"}, "sign-in cancelled")
            return {"FINISHED"}

    class EM_OT_sign_in_again(bpy.types.Operator):
        """The access to the node expired: sign in again in the browser"""

        bl_idname = "em.sign_in_again"
        bl_label = "Sign in again"

        def execute(self, context):
            try:
                self.report({"INFO"}, sign_in_again())
            except handoff.HandoffError as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            return {"FINISHED"}

    return (EM_OT_sign_in_cancel, EM_OT_sign_in_again)


_CLASSES = ()


def register():  # pragma: no cover — bpy
    import bpy
    global _CLASSES
    _CLASSES = _operator_classes()
    for c in _CLASSES:
        bpy.utils.register_class(c)


def unregister():  # pragma: no cover — bpy
    import bpy
    for c in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
