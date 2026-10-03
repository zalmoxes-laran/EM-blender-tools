"""P3 · ONE function that puts a file into a room's asset store.

`upload_asset(node, room, path, sha256, media_type, token, progress_cb)` — and
nothing else in the add-on talks to the upload doors. When the transport
changes, it changes here.

The order is the node's own (stratigraph-server `app/main.py`, U1, commit
1a1bbf8), and it is the order EMStudio follows too:

1. **`HEAD {node}/v1/rooms/{room}/asset/sha256:<hex>`** — 200: the room already
   has these bytes, nothing is sent. This is what makes a second «Bring into a
   room» upload nothing.
2. a file up to `SINGLE_SHOT_MAX` goes in one **streamed `PUT
   …/asset?media_type=…&expected_sha256=…`**: the body is the FILE OBJECT with
   its `Content-Length`, read by `http.client` block by block — never `read()`
   into memory. The node checks the digest and answers 422 if the bytes that
   arrived are not the ones declared;
3. a bigger file goes through the **resumable door**: `POST …/uploads {size,
   sha256, media_type}` → `upload_id`; `PATCH …/uploads/{id}` with
   `Upload-Offset` and a piece of `PIECE` bytes, streamed from the file at that
   offset; after a cut, `HEAD …/uploads/{id}` says how much the node HAS and the
   next piece starts there (a 409 says the same thing in its body). The PATCH
   that brings the offset to the size answers `complete: true` with the asset.

stdlib only (Blender's Python), no `bpy`. TLS verified (the default context;
`SSL_CERT_FILE` for a node with a private CA). The token is a parameter, never
stored here.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Optional, Tuple

from .room import RoomError

#: Up to here one streamed PUT; beyond, the resumable door. 64 MiB: a model or
#: an orthophoto goes in one request, a scan of several GB in pieces that
#: survive a dropped Wi-Fi.
SINGLE_SHOT_MAX = 64 * 1024 * 1024
#: One PATCH. Streamed from disk, so this is the unit of RETRY, not of memory.
PIECE = 16 * 1024 * 1024
#: How many times a cut piece is resumed before giving up.
RETRIES = 5
_BLOCK = 1024 * 1024

ProgressCb = Optional[Callable[[int, int], None]]


def sha256_of_file(path: str) -> str:
    """The bare hex digest of a file, read in blocks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(_BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


def _hex(sha256: str) -> str:
    text = str(sha256 or "").strip().lower()
    return text[len("sha256:"):] if text.startswith("sha256:") else text


def _room_url(node: str, room: str, tail: str) -> str:
    base = (node or "").strip().rstrip("/")
    if "://" not in base:
        base = "http://" + base
    return f"{base}/v1/rooms/{urllib.parse.quote(str(room), safe='')}/{tail}"


def asset_url(node: str, room: str, sha256: str) -> str:
    """The fetchable address of a stored asset — what the resource records."""
    return _room_url(node, room, f"asset/sha256:{_hex(sha256)}")


def _headers(token: Optional[str], **extra: str) -> Dict[str, str]:
    headers = dict(extra)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def has_asset(node: str, room: str, sha256: str, token: Optional[str], *,
              timeout: float = 30.0) -> bool:
    """`HEAD …/asset/sha256:<hex>` → True on 200, False on 404.

    Anything else (401, 403, the network) is RAISED: «the room does not have
    it» and «the room would not say» are different answers, and treating the
    second as the first would re-send gigabytes for a refused token.
    """
    request = urllib.request.Request(asset_url(node, room, sha256), method="HEAD",
                                     headers=_headers(token))
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            return True
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise RoomError(f"the room would not say whether it has "
                        f"sha256:{_hex(sha256)[:12]}… ({exc.code})",
                        status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise RoomError(f"could not reach the node: {exc.reason}") from exc


def asset_head(node: str, room: str, sha256: str, token: Optional[str], *,
               timeout: float = 30.0) -> Tuple[bool, Optional[str]]:
    """F1 · the same HEAD as `has_asset`, read whole: `(present, home)`.

    `home` is the room the bytes LIVE in (`X-EM-Home-Room`): a file the node
    holds at home in another room is not this room's, and «Bring into a room»
    proposes «Move here» for it instead of calling it «already in the room».
    Errors are raised as in `has_asset`."""
    request = urllib.request.Request(asset_url(node, room, sha256), method="HEAD",
                                     headers=_headers(token))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            return True, (answer.headers.get("X-EM-Home-Room") or None)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False, None
        raise RoomError(f"the room would not say whether it has "
                        f"sha256:{_hex(sha256)[:12]}… ({exc.code})",
                        status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise RoomError(f"could not reach the node: {exc.reason}") from exc


def asset_home_view(node: str, room: str, sha256: str, token: Optional[str], *,
                    timeout: float = 30.0) -> Dict[str, Any]:
    """F1 · `GET …/asset-home/sha256:<hex>`: where the file lives, which rooms'
    graphs cite it, and whether this caller may move it into `room`. A refusal
    is returned as `{"error": "<status> <detail>"}`, not raised: it is one
    row of the confirmation, not the end of the gesture."""
    url = _room_url(node, room, f"asset-home/sha256:{_hex(sha256)}")
    request = urllib.request.Request(url, headers=_headers(token))
    try:
        return _json_call(request, timeout)[0]
    except urllib.error.HTTPError as exc:
        return {"error": f"{exc.code} {_detail(exc)}"}
    except urllib.error.URLError as exc:
        return {"error": f"could not reach the node: {exc.reason}"}


def move_asset_home(node: str, room: str, sha256: str, from_room: Optional[str],
                    token: Optional[str], *, timeout: float = 30.0) -> Dict[str, Any]:
    """F1 · «Move here», after the person said yes: `room` becomes the file's
    ONLY home. No byte travels. `from_room` is the home the confirmation
    showed: the node refuses (409) if it changed since. Raises `RoomError`."""
    url = _room_url(node, room, f"asset-home/sha256:{_hex(sha256)}")
    body = json.dumps({"from_room": from_room, "confirm": True}).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers=_headers(token, **{"Content-Type": "application/json"}))
    try:
        return _json_call(request, timeout)[0]
    except urllib.error.HTTPError as exc:
        raise RoomError(f"could not move sha256:{_hex(sha256)[:12]}… here: "
                        f"{_detail(exc)}", status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise RoomError(f"could not reach the node: {exc.reason}") from exc


class _Window:
    """A file read from `start` for `length` bytes — a streamed request body.

    `http.client` sends any object with `read()` block by block, so the piece
    is never in memory as a whole. Progress is counted as it is read.
    """

    def __init__(self, path: str, start: int, length: int,
                 on_read: Optional[Callable[[int], None]] = None):
        self._handle = open(path, "rb")
        self._handle.seek(start)
        self._left = length
        self._on_read = on_read

    def read(self, size: int = -1) -> bytes:
        if self._left <= 0:
            return b""
        size = self._left if size is None or size < 0 else min(size, self._left)
        data = self._handle.read(min(size, _BLOCK))
        self._left -= len(data)
        if self._on_read and data:
            self._on_read(len(data))
        return data

    def close(self) -> None:
        self._handle.close()


def _json_call(request: urllib.request.Request, timeout: float):
    with urllib.request.urlopen(request, timeout=timeout) as answer:
        body = answer.read()
        return json.loads(body.decode("utf-8")) if body else {}, answer.headers


def _detail(exc: urllib.error.HTTPError) -> str:
    try:
        return str(json.loads(exc.read().decode("utf-8")).get("detail") or "")
    except Exception:  # noqa: BLE001
        return ""


def _single_shot(node, room, path, hexd, size, media_type, token, progress_cb,
                 timeout) -> Dict[str, Any]:
    query = urllib.parse.urlencode({"media_type": media_type,
                                    "expected_sha256": hexd})
    sent = [0]

    def counted(n):
        sent[0] += n
        if progress_cb:
            progress_cb(sent[0], size)

    body = _Window(path, 0, size, counted)
    request = urllib.request.Request(
        _room_url(node, room, f"asset?{query}"), data=body, method="PUT",
        headers=_headers(token, **{"Content-Type": media_type,
                                   "Content-Length": str(size)}))
    try:
        info, _h = _json_call(request, timeout)
    except urllib.error.HTTPError as exc:
        raise RoomError(f"the room refused the upload ({exc.code}): "
                        f"{_detail(exc)}", status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise RoomError(f"could not reach the node: {exc.reason}") from exc
    finally:
        body.close()
    return info


def _offset_now(url: str, token, timeout) -> int:
    request = urllib.request.Request(url, method="HEAD", headers=_headers(token))
    with urllib.request.urlopen(request, timeout=timeout) as answer:
        return int(answer.headers.get("Upload-Offset") or 0)


def _resumable(node, room, path, hexd, size, media_type, token, progress_cb,
               timeout, piece) -> Dict[str, Any]:
    start = urllib.request.Request(
        _room_url(node, room, "uploads"), method="POST",
        data=json.dumps({"size": size, "sha256": hexd,
                         "media_type": media_type}).encode("utf-8"),
        headers=_headers(token, **{"Content-Type": "application/json"}))
    try:
        session, _h = _json_call(start, timeout)
    except urllib.error.HTTPError as exc:
        raise RoomError(f"the room refused to open an upload ({exc.code}): "
                        f"{_detail(exc)}", status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise RoomError(f"could not reach the node: {exc.reason}") from exc
    url = _room_url(node, room, f"uploads/{session['upload_id']}")
    offset = int(session.get("offset") or 0)
    failures = 0
    while True:
        length = min(piece, size - offset)
        read_so_far = [0]

        def counted(n, base=offset):
            read_so_far[0] += n
            progress_cb(base + read_so_far[0], size)

        body = _Window(path, offset, length, counted if progress_cb else None)
        request = urllib.request.Request(
            url, data=body, method="PATCH",
            headers=_headers(token, **{"Upload-Offset": str(offset),
                                       "Content-Type": "application/offset+octet-stream",
                                       "Content-Length": str(length)}))
        try:
            answer, headers = _json_call(request, timeout)
        except urllib.error.HTTPError as exc:
            if exc.code == 409:
                # the node says where it IS: resume from there, no guessing
                offset = int(exc.headers.get("Upload-Offset") or offset)
                failures += 1
                if failures > RETRIES:
                    raise RoomError("the upload kept disagreeing about its "
                                    "offset: given up", status=409) from exc
                continue
            raise RoomError(f"the room refused a piece ({exc.code}): "
                            f"{_detail(exc)}", status=exc.code) from exc
        except (urllib.error.URLError, OSError) as exc:
            # A CUT. The bytes that arrived are on the node: ask how many.
            failures += 1
            if failures > RETRIES:
                raise RoomError(f"the upload was cut {failures} times: given up "
                                f"at {offset} of {size} bytes ({exc})") from exc
            try:
                offset = _offset_now(url, token, timeout)
            except Exception as again:  # noqa: BLE001
                raise RoomError(f"the upload was cut and the node does not "
                                f"answer: {again}") from exc
            continue
        finally:
            body.close()
        failures = 0
        if answer.get("complete"):
            return dict(answer.get("asset") or {})
        offset = int(answer.get("offset") or headers.get("Upload-Offset") or offset)


def upload_asset(node: str, room: str, path: str, sha256: Optional[str],
                 media_type: str, token: Optional[str],
                 progress_cb: ProgressCb = None, *,
                 timeout: float = 600.0,
                 single_shot_max: int = SINGLE_SHOT_MAX,
                 piece: int = PIECE) -> Dict[str, Any]:
    """Put the file at `path` into `room`'s store on `node`.

    → `{ref, sha256, size, media_type, created, author, url, already}`.
    `already: True` means the HEAD said the room has it and nothing was sent.
    `sha256` may be None (it is computed here); when given it is checked by
    the node, so a file changed since the inventory read it is refused (422)
    rather than stored under the wrong name.
    """
    if not os.path.isfile(path):
        raise RoomError(f"not a file: {path}")
    hexd = _hex(sha256) if sha256 else sha256_of_file(path)
    size = os.path.getsize(path)
    media_type = media_type or "application/octet-stream"
    if has_asset(node, room, hexd, token):
        if progress_cb:
            progress_cb(size, size)
        return {"ref": f"sha256:{hexd}", "sha256": hexd, "size": size,
                "media_type": media_type, "created": False, "author": None,
                "url": asset_url(node, room, hexd), "already": True}
    if size <= single_shot_max:
        info = _single_shot(node, room, path, hexd, size, media_type, token,
                            progress_cb, timeout)
    else:
        info = _resumable(node, room, path, hexd, size, media_type, token,
                          progress_cb, timeout, piece)
    got = _hex(info.get("ref") or info.get("sha256") or "")
    if got != hexd:
        raise RoomError(f"the room stored sha256:{got[:12]}…, not the "
                        f"sha256:{hexd[:12]}… we sent")
    info["url"] = asset_url(node, room, hexd)
    info["already"] = False
    return info
