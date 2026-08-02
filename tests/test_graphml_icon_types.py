"""C1 — typing the icon nodes of a pre-1.4 EM GraphML.

Old EM graphs draw extractors, combiners and continuity nodes as `y:SVGNode`:
an icon, no shape, all filled with yEd's default `#CCCCFF`. The s3Dgraphy
importer recognises them only by the label convention (`D.` / `C.`), so an
author who named an extractor after the unit it reads from — `SF04.2` — got an
untyped node and a fistful of degraded edges.

The type is in the file: it is the SVG resource the node points at. What that
resource *means* is learned from the file's own usage. These tests pin the two
halves of that: the learning must be strict enough never to invent a meaning,
and the annotation must touch only the nodes that actually need it.
"""

import importlib.util
import pathlib
import xml.etree.ElementTree as ET

# ``operators/__init__.py`` pulls in the whole addon (and thus bpy), so the
# package path is unusable outside Blender. The module under test imports
# nothing but ElementTree on purpose — load it straight from its file.
_spec = importlib.util.spec_from_file_location(
    "_emtools_test_graphml_icon_types",
    pathlib.Path(__file__).resolve().parent.parent
    / "operators" / "graphml_icon_types.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
annotate_icon_node_types = _mod.annotate_icon_node_types
learn_svg_resource_classes = _mod.learn_svg_resource_classes

G = "http://graphml.graphdrawing.org/xmlns"
Y = "http://www.yworks.com/xml/graphml"

CONTINUITY_SVG = '<svg sodipodi:docname="continuity.svg"><path/></svg>'
ANONYMOUS_SVG = '<svg sodipodi:docname="New document 13"><path/></svg>'


def build(resources, nodes):
    """Assemble a minimal yEd-shaped GraphML.

    ``resources``: {refid: svg text}. ``nodes``: list of
    ``(label, refid, description, is_group)``.
    """
    root = ET.Element(f"{{{G}}}graphml")
    key = ET.SubElement(root, f"{{{G}}}key")
    key.set("for", "node")
    key.set("attr.name", "description")
    key.set("id", "d5")
    graph = ET.SubElement(root, f"{{{G}}}graph")
    for label, refid, desc, is_group in nodes:
        node = ET.SubElement(graph, f"{{{G}}}node")
        node.set("id", f"n_{label or 'anon'}_{refid}")
        if desc is not None:
            data = ET.SubElement(node, f"{{{G}}}data", {"key": "d5"})
            data.text = desc
        gfx = ET.SubElement(node, f"{{{G}}}data", {"key": "d6"})
        if is_group:
            gfx = ET.SubElement(gfx, f"{{{Y}}}ProxyAutoBoundsNode")
        svg = ET.SubElement(gfx, f"{{{Y}}}SVGNode")
        lbl = ET.SubElement(svg, f"{{{Y}}}NodeLabel")
        lbl.text = label
        model = ET.SubElement(svg, f"{{{Y}}}SVGModel")
        ET.SubElement(model, f"{{{Y}}}SVGContent", {"refid": refid})
        if is_group:
            ET.SubElement(node, f"{{{G}}}graph")
    res_data = ET.SubElement(root, f"{{{G}}}data", {"key": "d7"})
    holder = ET.SubElement(res_data, f"{{{Y}}}Resources")
    for rid, body in resources.items():
        r = ET.SubElement(holder, f"{{{Y}}}Resource", {"id": rid})
        r.text = body
    return root


def descriptions(root):
    out = {}
    for node in root.iter(f"{{{G}}}node"):
        label = node.find(f".//{{{Y}}}NodeLabel")
        data = node.find(f'{{{G}}}data[@key="d5"]')
        out[(label.text or "") if label is not None else ""] = (
            data.text if data is not None else None)
    return out


# ── learning what a resource means ────────────────────────────────────────────

def test_resource_that_names_itself_needs_no_vote():
    root = build({"1": CONTINUITY_SVG},
                 [("BR1", "1", None, False)])
    assert learn_svg_resource_classes(root) == {"1": ("ContinuityNode", "docname")}


def test_majority_of_labelled_users_identifies_the_icon():
    """102 nodes called `D.something` share one icon → that icon is the
    extractor icon, whatever the stragglers are called."""
    nodes = [(f"D.0{i}", "2", None, False) for i in range(1, 6)]
    nodes.append(("SF04.2", "2", None, False))
    learned = learn_svg_resource_classes(build({"2": ANONYMOUS_SVG}, nodes))
    assert learned == {"2": ("ExtractorNode", "vote")}


def test_too_few_voters_is_a_coincidence_not_a_convention():
    nodes = [("D.01", "2", None, False), ("SF04.2", "2", None, False)]
    assert learn_svg_resource_classes(build({"2": ANONYMOUS_SVG}, nodes)) == {}


def test_disagreement_identifies_nothing():
    """An icon used for both extractors and combiners means neither."""
    nodes = [("D.01", "2", None, False), ("D.02", "2", None, False),
             ("C.01", "2", None, False), ("C.02", "2", None, False)]
    assert learn_svg_resource_classes(build({"2": ANONYMOUS_SVG}, nodes)) == {}


def test_docname_beats_the_vote():
    nodes = [(f"D.0{i}", "1", None, False) for i in range(1, 6)]
    learned = learn_svg_resource_classes(build({"1": CONTINUITY_SVG}, nodes))
    assert learned["1"] == ("ContinuityNode", "docname")


# ── annotating only what needs it ─────────────────────────────────────────────

def test_the_straggler_is_typed_and_the_others_left_alone():
    nodes = [(f"D.0{i}", "2", "prosa", False) for i in range(1, 6)]
    nodes.append(("SF04.2", "2", "colore dell'intonaco", False))
    root = build({"2": ANONYMOUS_SVG}, nodes)
    annotated, skipped = annotate_icon_node_types(root)
    assert (annotated, skipped) == (1, 0)
    d = descriptions(root)
    assert d["SF04.2"] == "colore dell'intonaco _s3d_node_type:ExtractorNode"
    # the ones the label already identifies keep their description untouched
    assert d["D.01"] == "prosa"


def test_a_node_with_no_description_gets_one():
    nodes = [(f"D.0{i}", "2", None, False) for i in range(1, 6)]
    nodes.append(("", "2", None, False))  # the unlabelled straggler
    root = build({"2": ANONYMOUS_SVG}, nodes)
    assert annotate_icon_node_types(root) == (1, 0)
    assert descriptions(root)[""] == "_s3d_node_type:ExtractorNode"


def test_annotation_is_idempotent():
    nodes = [(f"D.0{i}", "2", None, False) for i in range(1, 6)]
    nodes.append(("SF04.2", "2", None, False))
    root = build({"2": ANONYMOUS_SVG}, nodes)
    assert annotate_icon_node_types(root)[0] == 1
    assert annotate_icon_node_types(root)[0] == 0
    assert descriptions(root)["SF04.2"].count("_s3d_node_type:") == 1


def test_groups_are_never_annotated():
    """A box drawn with an icon realizer is still a container; the importer
    types it from its palette colour. Calling it a Combiner would be a new
    error, not a fix."""
    nodes = [(f"C.0{i}", "3", None, False) for i in range(1, 6)]
    nodes.append(("Vestibolo", "3", None, True))
    root = build({"3": ANONYMOUS_SVG}, nodes)
    assert annotate_icon_node_types(root) == (0, 0)
    assert descriptions(root)["Vestibolo"] is None


def test_self_naming_resources_are_left_to_the_importer():
    """The importer reads `continuity.svg` itself — writing a marker there
    would be noise for no gain."""
    root = build({"1": CONTINUITY_SVG}, [("BR1", "1", None, False)])
    assert annotate_icon_node_types(root) == (0, 0)


def test_an_unidentifiable_icon_is_reported_not_guessed():
    root = build({"9": ANONYMOUS_SVG}, [("mystery", "9", None, False)])
    annotated, skipped = annotate_icon_node_types(root)
    assert (annotated, skipped) == (0, 1)
    assert descriptions(root)["mystery"] is None
