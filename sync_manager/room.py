"""The ROOM as seen from Blender: where the study lives, and where its bytes go.

Until now EMtools was only a **host**: it ran a socket and EMStudio connected to
it. A room (StratiGraph Server, run as a local FCN or as an institutional node) is the
other arrangement — a place that holds the graph AND the object store, that
several people reach at once, and that nobody's laptop has to stay awake for.

This module is what Blender needs to be a **client** of such a place:

* the address of the room and the token to speak to it — held **in memory only**;
* `put_asset`, which publishes bytes into the room's content-addressed store and
  returns the reference the graph will point at (STEP 2, DP-76).

**The token is never written to disk.** Same rule as the AI key: a token on disk
outlives the reason it was issued, gets copied into a backup, and is still valid
when the laptop is sold. It is pasted per session, and a Blender that quits
forgets it — which is the correct amount of memory for a credential.

Only the standard library: this runs inside Blender's Python, where a `pip
install` is somebody else's afternoon.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

#: The room this Blender is talking to, for the length of THIS session.
#: A module-level dict and not a Scene property on purpose: a Scene property is
#: saved inside the .blend, and the token must not be.
_session: Dict[str, Optional[str]] = {"base_url": None, "room_id": None,
                                      "token": None}

#: What we upload as, when the caller does not say. glTF-binary is the canonical
#: published form (what Heriverse/ATON read) — the .blend stays the workshop.
GLTF_MEDIA_TYPE = "model/gltf-binary"


class RoomError(RuntimeError):
    """The room refused, or could not be reached. Carries a sentence a user can
    act on rather than an HTTP number nobody reads.

    …and, when there was one, the **status** beside the sentence. Not for
    display: for the one caller that must tell refusals apart. A 403 on an asset
    is the embargo gate doing its job (the study is closed and this token is not
    an editor of it) while a 404 is a missing file — the first is a row to skip
    with an explanation, the second is something wrong. A consumer that could
    only read the sentence would have to match on English.
    """

    def __init__(self, message: str, *, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


# ── the session ──────────────────────────────────────────────────────────────

def set_room(base_url: Optional[str], room_id: Optional[str],
             token: Optional[str] = None) -> None:
    """Point this Blender at a room. `token` stays in memory, never on disk."""
    _session["base_url"] = (base_url or "").rstrip("/") or None
    _session["room_id"] = (room_id or "").strip() or None
    if token is not None:
        _session["token"] = token.strip() or None


def forget_token() -> None:
    """Drop the credential without leaving the room configured.

    Worth having as its own gesture: "I am done for today" should not require
    re-typing an address, and a token that outlives the session by accident is
    exactly what this module exists to prevent.
    """
    _session["token"] = None


def room() -> Dict[str, Optional[str]]:
    """The room configuration, WITHOUT the token.

    The token is deliberately absent from anything that can be printed, logged
    or sent in a `host_info`: a credential that travels in a status message is a
    credential that ends up in somebody's screenshot.
    """
    return {"base_url": _session["base_url"], "room_id": _session["room_id"],
            "has_token": bool(_session["token"])}


def is_configured() -> bool:
    return bool(_session["base_url"] and _session["room_id"])


def ws_url(path: str = "ws") -> str:
    """The room's WebSocket address (STEP 3 joins here).

    Derived from the same base as the REST calls rather than configured twice:
    two addresses that must agree are two addresses that will one day disagree.
    """
    if not is_configured():
        raise RoomError("no room configured: set the room address and id first")
    base = str(_session["base_url"])
    scheme = "wss" if base.startswith("https://") else "ws"
    rest = base.split("://", 1)[1] if "://" in base else base
    return f"{scheme}://{rest}/v1/rooms/{_session['room_id']}/{path}"


def _auth_headers() -> Dict[str, str]:
    token = _session["token"]
    if not token:
        raise RoomError("no token for this room: paste one for this session "
                        "(it is kept in memory only)")
    return {"Authorization": f"Bearer {token}"}


# ── the assets ───────────────────────────────────────────────────────────────

def content_id(data: bytes) -> str:
    """`sha256:<hex>` — the name the bytes will have in the store, computed HERE.

    Computed on this side as well as on the server's so the graph can record a
    checksum the uploader verified, not one it was told. The two must agree, and
    :func:`put_asset` says so out loud when they do not.
    """
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def put_asset(data: bytes, media_type: str = GLTF_MEDIA_TYPE,
              timeout: float = 60.0) -> Dict[str, Any]:
    """Publish bytes into the room's store; return `{ref, url, sha256, …}`.

    The store is content-addressed, so this is idempotent by construction:
    uploading the same model twice is one object, and the second answer says
    `created: false` rather than inventing a second asset.
    """
    if not is_configured():
        raise RoomError("no room configured: set the room address and id first")
    local = content_id(data)
    base, room_id = _session["base_url"], _session["room_id"]
    url = (f"{base}/v1/rooms/{urllib.parse.quote(str(room_id))}/asset"
           f"?media_type={urllib.parse.quote(media_type)}")
    request = urllib.request.Request(url, data=data, method="PUT",
                                     headers={"Content-Type": media_type,
                                              **_auth_headers()})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            info = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:                     # noqa: PERF203
        detail = exc.read().decode("utf-8", "replace")[:200]
        raise RoomError(f"the room refused the upload ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RoomError(f"could not reach the room at {base}: {exc.reason}") from exc

    if info.get("ref") != local:
        # the store names an object by its content: a disagreement means the
        # bytes that arrived are not the bytes we sent, and publishing a
        # checksum we cannot stand behind is worse than failing
        raise RoomError(f"the room stored a different digest ({info.get('ref')}) "
                        f"than the bytes we sent ({local})")
    info["url"] = asset_url(info["ref"])
    return info


def asset_url(ref: str) -> str:
    """The fetchable address of a stored asset — what the ResourceNode records."""
    if not is_configured():
        raise RoomError("no room configured: set the room address and id first")
    return (f"{_session['base_url']}/v1/rooms/"
            f"{urllib.parse.quote(str(_session['room_id']))}/asset/"
            f"{urllib.parse.quote(ref, safe=':')}")


def get_asset(ref: str, timeout: float = 60.0) -> Tuple[bytes, str]:
    """Fetch a stored asset; returns `(bytes, media_type)`, digest verified.

    Verified on arrival for the same reason the upload is: a content address you
    do not check is just a URL with a long name.
    """
    request = urllib.request.Request(asset_url(ref), method="GET",
                                     headers=_auth_headers())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
            media = response.headers.get("Content-Type") or "application/octet-stream"
    except urllib.error.HTTPError as exc:
        # The status travels with the sentence: 403 here is the EMBARGO GATE,
        # not a missing file, and the consumer (materialise.py) has to be able
        # to say so. Same words as before for 404 and the rest.
        if exc.code == 403:
            message = (f"the room will not serve {ref} to this token (403): "
                       f"an embargo, or a role below editor")
        elif exc.code == 401:
            message = f"the room did not accept the token (401) for {ref}"
        else:
            message = f"the room has no asset {ref} ({exc.code})"
        raise RoomError(message, status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise RoomError(f"could not reach the room: {exc.reason}") from exc
    if content_id(data) != ref:
        raise RoomError(f"the asset {ref} does not hash to its own reference — "
                        f"do not use these bytes")
    return data, media


# ── the .blend safety archive (opaque snapshots, on demand) ──────────────────
#
# A DIFFERENT thing from `put_asset` above, and the difference is the whole
# design. An asset is PUBLISHED: content-addressed, citable, served under the
# rights the graph declares — the glTF of record. A `.blend` snapshot is KEPT:
# opaque, in the room's backup namespace, readable only by the person who kept
# it, cited by nothing.
#
# What this is NOT: it is not versioning of the shared data (em.json and the
# glTF are already content-addressed — the version IS the hash and the history
# IS the DTC), and it is not a save hook. Somebody decides "keep this one".

#: What an opaque snapshot is stored as. Generic on purpose.
BLEND_MEDIA_TYPE = "application/x-blender"


def _room_path(path: str) -> str:
    if not is_configured():
        raise RoomError("no room configured: set the room address and id first")
    return (f"{_session['base_url']}/v1/rooms/"
            f"{urllib.parse.quote(str(_session['room_id']))}/{path}")


def _room_json(url: str, *, method: str = "GET", data: Optional[bytes] = None,
               content_type: Optional[str] = None,
               timeout: float = 120.0) -> Any:
    """One JSON call to the room, with the sentence a user can act on.

    The timeout is generous because a `.blend` is not a thumbnail: a snapshot of
    a reconstruction phase is hundreds of megabytes, and an upload that gave up
    at 60 s would be a backup that silently never happened.
    """
    headers = dict(_auth_headers())
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, method=method,
                                     headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RoomError(f"the room refused ({exc.code}): {detail}",
                        status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise RoomError(f"could not reach the room: {exc.reason}") from exc
    return json.loads(body.decode("utf-8")) if body else None


def put_blend_backup(data: bytes, *, label: str = "", filename: str = "",
                     timeout: float = 600.0) -> Dict[str, Any]:
    """Keep these bytes as an opaque snapshot; return the room's record.

    Idempotent by content, and the answer says so: archiving an unchanged
    `.blend` returns `created: false` and does **not** make a second snapshot.
    The digest is computed here as well, and a disagreement is an error rather
    than a shrug — a backup you cannot verify is a copy you hope exists.
    """
    local = hashlib.sha256(data).hexdigest()
    query = urllib.parse.urlencode({"label": label, "filename": filename})
    record = _room_json(f"{_room_path('blend-backup')}?{query}", method="PUT",
                        data=data, content_type=BLEND_MEDIA_TYPE,
                        timeout=timeout)
    if not isinstance(record, dict) or record.get("sha256") != local:
        raise RoomError(f"the room stored a different digest "
                        f"({(record or {}).get('sha256')}) than the bytes we "
                        f"sent ({local})")
    return record


def list_blend_backups(timeout: float = 30.0) -> List[Dict[str, Any]]:
    """The snapshots THIS identity kept in this room, newest first.

    Only your own — the room's register is per author. Being an editor is what
    let you archive; somebody else's work in progress is not yours to read.
    """
    answer = _room_json(_room_path("blend-backups"), timeout=timeout)
    return list(answer or [])


def get_blend_backup(sha256: str, timeout: float = 600.0) -> bytes:
    """The exact bytes back, digest verified on arrival."""
    wanted = str(sha256).strip().lower()
    url = _room_path(f"blend-backup/{urllib.parse.quote(wanted)}")
    request = urllib.request.Request(url, method="GET", headers=_auth_headers())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RoomError(f"no snapshot {wanted[:12]}… kept by you in this "
                            f"room", status=404) from exc
        raise RoomError(f"the room refused ({exc.code})", status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise RoomError(f"could not reach the room: {exc.reason}") from exc
    got = hashlib.sha256(data).hexdigest()
    if got != wanted:
        # The name IS the content: a mismatch means these are not the bytes that
        # were kept, and restoring them over anything would be the actual damage.
        raise RoomError(f"the restored bytes hash to {got[:12]}…, not "
                        f"{wanted[:12]}… — refusing to hand back a snapshot "
                        f"that does not verify")
    return data
