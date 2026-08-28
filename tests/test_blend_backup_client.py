"""The `.blend` safety archive, from Blender's side — measured headless.

What is under test is the CLIENT (`sync_manager/room.py`): real HTTP against a
real socket, with a stand-in room that is content-addressed the way StratiGraph Server's
backup namespace is. Three properties, and each one is a way this could quietly
fail:

* **dedup is visible.** Archiving an unchanged `.blend` must come back
  `created: false` rather than looking like a fresh snapshot — otherwise the
  panel tells somebody they have five backups of one file;
* **a digest that does not match is REFUSED.** On the way out and on the way
  back. A backup you cannot verify is a copy you hope exists, and restoring
  unverified bytes over anything is the actual damage;
* **restore never lands on the working file.** The path is computed, and it is
  computed to be a different name.

The Blender halves — the operators, the panel, `bpy.data.is_dirty` — are not
exercised here: they need bpy. `_restore_path` is, with a fake `bpy` module,
because that one is arithmetic on a path and it is the one that could destroy
work.
"""

import hashlib
import http.server
import importlib.util
import json
import pathlib
import sys
import threading
import types
import urllib.parse

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _load(module_name: str, relative: str):
    """Load one addon module by path — the package `__init__` imports bpy."""
    spec = importlib.util.spec_from_file_location(module_name, _REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


room = _load("_emtools_backup_room", "sync_manager/room.py")

BLEND = b"BLENDER-v405RENDH" + b"\x00opaque, nobody parses this\x00" * 50
CHANGED = BLEND + b"one more object"


# ── a stand-in room: the backup namespace, per author ────────────────────────

class _FakeBackupRoom(http.server.BaseHTTPRequestHandler):
    blobs: dict = {}
    records: list = []
    lie_about_the_digest = False

    def log_message(self, *_args):
        pass

    def _unauthorised(self) -> bool:
        if not self.headers.get("Authorization", "").startswith("Bearer "):
            self.send_response(401)
            self.end_headers()
            return True
        return False

    def _json(self, payload, status: int = 200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):
        if self._unauthorised():
            return
        length = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(length)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        sha = hashlib.sha256(data).hexdigest()
        created = sha not in type(self).blobs
        type(self).blobs[sha] = data
        if created:
            type(self).records.append(
                {"sha256": sha, "size": len(data),
                 "label": (query.get("label") or [""])[0],
                 "filename": (query.get("filename") or [""])[0],
                 "orcid": "0000-0002-1825-0097",
                 "created_at": "2026-08-24T02:00:00Z", "seen": 1,
                 "dtc": {"kind": "backup", "publishable": False}})
        record = next(r for r in type(self).records if r["sha256"] == sha)
        answer = dict(record, created=created)
        if type(self).lie_about_the_digest:
            answer["sha256"] = "f" * 64
        self._json(answer)

    def do_GET(self):
        if self._unauthorised():
            return
        path = urllib.parse.urlsplit(self.path).path
        if path.endswith("/blend-backups"):
            return self._json([dict(r, created=False)
                               for r in reversed(type(self).records)])
        sha = path.rsplit("/", 1)[-1]
        data = type(self).blobs.get(sha)
        if data is None:
            self.send_response(404)
            self.end_headers()
            return
        if type(self).lie_about_the_digest:
            data = data + b"tampered"
        self.send_response(200)
        self.send_header("Content-Type", "application/x-blender")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture()
def fake_room():
    _FakeBackupRoom.blobs = {}
    _FakeBackupRoom.records = []
    _FakeBackupRoom.lie_about_the_digest = False
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FakeBackupRoom)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    room.set_room(f"http://{host}:{port}", "scavo-2026", token="a-session-token")
    try:
        yield _FakeBackupRoom
    finally:
        server.shutdown()
        server.server_close()
        room.set_room(None, None)
        room.forget_token()


# ── the client ───────────────────────────────────────────────────────────────

def test_a_snapshot_goes_out_and_the_record_comes_back(fake_room):
    record = room.put_blend_backup(BLEND, label="prima del taglio",
                                   filename="scavo.blend")
    assert record["sha256"] == hashlib.sha256(BLEND).hexdigest()
    assert record["created"] is True
    assert record["label"] == "prima del taglio"
    assert record["size"] == len(BLEND)
    assert record["dtc"]["kind"] == "backup"
    assert record["dtc"]["publishable"] is False


def test_the_same_bytes_are_not_a_second_snapshot(fake_room):
    room.put_blend_backup(BLEND, label="one")
    again = room.put_blend_backup(BLEND, label="one again")
    assert again["created"] is False, "dedup was not reported"
    assert len(fake_room.blobs) == 1
    assert len(room.list_blend_backups()) == 1


def test_a_changed_blend_is_a_new_snapshot(fake_room):
    room.put_blend_backup(BLEND, label="before")
    room.put_blend_backup(CHANGED, label="after")
    assert len(fake_room.blobs) == 2
    listing = room.list_blend_backups()
    assert len(listing) == 2
    assert {r["sha256"] for r in listing} == {
        hashlib.sha256(BLEND).hexdigest(), hashlib.sha256(CHANGED).hexdigest()}


def test_the_exact_bytes_come_back(fake_room):
    sha = room.put_blend_backup(BLEND, label="x")["sha256"]
    restored = room.get_blend_backup(sha)
    assert restored == BLEND
    assert hashlib.sha256(restored).hexdigest() == sha


def test_a_room_that_stores_a_different_digest_is_refused(fake_room):
    """On the way out: a snapshot whose name we cannot stand behind is not a
    snapshot, and recording it would be worse than failing."""
    fake_room.lie_about_the_digest = True
    with pytest.raises(room.RoomError) as caught:
        room.put_blend_backup(BLEND, label="x")
    assert "different digest" in str(caught.value)


def test_bytes_that_do_not_verify_are_not_handed_back(fake_room):
    """And on the way back. This is the one that protects the file on disk."""
    sha = room.put_blend_backup(BLEND, label="x")["sha256"]
    fake_room.lie_about_the_digest = True
    with pytest.raises(room.RoomError) as caught:
        room.get_blend_backup(sha)
    assert "does not verify" in str(caught.value)


def test_a_missing_snapshot_says_so_with_its_status(fake_room):
    with pytest.raises(room.RoomError) as caught:
        room.get_blend_backup("a" * 64)
    assert caught.value.status == 404


def test_no_room_is_a_sentence_not_a_traceback():
    room.set_room(None, None)
    with pytest.raises(room.RoomError) as caught:
        room.put_blend_backup(BLEND)
    assert "no room" in str(caught.value)


# ── the one Blender-side computation that could destroy work ────────────────

def test_a_restore_never_lands_on_the_file_in_use(monkeypatch, tmp_path):
    """`_restore_path` is arithmetic on a path, and getting it wrong would
    overwrite the working file at the exact moment somebody is panicking."""
    current = tmp_path / "scavo.blend"
    current.write_bytes(BLEND)
    fake_bpy = types.ModuleType("bpy")
    fake_bpy.data = types.SimpleNamespace(filepath=str(current), is_dirty=False)
    fake_bpy.app = types.SimpleNamespace(tempdir=str(tmp_path))
    fake_bpy.props = types.SimpleNamespace(
        StringProperty=lambda **k: None, BoolProperty=lambda **k: None)
    fake_bpy.types = types.SimpleNamespace(Operator=object)
    fake_bpy.utils = types.SimpleNamespace(
        register_class=lambda c: None, unregister_class=lambda c: None)
    monkeypatch.setitem(sys.modules, "bpy", fake_bpy)
    backups = _load("_emtools_backups", "sync_manager/backups.py")

    sha = hashlib.sha256(BLEND).hexdigest()
    target = pathlib.Path(backups._restore_path(sha))
    assert target != current, "a restore would have overwritten the working file"
    assert target.parent == current.parent, "…and it lands beside it"
    assert sha[:12] in target.name and target.suffix == ".blend"
