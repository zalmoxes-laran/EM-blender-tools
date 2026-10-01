"""MICRO-EMTOOLS-DEV26, parte 1 — il rapporto dell'esportazione RDF.

* la riga breve è ``exporter.summary()`` di s3Dgraphy;
* i testi senza lingua sono un AVVISO, e l'avviso dice dove dichiararla;
* in ``publish`` la traduzione AI non verificata resta fuori, e il rapporto la conta;
* il dettaglio va in ``<nome>.export-report.txt`` accanto al ``.ttl``.
"""

from __future__ import annotations

import os
import sys

import pytest

pytest.importorskip("rdflib")

from s3dgraphy import api
from s3dgraphy.exporter.rdf_exporter import RDFExporter
from s3dgraphy.graph import Graph
from s3dgraphy.nodes.author_node import AuthorAINode, AuthorNode
from s3dgraphy.nodes.document_node import DocumentNode

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "export_operators", "rdf"))
import report as rdf_report  # noqa: E402  (bpy-free module of the operator)

QUOTE = "firmitatis, utilitatis, venustatis"


def _graph(study_lang=None):
    g = Graph("vitruvio")
    g.add_node(AuthorNode("ed", name="Emanuel", orcid="0000-0002-1825-0097", surname="D"))
    g.add_node(AuthorAINode("claude", name="Claude"))
    doc = DocumentNode("d1", "D.1", QUOTE)
    doc.data = {"lang": "la"}
    g.add_node(doc)
    g.add_node(DocumentNode("d2", "D.2", "una descrizione senza lingua propria"))
    if study_lang:
        api.set_working_language(g, study_lang)
    return g


def _export(graph, tmp_path, mode):
    exporter = RDFExporter(str(tmp_path / "vitruvio.ttl"), format="turtle", mode=mode)
    path = exporter.export_single_graph(graph)
    return exporter, path


def test_testi_senza_lingua_sono_un_avviso_che_dice_dove_dichiararla(tmp_path):
    g = _graph()
    exporter, path = _export(g, tmp_path, "publish")
    rep = rdf_report.build(exporter, path, [g], mode="publish")
    assert exporter.stats["literals_untagged"] > 0
    assert rep["level"] == "WARNING"
    assert exporter.summary() in rep["line"]
    assert rdf_report.WHERE_TO_DECLARE in rep["line"]
    assert "vitruvio declares no language" in rep["line"]


def test_con_la_lingua_dello_studio_nessun_avviso(tmp_path):
    g = _graph("it")
    exporter, path = _export(g, tmp_path, "publish")
    rep = rdf_report.build(exporter, path, [g], mode="publish")
    assert exporter.stats["literals_untagged"] == 0
    assert rep["level"] == "INFO" and not rep["warnings"]
    assert "vitruvio: it" in rep["text"]


def test_la_traduzione_ai_non_verificata_resta_fuori_e_si_conta(tmp_path):
    g = _graph("it")
    api.add_translation(g, "d1", "description", "it", "solidità, utilità, bellezza",
                        by="ed")
    api.add_translation(g, "d1", "description", "en", "strength, utility, beauty",
                        by="ed", method="ai", ai="claude", model="claude-opus-5-5")
    exporter, path = _export(g, tmp_path, "publish")
    rep = rdf_report.build(exporter, path, [g], mode="publish")
    assert exporter.stats["translations"] == 1          # only the Italian one
    assert "strength, utility" not in open(path, encoding="utf-8").read()
    assert rdf_report.excluded_counts(exporter.excluded)["translations"] == 1
    assert "1 AI translations not verified left out" in rep["line"]
    assert "AI not verified, left out:     1" in rep["text"]


def test_in_round_trip_viaggia_tutto(tmp_path):
    g = _graph("it")
    api.add_translation(g, "d1", "description", "en", "strength, utility, beauty",
                        by="ed", method="ai", ai="claude")
    exporter, path = _export(g, tmp_path, "round_trip")
    rep = rdf_report.build(exporter, path, [g], mode="round_trip")
    assert exporter.excluded == [] and exporter.stats["translations"] == 1
    assert "strength, utility" in open(path, encoding="utf-8").read()
    assert rep["level"] == "INFO"


def test_il_dettaglio_accanto_al_ttl(tmp_path):
    g = _graph()
    exporter, path = _export(g, tmp_path, "publish")
    rep = rdf_report.build(exporter, path, [g], mode="publish")
    written = rdf_report.write(rep)
    assert written == str(tmp_path / "vitruvio.export-report.txt")
    text = open(written, encoding="utf-8").read()
    assert text.startswith("EMtools — RDF export report")
    assert "▲" in text and "literals_untagged" in text
