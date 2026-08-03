"""C1 — the georeferencing done in Blender must survive the export.

The bug this pins was silent and symmetrical to one found in s3Dgraphy:
``push_to_geonode`` wrote epsg / shift as INSTANCE ATTRIBUTES on the
GeoPositionNode, while s3Dgraphy keeps those values in ``node.data`` and
``to_dict()`` serialises ``node.data`` and nothing else. Inside a Blender session
everything looked right — ``pull_from_geonode`` read back the same attributes it
had just written — and the loss only appeared on the other side of an export:
EPSG 32633 with a shift of 291960.5 / 4640631.8 arrived at EMStudio and Heriverse
as 4326 and 0 / 0. G1 and G3 (reprojection, oriented footprint) had nothing to
work with.

So the test is deliberately end-to-end and unglamorous: **write, export, reload,
compare**. It is the shape of test that would have caught it, and the shape that
keeps it caught — anything that stops serialising one of these fields fails here
rather than in somebody's browser.

``graph_sync`` imports ``bpy`` only INSIDE ``get_active_graph``, so the functions
under test run outside Blender; they are loaded straight from the file to avoid the
addon's ``__init__`` (which does import bpy at module level).
"""

import importlib.util
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent

# The s3Dgraphy CHECKOUT wins over any installed s3dgraphy: this test is about
# agreeing with the reference implementation as it is now, and a stale wheel in
# the dev venv would make the agreement untestable.
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))

s3dgraphy_api = pytest.importorskip(
    "s3dgraphy.api", reason="s3dgraphy not importable (checkout or wheel)")
from s3dgraphy.graph import Graph  # noqa: E402  (after the importorskip)


def _load_graph_sync():
    spec = importlib.util.spec_from_file_location(
        "_emtools_test_graph_sync", _REPO / "georef_manager" / "graph_sync.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


graph_sync = _load_graph_sync()

# A real anchor: the Colosseum in UTM zone 33N, with a scene rotated off north.
EPSG = "32633"
SHIFT = (291960.5, 4640631.8, 12.0)
AZIMUTH = 27.5


def _graph_with_pushed_georef(graph_id="tm", rotation=AZIMUTH):
    graph = Graph(graph_id=graph_id)
    assert graph_sync.push_to_geonode(
        graph, EPSG, SHIFT[0], SHIFT[1], SHIFT[2], rotation) is True
    return graph


def _round_trip(graph):
    """Blender → em.json → back, the way an export actually goes."""
    doc = s3dgraphy_api.graph_to_emjson(graph)
    reloaded, _warnings = s3dgraphy_api.load_emjson(doc)
    return doc, reloaded


# ── the fix, stated as the failure it prevents ────────────────────────────────

def test_the_georef_survives_the_export():
    graph = _graph_with_pushed_georef()
    doc, reloaded = _round_trip(graph)

    geo_payloads = [n for n in doc["graph"]["nodes"]
                    if n["node_type"] == "geo_position"]
    assert len(geo_payloads) == 1, "one anchor per graph"
    exported = geo_payloads[0]["data"]
    assert exported["epsg"] == 32633
    assert exported["shift_x"] == pytest.approx(SHIFT[0])
    assert exported["shift_y"] == pytest.approx(SHIFT[1])
    assert exported["shift_z"] == pytest.approx(SHIFT[2])
    assert exported["rotation"] == pytest.approx(AZIMUTH)

    back = graph_sync.get_geo_node(reloaded)
    assert back.data["epsg"] == 32633, "before C1 this came back 4326"
    assert back.data["shift_x"] == pytest.approx(SHIFT[0]), "…and this came back 0.0"
    assert back.data["rotation"] == pytest.approx(AZIMUTH)


def test_push_writes_where_to_dict_reads():
    """The mechanism, not just the outcome: `to_dict()` serialises `node.data`,
    so that is where a push has to land. Reading it from the node's own
    serialiser is what makes this a statement about the contract."""
    graph = _graph_with_pushed_georef()
    node = graph_sync.get_geo_node(graph)
    serialised = node.to_dict()["data"]
    assert serialised["epsg"] == 32633
    assert serialised["shift_y"] == pytest.approx(SHIFT[1])
    assert serialised["rotation"] == pytest.approx(AZIMUTH)


def test_pull_reads_back_what_push_wrote():
    graph = _graph_with_pushed_georef()
    state = graph_sync.pull_from_geonode(graph)
    assert state == {
        "epsg": "32633",
        "shift_x": pytest.approx(SHIFT[0]),
        "shift_y": pytest.approx(SHIFT[1]),
        "shift_z": pytest.approx(SHIFT[2]),
        "rotation": pytest.approx(AZIMUTH),
    }


def test_pull_works_after_a_round_trip():
    """The panel must show the same numbers whether the graph was just edited or
    reopened from disk — otherwise "Pull from graph" lies after a reload."""
    _doc, reloaded = _round_trip(_graph_with_pushed_georef())
    assert graph_sync.pull_from_geonode(reloaded) == \
        graph_sync.pull_from_geonode(_graph_with_pushed_georef())


# ── field names agree with s3Dgraphy, which owns them ─────────────────────────

def test_the_field_names_are_s3dgraphys_own():
    """Not "the same names as far as I remember": the keys a freshly constructed
    GeoPositionNode carries ARE the vocabulary, and a push must not add a key
    beside them (`azimuth`, `rot`, `epsg_code`…) that nothing downstream reads."""
    from s3dgraphy.nodes.geo_position_node import GeoPositionNode

    reference = set(GeoPositionNode(node_id="geo_ref").data)
    pushed = set(graph_sync.get_geo_node(_graph_with_pushed_georef()).data)
    assert pushed == reference, (
        f"push_to_geonode writes {pushed - reference or '{}'} that s3Dgraphy does "
        f"not define, and omits {reference - pushed or '{}'}")


def test_rotation_is_the_name_and_zero_means_north_up():
    from s3dgraphy.nodes.geo_position_node import GeoPositionNode

    assert GeoPositionNode(node_id="geo_ref").data["rotation"] == 0.0
    graph = _graph_with_pushed_georef(rotation=0.0)
    assert graph_sync.get_geo_node(graph).data["rotation"] == 0.0


# ── additive: nothing is destroyed by a partial push ──────────────────────────

def test_a_non_numeric_epsg_leaves_the_previous_one_alone():
    """'NotSet' / '' is "the user has not chosen a CRS yet", not "reset it": a
    Heriverse export that happened while the field was empty must not silently
    demote a graph that already had 32633."""
    graph = _graph_with_pushed_georef()
    assert graph_sync.push_to_geonode(graph, "", 1.0, 2.0, 3.0, 0.0) is True
    data = graph_sync.get_geo_node(graph).data
    assert data["epsg"] == 32633, "the EPSG survived an empty push"
    assert data["shift_x"] == pytest.approx(1.0), "the shift did update"


def test_a_caller_that_omits_the_azimuth_does_not_wipe_it():
    """`rotation` is additive: the default keeps a scene's orientation rather
    than flattening it to north-up behind the author's back."""
    graph = _graph_with_pushed_georef(rotation=42.0)
    graph_sync.push_to_geonode(graph, EPSG, *SHIFT)   # no rotation argument
    assert graph_sync.get_geo_node(graph).data["rotation"] == pytest.approx(0.0), (
        "the documented default is 0.0; if this ever becomes 'keep', update the "
        "docstring and this test together")


def test_a_node_without_a_data_dict_still_exports():
    """Defensive, and cheap: a GeoPositionNode built by some other path (or by an
    older s3dgraphy) must not make the push fail silently."""
    graph = Graph(graph_id="nodata")
    node = graph_sync.get_geo_node(graph)
    node.data = None                                   # simulate the odd case
    assert graph_sync.push_to_geonode(graph, EPSG, *SHIFT, AZIMUTH) is True
    assert graph_sync.get_geo_node(graph).data["epsg"] == 32633


def test_no_graph_no_crash():
    assert graph_sync.push_to_geonode(None, EPSG, *SHIFT) is False
    assert graph_sync.pull_from_geonode(None) is None
