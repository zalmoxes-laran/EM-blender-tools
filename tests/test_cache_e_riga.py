"""MICRO-CACHE-E-RIGA (13 Oct 2026), room `tavolo-2026-10-12`, editor2.

1 · At 20:36 E.D. moved the four proxies beside the RM and pressed «Sync the
scene…»: four new revisions went to the room, and Files said «4 only on the
node» and offered Download for bytes this computer had just exported. The
rule: every upload that succeeds keeps its bytes in the cache, by their
digest — the name the one resolver reads — so what was sent is «Here and on
the node» (`both`), never `on_node`.

2 · Files showed «ME_EST_bk_LOD0 — model in this .blend» and under it
«ME_EST_bk_LOD0 lod0», the web version made from it: two rows for one model.
The rule: an asset and its versions are one row, «v1/1 · web» on the right,
the sign of the version the scene uses; the card lists the master and the
versions.
"""

import hashlib
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import types

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
if _S3D.is_dir():
    sys.path.insert(0, str(_S3D))

pytest.importorskip("s3dgraphy.resources.versions")

from s3dgraphy import api  # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _pkg(name, rel):
    p = types.ModuleType(name)
    p.__path__ = [str(_REPO / rel)]
    sys.modules[name] = p


sys.path.insert(0, str(_REPO))
_pkg("_cr", "")
_pkg("_cr.sync_manager", "sync_manager")
ROOM = _load("_cr.sync_manager.room", "sync_manager/room.py")
AV = _load("_cr.sync_manager.asset_versions", "sync_manager/asset_versions.py")
# the transport is the room importer's (s3Dgraphy, since 15 Oct 2026):
# `file_states._send` reads `upload_asset` from it at every call
from s3dgraphy.room_import import node as UP  # noqa: E402
FS = _load("_cr.sync_manager.file_states", "sync_manager/file_states.py")
GOV = _load("resource_governance", "resource_governance.py")
WV = _load("_cr.sync_manager.web_version", "sync_manager/web_version.py")
FL = _load("_cr.sync_manager.files_list", "sync_manager/files_list.py")

BASE = "https://em.localhost:8443/em"
ROOM_ID = "tavolo-2026-10-12"
RM = "ME_EST_bk_LOD0_model"
BLEND = "ME_EST_bk_LOD0_model_res_blend"
LOCATOR = "blend://../RB/TempluMare_2021.blend#Object/ME_EST_bk_LOD0"
GLB_BYTES = b"glTF\x02\x00\x00\x00 ME_EST_bk_LOD0 lod0 web"
GLB = "sha256:" + hashlib.sha256(GLB_BYTES).hexdigest()


@pytest.fixture
def cache(monkeypatch, tmp_path):
    """The folder beside the .blend, where `em_cache/` is."""
    monkeypatch.setattr(AV, "cache_folder", lambda: str(tmp_path))
    return tmp_path


def _cache_dirs(root):
    """What `file_states.resolve_active` gives the resolver."""
    c = os.path.join(str(root), AV.CACHE_DIR)
    return [d for d in (c, os.path.join(c, "files")) if os.path.isdir(d)]


def _store(digest):
    return GOV.store_url(BASE, ROOM_ID, digest)


def _states(g, root):
    """The one resolver, with a node that has everything that was sent."""
    return {r["id"]: r["state"] for r in api.resolve_files(
        g, cache_dirs=_cache_dirs(root), on_node=lambda hexd: True)}


# ── 1 · what is sent stays here ─────────────────────────────────────────────

def test_keep_sent_writes_the_name_the_resolver_reads(cache):
    kept = AV.keep_sent(GLB, data=GLB_BYTES, ext=".glb")
    hexd = GLB[7:]
    assert kept == os.path.join(str(cache), "em_cache", "files", hexd[:2], hexd + ".glb")
    assert pathlib.Path(kept).read_bytes() == GLB_BYTES
    from s3dgraphy.resources.locate import in_cache
    assert in_cache(_cache_dirs(cache), hexd) == kept
    # twice is once, and nothing half-written is left beside it
    assert AV.keep_sent(GLB, data=GLB_BYTES, ext=".glb") == kept
    assert os.listdir(os.path.dirname(kept)) == [hexd + ".glb"]


def test_a_copy_that_fails_never_fails_the_upload(monkeypatch):
    def nowhere():
        raise RuntimeError("no .blend, no temp folder")
    monkeypatch.setattr(AV, "cache_folder", nowhere)
    assert AV.keep_sent(GLB, data=GLB_BYTES) == ""
    assert AV.keep_sent("", data=GLB_BYTES) == ""


def test_a_proxy_revision_sent_by_sync_is_here_and_on_the_node(cache, monkeypatch):
    """Sync and Replace send through `room.put_asset`: the bytes in memory are
    kept, and the revision the graph cites reads `both`."""
    monkeypatch.setitem(ROOM._session, "base_url", BASE)
    monkeypatch.setitem(ROOM._session, "room_id", ROOM_ID)
    monkeypatch.setitem(ROOM._session, "token", "t")
    monkeypatch.setattr(ROOM, "_room_has", lambda ref, timeout=30.0: False)

    class _Answer:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"ref": GLB, "created": True}).encode()
    monkeypatch.setattr(ROOM, "_urlopen", lambda req, timeout=None: _Answer())
    from s3dgraphy.graph import Graph
    g = Graph("g")
    api.add_resource(g, resource_id="US1_proxy", name="US 1 — proxy", kind="3d_model",
                     files=[{"url": "/tmp/US1.glb"}])
    before = _states(g, cache)
    info = ROOM.put_asset(GLB_BYTES, ROOM.GLTF_MEDIA_TYPE)
    spec = {"path": "US1.glb", "url": _store(info["ref"]), "checksum": info["ref"],
            "size_bytes": len(GLB_BYTES), "media_type": ROOM.GLTF_MEDIA_TYPE}
    out = GOV.revise_and_cite(g, "US1_proxy", spec)
    after = _states(g, cache)
    assert before["US1_proxy"] != "both"
    assert after[out["resource_id"]] == "both"


def test_a_room_that_had_the_bytes_still_leaves_them_here(cache, monkeypatch):
    monkeypatch.setitem(ROOM._session, "base_url", BASE)
    monkeypatch.setitem(ROOM._session, "room_id", ROOM_ID)
    monkeypatch.setitem(ROOM._session, "token", "t")
    monkeypatch.setattr(ROOM, "_room_has", lambda ref, timeout=30.0: True)
    assert ROOM.put_asset(GLB_BYTES)["already"] is True
    from s3dgraphy.resources.locate import in_cache
    assert in_cache(_cache_dirs(cache), GLB[7:])


def _graph():
    from s3dgraphy.graph import Graph
    g = Graph("tavolo")
    g.add_node(RepresentationModelNode(RM, name="Model for ME_EST_bk_LOD0", type="RM",
                                       description=""))
    api.add_resource(g, resource_id=BLEND, name="Blend datablock for ME_EST_bk_LOD0",
                     kind="3d_model", tier="master", packaging="datablock",
                     files=[{"url": LOCATOR}])
    g.add_edge(f"{RM}_has_linked_resource_{BLEND}", RM, BLEND, "has_linked_resource")
    return g


def _send_web(g, cache, monkeypatch, sent):
    """«Send a web version» with the transport of the operator (`_send`) and
    a node that takes everything."""
    glb = tempfile.mktemp(suffix="·lod0-web.glb")
    pathlib.Path(glb).write_bytes(GLB_BYTES)
    monkeypatch.setattr(FS, "_personal", lambda base: False)
    monkeypatch.setattr(UP, "upload_asset",
                        lambda node, room, path, sha, media, token: sent.append(path) or
                        {"sha256": GLB[7:], "already": False})

    def prepare(name):
        files = [{"path": os.path.basename(glb), "url": glb, "checksum": GLB,
                  "size_bytes": len(GLB_BYTES), "media_type": WV.GLB_MEDIA}]
        out = api.add_version(g, BLEND, use=["web"], files=files, residency="resident")
        return {**out, "files": files}
    where = {"base_url": BASE, "room_id": ROOM_ID}
    out = WV.send_web_version(g, BLEND, prepare=prepare, store_url=_store,
                              upload=lambda f: FS._send(where, f["url"], f.get("checksum"),
                                                        WV.GLB_MEDIA))
    os.remove(glb)                    # the export is gone: only the cache has it
    return out


def test_a_web_version_just_sent_is_here_and_on_the_node(cache, monkeypatch):
    g = _graph()
    sent = []
    out = _send_web(g, cache, monkeypatch, sent)
    assert out["ok"], out
    assert len(sent) == 1
    assert _states(g, cache)[out["version_id"]] == "both"


def test_upload_of_a_file_keeps_it_here(cache, monkeypatch):
    g = _graph()
    doc = tempfile.mktemp(suffix="D.32.jpg")
    pathlib.Path(doc).write_bytes(b"jpeg D.32")
    hexd = hashlib.sha256(b"jpeg D.32").hexdigest()
    api.add_resource(g, resource_id="D.32", name="D.32.jpg", kind="image",
                     files=[{"url": doc}])
    monkeypatch.setattr(FS, "_personal", lambda base: False)
    monkeypatch.setattr(UP, "upload_asset",
                        lambda *a: {"sha256": hexd, "already": False})
    where = {"base_url": BASE, "room_id": ROOM_ID}
    out = WV.upload_row(g, {"id": "D.32", "path": doc, "sha256": None},
                        upload=lambda r: FS._send(where, r["path"], r.get("sha256")),
                        store_url=_store)
    assert out["ok"] and out["recorded"]
    os.remove(doc)                    # moved away: the cache still has it
    assert _states(g, cache)["D.32"] == "both"


# ── 2 · one row per asset ───────────────────────────────────────────────────

def test_a_model_and_its_web_version_are_one_row(cache, monkeypatch):
    g = _graph()
    out = _send_web(g, cache, monkeypatch, [])
    results = api.resolve_files(g, cache_dirs=_cache_dirs(cache), on_node=lambda h: True)
    rows = [r for r in FL.build_rows(g, results) if r["asset_id"] == BLEND]
    assert len(rows) == 1, [r["file"] for r in rows]
    row = rows[0]
    assert row["id"] == BLEND                    # the model's gestures: Send a web version
    assert row["file"] == "ME_EST_bk_LOD0"
    assert row["versions"] == "v1/1 · web"
    assert row["use_id"] == out["version_id"] and row["state"] == "both"
    lines = [(m["text"], m["in_use"]) for m in row["members"]]
    assert lines == [("in the .blend", False), ("lod0 · web · resident", True)]
    # the head counts the rows it shows
    assert FL.row_counts(rows) == {"both": 1}


def test_a_proxy_revision_chain_keeps_its_own_row():
    g = _graph()
    api.add_resource(g, resource_id="US1_proxy", name="US 1 — proxy", kind="3d_model",
                     files=[{"url": "/tmp/US1.glb", "checksum": "sha256:" + "11" * 32}])
    GOV.revise_and_cite(g, "US1_proxy", {"path": "US1.glb", "url": _store("sha256:" + "22" * 32),
                                         "checksum": "sha256:" + "22" * 32})
    results = api.resolve_files(g, on_node=lambda h: True)
    rows = FL.build_rows(g, results)
    proxy = [r for r in rows if "US 1" in r["file"]]
    assert len(proxy) == 1 and proxy[0]["versions"] == "v2/2"
    assert not proxy[0].get("members")
