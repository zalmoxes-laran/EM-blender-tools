"""R4 · every version is born with its dtcstamp.

E.D. (6 Oct 2026, «molto importante»): a version made by the tools — «Prepare
for a use…», «Add version…» (Asset versions, the LODs), a version for
Heriverse/ATON — is born with its **stamp**: the receipt of its DTC step
(process, who, when, with which tool, the inputs with their digests, the
recipe), written with dtcstamp beside the version's files and recorded in the
graph. **A version without a stamp is not born**: the stamp is written BEFORE
the version enters the graph, and a stamp that could not be written, or whose
digest is not the one the graph will register, cancels the version.

The stamp is ``birth_stamp.stamp_export``'s (the same writer as every export of
EM Tools, dtcstamp in the bundle), so the bytes are MEASURED on disk — a glTF
with its .bin and textures is a ``file_set`` checked member by member. What is
added here is what a version knows and an export does not:

* ``from`` is the step's input — the version it was made from, by id and
  digest, or the master (the datablock, by id, with the fingerprint and the
  sha256 of its ``.blend``);
* ``how`` is ``lod_generation`` with the technique and the recipe
  (``version_recipe``) as parameters;
* in the graph, the version carries ``stamp_receipt`` (``dtcstamp.receipt``, the
  same form the Shelf keeps: ``s3dgraphy.shelf.core.STAMP_RECEIPT_KEY``).

``bpy``-free except where marked: the suite drives it with real files.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

#: the key the graph keeps the receipt under (the Shelf's)
RECEIPT_KEY = "stamp_receipt"

#: the states of ``birth_stamp.stamp_export`` that mean «the stamp is there»
STAMPED = ("stamped", "revised", "unchanged")


def _birth_stamp():
    try:
        from . import birth_stamp  # inside the addon package
    except ImportError:
        import birth_stamp  # type: ignore  # tests: repo root on the path
    return birth_stamp


def _dtc():
    try:
        from . import resource_digest
    except ImportError:
        import resource_digest  # type: ignore
    return resource_digest.dtcstamp()


def scalar_parameters(parameters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The parameters a stamp's ``how`` takes: scalars only (a placement, a
    list, goes in the graph's step, not in the stamp)."""
    return {k: v for k, v in (parameters or {}).items()
            if isinstance(v, (str, int, float, bool)) or v is None}


def inputs_for(graph, mother_id: str, *, master: Optional[Dict[str, Any]] = None
               ) -> Dict[str, List[Dict[str, Any]]]:
    """``{masters, parents}`` for ``birth_stamp.stamp_export``: the input of the
    step. A mother that is a version (it has bytes) is a parent by id and
    digest; a mother that is the master (a datablock) is the master entry —
    ``master`` (``birth_stamp.master_of``) with the graph's id for it."""
    node = graph.find_node_by_id(mother_id) if graph is not None else None
    data = (getattr(node, "data", None) or {}) if node is not None else {}
    digest = str(data.get("checksum") or "")
    tier = str(data.get("tier") or "")
    if digest.startswith("sha256:") and tier != "master":
        entry = {"resource_id": str(mother_id), "digest": digest, "tier": "distribution"}
        label = str(getattr(node, "name", "") or "")
        if label:
            entry["label"] = label
        if data.get("packaging"):
            entry["packaging"] = str(data["packaging"])
        return {"masters": [], "parents": [entry]}
    m = dict(master or {})
    m["resource_id"] = str(mother_id)
    if not m.get("label"):
        m["label"] = str(getattr(node, "name", "") or mother_id)
    return {"masters": [m], "parents": []}


def stamp_version(entry_path: str, *, version_id: str, inputs: Dict[str, List],
                  technique: str, parameters: Dict[str, Any], label: str,
                  expected_digest: str = "", operator=None, software=None,
                  revision_of: Optional[Dict[str, Any]] = None,
                  stamp_export=None) -> Dict[str, Any]:
    """Write the stamp of a version whose bytes are at ``entry_path`` (the
    file, or the door of a file set). ``expected_digest`` is the checksum the
    graph will register: a stamp measuring other bytes is refused.
    ``revision_of`` (``{resource_id, digest}``): the version this one revises
    (the same level made again with another recipe), written as the stamp's
    ``self.was_revision_of``.

    → ``birth_stamp.stamp_export``'s result plus ``ok`` and, when not ok,
    ``why``."""
    bs = _birth_stamp()
    how = {"dtc_kind": bs.KIND_LOD, "parameters": scalar_parameters(parameters)}
    if technique:
        how["technique"] = technique
    if software:
        how["software"] = software
    writer = stamp_export or bs.stamp_export
    result = writer(entry_path, masters=inputs.get("masters") or [],
                    parents=inputs.get("parents") or [], how=how, operator=operator,
                    resource_id=version_id, label=label)
    result["ok"] = False
    if result.get("state") not in STAMPED:
        result["why"] = result.get("line") or "the stamp was not written"
        return result
    stamp = result.get("stamp") or {}
    itself = stamp.get("self") or {}
    if expected_digest and itself.get("digest") != expected_digest:
        result["why"] = (f"the stamp measures {str(itself.get('digest'))[:19]}…, the "
                         f"version registers {expected_digest[:19]}…")
        return result
    if result["state"] == "unchanged" and itself.get("resource_id") != version_id:
        result["why"] = (f"these bytes are already stamped as "
                         f"{itself.get('resource_id')}, not as {version_id}")
        return result
    if revision_of and result["state"] != "unchanged" and not itself.get("was_revision_of"):
        itself["was_revision_of"] = {k: v for k, v in revision_of.items() if v}
        _dtc().write_stamp(stamp, result["stamp_path"])
    result["ok"] = True
    return result


def receipt(stamp: Dict[str, Any]) -> Dict[str, Any]:
    """``dtcstamp.receipt``: what the graph keeps of the stamp."""
    return _dtc().receipt(stamp)


def record(graph, version_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """The receipt on the version's node (``stamp_receipt``), the stamp
    rewritten with the graph's id if the graph gave another. → the receipt."""
    node = graph.find_node_by_id(version_id)
    if node is None:
        raise ValueError(f"{version_id!r} is not in the graph")
    _birth_stamp().adopt_graph_id(result, version_id)
    rec = receipt(result["stamp"])
    node.data[RECEIPT_KEY] = rec
    return rec


def check(graph, version_id: str) -> Dict[str, Any]:
    """Whether the version's stamp is there and its bytes are the stamped
    ones: ``{state, line, stamp_path, receipt, mother}`` — ``state`` one of
    ``ok``, ``differs``, ``missing`` (no bytes), ``no_stamp``, ``other``
    (the stamp beside the file names another resource). ``mother`` is True
    when the stamp's ``from`` names the input of the graph's step."""
    try:
        from . import resource_seal
    except ImportError:
        import resource_seal  # type: ignore
    node = graph.find_node_by_id(version_id)
    data = (getattr(node, "data", None) or {}) if node is not None else {}
    url = str(data.get("url") or "")
    out = {"state": "no_stamp", "line": "no stamp", "stamp_path": "",
           "receipt": data.get(RECEIPT_KEY), "mother": False}
    path = resource_seal.find_stamp(url) if url and "://" not in url else None
    if not path:
        out["line"] = "no stamp beside its file" if url else "no file"
        return out
    stamp, _raw = resource_seal.load(path)
    out["stamp_path"] = path
    if (stamp.get("self") or {}).get("resource_id") != version_id:
        out.update(state="other", line=f"the stamp beside it is "
                                       f"{(stamp.get('self') or {}).get('resource_id')}")
        return out
    res = resource_seal.verify_cached(stamp, path, url)
    out.update(state=res["state"], line=res["line"])
    try:
        from s3dgraphy import api
        made_by = api.derivation_chain(graph, version_id).get("made_by") or []
        inputs = {i for ev in made_by for i in (ev.get("inputs") or [])}
    except Exception:  # noqa: BLE001 — a graph without the chain: no claim
        inputs = set()
    named = {str(p.get("resource_id")) for p in stamp.get("from") or []}
    out["mother"] = bool(inputs) and inputs <= named
    return out


def said(state: Dict[str, Any]) -> str:
    """One line for «Where it comes from»."""
    if state["state"] == "ok":
        return "stamp ✓ " + (state.get("line") or "the bytes are the stamped ones") \
            + (" · from its mother" if state.get("mother") else "")
    if state["state"] == "no_stamp":
        return "no stamp: " + state.get("line", "")
    return f"stamp ▲ {state.get('line', '')}"


def entry_of(files: List[Dict[str, Any]]) -> str:
    """The path a stamp is written beside: the entry point's file."""
    door = next((f for f in files if f.get("role") == "entry_point"), files[0] if files else {})
    return str(door.get("url") or door.get("path") or "")


def operator_and_software():  # pragma: no cover — bpy
    """Who stamps and with what: ``(operator, software)`` from Blender."""
    bs = _birth_stamp()
    return bs.current_operator(), bs.blender_software()


def exists(path: str) -> bool:
    return bool(path) and os.path.exists(path)
