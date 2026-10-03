"""R1 · the room list of a node — the id rule, the grouping, and a real node.

* **the id rule** is asserted against the SAME vector the node's
  `tests/test_room_id_parity.py` pins (read from that file, not copied: a copy
  is a fourth derivation nobody remembers to update). Skipped only when the
  sibling checkout is absent; a local copy of three cases keeps this file from
  testing nothing then.
* **the grouping**: owner → «Your rooms», every other role → «Shared with you»
  with its role; archived rooms out unless asked; the filter on id or title.
* **a real node** (StratiGraph Server from the sibling checkout, dev mode, free
  port): `list_rooms` reads `GET /v1/rooms`, `create_room` posts the derived id
  and the room appears in the list as yours.
"""

import ast
import importlib.util
import os
import pathlib
import socket
import subprocess
import sys
import time
import types
import urllib.error
import urllib.request

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_SERVER = _REPO.parent / "stratigraph-server"
_SERVER_PY = _SERVER / ".venv" / "bin" / "python"
_S3D = _REPO.parent / "s3Dgraphy" / "src"
_PARITY_FILE = _SERVER / "tests" / "test_room_id_parity.py"


def _load():
    """`sync_manager.rooms_list` without the addon package (its `__init__`
    imports bpy): a throwaway parent package holding `room` and `rooms_list`."""
    pkg = types.ModuleType("_r1_pkg")
    pkg.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_r1_pkg"] = pkg
    for name in ("room", "rooms_list"):
        spec = importlib.util.spec_from_file_location(
            f"_r1_pkg.{name}", _REPO / "sync_manager" / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return sys.modules["_r1_pkg.rooms_list"]


rl = _load()


def _parity_vector():
    """The server's PARITY list, evaluated from its own source."""
    tree = ast.parse(_PARITY_FILE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target.id
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
        if target == "PARITY":
            expr = ast.Expression(node.value)
            return eval(compile(expr, str(_PARITY_FILE), "eval"),  # noqa: S307
                        {"__builtins__": {}})
    raise AssertionError("PARITY not found in the server's parity test")


@pytest.mark.skipif(not _PARITY_FILE.is_file(),
                    reason="stratigraph-server checkout not beside this repo")
def test_the_room_id_is_the_one_the_other_two_doors_derive():
    vector = _parity_vector()
    assert len(vector) >= 8
    for name, expected in vector:
        assert rl.room_id_from_name(name) == expected, name


def test_the_room_id_rule_even_without_the_sibling_checkout():
    assert rl.room_id_from_name("  Templu Mare  ") == "templu-mare"
    assert rl.room_id_from_name("US 101 / US 102") == "us-101-us-102"
    assert rl.room_id_from_name("???") == ""
    assert rl.room_id_from_name("x" * 59 + " coda") == "x" * 59 + "-"


_ROOMS = [
    {"room_id": "scavo-2026", "title": "Scavo 2026", "your_role": "owner"},
    {"room_id": "cantiere-demo", "title": "Cantiere demo", "your_role": "viewer"},
    {"room_id": "aiano", "title": "Villa di Aiano", "your_role": "editor"},
    {"room_id": "old", "title": "Old", "your_role": "owner",
     "archived_at": "2026-09-01T00:00:00Z"},
]


def test_owner_is_yours_every_other_role_is_shared():
    groups = rl.group_rooms(_ROOMS)
    assert [r["room_id"] for r in groups["mine"]] == ["scavo-2026"]
    assert [(r["room_id"], r["your_role"]) for r in groups["shared"]] == [
        ("cantiere-demo", "viewer"), ("aiano", "editor")]
    assert rl.summary(groups) == "1 yours · 2 shared with you"


def test_archived_rooms_only_when_asked():
    assert "old" not in [r["room_id"] for r in rl.group_rooms(_ROOMS)["mine"]]
    assert "old" in [r["room_id"] for r in
                     rl.group_rooms(_ROOMS, include_archived=True)["mine"]]


def test_the_filter_reads_id_and_title():
    groups = rl.group_rooms(_ROOMS, filter_text="aiano villa")
    assert groups["mine"] == [] and [r["room_id"] for r in groups["shared"]] == ["aiano"]
    assert rl.group_rooms(_ROOMS, filter_text="SCAVO")["mine"][0]["room_id"] == "scavo-2026"


def test_a_name_with_nothing_usable_is_refused_before_the_network():
    with pytest.raises(rl.RoomError):
        rl.create_room("http://127.0.0.1:9", None, "???")


def test_an_unreachable_node_is_a_sentence():
    with pytest.raises(rl.RoomError) as caught:
        rl.list_rooms("http://127.0.0.1:9", None, timeout=1)
    assert "could not reach the node" in str(caught.value)


# ── a real node ──────────────────────────────────────────────────────────────

def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def node(tmp_path_factory):
    if not _SERVER_PY.is_file() or not _S3D.is_dir():
        pytest.skip("the StratiGraph Server checkout (with its venv) is not beside this repo")
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
            pytest.skip(f"StratiGraph Server did not start: "
                        f"{process.stderr.read().decode()[-300:]}")
        try:
            with urllib.request.urlopen(base + "/v1/health", timeout=1) as answer:
                if answer.status == 200:
                    break
        except (urllib.error.URLError, OSError):
            time.sleep(0.25)
    else:  # pragma: no cover
        process.kill()
        pytest.skip("StratiGraph Server did not become healthy in time")
    try:
        yield base
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            process.kill()


def test_a_room_created_by_name_is_listed_as_yours(node):
    name = f"R1 prova {int(time.time() * 1000)}"
    created = rl.create_room(node, None, name)
    assert created["room_id"] == rl.room_id_from_name(name)
    listed = rl.list_rooms(node, None)
    groups = rl.group_rooms(listed)
    ids = [r["room_id"] for r in groups["mine"] + groups["shared"]]
    assert created["room_id"] in ids
    mine = {r["room_id"]: r for r in rl.group_rooms(listed)["mine"]}
    # dev mode: the creator is the owner, so the room is in «Your rooms»
    assert created["room_id"] in mine, rl.summary(groups)


def test_the_same_name_twice_is_the_nodes_409_with_its_sentence(node):
    name = f"R1 doppio {int(time.time() * 1000)}"
    rl.create_room(node, None, name)
    with pytest.raises(rl.RoomError) as caught:
        rl.create_room(node, None, name)
    assert caught.value.status == 409
    assert "already declared" in str(caught.value)
