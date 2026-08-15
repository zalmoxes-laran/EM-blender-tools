"""L'export Heriverse non pubblica i morti — misurato, non dichiarato.

Due superfici, non una, e sono la ragione per cui questo test sta in EMtools e
non solo in s3Dgraphy:

* il **grafo** pubblicato (``JSONExporter``, la chiamata che
  ``export.heriversejson`` fa e basta) — filtrato dentro la libreria;
* i **proxy .glb**, scelti dall'elenco dei nomi stratigrafici che l'operatore
  costruisce. Se solo il primo filtrasse, la scena conterrebbe il modello 3D di
  una US che il grafo non nomina più.

Il predicato è quello di s3Dgraphy (``dissemination.is_removed_node`` →
``crdt.is_removed``): qui si verifica che venga USATO, non lo si riscrive.

Limite dichiarato: ``EXPORT_OT_heriverse`` importa ``bpy`` e non è caricabile
headless, quindi si misura il modulo bpy-free che l'operatore chiama
(``export_operators/heriverse/dissemination.py``) e non il metodo
dell'operatore. È per renderlo misurabile che quel modulo esiste.
"""

import json
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent

# il CHECKOUT di s3Dgraphy vince sulla wheel installata: `dissemination` è
# nuovo e una wheel vecchia renderebbe questa regola non misurabile
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))

s3d_api = pytest.importorskip(
    "s3dgraphy.api", reason="s3dgraphy non importabile (checkout o wheel)")
pytest.importorskip(
    "s3dgraphy.dissemination",
    reason="s3dgraphy senza la politica di disseminazione (< 1.6.0.dev14)")

def _load(module_name: str, relative: str):
    """Carica un modulo dell'addon per percorso — il package `__init__` importa
    bpy, e mettere quella cartella su ``sys.path`` farebbe ombra a nomi generici
    (``utils``, ``gltf``) per tutta la sessione di test."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, _REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


emtools_dissemination = _load("_emtools_test_dissemination",
                              "export_operators/heriverse/dissemination.py")

from s3dgraphy.exporter.json_exporter import JSONExporter          # noqa: E402
from s3dgraphy.multigraph.multigraph import multi_graph_manager    # noqa: E402

BORN = "2026-08-14T10:00:00+00:00"
KILLED = "2026-08-14T11:00:00+00:00"
LATER = "2026-08-14T12:00:00+00:00"


def _graph(resurrect=False):
    """US 1 viva, US 2 cancellata (e, se richiesto, riesumata da una modifica
    successiva). Costruito attraverso il documento, come sul campo."""
    section = {"graph_id": "heriverse-tomb", "nodes": [], "edges": []}
    ops = [
        s3d_api.make_op("add_node", id="us1",
                        node={"node_type": "US", "name": "US 1"},
                        ts=BORN, author="scavatrice"),
        s3d_api.make_op("add_node", id="us2",
                        node={"node_type": "US", "name": "US 2"},
                        ts=BORN, author="scavatrice"),
        s3d_api.make_op("add_edge", source="us1", target="us2",
                        edge_type="is_after", ts=BORN, author="scavatrice"),
        s3d_api.make_op("remove_node", id="us2", ts=KILLED, author="scavatrice"),
    ]
    if resurrect:
        ops.append(s3d_api.make_op("update_field", id="us2", field="description",
                                   value="ripresa", ts=LATER, author="direttore"))
    for op in ops:
        assert s3d_api.apply_op(section, op)["applied"], op
    doc = {"header": {"format": "em.json", "version": "1.0"}, "graph": section}
    graph, _warnings = s3d_api.load_emjson(doc)
    return graph


def test_il_grafo_pubblicato_non_contiene_la_us_cancellata(tmp_path):
    graph = _graph()
    out = tmp_path / "heriverse.json"
    multi_graph_manager.graphs[graph.graph_id] = graph
    try:
        JSONExporter(str(out)).export_graphs([graph.graph_id])
    finally:
        multi_graph_manager.graphs.pop(graph.graph_id, None)

    blob = out.read_text(encoding="utf-8")
    assert "us2" not in blob
    assert "US 2" not in blob
    assert "removed" not in blob, "assente, non nascosta: nemmeno il marcatore"
    payload = json.loads(blob)
    strat = payload["graphs"][graph.graph_id]["nodes"]["stratigraphic"]["US"]
    assert set(strat) == {"us1"}
    flat = [e for bucket in payload["graphs"][graph.graph_id]["edges"].values()
            for e in bucket]
    assert flat == [], "l'arco rimasto appeso al morto doveva sparire con lui"


def test_i_proxy_esportati_escludono_la_us_cancellata():
    graph = _graph()
    names, removed = emtools_dissemination.publishable_stratigraphic_names(
        graph, ["US"])
    assert names == ["US 1"]
    assert removed == 1


def test_una_modifica_successiva_alla_cancellazione_e_una_resurrezione():
    """Il predicato è quello della libreria, non "c'è la chiave removed": una
    US ripresa dopo la cancellazione torna a esportarsi."""
    graph = _graph(resurrect=True)
    names, removed = emtools_dissemination.publishable_stratigraphic_names(
        graph, ["US"])
    assert sorted(names) == ["US 1", "US 2"]
    assert removed == 0


def test_senza_la_libreria_lo_si_dichiara_invece_di_fingere(monkeypatch):
    """Una wheel vecchia non deve far fallire l'export — ma nemmeno far credere
    che il filtro ci sia stato."""
    import builtins
    real_import = builtins.__import__

    def _no_dissemination(name, *args, **kwargs):
        if name == "s3dgraphy.dissemination":
            raise ImportError("wheel vecchia")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_dissemination)
    assert emtools_dissemination.predicate_available() is False
    graph = _graph()
    names, removed = emtools_dissemination.publishable_stratigraphic_names(
        graph, ["US"])
    assert sorted(names) == ["US 1", "US 2"]
    assert removed == 0
