"""D1 · «Where it comes from»: the DTC of one asset as a card (pure half).

A derivation declared through `s3dgraphy.api.declare_derivation` — the one
gesture «Prepare for a use…», «Add version…» and EMStudio use — is read back
as the card says it: the step, its technique, who, when, the tool, the inputs
with the common signs of where their bytes are."""
import importlib.util
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
if _S3D.is_dir() and str(_S3D) not in sys.path:
    sys.path.insert(0, str(_S3D))

spec = importlib.util.spec_from_file_location("_em_provenance_card", _REPO / "provenance_card.py")
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)


def _graph():
    from s3dgraphy import api
    from s3dgraphy.graph import Graph
    g = Graph("G")
    photos = [api.add_resource(g, name=f"IMG_{i}.jpg", files=[{"url": f"/p/IMG_{i}.jpg"}])
              for i in range(6)]
    model = api.add_resource(g, name="ME_PODIO.glb", files=[{"url": "/m/ME_PODIO.glb"}])
    api.declare_derivation(g, model.node_id, [p.node_id for p in photos],
                           act_name="Photogrammetry", tool="Metashape 2.1",
                           technique="structure from motion",
                           author="0000-0002-1825-0097", at="2026-10-05T10:00:00Z")
    return g, model, photos


def test_the_card_says_the_step_who_when_the_tool_and_the_inputs():
    g, model, photos = _graph()
    states = {photos[0].node_id: "on_node", model.node_id: "both"}
    c = pc.card(g, model.node_id, states)
    assert c["name"] == "ME_PODIO.glb" and c["state"] == "both"
    (step,) = c["steps"]
    assert step["process"] == "Photogrammetry"
    assert step["technique"] == "structure from motion"
    assert step["tool"] == "Metashape 2.1"
    assert step["who"] == "0000-0002-1825-0097" and step["when"] == "2026-10-05"
    assert len(step["inputs"]) == pc.INPUTS_SHOWN and step["more"] == 2
    glyphs = {"on_node": "☁", "both": "◉"}
    said = pc.lines(c, lambda s: glyphs.get(s, ""))
    assert said[0] == "◉ ME_PODIO.glb"
    assert any(line.startswith("made by: Photogrammetry") for line in said)
    assert "by 0000-0002-1825-0097 · on 2026-10-05 · with Metashape 2.1" in said
    assert any(line.startswith("from: ☁ IMG_") for line in said)
    assert "from: +2 more" in said


def test_an_input_says_it_was_used_and_a_lone_file_says_it_has_no_step():
    g, model, photos = _graph()
    c = pc.card(g, photos[0].node_id)
    assert c["steps"] == [] and c["used_by"] == 1
    said = pc.lines(c)
    assert "no step of its chain is recorded" in said[1]
    assert said[-1] == "used by 1 later step(s)"


def test_no_resource_no_card():
    g, _m, _p = _graph()
    assert pc.card(g, "nope")["resource"] is None
    assert pc.lines(pc.card(g, ""))[0] == "no resource selected"


def test_a_document_links_its_resource():
    from s3dgraphy import api
    g, model, _p = _graph()
    from s3dgraphy.nodes.document_node import DocumentNode
    doc = DocumentNode("D1", "D.01")
    g.add_node(doc)
    g.add_edge("D1_has_linked_resource_m", "D1", model.node_id, "has_linked_resource")
    assert pc.resource_linked_to(g, "D1") == model.node_id
    assert pc.resource_linked_to(g, "none") == ""
