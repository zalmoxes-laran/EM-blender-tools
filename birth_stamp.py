"""The stamp born with the file: a ``.stamp.json`` beside what Blender exports.

E.D. (1 Oct 2026): «laddove Blender CREA asset nuovi, li può già timbrare».
The ``.blend`` is the OPERATIONAL STATE, and a resource has two identities by
tier (brain: *La risorsa e i suoi file*):

* the **master** (``tier: master``, ``packaging: datablock``) is the object in
  the ``.blend``; its identity is its locator ``blend://<file>#Object/<name>``,
  stable across saves;
* the **distribution** (the exported file) is identified by its bytes.

One function, :func:`stamp_export`, writes the stamp of a distribution right
after a successful export, with dtcstamp (the wheel in the bundle). Nothing of
the identity is computed here: the digests, the members of a file set, the
content of a tree are dtcstamp's. This module only decides WHICH of dtcstamp's
stamps a path is, fills ``from`` / ``how`` / ``by``, and keeps the previous
stamp when the bytes change (a revision of the distribution).

What the format decides and this module follows (``dtcstamp/stamp-format.md``):

* ``from`` names its inputs **by identity, never by path**. The master's
  ``blend://`` locator is a path, so it does NOT go in the stamp: it is a
  private hint (``kind: blend``) in ``<asset>.hints.json``, under ``from``,
  one key per master (dtcstamp 0.1.3; before, ``<asset>.from.hints.json``);
* a datablock has no digest of bytes. EMtools' structural fingerprint is
  ``struct:…`` (``resource_levels.impronta_strutturale``), not dtcstamp's
  ``emstruct1:``, so it is NOT written as a ``digest``: it travels in
  ``from[].state`` (dtcstamp 0.1.3) as ``fingerprint``, beside ``sha256`` (the
  ``.blend`` as it is on disk at that moment) and ``saved``;
* a second export with new bytes is a revision: ``self.was_revision_of``
  ``{resource_id, digest}`` of the previous distribution (dtcstamp 0.1.3);
* ``by.operator`` is who is exporting: the identity a room reports for the
  token, else (dev28) the LOCAL identity of the preferences, an ORCID iD
  declared and checked by nobody (``auth: {mode: declared}``). Without either
  it is omitted, and the agent is the software in ``how`` — the format's rule.

``bpy``-free above the line marked «Blender»: the stamps are measured outside
Blender, by pytest.
"""

from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Optional

#: what a stamp says about the kind of step: the GESTURE. s3Dgraphy dev28
#: (``em_visual_rules`` 1.6.29, ``dtc_kinds.process``) has the four words; a
#: bundled s3dgraphy before it does not, and there :func:`resolve_kind` writes
#: the equivalent of the dev27 vocabulary, the gesture staying in
#: ``technique``. Measured at the moment of the stamp, so the rebundle of the
#: dev28 switches it with no change here.
KIND_EXPORT = "export"                 # datablock → glb/gltf/obj/fbx
KIND_LOD = "lod_generation"            # a LOD baked from the master
KIND_TILING = "tiling"                 # a mesh split into a 3D Tiles tree
KIND_PACKING = "packing"               # a tree packed into a .3tz

#: the dev27 equivalents, for a vocabulary that lacks the gesture
_BEFORE_DEV28 = {KIND_EXPORT: "format_conversion", KIND_LOD: "decimation",
                 KIND_TILING: "transformation", KIND_PACKING: "format_conversion"}


def process_kinds() -> List[str]:
    """The ``process`` kinds of the s3dgraphy this Blender runs (empty when it
    cannot be read)."""
    try:
        from s3dgraphy.utils.utils import get_dtc_kinds
        return list(get_dtc_kinds().get("process") or ())
    except Exception:                               # noqa: BLE001
        return []


def resolve_kind(kind: Optional[str], known: Optional[List[str]] = None) -> Optional[str]:
    """``kind`` when the vocabulary has it; the dev27 equivalent of a gesture
    it lacks; anything else as it is (the graph's builder validates)."""
    if not kind:
        return kind
    vocabulary = process_kinds() if known is None else known
    if kind in vocabulary or kind not in _BEFORE_DEV28:
        return kind
    return _BEFORE_DEV28[kind]

#: the suffix of the previous stamp when the bytes change: it stays beside the
#: file, a true statement about bytes that are no longer there
PREVIOUS_INFIX = ".prev-"
#: where the masters' hints went before dtcstamp 0.1.3 — READ only, to fold an
#: old file in; they are now in ``<asset>.hints.json`` under ``from``
FROM_HINTS_SUFFIX = ".from.hints.json"

#: archives that are not a 3tz: a plain zip has no index to read the content
#: through, so it is stamped by its bytes alone
_PLAIN_ARCHIVES = (".zip",)


def _dtcstamp():
    try:
        from . import resource_digest  # inside the addon package
    except ImportError:
        import resource_digest  # type: ignore  # tests: repo root on the path
    return resource_digest.dtcstamp()


def stamp_path_for(path: str) -> str:
    """``<path>.stamp.json`` beside a file, a folder or the door of a file set
    — the rule the seal reads with (``resource_seal.stamp_path_for``)."""
    path = os.path.abspath(path.rstrip("/\\"))
    return os.path.join(os.path.dirname(path),
                        _dtcstamp().stamp_filename({}, asset=os.path.basename(path)))


def _hex(digest: str) -> str:
    return str(digest or "").split(":", 1)[-1]


def default_resource_id(digest: str) -> str:
    """The id of a distribution nobody named: derived from its bytes, so the same
    bytes always get the same id and new bytes a new one."""
    return f"res:{_hex(digest)[:16]}"


_MEDIA = {".glb": ("model/gltf-binary", "glb"), ".gltf": ("model/gltf+json", "gltf"),
          ".obj": ("model/obj", "obj"), ".fbx": ("application/octet-stream", "fbx"),
          ".zip": ("application/zip", "zip"), ".ply": ("application/octet-stream", "ply")}


def _base_stamp(path: str, resource_id: Optional[str]) -> Dict[str, Any]:
    """dtcstamp's stamp for whatever ``path`` is, with ``self`` only.

    * a folder → a tree (``directory``, the digest IS the content);
    * a ``.3tz`` → a tree (``archive``, sha256 of the file + ``content_digest``);
    * an ``.obj`` / ``.gltf`` that calls other files → a ``file_set``;
    * anything else → one ``file`` (a ``.zip`` declares ``packaging: archive``).
    """
    dtc = _dtcstamp()
    placeholder = resource_id or "res:pending"
    lower = path.lower()
    if os.path.isdir(path):
        entry = "tileset.json" if os.path.isfile(os.path.join(path, "tileset.json")) else None
        stamp = dtc.new_tree_stamp(path, placeholder, computed_by="producer",
                                   entry_point=entry)
    elif lower.endswith(".3tz"):
        stamp = dtc.new_tree_stamp(path, placeholder, computed_by="producer")
    else:
        followed = None
        if lower.endswith((".obj", ".gltf")):
            followed = dtc.follow_references(path)
        if followed and len(followed["members"]) > 1:
            stamp = dtc.new_file_set_stamp(path, placeholder)
        else:
            media, fmt = _MEDIA.get(os.path.splitext(lower)[1], (None, None))
            itself = {"resource_id": placeholder, "digest": dtc.file_digest(path),
                      "digest_covers": "artifact",
                      "packaging": "archive" if lower.endswith(_PLAIN_ARCHIVES) else "file",
                      "measures": {"size_bytes": os.path.getsize(path)}}
            if media:
                itself["media_type"] = media
            if fmt:
                itself["format"] = fmt
            stamp = {"stamp": dtc.STAMP_VERSION, "self": itself}
    itself = stamp["self"]
    if not resource_id:
        itself["resource_id"] = default_resource_id(itself["digest"])
    if lower.endswith((".gltf", ".glb", ".obj")) and "format" not in itself:
        media, fmt = _MEDIA[os.path.splitext(lower)[1]]
        itself["format"] = fmt
        itself.setdefault("media_type", media)
    return stamp


def master_entry(master: Dict[str, Any]) -> Dict[str, Any]:
    """The ``from`` entry of the master — by identity, never by path.

    ``master``: ``{resource_id, label, blend_digest, blend_saved, fingerprint,
    locator}``; the locator is NOT copied (it goes in the hints)."""
    entry: Dict[str, Any] = {"resource_id": str(master["resource_id"])}
    if master.get("label"):
        entry["label"] = str(master["label"])
    entry["tier"] = "master"
    entry["packaging"] = "datablock"
    # dtcstamp 0.1.3 `from[].state`: fingerprint · sha256 (of the container,
    # the .blend) · saved — the spelling of the format (it was blend /
    # blend_saved on 1 Oct, before the format had the field)
    state: Dict[str, Any] = {}
    if master.get("fingerprint"):
        state["fingerprint"] = master["fingerprint"]
    if master.get("blend_digest"):
        state["sha256"] = master["blend_digest"]
    if master.get("blend_saved") is not None:
        state["saved"] = bool(master["blend_saved"])
        if not master["blend_saved"]:
            state["note"] = ("the .blend had unsaved changes: the object exported "
                             "is not the one in this file on disk")
    if state:
        entry["state"] = state
    return entry


def stamp_export(path: str, *, masters: Optional[List[Dict[str, Any]]] = None,
                 parents: Optional[List[Dict[str, Any]]] = None,
                 how: Optional[Dict[str, Any]] = None,
                 operator: Optional[Dict[str, Any]] = None,
                 resource_id: Optional[str] = None, label: Optional[str] = None,
                 description: Optional[str] = None,
                 when: Optional[str] = None, machine: Optional[str] = None
                 ) -> Dict[str, Any]:
    """Write the ``.stamp.json`` of an exported file, folder or archive.

    ``masters`` are the objects it was made from (:func:`master_entry`);
    ``parents`` other ``from`` entries as they are (a folder a ``.3tz`` was
    packed from). Returns ``{state, stamp_path, stamp, packaging, digest,
    revision_of, previous_path, hints_path, line}`` with ``state`` one of
    ``stamped``, ``revised`` (new bytes: the previous stamp kept as
    ``<asset>.prev-<hex12>.stamp.json``, the new one ``self.was_revision_of`` it),
    ``unchanged`` (the same bytes: the stamp there is the same fact, kept as it
    is) or ``failed`` (nothing written; ``line`` says why). Never raises for the
    export's sake: an export does not fail because its stamp could not be
    written, it says so.
    """
    dtc = _dtcstamp()
    out: Dict[str, Any] = {"state": "failed", "stamp_path": "", "stamp": None,
                           "packaging": "", "digest": "", "revision_of": None,
                           "previous_path": "", "hints_path": "", "line": ""}
    try:
        if not path or not os.path.exists(path):
            out["line"] = f"nothing at {path!r}"
            return out
        stamp = _base_stamp(path, resource_id)
        itself = stamp["self"]
        itself["tier"] = "distribution"
        if label:
            itself["label"] = str(label)
        if description:
            itself["description"] = str(description)
        target = stamp_path_for(path)
        out.update(stamp_path=target, packaging=itself.get("packaging", ""),
                   digest=itself.get("digest", ""))

        previous = None
        if os.path.isfile(target):
            try:
                previous = dtc.read_stamp(target)
            except (OSError, ValueError):
                previous = None          # not a stamp: it is overwritten below
        if previous is not None and (previous.get("self") or {}).get("digest") == itself["digest"]:
            out.update(state="unchanged", stamp=previous,
                       line=f"same bytes, the stamp there stands ({os.path.basename(target)})")
            return out

        entries = [master_entry(m) for m in (masters or [])] + list(parents or [])
        stamp["from"] = entries
        if how:
            stamp["how"] = dict(how)
            if how.get("dtc_kind"):
                stamp["how"]["dtc_kind"] = resolve_kind(how["dtc_kind"])
        by: Dict[str, Any] = {"at": when or dtc.now_iso()}
        if operator and operator.get("id"):
            op = {"id": str(operator["id"])}
            if operator.get("label"):
                op["label"] = str(operator["label"])
            if isinstance(operator.get("auth"), dict) and operator["auth"].get("mode"):
                # dtcstamp 0.1.3 `by.operator.auth`: how the operator had entered
                op["auth"] = dict(operator["auth"])
            by = {"operator": op, **by}
        stamp["by"] = by

        if previous is not None:
            old = previous.get("self") or {}
            old_rid = str(old.get("resource_id") or "")
            if old_rid == itself["resource_id"]:
                #: an id given by the caller for a distribution whose bytes
                #: changed: the revision needs its own id
                itself["resource_id"] = f"{old_rid}.r{_hex(itself['digest'])[:8]}"
            itself["was_revision_of"] = {"resource_id": old_rid,
                                         "digest": old.get("digest")}
            keep = os.path.join(
                os.path.dirname(target),
                os.path.basename(target)[:-len(dtc.STAMP_SUFFIX)]
                + PREVIOUS_INFIX + _hex(old.get("digest"))[:12] + dtc.STAMP_SUFFIX)
            shutil.copy2(target, keep)
            out.update(revision_of=itself["was_revision_of"], previous_path=keep)

        dtc.write_stamp(stamp, target)
        hints_path = write_hints(path, target, itself["digest"],
                                 [m for m in (masters or []) if m.get("locator")],
                                 machine=machine, when=by["at"])
        out["hints_path"] = hints_path
        out.update(state="revised" if previous is not None else "stamped",
                   stamp=dtc.clean_stamp(stamp),
                   line=(f"stamped {os.path.basename(target)} "
                         f"({itself.get('packaging')}, {itself['digest'][:19]}…)"
                         + (f", a revision of {itself['was_revision_of']['resource_id']}"
                            if previous is not None else "")))
        return out
    except Exception as exc:                        # noqa: BLE001 — said, not raised
        out["line"] = f"not stamped: {exc}"
        return out


def write_hints(path: str, stamp_path: str, digest: str, masters: List[Dict[str, Any]],
                *, machine: Optional[str] = None, when: Optional[str] = None) -> str:
    """``<asset>.hints.json`` beside the stamp (dtcstamp 0.1.3): the asset's own
    register — seen HERE, now, private — and the masters' ``blend://``
    locators under ``from``, ONE KEY PER MASTER (its ``resource_id`` in the
    stamp). Read before it is written: a register is updated, never replaced.

    Before 0.1.3 the masters went in ``<asset>.from.hints.json`` under the
    first master's id (two masters shared one key, a defect); a file of that
    shape found beside it is folded in under its own id, and left where it is.
    With a dtcstamp that predates ``note_parent_seen`` the same JSON is written
    by hand: the shape is the format's, additive, and 0.1.2 keeps it."""
    dtc = _dtcstamp()
    hints_path = stamp_path[:-len(dtc.STAMP_SUFFIX)] + dtc.HINTS_SUFFIX
    hints = None
    if os.path.isfile(hints_path):
        try:
            hints = dtc.read_hints(hints_path)
        except (OSError, ValueError):
            hints = None
    if not isinstance(hints, dict) or hints.get("digest") != digest:
        hints = dtc.new_hints(digest)
    dtc.note_seen(hints, os.path.abspath(path), kind="local", scope="private",
                  machine=machine, when=when)

    def note_parent(parent_id: str, locator: str, kind: str = "blend",
                    seen_when: Optional[str] = None) -> None:
        if hasattr(dtc, "note_parent_seen"):
            dtc.note_parent_seen(hints, parent_id, locator, kind=kind, scope="private",
                                 machine=machine, when=seen_when or when)
            return
        register = {"seen": list((hints.setdefault("from", {})).get(parent_id) or [])}
        dtc.note_seen(register, locator, kind=kind, scope="private",
                      machine=machine, when=seen_when or when)
        hints["from"][parent_id] = register["seen"]

    legacy = stamp_path[:-len(dtc.STAMP_SUFFIX)] + FROM_HINTS_SUFFIX
    if os.path.isfile(legacy):
        try:
            old = dtc.read_hints(legacy)
            for entry in old.get("seen") or []:
                if isinstance(entry, dict) and entry.get("locator"):
                    note_parent(str(old.get("digest") or ""), entry["locator"],
                                entry.get("kind") or "blend", entry.get("when"))
        except (OSError, ValueError, AttributeError):
            pass
    for m in masters:
        note_parent(str(m["resource_id"]), m["locator"])
    dtc.write_hints(hints, hints_path)
    return hints_path


def file_sha256(path: str) -> str:
    """``sha256:<hex>`` of a file (the ``.blend`` on disk), or ``""``."""
    if not path or not os.path.isfile(path):
        return ""
    return _dtcstamp().file_digest(path)


def report_line(results: List[Dict[str, Any]]) -> str:
    """One line for the operator's report: how many stamped, revised, kept,
    failed — and the first reason, when something was not stamped."""
    counts: Dict[str, int] = {}
    for r in results:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    if not counts:
        return ""
    parts = [f"{n} {word}" for word, n in (
        ("stamped", counts.get("stamped", 0)), ("revised", counts.get("revised", 0)),
        ("unchanged", counts.get("unchanged", 0)),
        ("not stamped", counts.get("failed", 0))) if n]
    line = "Stamps: " + ", ".join(parts)
    failed = next((r["line"] for r in results if r["state"] == "failed"), "")
    return line + (f" ({failed})" if failed else "")


# ══════════════════════════════════════════════════════════════════════════
# Blender — what Blender knows at the moment of the export
# ══════════════════════════════════════════════════════════════════════════

ADDON_NAME = "EM Tools"


def _addon_package() -> str:
    return __package__ or ""


def python_idname(name: str) -> str:
    """``glb.exportbatch`` from ``GLB_OT_exportbatch``. Measured in 5.2: an
    operator INSTANCE's ``bl_idname`` is the registered C-style name, not the
    ``bpy.ops`` one a person types; the stamp says the one a person types."""
    name = str(name or "")
    if "_OT_" in name:
        prefix, rest = name.split("_OT_", 1)
        return f"{prefix.lower()}.{rest}"
    return name


def stamping_enabled() -> bool:
    """The preference «Stamp what you export» (on by default)."""
    try:
        import bpy
        prefs = bpy.context.preferences.addons[_addon_package()].preferences
        return bool(getattr(prefs, "stamp_exports", True))
    except Exception:                               # noqa: BLE001 — no prefs: the default
        return True


def _manifest_version(folder: str) -> str:
    try:
        with open(os.path.join(folder, "blender_manifest.toml"), "r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip().startswith("version"):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


def addon_commit(folder: str) -> str:
    """The commit the add-on was built from: ``build_info.json`` (written by
    ``scripts/build.py``), else ``git`` when the add-on runs from a checkout,
    else ``""`` — never invented."""
    import json
    try:
        with open(os.path.join(folder, "build_info.json"), "r", encoding="utf-8") as fh:
            info = json.load(fh)
        return str(info.get("commit") or "") + ("-dirty" if info.get("dirty") else "")
    except (OSError, ValueError):
        pass
    if os.path.isdir(os.path.join(folder, ".git")):
        import subprocess
        try:
            res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=folder,
                                 capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return res.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return ""


def software_entry(name: str, folder: str) -> Dict[str, str]:
    """``{name, version, commit}`` of an add-on from its folder."""
    entry = {"name": name}
    version = _manifest_version(folder)
    if version:
        entry["version"] = version
    commit = addon_commit(folder)
    if commit:
        entry["commit"] = commit
    return entry


def blender_software(producer: Optional[Dict[str, str]] = None) -> List[Dict[str, str]]:
    """Blender with its version, the add-on that made the file (``producer``,
    when it is not EMtools), EMtools, and the libraries that wrote the stamp."""
    import bpy
    out = [{"name": "Blender", "version": bpy.app.version_string}]
    if producer:
        out.append(dict(producer))
    out.append(software_entry(ADDON_NAME, os.path.dirname(os.path.abspath(__file__))))
    dtc = _dtcstamp()
    out.append({"name": "dtcstamp", "version": getattr(dtc, "__version__", "?")})
    return out


def current_operator() -> Optional[Dict[str, Any]]:
    """Who is exporting, if EMtools knows.

    * in a ROOM, the identity the room reports for the token (``sync_manager``);
    * otherwise (dev28, decision 17) the LOCAL identity of the preferences: an
      iD declared and checked by nobody, so ``auth: {mode: declared}``;
    * otherwise None — and the stamp names no operator (the format's rule: the
      agent is the software in ``how``)."""
    # T1 (4 Oct 2026) · the session lives in `room_session`, and it is read
    # through the module at each call: `activate()` rebinds `SESSION` to the
    # active graph's room. The import used to name `operators.SESSION`, which
    # does not exist — the ImportError was swallowed below and no stamp made
    # in a room ever carried the room's author.
    try:
        from .sync_manager import room_session
    except ImportError:                             # no room module (tests, CLI)
        room_session = None
    session = getattr(room_session, "SESSION", None) if room_session else None
    author = str(getattr(session, "author", "") or "").strip() \
        if session is not None and getattr(session, "joined", False) else ""
    if author:
        orcid = author.rsplit("/", 1)[-1]
        if len(orcid) == 19 and orcid.count("-") == 3:
            return {"id": f"https://orcid.org/{orcid}"}
        return {"id": author}
    return local_operator()


def local_operator() -> Optional[Dict[str, Any]]:
    """The local identity of the preferences as ``by.operator``, or None."""
    try:
        from . import local_identity
    except ImportError:
        import local_identity  # type: ignore  # tests: repo root on the path
    try:
        import bpy
        prefs = bpy.context.preferences.addons[_addon_package()].preferences
        return local_identity.declared_operator(getattr(prefs, "local_orcid", ""),
                                                getattr(prefs, "local_name", ""))
    except Exception:                               # noqa: BLE001 — no prefs: nobody
        return None


def master_of(obj, *, graph=None, scene=None) -> Optional[Dict[str, Any]]:
    """What Blender knows of the object an export started from.

    The master's id is EMtools' internal resource (``<rm>_res_blend``) when the
    object is an RM of the active graph, else one derived from the locator — the
    same object in the same file keeps the same id across saves."""
    import bpy
    if obj is None:
        return None
    from .rm_manager.containers import (SUFFISSO_RISORSA_INTERNA, blend_locator_per,
                                        impronta_di, resolve_rm_node_id)
    locator = blend_locator_per(obj)
    rm_id = resolve_rm_node_id(graph, obj, scene=scene, migra=False) if graph is not None else None
    if rm_id:
        rid = f"{rm_id}{SUFFISSO_RISORSA_INTERNA}"
    else:
        import uuid
        rid = "blend:" + str(uuid.uuid5(uuid.NAMESPACE_URL, locator or f"unsaved#{obj.name}"))
    blend = bpy.path.abspath(bpy.data.filepath) if bpy.data.filepath else ""
    return {"resource_id": rid, "label": obj.name, "locator": locator,
            "blend_digest": file_sha256(blend),
            "blend_saved": bool(blend) and not bpy.data.is_dirty,
            "fingerprint": impronta_di(obj), "rm_id": rm_id}


def active_graph(context=None):
    """The active graph, or None (no graph is not an error for a stamp)."""
    try:
        from .functions import check_active_graph
        import bpy
        ok, graph = check_active_graph(context or bpy.context, show_message=False)
        return graph if ok else None
    except Exception:                               # noqa: BLE001
        return None


def stamp_blender_export(path: str, *, objects=None, dtc_kind: str = KIND_EXPORT,
                         technique: str = "", parameters: Optional[Dict[str, Any]] = None,
                         producer: Optional[Dict[str, str]] = None,
                         parents: Optional[List[Dict[str, Any]]] = None,
                         resource_id: Optional[str] = None,
                         label: Optional[str] = None,
                         register_in_graph: bool = True, context=None,
                         force: bool = False) -> Dict[str, Any]:
    """THE call for an export made in Blender — EMtools' and 3DSC's.

    ``objects`` the meshes it was made from (the masters); ``producer`` the
    ``{name, version, commit}`` of the add-on that wrote the file when it is not
    EMtools (3DSC passes its own). With the preference off it writes nothing and
    says so (``state: off``) unless ``force``. When the single master is an RM of
    the active graph and ``register_in_graph``, the distribution also enters the
    graph (:func:`register_distribution`)."""
    import bpy
    if not force and not stamping_enabled():
        return {"state": "off", "line": "stamping is off (Preferences ▸ EM Tools)",
                "stamp_path": "", "stamp": None}
    ctx = context or bpy.context
    graph = active_graph(ctx)
    masters = [m for m in (master_of(o, graph=graph, scene=getattr(ctx, "scene", None))
                           for o in (objects or [])) if m]
    how = {"dtc_kind": dtc_kind}
    if technique:
        how["technique"] = technique
    if parameters:
        how["parameters"] = {k: v for k, v in parameters.items()
                             if isinstance(v, (str, int, float, bool)) or v is None}
        if "operator" in how["parameters"]:
            how["parameters"]["operator"] = python_idname(how["parameters"]["operator"])
    how["software"] = blender_software(producer)
    result = stamp_export(path, masters=masters, parents=parents, how=how,
                          operator=current_operator(), resource_id=resource_id,
                          label=label)
    result["graph"] = ""
    if (register_in_graph and graph is not None and len(masters) == 1
            and masters[0].get("rm_id") and result["state"] in ("stamped", "revised")):
        result["graph"] = register_distribution(graph, objects[0], path, result,
                                                rm_id=masters[0]["rm_id"])
    return result


def adopt_graph_id(result: Dict[str, Any], resource_id: str) -> None:
    """Give the written stamp the id the graph gave the distribution (its current
    revision), so the stamp and the node name the same resource. Rewrites the
    ``.stamp.json`` only when the id differs."""
    stamp = result.get("stamp")
    if not stamp or not resource_id or result.get("state") not in ("stamped", "revised"):
        return
    if stamp["self"].get("resource_id") == resource_id:
        return
    stamp["self"]["resource_id"] = resource_id
    _dtcstamp().write_stamp(stamp, result["stamp_path"])


def register_distribution(graph, obj, path: str, result: Dict[str, Any], *, rm_id: str) -> str:
    """The distribution in the graph, beside its RM: ``api.add_resource`` (or
    ``replace_file`` for new bytes) through ``resource_levels.registra_derivata``
    — the same path as the Heriverse bake — with ``dtc_derived_from`` the
    internal master. → a line for the report."""
    from . import resource_levels as rl
    from .rm_manager.containers import SUFFISSO_RISORSA_INTERNA, blend_locator_per, misura_oggetto
    master_id = f"{rm_id}{SUFFISSO_RISORSA_INTERNA}"
    locator = blend_locator_per(obj)
    if locator:
        rl.assicura_master(graph, master_id=master_id, url=locator,
                           name=f"datablock for {obj.name}", link_to=rm_id,
                           misure=misura_oggetto(obj))
    ext = os.path.splitext(path.rstrip("/\\"))[1].lstrip(".").lower() or "tileset"
    derivata_id = f"{rm_id}_export_{ext}"
    packaging = result.get("packaging") or None
    membri = None
    itself = (result.get("stamp") or {}).get("self") or {}
    if packaging == "file_set":
        #: the members dtcstamp found (obj → mtl → textures, gltf → bin →
        #: images), the door excluded: `specifiche_del_file_set` adds it
        base = os.path.dirname(os.path.abspath(path))
        membri = [{"path": m["path"], "file": os.path.join(base, *m["path"].split("/"))}
                  for m in itself.get("members") or [] if m.get("role") != "entry_point"]
    file_esportato = path
    contenuto = None
    if os.path.isdir(path):
        file_esportato = os.path.join(path, "tileset.json")
        contenuto = itself.get("digest")
    ok, why = rl.registra_derivata(
        graph, derivata_id=derivata_id, url=path, source_id=master_id if locator else None,
        link_to=rm_id, name=os.path.basename(path.rstrip("/\\")),
        file_esportato=file_esportato, packaging=packaging, membri=membri,
        contenuto=contenuto)
    if not ok:
        return f"graph: not registered ({why})"
    from s3dgraphy import api as _api
    current = _api.current_revision(graph, derivata_id)
    adopt_graph_id(result, current)
    return f"graph: {current}" + (f" ({why})" if why else "")
