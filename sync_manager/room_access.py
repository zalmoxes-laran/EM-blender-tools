"""C1 · who takes part in a room and who sees its study — the node's own doors.

«Create a collaborative room from this study…» asks three things, in the words
of EMStudio's «Room settings»: the **name**; **who takes part** — people by
ORCID with a role (viewer, editor, admin), and/or an **invitation link**
(viewer or editor, with an expiry and a number of uses); **who sees** — the
study's visibility (`restricted`, the default, or `public`) and its embargo, in
the study's header. «Room settings…» in the room's menu reads and changes the
same things, for whoever may assign them (`may_assign` on the node).

The doors (stratigraph-server `app/main.py`), and nothing else:

* `GET  /v1/rooms/{id}/members`, `PUT /v1/rooms/{id}/members/{orcid}` `{role}`;
* `POST /v1/rooms/{id}/invites` `{role, ttl_seconds, max_uses}` — the token is
  in the answer that made it and never again (the node keeps a sha256);
* `GET|PUT /v1/rooms/{id}/study-access` `{visibility, embargo}`.

The link a person receives is the room's own door (`GET /v1/rooms/{id}/open`)
with `join=<token>`: the same address EMStudio mints (`connection.ts`), so an
invited person lands in the same place whichever tool invited them.

Only the standard library: no bpy here; the dialogs are in `windows.py`.
"""

import json
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .rooms_list import _call, _headers, _url

#: the roles a manager hands out by hand (`MemberIn`) and by link (`InviteIn`)
MEMBER_ROLES = ("viewer", "editor", "admin")
LINK_ROLES = ("viewer", "editor")
VISIBILITIES = ("restricted", "public")

ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


def valid_orcid(orcid: str) -> bool:
    return bool(ORCID_RE.match(str(orcid or "").strip()))


def _room(room_id: str) -> str:
    return f"/v1/rooms/{urllib.parse.quote(str(room_id), safe='')}"


def _json(base: str, token: Optional[str], method: str, path: str,
          body: Optional[Dict[str, Any]] = None, timeout: float = 15.0) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(_url(base, path), data=data, method=method,
                                     headers=_headers(token, json_body=data is not None))
    return _call(request, timeout)


def members(base: str, token: Optional[str], room_id: str) -> Dict[str, Any]:
    """`{owner, members: [{orcid, role}], groups, your_role}` (admin or owner)."""
    return _json(base, token, "GET", f"{_room(room_id)}/members") or {}


def set_member(base: str, token: Optional[str], room_id: str, orcid: str,
               role: str) -> Dict[str, Any]:
    orcid = str(orcid or "").strip()
    if not valid_orcid(orcid):
        raise ValueError(f"«{orcid}» is not an ORCID (0000-0000-0000-0000)")
    if role not in MEMBER_ROLES:
        raise ValueError(f"unknown role {role!r}: {', '.join(MEMBER_ROLES)}")
    return _json(base, token, "PUT",
                 f"{_room(room_id)}/members/{urllib.parse.quote(orcid)}",
                 {"role": role}) or {}


def invite(base: str, token: Optional[str], room_id: str, role: str, *,
           days: int = 0, uses: int = 0) -> Dict[str, Any]:
    """A new invitation. `days`/`uses` 0 = no expiry / no limit (asked for, as
    the node wants: an endless link is a choice, not a default forgotten)."""
    if role not in LINK_ROLES:
        raise ValueError(f"a link offers viewer or editor, not {role!r}")
    body: Dict[str, Any] = {"role": role,
                            "ttl_seconds": int(days) * 86400 if days else 0,
                            "max_uses": int(uses) if uses else None}
    return _json(base, token, "POST", f"{_room(room_id)}/invites", body) or {}


def invites(base: str, token: Optional[str], room_id: str) -> List[Dict[str, Any]]:
    answer = _json(base, token, "GET", f"{_room(room_id)}/invites")
    return answer if isinstance(answer, list) else []


def link_for(door: str, invite_token: str) -> str:
    """The room's door with `join=<token>` — EMStudio's link, the same address."""
    if not door:
        return invite_token or ""
    parts = urllib.parse.urlsplit(door)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query = [(k, v) for k, v in query if k != "join"] + [("join", invite_token)]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def study_access(base: str, token: Optional[str], room_id: str) -> Dict[str, Any]:
    return _json(base, token, "GET", f"{_room(room_id)}/study-access") or {}


def set_study_access(base: str, token: Optional[str], room_id: str, *,
                     visibility: Optional[str] = None,
                     embargo: Optional[str] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {}
    if visibility is not None:
        if visibility not in VISIBILITIES:
            raise ValueError(f"visibility is restricted or public, not {visibility!r}")
        body["visibility"] = visibility
    if embargo is not None:
        body["embargo"] = str(embargo).strip()
    return _json(base, token, "PUT", f"{_room(room_id)}/study-access", body) or {}


def parse_people(text: str) -> List[Dict[str, str]]:
    """«0000-0002-1825-0097 editor, 0000-0001-5109-3700» → `[{orcid, role}]`.

    One person per comma or line; a role after the ORCID, `viewer` when none.
    What is not an ORCID raises with the person's own words."""
    out = []
    for chunk in re.split(r"[,;\n]+", text or ""):
        words = chunk.split()
        if not words:
            continue
        orcid = words[0].strip()
        role = (words[1].strip().lower() if len(words) > 1 else "viewer")
        if not valid_orcid(orcid):
            raise ValueError(f"«{orcid}» is not an ORCID (0000-0000-0000-0000)")
        if role not in MEMBER_ROLES:
            raise ValueError(f"«{role}» for {orcid}: a role is "
                             f"{', '.join(MEMBER_ROLES)}")
        out.append({"orcid": orcid, "role": role})
    return out
