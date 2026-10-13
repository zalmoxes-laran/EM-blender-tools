"""MICRO-RM-WEB (13 Oct 2026) · an RM that lives in a .blend reaches the room
as a glb the graph cites, and «Upload» never sends a whole .blend.

Measured at 19:30 in the room `tavolo-2026-10-12` (editor2): in Files, on the
row «ME_EST_bk_LOD0 — model in this .blend», «Upload» sent 539 181 434 bytes
of ``application/x-blender`` — the whole ``TempluMare_2021.blend``, not the
model — and wrote nothing in the graph: the RM still cited only its
``blend://…#Object/ME_EST_bk_LOD0`` (no checksum, no residency), EMStudio said
«reference-only file», and the node refused the bytes to the room's people
(403: the graph of the room did not cite them).

The rules:

* a model as it lives in the .blend is not uploaded as it is: its gesture is
  **«Send a web version»** — the object exported as a glb by the way of
  «Prepare for a use…» (use ``web``), sent to the store, and in the graph a
  DISTRIBUTION version of the asset (``resources.versions``: ``tier
  distribution``, ``checksum``, ``residency resident``, ``model/gltf-binary``),
  made from the master by its ``lod_generation`` step — never
  ``was_revision_of`` it (a glb is not a revision of a datablock) — and sent to
  the room closed over what the room holds (the RM, its epoch and datablock
  with it);
* «Upload» on such a row refuses, and says the gesture; the whole .blend has
  its own («Archive this .blend»);
* «Upload» RECORDS what it sent: the resource gets ``checksum``, ``residency
  resident`` and its ``url`` on the room's one base, the disk path kept as a
  second address — so the room sees it and the node lets its people read it
  (the citation opens the gate).

The decisions are pure, the effects (export, upload, the store url) are
passed in; the operators are in `file_states`.
"""

from typing import Any, Callable, Dict, List

#: the use a «Send a web version» version serves (``resources.versions.USES``)
WEB_USE = "web"
GLB_MEDIA = "model/gltf-binary"
RM_TYPES = ("representation_model", "representation_model_doc",
            "representation_model_sf")


def _gov():
    try:
        from .. import resource_governance as governance
    except ImportError:              # loaded by path, outside the package (the suite)
        import resource_governance as governance
    return governance


def _data(node) -> Dict[str, Any]:
    data = getattr(node, "data", None)
    return data if isinstance(data, dict) else {}


def _digest(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return text if text.startswith("sha256:") else "sha256:" + text


def is_datablock(graph, rid: str) -> bool:
    """Is this row a model as it lives in the .blend — the internal resource
    of an RM («Blend datablock for …»), a ``blend://`` locator, a ``datablock``
    packaging?"""
    if graph is None or not rid:
        return False
    if _gov().datablock_object(graph, rid):
        return True
    data = _data(graph.find_node_by_id(rid))
    return (str(data.get("url") or "").startswith("blend://")
            or data.get("packaging") == "datablock")


def object_of(graph, rid: str) -> str:
    """The object of the .blend a datablock row is (``ME_EST_bk_LOD0``), from
    its name or its ``#Object/…`` locator; "" when it says none."""
    held = _gov().datablock_object(graph, rid)
    if held:
        return held
    url = str(_data(graph.find_node_by_id(rid)).get("url") or "")
    if "#Object/" in url:
        import urllib.parse
        return urllib.parse.unquote(url.split("#Object/", 1)[1])
    return ""


def upload_refusal(graph, rid: str) -> str:
    """Why «Upload» does not send this row, or "" when it may."""
    if not is_datablock(graph, rid):
        return ""
    name = object_of(graph, rid) or "this model"
    return (f"{name} lives in the .blend: Upload would send the whole .blend. "
            f"«Send a web version» sends it as a glb "
            f"(the whole .blend: «Archive this .blend»)")


def rm_of(graph, rid: str) -> str:
    """The RM that cites this resource (or a version of its chain), ""."""
    gov = _gov()
    for member in gov.chain_of(graph, rid):
        for c in gov.citing(graph, member):
            node = graph.find_node_by_id(c["source"])
            if getattr(node, "node_type", "") in RM_TYPES:
                return c["source"]
    return ""


def point_at_store(graph, rid: str, url: str, digest: str) -> None:
    """The resource now says where the room keeps its bytes: ``checksum``,
    ``residency resident`` (a resource; a file of a set carries no residency),
    ``url`` on the room's base. The address it had (the disk, the cache) stays
    as a second address, the store's first."""
    node = graph.find_node_by_id(rid)
    if node is None:
        raise ValueError(f"no resource {rid}")
    digest = _digest(digest)
    if not digest or not url:
        raise ValueError("a resource is resident only with its digest and its store url")
    data = node.data if isinstance(getattr(node, "data", None), dict) else {}
    node.data = data
    had = str(data.get("url") or "")
    data["checksum"] = digest
    data["url"] = url
    if getattr(node, "node_type", "") == "resource":
        data["residency"] = "resident"
    if hasattr(node, "url"):
        node.url = url
    if had and had != url and not had.startswith("blend://"):
        listed = [a for a in (data.get("addresses") or []) if isinstance(a, dict)
                  and a.get("locator") not in (url, had)]
        data["addresses"] = ([{"locator": url, "residency": "resident"},
                              {"locator": had, "residency": "resident"}] + listed)


def upload_row(graph, row: Dict[str, Any], *,
               upload: Callable[[Dict[str, Any]], Dict[str, Any]],
               store_url: Callable[[str], str]) -> Dict[str, Any]:
    """«Upload» on one row of Files: refused for a model in the .blend
    (nothing is sent), else the bytes sent (`upload(row)` → the node's answer,
    ``{sha256, already}``) and recorded on the resource (`point_at_store`).
    → ``{ok, error?, digest?, already?}``; the caller sends the change."""
    refusal = upload_refusal(graph, row.get("id", ""))
    if refusal:
        return {"ok": False, "error": refusal}
    if not row.get("path"):
        return {"ok": False, "error": "nothing on the disk to upload"}
    out = upload(row)
    digest = _digest(out.get("sha256") or out.get("ref") or row.get("sha256"))
    url = store_url(digest) if digest else ""
    if digest and url:
        point_at_store(graph, row["id"], url, digest)
    return {"ok": True, "digest": digest, "already": bool(out.get("already")),
            "recorded": bool(digest and url)}


def send_web_version(graph, rid: str, *,
                     prepare: Callable[[str], Dict[str, Any]],
                     upload: Callable[[Dict[str, Any]], Dict[str, Any]],
                     store_url: Callable[[str], str]) -> Dict[str, Any]:
    """«Send a web version» of a model in the .blend.

    `prepare(object_name)` makes the version the way «Prepare for a use…»
    does (use ``web``) → ``{version_id, asset_id, files}``; each file goes to
    the store (`upload(file)`), and the version points at it. Refused when
    the row is not a datablock, or when the version is not of this asset.
    → ``{ok, error?, version_id, rm_id, object, sent}``; the caller sends the
    change with the RM brought (`scene_sync.close_over`)."""
    if not is_datablock(graph, rid):
        return {"ok": False, "error": "a web version is made of a model in the .blend: "
                                      "this file is uploaded as it is"}
    name = object_of(graph, rid)
    if not name:
        return {"ok": False, "error": "this model names no object of the .blend"}
    made = prepare(name)
    vid = str(made.get("version_id") or "")
    vnode = graph.find_node_by_id(vid) if vid else None
    if vnode is None:
        return {"ok": False, "error": f"{name}: no version was made"}
    gov = _gov()
    asset = str(made.get("asset_id") or "")
    if asset and asset not in gov.chain_of(graph, rid) and rid not in gov.chain_of(graph, asset):
        return {"ok": False, "error": f"{name}: the version made is of another model ({asset})"}
    sent: List[str] = []
    for f in made.get("files") or []:
        got = upload(f)
        sent.append(_digest(got.get("sha256") or got.get("ref") or f.get("checksum")))
    digest = _digest(_data(vnode).get("checksum")) or (sent[0] if len(sent) == 1 else "")
    if not digest:
        return {"ok": False, "error": f"{name}: the version has no digest"}
    point_at_store(graph, vid, store_url(digest), digest)
    return {"ok": True, "version_id": vid, "rm_id": rm_of(graph, rid), "object": name,
            "sent": sent, "digest": digest}


def said(out: Dict[str, Any], graph=None) -> str:
    """The line for the person after «Send a web version»."""
    if not out.get("ok"):
        return str(out.get("error") or "not sent")
    rm = out.get("rm_id") or ""
    whose = ""
    if graph is not None and rm:
        node = graph.find_node_by_id(rm)
        whose = f" · {getattr(node, 'name', '') or rm} shows it" if node is not None else ""
    return f"{out['object']}: a web version sent to the room{whose}"
