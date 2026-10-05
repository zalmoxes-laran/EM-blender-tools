"""Z1/C1/J1 · the pure halves: the four zones of «Where you work», who takes
part in a room, and the question at the entry with a file that is not empty.

`where.zones`, `room_access.parse_people`/`link_for` and `entry.choices` need no
Blender; the panel that draws them is measured by
`tests/blender_inventory_where_you_work.py`.
"""
import importlib.util
import pathlib
import sys
import types

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
if _S3D.is_dir():
    sys.path.insert(0, str(_S3D))


def _load(name):
    pkg = types.ModuleType("_wyw")
    pkg.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_wyw"] = pkg
    spec = importlib.util.spec_from_file_location(f"_wyw.{name}",
                                                  _REPO / "sync_manager" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


sys.path.insert(0, str(_REPO))
where = _load("where")
_load("room")
_load("rooms_list")
room_access = _load("room_access")
entry = _load("entry")


def test_on_this_computer_says_the_file_and_that_no_node_is_needed():
    z = where.zones({"place": "here", "study_file": "Templu Mare.em.json"})
    assert z["place"][1] == "□ On this computer · Templu Mare.em.json"
    assert z["who"][1] == "not signed in to a node — none needed here"
    assert z["message"]["text"] == ""
    assert z["log"][1] == "no refused edit"
    assert z["healthy"]


def test_the_red_alarm_of_the_reopened_file_is_a_sentence_with_reconnect():
    z = where.zones({"place": "here", "declared": "emstudio"})
    msg = z["message"]
    assert msg["text"] == "Last time this file worked with EMStudio"
    assert (msg["op"], msg["op_text"], msg["op_props"]) == ("em.set_mode", "Reconnect",
                                                            {"mode": "sidecar"})
    assert not msg["alert"] and z["healthy"]
    room = where.zones({"place": "here", "declared": "room", "declared_room": "scavo"})
    assert room["message"]["text"] == "Last time this file worked in the room scavo"
    assert room["message"]["op"] == "em.room_reconnect"


def test_with_emstudio_counts_the_clients_and_says_the_document():
    z = where.zones({"place": "emstudio", "clients": 1, "same_document": True})
    assert z["place"][1] == "⇄ With EMStudio · 1 client · same document ✓"
    other = where.zones({"place": "emstudio", "clients": 2, "same_document": False})
    assert "≠ another document" in other["place"][1] and not other["healthy"]
    assert other["message"]["text"].startswith("≠ EMStudio has another document open")


def test_in_a_room_the_title_the_node_who_and_the_log():
    s = {"place": "room", "room_title": "Templu Mare", "room_id": "templu-mare",
         "node": "https://em.localhost:8443/em", "members": 1, "author": "dev",
         "role": "owner", "sent": 12, "answered": 12}
    z = where.zones(s)
    assert z["place"][1] == "▣ Templu Mare · em.localhost:8443/em · 1 present"
    assert z["who"][1] == "dev ✓ · ★ owner"
    assert z["log"][1] == "✓ aligned · 12 sent, 12 answered"
    waiting = where.zones({**s, "waiting": 3})
    assert waiting["log"][1] == "⋯ 3 edits waiting to be sent"
    viewer = where.zones({**s, "role": "viewer", "can_write": False})
    assert viewer["message"]["text"] == "⊘ your role does not write"
    off = where.zones({**s, "offline": True, "waiting": 2})
    assert off["place"][1].endswith("· offline") and not off["healthy"]
    assert off["message"]["op"] == "em.room_reconnect"


def test_the_waiting_browser_and_the_expired_access_come_first():
    z = where.zones({"place": "here", "signin_waiting": True, "declared": "emstudio"})
    assert z["message"]["text"] == "Waiting for the browser…"
    assert z["message"]["op"] == "em.sign_in_cancel"
    z = where.zones({"place": "room", "expired": "https://em.localhost:8443/em"})
    assert z["message"]["text"] == "The access to em.localhost:8443/em has expired"
    assert z["message"]["op_text"] == "Sign in again"


def test_a_node_is_its_host_and_port_not_its_service_name():
    assert where.host_of("http://localhost:8000") == "localhost:8000"
    assert where.host_of("https://em.localhost:8443/em/") == "em.localhost:8443/em"
    assert where.host_of("") == ""


def test_people_by_orcid_with_a_role_and_viewer_when_none():
    got = room_access.parse_people("0000-0002-1825-0097 editor, 0000-0001-5109-3700")
    assert got == [{"orcid": "0000-0002-1825-0097", "role": "editor"},
                   {"orcid": "0000-0001-5109-3700", "role": "viewer"}]
    assert room_access.parse_people("") == []
    with pytest.raises(ValueError, match="not an ORCID"):
        room_access.parse_people("dev editor")
    with pytest.raises(ValueError, match="a role is"):
        room_access.parse_people("0000-0002-1825-0097 owner")


def test_the_invitation_link_is_the_rooms_door_with_join():
    door = "https://em.localhost:8443/em/open?server=x&room=scavo"
    link = room_access.link_for(door, "TOK")
    assert link.endswith("&join=TOK") and "room=scavo" in link
    assert room_access.link_for("", "TOK") == "TOK"


def test_the_entry_asks_only_when_the_file_holds_a_study():
    assert entry.is_empty_state([], 0)
    assert not entry.is_empty_state(["Templu Mare"], 0)
    assert not entry.is_empty_state([], 3)


def test_the_package_comes_first_and_recommended_when_the_room_has_one():
    with_pkg = entry.choices(True)
    assert [c["id"] for c in with_pkg] == ["PACKAGE", "NEW", "MERGE"]
    assert with_pkg[0]["recommended"] and with_pkg[0]["enabled"]
    without = entry.choices(False)
    assert [c["id"] for c in without][:2] == ["NEW", "MERGE"]
    assert not next(c for c in without if c["id"] == "PACKAGE")["enabled"]
