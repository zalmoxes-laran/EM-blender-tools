"""The site, its footprint and its GIS layers survive EM Tools' save (MICRO lab
sito Sarmizegetusa, 30 Oct 2026).

EM Tools saves the graph it holds (graph_origins.save_file → s3dgraphy's
container writer): nothing of the site is rebuilt from Blender. Measured before
s3Dgraphy's connections 1.6.50: the site's has_property (the footprint) and
has_linked_resource (a layer) were degraded to generic_connection on LOAD, and
the next save wrote them so. This pins the whole way: build with s3dgraphy.gis,
write the container, load it as EM Tools loads it, write it again, compare; and
the panel's lines (``georef_manager/site_info.py``, pure).
"""

import importlib.util
import json
import pathlib
import struct
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))

gis = pytest.importorskip("s3dgraphy.gis", reason="s3dgraphy without the gis package (checkout or wheel)")
from s3dgraphy import api  # noqa: E402
from s3dgraphy.exporter.emjson_exporter import build_emjson  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.property_node import PropertyNode  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402

spec = importlib.util.spec_from_file_location("_emt_site_info", _REPO / "georef_manager" / "site_info.py")
site_info = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site_info)


def _points_shapefile(base: pathlib.Path):
    pts = [("101", 327350.0, 448660.0, 491.5), ("R2", 327340.405, 448689.677, 493.014)]
    recs = b""
    for i, (_l, x, y, _z) in enumerate(pts, 1):
        c = struct.pack("<i2d", 1, x, y)
        recs += struct.pack(">2i", i, len(c) // 2) + c
    head = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, (100 + len(recs)) // 2)
    head += struct.pack("<2i8d", 1000, 1, 327340.405, 448660.0, 327350.0, 448689.677, 0, 0, 0, 0)
    base.with_suffix(".shp").write_bytes(head + recs)
    fields = [("field_1", "C", 10, 0), ("field_4", "N", 12, 4)]
    dbf = struct.pack("<B3BIHH20x", 3, 126, 10, 30, len(pts), 32 + 32 * len(fields) + 1, 1 + 22)
    for n, t, ln, dec in fields:
        dbf += n.encode().ljust(11, b"\0") + t.encode() + b"\0" * 4 + bytes([ln, dec]) + b"\0" * 14
    dbf += b"\x0d" + b"".join(b" " + l.encode().ljust(10) + f"{z:12.4f}".encode() for l, _x, _y, z in pts)
    base.with_suffix(".dbf").write_bytes(dbf)
    base.with_suffix(".prj").write_text('PROJCS["Dealul_Piscului_1970_Stereo_70_deprecated"]')
    return base.with_suffix(".shp")


def _study(tmp_path):
    g = Graph("GT16")
    geo = next(n for n in g.nodes if n.node_type == "geo_position")
    geo.data.update({"epsg": 3844, "shift_x": 327372.56, "shift_y": 448682.65, "shift_z": 0, "rotation": 0})
    g.add_node(StratigraphicUnit("su1", "SU001"))
    g.add_node(PropertyNode("p_geom", "geometry", value="shape", property_type="geometry"))
    g.add_edge("su1_geom", "su1", "p_geom", "has_property")
    site = gis.add_site(g, "Templu Mare")
    ring = [[327337.8, 448685.8, 491.2], [327346.4, 448645.2, 491.2], [327380.0, 448650.0, 491.3]]
    gis.set_footprint(g, site.node_id, [[ring]], "EPSG:3844", sources=["p_geom"])
    gis.add_gis_layer(g, str(_points_shapefile(tmp_path / "M_SR15_AREA_A")), attach_to=site.node_id,
                      acquisition={"dtc_kind": "topographic", "name": "Rilievo 2015"})
    return g, site


def _container(graph):
    return {"header": {"format": "em.json", "version": "1.1"}, "graphs": {"GT16": build_emjson(graph)["graph"]},
            "active_graph_id": "GT16"}


def _site_part(doc):
    gd = doc["graphs"]["GT16"] if "graphs" in doc else doc["graph"]
    keep = {n["id"] for n in gd["nodes"] if n.get("node_type") in ("LocationNodeGroup", "resource", "resource_file", "dtc_acquisition")
            or (n.get("data") or {}).get("property_type") == "footprint"
            or n.get("node_type") == "extractor"}
    nodes = sorted(json.dumps({k: v for k, v in n.items() if k != "field_clocks"}, sort_keys=True)
                   for n in gd["nodes"] if n["id"] in keep)
    edges = sorted((e["source"], e["edge_type"], e["target"]) for e in gd["edges"]
                   if e["source"] in keep or e["target"] in keep)
    return nodes, edges


def test_the_site_survives_a_load_and_a_save(tmp_path):
    from s3dgraphy.multigraph import MultiGraphManager
    spec_o = importlib.util.spec_from_file_location("_emt_graph_origins", _REPO / "graph_origins.py")
    origins = importlib.util.module_from_spec(spec_o)
    sys.modules[spec_o.name] = origins   # a dataclass module must be registered
    spec_o.loader.exec_module(origins)
    g, site = _study(tmp_path)
    first = tmp_path / "first.em.json"
    first.write_text(json.dumps(_container(g)))
    # as EM Tools loads it (multi_graph_manager.load_container) and saves it
    # (graph_origins.save_file → save_container_file with the live graphs)
    mgr = MultiGraphManager()
    container, warnings = mgr.load_container(str(first))
    assert not [w for w in warnings if "generic" in w or "not allowed" in w], warnings
    second = tmp_path / "second.em.json"
    second.write_text(first.read_text())
    # EM Tools' «Save em.json»: the file's container as base, its graphs from the scene
    res = origins.save_file(str(second), ["GT16"], live=lambda gid: mgr.graphs.get(gid),
                            active_graph_id="GT16")
    assert res.written == ["GT16"]
    a, b = json.loads(first.read_text()), json.loads(second.read_text())
    assert _site_part(a)[1] == _site_part(b)[1]
    assert not [e for e in _site_part(b)[1] if e[1] == "generic_connection"]
    nb = {json.loads(x)["id"]: json.loads(x) for x in _site_part(b)[0]}
    assert nb[site.node_id]["data"]["level"] == "sito"
    fp = next(n for n in nb.values() if (n.get("data") or {}).get("property_type") == "footprint")
    assert fp["data"]["value"].startswith("<http://www.opengis.net/def/crs/EPSG/0/3844> POLYGON Z")
    layer = next(n for n in nb.values() if (n.get("data") or {}).get("url_type") == "gis_layer")
    assert layer["data"]["crs"] == "EPSG:31700" and layer["data"]["frame"]["crs"] == "EPSG:3844"


def test_the_panel_says_the_site(tmp_path):
    g, _site = _study(tmp_path)
    reloaded, _w = api.load_emjson(build_emjson(g))
    lines = site_info.site_lines(site_info.site_summary(reloaded))
    assert lines == ["Site: Templu Mare",
                     "Footprint: POLYGON Z, EPSG:3844, 4 vertices",
                     "GIS layer: M_SR15_AREA_A (shapefile, EPSG:31700, 2 features)"]
    assert site_info.site_summary(Graph("empty")) is None
