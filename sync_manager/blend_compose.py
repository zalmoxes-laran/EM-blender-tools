"""MICRO-BLEND-OFFICINA-2 · a working .blend composed for a profile (point 2).

The plan is s3Dgraphy's (``resources.blend_room.compose_plan`` on the
inventory of a .blend: link or append, only what the profile needs or
everything, each object from the FILE that holds it — the last library of its
chain —, or a version's file imported). :func:`compose` carries it out in a
Blender: a new, empty file, one collection per source, saved with RELATIVE
paths. It changes the session it runs in (it starts from an empty file), so:

* EMStudio's runner calls it in its headless Blender (op ``compose``);
* the operator in Blender (``em.compose_working_blend``) runs it in a
  SEPARATE background Blender (this file as a script: no add-on needed), so
  the open .blend is never touched; the composed file is opened only if asked.

The source .blend is read as SAVED (the rule of round 1): with unsaved
changes the operator says so.
"""

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional


def _bpy():  # pragma: no cover — bpy
    import bpy
    return bpy


def free_path(path: str) -> str:
    """``path``, or ``<stem>-2.blend``, ``-3``… — a composed file is never
    written over another."""
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{stem}-{n}{ext}"):
        n += 1
    return f"{stem}-{n}{ext}"


def default_out(blend: str, profile: str) -> str:
    stem = os.path.splitext(os.path.basename(blend))[0]
    return free_path(os.path.join(os.path.dirname(blend), f"{stem}__{profile}.blend"))


def _import_file(path: str) -> List[Any]:  # pragma: no cover — bpy
    bpy = _bpy()
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".ply":
        bpy.ops.wm.ply_import(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        raise RuntimeError(f"cannot import {path}")
    return [o for o in bpy.data.objects if o not in before]


def compose(plan: Dict[str, Any], out_path: str, *, save: bool = True) -> Dict[str, Any]:  # pragma: no cover
    """Carry out a ``compose_plan`` into a NEW .blend at ``out_path`` (never
    over an existing file). → ``{ok, path, objects, libraries, sources,
    missing, seconds}``."""
    bpy = _bpy()
    t0 = time.time()
    out_path = free_path(os.path.abspath(out_path))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bpy.ops.wm.read_homefile(use_empty=True)
    # saved first, empty: so the libraries are loaded with paths relative to it
    bpy.ops.wm.save_as_mainfile(filepath=out_path)
    scene = bpy.context.scene
    missing: List[str] = []
    done: List[Dict[str, Any]] = []
    for src in plan.get("sources") or []:
        f = src["file"]
        how = src.get("how") or plan.get("how") or "link"
        col = bpy.data.collections.new(os.path.splitext(os.path.basename(f))[0] + f" ({how})")
        scene.collection.children.link(col)
        got: List[Any] = []
        if not os.path.exists(f):
            missing += list(src.get("objects") or [])
            continue
        if how == "import":
            got = _import_file(f)
            for o in got:
                for c in list(o.users_collection):
                    c.objects.unlink(o)
        else:
            want = list(src.get("objects") or [])
            with bpy.data.libraries.load(f, link=(how == "link"), relative=True) as (data_from, data_to):
                have = set(data_from.objects)
                data_to.objects = [n for n in want if n in have]
                missing += [n for n in want if n not in have]
            got = [o for o in data_to.objects if o is not None]
        for o in got:
            col.objects.link(o)
        done.append({"file": f, "how": how, "objects": [o.name for o in got]})
    libs = [{"name": lb.name, "filepath": lb.filepath} for lb in bpy.data.libraries]
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=out_path, relative_remap=True)
    return {"ok": True, "path": out_path, "profile": plan.get("profile"), "how": plan.get("how"),
            "objects": sum(len(d["objects"]) for d in done), "sources": done, "libraries": libs,
            "missing": missing, "seconds": round(time.time() - t0, 2)}


def plan_for(context, profile: str, how: str, only_needed: bool) -> Dict[str, Any]:  # pragma: no cover
    """The plan for the OPEN .blend (its inventory as saved)."""
    from .blend_officina import bf, inventory
    try:
        from s3dgraphy.resources import blend_room
    except ImportError as exc:
        from .blend_officina import NEEDS_DEV79
        raise RuntimeError(NEEDS_DEV79) from exc
    inv = inventory()
    bf()  # the same s3dgraphy says the inventory
    return blend_room.compose_plan(inv, profile, how=how, only_needed=only_needed)


def run_detached(plan: Dict[str, Any], out_path: str, *, wait: bool = True, timeout: float = 600
                 ) -> Dict[str, Any]:  # pragma: no cover — bpy
    """:func:`compose` in a separate background Blender (the open session is
    never touched): this file run as a script, the plan in a JSON file."""
    import subprocess
    import tempfile
    bpy = _bpy()
    tmp = tempfile.NamedTemporaryFile("w", suffix=".compose.json", delete=False)
    json.dump(plan, tmp)
    tmp.close()
    cmd = [bpy.app.binary_path, "-b", "--factory-startup", "--python-exit-code", "1",
           "--python", os.path.abspath(__file__), "--", tmp.name, out_path]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    for line in (p.stdout or "").splitlines():
        if line.startswith("EM-COMPOSE "):
            return json.loads(line[len("EM-COMPOSE "):])
    raise RuntimeError("the background Blender did not compose: " + (p.stderr or p.stdout or "")[-600:])


def _operator_classes():  # pragma: no cover — bpy
    bpy = _bpy()
    from bpy.props import BoolProperty, EnumProperty, StringProperty

    def _profiles(self, context):
        try:
            from s3dgraphy.resources import blend_room
            keys = list(blend_room.PROFILE_KINDS)
        except ImportError:
            keys = ["modelling"]
        return [(k, k.replace("_", " "), "") for k in keys]

    class EM_OT_compose_working_blend(bpy.types.Operator):
        """Compose a working .blend for a profile from this .blend (as saved): link or append,
        only what the profile needs or all, each object from the file that holds it"""
        bl_idname = "em.compose_working_blend"
        bl_label = "Compose a working .blend for…"
        profile: EnumProperty(name="Profile", items=_profiles)  # type: ignore
        how: EnumProperty(name="How", items=[("link", "Link", "linked: light, follows the sources"),
                                             ("append", "Append", "copied: on its own")],
                          default="link")  # type: ignore
        only_needed: BoolProperty(name="Only what the profile needs", default=True)  # type: ignore
        open_after: BoolProperty(name="Open it after", default=False)  # type: ignore
        filepath: StringProperty(name="Into", subtype="FILE_PATH", default="")  # type: ignore

        def invoke(self, context, event):
            if not bpy.data.filepath:
                self.report({"WARNING"}, "Save the .blend first")
                return {"CANCELLED"}
            return context.window_manager.invoke_props_dialog(self, width=480)

        def draw(self, context):
            col = self.layout.column()
            for p in ("profile", "how", "only_needed", "open_after", "filepath"):
                col.prop(self, p)
            if bpy.data.is_dirty:
                col.label(text="Unsaved changes: the composition reads the SAVED file", icon="ERROR")
            try:
                plan = plan_for(context, self.profile, self.how, self.only_needed)
                col.label(text=plan["say"], icon="INFO")
            except Exception as exc:  # noqa: BLE001
                col.label(text=str(exc), icon="ERROR")

        def execute(self, context):
            try:
                plan = plan_for(context, self.profile, self.how, self.only_needed)
                out = bpy.path.abspath(self.filepath) if self.filepath else default_out(bpy.data.filepath,
                                                                                        self.profile)
                got = run_detached(plan, out)
            except Exception as exc:  # noqa: BLE001
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            self.report({"INFO"}, f"Composed {got['objects']} object(s) into {os.path.basename(got['path'])}"
                        + (f", {len(got['missing'])} missing" if got.get("missing") else ""))
            if self.open_after:
                bpy.ops.wm.open_mainfile(filepath=got["path"])
            return {"FINISHED"}

    return (EM_OT_compose_working_blend,)


_CLASSES: tuple = ()


def register():  # pragma: no cover — bpy
    bpy = _bpy()
    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():  # pragma: no cover — bpy
    bpy = _bpy()
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":  # pragma: no cover — run by run_detached
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    with open(argv[0], "r", encoding="utf-8") as fh:
        _plan = json.load(fh)
    _got = compose(_plan, argv[1])
    sys.stdout.write("EM-COMPOSE " + json.dumps(_got) + "\n")
    sys.stdout.flush()
