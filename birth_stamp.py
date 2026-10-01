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
  private hint (``kind: blend``), written beside the stamp as
  ``<asset>.from.hints.json`` — the same rule as ``new_datablock_stamp``;
* a datablock has no digest of bytes. EMtools' structural fingerprint is
  ``struct:…`` (``resource_levels.impronta_strutturale``), not dtcstamp's
  ``emstruct1:``, so it is NOT written as a ``digest``: it travels in
  ``from[].state.fingerprint``, beside the sha256 of the ``.blend`` as it is on
  disk at that moment and whether it was saved (``blend_saved``);
* ``by.operator`` is written only when EMtools knows who is exporting (the
  identity a room reports for the token). Otherwise it is omitted, and the
  agent is the software in ``how`` — the format's own rule.

``bpy``-free above the line marked «Blender»: the stamps are measured outside
Blender, by pytest.
"""

from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Optional

#: what a stamp says about the kind of step. The dev26 vocabulary
#: (``em_visual_rules.json`` → ``dtc_kinds.process``) has no «export», «LOD» or
#: «tiling»: the nearest kinds are used, the step is said in ``technique``,
#: and the three are a proposal for the dev28.
KIND_EXPORT = "format_conversion"      # datablock → glb/gltf/obj/fbx, folder → 3tz
KIND_LOD = "decimation"                # a LOD baked from the master
KIND_TILING = "transformation"         # a mesh split into a 3D Tiles tree

#: the suffix of the previous stamp when the bytes change: it stays beside the
#: file, a true statement about bytes that are no longer there
PREVIOUS_INFIX = ".prev-"
#: the private hint of the master, beside the stamp
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
    state: Dict[str, Any] = {}
    if master.get("blend_digest"):
        state["blend"] = master["blend_digest"]
    if master.get("blend_saved") is not None:
        state["blend_saved"] = bool(master["blend_saved"])
        if not master["blend_saved"]:
            state["note"] = ("the .blend had unsaved changes: the object exported "
                             "is not the one in this file on disk")
    if master.get("fingerprint"):
        state["fingerprint"] = master["fingerprint"]
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
            stamp["how"] = how
        by: Dict[str, Any] = {"at": when or dtc.now_iso()}
        if operator and operator.get("id"):
            op = {"id": str(operator["id"])}
            if operator.get("label"):
                op["label"] = str(operator["label"])
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
        locators = [m for m in (masters or []) if m.get("locator")]
        if locators:
            hints_path = target[:-len(dtc.STAMP_SUFFIX)] + FROM_HINTS_SUFFIX
            hints = dtc.new_hints(str(locators[0]["resource_id"]))
            for m in locators:
                dtc.note_seen(hints, m["locator"], kind="blend", scope="private",
                              machine=machine, when=by["at"])
            dtc.write_hints(hints, hints_path)
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


def current_operator() -> Optional[Dict[str, str]]:
    """Who is exporting, if EMtools knows: the identity a room reports for the
    token (``sync_manager``). Otherwise None — and the stamp names no operator."""
    try:
        from .sync_manager.operators import SESSION
    except Exception:                               # noqa: BLE001 — no room module
        return None
    author = str(getattr(SESSION, "author", "") or "").strip()
    if not author:
        return None
    orcid = author.rsplit("/", 1)[-1]
    if len(orcid) == 19 and orcid.count("-") == 3:
        return {"id": f"https://orcid.org/{orcid}"}
    return {"id": author}


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
