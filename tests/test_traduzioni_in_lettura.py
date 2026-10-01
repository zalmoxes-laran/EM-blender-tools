"""MICRO-EMTOOLS-DEV26, parte 3 — le traduzioni, in lettura.

EMtools non scrive traduzioni, ma le rispetta:

* un grafo con TranslationNode passa per l'em.json di EMtools (container) e
  per il suo export RDF senza perderle;
* il TTL di Vitruvio del referto di s3Dgraphy, importato ed esportato, dà lo
  stesso grafo. Il file è ``vitruvio_publish.ttl``: ``vitruvio_excerpt.ttl`` ne
  è un ritaglio (tutte le sue triple sono nel primo) senza la risorsa
  ``em:EMGraph``, e nessun importer lo legge come grafo (misurato: 0 grafi);
* il Document Manager mostra le lingue come etichette: ``la · it ✓ · en ✦``.
"""

from __future__ import annotations

import pathlib

import pytest

pytest.importorskip("rdflib")

from s3dgraphy import api
from s3dgraphy.exporter.emjson_exporter import build_emjson
from s3dgraphy.exporter.rdf_exporter import RDFExporter
from s3dgraphy.graph import Graph
from s3dgraphy.importer.emjson_importer import parse_emjson
from s3dgraphy.importer.rdf_importer import RDFImporter
from s3dgraphy.multigraph.multigraph import multi_graph_manager
from s3dgraphy.nodes.author_node import AuthorAINode, AuthorNode
from s3dgraphy.nodes.document_node import DocumentNode

import emjson_support
import translation_tags as tt

TTL = pathlib.Path(__file__).resolve().parent / "fixtures" / "translations" / "vitruvio_publish.ttl"
QUOTE = "firmitatis, utilitatis, venustatis"


def _snapshot(graph):
    nodes = {n.node_id: (n.node_type, n.name, n.description or "",
                         dict(sorted((getattr(n, "data", None) or {}).items())))
             for n in graph.nodes}
    edges = sorted((e.edge_source, e.edge_target, e.edge_type) for e in graph.edges)
    return nodes, edges


def _vitruvio():
    g = Graph("vitruvio_emtools")
    g.add_node(AuthorNode("ed", name="Emanuel", orcid="0000-0002-1825-0097", surname="D"))
    g.add_node(AuthorAINode("claude", name="Claude"))
    doc = DocumentNode("d1", "D.1", QUOTE)
    doc.data = {"lang": "la"}
    g.add_node(doc)
    api.set_working_language(g, "it")
    api.add_translation(g, "d1", "description", "it", "solidità, utilità, bellezza",
                        by="ed")
    api.add_translation(g, "d1", "description", "en", "strength, utility, beauty",
                        by="ed", method="ai", ai="claude", model="claude-opus-5-5")
    return g


def test_il_ttl_di_vitruvio_importato_ed_esportato_da_lo_stesso_grafo(tmp_path):
    first = RDFImporter().parse(str(TTL))[0]
    assert len(api.translations(first, "d1")) == 1
    exporter = RDFExporter(str(tmp_path / "again.ttl"), format="turtle", mode="round_trip")
    path = exporter.export_single_graph(first)
    again = RDFImporter().parse(path)[0]
    assert _snapshot(again) == _snapshot(first)


def test_l_em_json_di_emtools_le_conserva(tmp_path):
    g = _vitruvio()
    before = _snapshot(parse_emjson(build_emjson(g))[0])
    saved = tmp_path / "project.em.json"
    old = dict(multi_graph_manager.graphs)
    try:
        multi_graph_manager.graphs.clear()
        multi_graph_manager.graphs[g.graph_id] = g
        emjson_support.export_container_to_emjson(str(saved), active_graph_id=g.graph_id)
        multi_graph_manager.graphs.clear()
        emjson_support.import_container_from_emjson(str(saved), replace=True)
        back = multi_graph_manager.graphs[g.graph_id]
    finally:
        multi_graph_manager.graphs.clear()
        multi_graph_manager.graphs.update(old)
    assert len(api.translations(back, "d1")) == 2
    assert _snapshot(back) == before


def test_l_export_rdf_round_trip_le_porta_e_tornano(tmp_path):
    g = _vitruvio()
    first = parse_emjson(build_emjson(g))[0]
    exporter = RDFExporter(str(tmp_path / "rt.ttl"), format="turtle", mode="round_trip")
    back = RDFImporter().parse(exporter.export_single_graph(first))[0]
    assert {t.data["lang"] for t in api.translations(back, "d1")} == {"it", "en"}
    nodes, edges = _snapshot(first)
    after_nodes, after_edges = _snapshot(parse_emjson(build_emjson(back))[0])
    assert after_edges == edges
    for nid, value in nodes.items():
        assert after_nodes.get(nid) == value, nid


def test_le_etichette_delle_lingue():
    g = _vitruvio()
    assert tt.line(g, g.find_node_by_id("d1")) == "la · en ✦ · it ✓"
    # a document without translations says nothing
    g.add_node(DocumentNode("d2", "D.2", "senza traduzioni"))
    assert tt.line(g, g.find_node_by_id("d2")) == ""


def test_una_traduzione_da_riallineare_e_una_da_rivedere():
    g = _vitruvio()
    api.add_translation(g, "d1", "description", "fr", "solidité, utilité, beauté",
                        by="ed", review=True)
    g.find_node_by_id("d1").description = "firmitas, utilitas, venustas"
    marks = {t["lang"]: t["mark"] for t in tt.tags(g, g.find_node_by_id("d1"))}
    assert marks["fr"] == "?↻" and marks["it"] == "↻" and marks["en"] == "✦↻"


def test_dal_ttl_l_originale_e_il_latino():
    g = RDFImporter().parse(str(TTL))[0]
    assert tt.line(g, g.find_node_by_id("d1")) == "la · it ✓"
