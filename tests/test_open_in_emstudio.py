"""U7 · «Open in EMStudio» from the read-only paradata: which way it takes."""
import importlib.util
import pathlib

_P = pathlib.Path(__file__).resolve().parent.parent / "sync_manager" / "open_in_emstudio.py"
spec = importlib.util.spec_from_file_location("_open_in_emstudio", _P)
oe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oe)


def test_with_the_sidecar_emstudio_selects_the_unit():
    p = oe.plan(sidecar_running=True, room={"base_url": "https://n", "room_id": "r"}, unit_name="US12")
    assert p["way"] == "sidecar" and "selects US12" in p["sentence"]


def test_in_a_room_the_room_opens_and_the_unit_is_picked_there():
    p = oe.plan(sidecar_running=False, room={"base_url": "https://em.localhost:8443/em", "room_id": "templu"},
                unit_name="US12")
    assert p["way"] == "room"
    assert p["url"] == "stratigraph://open?server=https%3A%2F%2Fem.localhost%3A8443%2Fem&room=templu"
    assert "pick US12 there" in p["sentence"]


def test_otherwise_emstudio_starts_and_the_sentence_says_how_to_land():
    p = oe.plan(sidecar_running=False, room={"base_url": None, "room_id": None}, unit_name="US12",
                graph_path="/p/EM/x.em.json")
    assert p["way"] == "app" and "/p/EM/x.em.json" in p["sentence"] and "Sidecar" in p["sentence"]
