"""H4 · Heriverse as a destination: two roads, ON THE NODE and ON DISK.

E.D., 5 Oct 2026 («Heriverse legge l'em.json e sceglie la versione», and the
correction of the evening): nothing is re-exported from Blender for Heriverse.
Heriverse reads the study (em.json) and, for each representation model, picks
by itself among the resources hung on it the version to load, with ONE rule
that lives in s3dgraphy: ``api.version_for(graph, rm_id, VIEWER_USES)`` —
heriverse, aton, web, realtime, in that order (the pure part is
``resources.versions.choose_version``). Two roads lead there:

* **on the node** — the em.json and the assets are in the room, and Heriverse
  fetches the chosen version by its sha256 (H3). This module says, for each
  published model, what the rule picks and whether its bytes are on the node;
* **on disk** — the desktop keeps working without a node: a FOLDER with the
  em.json and the versions it names (``versions/…``, paths relative to the
  em.json), which Heriverse opens offline (as a zip, its server reads
  ``project.json``) and so does an ATON app. A version for Heriverse is a
  VERSION like any other — use ``heriverse``/``aton``, made by «Prepare for a
  use…» as the model is (Q5: no optimisation of its own), registered with its
  sha256 — and the package copies its bytes byte for byte and checks them.

The rule is NOT copied here: it is asked to s3dgraphy, and a s3dgraphy without
it is said in one line (:func:`version_for_function`) instead of guessed.

Which models are published is what the Heriverse exporter read: the rows of
the RM list (``scene.rm_list``) with ``is_publishable`` (``publication_flags``
explains why that flag is the inclusion for Heriverse), minus the models the
dissemination policy removes (``s3dgraphy.dissemination.is_removed_node``: a
deleted node is absent, not marked — and the em.json of the package is the
``heriverse`` surface, ``dissemination.live_view``). The Blender side picks the
rows and the folders; this file has no ``bpy`` and is tested headless.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import zipfile
from typing import Any, Callable, Dict, Iterable, List, Optional

#: the uses Heriverse asks for, in its order (`publication_targets.USI_HERIVERSE`,
#: `s3dgraphy.resources.versions.VIEWER_USES`)
USES = ("heriverse", "aton", "web", "realtime")

#: the uses a version made FOR Heriverse carries (the disk package's)
PACKAGE_USES = ("aton", "heriverse")

#: the answers of the rule that are a version (not the master)
READY = ("level", "use")

#: the resolver's states (R1, `s3dgraphy.resources.locate`) that mean «on the node»
ON_NODE_STATES = ("on_node", "both")

NO_VERSION_FOR = "this s3dgraphy has no version_for: update it"

#: inside the package: where the versions go, and the two names of the study
VERSIONS_DIR = "versions"
EM_JSON = "em.json"
#: the name the Heriverse server reads from an uploaded zip
#: (Heriverse-Server `storage/*StorageAdapter.getHeriverseProject`)
PROJECT_JSON = "project.json"


def version_for_function() -> Optional[Callable[..., Any]]:
    """``s3dgraphy.api.version_for``, or None when the s3dgraphy in use is older
    than the rule (the wheel bundled up to 1.6.0.dev38 has not got it)."""
    try:
        from s3dgraphy import api
    except ImportError:
        return None
    return getattr(api, "version_for", None)


def s3dgraphy_version() -> str:
    try:
        import s3dgraphy
    except ImportError:
        return "none"
    return str(getattr(s3dgraphy, "__version__", "?"))


def said_uses(uses: Iterable[str] = USES) -> str:
    """«heriverse, aton, web or realtime»."""
    uses = [str(u) for u in uses]
    return f"{', '.join(uses[:-1])} or {uses[-1]}" if len(uses) > 1 else "".join(uses)


def short_sha(checksum: Any, n: int = 12) -> str:
    """``sha256:ab12…`` → ``ab12…`` (``n`` hex digits); ``""`` when there is none."""
    s = str(checksum or "").strip()
    if ":" in s:
        s = s.split(":", 1)[1]
    return s[:n]


def sha_hex(checksum: Any) -> str:
    """The bare lowercase hex of a sha256 checksum, ``""`` when it is not one."""
    m = re.match(r"^(?:sha256:)?([0-9a-fA-F]{64})$", str(checksum or "").strip())
    return m.group(1).lower() if m else ""


def sha256_of_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_store_url(url: str) -> bool:
    """A node's asset address (`…/v1/rooms/<room>/asset/sha256:<hex>`): the
    same test as `sync_manager.inventory._is_store_url`."""
    try:
        from .sync_manager.inventory import _is_store_url as store
    except ImportError:      # loaded outside the package (the suite): the
        store = None         # package imports bpy, its one line is below
    if store is not None:
        return bool(store(str(url or "")))
    u = str(url or "")
    return "/v1/rooms/" in u and "/asset/sha256:" in u


def on_node(entry: Dict[str, Any], states: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Whether the bytes of ``entry`` are on the node, and how it is known.

    ``states`` is the last resolution of the graph (``{resource_id: state}``
    of «Check files», `sync_manager/file_states.py`, R1): when it knows the
    entry, it is the answer. Otherwise the entry's own address speaks: a
    sha256 and a node asset address → on the node by its address; a sha256
    and another address → not checked; no sha256 → Heriverse cannot ask the
    node for it. ``{state, said}``: ``state`` is ``yes`` / ``no`` /
    ``unknown``."""
    rid = str(entry.get("id") or "")
    known = (states or {}).get(rid)
    if known:
        if known in ON_NODE_STATES:
            return {"state": "yes", "said": "on the node"}
        return {"state": "no", "said": known.replace("_", " ")}
    if not entry.get("checksum"):
        return {"state": "no", "said": "no sha256"}
    if _is_store_url(entry.get("url") or ""):
        return {"state": "yes", "said": "on the node (its address)"}
    return {"state": "unknown", "said": "not checked: Check files"}


def is_removed(node) -> bool:
    """The dissemination predicate of s3dgraphy; False when it is missing."""
    try:
        from s3dgraphy.dissemination import is_removed_node
    except ImportError:
        return False
    return bool(is_removed_node(node))


def plan_for(graph, rms: Iterable[Any], *, uses=USES,
             states: Optional[Dict[str, str]] = None,
             version_for: Optional[Callable[..., Any]] = None) -> Dict[str, Any]:
    """What Heriverse will find for each model of ``rms``.

    ``rms``: node ids, or ``(node_id, object_name)`` pairs (the object is
    what «Prepare for a use…» needs). Returns ``{available, note, ready,
    missing, removed, absent}``:

    * ``ready`` — one row per model whose rule answers a version for one of
      ``uses``: ``{rm_id, rm_name, object, name, lod_level, use, sha, reason,
      note, on_node, on_node_said, version_id, asset_id, checksum, url,
      media_type}``;
    * ``missing`` — the models with no such version (``reason`` ``master``:
      the master is loaded; ``none``: nothing to load), same keys, ``name``
      the master's when there is one;
    * ``removed`` — how many were left out by the dissemination policy;
    * ``absent`` — the ids not in the graph.

    ``available`` is False, with ``note`` :data:`NO_VERSION_FOR`, when the
    s3dgraphy in use has no ``version_for``: nothing is guessed then.
    """
    fn = version_for if version_for is not None else version_for_function()
    out: Dict[str, Any] = {"available": fn is not None, "note": "", "ready": [],
                           "missing": [], "removed": 0, "absent": [],
                           "uses": list(uses)}
    if fn is None:
        out["note"] = f"{NO_VERSION_FOR} (s3dgraphy {s3dgraphy_version()})"
        return out
    seen = set()
    for item in rms or ():
        rm_id, obj_name = (item if isinstance(item, (tuple, list)) else (item, ""))
        rm_id = str(rm_id or "")
        if not rm_id or rm_id in seen:
            continue
        seen.add(rm_id)
        node = graph.find_node_by_id(rm_id) if graph is not None else None
        if node is None:
            out["absent"].append(rm_id)
            continue
        if is_removed(node):
            out["removed"] += 1
            continue
        try:
            choice = fn(graph, rm_id, list(uses))
        except ValueError:
            out["absent"].append(rm_id)
            continue
        choice = choice or {"entry": None, "reason": "none", "use": None,
                            "note": "nothing hangs on it", "asset_id": None}
        entry = choice.get("entry") or {}
        where = on_node(entry, states) if entry else {"state": "no", "said": ""}
        row = {"rm_id": rm_id, "rm_name": str(getattr(node, "name", "") or rm_id),
               "object": str(obj_name or ""),
               "name": str(entry.get("name") or ""),
               "lod_level": entry.get("lod_level") or "",
               "use": choice.get("use") or "",
               "sha": short_sha(entry.get("checksum")),
               "reason": choice.get("reason") or "none",
               "note": choice.get("note") or "",
               "on_node": where["state"], "on_node_said": where["said"],
               "version_id": str(entry.get("id") or ""),
               "asset_id": str(choice.get("asset_id") or ""),
               "checksum": str(entry.get("checksum") or ""),
               "url": str(entry.get("url") or ""),
               "media_type": str(entry.get("media_type") or "")}
        (out["ready"] if row["reason"] in READY else out["missing"]).append(row)
    return out


def summary(plan: Dict[str, Any]) -> str:
    """One line for the head of the popup."""
    if not plan.get("available"):
        return plan.get("note") or NO_VERSION_FOR
    ready, missing = plan.get("ready") or [], plan.get("missing") or []
    off = sum(1 for r in ready if r["on_node"] != "yes")
    parts = [f"{len(ready)} model(s) with a version for "
             f"{said_uses(plan.get('uses') or USES)}"]
    if off:
        parts.append(f"{off} of them not known to be on the node")
    parts.append(f"{len(missing)} without one")
    if plan.get("removed"):
        parts.append(f"{plan['removed']} removed (not published)")
    return " · ".join(parts)


def row_line(row: Dict[str, Any]) -> str:
    """What the rule picks for one model, in one line (the Deck's list)."""
    if row["reason"] in READY:
        level = str(row.get("lod_level") or "").upper()
        return (f"{row['rm_name']} → {row['use']} version {level}".rstrip()
                + (f", sha256 {row['sha']}…" if row.get("sha") else ""))
    if row["reason"] == "master":
        return (f"{row['rm_name']}: no version for {said_uses()}, the master "
                f"is loaded" + (f" (sha256 {row['sha']}…)" if row.get("sha") else ""))
    return f"{row['rm_name']}: nothing Heriverse can load"


# ── ON DISK: the package (H4, E.D. 5 Oct 2026, evening) ────────────────────
#
# A folder beside nothing: the em.json (and the same document as project.json,
# the name the Heriverse server reads from a zip) and `versions/`, the bytes of
# the version the rule picks for each published model. In the package em.json
# the url of each of those resources is its path in the folder; its sha256 is
# the registered one, and the copy is checked against it. Nothing else of the
# study changes: the other resources keep the address they have.


def local_bytes(row: Dict[str, Any], *, roots: Iterable[str] = (),
                caches: Iterable[str] = ()) -> Dict[str, str]:
    """Where the bytes of a chosen resource are ON THIS DISK.

    The candidates, in order: its url when it is a path (absolute, or relative
    to one of ``roots`` — the .blend's folder, the em.json's); then, in the
    ``caches`` (the ``em_cache`` folders, where «Prepare for a use…» writes a
    version), a file with the same name. A candidate counts only if its sha256
    is the registered one: a file with the right name and other bytes is not
    the version. ``{path, said}``; ``path`` empty when there is none."""
    want = sha_hex(row.get("checksum"))
    if not want:
        return {"path": "", "said": "no sha256: the package could not check it"}
    url = str(row.get("url") or "")
    candidates: List[str] = []
    if url and "://" not in url and not url.startswith("//"):
        if os.path.isabs(url):
            candidates.append(url)
        else:
            candidates += [os.path.join(r, url) for r in roots if r]
    name = os.path.basename(url.split("?")[0]) if url and "://" not in url else ""
    for cache in caches:
        if not cache or not os.path.isdir(cache):
            continue
        for folder, _dirs, files in os.walk(cache):
            if name and name in files:
                candidates.append(os.path.join(folder, name))
    seen = set()
    for path in candidates:
        path = os.path.normpath(path)
        if path in seen or not os.path.isfile(path):
            continue
        seen.add(path)
        if sha256_of_file(path) == want:
            return {"path": path, "said": "on this disk"}
    return {"path": "", "said": "not on this disk" + (" (a file with its name has other "
                                                      "bytes)" if seen else "")}


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._@-]+", "_", str(text or "")).strip("_") or "model"


def _extension(row: Dict[str, Any]) -> str:
    url = str(row.get("url") or "").split("?")[0]
    ext = os.path.splitext(url)[1].lower()
    if ext in OPENED:
        return ext
    media = str(row.get("media_type") or "").lower()
    return {"model/gltf+json": ".gltf"}.get(media, ".glb")


#: the formats Heriverse opens (`Heriverse.canConsumeResource`): glTF, a 3D
#: Tiles tileset, an archive it unpacks
OPENED = (".glb", ".gltf", ".json", ".zip")


def package_relpath(row: Dict[str, Any], taken: Optional[set] = None) -> str:
    """The path of a chosen version in the package: ``versions/<model>@<level
    and use>.<ext>`` (``PODIO@lod0-heriverse.glb``, ``MURO@master.glb``) — a
    name a person reads, made unique with the sha256."""
    tag = ("master" if row["reason"] == "master"
           else "-".join(str(x) for x in (row.get("lod_level"), row.get("use")) if x)
           or "version")
    base = f"{_safe(row.get('rm_name') or row.get('rm_id'))}@{_safe(tag)}"
    rel = f"{VERSIONS_DIR}/{base}{_extension(row)}"
    if taken is not None:
        if rel in taken:
            rel = f"{VERSIONS_DIR}/{base}-{short_sha(row.get('checksum'), 8)}{_extension(row)}"
        taken.add(rel)
    return rel


def disk_plan(plan: Dict[str, Any], *, finder: Callable[[Dict[str, Any]], Dict[str, str]]
              ) -> Dict[str, Any]:
    """The package, before it is written: for each published model whose rule
    answers something (a version, or the master), where its bytes are and where
    they will go. ``{rows, ready, missing_version, no_bytes}``; each row gains
    ``local`` (a path or ``""``), ``local_said`` and ``rel``."""
    taken: set = set()
    rows = []
    for row in list(plan.get("ready") or []) + list(plan.get("missing") or []):
        row = dict(row)
        raw = os.path.splitext(str(row.get("url") or "").split("?")[0])[1].lower()
        if not row.get("version_id"):
            row.update(local="", local_said="nothing to package", rel="")
        elif row["reason"] == "master" and raw and raw not in OPENED:
            # a master in a working format (.blend, .obj…) is not loaded by
            # Heriverse: packaging it would be bytes nobody opens
            row.update(local="", local_said=f"the master is a {raw} file Heriverse does "
                                            f"not open: prepare a version for it", rel="")
        else:
            found = finder(row)
            row.update(local=found["path"], local_said=found["said"],
                       rel=package_relpath(row, taken))
        rows.append(row)
    return {"rows": rows,
            "ready": [r for r in rows if r["reason"] in READY],
            "missing_version": [r for r in rows if r["reason"] not in READY],
            "no_bytes": [r for r in rows if r.get("rel") and not r["local"]]}


def heriverse_document(graphs: Dict[str, Any], *, active: Optional[str] = None) -> Dict[str, Any]:
    """The em.json of the package: the study's graphs as the ``heriverse``
    dissemination surface sees them (removed nodes absent, not marked) — the
    same container shape any em.json has."""
    from s3dgraphy.container import Container, build_container
    from s3dgraphy.dissemination import live_view
    views = {}
    for gid, graph in graphs.items():
        view, _hidden = live_view(graph, surface="heriverse")
        views[gid] = view
    return build_container(Container(graphs=views, active_graph_id=active or next(iter(views), None)))


def rewrite_urls(doc: Dict[str, Any], urls: Dict[str, str]) -> int:
    """In ``doc`` (an em.json, container or single graph), the url of each
    resource of ``urls`` (``{resource_id: path}``) becomes that path. How many
    were rewritten."""
    sections = list((doc.get("graphs") or {}).values())
    if isinstance(doc.get("graph"), dict):
        sections.append(doc["graph"])
    n = 0
    for section in sections:
        for node in section.get("nodes") or [] if isinstance(section, dict) else []:
            rel = urls.get(str(node.get("id")))
            if rel is None:
                continue
            node["data"] = dict(node.get("data") or {}, url=rel)
            n += 1
    return n


def write_package(dest: str, doc: Dict[str, Any], rows: Iterable[Dict[str, Any]], *,
                  fetch: Optional[Callable[[str], Any]] = None,
                  make_zip: bool = False) -> Dict[str, Any]:
    """Write the package into ``dest``: the bytes of each row (from its
    ``local`` path, else from ``fetch(checksum)`` — the node — when given) at
    its ``rel``, CHECKED against the registered sha256; then the em.json with
    those urls, and ``project.json`` (the same document). A row whose bytes
    could not be had or do not match is NOT in the package and is said.

    ``{dest, written: [{rm_name, rel, sha, from}], failed: [{rm_name, why}],
    em_json, project_json, zip}``."""
    os.makedirs(os.path.join(dest, VERSIONS_DIR), exist_ok=True)
    written, failed, urls = [], [], {}
    for row in rows:
        if not row.get("version_id") or not row.get("rel"):
            continue
        want = sha_hex(row.get("checksum"))
        target = os.path.join(dest, *row["rel"].split("/"))
        source = "this disk"
        try:
            if row.get("local"):
                shutil.copyfile(row["local"], target)
            elif fetch is not None and want:
                data = fetch(f"sha256:{want}")
                data = data[0] if isinstance(data, tuple) else data
                with open(target, "wb") as fh:
                    fh.write(data)
                source = "the node"
            else:
                failed.append({"rm_name": row["rm_name"], "why": row.get("local_said")
                               or "its bytes are not on this disk"})
                continue
        except Exception as exc:  # noqa: BLE001 — a refusal is a row
            failed.append({"rm_name": row["rm_name"], "why": str(exc)})
            continue
        got = sha256_of_file(target)
        if want and got != want:
            os.remove(target)
            failed.append({"rm_name": row["rm_name"],
                           "why": f"the bytes are not the registered version (registered "
                                  f"{want[:12]}…, got {got[:12]}…)"})
            continue
        urls[row["version_id"]] = row["rel"]
        written.append({"rm_name": row["rm_name"], "rel": row["rel"], "sha": got,
                        "from": source, "reason": row["reason"], "use": row.get("use") or ""})
    doc = json.loads(json.dumps(doc))
    rewrite_urls(doc, urls)
    text = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    em_json = os.path.join(dest, EM_JSON)
    project_json = os.path.join(dest, PROJECT_JSON)
    for path in (em_json, project_json):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    zip_path = ""
    if make_zip:
        zip_path = dest.rstrip(os.sep) + ".zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for folder, _dirs, files in os.walk(dest):
                for f in sorted(files):
                    full = os.path.join(folder, f)
                    zf.write(full, os.path.relpath(full, dest))
    return {"dest": dest, "written": written, "failed": failed,
            "em_json": em_json, "project_json": project_json, "zip": zip_path}


def package_sentence(report: Dict[str, Any]) -> str:
    """One line for the report of the operator."""
    w, f = report.get("written") or [], report.get("failed") or []
    parts = [f"{len(w)} model(s) in {report.get('dest')}"]
    if f:
        parts.append(f"{len(f)} left out: " + "; ".join(f"{x['rm_name']} ({x['why']})"
                                                       for x in f[:3]))
    return " · ".join(parts)
