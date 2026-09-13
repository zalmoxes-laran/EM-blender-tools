"""D2 · L'intenzione di pubblicare — e perché non è `is_publishable`.

DECK2 aveva legato la spunta del deck a `RMItem.is_publishable` con l'argomento
giusto (non inventare uno stato di UI parallelo a uno che esiste) e il bersaglio
sbagliato: quel flag lo legge l'**exporter Heriverse** e significa «questo RM
entra nel bundle», cioè un'inclusione per un consumatore. Un documento DosCo
non è un RM, quindi non poteva portarlo — e su un progetto di diciannove
documenti diciannove righe erano senza casella.

Sono due fatti (decisione 35). Qui si prova quello nuovo.
"""

from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
_sp = importlib.util.spec_from_file_location(
    "emt_flags", ROOT / "publication_flags.py")
PF = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(PF)          # type: ignore[union-attr]


class Riga:
    def __init__(self, nome, asset_id=None):
        self.name = nome
        self.asset_id = asset_id if asset_id is not None else nome


# ── un flag per volta ───────────────────────────────────────────────────────

def test_accendere_e_spegnere_un_flag():
    assert PF.scegli(set(), "D.01", True) == {"D.01"}
    assert PF.scegli({"D.01"}, "D.01", False) == set()


def test_un_id_vuoto_non_si_scrive():
    """Una chiave vuota nella collezione è una riga che non corrisponde a
    niente, e che nessun Refresh toglierà mai."""
    assert PF.scegli(set(), "", True) == set()
    assert PF.scegli(set(), None, True) == set()


def test_la_funzione_non_MUTA_l_insieme_che_riceve():
    """Torna un insieme nuovo: così la regola si prova senza una scena, e il
    lato Blender resta un traduttore di tre righe."""
    prima = {"a"}
    PF.scegli(prima, "b", True)
    assert prima == {"a"}


# ── D3 · i verbi collettivi ────────────────────────────────────────────────

def test_il_verbo_collettivo_e_ADDITIVO():
    """Il rimedio a una scrittura massiva è l'annullamento, non l'amputazione
    — ma il verbo che aggiunge non deve MAI togliere: chi ha escluso una cosa
    a mano se la ritrova esclusa."""
    assert PF.aggiungi({"a"}, ["b", "c"]) == {"a", "b", "c"}


def test_aggiungere_due_volte_non_cambia_niente():
    assert PF.aggiungi({"a", "b"}, ["a", "b"]) == {"a", "b"}


def test_togliere_e_un_verbo_SUO_e_si_chiama_cosi():
    """Non è il rovescio silenzioso di `aggiungi`: in interfaccia si chiama
    «Clear in view» e non «none»."""
    assert PF.togli({"a", "b", "c"}, ["b"]) == {"a", "c"}


def test_togliere_qualcosa_che_non_c_e_non_solleva():
    assert PF.togli({"a"}, ["z"]) == {"a"}


# ── D3 · «in vista» vuol dire il filtro corrente ───────────────────────────

def test_il_verbo_agisce_su_CIO_CHE_E_IN_VISTA():
    """Chi ha filtrato per «US_0» sta guardando quelli, e un verbo che tocca
    anche il resto agisce su cose che in quel momento non sono sullo schermo."""
    righe = [Riga("D.01"), Riga("D.02"), Riga("muro"), Riga("Reconstruction")]
    assert PF.in_vista(righe, "D.0") == ["D.01", "D.02"]
    assert len(PF.in_vista(righe, "")) == 4


def test_il_filtro_non_guarda_le_maiuscole():
    righe = [Riga("Reconstruction"), Riga("muro")]
    assert PF.in_vista(righe, "recon") == ["Reconstruction"]


def test_in_vista_torna_gli_ID_e_non_i_nomi():
    """La collezione è chiavata per id: un nome può ripetersi, un id no."""
    righe = [Riga("muro", asset_id="muro_model")]
    assert PF.in_vista(righe, "") == ["muro_model"]


def test_una_riga_senza_id_ripiega_sul_nome_e_non_sparisce():
    righe = [Riga("solo-nome", asset_id="")]
    assert PF.in_vista(righe, "") == ["solo-nome"]


# ── l'insieme si legge da una collezione di Blender ────────────────────────

def test_l_insieme_si_legge_da_voci_con_un_nome():
    class Voce:
        def __init__(self, n): self.name = n
    assert PF.insieme([Voce("a"), Voce("b"), Voce("")]) == {"a", "b"}
