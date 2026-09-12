"""C1 · i due capi si dicono quale documento hanno aperto — e il confronto.

Il gemello di questo file è `EMStudio/frontend/scripts/check-alignment.mjs`, e
la tabella asserita è la stessa nelle due lingue: la regola è troppo piccola per
meritare una dipendenza fra i due repo, e il giorno in cui le due implementazioni
divergono la divergenza è in questi due file.

Quello che si difende qui non è il trasporto — la selezione EM Studio → Blender
è stata MISURATA funzionante il 12-09-2026 — ma la diagnosi: due capi su
documenti diversi producono esattamente il silenzio di un canale chiuso, e fino
a stanotte i due erano indistinguibili.

Gira fuori da Blender: il modulo sotto prova non importa `bpy`, e che il
confronto sia provabile senza Blender è parte del punto (le due frasi che
l'utente legge sono un valore di ritorno, non una stringa costruita in un
`draw`).
"""

from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load():
    """Importa `sync_manager/alignment.py` DA SOLO: l'`__init__` del pacchetto
    tira dentro gli operatori, che importano `bpy`."""
    spec = importlib.util.spec_from_file_location(
        "emtools_alignment", ROOT / "sync_manager" / "alignment.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)          # type: ignore[union-attr]
    return module


A = load()


def test_le_tre_chiavi_sono_quelle_del_filo():
    """Scritte una volta sola, e uguali di là: un refuso qui è un
    disallineamento che non si vede."""
    assert (A.CHIAVE_ID, A.CHIAVE_NOME, A.CHIAVE_TUTTI) == (
        "graph_id", "graph_name", "graph_ids")


def test_stesso_id_stesso_documento_e_non_si_dice_niente():
    r = A.confronta({"graph_id": "g-1", "graph_name": "Aiano"},
                    {"graph_id": "g-1", "graph_name": "Aiano"})
    assert r["allineati"] and r["noto"]
    assert r["frase"] == ""


def test_id_diversi_la_frase_del_prompt():
    r = A.confronta({"graph_id": "g-1", "graph_name": "TempluMare"},
                    {"graph_id": "g-2", "graph_name": "Aiano"})
    assert not r["allineati"]
    # «tu hai aperto X, io Y», e il «tu» è sempre l'altro capo. L'id viaggia
    # accanto al nome DI PROPOSITO: il guasto che questo modulo esiste per
    # vedere è due documenti che si somigliano, e una frase coi soli nomi
    # sarebbe illeggibile proprio nel caso che conta.
    assert r["frase"] == "you have Aiano (g-2) open, I have TempluMare (g-1)"
    assert not r["anche_aperto"]


def test_non_sapere_non_e_un_allarme():
    """La regola su cui il modulo è costruito.

    Un capo che non dichiara niente — una EM Studio di prima di stanotte, un
    Blender senza grafo caricato — è MUTO, non disallineato. Dirgli che sta
    guardando altrove inventerebbe un fatto, e un avviso che scatta senza prove
    è un avviso che si impara a ignorare.
    """
    muto = A.confronta({"graph_id": "g-1"}, {})
    assert muto["allineati"], "un pari muto non è un pari disallineato"
    assert not muto["noto"], "…ma `noto` dice che non si è concluso niente"
    assert muto["frase"] == ""

    nessuno = A.confronta({}, {})
    assert nessuno["allineati"] and not nessuno["noto"]

    senza_di_me = A.confronta({}, {"graph_id": "g-2"})
    assert senza_di_me["allineati"] and not senza_di_me["noto"], (
        "nessun grafo caricato QUI non è un disallineamento")


def test_ce_l_ho_in_un_altra_scheda_e_una_situazione_diversa():
    r = A.confronta({"graph_id": "g-1", "graph_name": "TempluMare",
                     "graph_ids": ["g-1", "g-2"]},
                    {"graph_id": "g-2", "graph_name": "Aiano"})
    assert not r["allineati"] and r["anche_aperto"]
    assert r["frase"].endswith("switch to it"), "la cura nominata è quella vera"


def test_il_nome_e_un_etichetta_mai_il_confronto():
    """Due persone possono avere ciascuna il proprio `TempluMare.em.json`.
    Confrontare i nomi chiamerebbe «stesso documento» proprio il caso che
    questo modulo deve prendere."""
    diversi = A.confronta({"graph_id": "g-1", "graph_name": "TempluMare"},
                          {"graph_id": "g-9", "graph_name": "TempluMare"})
    assert not diversi["allineati"]
    stesso = A.confronta({"graph_id": "g-1"},
                         {"graph_id": "g-1", "graph_name": "X"})
    assert stesso["allineati"]


def test_etichetta():
    assert A.etichetta("0123456789abcdef", "Aiano") == "Aiano (01234567)"
    assert A.etichetta("0123456789abcdef", "") == "0123456789abcdef"
    assert A.etichetta("g-1", "g-1") == "g-1"
    assert A.etichetta("", "") == ""


def test_non_solleva_mai():
    for spazzatura in (None, {}, {"graph_id": None},
                       {"graph_id": "g", "graph_ids": "non-una-lista"}):
        r = A.confronta(spazzatura, spazzatura)
        assert isinstance(r["allineati"], bool)
