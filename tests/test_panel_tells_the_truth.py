"""V1 · the panel tells the truth after a restart: one source for the room.

Measured on 5 Oct 2026 on a reopened `Untitled.blend`: «Where you work» showed
the room and «✓ aligned», the EM Data Tree «joined as owner · 1 here», and
`room_session.SESSION.joined` was False — `activate()` for a graph of a file had
put a fresh session in `SESSION` while the room's stayed joined. Sync then said
«not downloaded» without why. Now every part reads `room_session.here`, a file
reopened in its room says «not connected» with Reconnect, and the sentence of
Sync always says why nothing came.
"""
import importlib.util
import pathlib
import sys
import types

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, _REPO / path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _pkg(name, path):
    p = types.ModuleType(name)
    p.__path__ = [str(_REPO / path)]
    sys.modules[name] = p


sys.path.insert(0, str(_REPO))
_pkg("_tv1", "")
_pkg("_tv1.sync_bridge", "sync_bridge")
_load("_tv1.sync_bridge.wire", "sync_bridge/wire.py")
_load("_tv1.sync_bridge.ws_client", "sync_bridge/ws_client.py")
_pkg("_tv1.sync_manager", "sync_manager")
_load("_tv1.sync_manager.room", "sync_manager/room.py")
rs = _load("_tv1.sync_manager.room_session", "sync_manager/room_session.py")
where = _load("_tv1.sync_manager.where", "sync_manager/where.py")


class _Client:
    connected = True

    def close(self):
        self.connected = False


def _joined(room_id, base="https://node/em"):
    s = rs.RoomSession()
    s.client, s.seated, s.room_id, s.base_url = _Client(), True, room_id, base
    s.role, s.members = "owner", [{"id": "me"}]
    return s


def setup_function(_f):
    rs._by_graph.clear()
    rs._where.clear()
    rs.SESSION = rs.RoomSession()


def test_a_graph_of_a_file_made_active_does_not_hide_the_room():
    room = _joined("templu")
    rs.bind("templu", room, "https://node/em", "templu")
    rs.SESSION = room
    rs.activate("GT16")                     # a graph of a file
    assert rs.SESSION is not room and not rs.SESSION.joined   # the old defect's cause
    # …but the scene's session is still the room's, by the active graph or by
    # the room the file saved, and the tree's lookup finds the same one
    assert rs.here("GT16", "https://node/em", "templu") is room
    assert rs.session_of_room(None, "templu") is room
    assert rs.here("templu", "", "") is room


def test_no_session_anywhere_is_the_empty_one():
    assert rs.here("x", "https://node/em", "templu") is rs.SESSION
    assert not rs.here("x", "https://node/em", "templu").joined


def test_a_room_on_another_node_is_not_this_one():
    room = _joined("templu", base="https://other/em")
    rs.bind("templu", room, "https://other/em", "templu")
    assert rs.session_of_room("https://node/em", "templu") is None


def test_reopened_in_its_room_says_not_connected_with_reconnect():
    z = where.zones({"place": where.PLACE_ROOM, "not_connected": True,
                     "room_id": "templu-mare-prova-claude",
                     "node": "https://em.localhost:8443/em", "user": "dev"})
    assert "not connected" in z["place"][1] and not z["healthy"]
    assert z["message"]["op"] == "em.room_reconnect"
    assert z["message"]["op_text"] == "Reconnect"
    assert "aligned" not in z["log"][1]           # nothing claims an alignment
    assert "no role said" not in z["who"][1]


def test_connected_room_reads_role_and_people_of_the_same_session():
    z = where.zones({"place": where.PLACE_ROOM, "room_id": "t", "members": 1,
                     "role": "owner", "author": "dev", "node": "https://n/em"})
    assert "1 present" in z["place"][1] and "owner" in z["who"][1]
