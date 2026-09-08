"""Gli archi epoca↔modello rispecchiano la scena — misurato, non dichiarato.

Il bug che questo test recinta: gli archi si scrivono
``epoca --has_representation_model--> modello`` ma sette punti del RM manager
li cercavano dal capo opposto (``edge_source == model_node_id``). Una ricerca
nel verso sbagliato non trova nulla e non solleva niente: l'epoca spariva dal
pannello e l'arco restava nel grafo, così l'export Heriverse continuava a
dichiarare quel modello sotto un'epoca che l'utente aveva già staccato. Un
export che sopravvive a una modifica della scena non è un export, è un ricordo.

Due proprietà, e la seconda esiste solo sulla 1.6:

1. **Specchio.** ``sync_epoch_edges`` aggiunge ciò che manca e toglie ciò che
   non c'è più — non accumula. L'esito non dipende da quante volte la si
   chiama.
2. **Il Documento non si tocca.** Sulla 1.6 lo stesso ``edge_type``
   ``has_representation_model`` porta anche l'arco Documento→RM (container RM,
   ``proxy_box_creator``). Una pulizia che cancellasse per tipo di arco
   staccherebbe il modello dal suo documento: qui si verifica che il criterio
   sia l'altro capo (un ``EpochNode``), non il nome dell'arco.

Il modulo sotto misura è ``rm_manager/epoch_edges.py``, che non importa ``bpy``
proprio per poter essere misurato qui; il grafo è un doppio minimo, perché la
regola riguarda la direzione degli archi e non la libreria.
"""

import importlib.util
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _load(module_name: str, relative: str):
    """Carica un modulo dell'addon per percorso — ``rm_manager/__init__.py``
    importa bpy e fuori da Blender non si carica."""
    spec = importlib.util.spec_from_file_location(module_name, _REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


epoch_edges = _load("_emtools_test_epoch_edges", "rm_manager/epoch_edges.py")


# --------------------------------------------------------------------------
# Doppio minimo di grafo: quel poco che l'helper usa davvero.
# --------------------------------------------------------------------------

class _Node:
    def __init__(self, node_id, node_type, name=""):
        self.node_id = node_id
        self.node_type = node_type
        self.name = name


class _Edge:
    def __init__(self, edge_id, edge_source, edge_target, edge_type):
        self.edge_id = edge_id
        self.edge_source = edge_source
        self.edge_target = edge_target
        self.edge_type = edge_type


class _Graph:
    def __init__(self, nodes, edges):
        self.nodes = list(nodes)
        self.edges = list(edges)

    def find_node_by_id(self, node_id):
        return next((n for n in self.nodes if n.node_id == node_id), None)

    def find_edge_by_id(self, edge_id):
        return next((e for e in self.edges if e.edge_id == edge_id), None)

    def remove_edge(self, edge_id):
        self.edges = [e for e in self.edges if e.edge_id != edge_id]

    def add_edge(self, edge_id, edge_source, edge_target, edge_type):
        self.edges.append(_Edge(edge_id, edge_source, edge_target, edge_type))


MODEL = "Portixol_sand_past_model"


@pytest.fixture
def graph():
    """Due epoche, un documento, un modello. Nessun arco: li scrive il test."""
    return _Graph(
        nodes=[
            _Node("ep_study", "EpochNode", "Study"),
            _Node("ep_post", "EpochNode", "Post-antiquity"),
            _Node("ep_one", "EpochNode", "epoch 1"),
            _Node("D.01", "document", "D.01"),
            _Node(MODEL, "representation_model", "Model for the sand"),
        ],
        edges=[],
    )


def _epoch_edge(graph, epoch_id):
    return [e for e in graph.edges
            if e.edge_source == epoch_id and e.edge_target == MODEL]


# --------------------------------------------------------------------------
# 1. Specchio della scena
# --------------------------------------------------------------------------

def test_sync_writes_the_scene_epochs(graph):
    added, removed = epoch_edges.sync_epoch_edges(
        graph, MODEL, ["epoch 1", "Post-antiquity"])

    assert (added, removed) == (2, 0)
    assert sorted(epoch_edges.epoch_names_for_model(graph, MODEL)) == [
        "Post-antiquity", "epoch 1"]


def test_sync_is_idempotent(graph):
    epoch_edges.sync_epoch_edges(graph, MODEL, ["epoch 1"])
    assert epoch_edges.sync_epoch_edges(graph, MODEL, ["epoch 1"]) == (0, 0)
    assert len(_epoch_edge(graph, "ep_one")) == 1


def test_detached_epoch_does_not_survive(graph):
    """Il cuore del bug: l'epoca tolta in Blender deve sparire dal grafo."""
    epoch_edges.sync_epoch_edges(graph, MODEL, ["epoch 1", "Post-antiquity"])

    added, removed = epoch_edges.sync_epoch_edges(graph, MODEL, ["Post-antiquity"])

    assert (added, removed) == (0, 1)
    assert epoch_edges.epoch_names_for_model(graph, MODEL) == ["Post-antiquity"]
    assert _epoch_edge(graph, "ep_one") == []


def test_no_epoch_is_not_an_epoch(graph):
    """``no_epoch`` è il segnaposto della lista Blender, non un'epoca."""
    added, _ = epoch_edges.sync_epoch_edges(graph, MODEL, ["no_epoch", ""])

    assert added == 0
    assert epoch_edges.epoch_names_for_model(graph, MODEL) == []


def test_unknown_epoch_name_is_skipped_not_invented(graph):
    added, _ = epoch_edges.sync_epoch_edges(graph, MODEL, ["Bronzo medio"])

    assert added == 0
    assert epoch_edges.epoch_names_for_model(graph, MODEL) == []


# --------------------------------------------------------------------------
# 2. Direzione: l'arco si riconosce da entrambi i capi
# --------------------------------------------------------------------------

def test_legacy_reversed_edge_is_seen_and_mirrored(graph):
    """Grafi vecchi possono avere l'arco scritto modello→epoca: va visto."""
    graph.add_edge("legacy", MODEL, "ep_study", "has_representation_model")

    assert epoch_edges.epoch_names_for_model(graph, MODEL) == ["Study"]

    added, removed = epoch_edges.sync_epoch_edges(graph, MODEL, ["Post-antiquity"])

    assert (added, removed) == (1, 1)
    assert epoch_edges.epoch_names_for_model(graph, MODEL) == ["Post-antiquity"]


def test_existing_pair_is_not_duplicated_by_a_different_id(graph):
    """Stessa coppia epoca/modello sotto un id diverso: nessun doppione."""
    graph.add_edge("uuid-ish", MODEL, "ep_post", "has_representation_model")

    added, removed = epoch_edges.sync_epoch_edges(graph, MODEL, ["Post-antiquity"])

    assert (added, removed) == (0, 0)
    assert len(graph.edges) == 1


# --------------------------------------------------------------------------
# 3. Il Documento non si tocca (proprietà specifica della 1.6)
# --------------------------------------------------------------------------

def test_document_edge_survives_the_sync(graph):
    graph.add_edge("doc", "D.01", MODEL, "has_representation_model")
    graph.add_edge("link", MODEL, "L.01", "has_linked_resource")
    epoch_edges.sync_epoch_edges(graph, MODEL, ["epoch 1"])

    epoch_edges.sync_epoch_edges(graph, MODEL, [])

    surviving = sorted((e.edge_source, e.edge_type) for e in graph.edges)
    assert surviving == [("D.01", "has_representation_model"),
                         (MODEL, "has_linked_resource")]


def test_remove_all_epoch_edges_leaves_the_document_edge(graph):
    graph.add_edge("doc", "D.01", MODEL, "has_representation_model")
    epoch_edges.sync_epoch_edges(graph, MODEL, ["epoch 1", "Study"])

    assert epoch_edges.remove_epoch_edges(graph, MODEL) == 2
    assert [e.edge_id for e in graph.edges] == ["doc"]


def test_remove_can_target_one_epoch(graph):
    epoch_edges.sync_epoch_edges(graph, MODEL, ["epoch 1", "Study"])

    assert epoch_edges.remove_epoch_edges(graph, MODEL, ["Study"]) == 1
    assert epoch_edges.epoch_names_for_model(graph, MODEL) == ["epoch 1"]


def test_first_epoch_and_survive_edges_are_epoch_edges_too(graph):
    """``remove_epoch_edges`` copre i tre tipi che legano RM ed epoca, e solo
    quelli: è la pulizia che il riordino delle epoche si aspetta."""
    graph.add_edge("first", MODEL, "ep_one", "has_first_epoch")
    graph.add_edge("surv", MODEL, "ep_post", "survive_in_epoch")
    graph.add_edge("doc", "D.01", MODEL, "has_representation_model")

    removed = epoch_edges.remove_epoch_edges(
        graph, MODEL, edge_types=("has_first_epoch", "survive_in_epoch"))

    assert removed == 2
    assert [e.edge_id for e in graph.edges] == ["doc"]
