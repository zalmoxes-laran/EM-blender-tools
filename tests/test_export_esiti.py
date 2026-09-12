"""T4 · «fallito» non è «saltato», e un difetto del codice non è un warning.

Regola 24, e la ragione per cui esiste: il ramo del tileset è rimasto morto per
un intero commit range perché `export_tilesets` usava `scene` senza averlo mai
legato, e il `NameError` usciva dall'`except Exception` di turno come un
warning fra i warning. Nessuno se n'è accorto perché **non c'era niente da
accorgersi**: quella riga diceva la stessa cosa che dice un tileset
legittimamente saltato.

Queste prove leggono il SORGENTE, e non è un ripiego: `operator.py` importa
`bpy`, quindi la regola qui si difende strutturalmente — che è anche il modo in
cui si accorge di un gestore nuovo aggiunto domani senza la guardia.
"""

from __future__ import annotations

import ast
import pathlib
import re

_REPO = pathlib.Path(__file__).resolve().parent.parent
_OPERATOR = _REPO / "export_operators" / "heriverse" / "operator.py"
_SORGENTE = _OPERATOR.read_text(errors="replace")


def _classe_export() -> ast.ClassDef:
    albero = ast.parse(_SORGENTE)
    return next(n for n in ast.walk(albero)
                if isinstance(n, ast.ClassDef) and n.name == "EXPORT_OT_heriverse")


def test_l_elenco_dei_difetti_di_programmazione_e_quello_della_decisione_24():
    """Quattro nomi, e sono quelli scritti nella decisione: un elenco che si
    allarga da solo perderebbe il senso di essere un elenco."""
    m = re.search(r"DIFETTI_DI_PROGRAMMAZIONE = \(([^)]*)\)", _SORGENTE, re.S)
    assert m, "la costante non c'è più"
    nomi = {n.strip() for n in m.group(1).replace("\n", " ").split(",") if n.strip()}
    assert nomi == {"NameError", "AttributeError", "TypeError", "ImportError"}


def test_ogni_gestore_per_elemento_lascia_emergere_i_difetti():
    """LA PROVA CHE AVREBBE PRESO IL GUASTO.

    Un `except Exception` che avvolge il tentativo di esportare UN elemento
    deve essere preceduto da un `except self.DIFETTI_DI_PROGRAMMAZIONE`. Se
    non lo è, un `NameError` in quel ramo torna a travestirsi da warning — che
    è letteralmente la storia del tileset.

    Riconosce un gestore per-elemento dal fatto che il suo corpo nomina
    `self._fallito`: è la voce che abbiamo dato ai fallimenti, quindi chi la
    usa sta gestendo un tentativo, non una condizione di contorno.

    **Solo i gestori LARGHI** (`except Exception`, o nudi): un `except OSError`
    non può inghiottire un `NameError`, quindi pretendere la guardia anche lì
    sarebbe cerimonia. La regola difende ciò che il difetto ha insegnato, non
    una forma. (Distinzione arrivata da questa prova stessa, che al primo giro
    segnalava un `except OSError` legittimo.)
    """
    albero = ast.parse(_SORGENTE)
    scoperti = []
    for nodo in ast.walk(albero):
        if not isinstance(nodo, ast.Try):
            continue
        nomi = [ast.unparse(g.type) if g.type is not None else "bare"
                for g in nodo.handlers]
        tipi = []
        for gestore in nodo.handlers:
            sorgente_gestore = ast.dump(gestore)
            tipi.append(("_fallito" in sorgente_gestore, gestore))
        per_elemento = [g for chiama, g in tipi if chiama]
        if not per_elemento:
            continue
        def _largo(g):
            if g.type is None:
                return True
            return "Exception" in ast.unparse(g.type) \
                and "DIFETTI" not in ast.unparse(g.type)
        if not any(_largo(g) for g in nodo.handlers):
            continue          # solo catture strette: non possono mascherare
        #: fra i gestori di questo `try` ce ne deve essere uno che rilancia i
        #: difetti, e deve venire PRIMA (Python prova in ordine)
        indice_difetti = next(
            (i for i, n in enumerate(nomi)
             if "DIFETTI_DI_PROGRAMMAZIONE" in n), None)
        indice_fallito = min(i for i, (chiama, _g) in enumerate(tipi) if chiama)
        if indice_difetti is None or indice_difetti > indice_fallito:
            scoperti.append(f"riga {nodo.lineno}: {nomi}")
    assert not scoperti, (
        "gestori per-elemento senza la guardia sui difetti di programmazione "
        "(o con la guardia dopo):\n" + "\n".join(scoperti))


def test_execute_rilancia_i_difetti_invece_di_riportarli():
    """Il gestore esterno è l'ultima rete: se cattura anche i difetti, un
    `NameError` diventa `{'CANCELLED'}` e una riga di log."""
    i = _SORGENTE.index("    def execute(self, context):")
    corpo = _SORGENTE[i:]
    guardia = corpo.index("except self.DIFETTI_DI_PROGRAMMAZIONE")
    generico = corpo.index("except Exception as e:\n            em_log(f\"\\n!!! Export Failed !!!\"")
    assert guardia < generico, "la guardia deve venire prima del generico"
    frammento = corpo[guardia:generico]
    assert "raise" in frammento, "i difetti si rilanciano, non si riportano"


def test_le_due_voci_esistono_e_sono_diverse():
    classe = _classe_export()
    metodi = {n.name for n in classe.body
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert {"_fallito", "_saltato", "_resoconto_esiti", "_azzera_esiti"} <= metodi


def test_il_conto_finale_NON_passa_dal_filtro_dei_livelli():
    """MISURATO, e per poco non restava una dichiarazione: `_saltato` scrive a
    livello INFO, e `em_log` filtra INFO e DEBUG quando `verbose_logging` è
    spento. Alla prima corsa vera nessuna riga «saltato» compariva — una
    distinzione invisibile, cioè il difetto che T4 doveva togliere.

    Il conto finale esce con `print`, che non passa da nessun filtro."""
    i = _SORGENTE.index("    def _resoconto_esiti(self):")
    corpo = _SORGENTE[i:_SORGENTE.index("\n    def ", i + 10)]
    assert "print(" in corpo, (
        "il conto deve uscire senza passare da em_log, o torna invisibile")
    assert "failed" in corpo and "skipped" in corpo


def test_nessun_sito_di_salto_parla_ancora_con_la_voce_dei_warning():
    """I salti legittimi non devono più uscire come WARNING: erano loro a
    rendere illeggibile il canale, e a far passare inosservato un fallimento
    vero in mezzo."""
    sospetti = []
    for riga in _SORGENTE.splitlines():
        spoglio = riga.strip()
        if spoglio.startswith("#"):
            continue
        if 'em_log(' in spoglio and '"WARNING"' in spoglio:
            if re.search(r"[Ss]kipping|[Nn]ot publishable|NOT FOUND", spoglio):
                sospetti.append(spoglio[:90])
    assert not sospetti, "\n".join(sospetti)
