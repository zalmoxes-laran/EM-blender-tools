"""P4/D5 · «Pronto per chi» — e la porta d'ingresso che mancava.

La colonna «ready for heriverse» rispondeva **yes** a diciannove pdf di un
progetto vero. Un pdf non chiede nessuna capacità nota (`gltf`, `tiles3d`,
`unpackArchive`), quindi la regola di chiusura — «un locator sconosciuto è un
endpoint», che esiste di proposito e va tenuta — lo faceva passare.

Ma la PRIMA riga di `canConsumeResource`, in Heriverse, è un guardiano sul
tipo:

    if (data.url_type !== "3d_model") return { ok: false, why: "not a 3d model" }

e quella riga non era stata letta. Cioè esattamente la malattia contro cui il
commento in testa a `publication_targets` mette in guardia — **due fonti per un
fatto solo** — comparsa una notte dopo averla scritta. Il rimedio non è
ricopiare «3d_model» di qua: è leggere anche il guardiano.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent

_pkg = types.ModuleType("emt_tg"); _pkg.__path__ = [str(ROOT)]
sys.modules["emt_tg"] = _pkg
for _n in ("publication_gesture", "publication_targets"):
    _sp = importlib.util.spec_from_file_location(f"emt_tg.{_n}", ROOT / f"{_n}.py")
    _m = importlib.util.module_from_spec(_sp)
    sys.modules[f"emt_tg.{_n}"] = _m
    _sp.loader.exec_module(_m)                     # type: ignore[union-attr]
PT = sys.modules["emt_tg.publication_targets"]

CAP = {"gltf": "yes", "tiles3d": "unknown", "unpackArchive": "no"}
PDF = {"url": "Schede/US_001.pdf", "url_type": "document",
       "tier": "distribution"}
GLTF = {"url": "models/muro.gltf", "url_type": "3d_model",
        "tier": "distribution"}


# ── il guardiano si LEGGE ───────────────────────────────────────────────────

def test_il_tipo_consumato_si_legge_dal_guardiano():
    testo = 'if (!data || data.url_type !== "3d_model") return {ok:false};'
    assert PT._tipi_consumati(testo) == ["3d_model"]


def test_una_forma_che_non_si_riconosce_non_filtra_NIENTE():
    """Dedurre un elenco da un guardiano che non si è riconosciuto sarebbe
    peggio del difetto che questo parametro chiude."""
    assert PT._tipi_consumati("qualunque altra cosa") == []
    giudica = PT.giudice(CAP, "", [])
    assert giudica(PDF)["ok"] is True


def test_Heriverse_dichiara_di_consumare_SOLO_i_modelli_3d():
    """Letto dal suo sorgente, non ricopiato qui. Se il checkout non c'è, la
    prova non ha niente da dire e si salta invece di fingere."""
    letto = PT.leggi_capacita_heriverse()
    if not letto["capacita"]:
        import pytest
        pytest.skip(letto["perche"])
    assert letto["tipi"] == ["3d_model"]


# ── il verdetto per ciò che sta fuori dal discorso ──────────────────────────

def test_un_pdf_verso_un_visore_di_modelli_e_n_a_e_NON_un_si():
    """La colonna mentiva proprio dove doveva aiutare."""
    esito = PT.giudice(CAP, "", ["3d_model"])(PDF)
    assert esito["ok"] is False and esito["state"] == PT.NA
    assert "3d model" in esito["why"]
    #: e la frase parla di un LETTORE, non di una destinazione: da DECK3 la
    #: destinazione del deck è lo store, e questo annota soltanto
    assert "destination" not in esito["why"]


def test_n_a_NON_e_un_rifiuto():
    """`no` in quella colonna sembra un lavoro da fare, e diciannove documenti
    marcati «no» manderebbero qualcuno a cercare un guasto che non c'è."""
    assert PT.NA not in (PT.YES, PT.NO, PT.UNKNOWN)


def test_un_modello_del_tipo_giusto_passa_il_guardiano():
    assert PT.giudice(CAP, "", ["3d_model"])(GLTF)["ok"] is True


def test_i_tre_stati_di_T3_arrivano_interi_attraverso_il_guardiano():
    tileset = dict(GLTF, url="tilesets/r/tileset.json")
    zip_ = dict(GLTF, url="tilesets/r.zip", packaging="archive")
    assert PT.giudice(CAP, "", ["3d_model"])(tileset)["state"] == PT.UNKNOWN
    assert PT.giudice(CAP, "", ["3d_model"])(zip_)["state"] == PT.NO


def test_un_master_non_e_pronto_per_nessuno_e_la_regola_sta_sul_TIER():
    master = {"url": "blend://s.blend#Object/muro", "url_type": "3d_model",
              "tier": "master"}
    assert PT.giudice(CAP, "", ["3d_model"])(master)["ok"] is False


def test_capacita_illeggibili_danno_UNKNOWN_con_la_ragione():
    esito = PT.giudice({}, "no Heriverse checkout beside this add-on",
                       ["3d_model"])(GLTF)
    assert esito["state"] == PT.UNKNOWN and "checkout" in esito["why"]


def test_il_registro_porta_i_tipi_di_ogni_destinazione():
    registro = PT.destinazioni()
    assert set(registro) == {"heriverse", "room"}
    assert "tipi" in registro["heriverse"] and "tipi" in registro["room"]
    #: la stanza non dichiara nemmeno CHE COSA consuma: nessun filtro, e la
    #: ragione la porta già `perche`
    assert registro["room"]["tipi"] == [] and registro["room"]["perche"]
