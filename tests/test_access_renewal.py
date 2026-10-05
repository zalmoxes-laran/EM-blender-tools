"""X1 · the access to a node, renewed before it runs out — measured headless.

Measured on 4 Oct 2026: «Archive this .blend» died fifteen minutes after
entering the room with «could not reach the room: [Errno 32] Broken pipe»; the
node had answered 401 (the `em-tools` client's tokens live 900 s). What is under
test is `sync_manager/access.py` with `room.py` beside it, loaded as a package
(without the addon's `__init__`, which imports bpy), against a real socket that
plays both the node and the realm's token endpoint:

* an access about to run out is renewed BEFORE the call: the node only ever
  sees the new token, also when the caller handed in the old copy;
* a 401 on a live-looking token is renewed once and sent again;
* a realm that will not renew gives the sentence «has expired: sign in again»,
  never a pipe, and the panel's «Sign in again» knows which node;
* the backup itself (`room.put_blend_backup`) goes through it.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import importlib
import json
import pathlib
import sys
import threading
import time
import types
import urllib.parse
import urllib.request

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_PKG = "_emt_access_pkg"


def _package():
    if _PKG not in sys.modules:
        pkg = types.ModuleType(_PKG)
        pkg.__path__ = [str(_REPO / "sync_manager")]
        sys.modules[_PKG] = pkg
    return (importlib.import_module(f"{_PKG}.access"),
            importlib.import_module(f"{_PKG}.room"))


access, room = _package()


def jwt(exp: float, name: str) -> str:
    def b64(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()
    return f"{b64({'alg': 'none'})}.{b64({'exp': int(exp), 'n': name})}.sig"


class _World(http.server.BaseHTTPRequestHandler):
    valid: set = set()
    seen: list = []
    refresh_ok = True
    issued = 0

    def log_message(self, *_a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):                                       # the realm
        n = int(self.headers.get("Content-Length") or 0)
        form = urllib.parse.parse_qs(self.rfile.read(n).decode())
        if self.path != "/token" or form.get("grant_type") != ["refresh_token"]:
            return self._send(400, {"error": "unsupported"})
        if not _World.refresh_ok:
            return self._send(400, {"error": "invalid_grant",
                                    "error_description": "Session not active"})
        _World.issued += 1
        token = jwt(time.time() + 900, f"renewed{_World.issued}")
        _World.valid.add(token)
        return self._send(200, {"access_token": token, "expires_in": 900,
                                "refresh_token": f"r{_World.issued}"})

    def _auth(self):
        token = (self.headers.get("Authorization") or "")[7:]
        _World.seen.append(token)
        return token in _World.valid

    def do_GET(self):                                        # the node
        if not self._auth():
            return self._send(401, {"detail": "invalid token"})
        return self._send(200, {"ok": True})

    def do_PUT(self):
        if not self._auth():
            return self._send(401, {"detail": "invalid token"})
        n = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(n)
        return self._send(200, {"sha256": hashlib.sha256(data).hexdigest(),
                                "created": True, "size": len(data)})


@pytest.fixture()
def world():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _World)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    _World.valid, _World.seen, _World.refresh_ok, _World.issued = set(), [], True, 0
    access.forget()
    access.EXPIRED.update({"base": "", "line": ""})
    yield base
    server.shutdown()
    room.set_room(None, None, "")


def _sign_in(base, *, left: float, refresh: str = "r0"):
    token = jwt(time.time() + left, "first")
    _World.valid.add(token)
    access.remember(base, token, refresh_token=refresh,
                    token_endpoint=f"{base}/token", client_id="em-tools")
    return token


def _get(base, token):
    req = urllib.request.Request(f"{base}/v1/rooms",
                                 headers={"Authorization": f"Bearer {token}"})
    with access.urlopen(req, timeout=5) as answer:
        return json.loads(answer.read())


def test_an_access_about_to_run_out_is_renewed_before_the_call(world):
    old = _sign_in(world, left=30)                  # less than SKEW
    assert _get(world, old) == {"ok": True}
    assert _World.seen == [t for t in _World.seen if t != old], \
        "the node must never see the access that was running out"
    assert _World.issued == 1


def test_a_stale_copy_is_replaced_by_the_newest_of_its_lineage(world):
    old = _sign_in(world, left=30)
    _get(world, old)                                # renewed once
    _get(world, old)                                # the caller's copy is stale
    assert _World.issued == 1
    assert old not in _World.seen


def test_a_401_is_renewed_once_and_sent_again(world):
    old = _sign_in(world, left=600)                 # looks alive
    _World.valid.discard(old)                       # …but the node refuses it
    assert _get(world, old) == {"ok": True}
    assert _World.seen[0] == old and _World.seen[1] != old
    assert _World.issued == 1


def test_a_realm_that_will_not_renew_says_expired_not_broken_pipe(world):
    old = _sign_in(world, left=-5)
    _World.refresh_ok = False
    with pytest.raises(access.AccessExpired) as caught:
        _get(world, old)
    sentence = str(caught.value)
    assert "has expired: sign in again" in sentence
    assert "Broken pipe" not in sentence and "Session not active" in sentence
    assert access.EXPIRED["base"] == world
    assert _World.seen == [], "nothing is sent on an access that is known dead"
    assert isinstance(caught.value, room.RoomError) and caught.value.status == 401


def test_a_pasted_token_without_refresh_says_expired(world):
    room.set_room(world, "r", jwt(time.time() - 5, "pasted"))
    with pytest.raises(access.AccessExpired):
        _get(world, room._session["token"])


def test_another_person_on_the_same_node_is_another_lineage(world):
    """Measured on 5 Oct 2026 (the room list smoke): a viewer's token pasted
    after dev's joined dev's lineage, and every call went out as dev."""
    def b64(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    def person(sub):
        return f"{b64({'alg': 'none'})}.{b64({'exp': int(time.time() + 900), 'sub': sub})}.sig"

    dev = person("dev")
    access.remember(world, dev, refresh_token="r0", token_endpoint=world + "/token",
                    client_id="em-tools")
    viewer = person("viewer")
    room.set_room(world, None, viewer)
    assert access.fresh(viewer) == viewer
    assert access.fresh(dev) == dev          # dev's own copy is not swapped either


def test_the_blend_backup_goes_through_the_renewal(world):
    old = _sign_in(world, left=100)                 # < SKEW_BODY: renewed first
    room.set_room(world, "templu", old)
    record = room.put_blend_backup(b"BLENDER" * 1000, filename="t.blend")
    assert record["created"] is True
    assert old not in _World.seen
    assert room._session["token"] != old, "the session follows the renewal"


# ── X2 · «Bring into a room…» counts what travelled apart ────────────────────

def test_the_bring_sentence_counts_uploads_and_files_already_there_apart():
    bring = importlib.import_module(f"{_PKG}.bring")
    assert bring.upload_phrase(0, 0, 66) == "66 already on the node, nothing uploaded"
    assert bring.upload_phrase(3, 2048, 63) == "uploaded 3 (2.0 KB), 63 already on the node"
    assert bring.upload_phrase(2, 1024, 0) == "uploaded 2 (1.0 KB)"
    assert bring.upload_phrase(0, 0, 0) == "nothing uploaded"


def test_put_asset_does_not_send_bytes_the_room_holds(world):
    """The HEAD first: a model the room keeps is not uploaded again."""
    class Room(_World):
        def do_HEAD(self):
            ok = self._auth() and self.path.endswith(Room.held)
            self.send_response(200 if ok else 404)
            self.end_headers()
    data = b"glb bytes"
    Room.held = "sha256:" + hashlib.sha256(data).hexdigest()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Room)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        token = _sign_in(base, left=900)
        room.set_room(base, "r", token)
        info = room.put_asset(data)
        assert info["already"] is True and info["created"] is False
        assert info["ref"] == Room.held
    finally:
        server.shutdown()


def test_a_short_access_is_not_renewed_at_every_call(world):
    """Measured with a 60 s access (the run of T-X1): 195 renewals in one
    bring, because the margin was longer than the access's life."""
    def b64(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()
    now = time.time()
    token = f"{b64({'alg': 'none'})}.{b64({'iat': int(now), 'exp': int(now) + 60})}.sig"
    _World.valid.add(token)
    access.remember(world, token, refresh_token="r0",
                    token_endpoint=f"{world}/token", client_id="em-tools")
    for _ in range(5):
        _get(world, token)
    assert _World.issued == 0, "a 60 s access with 59 s left needs no renewal"
