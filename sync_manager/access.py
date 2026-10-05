"""The access to a node, renewed before it runs out — and said when it cannot be.

Measured on 4 Oct 2026: «Archive this .blend» failed about fifteen minutes after
entering the room with «could not reach the room: [Errno 32] Broken pipe». The
node had answered **401** (em-dev-server's log, four times between 13:49:09 and
13:49:34) while Blender was still sending the file, and the realm says why: the
`em-tools` client issues access tokens that live **900 s**
(`access.token.lifespan`, read from Keycloak's admin API). Blender kept only the
access token, so after fifteen minutes every call was refused — and a refusal
that arrives before a large body is sent reads, on this side, as a cut pipe.

Now the sign-in keeps what the realm gives beside the access token — the refresh
token, the token endpoint, the client — in memory, like the token itself
(`room.py`'s rule: never on disk). Every call to a node goes through `urlopen`
here, which:

* **before** the call, renews an access that expires within `SKEW` seconds (more
  for a call that carries a body: the node reads the header first, and a large
  body must not set off on a token about to die);
* **after** a 401 — or a cut pipe on an access that has expired — renews once and
  sends again, when the body can be sent again;
* when the realm will not renew (the sign-in session idled out: 30 minutes on
  the dev realm), raises `AccessExpired`, whose sentence says what happened:
  «the access to <node> has expired: sign in again», never «Broken pipe».

A token that came from somewhere else (pasted) has no refresh token: it is used
until it expires, and then the same sentence.

Calls carry the token they were given, often a copy taken minutes ago (a
per-graph room keeps one in `room_session._where`). The header is therefore
matched by LINEAGE: any token this session ever received for a node is replaced
by that node's newest one. Stale copies heal at the one place every call
crosses.

Standard library only (Blender's Python).
"""

from __future__ import annotations

import base64
import errno
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

try:
    from .room import RoomError
except ImportError:              # loaded by path, outside the package (the suite)
    class RoomError(RuntimeError):                       # type: ignore[no-redef]
        def __init__(self, message: str, *, status: Optional[int] = None):
            super().__init__(message)
            self.status = status

#: renew when the access has less than this left (seconds)
SKEW = 60
#: …and this much for a call that carries a body
SKEW_BODY = 180

#: base → {token, refresh_token, expires_at, token_endpoint, client_id}
_creds: Dict[str, Dict[str, Any]] = {}
#: every token this session received → the base it belongs to
_lineage: Dict[str, str] = {}
_lock = threading.RLock()

#: the last access that ran out, for the panel's «Sign in again» (base or "")
EXPIRED = {"base": "", "line": ""}


class AccessExpired(RoomError):
    """The access to a node ran out and could not be renewed: sign in again."""

    def __init__(self, base: str, why: str = ""):
        self.base = base
        sentence = (f"the access to {base or 'the node'} has expired: sign in "
                    f"again (EM ▸ Where you work ▸ Sign in again)")
        if why:
            sentence += f" — {why}"
        super().__init__(sentence, status=401)


def _norm(base: str) -> str:
    return (base or "").strip().rstrip("/")


def expiry_of(token: str) -> Optional[float]:
    """The `exp` claim of a JWT, read and not verified (the node verifies)."""
    try:
        part = str(token).split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        exp = claims.get("exp")
        return float(exp) if exp is not None else None
    except Exception:  # noqa: BLE001 — an opaque token: no expiry to read
        return None


def _life_of(token: str) -> Optional[float]:
    """How long the realm let this access live (`exp - iat`), when it says."""
    try:
        part = str(token).split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        return float(claims["exp"]) - float(claims["iat"])
    except Exception:  # noqa: BLE001
        return None


def remember(base: str, token: str, *, refresh_token: str = "",
             expires_in: Optional[float] = None, token_endpoint: str = "",
             client_id: str = "") -> None:
    """Keep what a sign-in returned, in memory, for `base`."""
    if not token:
        return
    base = _norm(base)
    expires_at = (time.time() + float(expires_in)) if expires_in else expiry_of(token)
    life = float(expires_in) if expires_in else _life_of(token)
    with _lock:
        old = _creds.get(base) or {}
        _creds[base] = {
            "token": token,
            "refresh_token": refresh_token or "",
            "expires_at": expires_at,
            "life": life,
            "token_endpoint": token_endpoint or old.get("token_endpoint") or "",
            "client_id": client_id or old.get("client_id") or "",
        }
        _lineage[token] = base
    if EXPIRED["base"] == base:
        EXPIRED.update({"base": "", "line": ""})


def adopt(base: str, token: Optional[str]) -> None:
    """A token that reached the session another way (pasted, a link): known by
    its base, so a refusal can be said as an expiry. No refresh token."""
    if not token:
        return
    base = _norm(base)
    with _lock:
        if token in _lineage:
            return
        _lineage[token] = base
        if base not in _creds:
            _creds[base] = {"token": token, "refresh_token": "",
                            "expires_at": expiry_of(token), "life": _life_of(token),
                            "token_endpoint": "", "client_id": ""}


def forget(base: Optional[str] = None) -> None:
    """Drop what is kept for `base` (every base when None)."""
    with _lock:
        for b in ([_norm(base)] if base else list(_creds)):
            _creds.pop(b, None)
            for t in [t for t, bb in _lineage.items() if bb == b]:
                _lineage.pop(t, None)


def base_of(token: Optional[str]) -> Optional[str]:
    return _lineage.get(token or "")


def _left(cred: Dict[str, Any]) -> Optional[float]:
    exp = cred.get("expires_at")
    return None if exp is None else exp - time.time()


def _post_form(url: str, fields: Dict[str, str], timeout: float = 30.0) -> Dict[str, Any]:
    try:
        from .trust import urlopen as _open
    except ImportError:          # loaded by path, outside the package (the suite)
        _open = urllib.request.urlopen
    request = urllib.request.Request(
        url, data=urllib.parse.urlencode(fields).encode(), method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with _open(request, timeout=timeout) as answer:
        return json.loads(answer.read() or b"{}")


def renew(base: str) -> str:
    """A new access for `base` through its refresh token → the new token.

    Raises `AccessExpired` with the reason when there is nothing to renew with,
    or the realm refuses (the sign-in session idled out)."""
    base = _norm(base)
    with _lock:
        cred = dict(_creds.get(base) or {})
    if not cred.get("refresh_token") or not cred.get("token_endpoint"):
        raise _expired(base, "this access cannot be renewed from here")
    try:
        payload = _post_form(cred["token_endpoint"], {
            "grant_type": "refresh_token",
            "refresh_token": cred["refresh_token"],
            "client_id": cred.get("client_id") or "",
            # NO client_secret: a public client
        })
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read() or b"{}").get("error_description") or ""
        except Exception:  # noqa: BLE001
            pass
        raise _expired(base, f"the realm would not renew it ({exc.code}"
                             + (f": {detail}" if detail else "") + ")") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise RoomError(f"could not reach the sign-in of {base} to renew the "
                        f"access: {getattr(exc, 'reason', exc)}") from exc
    token = str(payload.get("access_token") or "")
    if not token:
        raise _expired(base, "the realm returned no access token")
    remember(base, token,
             refresh_token=str(payload.get("refresh_token") or cred["refresh_token"]),
             expires_in=payload.get("expires_in"),
             token_endpoint=cred["token_endpoint"], client_id=cred.get("client_id", ""))
    _follow(base, token)
    print(f"[EM access] renewed the access to {base}")
    return token


def _expired(base: str, why: str) -> AccessExpired:
    exc = AccessExpired(base, why)
    EXPIRED.update({"base": base, "line": str(exc)})
    return exc


def _follow(base: str, token: str) -> None:
    """The REST session and the per-graph rooms carry the new token too."""
    try:
        from . import room as room_cfg
        if room_cfg._session.get("token") in _lineage and \
                _lineage.get(room_cfg._session.get("token")) == base:
            room_cfg._session["token"] = token
    except Exception:  # noqa: BLE001 — loaded by path
        pass
    try:
        from . import room_session
        for where in room_session._where.values():
            if where.get("token") and _lineage.get(where["token"]) == base:
                where["token"] = token
    except Exception:  # noqa: BLE001 — loaded by path, or no bpy
        pass


def fresh(token: Optional[str], *, margin: float = SKEW) -> Optional[str]:
    """The newest token of `token`'s lineage, renewed when it has less than
    `margin` seconds left. A token this session does not know is returned as is."""
    base = base_of(token)
    if not token or base is None:
        return token
    with _lock:
        cred = dict(_creds.get(base) or {})
    current = cred.get("token") or token
    left = _left(cred)
    life = cred.get("life")
    if life:
        # an access that lives less than the margin would be renewed at every
        # call (measured with a 60 s access: 195 renewals in one bring)
        margin = min(margin, life / 4)
    if left is not None and left < margin:
        if cred.get("refresh_token"):
            return renew(base)
        if left <= 0:
            raise _expired(base, "")
    return current


def _bearer(request) -> Optional[str]:
    value = request.get_header("Authorization") or ""
    return value[7:].strip() if value.lower().startswith("bearer ") else None


def _resendable(request) -> bool:
    data = request.data
    return data is None or isinstance(data, (bytes, bytearray))


def _cut(exc: BaseException) -> bool:
    """A pipe cut or a connection reset — what a 401 before a body looks like."""
    reason = getattr(exc, "reason", exc)
    code = getattr(reason, "errno", None)
    return code in (errno.EPIPE, errno.ECONNRESET) or isinstance(
        reason, (BrokenPipeError, ConnectionResetError))


def urlopen(request, timeout: Optional[float] = None):
    """`urllib.request.urlopen` for a call to a node — TLS through `trust`, the
    access renewed before it runs out and once more after a refusal."""
    try:
        from .trust import urlopen as _open
    except ImportError:          # loaded by path, outside the package (the suite)
        def _open(req, timeout=None):
            return urllib.request.urlopen(req, timeout=timeout)
    if isinstance(request, str):
        request = urllib.request.Request(request)
    token = _bearer(request)
    base = base_of(token)
    if token and base is not None:
        margin = SKEW_BODY if request.data is not None else SKEW
        current = fresh(token, margin=margin)
        if current and current != token:
            request.add_header("Authorization", f"Bearer {current}")
            token = current
    try:
        return _open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code != 401 or base is None:
            raise
    except (urllib.error.URLError, OSError) as exc:
        if base is None or not _cut(exc):
            raise
        with _lock:
            left = _left(_creds.get(base) or {})
        if left is None or left > 0:
            raise                # a cut, not an expiry: the caller says it
    # 401, or a cut on an access that ran out: renew once and send again
    token = renew(base)
    if not _resendable(request):
        # a streamed body cannot be read twice: the access is renewed, the
        # gesture is the person's to repeat
        raise RoomError(f"the access to {base} ran out during the call and has "
                        f"been renewed: press the button again", status=401)
    request.add_header("Authorization", f"Bearer {token}")
    try:
        return _open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise _expired(base, "the node refused the renewed access too") from exc
        raise
