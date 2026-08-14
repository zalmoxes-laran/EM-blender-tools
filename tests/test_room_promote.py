"""The room client and the `promote_model` verb (DP-76), measured headless.

Two things are under test and they are different in kind:

* `sync_manager/room.py` — real HTTP against a real socket (a stdlib server
  standing in for em-server's asset endpoint, which is content-addressed the
  same way). What is measured is that bytes go out, come back byte-identical,
  and that a digest disagreement is REFUSED rather than recorded.
* `promote_model` — the graph side of the verb, with the two Blender-only steps
  (finding the object, exporting glTF) replaced by stubs. What is measured is
  what ends up in the graph: a ResourceNode that is a reference with a checksum,
  a dated D7 event, a delta, and idempotence.

The glTF export itself is Blender's own operator and is not exercised here: it
needs bpy. That limit is stated in the end-of report rather than papered over.
"""

import hashlib
import http.server
import importlib.util
import json
import pathlib
import sys
import threading

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent

# the s3Dgraphy CHECKOUT wins over any installed wheel — `promote_resource` is
# new, and a stale wheel in the dev venv would make this untestable
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))

s3dgraphy_api = pytest.importorskip(
    "s3dgraphy.api", reason="s3dgraphy not importable (checkout or wheel)")
if not hasattr(s3dgraphy_api, "promote_resource"):  # pragma: no cover
    pytest.skip("s3dgraphy without promote_resource (pre-DP-76)",
                allow_module_level=True)

from s3dgraphy.graph import Graph            # noqa: E402
from s3dgraphy.nodes import StratigraphicUnit  # noqa: E402


def _load(module_name: str, relative: str):
    """Load one addon module by path — the package `__init__` imports bpy."""
    spec = importlib.util.spec_from_file_location(module_name, _REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


room = _load("_emtools_test_room", "sync_manager/room.py")


# ── a stand-in room: content-addressed, like the real one ────────────────────

class _FakeRoomHandler(http.server.BaseHTTPRequestHandler):
    store: dict = {}
    lie_about_the_digest = False

    def log_message(self, *_args):        # silence: a test is not a web log
        pass

    def _unauthorised(self) -> bool:
        if not self.headers.get("Authorization", "").startswith("Bearer "):
            self.send_response(401)
            self.end_headers()
            return True
        return False

    def do_PUT(self):
        if self._unauthorised():
            return
        length = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(length)
        ref = "sha256:" + hashlib.sha256(data).hexdigest()
        created = ref not in type(self).store
        type(self).store[ref] = data
        if type(self).lie_about_the_digest:
            ref = "sha256:" + "f" * 64
        body = json.dumps({"ref": ref, "sha256": ref.split(":", 1)[1],
                           "media_type": "model/gltf-binary", "size": len(data),
                           "created": created,
                           "author": "0000-0002-1825-0097"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self._unauthorised():
            return
        ref = self.path.rsplit("/", 1)[-1]
        data = type(self).store.get(ref)
        if data is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "model/gltf-binary")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture()
def fake_room():
    _FakeRoomHandler.store = {}
    _FakeRoomHandler.lie_about_the_digest = False
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FakeRoomHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    room.set_room(f"http://{host}:{port}", "scavo-2026", token="a-session-token")
    try:
        yield _FakeRoomHandler
    finally:
        server.shutdown()
        server.server_close()
        room.set_room(None, None)
        room.forget_token()


# ── the client ───────────────────────────────────────────────────────────────

def test_bytes_go_out_and_come_back_byte_identical(fake_room):
    payload = b"glTF\x02\x00\x00\x00not-really-a-model"
    info = room.put_asset(payload)
    assert info["ref"] == room.content_id(payload)
    assert info["created"] is True
    fetched, media = room.get_asset(info["ref"])
    assert fetched == payload
    assert media == "model/gltf-binary"


def test_the_same_model_twice_is_one_object(fake_room):
    payload = b"the same bytes"
    first, second = room.put_asset(payload), room.put_asset(payload)
    assert first["ref"] == second["ref"]
    assert second["created"] is False
    assert len(fake_room.store) == 1


def test_a_digest_that_does_not_match_is_refused(fake_room):
    """Publishing a checksum we cannot stand behind is worse than failing."""
    fake_room.lie_about_the_digest = True
    with pytest.raises(room.RoomError) as exc:
        room.put_asset(b"whatever")
    assert "digest" in str(exc.value)


def test_without_a_token_nothing_is_uploaded(fake_room):
    room.forget_token()
    with pytest.raises(room.RoomError) as exc:
        room.put_asset(b"whatever")
    assert "token" in str(exc.value)
    assert fake_room.store == {}


def test_the_token_never_appears_in_what_can_be_printed(fake_room):
    """A credential in a status message is a credential in a screenshot."""
    described = room.room()
    assert described["has_token"] is True
    assert "a-session-token" not in json.dumps(described)


def test_the_socket_address_is_derived_from_the_same_base():
    room.set_room("https://em.example.org", "scavo-2026", token="t")
    assert room.ws_url() == "wss://em.example.org/v1/rooms/scavo-2026/ws"
    room.set_room("http://127.0.0.1:8000", "scavo-2026")
    assert room.ws_url() == "ws://127.0.0.1:8000/v1/rooms/scavo-2026/ws"
    room.set_room(None, None)
    room.forget_token()


def test_a_room_that_was_never_configured_says_so():
    room.set_room(None, None)
    with pytest.raises(room.RoomError):
        room.put_asset(b"x")


# ── the verb ─────────────────────────────────────────────────────────────────

class _FakeObject:
    """Just enough object for the graph side: a name and custom properties."""

    def __init__(self, name):
        self.name = name
        self._props = {}

    def __setitem__(self, key, value):
        self._props[key] = value

    def get(self, key, default=None):
        return self._props.get(key, default)


@pytest.fixture()
def commands(monkeypatch):
    """`sync_manager.commands`, with the two bpy-only steps stubbed.

    Loaded as a package member so its `from . import room` resolves — the module
    under test is the real one, only the scene access is replaced.
    """
    import types

    package = types.ModuleType("_emtools_pkg")
    package.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_emtools_pkg"] = package
    sys.modules["_emtools_pkg.room"] = room
    module = _load("_emtools_pkg.commands", "sync_manager/commands.py")
    monkeypatch.setattr(module, "_object_for_target",
                        lambda target, params, context, graph: _FakeObject("US101_proxy"))
    monkeypatch.setattr(module, "_export_gltf",
                        lambda obj, context: b"glTF\x02\x00\x00\x00US101")
    module.clear_history()
    return module


def _graph_with_unit():
    graph = Graph(graph_id="promote-test")
    graph.add_node(StratigraphicUnit("US101", name="US101"))
    return graph


def test_promoting_a_unit_publishes_the_bytes_and_references_them(commands, fake_room):
    graph = _graph_with_unit()
    result = commands.promote_model("US101", {}, None, graph)
    assert result["ok"], result.get("error")
    assert len(fake_room.store) == 1

    resource = graph.find_node_by_id("US101.model")
    assert resource.data["residency"] == "reference"
    assert resource.data["checksum"] == room.content_id(b"glTF\x02\x00\x00\x00US101")
    assert resource.data["url"].endswith(resource.data["checksum"])
    triples = {(e.edge_source, e.edge_type, e.edge_target) for e in graph.edges}
    assert ("US101", "has_linked_resource", "US101.model") in triples


def test_the_genesis_is_attributed_to_the_identity_the_room_reports(commands, fake_room):
    """Never to one the client declares — the relay's rule, kept here."""
    graph = _graph_with_unit()
    result = commands.promote_model("US101", {"author": "somebody-else"}, None, graph)
    process = graph.find_node_by_id(result["info"]["process_id"])
    assert process.node_type == "dtc_process"
    assert process.data["created_by"] == "0000-0002-1825-0097"
    assert process.data.get("created_at")


def test_the_delta_comes_back_and_carries_the_reference(commands, fake_room):
    graph = _graph_with_unit()
    delta = commands.promote_model("US101", {}, None, graph)["delta"]
    resource = next(n for n in delta["nodes"] if n["id"] == "US101.model")
    assert resource["data"]["residency"] == "reference"
    assert resource["data"]["media_type"] == "model/gltf-binary"
    assert any(e["edge_type"] == "has_linked_resource" for e in delta["edges"])


def test_the_same_command_twice_does_not_promote_twice(commands, fake_room):
    graph = _graph_with_unit()
    cmd_id = commands.make_cmd_id("promote_model", "US101", {})
    msg = {"cmd_id": cmd_id, "verb": "promote_model", "target": "US101",
           "params": {}}
    first = commands.execute(msg, None, graph)
    second = commands.execute(dict(msg), None, graph)
    assert first["ok"] and second["ok"]
    assert second.get("repeated") is True
    assert len(fake_room.store) == 1
    assert len([n for n in graph.nodes if n.node_type == "dtc_process"]) == 1


def test_re_exporting_the_same_mesh_is_the_same_asset(commands, fake_room, monkeypatch):
    """A NEW command id, the same bytes: content-addressing does the rest."""
    graph = _graph_with_unit()
    commands.execute({"cmd_id": "one", "verb": "promote_model", "target": "US101",
                      "params": {}}, None, graph)
    commands.execute({"cmd_id": "two", "verb": "promote_model", "target": "US101",
                      "params": {}}, None, graph)
    assert len(fake_room.store) == 1
    assert len([n for n in graph.nodes if n.node_type == "dtc_process"]) == 1


def test_when_the_upload_fails_the_graph_is_not_written(commands, fake_room):
    """A reference to an asset nobody can fetch is worse than no reference."""
    room.forget_token()
    graph = _graph_with_unit()
    result = commands.promote_model("US101", {}, None, graph)
    assert result["ok"] is False and "token" in result["error"]
    assert graph.find_node_by_id("US101.model") is None


def test_the_verb_is_declared_by_name(commands):
    assert "promote_model" in commands.VERBS
    refused = commands.execute({"cmd_id": "x", "verb": "publish_everything",
                                "target": "US101", "params": {}}, None,
                               _graph_with_unit())
    assert refused["ok"] is False and "promote_model" in refused["error"]
