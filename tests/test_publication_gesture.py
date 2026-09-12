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
    assert not esito["si"] and "archivia" in esito["perche"]


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
    assert PG.stato_di_pubblicazione(fatta)["perche"] == "già pubblicata"
    promessa = Finta("q", url="https://x/a.glb", tier="distribution")
    assert "promessa" in PG.stato_di_pubblicazione(promessa)["perche"]


def test_i_byte_che_non_ci_sono_si_dicono():
    d = Finta("d", url="/prog/models/muro.glb", tier="distribution")
    esito = PG.stato_di_pubblicazione(d, esiste=lambda p: False)
    assert not esito["si"] and "byte" in esito["perche"]


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
