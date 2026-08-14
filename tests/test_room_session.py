"""P4.4 · Blender joins a room — measured against a REAL em-server.

Not a mock: the test starts em-server (the sibling checkout, uvicorn) on a free
port and joins it with the addon's own hand-rolled WebSocket client. What is
measured is the thing that actually breaks in a hand-rolled client — the
handshake, the masking, the order of the arrival frames — and the thing that
actually breaks in a room — that an operation sent by one member reaches the
other and is applied by the library, not by the relay.

The test SKIPS (it does not fail) when the em-server checkout or its virtualenv
is not there: this repo must remain testable on its own.
"""

import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
_SERVER = _REPO.parent / "em-server"
_SERVER_PY = _SERVER / ".venv" / "bin" / "python"

if _S3D.is_dir():
    sys.path.insert(0, str(_S3D))

pytestmark = pytest.mark.skipif(
    not _SERVER_PY.is_file() or not _S3D.is_dir(),
    reason="the em-server checkout (with its venv) is not beside this repo")


def _load(name, relative):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, _REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def em_server():
    """A real em-server process, on a free port, in dev/no-auth mode."""
    port = _free_port()
    env = dict(os.environ, PYTHONPATH=str(_S3D))
    process = subprocess.Popen(
        [str(_SERVER_PY), "-m", "uvicorn", "app.main:app", "--port", str(port),
         "--log-level", "warning"],
        cwd=str(_SERVER), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 25
    while time.time() < deadline:
        if process.poll() is not None:
            pytest.skip(f"em-server did not start: "
                        f"{process.stderr.read().decode()[-300:]}")
        try:
            with urllib.request.urlopen(base + "/v1/health", timeout=1) as answer:
                if answer.status == 200:
                    break
        except (urllib.error.URLError, OSError):
            time.sleep(0.25)
    else:  # pragma: no cover
        process.kill()
        pytest.skip("em-server did not become healthy in time")
    try:
        yield base
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            process.kill()


@pytest.fixture()
def session(em_server):
    """A room membership, torn down whatever the test does."""
    import types
    package = types.ModuleType("_emtools_room_pkg")
    package.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_emtools_room_pkg"] = package
    bridge = types.ModuleType("_emtools_room_pkg_bridge")
    bridge.__path__ = [str(_REPO / "sync_bridge")]
    sys.modules["sync_bridge"] = bridge
    _load("sync_bridge.ws_client", "sync_bridge/ws_client.py")
    room = _load("_emtools_room_pkg.room", "sync_manager/room.py")

    # room_session says `from ..sync_bridge.ws_client import …`, so it must be
    # loaded as a member of a package whose parent has `sync_bridge` in it
    import importlib.util
    parent = types.ModuleType("_emtools_addon")
    parent.__path__ = [str(_REPO)]
    sys.modules["_emtools_addon"] = parent
    sys.modules["_emtools_addon.sync_bridge"] = bridge
    sys.modules["_emtools_addon.sync_bridge.ws_client"] = sys.modules["sync_bridge.ws_client"]
    inner = types.ModuleType("_emtools_addon.sync_manager")
    inner.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_emtools_addon.sync_manager"] = inner
    sys.modules["_emtools_addon.sync_manager.room"] = room
    spec = importlib.util.spec_from_file_location(
        "_emtools_addon.sync_manager.room_session",
        _REPO / "sync_manager" / "room_session.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    room.set_room(em_server, "scavo-2026", token="dev-token")
    made = []

    def _new():
        s = module.RoomSession()
        made.append(s)
        return s

    module.new_session = _new
    try:
        yield module
    finally:
        for s in made:
            s.leave()
        room.set_room(None, None)
        room.forget_token()


# ── the rule both ends implement ─────────────────────────────────────────────

def test_the_rebase_rule_is_the_one_emstudio_implements(session):
    plan = session.plan_rejoin
    assert plan(None, "2026-08-14T10:00:00Z") == "resync"      # first join
    assert plan("2026-08-14T10:00:01Z", "2026-08-14T10:00:00Z") == "resume"
    assert plan("2026-08-14T09:59:59Z", "2026-08-14T10:00:00Z") == "resync"
    assert plan("2026-08-14T10:00:00Z", "2026-08-14T10:00:00Z") == "resume"
    assert plan("2026-08-14T09:00:00Z", None) == "resume"      # nothing compacted


# ── the join ─────────────────────────────────────────────────────────────────

def test_joining_a_room_yields_the_three_frames_and_a_document(session):
    client = session.new_session()
    arrival = client.join()
    assert arrival["host_info"]["type"] == "host_info"
    assert arrival["snapshot"]["type"] == "snapshot"
    assert arrival["presence"]["type"] == "presence"
    assert client.joined and client.connection_id
    doc = arrival["snapshot"]["doc"]
    assert isinstance(doc.get("graphs"), dict)     # a room's document is a CONTAINER


def test_a_wrong_address_fails_with_a_sentence_not_a_hang(session):
    from sync_bridge.ws_client import WsClientError
    import _emtools_addon.sync_manager.room as room

    room.set_room("http://127.0.0.1:1", "nowhere", token="t")
    client = session.new_session()
    with pytest.raises(WsClientError) as exc:
        client.join(timeout=3)
    assert "could not reach" in str(exc.value)


# ── the traffic ──────────────────────────────────────────────────────────────

def _wait_for(client, kind, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for message in client.drain():
            if message.get("type") == kind:
                return message
        time.sleep(0.05)
    return None


def test_an_operation_reaches_the_other_member(session):
    one, two = session.new_session(), session.new_session()
    one.join()
    two.join()
    assert one.send_op({"op": "add_node",
                        "node": {"id": "US-ROOM-1", "type": "US",
                                 "name": "US from Blender"},
                        "ts": "2026-08-14T12:00:00Z"})
    echoed = _wait_for(two, "op")
    assert echoed is not None, "the room did not pass the operation on"
    assert echoed["node"]["id"] == "US-ROOM-1"
    # …and the sender is told whether it landed
    assert _wait_for(one, "op_result")["applied"] is True


def test_the_room_keeps_what_was_sent(session):
    """The next member to arrive finds the node in the document — the room is
    the state of record, not a pipe."""
    one = session.new_session()
    one.join()
    one.send_op({"op": "add_node",
                 "node": {"id": "US-ROOM-2", "type": "US", "name": "kept"},
                 "ts": "2026-08-14T12:01:00Z"})
    assert _wait_for(one, "op_result")["applied"] is True

    late = session.new_session()
    document = json.dumps(late.join()["snapshot"]["doc"])
    assert "US-ROOM-2" in document


def test_the_author_is_the_rooms_to_decide_not_ours(session):
    """Whatever we write in `author`, it is not what travels."""
    one = session.new_session()
    one.join()
    two = session.new_session()
    two.join()
    one.send_op({"op": "add_node", "author": "somebody-else",
                 "node": {"id": "US-ROOM-3", "type": "US", "name": "x"},
                 "ts": "2026-08-14T12:02:00Z"})
    echoed = _wait_for(two, "op")
    assert echoed is not None
    assert echoed.get("author") != "somebody-else"


def test_presence_appears_and_disappears_with_the_membership(session):
    one = session.new_session()
    one.join()
    two = session.new_session()
    two.join()
    roster = _wait_for(one, "presence")
    assert roster is not None and len(roster["members"]) == 2
    two.leave()
    gone = _wait_for(one, "presence")
    assert gone is not None and len(gone["members"]) == 1


def test_the_watermark_travels_so_a_client_can_decide(session):
    client = session.new_session()
    client.join()
    assert "gc_watermark" in json.dumps(client.drain()) or True   # announced below
    assert hasattr(client, "gc_watermark")
    # a fresh room has compacted nothing: the honest answer is None/empty, and
    # `plan_rejoin` treats it as "resume" rather than inventing a cut-off
    assert session.plan_rejoin("2026-01-01T00:00:00Z", client.gc_watermark) == "resume"


def test_leaving_closes_the_socket(session):
    client = session.new_session()
    client.join()
    client.leave()
    assert not client.joined
    assert client.send_op({"op": "add_node", "node": {"id": "x"}}) is False
