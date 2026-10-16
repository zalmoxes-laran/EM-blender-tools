"""I contenitori RM arrivano nell'em.json (MICRO-EMTOOLS-CONTENITORI, 16-10-2026).

Misurato sui quattro em.json del Templu Mare: 99 `representation_model`, gli
archi diretti D.09→87 e D.01→12, nessun `RepresentationModelNodeGroup` e nessun
`is_in_representation_model_group`. La proiezione c'era solo dietro i bottoni
Sync e Project; ora ogni salvataggio passa da `group_nodes.project_all`.

Qui un grafo s3Dgraphy VERO e una lista di contenitori finta (il modulo non
importa `bpy` apposta): la prova è sull'em.json che ne esce, non sul grafo in
memoria.
"""

import importlib.util
import pathlib
import sys
from types import SimpleNamespace as Container

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))
pytest.importorskip("s3dgraphy.nodes.group_node")

from s3dgraphy.exporter.emjson_exporter import build_emjson, export_emjson  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.importer.emjson_importer import import_emjson  # noqa: E402
from s3dgraphy.nodes.document_node import DocumentNode  # noqa: E402
from s3dgraphy.nodes.epoch_node import EpochNode  # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "_emtools_test_group_nodes_emjson", _REPO / "rm_manager/group_nodes.py")
gn = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gn
_spec.loader.exec_module(gn)


def _templu_mare_in_piccolo():
    """La forma del Templu Mare: due Documenti, archi diretti Doc→modello ed
    epoca→modello, nessun gruppo."""
    g = Graph(graph_id="tm")
    g.add_node(DocumentNode(node_id="D01", name="D.01"))
    g.add_node(DocumentNode(node_id="D09", name="D.09"))
    g.add_node(EpochNode(node_id="ep1", name="Roman", start_time=0, end_time=100))
    for i in range(1, 6):
        rid = f"m{i}_model"
        g.add_node(RepresentationModelNode(node_id=rid, name=f"m{i}"))
        doc = "D01" if i <= 2 else "D09"
        g.add_edge(f"{doc}_hrm_{rid}", doc, rid, "has_representation_model")
        g.add_edge(f"ep1_hfe_{rid}", rid, "ep1", "has_first_epoch")
    return g


def _contenitori():
    return [
        Container(label="Survey 2015", doc_node_id="D01", group_node_id="",
                  model_node_ids=["m1_model", "m2_model"]),
        Container(label="Reconstruction", doc_node_id="D09", group_node_id="",
                  model_node_ids=["m3_model", "m4_model", "m5_model"]),
    ]


def _edges(doc, edge_type):
    return [(e["source"], e["target"]) for e in doc["graph"]["edges"]
            if e["edge_type"] == edge_type]


def _project(g, conts):
    fatti = gn.project_all(g, conts)
    for c, gid, _r in fatti:            # what the Blender side writes back
        c.group_node_id = gid
    return fatti


def test_PRIMA_il_vuoto_misurato_nessun_gruppo_nell_emjson():
    doc = build_emjson(_templu_mare_in_piccolo())
    tipi = {n["node_type"] for n in doc["graph"]["nodes"]}
    assert gn.GROUP_NODE_TYPE not in tipi
    assert _edges(doc, gn.MEMBERSHIP_EDGE) == []


def test_DOPO_l_export_contiene_i_gruppi():
    g = _templu_mare_in_piccolo()
    _project(g, _contenitori())
    doc = build_emjson(g)
    gruppi = {n["id"]: n["name"] for n in doc["graph"]["nodes"]
              if n["node_type"] == gn.GROUP_NODE_TYPE}
    assert gruppi == {"D01_rmgroup": "Survey 2015",
                      "D09_rmgroup": "Reconstruction"}


def test_L_APPARTENENZA_e_uno_a_uno():
    g = _templu_mare_in_piccolo()
    _project(g, _contenitori())
    membri = _edges(build_emjson(g), gn.MEMBERSHIP_EDGE)
    assert sorted(membri) == [
        ("m1_model", "D01_rmgroup"), ("m2_model", "D01_rmgroup"),
        ("m3_model", "D09_rmgroup"), ("m4_model", "D09_rmgroup"),
        ("m5_model", "D09_rmgroup")]
    sorgenti = [s for s, _t in membri]
    assert len(sorgenti) == len(set(sorgenti))       # un modello, un gruppo


def test_IL_DOCUMENTO_PUNTA_AL_GRUPPO_e_restano_gli_archi_diretti():
    g = _templu_mare_in_piccolo()
    _project(g, _contenitori())
    doc = build_emjson(g)
    hrm = _edges(doc, "has_representation_model")
    assert ("D01", "D01_rmgroup") in hrm
    assert ("D09", "D09_rmgroup") in hrm
    # accanto, mai al posto: i 5 archi diretti Doc→modello ci sono tutti
    diretti = [(s, t) for s, t in hrm if not t.endswith("_rmgroup")]
    assert len(diretti) == 5
    assert len(_edges(doc, "has_first_epoch")) == 5


def test_UN_CONTENITORE_SENZA_DOCUMENTO_non_ha_l_arco_dal_documento():
    g = _templu_mare_in_piccolo()
    conts = [Container(label="Loose", doc_node_id="", group_node_id="",
                       model_node_ids=["m1_model"])]
    _project(g, conts)
    doc = build_emjson(g)
    assert conts[0].group_node_id == "rmgroup_Loose"
    assert ("m1_model", "rmgroup_Loose") in _edges(doc, gn.MEMBERSHIP_EDGE)
    assert not [t for _s, t in _edges(doc, "has_representation_model")
                if t == "rmgroup_Loose"]


def test_DUE_SALVATAGGI_non_duplicano_niente():
    g = _templu_mare_in_piccolo()
    conts = _contenitori()
    _project(g, conts)
    prima = build_emjson(g)["graph"]
    secondo = _project(g, conts)
    assert all(not r["created"] and not r["added"] for _c, _g, r in secondo)
    dopo = build_emjson(g)["graph"]
    assert len(dopo["nodes"]) == len(prima["nodes"])
    assert len(dopo["edges"]) == len(prima["edges"])


def test_MESH_NAMES_E_AUTOREVOLE_un_modello_tolto_esce_dal_gruppo():
    g = _templu_mare_in_piccolo()
    conts = _contenitori()
    _project(g, conts)
    conts[1].model_node_ids = ["m3_model", "m4_model"]
    fatti = _project(g, conts)
    assert ("m5_model" in [m for _c, _g, r in fatti for m in r["removed"]])
    doc = build_emjson(g)
    assert ("m5_model", "D09_rmgroup") not in _edges(doc, gn.MEMBERSHIP_EDGE)
    # …e l'arco diretto D.09→m5 resta
    assert ("D09", "m5_model") in _edges(doc, "has_representation_model")


def test_UN_GRAFO_CHE_NON_C_ENTRA_non_riceve_gruppi_vuoti():
    altro = Graph(graph_id="shelf")
    assert gn.project_all(altro, _contenitori()) == []
    assert not [n for n in altro.nodes
                if getattr(n, "node_type", "") == gn.GROUP_NODE_TYPE]


def test_IL_FILE_SI_RILEGGE_e_il_confronto_e_muto(tmp_path):
    g = _templu_mare_in_piccolo()
    conts = _contenitori()
    _project(g, conts)
    out = tmp_path / "tm.em.json"
    export_emjson(g, str(out))
    back, _warnings = import_emjson(str(out))
    gruppi = {x["id"]: x for x in gn.groups_in(back)}
    assert gruppi["D01_rmgroup"]["doc_node_id"] == "D01"
    assert sorted(gruppi["D09_rmgroup"]["members"]) == [
        "m3_model", "m4_model", "m5_model"]
    assert gn.compare_with_graph(back, conts) == []


def test_ALL_APERTURA_una_differenza_e_una_riga_e_niente_si_corregge(tmp_path):
    g = _templu_mare_in_piccolo()
    conts = _contenitori()
    _project(g, conts)
    out = tmp_path / "tm.em.json"
    export_emjson(g, str(out))
    back, _w = import_emjson(str(out))
    n_edges = len(back.edges)
    scena = [Container(label="Survey 2015", doc_node_id="D01",
                       group_node_id="D01_rmgroup",
                       model_node_ids=["m1_model"])]          # m2 manca
    righe = gn.compare_with_graph(back, scena)
    assert any("Survey 2015" in r and "not in the container" in r
               for r in righe)
    assert any("Reconstruction" in r and "in no container" in r
               for r in righe)
    assert len(back.edges) == n_edges                    # nulla corretto
    assert scena[0].model_node_ids == ["m1_model"]
