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
        from .trust import urlopen as _open
    except ImportError:          # loaded by path, outside the package (the suite)
        _open = urllib.request.urlopen
    try:
        with _open(f"{server.rstrip('/')}/v1/auth-config", timeout=timeout) as answer:
            if answer.status != 200:
                return None
            return json.loads(answer.read() or b"{}")
    except (urllib.error.URLError, OSError, ValueError):
        return None


#: The client a NATIVE app signs in as, when the node names one
#: (`native_client_id` in `/v1/auth-config`). MEASURED on Keycloak 24.0.4 (4 Oct
#: 2026, a throwaway container): a redirect URI registered as
#: `http://127.0.0.1/` admits `http://127.0.0.1:<any port>/` — the port on the
#: loopback is ignored, as RFC 8252 §7.3 asks — while the PATH stays exact
#: (`/other` refused) and `[::1]` is refused. The browser client `em-console`
#: does not carry that URI, and must not need to: its redirects are pages.
LOOPBACK_PATH = "/"


def _client_of(config: Dict[str, Any]) -> str:
    return str(config.get("native_client_id") or config.get("client_id")
               or "em-console")


def _who(token: str) -> str:
    """The name to SAY on the return page — read, not verified (the node verifies)."""
    import base64
    import json
    try:
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except Exception:  # noqa: BLE001 — an opaque token: no name to say
        return ""
    return str(claims.get("preferred_username") or claims.get("orcid")
               or claims.get("sub") or "")


def _page(title: str, line: str) -> bytes:
    import html
    return (f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}</title>"
            f"<body style=\"font:16px system-ui;margin:3em\"><h1>{html.escape(title)}</h1>"
            f"<p>{html.escape(line)}</p></body>").encode("utf-8")


def _refused_redirect(url: str, timeout: float = 10.0) -> bool:
    """Does the realm refuse this return address? Asked BEFORE the browser opens.

    Keycloak answers an unknown `redirect_uri` with its own error page and never
    comes back — so without this question Blender would wait for a return that
    cannot happen, and the person would read the refusal in a browser tab.
    """
    import urllib.error
    import urllib.request

    class _Stay(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):           # noqa: D401
            return None

    handlers = [_Stay()]
    try:
        from .trust import context as _ctx
        handlers.append(urllib.request.HTTPSHandler(context=_ctx()))
    except ImportError:          # loaded by path, outside the package (the suite)
        pass
    try:
        with urllib.request.build_opener(*handlers).open(url, timeout=timeout) as answer:
            body = answer.read(65536).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read(65536).decode("utf-8", "replace") if exc.code == 400 else ""
    except (urllib.error.URLError, OSError):
        return False             # not reachable from here: the browser will say it
    return "redirect_uri" in body and "nvalid" in body


class SignIn:
    """One Authorization Code + PKCE round trip, run OFF Blender's UI thread.

    Measured on 4 Oct 2026: the old `sign_in` waited with `done.wait(timeout)` on
    the thread that draws Blender, so a realm that refused the return address left
    Blender frozen for five minutes. Now the listener and the code exchange run in
    a daemon thread; the UI only READS `state` (a timer polls it) and may
    `cancel()`. And the tab the browser lands on says what really happened —
    signed in as whom, or refused and why — instead of «Signed in» to everything.

    `state` is `waiting`, then one of `done`, `failed`, `cancelled`.
    """

    def __init__(self, server: str, config: Dict[str, Any], *,
                 open_browser: Optional[Callable[[str], Any]] = None,
                 timeout: float = 300.0, preflight: bool = True):
        import base64
        import hashlib
        import http.server
        import secrets
        import threading
        import time
        import webbrowser

        self.server = server
        self.state = "waiting"
        self.token: Optional[str] = None
        self.who = ""
        self.error = ""
        self._cancel = threading.Event()
        self.finished = threading.Event()
        self.deadline = time.monotonic() + timeout

        verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)).rstrip(b"=").decode()
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(24)
        client_id = _client_of(config)
        me = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):                                   # noqa: N802
                split = urllib.parse.urlsplit(self.path)
                got = {k: v[0] for k, v in urllib.parse.parse_qs(split.query).items()}
                if split.path != LOOPBACK_PATH or not (got.get("code") or got.get("error")):
                    self.send_response(404)                     # a favicon, a probe
                    self.end_headers()
                    return
                title, line = me._conclude(got, state, verifier, redirect_uri,
                                           client_id, config)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(_page(title, line))

            def log_message(self, *args):                       # noqa: A003
                pass                        # Blender's console is not our log

        self._listener = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self._listener.timeout = 0.25
        redirect_uri = f"http://127.0.0.1:{self._listener.server_port}{LOOPBACK_PATH}"
        self.redirect_uri = redirect_uri
        self.client_id = client_id

        self.url = config["authorization_endpoint"] + "?" + urllib.parse.urlencode({
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": config.get("scope") or "openid profile email",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        })
        if preflight and _refused_redirect(self.url):
            self._listener.server_close()
            raise HandoffError(
                f"the node's sign-in (client {client_id}) does not accept Blender's "
                f"return address {redirect_uri}. The node must name a native client "
                f"whose redirect URI is http://127.0.0.1/ (any port on the loopback, "
                f"RFC 8252) — ask whoever runs the node; on the dev stack, recreate "
                f"Keycloak with the current realm-em-dev.json.")

        def serve():
            try:
                while (me.state == "waiting" and not me._cancel.is_set()
                       and time.monotonic() < me.deadline):
                    self._listener.handle_request()
                if me.state == "waiting":
                    if me._cancel.is_set():
                        me.state, me.error = "cancelled", "sign-in cancelled"
                    else:
                        me.state, me.error = "failed", (
                            f"nobody completed the sign-in within {int(timeout)}s — "
                            f"try again")
            finally:
                self._listener.server_close()
                me.finished.set()

        threading.Thread(target=serve, daemon=True, name="em-sign-in").start()
        (open_browser or webbrowser.open)(self.url)

    def _conclude(self, got, state, verifier, redirect_uri, client_id, config):
        """The code, checked and exchanged — and the page's TRUE sentence."""
        import json
        import urllib.error
        import urllib.request

        def fail(why):
            self.state, self.error = "failed", why
            return ("Sign-in did not complete",
                    f"{why}. Go back to Blender: nothing was signed in.")

        if got.get("error"):
            return fail(f"sign-in refused: {got.get('error_description') or got['error']}")
        if got.get("state") != state:
            # the one check that makes the round trip mean anything: a code delivered
            # with somebody else's state is one this Blender did not ask for
            return fail("the sign-in state did not match — refusing a code this "
                        "session did not ask for")
        if not got.get("code"):
            return fail("no authorization code came back")
        body = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": got["code"],
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": verifier,
            # NO client_secret: a public client that sent one would be publishing it
        }).encode()
        request = urllib.request.Request(
            config["token_endpoint"], data=body, method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            try:
                from .trust import urlopen as _open
            except ImportError:  # loaded by path, outside the package (the suite)
                _open = urllib.request.urlopen
            with _open(request, timeout=30) as answer:
                payload = json.loads(answer.read() or b"{}")
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = json.loads(exc.read() or b"{}").get("error_description") or ""
            except Exception:  # noqa: BLE001
                pass
            return fail(f"the realm refused the code ({exc.code})"
                        + (f": {detail}" if detail else ""))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return fail(f"could not reach the realm to finish: "
                        f"{getattr(exc, 'reason', exc)}")
        token = str(payload.get("access_token") or "")
        if not token:
            return fail("the sign-in returned no access token")
        self.token, self.who = token, _who(token)
        self.state = "done"
        return ("Signed in",
                f"Signed in to {self.server}"
                + (f" as {self.who}" if self.who else "")
                + ". You can close this tab and go back to Blender.")

    def cancel(self) -> None:
        self._cancel.set()

    def wait(self, timeout: Optional[float] = None) -> bool:
        """For a caller that is NOT the UI thread (the suite, a headless run)."""
        return self.finished.wait(timeout)


def start_sign_in(server: str, *, open_browser: Optional[Callable[[str], Any]] = None,
                  timeout: float = 300.0) -> Optional[SignIn]:
    """Begin a sign-in and return at once; `None` when the node has no OIDC."""
    config = auth_config(server)
    if not config or not config.get("authorization_endpoint"):
        return None
    return SignIn(server, config, open_browser=open_browser, timeout=timeout)


def sign_in(server: str, *, open_browser: Optional[Callable[[str], Any]] = None,
            timeout: float = 300.0) -> Optional[str]:
    """Authorization Code + PKCE against that server, WAITING for the result.

    The redirect comes back to a LOOPBACK listener, which is what a native app is
    supposed to use (RFC 8252) and what lets this work with no registered scheme
    and no embedded browser — an embedded webview is a phishing surface and
    several IdPs refuse it outright.

    **Blocks the caller** — never call it from Blender's UI thread: the panels go
    through `signin_ui.access_or_wait`, which runs a `SignIn` and polls it with a
    timer. This is the door for a headless run and for the suite.

    Returns the access token, or `None` when the node has no OIDC — in which case
    the caller joins without one, which is what that node expects.
    """
    running = start_sign_in(server, open_browser=open_browser, timeout=timeout)
    if running is None:
        return None
    running.wait(timeout + 5)
    if running.state != "done":
        raise HandoffError(running.error or "the sign-in did not complete")
    return running.token


def resolve(link: str, *, sign_in_with: Optional[Callable[[str], Optional[str]]] = None
            ) -> Dict[str, Optional[str]]:
    """A link in, `{server, room, token}` out — the three values the join needs.

    Kept apart from the join itself so the operator stays thin and the suite can
    measure this half without a room: `sign_in_with` is that seam.
    """
    where = parse(link)
    token = (sign_in_with or sign_in)(where["server"])
    return {"server": where["server"], "room": where["room"], "token": token}


# ── emit-only: hand this room to EMStudio ────────────────────────────────────
#
# The other direction — RECEIVING a link inside Blender — is deliberately absent
# and is a job of its own: Blender is not a URL-scheme handler, so it needs a
# registered launcher or the `ws_server` this addon already exposes. Offering
# half of it here as if it worked would be the worse half.

def open_targets(base_url: str, room_id: str, *, token: Optional[str] = None,
                 timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    """Ask the node how THIS room can be opened — `GET /v1/rooms/{id}/open`.

    The link is asked for and never assembled here: one grammar, on the server,
    measured against every consumer's copy. `None` when the node cannot be
    reached or refuses, so the caller can say which of the two happened.
    """
    import json
    import urllib.error
    import urllib.request

    url = (f"{base_url.rstrip('/')}/v1/rooms/"
           f"{urllib.parse.quote(str(room_id))}/open")
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    if token:
        # the token authenticates the QUESTION — a handoff for a room you have no
        # grant in is refused, because a listing is not a discovery service
        request.add_header("Authorization", f"Bearer {token}")
    try:
        from .trust import urlopen as _open
    except ImportError:          # loaded by path, outside the package (the suite)
        _open = urllib.request.urlopen
    try:
        with _open(request, timeout=timeout) as answer:
            return json.loads(answer.read() or b"{}")
    except (urllib.error.URLError, OSError, ValueError):
        return None


def emstudio_link(targets: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Which door of EMStudio this deployment actually offers.

    The browser one where a web build is hosted, the desktop scheme otherwise —
    the same rule the room browser follows, and the same reason: no door beats a
    door that fails after the click. Raises on a link carrying a credential,
    because forwarding one would end the contract's only property.
    """
    card = (targets.get("tools") or {}).get("emstudio") or {}
    browser = card.get("browser")
    scheme = card.get("scheme") or targets.get("scheme")
    link = browser or scheme
    if link:
        query = link.split("?", 1)[-1].lower() if "?" in link else ""
        carried = [k for k in FORBIDDEN
                   if f"{k}=" in query and (query.startswith(f"{k}=")
                                            or f"&{k}=" in query)]
        if carried:
            raise HandoffError(
                f"the node offered a link carrying {', '.join(carried)} — a "
                f"handoff names a place and never a permission. Refusing it.")
    return {"link": link, "kind": "browser" if browser else "scheme",
            "web": targets.get("web")}
