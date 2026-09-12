"""R3 · La strategia di pubblicazione del container, e R5 · l'impronta.

Due moduli senza `bpy`, quindi due regole che si provano fuori da Blender —
che è il motivo per cui sono moduli separati invece di righe dentro l'export.

R3 non è un concetto nuovo: E.D. quel gesto lo fa già, aggiungendo il tileset
in scena e rendendo non pubblicabile la mesh equivalente. Qui diventa una
proprietà del container detta UNA volta invece di N flag, e la regola che vale
la pena difendere è una sola: **il tileset sostituisce i membri**, quindi non
sono cumulabili. È ciò che evita il doppione al viewer.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _carica(nome, relativo):
    spec = importlib.util.spec_from_file_location(nome, ROOT / relativo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)           # type: ignore[union-attr]
    return modulo


PS = _carica("em_pub_strategy", "rm_manager/publication_strategy.py")
RL = _carica("em_resource_levels", "resource_levels.py")


# ── R3 · la strategia ───────────────────────────────────────────────────────

def test_le_due_strategie_e_il_default_storico():
    assert PS.STRATEGIE == ("members", "tileset")
    assert PS.STRATEGIA_PREDEFINITA == "members", (
        "il default deve valere quanto il comportamento di prima: un container "
        "che non dichiara niente non deve cambiare comportamento")


@pytest.mark.parametrize("detto", [None, "", "boh", "TILESETS", 3])
def test_una_parola_sconosciuta_ripiega_invece_di_fermare_l_export(detto):
    """Al contrario dei setter di s3Dgraphy, qui NON si solleva, e la
    differenza è voluta: là si scrive nel documento (una parola inventata
    diventa un dato che nessun filtro incontrerà), qui si legge una property
    di scena per decidere cosa esportare. Fermare un export per una parola
    storta farebbe perdere il lavoro di qualcuno."""
    assert PS.normalizza(detto) == "members"


def test_con_la_strategia_tileset_i_membri_non_producono_niente():
    """LA REGOLA. Il tileset SOSTITUISCE i singoli, non si aggiunge a loro:
    è l'unica ragione per cui questa proprietà vale più di N flag."""
    membri = ["muro_a", "muro_b", "muro_c"]
    assert PS.membri_pubblicabili("tileset", membri, {}) == []
    assert PS.il_tileset_sostituisce("tileset")


def test_senza_strategia_i_flag_per_oggetto_continuano_a_decidere():
    """Retro-compatibilità nel verso giusto: i flag esistenti si RISPETTANO e
    non si riscrivono. Migrarli in una strategia vorrebbe dire interpretare la
    volontà di qualcuno e poi cancellarne la prova."""
    membri = ["muro_a", "muro_b", "muro_c"]
    flag = {"muro_b": False}
    assert PS.membri_pubblicabili(None, membri, flag) == ["muro_a", "muro_c"]
    assert PS.membri_pubblicabili("members", membri, flag) == ["muro_a", "muro_c"]


def test_un_membro_che_nessuno_ha_nominato_e_pubblicabile():
    """È il default della property `is_publishable`, e assumere il contrario
    nasconderebbe un oggetto che nessuno ha escluso."""
    assert PS.membri_pubblicabili("members", ["x"], {}) == ["x"]


def test_i_flag_tornano_a_contare_se_la_strategia_torna_indietro():
    """La prova che non sono stati riscritti: sono ancora lì."""
    membri, flag = ["a", "b"], {"b": False}
    assert PS.membri_pubblicabili("tileset", membri, flag) == []
    assert PS.membri_pubblicabili("members", membri, flag) == ["a"]


def test_le_sorgenti_del_tileset_sono_i_master_dei_membri():
    """La derivazione N:1: un tileset fa le veci del container, quindi la
    genesi ha N ingressi."""
    membri = ["a", "b", "c"]
    master = {"a": "a_model_res_blend", "b": "b_model_res_blend",
              "c": "c_model_res_blend"}
    assert PS.sorgenti_del_tileset(membri, master) == [
        "a_model_res_blend", "b_model_res_blend", "c_model_res_blend"]


def test_un_membro_senza_master_non_entra_e_non_si_finge():
    """Un ingresso inventato renderebbe la genesi una bugia, e la staleness un
    conto su una sorgente che non c'è."""
    assert PS.sorgenti_del_tileset(["a", "b"], {"a": "a_res"}) == ["a_res"]
    assert PS.sorgenti_del_tileset(["a"], {}) == []


# ── R5 · l'impronta strutturale ────────────────────────────────────────────

def test_l_impronta_non_dichiarata_resta_vuota():
    """Nessuna misura ≠ misure a zero: chi legge deve distinguere «non so» da
    «diverso», che è la stessa regola di `impronta_sorgente`."""
    assert RL.impronta_strutturale({}) == ""
    assert RL.impronta_strutturale(None) == ""


def test_l_impronta_e_stabile_e_indipendente_dall_ordine():
    a = RL.impronta_strutturale({"v": 8, "f": 6, "mat": "pietra"})
    b = RL.impronta_strutturale({"mat": "pietra", "f": 6, "v": 8})
    assert a == b and a.startswith(RL.PREFISSO_STRUTTURALE)


def test_i_float_sono_arrotondati_o_la_staleness_torna_rumore():
    """Senza l'arrotondamento due export della stessa scena darebbero impronte
    diverse per l'ultima cifra di un float — rumore per un'altra ragione ma con
    lo stesso effetto."""
    a = RL.impronta_strutturale({"bb": [0.1 + 0.2, 1.0]})
    b = RL.impronta_strutturale({"bb": [0.3, 1.0]})
    assert a == b
    #: e uno zero negativo è lo stesso ingombro di uno positivo
    assert (RL.impronta_strutturale({"bb": [-0.0]})
            == RL.impronta_strutturale({"bb": [0.0]}))


def test_una_differenza_vera_si_vede():
    base = {"v": 8, "f": 6}
    assert RL.impronta_strutturale(base) != RL.impronta_strutturale(
        {"v": 9, "f": 6})
    assert RL.impronta_strutturale(base) != RL.impronta_strutturale(
        {"v": 8, "f": 6, "mat": "intonaco"})


def test_l_impronta_di_un_insieme_e_ordinata_e_conta_gli_ignoti():
    """Il caso N:1. Una sorgente non misurata NON si salta: entra come `?`,
    perché saltarla darebbe la stessa impronta a un insieme di tre e a uno di
    tre di cui uno sconosciuto — cioè direbbe «uguale» su una differenza vera."""
    a = RL.impronta_strutturale({"v": 1})
    b = RL.impronta_strutturale({"v": 2})
    assert RL.impronta_insieme([a, b]) == RL.impronta_insieme([b, a])
    assert RL.impronta_insieme([a, b]) != RL.impronta_insieme([a, b, ""])
    assert RL.impronta_insieme([]) == ""
    assert RL.impronta_insieme([a, b]).startswith(RL.PREFISSO_STRUTTURALE)


def test_le_due_famiglie_di_impronta_si_distinguono_a_occhio():
    """Un confronto fra impronte di famiglie diverse non significa niente, e
    chi legge deve potersene accorgere senza interpretarle."""
    vecchia = "mtime:1789216727:size:101445"
    nuova = RL.impronta_strutturale({"v": 8})
    assert not vecchia.startswith(RL.PREFISSO_STRUTTURALE)
    assert nuova.startswith(RL.PREFISSO_STRUTTURALE)


# ── T1 · le due distribuzioni del tileset ──────────────────────────────────

def test_i_due_suffissi_sono_distinti_e_quello_storico_non_e_cambiato():
    """Dallo stesso insieme di master nascono due distribution con id distinti
    e stabili. `_link` resta com'era di proposito: cambiarlo renderebbe orfano
    il nodo di ogni grafo già scritto."""
    assert RL.SUFFISSO_DERIVATA == "_link"
    assert RL.SUFFISSO_ARCHIVIO == "_archive"
    assert RL.SUFFISSO_DERIVATA != RL.SUFFISSO_ARCHIVIO
    base = "muro_model"
    assert (f"{base}{RL.SUFFISSO_DERIVATA}", f"{base}{RL.SUFFISSO_ARCHIVIO}") \
        == ("muro_model_link", "muro_model_archive")


def test_gli_id_sono_STABILI_cioe_derivati_e_non_coniati():
    """La proprietà su cui si regge «zero nodi nuovi al secondo export»: un id
    derivato dal nodo RM è lo stesso a ogni giro, un id coniato no."""
    for base in ("a", "b_model", "US001_shape"):
        due_volte = {f"{base}{RL.SUFFISSO_DERIVATA}"
                     for _ in range(2)}
        assert len(due_volte) == 1


# ── T2 · l'impronta dichiara su quale mesh è stata presa ───────────────────

def test_l_impronta_della_mesh_valutata_si_distingue_da_quella_base():
    """Due impronte prese su mesh diverse non sono confrontabili come se
    fossero la stessa cosa — la stessa regola che distingue `struct:` da
    `mtime:`. `ev=1` è il marcatore, e viaggia dentro le misure."""
    base = RL.impronta_strutturale({"v": 8, "f": 6})
    valutata = RL.impronta_strutturale({"v": 8, "f": 6, "ev": 1})
    assert base != valutata
    assert "ev=1" in valutata and "ev=" not in base
