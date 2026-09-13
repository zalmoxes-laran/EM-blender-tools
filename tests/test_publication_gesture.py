"""R6 · Quali distribuzioni sono pubblicabili, e perché le altre no.

La «pubblicata» non era raggiungibile da nessun gesto: il master nasce alla
promozione, la distribution al bake, e l'export si fermava a un url relativo.
Questo modulo è la metà che si può provare senza Blender — l'altra metà è
l'operatore, che cuce insieme il caricamento nello store (c'era già) e
`promote_resource` (sa già scrivere locator, checksum e D7).

Le ragioni sono **frasi e non codici** apposta: servono a dire perché un
bottone è spento, e un «no» muto è indistinguibile da un guasto.
"""

from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "em_publication_gesture", ROOT / "publication_gesture.py")
PG = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PG)          # type: ignore[union-attr]


class Finta:
    """Un nodo risorsa quanto basta: questa regola deve girare anche su un
    grafo degradato a `Node` da un import con avvisi, dove i metodi della
    classe non ci sono."""

    def __init__(self, node_id, tipo="resource", **dati):
        self.node_id = node_id
        self.node_type = tipo
        self.data = dati


def test_una_distribution_locale_e_pubblicabile():
    d = Finta("d", url="/prog/models/muro.glb", tier="distribution")
    assert PG.stato_di_pubblicazione(d, esiste=lambda p: True)["si"]


def test_un_master_NON_si_pubblica_e_la_ragione_lo_dice():
    """Archiviare un master è un gesto vero, ma è un altro: pubblicare vuol
    dire mettere a disposizione ciò che gli altri consumano, e un master è ciò
    da cui quello si fa. Confonderli metterebbe un originale fotogrammetrico
    in un bucket per sbaglio."""
    m = Finta("m", url="/Volumi/esterno/rilievo.obj", tier="master")
    esito = PG.stato_di_pubblicazione(m, esiste=lambda p: True)
    assert not esito["si"] and "archived, not published" in esito["perche"]


def test_un_locator_blend_non_si_pubblica_anche_senza_tier_dichiarato():
    """La lettura del tier è la stessa di `effective_tier`: i byte dentro un
    .blend sono un master anche se nessuno l'ha scritto."""
    b = Finta("b", url="blend://studio.blend#Object/muro")
    assert not PG.stato_di_pubblicazione(b)["si"]


def test_gia_pubblicata_e_diverso_da_promessa():
    """Due `no` che si somigliano e non sono la stessa cosa: uno è un lavoro
    finito, l'altro un riferimento di cui nessuno sa cosa dovrebbe trovare."""
    fatta = Finta("p", url="s3://em/aa", checksum="sha256:aa",
                  tier="distribution")
    assert PG.stato_di_pubblicazione(fatta)["perche"] == "already published"
    promessa = Finta("q", url="https://x/a.glb", tier="distribution")
    assert "promise" in PG.stato_di_pubblicazione(promessa)["perche"]


def test_i_byte_che_non_ci_sono_si_dicono():
    d = Finta("d", url="/prog/models/muro.glb", tier="distribution")
    esito = PG.stato_di_pubblicazione(d, esiste=lambda p: False)
    assert not esito["si"] and "bytes are not where" in esito["perche"]


def test_senza_il_fornitore_non_si_guarda_il_disco():
    """La risposta è sull'indirizzo soltanto, che è già metà del lavoro e non
    richiede un disco — serve a un pannello che non deve fare I/O per
    disegnarsi."""
    d = Finta("d", url="/prog/models/muro.glb", tier="distribution")
    assert PG.stato_di_pubblicazione(d)["si"]


def test_il_conto_ha_DUE_basket_e_non_una_lista_filtrata():
    """Chi guarda deve poter chiedere «e le altre?» e ricevere una risposta,
    non un silenzio."""
    nodi = [
        Finta("master", url="blend://a.blend#Object/x"),
        Finta("pronta", url="/p/a.glb", tier="distribution"),
        Finta("fatta", url="s3://em/aa", checksum="sha256:aa"),
        Finta("muta", url=""),
        Finta("non_risorsa", tipo="US"),
    ]
    conto = PG.pubblicabili(nodi, esiste=lambda p: True)
    assert conto["si"] == ["pronta"]
    assert set(conto["no"]) == {"master", "fatta", "muta"}
    assert "non_risorsa" not in conto["no"], "una US non è una risorsa non-pubblicabile"
    assert all(conto["no"].values()), "ogni no porta la sua ragione"


def test_il_nome_vecchio_del_tipo_resta_leggibile():
    """Un grafo caricato senza passare dall'importer porta ancora `link`
    (pre-MIG1), e rifiutarlo qui vorrebbe dire perderlo di vista."""
    vecchia = Finta("v", tipo="link", url="/p/a.glb")
    assert PG.stato_di_pubblicazione(vecchia, esiste=lambda p: True)["si"]


# ── D5 · un locator relativo non dice dove sono i byte ──────────────────────

def test_un_percorso_relativo_si_risolve_contro_le_BASI(tmp_path):
    """Nel modello ci sono due basi diverse, scritte in due posti diversi e per
    due ragioni legittime: la cartella DosCo per i documenti
    (`os.path.relpath(file_path, dosco_dir)` in `functions.py`) e la cartella
    del progetto esportato per le derivate. La cartella di lavoro del processo
    non è mai nessuna delle due."""
    dosco = tmp_path / "DosCo" / "Schede"
    dosco.mkdir(parents=True)
    (dosco / "US_001.pdf").write_bytes(b"%PDF")
    basi = [str(tmp_path / "DosCo"), str(tmp_path / "export")]
    assert PG.risolvi("Schede/US_001.pdf", basi).endswith("US_001.pdf")
    assert PG.risolvi("Schede/assente.pdf", basi) == ""


def test_senza_nessuna_base_la_risposta_e_NON_LO_SO_e_non_un_NO():
    """Il difetto misurato: con `os.path.isfile` nudo un progetto di
    diciannove documenti riportava diciannove volte «the bytes are not where
    the locator says» — un difetto del controllo, non un fatto del progetto.
    Dichiarare falso ciò che non si è potuto misurare è la bugia di T3."""
    assert PG.esistenza([])("Schede/US_001.pdf") is None


def test_un_NON_LO_SO_non_spegne_il_bottone():
    nodo = Finta("d1", url="Schede/US_001.pdf", tier="distribution")
    esito = PG.stato_di_pubblicazione(nodo, esiste=PG.esistenza([]))
    assert esito["si"] is True


def test_un_NO_misurato_invece_lo_spegne():
    nodo = Finta("d1", url="Schede/US_001.pdf", tier="distribution")
    esito = PG.stato_di_pubblicazione(nodo, esiste=lambda p: False)
    assert esito["si"] is False
    assert esito["perche"] == "the bytes are not where the locator says"


def test_un_locator_remoto_non_si_risolve_su_disco():
    for url in ("s3://b/x.glb", "https://x/y.gltf", "blend://a.blend#Object/x"):
        assert PG.risolvi(url, ["/tmp"]) == ""
