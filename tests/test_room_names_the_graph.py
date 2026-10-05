"""G1 · a room holds the whole study, and an operation names its graph (I-2).

MICRO-LO-STUDIO-IN-STANZA-NOMINA-IL-GRAFO (5 Oct 2026). EM Tools kept one
session per graph (2cc4404) and an operation never named its graph: a room
with two graphs, adopted whole, took every edit into its active graph and
every arrival went into the graph the session was bound to. Now the session
knows the graphs of the room's study (`room_graphs`) and which one is being
written (`writing_graph`): out, the envelope names it; in, the envelope's name
picks the graph. A room seeded from this scene (its one graph under the room's
id) names nothing, as before (D-A).
"""
import json

from test_room_per_graph import rs   # the same loader, without bpy


class _Wire:
    connected = True

    def __init__(self):
        self.sent = []

    def send(self, raw):
        self.sent.append(json.loads(raw))
        return True


def _session(room_graphs=(), writing=None):
    s = rs.RoomSession()
    s.client = _Wire()
    s.room_graphs = set(room_graphs)
    s.writing_graph = writing
    return s


def test_an_op_names_the_graph_of_the_study_it_is_for():
    s = _session({"tempio", "saggio"}, "saggio")
    s.send_op({"op": "update_field", "node_id": "US9", "field": "name", "value": "x"})
    frame = s.client.sent[-1]
    assert frame["graph_id"] == "saggio"
    assert "graph_id" not in frame["payload"]


def test_a_graph_the_room_does_not_hold_is_not_named():
    s = _session(set(), "tempio-locale")
    s.send_op({"op": "update_field", "node_id": "US1", "field": "name", "value": "x"})
    assert "graph_id" not in s.client.sent[-1]


def test_an_arrival_is_for_the_graph_its_envelope_names():
    s = _session({"tempio", "saggio"})
    assert rs.graph_of_message(s, {"type": "op", "graph_id": "saggio"}) == "saggio"
    assert rs.graph_of_message(s, {"type": "op"}) is None
    assert rs.graph_of_message(s, {"type": "op", "graph_id": "altrove"}) is None


def test_activating_a_graph_makes_it_the_one_written(monkeypatch):
    s = _session({"tempio", "saggio"})
    rs.bind("tempio", s, "http://node", "sanpietro")
    rs.bind("saggio", s, "http://node", "sanpietro")
    monkeypatch.setattr(rs.room, "set_room", lambda *a, **k: None)
    try:
        rs.activate("saggio")
        assert s.writing_graph == "saggio"
        rs.activate("tempio")
        assert s.writing_graph == "tempio"
    finally:
        rs.unbind_session(s)
