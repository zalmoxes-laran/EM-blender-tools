"""D6 · Lo stato del grafo rispetto alla stanza — mostrato, mai pubblicato.

Il grafo è ciò che dice **cosa un glb rappresenta**: senza di lui una derivata
pubblicata è un file orfano. Quindi il deck lo mostra — e non lo pubblica,
perché quel gesto è il push nella stanza e vive in `sync_manager`.

Il prompt chiedeva quattro stati. **I distinguibili sono tre**, e la ragione è
nel codice, non in una mancanza di zelo: in EM Tools ogni mutazione locale
parte nell'istante in cui avviene (`sync_manager/operators.py::emit_op`), non
esiste una coda di op non spedite, e quindi non esiste lo stato «ho roba che la
stanza non ha». Un quarto stato sarebbe una casella che non si accende mai.
"""

from __future__ import annotations

import importlib.util
import pathlib
import queue

ROOT = pathlib.Path(__file__).resolve().parent.parent
_sp = importlib.util.spec_from_file_location(
    "emt_room", ROOT / "publication_room.py")
PR = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(PR)          # type: ignore[union-attr]


class Sessione:
    """Una `RoomSession` quanto basta: il modulo non deve conoscerne la forma
    più di così, ed è per questo che l'adattatore è separato dalla regola."""

    def __init__(self, **kw):
        self.joined = kw.get("joined", False)
        self.room_id = kw.get("room_id")
        self.last_applied = kw.get("last_applied")
        self.error = kw.get("error")
        self.inbox = queue.Queue()
        for _ in range(kw.get("in_attesa", 0)):
            self.inbox.put("{}")


def test_fuori_da_una_stanza_lo_dice_e_non_e_un_errore():
    esito = PR.stato_della_stanza(dentro=False)
    assert esito["stato"] == "no_room"
    assert esito["frase"] == "this study is in no room"
    #: nessuna icona di errore: la maggior parte degli studi vive fuori da una
    #: stanza, e non è un guasto
    assert PR.ICONE["no_room"] not in ("ERROR", "CANCEL")


def test_dentro_e_senza_niente_in_attesa_e_allineato():
    esito = PR.stato_della_stanza(dentro=True, stanza="aiano",
                                  applicato="2026-09-13T20:00:00Z")
    assert esito["stato"] == "aligned"
    assert "aiano" in esito["frase"] and "2026-09-13" in esito["frase"]


def test_appena_arrivati_si_sta_allo_SNAPSHOT_e_non_a_None():
    """«up to None» è un campo vuoto; «at the snapshot» è un'informazione."""
    esito = PR.stato_della_stanza(dentro=True, stanza="aiano")
    assert esito["stato"] == "aligned"
    assert "snapshot" in esito["frase"] and "None" not in esito["frase"]


def test_la_stanza_e_avanti_quando_c_e_roba_NON_APPLICATA():
    """È un fatto osservato — i messaggi sono nella casella — non una stima."""
    esito = PR.stato_della_stanza(dentro=True, stanza="aiano", in_attesa=3)
    assert esito["stato"] == "room_ahead" and "3 changes" in esito["frase"]


def test_un_errore_della_stanza_NON_e_essere_fuori_da_una_stanza():
    """Due cose diverse con due cure diverse, e appiattirle è il difetto che
    NIGHT-SYNC è servita a togliere."""
    esito = PR.stato_della_stanza(dentro=True, errore="token expired")
    assert esito["stato"] == "unknown" and "token expired" in esito["frase"]


def test_gli_stati_dichiarati_sono_quelli_che_si_producono():
    prodotti = {
        PR.stato_della_stanza(dentro=False)["stato"],
        PR.stato_della_stanza(dentro=True, stanza="x")["stato"],
        PR.stato_della_stanza(dentro=True, stanza="x", in_attesa=1)["stato"],
        PR.stato_della_stanza(dentro=True, errore="boom")["stato"],
    }
    assert prodotti == set(PR.STATI_GRAFO)
    assert set(PR.ICONE) == set(PR.STATI_GRAFO)


# ── l'adattatore ───────────────────────────────────────────────────────────

def test_una_sessione_ASSENTE_e_nessuna_stanza_e_non_un_errore():
    assert PR.dalla_sessione(None)["stato"] == "no_room"


def test_l_adattatore_legge_la_sessione_e_basta():
    """Nessuna connessione nuova, nessun client di database: un pannello che
    apre un socket per disegnarsi blocca Blender quando la rete è lenta."""
    s = Sessione(joined=True, room_id="aiano", in_attesa=2)
    assert PR.dalla_sessione(s)["stato"] == "room_ahead"
    s2 = Sessione(joined=True, room_id="aiano",
                  last_applied="2026-09-13T20:00:00Z")
    assert PR.dalla_sessione(s2)["stato"] == "aligned"


def test_una_coda_che_non_sa_dire_quanto_e_lunga_non_vale_ZERO():
    class CodaMuta:
        def qsize(self): raise NotImplementedError

    s = Sessione(joined=True, room_id="aiano")
    s.inbox = CodaMuta()
    #: non saperlo non è «niente in attesa»: si ripiega su zero MA senza
    #: sollevare, e la riga resta leggibile
    assert PR.dalla_sessione(s)["stato"] in PR.STATI_GRAFO
