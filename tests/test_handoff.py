"""The deep-link, consumed by EMtools — the fourth consumer of one contract.

What it kills: `server.py::server_host` (default `localhost`) plus a room name
plus a pasted token. What replaces it: one link that carries a PLACE and never a
permission, and a sign-in EMtools does for itself.

Two things are measured, and the second is the one that matters:

* the GRAMMAR — the same strings the other three suites use
  (`stratigraph-server/tests/test_handoff.py`,
  `EMStudio/frontend/scripts/check-handoff.mjs`,
  `stratigraph-chatbot/tests/test_handoff.py`). Four implementations of one
  grammar drift unless something holds them to the same inputs;
* the JOIN — that `{server, room}` reach `room.set_room` FROM THE LINK, with the
  token from the sign-in, and that `server_host` is never consulted.

Blender is not importable here (`bpy`), so the modules are loaded by path — the
same way `test_room_session.py` does it — and `join_room` is measured through a
stand-in. The real join has its own live test next door.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent

SECRETS = ("token", "access_token", "id_token", "password", "secret", "code",
           "authorization", "bearer", "api_key")


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, _REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


handoff = _load("em_handoff", "sync_manager/handoff.py")


# ── 1 · the grammar ──────────────────────────────────────────────────────────

def test_both_forms_read_back_to_the_same_place():
    scheme = "stratigraph://open?server=https%3A%2F%2Fem.example.org&room=saggio-b"
    web = "https://em.example.org/open?server=https%3A%2F%2Fem.example.org&room=saggio-b"
    assert handoff.parse(scheme) == handoff.parse(web) == {
        "server": "https://em.example.org", "room": "saggio-b"}


def test_the_web_form_may_leave_the_server_implicit():
    assert handoff.parse("https://em.example.org/open?room=r")["server"] == \
        "https://em.example.org"


@pytest.mark.parametrize("secret", SECRETS)
def test_a_link_carrying_a_credential_is_refused_by_name(secret):
    with pytest.raises(handoff.HandoffError) as exc:
        handoff.parse(
            f"stratigraph://open?server=https%3A%2F%2Fx&room=r&{secret}=v")
    assert secret in str(exc.value)
    assert "never a permission" in str(exc.value)


@pytest.mark.parametrize("bad, fragment", [
    ("", "empty"),
    ("stratigraph://join?room=r", "unknown action"),
    ("mailto:someone@example.org", "not a handoff link"),
    ("https://em.example.org/rooms?room=r", "not a handoff link"),
    ("stratigraph://open?server=https%3A%2F%2Fx", "names no room"),
])
def test_what_is_not_a_handoff_is_said(bad, fragment):
    with pytest.raises(handoff.HandoffError) as exc:
        handoff.parse(bad)
    assert fragment in str(exc.value)


def test_the_scheme_is_the_ecosystems_not_this_addons():
    assert handoff.SCHEME == "stratigraph"
    assert handoff.ACTION == "open"


# ── 2 · the three values the join needs ──────────────────────────────────────

def test_a_link_resolves_to_server_room_and_a_token_from_the_SIGN_IN():
    asked = []
    where = handoff.resolve(
        "stratigraph://open?server=https%3A%2F%2Fem.example.org&room=saggio-b",
        sign_in_with=lambda server: asked.append(server) or "tok-from-oidc")
    assert where == {"server": "https://em.example.org", "room": "saggio-b",
                     "token": "tok-from-oidc"}
    # the sign-in went to the server the LINK named, and to nothing else
    assert asked == ["https://em.example.org"]


def test_a_node_with_no_oidc_resolves_to_no_token_rather_than_failing():
    where = handoff.resolve(
        "stratigraph://open?server=http%3A%2F%2F127.0.0.1%3A8000&room=r",
        sign_in_with=lambda _s: None)
    assert where["token"] is None and where["room"] == "r"


# ── 3 · the sign-in: dependency-free, and the three things easy to get wrong ─

def test_the_oidc_is_stdlib_only_because_blender_cannot_pip_install():
    source = (_REPO / "sync_manager" / "handoff.py").read_text(encoding="utf-8")
    for library in ("requests", "httpx", "authlib", "oauthlib", "jwt",
                    "requests_oauthlib"):
        assert f"import {library}" not in source, library
    # …and what it DOES use is all in the standard library
    for stdlib in ("urllib", "hashlib", "secrets", "base64", "http.server",
                   "webbrowser"):
        assert stdlib in source


def test_pkce_is_S256_the_state_is_checked_and_there_is_no_secret():
    source = (_REPO / "sync_manager" / "handoff.py").read_text(encoding="utf-8")
    # `plain` would make the interception PKCE prevents possible again
    assert '"code_challenge_method": "S256"' in source
    assert '"plain"' not in source
    # a code delivered with somebody else's state is one this Blender did not ask for
    assert 'got.get("state") != state' in source
    # a public client that sent a secret would be publishing it
    assert "client_secret" not in source.replace("# NO client_secret", "")


def test_the_token_is_never_written_anywhere():
    """Precise names, not substrings: the first version of this asserted on
    `open(` and matched `urlopen(` — a test that fails on the thing it is meant
    to allow teaches people to weaken it."""
    source = (_REPO / "sync_manager" / "handoff.py").read_text(encoding="utf-8")
    for sink in ("json.dump(", ".write_text(", "builtins.open",
                 "bpy.types.Scene", "os.environ["):
        assert sink not in source, f"{sink} in the sign-in path"
    # the ONLY `.write(` is the browser tab's own "you can close this" page, and
    # it goes to a SOCKET rather than to a file
    assert source.count(".write(") == source.count("self.wfile.write(") == 1


def test_the_redirect_is_a_loopback_listener_as_a_native_app_should_use():
    """RFC 8252 — and it is what lets this work with no registered scheme and no
    embedded browser (a webview is a phishing surface several IdPs refuse)."""
    source = (_REPO / "sync_manager" / "handoff.py").read_text(encoding="utf-8")
    assert '("127.0.0.1", 0)' in source
    assert "http://127.0.0.1:{self._listener.server_port}{LOOPBACK_PATH}" in source
    assert 'LOOPBACK_PATH = "/"' in source


# ── 4 · the join takes its three values FROM THE LINK ────────────────────────

def test_the_operator_hands_join_room_what_the_link_said(monkeypatch):
    """The gate: `{server, room}` from the link, the token from the sign-in, and
    `server_host` never consulted.

    `operators.py` imports `bpy`, so what is measured is the CALL it makes — read
    out of the module's own source and then performed against a stand-in, which
    is the honest half a headless test can reach."""
    source = (_REPO / "sync_manager" / "operators.py").read_text(encoding="utf-8")
    assert "class EM_OT_room_open_link" in source
    assert "where = handoff.resolve(" in source
    assert "link, adopt = self.link, self.adopt" in source
    assert ('join_room(context, where["server"], where["room"], token,' in source)
    # the panel's fields are UPDATED from the link, never read into it
    assert 'context.scene.em_room_url = where["server"]' in source
    assert 'context.scene.em_room_id = where["room"]' in source
    # and nothing in this path touches the old manual host
    path = source[source.index("class EM_OT_room_open_link"):
                  source.index("class EM_OT_set_mode")]
    assert "server_host" not in path


def test_the_whole_hop_link_to_set_room(monkeypatch):
    """Link → resolve → the values `join_room` would pass to `room.set_room`.

    `room.py` is importable without `bpy`, so this drives the REAL seam rather
    than asserting on a string."""
    room = _load("em_room_cfg", "sync_manager/room.py")
    room.set_room(None, None, None)
    assert not room.is_configured()

    where = handoff.resolve(
        "stratigraph://open?server=https%3A%2F%2Fem.example.org&room=saggio-b",
        sign_in_with=lambda _s: "tok-from-oidc")
    room.set_room(where["server"], where["room"], where["token"])

    assert room.is_configured()
    state = room.room()
    assert state["base_url"] == "https://em.example.org"
    assert state["room_id"] == "saggio-b"
    assert state["has_token"] is True
    # …and the token is REPORTED as present without being handed out
    assert "tok-from-oidc" not in str(state)
    assert room.ws_url().startswith("wss://em.example.org/v1/rooms/saggio-b/")
    room.set_room(None, None, None)


def test_the_manual_fields_remain_as_the_declared_fallback():
    """A node in a trench has no browser. Taking the manual route away to make a
    point would break the honest case.

    N1 (5 Oct 2026) · the fields left the panel for the two windows: the room
    by id in «Enter a collaborative room…», under the lists and beside the
    link; the node's address in «Choose the node», which probes it."""
    source = (_REPO / "sync_manager" / "windows.py").read_text(encoding="utf-8")
    enter = source[source.index("class EM_OT_room_enter"):
                   source.index("class EM_OT_room_reconnect")]
    assert 'prop(context.scene, "em_room_id", text="By id")' in enter
    assert '"em.room_open_link"' in enter
    # R1 · …and the node's room LIST comes before the field to type into
    assert enter.index('"EM_UL_rooms"') < enter.index('"em_room_id"')
    choose = source[source.index("class EM_OT_node_choose"):
                    source.index("class EM_OT_node_use")]
    assert '"em_node_address"' in choose
    panel = (_REPO / "sync_manager" / "panel.py").read_text(encoding="utf-8")
    assert '"em_room_url"' not in panel and '"em_room_id"' not in panel


# ── 5 · against a REAL server, when one is up ────────────────────────────────

def _live_server():
    import urllib.error
    import urllib.request
    base = "http://127.0.0.1:8000"
    try:
        with urllib.request.urlopen(f"{base}/v1/health", timeout=2) as answer:
            return base if answer.status == 200 else None
    except (urllib.error.URLError, OSError):
        return None


def _dev_token():
    import subprocess
    helper = _REPO.parent / "stratigraph-server" / "dev-stack" / "token.sh"
    if not helper.is_file():
        return None
    try:
        out = subprocess.run([str(helper)], capture_output=True, text=True,
                             timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


@pytest.mark.skipif(_live_server() is None,
                    reason="no StratiGraph Server at :8000 — start the dev stack "
                           "(stratigraph-server/dev-stack/fcn-up.sh) to measure this")
def test_a_LINK_joins_a_real_room_with_no_server_host_typed():
    """The gate FASE D exists for: the link supplies the place, the sign-in
    supplies the token, and the existing room session does the rest.

    The package shim is `test_room_session.py`'s — `room_session` says
    `from ..sync_bridge.ws_client import …` and must be loaded as a member of a
    package. Reused rather than reinvented, which is also the point of the
    feature.
    """
    import types
    import urllib.request

    base, token = _live_server(), _dev_token()
    if not token:
        pytest.skip("dev-stack/token.sh did not produce a token")
    s3d = _REPO.parent / "s3Dgraphy" / "src"
    if s3d.is_dir() and str(s3d) not in sys.path:
        sys.path.insert(0, str(s3d))

    room_id = "handoff-emtools"
    request = urllib.request.Request(
        f"{base}/v1/rooms", method="POST",
        data=b'{"room_id": "handoff-emtools", "title": "EMtools handoff"}',
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}"})
    try:
        urllib.request.urlopen(request, timeout=10).read()
    except Exception:                       # already there from an earlier run
        pass

    bridge = types.ModuleType("_hd_bridge")
    bridge.__path__ = [str(_REPO / "sync_bridge")]
    sys.modules["sync_bridge"] = bridge
    _load("sync_bridge.ws_client", "sync_bridge/ws_client.py")
    parent = types.ModuleType("_hd_addon")
    parent.__path__ = [str(_REPO)]
    sys.modules["_hd_addon"] = parent
    sys.modules["_hd_addon.sync_bridge"] = bridge
    sys.modules["_hd_addon.sync_bridge.ws_client"] = sys.modules["sync_bridge.ws_client"]
    inner = types.ModuleType("_hd_addon.sync_manager")
    inner.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_hd_addon.sync_manager"] = inner
    room = _load("_hd_addon.sync_manager.room", "sync_manager/room.py")
    session_module = _load("_hd_addon.sync_manager.room_session",
                           "sync_manager/room_session.py")

    # …and THIS is the whole feature: three values, from a link.
    link = (f"stratigraph://open?server="
            f"{urllib.parse.quote(base, safe='')}&room={room_id}")
    where = handoff.resolve(link, sign_in_with=lambda _s: token)
    assert where["server"] == base and where["room"] == room_id
    room.set_room(where["server"], where["room"], where["token"])

    made = session_module.RoomSession()
    try:
        arrival = made.join(timeout=15.0)
        assert made.joined, "the session did not report itself joined"
        assert arrival.get("snapshot"), "no snapshot came back from the room"
        assert made.room_id == room_id
    finally:
        try:
            made.leave()
        except Exception:                   # noqa: BLE001 — teardown, not the test
            pass
        room.set_room(None, None, None)


import urllib.parse  # noqa: E402  — used by the live test above


# ── 6 · the round-trip, emit half ────────────────────────────────────────────

def test_the_browser_door_wins_where_a_web_build_is_hosted():
    targets = {"scheme": "stratigraph://open?room=r",
               "web": "https://em.example.org/open?room=r",
               "tools": {"emstudio": {
                   "scheme": "stratigraph://open?room=r",
                   "browser": "http://localhost:5177/?room=r"}}}
    door = handoff.emstudio_link(targets)
    assert door == {"link": "http://localhost:5177/?room=r", "kind": "browser",
                    "web": "https://em.example.org/open?room=r"}


def test_the_desktop_scheme_is_the_door_when_no_web_build_is_hosted():
    targets = {"scheme": "stratigraph://open?room=r",
               "tools": {"emstudio": {"scheme": "stratigraph://open?room=r"}}}
    assert handoff.emstudio_link(targets)["kind"] == "scheme"


def test_a_link_carrying_a_credential_is_refused_rather_than_forwarded():
    """Forwarding one would end the contract's only property."""
    with pytest.raises(handoff.HandoffError) as exc:
        handoff.emstudio_link({"tools": {"emstudio": {
            "browser": "http://localhost:5177/?room=r&token=abc"}}})
    assert "token" in str(exc.value) and "never a permission" in str(exc.value)


def test_no_door_at_all_beats_a_door_that_fails_after_the_click():
    assert handoff.emstudio_link({"tools": {}})["link"] is None


def test_the_link_is_ASKED_FOR_never_assembled_here():
    source = (_REPO / "sync_manager" / "handoff.py").read_text(encoding="utf-8")
    emit = source[source.index("def open_targets"):]
    code = re.sub(r'"""[\s\S]*?"""|#.*', "", emit)
    assert "stratigraph://" not in code, "the emit half writes no scheme of its own"
    assert "/v1/rooms/" in code and "/open" in code, "it asks the handoff endpoint"


def test_the_operator_is_EMIT_only_and_says_so():
    """Receiving a link inside Blender is a job of its own — Blender is not a
    URL-scheme handler. Half of it, offered as if it worked, would be the worse
    half."""
    source = (_REPO / "sync_manager" / "operators.py").read_text(encoding="utf-8")
    block = source[source.index("class EM_OT_room_open_elsewhere"):
                   source.index("class EM_OT_set_mode")]
    assert "Emit-only" in block
    assert "webbrowser.open(door[\"link\"])" in block
    # …and it is offered only while joined: off a room it would open nothing
    assert "return bool(SESSION.joined)" in block
    panel = (_REPO / "sync_manager" / "panel.py").read_text(encoding="utf-8")
    inside = panel[panel.index("def _in_room"):]
    assert '"em.room_open_elsewhere"' in inside
    assert panel.count('"em.room_open_elsewhere"') == 1
    assert '"em.room_open_elsewhere"' in panel


import re  # noqa: E402 — used by the source checks above


# ── 7 · the manual door signs in too ─────────────────────────────────────────
#
# The LAST place a person saw a token. The link door has done its own OIDC for a
# while; this one still asked for a pasted one, so the credential somebody had
# to find, copy and carry existed purely because two doors into the same room
# were wired differently.
#
# `operators.py` imports `bpy`, so `join_manual` is exercised through the same
# kind of seam `handoff.resolve` uses: `sign_in_with` for the round trip, and a
# stand-in for `join_room` (which opens a socket).

def _join_manual(monkeypatch=None, **kwargs):
    """`join_manual` with `join_room` replaced, since a real join needs a room.

    Loaded by source rather than imported: the module pulls in `bpy` at import
    time and Blender is not here. What is compiled is the REAL function — the
    `bpy`-dependent classes below it are simply never referenced.
    """
    import types

    source = (_REPO / "sync_manager" / "operators.py").read_text(encoding="utf-8")
    start = source.index("def join_manual(")
    end = source.index("def leave_room(")
    module = types.ModuleType("_join_manual_probe")
    module.__dict__["handoff"] = handoff
    calls = {}

    def fake_join_room(context, base, room_id, token, adopt=True):
        calls["args"] = {"base": base, "room_id": room_id, "token": token,
                         "adopt": adopt}
        return {"ok": True, "room": room_id, "message": "joined"}

    module.__dict__["join_room"] = fake_join_room
    # `from . import handoff` cannot work outside the package: point the import
    # at the module already loaded above, which is the same file.
    body = source[start:end].replace("from . import handoff\n", "")
    exec(compile(body, "operators.py", "exec"), module.__dict__)
    result = module.join_manual(None, **kwargs)
    return result, calls.get("args")


def test_an_empty_token_signs_in_against_the_server_the_manual_fields_name():
    asked = []
    result, passed = _join_manual(
        base="https://em.example.org", room_id="scavo-cs03", token="",
        sign_in_with=lambda server: asked.append(server) or "tok-from-oidc")
    assert result["ok"] and result["signed_in"] == "signed-in"
    # the sign-in went to the server the FIELDS name, and to nothing else
    assert asked == ["https://em.example.org"]
    # …and the token that came back is the one the join used
    assert passed["token"] == "tok-from-oidc"
    assert passed["room_id"] == "scavo-cs03"


def test_a_pasted_token_WINS_and_no_sign_in_is_attempted():
    """The declared fallback for a node in a trench with no browser. Signing in
    over the top of somebody's deliberate paste would be the tool overruling
    them."""
    asked = []
    result, passed = _join_manual(
        base="https://em.example.org", room_id="r", token="  pasted-tok  ",
        sign_in_with=lambda server: asked.append(server) or "should-not-be-used")
    assert asked == []
    assert result["signed_in"] == "pasted"
    assert passed["token"] == "pasted-tok"


def test_a_node_with_no_oidc_is_joined_without_a_token_and_it_is_REPORTED():
    """An open node and a sign-in that never ran look the same from outside."""
    result, passed = _join_manual(base="http://127.0.0.1:8000", room_id="r",
                                  token="", sign_in_with=lambda _s: None)
    assert result["ok"] and result["signed_in"] == "open-node"
    assert passed["token"] == ""
    operators = (_REPO / "sync_manager" / "operators.py").read_text(encoding="utf-8")
    assert 'if result.get("signed_in") == "open-node":' in operators
    assert "running open" in operators


def test_a_sign_in_that_fails_refuses_the_join_rather_than_joining_anonymously():
    def boom(_server):
        raise handoff.HandoffError("nobody completed the sign-in within 300s")

    result, passed = _join_manual(base="https://em.example.org", room_id="r",
                                  token="", sign_in_with=boom)
    assert not result["ok"] and result["signed_in"] == "failed"
    assert "sign-in did not complete" in result["message"]
    assert passed is None, "the room was never joined"


def test_the_token_property_is_emptied_and_written_nowhere():
    """Same claim the sign-in makes, at the other door: read out of the source,
    because the property lives on a `bpy` class."""
    operators = (_REPO / "sync_manager" / "operators.py").read_text(encoding="utf-8")
    block = operators[operators.index("class EM_OT_room_join"):
                      operators.index("class EM_OT_room_open_link")]
    assert 'self.token = ""' in block
    for sink in ("json.dump(", ".write_text(", "bpy.types.Scene.em_room_token",
                 "os.environ["):
        assert sink not in block, f"{sink} in the manual join"


def test_the_token_field_now_reads_as_the_FALLBACK_it_is():
    """It stays — a node in a trench has no browser — but it no longer asks for
    something the ordinary path does not need."""
    operators = (_REPO / "sync_manager" / "operators.py").read_text(encoding="utf-8")
    block = operators[operators.index("class EM_OT_room_join"):
                      operators.index("class EM_OT_room_open_link")]
    assert "Leave EMPTY to sign in through your browser" in block
    # the description is a wrapped source string, so match a contiguous piece of
    # it rather than a phrase that spans a line break
    assert "Fill it in only when this machine has no" in block
    assert "browser to sign in with" in block


def test_no_second_button_appeared_the_door_is_the_same_one():
    """One door into a room by its id: `em.room_join`, reached from the
    windows through «Reconnect» / «Enter» (`em.room_reconnect`), never drawn
    as a second button in the panel."""
    panel = (_REPO / "sync_manager" / "panel.py").read_text(encoding="utf-8")
    assert '"em.room_join"' not in panel
    windows = (_REPO / "sync_manager" / "windows.py").read_text(encoding="utf-8")
    assert windows.count('bpy.ops.em.room_join(') == 1


# ── Q11 · the sign-in runs off Blender's UI thread and says the true outcome ──
#
# Measured on 4 Oct 2026: Keycloak refused the loopback return of `em-console`,
# Blender waited on its UI thread, and the return page said «Signed in» to an
# error. A fake realm on the loopback stands in for Keycloak here: the browser is
# a function that follows the authorization URL the way an IdP would.

import base64 as _b64
import http.server as _hs
import json as _json
import threading as _th
import urllib.parse as _up
import urllib.request as _ur


def _fake_realm(*, refuse_redirect=False, token_status=200):
    seen = {}

    class Realm(_hs.BaseHTTPRequestHandler):
        def do_GET(self):                                    # noqa: N802
            if refuse_redirect:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"<p>Invalid parameter: redirect_uri</p>")
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'<form id="kc-form-login"></form>')

        def do_POST(self):                                   # noqa: N802
            body = self.rfile.read(int(self.headers["Content-Length"]))
            seen.update({k: v[0] for k, v in _up.parse_qs(body.decode()).items()})
            claims = _b64.urlsafe_b64encode(
                _json.dumps({"preferred_username": "dev"}).encode()).rstrip(b"=").decode()
            self.send_response(token_status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(_json.dumps(
                {"access_token": f"h.{claims}.s"} if token_status == 200
                else {"error": "invalid_grant", "error_description": "Code not valid"}
            ).encode())

        def log_message(self, *a):                           # noqa: A003
            pass

    server = _hs.HTTPServer(("127.0.0.1", 0), Realm)
    _th.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    config = {"authorization_endpoint": f"{base}/auth", "token_endpoint": f"{base}/token",
              "client_id": "em-console", "native_client_id": "em-tools"}
    return server, config, seen


def _idp(answer):
    """A browser + IdP: reads the authorization URL, calls the loopback back."""
    pages = []

    def browse(url):
        q = {k: v[0] for k, v in _up.parse_qs(_up.urlsplit(url).query).items()}
        back = q["redirect_uri"] + "?" + _up.urlencode(answer(q))

        def go():
            with _ur.urlopen(back, timeout=10) as r:
                pages.append(r.read().decode())
        _th.Thread(target=go, daemon=True).start()
    return browse, pages


def test_the_sign_in_does_not_hold_the_caller_and_names_who_signed_in():
    server, config, seen = _fake_realm()
    browse, pages = _idp(lambda q: {"code": "c0de", "state": q["state"]})
    running = handoff.SignIn("https://node", config, open_browser=browse, timeout=20)
    # the constructor RETURNED: the caller (Blender's UI thread) is free
    assert running.wait(10) and running.state == "done"
    assert running.token.startswith("h.") and running.who == "dev"
    assert seen["client_id"] == "em-tools"          # the NATIVE client, not em-console
    assert seen["redirect_uri"].startswith("http://127.0.0.1:")
    assert seen["redirect_uri"].endswith("/") and "client_secret" not in seen
    _wait_for(pages)
    assert "Signed in to https://node as dev" in pages[0]
    server.shutdown()


def test_the_return_page_says_a_refusal_and_not_signed_in():
    server, config, _ = _fake_realm()
    browse, pages = _idp(lambda q: {"error": "access_denied", "state": q["state"],
                                    "error_description": "User cancelled"})
    running = handoff.SignIn("https://node", config, open_browser=browse, timeout=20)
    assert running.wait(10) and running.state == "failed"
    assert "User cancelled" in running.error and running.token is None
    _wait_for(pages)
    assert "Sign-in did not complete" in pages[0] and "Signed in to" not in pages[0]
    server.shutdown()


def test_a_code_the_realm_refuses_is_said_on_the_page_too():
    server, config, _ = _fake_realm(token_status=400)
    browse, pages = _idp(lambda q: {"code": "c0de", "state": q["state"]})
    running = handoff.SignIn("https://node", config, open_browser=browse, timeout=20)
    assert running.wait(10) and running.state == "failed"
    assert "Code not valid" in running.error
    _wait_for(pages)
    assert "Code not valid" in pages[0]
    server.shutdown()


def test_a_refused_return_address_is_said_BEFORE_the_browser_opens():
    server, config, _ = _fake_realm(refuse_redirect=True)
    opened = []
    with pytest.raises(handoff.HandoffError) as said:
        handoff.SignIn("https://node", config, open_browser=opened.append, timeout=20)
    assert not opened
    assert "http://127.0.0.1/" in str(said.value) and "em-tools" in str(said.value)
    server.shutdown()


def test_cancel_ends_the_wait_at_once():
    import time
    server, config, _ = _fake_realm()
    running = handoff.SignIn("https://node", config, open_browser=lambda u: None,
                             timeout=60)
    started = time.monotonic()
    running.cancel()
    assert running.wait(5) and running.state == "cancelled"
    assert time.monotonic() - started < 2
    server.shutdown()


def test_every_door_of_the_panels_waits_without_freezing_blender():
    """No operator calls the blocking `handoff.sign_in` any more: they go through
    `signin_ui.access_or_wait`, which raises `Waiting` and resumes by itself."""
    for name in ("rooms_ui.py", "bring.py", "operators.py"):
        source = (_REPO / "sync_manager" / name).read_text(encoding="utf-8")
        assert "except Waiting as exc:" in source, name
    ui = (_REPO / "sync_manager" / "signin_ui.py").read_text(encoding="utf-8")
    assert "bpy.app.timers.register(_poll" in ui
    assert '"em.sign_in_cancel"' in ui
    # Z1 · the wait and the expiry are the MESSAGE zone of «Where you work»
    zones = (_REPO / "sync_manager" / "where.py").read_text(encoding="utf-8")
    assert '"em.sign_in_cancel"' in zones and '"em.sign_in_again"' in zones
    panel = (_REPO / "sync_manager" / "panel.py").read_text(encoding="utf-8")
    assert 'row.operator(msg["op"], text=msg["op_text"])' in panel


def _wait_for(pages, seconds=5):
    import time
    end = time.monotonic() + seconds
    while not pages and time.monotonic() < end:
        time.sleep(0.05)
    assert pages, "the browser got no page back"
