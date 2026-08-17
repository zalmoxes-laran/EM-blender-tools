"""DP-76's consuming half: the room's geometry arriving in the scene.

The twin of `test_room_promote.py`, from the other direction. Two things are
under test and they are different in kind:

* **the room client's refusals** — real HTTP against a real socket: a 403 must
  arrive as a 403 (the embargo gate) and not as "the room has no asset", because
  a consumer that could only read the sentence would have to match on English;
* **the consumption logic** — with the two Blender-only steps (the mesh importer,
  the object properties) replaced by stubs. What is measured is what a batch
  DOES: which rows are fetched, which are reused, which are skipped and why, and
  that a scene is never left half-built by one refusal.

The glTF import itself is Blender's own operator and is not exercised here; that
limit is stated in the end-of report rather than papered over.
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

_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))

s3dgraphy_api = pytest.importorskip(
    "s3dgraphy.api", reason="s3dgraphy not importable (checkout or wheel)")
if not hasattr(s3dgraphy_api, "store_backed_geometry"):  # pragma: no cover
    pytest.skip("s3dgraphy without store_backed_geometry (pre-DP-76 consuming half)",
                allow_module_level=True)

from s3dgraphy.graph import Graph                                   # noqa: E402
from s3dgraphy.nodes.epoch_node import EpochNode                    # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402
from s3dgraphy.nodes.resource_node import ResourceNode              # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit    # noqa: E402


def _load(module_name: str, relative: str):
    """Load one addon module by path — the package `__init__` imports bpy."""
    spec = importlib.util.spec_from_file_location(module_name, _REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


room = _load("_emtools_mat_room", "sync_manager/room.py")
materialise = _load("_emtools_mat", "sync_manager/materialise.py")


# ── a stand-in room, with a gate ─────────────────────────────────────────────

class _GatedRoomHandler(http.server.BaseHTTPRequestHandler):
    """Content-addressed like the real one, and it can refuse like it too:
    `embargoed` holds the digests this token may not have (em-server answers 403
    for an embargoed asset to anybody below editor)."""

    store: dict = {}
    embargoed: set = set()

    def log_message(self, *_args):
        pass

    def do_GET(self):
        if not self.headers.get("Authorization", "").startswith("Bearer "):
            self.send_response(401)
            self.end_headers()
            return
        ref = self.path.rsplit("/", 1)[-1].replace("%3A", ":")
        if ref in type(self).embargoed:
            self.send_response(403)
            self.end_headers()
            return
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
    _GatedRoomHandler.store = {}
    _GatedRoomHandler.embargoed = set()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _GatedRoomHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    room.set_room(f"http://{host}:{port}", "scavo-2026", token="a-session-token")
    try:
        yield _GatedRoomHandler
    finally:
        server.shutdown()
        server.server_close()
        room.set_room(None, None)
        room.forget_token()


def publish(handler, payload: bytes) -> str:
    ref = "sha256:" + hashlib.sha256(payload).hexdigest()
    handler.store[ref] = payload
    return ref


# ── the scene, in miniature ──────────────────────────────────────────────────

class _EpochSlot:
    def __init__(self):
        self.epoch = ""


class _EpochCollection:
    """Stands in for `Object.EM_ep_belong_ob` — the epoch-manager convention the
    rest of the addon reads. Modelled rather than skipped: a stub that lacked it
    would make every binding test pass by not testing it."""

    def __init__(self):
        self._items = []

    def clear(self):
        self._items.clear()

    def add(self):
        slot = _EpochSlot()
        self._items.append(slot)
        return slot

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


class _FakeObject:
    """A name, custom properties, and the epoch collection — everything this
    module touches."""

    def __init__(self, name, *, epochs_supported: bool = True):
        self.name = name
        self._props = {}
        if epochs_supported:
            self.EM_ep_belong_ob = _EpochCollection()

    def __setitem__(self, key, value):
        self._props[key] = value

    def get(self, key, default=None):
        return self._props.get(key, default)


def graph_with(rm_digest: str, *, local: bool = True) -> Graph:
    g = Graph(graph_id="g")
    g.add_node(EpochNode("ep1", name="Fase I", start_time=-100, end_time=0))
    g.add_node(StratigraphicUnit("US1", name="US1"))
    g.add_node(ResourceNode("res_glb", name="basilica.glb", checksum=rm_digest,
                            residency="resident", url_type="3d_model"))
    g.add_node(RepresentationModelNode("rm1", name="Model for Fase I", type="RM"))
    g.add_edge("e1", "rm1", "res_glb", "has_linked_resource")
    g.add_edge("e2", "rm1", "ep1", "has_first_epoch")
    if local:
        # geometry the study knows about that is NOT in the store
        g.add_node(ResourceNode("res_local", name="proxy_US1.glb",
                                url="/Users/somebody/US1.glb",
                                checksum="sha256:" + "cd" * 32,
                                residency="reference", url_type="3d_model"))
        g.add_edge("e3", "US1", "res_local", "has_linked_resource")
    return g


# NOTE · every call below passes `fetch=room.get_asset` explicitly. The addon
# modules are loaded by PATH here (the package `__init__` imports bpy), so the
# module's own `from . import room` cannot resolve — handing it the client the
# test already built is both the fix and the more honest test: the real HTTP
# path is exercised, against the real socket.
def importer_making(names):
    """A stub importer: it stands where `bpy.ops.import_scene.gltf` stands, and
    records the bytes it was handed so the test can prove they arrived."""
    seen = []

    def _import(path):
        with open(path, "rb") as handle:
            seen.append(handle.read())
        return [_FakeObject(n) for n in names]

    _import.seen = seen
    return _import


# ── the client's refusals ────────────────────────────────────────────────────

def test_an_embargoed_asset_arrives_as_a_403_not_as_a_missing_file(fake_room):
    ref = publish(fake_room, b"glTF\x02embargoed")
    fake_room.embargoed = {ref}
    with pytest.raises(room.RoomError) as exc:
        room.get_asset(ref)
    assert exc.value.status == 403, "the consumer must be able to tell WHICH refusal"
    assert "embargo" in str(exc.value).lower()


def test_a_missing_asset_is_still_a_404_with_its_own_words(fake_room):
    with pytest.raises(room.RoomError) as exc:
        room.get_asset("sha256:" + "ff" * 32)
    assert exc.value.status == 404
    assert "no asset" in str(exc.value)


# ── the batch ────────────────────────────────────────────────────────────────

def test_the_resident_model_arrives_and_carries_its_epoch(fake_room):
    payload = b"glTF\x02\x00\x00\x00a-model"
    ref = publish(fake_room, payload)
    graph = graph_with(ref)
    stub = importer_making(["basilica"])

    report = materialise.materialise(graph, fetch=room.get_asset, importer=stub, objects=[])

    assert report["considered"] == 1, "only the resident one is even considered"
    assert report["elsewhere"] == 1, "…and the local one is COUNTED, not hidden"
    assert len(report["materialised"]) == 1
    row = report["materialised"][0]
    assert row["checksum"] == ref
    assert row["node_id"] == "rm1"
    assert row["objects"] == ["basilica"]
    assert row["epochs"] == ["Fase I"], "bound the way the graph says"
    # the bytes that reached the importer are the bytes the room holds
    assert stub.seen == [payload]


def test_a_build_without_the_epoch_property_says_so_instead_of_claiming(fake_room):
    """The report says what was WRITTEN. Measured in a background Blender with
    the addon unregistered: `EM_ep_belong_ob` is absent there, and naming the
    epochs anyway would make somebody trust a binding that is not on the object."""
    ref = publish(fake_room, b"glTF\x02no-props")
    graph = graph_with(ref, local=False)
    bare = _FakeObject("basilica", epochs_supported=False)
    report = materialise.materialise(graph, fetch=room.get_asset,
                                     importer=lambda _p: [bare], objects=[])
    row = report["materialised"][0]
    assert row["epochs"] == []
    assert row["epochs_not_written"] == ["Fase I"], "and the intention is not lost"


def test_the_object_carries_the_digest_so_the_scene_is_the_cache(fake_room):
    ref = publish(fake_room, b"glTF\x02cache-me")
    graph = graph_with(ref, local=False)
    made = _FakeObject("basilica")
    materialise.materialise(graph, fetch=room.get_asset, importer=lambda _p: [made], objects=[])
    assert made.get(materialise.PROP_DIGEST) == ref
    assert made.get(materialise.PROP_RESOURCE) == "res_glb"
    assert made.get(materialise.PROP_CARRIER) == "rm1"


def test_running_it_twice_downloads_nothing_and_duplicates_nothing(fake_room):
    ref = publish(fake_room, b"glTF\x02twice")
    graph = graph_with(ref, local=False)
    stub = importer_making(["basilica"])
    first = materialise.materialise(graph, fetch=room.get_asset, importer=stub, objects=[])
    already = [_FakeObject("basilica")]
    already[0][materialise.PROP_DIGEST] = ref

    second = materialise.materialise(graph, fetch=room.get_asset, importer=stub, objects=already)

    assert len(first["materialised"]) == 1
    assert second["materialised"] == [], "nothing new"
    assert len(second["reused"]) == 1
    assert second["reused"][0]["object"] == "basilica"
    assert len(stub.seen) == 1, "the second run did not even fetch"


def test_an_embargoed_model_is_skipped_with_a_reason_and_the_rest_arrives(fake_room):
    open_ref = publish(fake_room, b"glTF\x02open")
    closed_ref = publish(fake_room, b"glTF\x02closed")
    fake_room.embargoed = {closed_ref}
    graph = graph_with(open_ref, local=False)
    # a second RM, on another epoch, whose bytes are embargoed
    graph.add_node(EpochNode("ep2", name="Fase II", start_time=0, end_time=100))
    graph.add_node(ResourceNode("res_closed", name="closed.glb", checksum=closed_ref,
                                residency="resident", url_type="3d_model"))
    graph.add_node(RepresentationModelNode("rm2", name="Model for Fase II", type="RM"))
    graph.add_edge("e4", "rm2", "res_closed", "has_linked_resource")
    graph.add_edge("e5", "rm2", "ep2", "has_first_epoch")

    report = materialise.materialise(graph, fetch=room.get_asset, importer=importer_making(["obj"]),
                                     objects=[])

    assert len(report["materialised"]) == 1, "the batch did not stop at the refusal"
    assert report["materialised"][0]["checksum"] == open_ref
    assert len(report["skipped"]) == 1
    skipped = report["skipped"][0]
    assert skipped["checksum"] == closed_ref
    assert "embargo" in skipped["reason"].lower()
    assert report["failed"] == [], "a gate doing its job is not a failure"


def test_no_token_is_reported_per_row_and_never_crashes_the_batch(fake_room):
    """A missing credential is not the gate refusing — it is this side not being
    ready. It lands in `failed` with the client's own sentence (which says how to
    fix it), and the operator still returns a report instead of raising."""
    ref = publish(fake_room, b"glTF\x02no-token")
    room.forget_token()
    graph = graph_with(ref, local=False)
    report = materialise.materialise(graph, fetch=room.get_asset, importer=importer_making(["x"]),
                                     objects=[])
    assert report["materialised"] == []
    assert len(report["failed"]) == 1
    assert "token" in report["failed"][0]["reason"]


def test_bytes_blender_cannot_import_are_said_not_silently_dropped(fake_room):
    ref = publish(fake_room, b"not a mesh at all")
    graph = graph_with(ref, local=False)
    report = materialise.materialise(graph, fetch=room.get_asset, importer=lambda _p: [], objects=[])
    assert report["materialised"] == []
    assert len(report["skipped"]) == 1
    assert "importer" in report["skipped"][0]["reason"]


def test_a_reference_resource_is_never_fetched(fake_room):
    """The line the whole module rests on: bytes outside the store stay there."""
    ref = publish(fake_room, b"glTF\x02resident")
    graph = graph_with(ref)          # includes the local/reference one
    stub = importer_making(["basilica"])
    report = materialise.materialise(graph, fetch=room.get_asset, importer=stub, objects=[])
    assert [r["checksum"] for r in report["materialised"]] == [ref]
    assert len(stub.seen) == 1, "the reference one was not even asked for"


def test_the_plan_is_readable_before_anything_is_pressed(fake_room):
    ref = publish(fake_room, b"glTF\x02plan")
    graph = graph_with(ref)
    plan = materialise.plan(graph)
    assert plan["counts"] == {"resident": 1, "elsewhere": 1}
    assert plan["resident"][0]["node_id"] == "rm1"


def test_the_line_for_the_status_bar_hides_nothing(fake_room):
    report = {"materialised": [1], "reused": [1, 1], "skipped": [1],
              "failed": [], "elsewhere": 2}
    line = materialise.summarise(report)
    assert "1 materialised" in line
    assert "2 already here" in line
    assert "1 skipped" in line, "a skip is the thing the user must see"
    assert "2 outside the store" in line


def test_the_suffix_comes_from_the_media_type_then_the_url(fake_room):
    """The bytes arrive with no name — the suffix is what tells Blender which
    importer to use, so it is derived, not guessed."""
    assert materialise._suffix_for({"media_type": "model/gltf-binary"}) == ".glb"
    assert materialise._suffix_for({"media_type": "", "url": "a/b/mesh.ply"}) == ".ply"
    assert materialise._suffix_for({"media_type": "", "url": "", "name": ""}) == ".glb"
