"""The code the proxies are named by is the study's (E.D., 11 Oct 2026).

`graph_code.py` reads it with s3Dgraphy's `api.study_code` — the study's
code, else the GraphML header ID, else the retired em_id — so a file that
carries the code only on its study re-attaches the proxies like an old one.
Measured with the s3Dgraphy next door (`../s3Dgraphy/src`), the one that
knows the study's code; with the bundled wheel the header fields are read as
before.
"""
import importlib.util
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
S3D_SRC = REPO.parent / "s3Dgraphy" / "src"
if not S3D_SRC.is_dir():
    pytest.skip("needs ../s3Dgraphy/src", allow_module_level=True)
sys.path.insert(0, str(S3D_SRC))

spec = importlib.util.spec_from_file_location("_emtools_graph_code",
                                              REPO / "graph_code.py")
gc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gc)

from s3dgraphy import api  # noqa: E402

if not hasattr(api, "propose_study_code"):
    pytest.skip("the s3Dgraphy next door predates the stable study code",
                allow_module_level=True)

from s3dgraphy.exporter.emjson_exporter import build_emjson  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.importer.emjson_importer import (  # noqa: E402
    materialize_graph_scope, parse_emjson)
from s3dgraphy.importer.import_graphml import GraphMLImporter  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402

FIXTURE = S3D_SRC.parent / "tests" / "fixtures" / "canvas_metadata.graphml"


def _graphml(tmp_path, code="GT16"):
    out = tmp_path / f"{code}.graphml"
    out.write_text(FIXTURE.read_text(encoding="utf-8").replace(
        "ID:TestSite", f"ID:{code}"), encoding="utf-8")
    return GraphMLImporter(str(out), Graph(graph_id="tmp")).parse()


def test_the_graphml_and_the_em_json_it_becomes_give_the_same_code(tmp_path):
    graph = _graphml(tmp_path)
    assert gc.graph_code_of(graph) == "GT16"
    doc = json.loads(json.dumps(build_emjson(graph)))
    back, _ = parse_emjson(doc)
    assert "graph_code" not in back.attributes  # the em.json does not carry it
    assert gc.graph_code_of(back) == "GT16"
    assert gc.adopt_graph_code(back) == "GT16"
    assert back.attributes["graph_code"] == "GT16"  # where EM-tools looks
    assert gc.section_code(doc["graph"]) == "GT16"


def test_a_file_with_only_the_em_id_gives_the_same_code():
    g = Graph("old")
    g.add_node(StratigraphicUnit("u1", name="USM100"))
    materialize_graph_scope(g, em_id="GT16")
    doc = json.loads(json.dumps(build_emjson(g)))
    back, _ = parse_emjson(doc)
    assert gc.graph_code_of(back) == "GT16"
    assert gc.section_code(doc["graph"]) == "GT16"


def test_the_old_fields_are_still_read_and_the_placeholders_are_not_codes():
    g = Graph("table")
    g.data["graph_code"] = "U4CODE"  # a graph made from a table (U4)
    assert gc.graph_code_of(g) == "U4CODE"
    h = Graph("missing")
    h.attributes["graph_code"] = "MISSINGCODE"
    assert gc.graph_code_of(h) is None
    assert gc.graph_code_of(None) is None
    assert gc.section_code({"attributes": {"graph_code": "site_id"}}) == ""


def test_reading_never_proposes():
    g = Graph("bare")
    g.add_node(StratigraphicUnit("u1", name="US1"))
    assert gc.graph_code_of(g) is None
    assert not [n for n in g.nodes if n.node_type == "study"]
