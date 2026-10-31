"""MICRO valore-proprietà (E.D., 28 Oct 2026), the EM Tools side.

1. Every operator that creates or changes a property passes through
   s3Dgraphy's ``PropertyNode`` (constructor and setter), which keeps
   ``description`` and ``value`` equal: the shapes of the calls EM Tools makes
   are tested here as they are written in the operators.
2. A property is documented through its extractor: the EM Setup resource
   folder no longer writes property → document ``has_documentation``.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from s3dgraphy.graph import Graph
from s3dgraphy.nodes.document_node import DocumentNode
from s3dgraphy.nodes.property_node import PropertyNode
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit

_REPO = Path(__file__).resolve().parent.parent


def _module():
    sp = spec_from_file_location("emt_property_documentation",
                                 _REPO / "property_documentation.py")
    m = module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


# ── 1 · the value in two places, through s3Dgraphy ──────────────────────────

def test_canonical_document_year_is_in_both_places():
    # canonical_document_helpers.create_canonical_document_node
    pn = PropertyNode(node_id="p", name="absolute_time_start",
                      property_type="absolute_time_start",
                      value="1923", description="1923")
    pn.value = "1924"                       # a later edit, as the panels do
    assert (pn.value, pn.description) == ("1924", "1924")


def test_a_panel_writing_the_description_moves_the_value():
    # sync_manager / em_setup write `node.description = ...` on whatever node
    pn = PropertyNode("p", "material", value="tufo")
    pn.description = "peperino"
    assert pn.value == "peperino"


def test_the_surface_area_geometry_keeps_its_two_places():
    # surface_areale.postprocess: name «geometry» (the default), the value the
    # proxy object's name, the description a sentence — geometry is exempt
    pn = PropertyNode(node_id="p", name="geometry",
                      description="Geometry property for US1",
                      value="US1_areale", property_type="string")
    pn.value = "US1_areale.001"
    assert pn.description == "Geometry property for US1"


def test_the_proxy_box_property_value_is_its_description():
    # proxy_box_creator.create_enhanced: value "" and the sentence in the
    # description — EM's value is the description, so data.value mirrors it
    pn = PropertyNode(node_id="p", name="Proxy Geometry",
                      property_type="proxy_geometry", value="",
                      description="Coarse 3D bounding volume (proxy box)")
    assert pn.value == pn.description == "Coarse 3D bounding volume (proxy box)"


# ── 2 · property → document goes through the extractor ──────────────────────

def _graph():
    g = Graph("G")
    g.add_node(StratigraphicUnit("US1", "US1", "a wall"))
    g.add_node(PropertyNode("p1", "material", value="tufo"))
    g.add_node(DocumentNode("D1", "D.01", "a report"))
    g.add_edge("hp", "US1", "p1", "has_property")
    return g


def test_a_property_is_documented_through_a_new_extractor():
    m = _module()
    g = _graph()
    p, d = g.find_node_by_id("p1"), g.find_node_by_id("D1")
    assert m.documents_through_extractor(p, d)
    assert not m.documents_through_extractor(g.find_node_by_id("US1"), d)
    ext = m.document_through_extractor(g, p, d)
    assert ext.node_type == "extractor" and ext.name == "D.01.1"
    kinds = {(e.edge_source, e.edge_target, e.edge_type) for e in g.edges}
    assert ("p1", ext.node_id, "has_data_provenance") in kinds
    assert (ext.node_id, "D1", "extracted_from") in kinds
    assert not any(e.edge_type == "has_documentation" and e.edge_source == "p1"
                   for e in g.edges)
    # the same act twice is once
    assert m.document_through_extractor(g, p, d) is ext
    assert sum(1 for n in g.nodes if n.node_type == "extractor") == 1


def test_the_extractor_joins_the_property_paradata_group():
    from s3dgraphy.nodes.group_node import ParadataNodeGroup
    m = _module()
    g = _graph()
    g.add_node(ParadataNodeGroup("PD", "PD_US1", ""))
    g.add_edge("in", "p1", "PD", "is_in_paradata_nodegroup")
    ext = m.document_through_extractor(g, g.find_node_by_id("p1"), g.find_node_by_id("D1"))
    assert any(e.edge_source == ext.node_id and e.edge_target == "PD"
               and e.edge_type == "is_in_paradata_nodegroup" for e in g.edges)


def test_the_next_extractor_name_counts_on():
    m = _module()
    g = _graph()
    from s3dgraphy.nodes.extractor_node import ExtractorNode
    g.add_node(ExtractorNode("e1", "D.01.4", ""))
    assert m.next_extractor_name(g, "D.01") == "D.01.5"


def test_resource_utils_routes_a_property_through_the_extractor():
    src = (_REPO / "em_setup" / "resource_utils.py").read_text(encoding="utf-8")
    # three: an existing document, a new one, and (MICRO-BLEND-OFFICINA-2) the
    # document a detail-cache file is redirected to
    assert src.count("documents_through_extractor(target_node,") == 3
