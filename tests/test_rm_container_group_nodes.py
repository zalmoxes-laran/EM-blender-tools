"""La proiezione del container RM nel grafo (EM16-RMNG, lato EM Tools).

Il modulo sotto misura è ``rm_manager/group_nodes.py``, che NON importa ``bpy``
proprio per poter essere misurato qui — la stessa ragione che
``rm_manager/epoch_edges.py`` dà per sé. Il grafo è un doppio minimo: la regola
riguarda quali archi si scrivono e quali NON si toccano, non la libreria.

## LA PROPRIETÀ CHE GOVERNA TUTTO

Il gruppo si affianca e non sostituisce. Ogni prova di rimozione qui dentro
verifica due cose insieme: che sia sparito ciò che doveva sparire, e che siano
RESTATI gli archi d'epoca di ogni membro e gli archi diretti Documento→modello.
La seconda metà è quella che conta, perché è quella che un refactoring
distratto romperebbe senza che nessuno se ne accorga.
"""

import importlib.util
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _load(module_name: str, relative: str):
    spec = importlib.util.spec_from_file_location(module_name, _REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


gn = _load("_emtools_test_group_nodes", "rm_manager/group_nodes.py")


# ── doppio minimo di grafo ──────────────────────────────────────────────────

class FakeNode:
    def __init__(self, node_id, name, node_type, description=""):
        self.node_id = node_id
        self.name = name
        self.node_type = node_type
        self.description = description


class FakeEdge:
    def __init__(self, edge_id, source, target, edge_type):
        self.edge_id = edge_id
        self.edge_source = source
        self.edge_target = target
        self.edge_type = edge_type


class FakeGraph:
    """Quel poco che l'helper usa davvero — e `add_edge` rifiuta un tipo che
    non sia fra quelli che l'helper dichiara, perché il vero `Graph` declassa
    in silenzio a `generic_connection` e una prova che non lo riproduce
    nasconderebbe proprio quel guasto."""

    AMMESSI = (gn.MEMBERSHIP_EDGE, gn.DOC_EDGE, "has_first_epoch",
               "survive_in_epoch")

    def __init__(self):
        self.nodes = []
        self.edges = []

    def find_node_by_id(self, node_id):
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def add_node(self, node):
        self.nodes.append(node)
        return node

    def remove_node(self, node_id):
        n = self.find_node_by_id(node_id)
        if n is None:
            raise KeyError(node_id)
        self.nodes.remove(n)

    def add_edge(self, edge_id, edge_source, edge_target, edge_type):
        assert edge_type in self.AMMESSI, f"tipo non ammesso: {edge_type}"
        e = FakeEdge(edge_id, edge_source, edge_target, edge_type)
        self.edges.append(e)
        return e

    def remove_edge(self, edge_id):
        for e in list(self.edges):
            if e.edge_id == edge_id:
                self.edges.remove(e)
                return
        raise KeyError(edge_id)


def _terne(g):
    return {(e.edge_source, e.edge_target, e.edge_type) for e in g.edges}


def _scena():
    """Un grafo come quelli di oggi: un Document, due epoche, tre modelli con
    i loro archi d'epoca e i loro archi documentali DIRETTI."""
    g = FakeGraph()
    g.add_node(FakeNode("D01", "D.01", "document"))
    g.add_node(FakeNode("EP1", "Roman", "EpochNode"))
    g.add_node(FakeNode("EP2", "Late", "EpochNode"))
    for i in (1, 2, 3):
        g.add_node(FakeNode(f"rm{i}", f"mesh_0{i}", "representation_model"))
        g.add_edge(f"fe{i}", f"rm{i}", "EP1", "has_first_epoch")
        g.add_edge(f"se{i}", f"rm{i}", "EP2", "survive_in_epoch")
        g.add_edge(f"dr{i}", "D01", f"rm{i}", gn.DOC_EDGE)
    return g


# ═══ 1 · L'ID È STABILE, CHE È TUTTO IL REQUISITO ════════════════════════════

def test_L_ID_VIENE_DAL_DOCUMENTO_quando_c_e():
    """Stabile attraverso un rinomino: l'identità di un container è «l'insieme
    che D.01 pubblica», non la stringa che l'utente gli ha dato."""
    a = gn.group_node_id_for("Survey 2015", "D01")
    b = gn.group_node_id_for("Rilievo 2015 (rinominato)", "D01")
    assert a == b == "D01_rmgroup"


def test_E_DALL_ETICHETTA_solo_quando_non_c_e_un_documento():
    """Un container non collegato non ha altro da cui essere identificato — e
    allora un rinomino CAMBIA l'id, che è il motivo per cui `rename_group`
    esiste e non si affida a `ensure_group`."""
    a = gn.group_node_id_for("Survey 2015", "")
    b = gn.group_node_id_for("Survey 2016", "")
    assert a != b
    assert a.startswith("rmgroup_")
    #: e i caratteri che non stanno in un id vengono normalizzati
    assert gn.group_node_id_for("D.01 · Rilievo/2015", "") == \
        "rmgroup_D_01___Rilievo_2015"


# ═══ 2 · CREARE, RINOMINARE, POPOLARE ═══════════════════════════════════════

def test_ENSURE_GROUP_e_idempotente():
    g = _scena()
    n1, creato1 = gn.ensure_group(g, "D01_rmgroup", "Survey 2015")
    n2, creato2 = gn.ensure_group(g, "D01_rmgroup", "Survey 2015")
    assert creato1 is True and creato2 is False
    assert n1 is n2
    assert len([x for x in g.nodes if x.node_type == gn.GROUP_NODE_TYPE]) == 1


def test_ENSURE_GROUP_allinea_l_etichetta_se_e_cambiata():
    g = _scena()
    gn.ensure_group(g, "D01_rmgroup", "Survey 2015")
    nodo, creato = gn.ensure_group(g, "D01_rmgroup", "Rilievo 2015")
    assert creato is False and nodo.name == "Rilievo 2015"


def test_RENAME_cambia_il_nome_e_NON_l_id():
    """Perché cambiare l'id invaliderebbe ogni arco di appartenenza."""
    g = _scena()
    gn.ensure_group(g, "D01_rmgroup", "Survey 2015")
    gn.add_member(g, "D01_rmgroup", "rm1")
    assert gn.rename_group(g, "D01_rmgroup", "Rilievo 2015") is True
    assert gn.find_group(g, "D01_rmgroup").name == "Rilievo 2015"
    assert gn.members_of(g, "D01_rmgroup") == ["rm1"]
    #: e un rinomino a vuoto non mente
    assert gn.rename_group(g, "D01_rmgroup", "Rilievo 2015") is False


def test_UN_MODELLO_STA_IN_UN_SOLO_GRUPPO_e_si_RIFIUTA_di_spostarlo():
    """1:1, e imposto RIFIUTANDO e non spostando.

    Ri-alloggiarlo in silenzio farebbe disaccordare il grafo con `mesh_names`,
    che è autoritativo — e `add_mesh_to_container` rifiuta già lo stesso caso
    lato Blender, con una ragione che l'utente legge.
    """
    g = _scena()
    gn.ensure_group(g, "A", "Survey")
    gn.ensure_group(g, "B", "Reconstruction")
    assert gn.add_member(g, "A", "rm1") is True
    assert gn.add_member(g, "B", "rm1") is False, "l'ha spostato"
    assert gn.group_of_member(g, "rm1") == "A"
    assert gn.members_of(g, "B") == []
    #: …e riaggiungerlo dove già sta non è un errore ma non è un lavoro
    assert gn.add_member(g, "A", "rm1") is False
    assert gn.members_of(g, "A") == ["rm1"]


def test_NON_SI_TAGGA_in_un_gruppo_che_non_esiste():
    g = _scena()
    assert gn.add_member(g, "non_esiste", "rm1") is False
    assert _terne(g) == _terne(_scena())


# ═══ 3 · LA PROPRIETÀ CHIAVE · SI AFFIANCA, NON SOSTITUISCE ═════════════════

def test_PROIETTARE_non_tocca_un_solo_arco_preesistente():
    g = _scena()
    prima = _terne(g)
    assert len(prima) == 9                     # 3 modelli × 3 archi

    gn.ensure_group(g, "D01_rmgroup", "Survey 2015")
    for i in (1, 2, 3):
        gn.add_member(g, "D01_rmgroup", f"rm{i}")
    gn.attach_document(g, "D01_rmgroup", "D01")

    dopo = _terne(g)
    assert prima <= dopo, f"archi persi o cambiati: {prima - dopo}"
    assert dopo - prima == {
        ("rm1", "D01_rmgroup", gn.MEMBERSHIP_EDGE),
        ("rm2", "D01_rmgroup", gn.MEMBERSHIP_EDGE),
        ("rm3", "D01_rmgroup", gn.MEMBERSHIP_EDGE),
        ("D01", "D01_rmgroup", gn.DOC_EDGE),
    }


def test_TOGLIERE_UN_MEMBRO_toglie_SOLO_l_appartenenza():
    """Il modello resta con le sue epoche e col suo arco documentale diretto."""
    g = _scena()
    gn.ensure_group(g, "D01_rmgroup", "Survey 2015")
    gn.add_member(g, "D01_rmgroup", "rm1")
    assert gn.remove_member(g, "D01_rmgroup", "rm1") is True
    assert _terne(g) == _terne(_scena()), "ha toccato altro oltre l'appartenenza"
    assert ("D01", "rm1", gn.DOC_EDGE) in _terne(g)


def test_RIMUOVERE_IL_GRUPPO_lascia_il_Document_e_gli_archi_diretti():
    """Il comportamento che `unregister_container` ha già (Q_B), preservato
    alla lettera: via il gruppo, NON il Document e NON gli archi ai modelli."""
    g = _scena()
    prima = _terne(g)
    gn.ensure_group(g, "D01_rmgroup", "Survey 2015")
    for i in (1, 2, 3):
        gn.add_member(g, "D01_rmgroup", f"rm{i}")
    gn.attach_document(g, "D01_rmgroup", "D01")

    tolti = gn.remove_group(g, "D01_rmgroup")
    assert tolti == 4                          # 3 appartenenze + 1 documentale
    assert gn.find_group(g, "D01_rmgroup") is None
    #: IL DOCUMENT C'È ANCORA
    assert g.find_node_by_id("D01") is not None
    #: …e il grafo è tornato esattamente com'era
    assert _terne(g) == prima
    #: …e ogni modello ha ancora le sue due epoche
    for i in (1, 2, 3):
        fe = {e.edge_target for e in g.edges
              if e.edge_source == f"rm{i}" and e.edge_type == "has_first_epoch"}
        assert fe == {"EP1"}


def test_E_RIMUOVERE_IL_GRUPPO_non_tocca_archi_di_altri_tipi():
    """Conservativo di proposito: un arco di un tipo che questo modulo non
    scrive, e che punta al gruppo, non è suo e resta. È ciò che tiene vera la
    frase «nulla si rimuove» anche in un grafo che questo modulo non ha
    costruito."""
    g = _scena()
    gn.ensure_group(g, "GRP", "Survey")
    g.add_edge("estraneo", "rm1", "GRP", "has_first_epoch")
    gn.remove_group(g, "GRP")
    assert ("rm1", "GRP", "has_first_epoch") in _terne(g)


# ═══ 4 · GLI STATI LEGALI ═══════════════════════════════════════════════════

def test_UN_GRUPPO_VUOTO_e_legale():
    g = _scena()
    gn.ensure_group(g, "GRP", "appena creato")
    assert gn.members_of(g, "GRP") == []
    assert gn.find_group(g, "GRP") is not None


def test_UN_GRUPPO_SENZA_DOCUMENT_e_legale():
    g = _scena()
    gn.ensure_group(g, "rmgroup_Survey", "Survey 2015")
    gn.add_member(g, "rmgroup_Survey", "rm1")
    verso = [e for e in g.edges
             if e.edge_target == "rmgroup_Survey" and e.edge_type == gn.DOC_EDGE]
    assert verso == []
    assert gn.members_of(g, "rmgroup_Survey") == ["rm1"]


def test_ATTACH_DOCUMENT_e_idempotente_e_non_duplica():
    g = _scena()
    gn.ensure_group(g, "GRP", "Survey")
    assert gn.attach_document(g, "GRP", "D01") is True
    assert gn.attach_document(g, "GRP", "D01") is False
    doc = [e for e in g.edges
           if e.edge_target == "GRP" and e.edge_type == gn.DOC_EDGE]
    assert len(doc) == 1


# ═══ 5 · LA RICONCILIAZIONE · MESH_NAMES È L'INGRESSO ═══════════════════════

def test_RECONCILE_aggiunge_cio_che_manca_e_toglie_cio_che_non_c_e_piu():
    """Specchio e non accumulo: l'esito non dipende da quante volte la si
    chiama. La stessa proprietà che `sync_epoch_edges` ha già."""
    g = _scena()
    r1 = gn.reconcile_container(g, "D01_rmgroup", "Survey 2015",
                                ["rm1", "rm2"], doc_node_id="D01")
    assert r1["created"] is True
    assert sorted(r1["added"]) == ["rm1", "rm2"]
    assert r1["doc_attached"] is True
    assert sorted(gn.members_of(g, "D01_rmgroup")) == ["rm1", "rm2"]

    #: seconda chiamata con la stessa lista: NIENTE cambia
    r2 = gn.reconcile_container(g, "D01_rmgroup", "Survey 2015",
                                ["rm1", "rm2"], doc_node_id="D01")
    assert r2 == {"created": False, "added": [], "removed": [], "refused": [],
                  "unknown": [], "doc_attached": False}

    #: la lista cambia → lo specchio segue
    r3 = gn.reconcile_container(g, "D01_rmgroup", "Survey 2015",
                                ["rm2", "rm3"], doc_node_id="D01")
    assert r3["added"] == ["rm3"] and r3["removed"] == ["rm1"]
    assert sorted(gn.members_of(g, "D01_rmgroup")) == ["rm2", "rm3"]


def test_RECONCILE_RIPORTA_e_non_risolve_una_divergenza():
    """Un modello che il grafo dice in un ALTRO gruppo: si segnala, non si
    sposta. Risolverlo vorrebbe dire scegliere quale delle due intenzioni
    dell'utente buttare."""
    g = _scena()
    gn.ensure_group(g, "ALTRO", "Reconstruction")
    gn.add_member(g, "ALTRO", "rm1")
    r = gn.reconcile_container(g, "D01_rmgroup", "Survey 2015",
                               ["rm1", "rm2"], doc_node_id="D01")
    assert r["refused"] == ["rm1"], r
    assert r["added"] == ["rm2"]
    #: e rm1 è rimasto dov'era
    assert gn.group_of_member(g, "rm1") == "ALTRO"


def test_RECONCILE_non_tocca_gli_archi_d_epoca():
    g = _scena()
    prima = _terne(g)
    gn.reconcile_container(g, "D01_rmgroup", "Survey 2015",
                           ["rm1", "rm2", "rm3"], doc_node_id="D01")
    assert prima <= _terne(g)


def test_RECONCILE_SENZA_GRAFO_non_esplode():
    assert gn.reconcile_container(None, "GRP", "x", ["rm1"]) == {
        "created": False, "added": [], "removed": [], "refused": [],
        "unknown": [], "doc_attached": False}


# ═══ 6 · DALLA SELEZIONE 3D AL NODO DI GRUPPO ═══════════════════════════════

def test_PIU_OGGETTI_DELLO_STESSO_CONTAINER_danno_il_gruppo():
    """Il gesto della riunione: «seleziono gli oggetti, vado in graph, sono sul
    nodo»."""
    g = _scena()
    gn.ensure_group(g, "D01_rmgroup", "Survey 2015")
    for i in (1, 2, 3):
        gn.add_member(g, "D01_rmgroup", f"rm{i}")
    assert gn.common_group_of(g, ["rm1", "rm2"]) == "D01_rmgroup"
    assert gn.common_group_of(g, ["rm1", "rm2", "rm3"]) == "D01_rmgroup"


def test_UN_SOLO_OGGETTO_non_risolve_al_gruppo():
    """PLURALE di proposito: è ciò che rende il passo additivo. Con una
    selezione singola la risoluzione di prima resta intatta, perché una
    selezione singola ha già una risposta giusta — il nodo di quell'oggetto."""
    g = _scena()
    gn.ensure_group(g, "D01_rmgroup", "Survey 2015")
    gn.add_member(g, "D01_rmgroup", "rm1")
    assert gn.common_group_of(g, ["rm1"]) is None
    assert gn.common_group_of(g, []) is None
    assert gn.common_group_of(g, None) is None


def test_DUE_CONTAINER_INSIEME_non_hanno_una_risposta_sola():
    """E allora non se ne inventa una: portare l'utente su uno dei due
    sarebbe portarlo dove non ha puntato."""
    g = _scena()
    gn.ensure_group(g, "A", "Survey")
    gn.ensure_group(g, "B", "Reconstruction")
    gn.add_member(g, "A", "rm1")
    gn.add_member(g, "B", "rm2")
    assert gn.common_group_of(g, ["rm1", "rm2"]) is None


def test_E_MODELLI_SENZA_GRUPPO_non_ne_inventano_uno():
    g = _scena()
    assert gn.common_group_of(g, ["rm1", "rm2"]) is None


# ═══ 7 · LA DIVERGENZA TROVATA SUL FILE VERO ════════════════════════════════
#
# Misurato il 10-09-2026 su `GreatTemple_2026_v3_multigraph.blend`, il file di
# lavoro di E.D.: 98 mesh su 99 portano un `em_rm_node_id`, e NESSUNO di quegli
# id risolve in nessuno dei due grafi caricati — i nodi `representation_model`
# non ci sono affatto (0 su 266 nodi, in entrambi i grafi).
#
# Senza le due prove qui sotto la proiezione avrebbe scritto archi di
# appartenenza verso nodi inesistenti: una divergenza da segnalare trasformata
# in un grafo rotto.

def test_UN_MODELLO_CHE_IL_GRAFO_NON_HA_non_si_tagga():
    g = _scena()
    gn.ensure_group(g, "GRP", "Survey")
    assert gn.add_member(g, "GRP", "rm_che_non_esiste") is False
    assert gn.members_of(g, "GRP") == []


def test_E_RECONCILE_LO_SEGNALA_invece_di_scrivere_un_arco_appeso():
    """Si dice, non si scrive — e non si tace: un gruppo vuoto senza spiegazione
    manderebbe l'utente a cercare il difetto dalla parte sbagliata."""
    g = _scena()
    r = gn.reconcile_container(g, "D01_rmgroup", "Survey 2015",
                               ["rm1", "fantasma1", "fantasma2"],
                               doc_node_id="D01")
    assert r["added"] == ["rm1"]
    assert sorted(r["unknown"]) == ["fantasma1", "fantasma2"], r
    assert gn.members_of(g, "D01_rmgroup") == ["rm1"]
    #: e nessun arco punta ai fantasmi
    for e in g.edges:
        assert "fantasma" not in e.edge_source
        assert "fantasma" not in e.edge_target
