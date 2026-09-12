"""La REGOLA DEL PAGLIAIO, in un posto solo.

Questo repo SPIEGA le sue scelte nei commenti e nelle docstring, in italiano e
per esteso. Ogni volta che una prova asserisce «questo nome non compare più»,
il nome compare — nella riga che racconta perché è stato tolto. È successo
cinque volte in una settimana: sui commenti (4 ottobre), sulle docstring (UX3,
due volte), sul vocabolario della direzione (NIGHT-SYNC) e sulle regole del
deck (NIGHT-DECK). La quinta è quella che ha fatto estrarre questa funzione.

`tokenize` e non un taglio a stati riga per riga: riceve file INTERI, dove il
tokenizzatore non sbaglia mai. Le stringhe NON-docstring restano, perché
`getattr(scene, "em_sync_accept")` è codice vero anche se il nome sta fra
virgolette — ed è proprio la forma che le asserzioni devono poter mordere.
"""

from __future__ import annotations

import io
import pathlib
import token as _token
import tokenize as _tokenize


def codice(percorso) -> str:
    """Il sorgente senza commenti né docstring."""
    testo = pathlib.Path(percorso).read_text(errors="replace")
    fuori, attesa_docstring, precedente = [], True, None
    for tok in _tokenize.generate_tokens(io.StringIO(testo).readline):
        if tok.type == _token.COMMENT:
            continue
        if tok.type == _token.STRING and attesa_docstring:
            continue
        if tok.type == _token.STRING and precedente in (
                _token.INDENT, _token.NEWLINE, _token.NL):
            continue
        if tok.type not in (_token.NEWLINE, _token.NL, _token.INDENT,
                            _token.DEDENT, _token.ENDMARKER):
            attesa_docstring = False
        if tok.type in (_token.INDENT, _token.NEWLINE, _token.NL):
            attesa_docstring = True
        precedente = tok.type
        fuori.append(tok.string)
    return "\n".join(fuori)
