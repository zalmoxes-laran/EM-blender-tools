"""La strumentazione si prova come il codice (decisione 21), e questa è quella
che lo ha imparato nel modo caro.

`spoglia.codice` toglie commenti e docstring perché questo repo **spiega** le
sue scelte per esteso, e ogni asserzione del tipo «questo nome non compare più»
altrimenti morde la riga che racconta perché è stato tolto.

Ma la prima versione univa i token con un a-capo — **un token per riga** — e
quindi `os.stat` nel sorgente usciva come tre righe. Il che rendeva

    assert "os.stat" not in codice(pannello)

**vera per costruzione**: passava anche su un file che chiama `os.stat` a ogni
riga. Quattro asserzioni del deck erano vacue così, fra cui quella che difende
la regola architetturale del `draw`. Una prova che non può fallire non è una
prova: è una dichiarazione con la sintassi di una prova.

E la stessa lettura aveva un secondo buco: trattava come docstring anche le
stringhe dopo un a-capo **dentro le parentesi**, cioè le chiavi dei dizionari
scritti su più righe. Il pagliaio si portava via anche l'ago.
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from spoglia import codice as _codice  # noqa: E402

_ESEMPIO = '''"""La docstring di modulo, che deve sparire."""
import os

# un commento, che deve sparire
TAVOLA = {
    "chiave": "valore",
    "altra": os.sep,
}


def f(percorso):
    """La docstring di funzione, che deve sparire."""
    if os.stat(percorso):        # e anche questo commento
        return TAVOLA["chiave"]
    return layout.alert


class C:
    """Anche questa."""

    def g(self):
        return "una stringa di codice, che deve RESTARE"
'''


def _scrivi(tmp_path):
    f = tmp_path / "esempio.py"
    f.write_text(_ESEMPIO)
    return _codice(f)


def test_una_chiamata_col_punto_resta_INTERA(tmp_path):
    """IL DIFETTO. Se `os.stat` esce spezzato, l'asserzione che lo cerca non
    può fallire, e la regola che difende non è più difesa da niente."""
    spogliato = _scrivi(tmp_path)
    assert "os.stat(" in spogliato
    assert "layout.alert" in spogliato


def test_le_chiavi_di_un_dizionario_su_piu_righe_RESTANO(tmp_path):
    """Il secondo buco: una stringa dopo un a-capo *dentro* le parentesi non è
    una docstring, è una chiave. Toglierla svuota proprio i dizionari che le
    prove dell'interfaccia leggono."""
    spogliato = _scrivi(tmp_path)
    assert '"chiave": "valore"' in spogliato
    assert '"altra"' in spogliato


def test_i_commenti_e_le_docstring_se_ne_vanno(tmp_path):
    spogliato = _scrivi(tmp_path)
    for sparito in ("un commento", "docstring di modulo",
                    "docstring di funzione", "Anche questa",
                    "e anche questo commento"):
        assert sparito not in spogliato, sparito


def test_una_stringa_di_CODICE_resta(tmp_path):
    """`getattr(scene, "em_sync_accept")` è codice vero anche fra virgolette, ed
    è proprio la forma che le asserzioni devono poter mordere."""
    assert "una stringa di codice, che deve RESTARE" in _scrivi(tmp_path)


def test_le_righe_restano_dove_erano(tmp_path):
    """Il numero di righe non cambia: così un `.index()` in una prova indica
    ancora il punto giusto del file vero."""
    spogliato = _scrivi(tmp_path)
    assert len(spogliato.splitlines()) == len(_ESEMPIO.splitlines())


def test_il_risultato_e_ancora_python_valido(tmp_path):
    """Non è un requisito delle asserzioni, ma è la prova che il rimontaggio
    alle posizioni originali non sposta niente."""
    import ast
    ast.parse(_scrivi(tmp_path))


def test_la_regex_dell_inglese_trova_davvero_qualcosa():
    """L'asserzione più silenziosa delle quattro: cercava `text="…"` in un
    testo dove `text`, `=` e la stringa stavano su tre righe diverse, quindi
    non trovava MAI niente e nessuna parola italiana poteva mai fallirla."""
    ui = pathlib.Path(__file__).resolve().parent.parent / "publication_deck_ui" / "ui.py"
    trovate = re.findall(r'text=(?:f?)"([^"]{4,})"', _codice(ui))
    assert len(trovate) >= 5, trovate
