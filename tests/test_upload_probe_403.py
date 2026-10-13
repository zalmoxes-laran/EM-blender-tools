"""13 Oct 2026 · a 403 on the «do you have it?» HEAD does not stop an upload.

Measured: the RM ME_EST_bk_LOD0 (bytes sha256:7fb52213…) answered
«the room would not say whether it has … (403)» to editor2 — the node holds
those bytes at home in a room editor2 is not part of. Sending the bytes is
the proof of possession the node asks for, so the upload goes on.
"""
import importlib.util
import pathlib
import sys
import types

_REPO = pathlib.Path(__file__).resolve().parents[1]


def _load():
    pkg = types.ModuleType("_p403_pkg")
    pkg.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_p403_pkg"] = pkg
    for name in ("room", "asset_upload"):
        spec = importlib.util.spec_from_file_location(
            f"_p403_pkg.{name}", _REPO / "sync_manager" / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return sys.modules["_p403_pkg.asset_upload"]


up = _load()


def _probe(status):
    def has_asset(*a, **k):
        raise up.RoomError("the room would not say", status=status)
    return has_asset


def test_a_refused_probe_still_sends_the_bytes(tmp_path, monkeypatch):
    f = tmp_path / "rm.glb"
    f.write_bytes(b"glTF-bytes")
    sent = {}
    monkeypatch.setattr(up, "has_asset", _probe(403))
    import hashlib
    hexd = hashlib.sha256(b"glTF-bytes").hexdigest()
    monkeypatch.setattr(up, "_single_shot", lambda *a, **k: sent.setdefault(
        "info", {"ref": f"sha256:{hexd}", "sha256": hexd, "size": 10, "created": False}))
    out = up.upload_asset("https://node/em", "room", str(f), None, "model/gltf-binary", "tok")
    assert "info" in sent and not out.get("already")


def test_other_refusals_still_raise(tmp_path, monkeypatch):
    f = tmp_path / "rm.glb"
    f.write_bytes(b"glTF-bytes")
    monkeypatch.setattr(up, "has_asset", _probe(401))
    try:
        up.upload_asset("https://node/em", "room", str(f), None, "model/gltf-binary", "tok")
    except up.RoomError:
        return
    raise AssertionError("a 401 must not be read as «send it»")
