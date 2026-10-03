"""M2 · several rooms in one scene, one per graph (no network: the registry).

With «one room = one graph» (D-A) a scene holding Tempio Grande and the temple
beside it can be in two rooms. The rules measured here:

* a second join gets its OWN session — the first room stays joined;
* activating a graph points `SESSION` (where the edits go) and the REST address
  at that graph's room;
* activating a graph in no room leaves no room as the edit target;
* leaving one room forgets only its graph.
"""

import importlib.util
import pathlib
import sys
import types

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _load_room_session():
    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, _REPO / path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    parent = types.ModuleType("_m2_addon")
    parent.__path__ = [str(_REPO)]
    sys.modules["_m2_addon"] = parent
    bridge = types.ModuleType("_m2_addon.sync_bridge")
    bridge.__path__ = [str(_REPO / "sync_bridge")]
    sys.modules["_m2_addon.sync_bridge"] = bridge
    load("_m2_addon.sync_bridge.wire", "sync_bridge/wire.py")
    load("_m2_addon.sync_bridge.ws_client", "sync_bridge/ws_client.py")
    inner = types.ModuleType("_m2_addon.sync_manager")
    inner.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_m2_addon.sync_manager"] = inner
    room = load("_m2_addon.sync_manager.room", "sync_manager/room.py")
    rs = load("_m2_addon.sync_manager.room_session", "sync_manager/room_session.py")
    return room, rs


room, rs = _load_room_session()


class _Joined:
    """Stands for a connected WsClient."""
    connected = True

    def close(self):
        self.connected = False


def _join(session, room_id):
    session.client = _Joined()
    session.room_id = room_id
    return session


def test_two_rooms_two_graphs_edits_follow_the_active_graph():
    a = _join(rs.fresh_for_join(), "tempio-grande")
    rs.bind("g-tg", a, "https://em.localhost:8443", "tempio-grande", "tok-a")
    b = rs.fresh_for_join()
    assert b is not a, "the second join must not reuse the joined session"
    _join(b, "tempio-silvano")
    rs.bind("g-ts", b, "https://em.localhost:8443/", "tempio-silvano", "tok-b")
    assert a.joined and b.joined and rs.any_joined()

    rs.activate("g-tg")
    assert rs.SESSION is a
    assert room.room()["room_id"] == "tempio-grande"
    rs.activate("g-ts")
    assert rs.SESSION is b
    assert room.room()["room_id"] == "tempio-silvano"
    assert room._session["token"] == "tok-b"
    assert rs.where_of("g-ts") == {"base_url": "https://em.localhost:8443",
                                   "room_id": "tempio-silvano"}

    # a graph in no room: edits go to no room, the two rooms stay joined
    rs.activate("g-local")
    assert rs.SESSION is not a and rs.SESSION is not b
    assert not rs.SESSION.joined and rs.any_joined()

    # leaving Silvano's room forgets only Silvano's graph
    b.leave()
    assert rs.unbind_session(b) == ["g-ts"]
    assert rs.session_of("g-tg") is a and rs.session_of("g-ts") is None
    assert [g for g, _s in rs.sessions() if g] == ["g-tg"]


def test_a_joined_session_with_no_graph_is_never_orphaned():
    lonely = _join(rs.fresh_for_join(), "stanza-senza-grafo")
    assert lonely not in rs._by_graph.values()
    assert rs.activate("g-tg") is lonely, "still the edit target, not dropped"
    lonely.leave()
