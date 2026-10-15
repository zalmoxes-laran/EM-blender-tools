"""13 Oct 2026 · a 403 on the «do you have it?» HEAD does not stop an upload.

Measured: the RM ME_EST_bk_LOD0 (bytes sha256:7fb52213…) answered
«the room would not say whether it has … (403)» to editor2 — the node holds
those bytes at home in a room editor2 is not part of. Sending the bytes is
the proof of possession the node asks for, so the upload goes on.
"""
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[1]
_S3D = _REPO.parent / "s3Dgraphy" / "src"
if _S3D.is_dir() and str(_S3D) not in sys.path:
    sys.path.insert(0, str(_S3D))

# EM Tools' uploads (Files, «Bring into a room») go through the room importer's
# doors since 15 Oct 2026: the rule is measured there, where it lives
from s3dgraphy.room_import import node as up  # noqa: E402


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
