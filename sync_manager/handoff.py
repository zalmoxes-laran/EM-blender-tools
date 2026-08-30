"""The deep-link, consumed — a room opened by a link instead of by typing a host.

The manual configuration this kills is `server.py::server_host` (default
`localhost`) plus a room name plus a token: three things to get right in a panel,
and the third one a credential somebody pasted from a terminal.

Now: one link.

    stratigraph://open?server=<addr>&room=<id>

**It carries a place and never a permission.** EMtools signs in against that
server itself (Authorization Code + PKCE, public client) and holds the token in
memory — `room.py` already keeps it there and never writes it anywhere. So a link
in a chat or a screenshot leaks nothing, and the token belongs to whoever is at
this Blender rather than to whoever wrote the link.

**Nothing new is built here** — the point of being connector #1. The link supplies
`{server, room}`, this module supplies the token, and `operators.join_room` does
what it has always done. What changed is only where those three values come from.

**Dependency-free, and that is a requirement rather than a style.** Blender's
bundled Python has no `requests`, no `websockets` and no OIDC library, and an
addon cannot ask a user to `pip install`. So this is stdlib only, exactly like
`sync_bridge/ws_client.py` next door: `urllib`, `hashlib`, `secrets`, `base64`,
`http.server`, `webbrowser`. PKCE is small; what makes it correct is that the
three things easy to get wrong are all here — `S256` (never `plain`), the `state`
check, and no client secret.

The grammar is StratiGraph Server's (`app/handoff.py` there) and is implemented
here rather than fetched: a client that had to reach a server to learn WHICH
server to reach could not start. The four copies are held to the same strings by
each repo's own suite.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Callable, Dict, Optional

SCHEME = "stratigraph"
ACTION = "open"

#: Refused rather than ignored: accepting one teaches whoever built the link that
#: sending one works, and then the contract has no property left.
FORBIDDEN = ("token", "access_token", "id_token", "password", "secret", "code",
             "authorization", "bearer", "api_key")


class HandoffError(RuntimeError):
    """A link that is not a handoff, said rather than half-read."""


def parse(link: str) -> Dict[str, str]:
    """`{server, room}` out of either form of the link, or a sentence."""
    raw = str(link or "").strip()
    if not raw:
        raise HandoffError("empty link")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme == SCHEME:
        action = parsed.netloc or parsed.path.lstrip("/")
        if action != ACTION:
            raise HandoffError(
                f"unknown action {action!r}: this scheme understands "
                f"{SCHEME}://{ACTION}")
    elif parsed.scheme in ("http", "https"):
        if not parsed.path.rstrip("/").endswith(f"/{ACTION}"):
            raise HandoffError(
                f"not a handoff link: {raw} (expected a path ending in /{ACTION})")
    else:
        raise HandoffError(
            f"not a handoff link: {raw} (expected {SCHEME}://{ACTION}?… or an "
            f"https link to /{ACTION})")

    query = urllib.parse.parse_qs(parsed.query)
    carried = sorted(k for k in query if k.lower() in FORBIDDEN)
    if carried:
        raise HandoffError(
            f"this link carries {', '.join(carried)} — a handoff names a place "
            f"and never a permission. Refused so that sending one never starts "
            f"working: EMtools signs in by itself.")

    room = (query.get("room") or [""])[0].strip()
    if not room:
        raise HandoffError("the link names no room")
    server = (query.get("server") or [""])[0].strip().rstrip("/")
    if not server:
        if parsed.scheme in ("http", "https"):
            server = f"{parsed.scheme}://{parsed.netloc}"
        else:
            raise HandoffError("the link names no server")
    return {"server": server, "room": room}


# ── signing in, stdlib only ─────────────────────────────────────────────────

def auth_config(server: str, *, timeout: float = 10.0
                ) -> Optional[Dict[str, Any]]:
    """How that node wants a client to sign in — `GET /v1/auth-config`.

    `None` when it has no OIDC at all: a dev node runs open, and that is a fact
    about the deployment rather than a failure to report.
    """
    import json
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(
                f"{server.rstrip('/')}/v1/auth-config", timeout=timeout) as answer:
            if answer.status != 200:
                return None
            return json.loads(answer.read() or b"{}")
    except (urllib.error.URLError, OSError, ValueError):
        return None


def sign_in(server: str, *, open_browser: Optional[Callable[[str], Any]] = None,
            timeout: float = 300.0) -> Optional[str]:
    """Authorization Code + PKCE against that server; the token stays in memory.

    The redirect comes back to a LOOPBACK listener, which is what a native app is
    supposed to use (RFC 8252) and what lets this work with no registered scheme
    and no embedded browser — an embedded webview is a phishing surface and
    several IdPs refuse it outright.

    **Blender-safe**: the listener is a daemon thread that answers exactly one
    request and closes. It touches no `bpy` and nothing on disk.

    Returns the access token, or `None` when the node has no OIDC — in which case
    the caller joins without one, which is what that node expects.
    """
    import base64
    import hashlib
    import http.server
    import json
    import secrets
    import threading
    import urllib.request
    import webbrowser

    config = auth_config(server)
    if not config or not config.get("authorization_endpoint"):
        return None

    verifier = base64.urlsafe_b64encode(
        secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(24)
    got: Dict[str, str] = {}
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):                                   # noqa: N802
            got.update({k: v[0] for k, v in urllib.parse.parse_qs(
                urllib.parse.urlsplit(self.path).query).items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>Signed in</h1><p>You can close this tab and "
                             b"go back to Blender.</p>")
            done.set()

        def log_message(self, *args):                       # noqa: A003
            pass                        # Blender's console is not our log

    listener = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    redirect_uri = f"http://127.0.0.1:{listener.server_port}/"
    threading.Thread(target=listener.handle_request, daemon=True).start()

    url = config["authorization_endpoint"] + "?" + urllib.parse.urlencode({
        "response_type": "code",
        "client_id": config.get("client_id") or "em-console",
        "redirect_uri": redirect_uri,
        "scope": config.get("scope") or "openid profile email",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    })
    (open_browser or webbrowser.open)(url)
    if not done.wait(timeout):
        listener.server_close()
        raise HandoffError(
            f"nobody completed the sign-in within {int(timeout)}s. The link is "
            f"still good — press Join again.")
    listener.server_close()

    if got.get("error"):
        raise HandoffError(
            f"sign-in refused: {got.get('error_description') or got['error']}")
    if got.get("state") != state:
        # the one check that makes the round trip mean anything: a code delivered
        # with somebody else's state is one this Blender did not ask for
        raise HandoffError("the sign-in state did not match — refusing a code "
                           "this session did not ask for")
    if not got.get("code"):
        raise HandoffError("no authorization code came back")

    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": got["code"],
        "redirect_uri": redirect_uri,
        "client_id": config.get("client_id") or "em-console",
        "code_verifier": verifier,
        # NO client_secret: a public client that sent one would be publishing it
    }).encode()
    request = urllib.request.Request(
        config["token_endpoint"], data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(request, timeout=30) as answer:
        payload = json.loads(answer.read() or b"{}")
    token = str(payload.get("access_token") or "")
    if not token:
        raise HandoffError("the sign-in returned no access token")
    return token


def resolve(link: str, *, sign_in_with: Optional[Callable[[str], Optional[str]]] = None
            ) -> Dict[str, Optional[str]]:
    """A link in, `{server, room, token}` out — the three values the join needs.

    Kept apart from the join itself so the operator stays thin and the suite can
    measure this half without a room: `sign_in_with` is that seam.
    """
    where = parse(link)
    token = (sign_in_with or sign_in)(where["server"])
    return {"server": where["server"], "room": where["room"], "token": token}
