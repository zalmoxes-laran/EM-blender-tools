"""U7 / E4 · «Edit in EMStudio» from the read-only paradata: which way lands on
the unit — the Sidecar, or the room's link with `&node=` — or grey."""
import importlib.util
import pathlib
import urllib.parse

_P = pathlib.Path(__file__).resolve().parent.parent / "sync_manager" / "open_in_emstudio.py"
spec = importlib.util.spec_from_file_location("_open_in_emstudio", _P)
oe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oe)

ROOM = {"base_url": "https://em.localhost:8443/em", "room_id": "templu"}
NONE = {"base_url": None, "room_id": None}


def test_with_emstudio_on_the_sidecar_it_selects_the_unit():
    p = oe.plan(sidecar_clients=1, room=ROOM, unit_name="US12", node_id="n-12")
    assert p["way"] == "sidecar" and "selects US12" in p["sentence"]


def test_a_sidecar_with_nobody_connected_does_not_count():
    assert oe.plan(sidecar_clients=0, room=NONE, unit_name="US12", node_id="n-12")["way"] == "off"


def test_in_a_room_the_link_names_the_node():
    p = oe.plan(sidecar_clients=0, room=ROOM, unit_name="US12", node_id="n-12")
    assert p["way"] == "room"
    assert p["url"] == ("stratigraph://open?server=https%3A%2F%2Fem.localhost%3A8443%2Fem"
                        "&room=templu&node=n-12")
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(p["url"]).query)
    assert q == {"server": ["https://em.localhost:8443/em"], "room": ["templu"], "node": ["n-12"]}
    assert "on US12" in p["sentence"]


def test_otherwise_grey_and_the_sentence_says_how_to_turn_it_on():
    p = oe.plan(sidecar_clients=0, room=NONE, unit_name="US12", node_id="n-12")
    assert p["way"] == "off" and p["url"] == ""
    assert "Sidecar" in p["sentence"] and "room" in p["sentence"]
    assert p["sentence"] == oe.OFF
