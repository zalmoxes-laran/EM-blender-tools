"""B1 · the .blend as a STARTER PACKAGE for a computer that has no cache yet.

MICRO-ASSET-VERSIONI, decided by E.D. on 3 October 2026 (V-b): what goes up as
shared truth is the graph and the open formats of the versions; the .blend is a
local cache that can be rebuilt. But rebuilding it from scratch on a new
computer is slow, so the scene can ALSO be archived as a package:

* «Archive the scene package» sends ONE .blend to the room as a ROOM
  ATTACHMENT — the same opaque namespace as the safety snapshots
  (``blend-backup``, ``kind=package``), NEVER a node of the graph. The asset
  libraries the scene links (``//em_cache/…``) are PACKED into it, so it opens
  whole where there is no cache. Packing happens in a second, background
  Blender on the file on disk: the session you work in is not touched;
* «Download the package» fetches it (digest verified), unpacks the libraries
  beside it — that is the cache, from then on — and opens it;
* with a cache already present nobody needs the package: «Check the scene
  against the room» exchanges only the meshes that are missing or changed.

Unlike a safety snapshot, a package is readable by everybody in the room
(that is what it is for); keeping one needs editor, like a snapshot.
"""

# NOT `from __future__ import annotations`: Blender evaluates the operators'
# property annotations in this module's globals (see scene_check).
import hashlib
import os
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


def _urlopen(request, timeout=None):
    """Every call to a node verifies TLS against what this computer trusts
    (`trust.py`: the dev node behind Caddy included), with an access renewed
    before it runs out and said when it cannot be (`access.py`)."""
    try:
        from .access import urlopen
    except ImportError:          # loaded by path, outside the package (the suite)
        import urllib.request
        return urllib.request.urlopen(request, timeout=timeout)
    return urlopen(request, timeout=timeout)

KIND = "package"

#: the last listing (session state, never saved in the .blend)
_listing: List[Dict[str, Any]] = []
_note: str = ""


def package_name(blend_path: str, sha256: str) -> str:
    """`<stem>-package-<sha12>.blend`: never the name of the file in use."""
    stem = os.path.splitext(os.path.basename(blend_path or ""))[0] or "scene"
    return f"{stem}-package-{str(sha256)[:12]}.blend"


def pack_script(target: str) -> str:
    """The Python the background Blender runs: pack the linked libraries and
    save a COPY, compressed."""
    return ("import bpy\n"
            "bpy.ops.file.pack_libraries()\n"
            f"bpy.ops.wm.save_as_mainfile(filepath={target!r}, copy=True, "
            "compress=True)\n"
            "print('EM_PACKED', len([l for l in bpy.data.libraries "
            "if l.packed_file]))\n")


UNPACK_SCRIPT = ("import bpy\n"
                 "n = len([l for l in bpy.data.libraries if l.packed_file])\n"
                 "bpy.ops.file.unpack_libraries()\n"
                 "bpy.ops.wm.save_mainfile()\n"
                 "print('EM_UNPACKED', n)\n")


def _background(blender: str, blend: str, script: str, marker: str) -> int:
    """Run ``script`` on ``blend`` in a background Blender; → the count after
    ``marker`` in its output. Raises with the tail of the log when it fails."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
        handle.write(script)
        path = handle.name
    try:
        done = subprocess.run([blender, "-b", "--factory-startup", blend,
                               "--python", path], capture_output=True,
                              text=True, timeout=3600)
    finally:
        os.unlink(path)
    for line in (done.stdout or "").splitlines():
        if line.startswith(marker):
            return int(line.split()[-1])
    raise RuntimeError(f"the background Blender did not finish ({done.returncode}): "
                       + ((done.stderr or done.stdout or "")[-300:]))


def make_package(blender: str, blend: str, out: str) -> int:
    """A copy of ``blend`` with its libraries packed, at ``out``. → how many
    libraries went in."""
    return _background(blender, blend, pack_script(out), "EM_PACKED")


def unpack_beside(blender: str, blend: str) -> int:
    """Write the packed libraries of ``blend`` to their places beside it (the
    cache), and save it linking them. → how many."""
    return _background(blender, blend, UNPACK_SCRIPT, "EM_UNPACKED")


# ── the room ─────────────────────────────────────────────────────────────────

def put_package(data: bytes, *, label: str = "", filename: str = "",
                timeout: float = 1800.0) -> Dict[str, Any]:
    from . import room
    local = hashlib.sha256(data).hexdigest()
    query = urllib.parse.urlencode({"label": label, "filename": filename,
                                    "kind": KIND})
    record = room._room_json(f"{room._room_path('blend-backup')}?{query}",
                             method="PUT", data=data,
                             content_type=room.BLEND_MEDIA_TYPE, timeout=timeout)
    if not isinstance(record, dict) or record.get("sha256") != local:
        raise room.RoomError(f"the room stored a different digest "
                             f"({(record or {}).get('sha256')}) than the bytes "
                             f"we sent ({local})")
    return record


def list_packages(timeout: float = 30.0) -> List[Dict[str, Any]]:
    from . import room
    return list(room._room_json(room._room_path("blend-packages"),
                                timeout=timeout) or [])


def get_package(sha256: str, timeout: float = 1800.0) -> bytes:
    from . import room
    wanted = str(sha256).strip().lower()
    url = room._room_path(f"blend-package/{urllib.parse.quote(wanted)}")
    request = urllib.request.Request(url, method="GET",
                                     headers=room._auth_headers())
    try:
        with _urlopen(request, timeout=timeout) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        raise room.RoomError(f"the room refused the package ({exc.code})",
                             status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise room.RoomError(f"could not reach the room: {exc.reason}") from exc
    got = hashlib.sha256(data).hexdigest()
    if got != wanted:
        raise room.RoomError(f"the package hashes to {got[:12]}…, not "
                             f"{wanted[:12]}… — not using it")
    return data


# ── Blender ──────────────────────────────────────────────────────────────────

def _operator_classes():  # pragma: no cover — bpy
    import bpy  # type: ignore

    class EM_OT_scene_package_archive(bpy.types.Operator):
        """Archive this scene as a starter package in the room: the .blend on
        disk with the asset libraries packed in. A room attachment for a
        computer without a cache — never a node of the graph"""

        bl_idname = "em.scene_package_archive"
        bl_label = "Archive the scene package"

        label: bpy.props.StringProperty(name="Label", default="")  # type: ignore
        save_first: bpy.props.BoolProperty(  # type: ignore
            name="Save the file first", default=True)

        def invoke(self, context, event):
            return context.window_manager.invoke_props_dialog(self)

        def execute(self, context):
            from . import room
            if not room.is_configured():
                self.report({"ERROR"}, "no room: join one first")
                return {"CANCELLED"}
            if not bpy.data.filepath:
                self.report({"ERROR"}, "save the .blend once: the package is "
                                       "made from the file on disk")
                return {"CANCELLED"}
            if bpy.data.is_dirty:
                if not self.save_first:
                    self.report({"ERROR"}, "unsaved changes: save first")
                    return {"CANCELLED"}
                bpy.ops.wm.save_mainfile()
            out = os.path.join(tempfile.mkdtemp(prefix="em-package-"),
                               os.path.basename(bpy.data.filepath))
            try:
                packed = make_package(bpy.app.binary_path, bpy.data.filepath, out)
                with open(out, "rb") as handle:
                    data = handle.read()
                record = put_package(data, label=self.label,
                                     filename=os.path.basename(bpy.data.filepath))
            except Exception as exc:  # noqa: BLE001 — the reason is the user's
                self.report({"ERROR"}, f"could not archive the package: {exc}")
                return {"CANCELLED"}
            finally:
                try:
                    os.unlink(out)
                except OSError:
                    pass
            _refresh(None)
            self.report({"INFO"}, f"package kept: {len(data) // 1024} kB, "
                                  f"{packed} asset librar(ies) inside, "
                                  f"{record['sha256'][:12]}…"
                                  + ("" if record.get("created")
                                     else " (the same bytes were already kept)"))
            return {"FINISHED"}

    class EM_OT_scene_package_list(bpy.types.Operator):
        """Ask the room which scene packages it holds"""

        bl_idname = "em.scene_package_list"
        bl_label = "Refresh the packages"

        def execute(self, context):
            return {"FINISHED"} if _refresh(self) else {"CANCELLED"}

    class EM_OT_scene_package_download(bpy.types.Operator):
        """Start from the room's package on a computer with no cache: download
        it, unpack its asset libraries beside it (that is the cache from now
        on) and open it"""

        bl_idname = "em.scene_package_download"
        bl_label = "Download the package"

        sha256: bpy.props.StringProperty(name="Package")  # type: ignore
        folder: bpy.props.StringProperty(  # type: ignore
            name="Folder", subtype="DIR_PATH", default="")
        open_it: bpy.props.BoolProperty(name="Open it", default=True)  # type: ignore

        def execute(self, context):
            from . import asset_versions
            folder = bpy.path.abspath(self.folder) if self.folder else \
                asset_versions.cache_folder()
            if not self.sha256:
                self.report({"ERROR"}, "no package named")
                return {"CANCELLED"}
            record = next((r for r in _listing if r.get("sha256") == self.sha256), {})
            target = os.path.join(folder, package_name(
                record.get("filename") or bpy.data.filepath, self.sha256))
            if os.path.exists(target):
                self.report({"ERROR"}, f"{os.path.basename(target)} already "
                                       f"exists: refusing to overwrite it")
                return {"CANCELLED"}
            try:
                data = get_package(self.sha256)
                with open(target, "wb") as handle:
                    handle.write(data)
                n = unpack_beside(bpy.app.binary_path, target)
            except Exception as exc:  # noqa: BLE001
                self.report({"ERROR"}, f"could not use the package: {exc}")
                return {"CANCELLED"}
            self.report({"INFO"}, f"{os.path.basename(target)}: {n} asset "
                                  f"librar(ies) unpacked into em_cache beside it")
            if self.open_it:
                bpy.ops.wm.open_mainfile(filepath=target)
            return {"FINISHED"}

    return (EM_OT_scene_package_archive, EM_OT_scene_package_list,
            EM_OT_scene_package_download)


def _refresh(reporter) -> bool:  # pragma: no cover — bpy
    global _listing, _note
    from . import room
    if not room.is_configured():
        _listing, _note = [], "no room joined"
        return False
    try:
        _listing, _note = list_packages(), ""
    except room.RoomError as exc:
        _listing, _note = [], str(exc)
        if reporter is not None:
            reporter.report({"ERROR"}, str(exc))
        return False
    return True


def draw(layout) -> None:  # pragma: no cover — bpy
    box = layout.box()
    box.label(text="Scene package (for a computer without the cache)",
              icon="PACKAGE")
    row = box.row(align=True)
    row.operator("em.scene_package_archive", icon="EXPORT")
    row.operator("em.scene_package_list", text="", icon="FILE_REFRESH")
    for rec in _listing[:5]:
        r = box.row(align=True)
        r.label(text=f"{rec.get('filename') or '?'} · {rec.get('label') or ''} "
                     f"· {int(rec.get('size') or 0) // 1048576} MB")
        r.operator("em.scene_package_download", text="",
                   icon="IMPORT").sha256 = rec.get("sha256", "")
    if _note:
        box.label(text=_note[:90], icon="INFO")
    box.label(text="With a cache, «Check the scene» exchanges only meshes.",
              icon="BLANK1")


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
