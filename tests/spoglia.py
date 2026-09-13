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

## IL DIFETTO CHE QUESTA FUNZIONE AVEVA, e che ha disarmato quattro prove

La prima versione restituiva `"\n".join(tok.string)`: **un token per riga**.
Il che vuol dire che `os.stat` nel sorgente diventava tre righe (`os`, `.`,
`stat`), e quindi `assert "os.stat" not in codice(...)` era **vero per
costruzione** — passava su qualunque file, compreso uno che chiamava `os.stat`
in ogni riga. Nel deck erano vacue così: `os.stat`, `os.path.isfile`,
`os.path.getsize` e `publication_deck.righe` nella prova che difende la regola
architetturale del `draw`, `.alert` in quella del «niente rosso», e l'intera
regex della prova sull'inglese, che cerca `text="…"` e trovava `text`, `=` e la
stringa su tre righe diverse.

È la decisione 21 — *la strumentazione va provata come il codice* — che morde
il codice scritto per rispettarla: una prova che non può fallire non è una
prova, è una dichiarazione. Ora il testo si **ricostruisce alle posizioni
originali**, quindi la forma che si legge nel sorgente è la forma che le
asserzioni vedono; e `test_spoglia.py` prova questa funzione con un file che
contiene di proposito ciò che deve sopravvivere e ciò che deve sparire.
"""

from __future__ import annotations

import io
import pathlib
import token as _token
import tokenize as _tokenize


def codice(percorso) -> str:
    """Il sorgente senza commenti né docstring, **nella sua forma originale**.

    I token si riscrivono dove stavano: stessa riga, stessa colonna. Così
    `os.stat` resta `os.stat` e una prova che lo cerca può fallire — che è
    l'unica ragione per cui una prova esiste.
    """
    testo = pathlib.Path(percorso).read_text(errors="replace")
    righe = testo.splitlines()
    tenuti = []
    #: **Una stringa è una docstring solo se è la PRIMA ISTRUZIONE** di modulo,
    #: classe o funzione: fuori da ogni parentesi, e dopo un a-capo LOGICO
    #: (`NEWLINE`, `INDENT`, `DEDENT`) o all'inizio del file.
    #:
    #: La versione di prima si accontentava di `NL`, che è l'a-capo *dentro*
    #: le parentesi — e così mangiava le chiavi dei dizionari scritti su più
    #: righe. `_ICONA_STATO` usciva senza nessuna delle sue chiavi, e la prova
    #: che cerca le etichette inglesi non poteva trovarle. Un pagliaio che si
    #: porta via anche l'ago.
    profondita = 0
    attesa_docstring, precedente = True, _token.NEWLINE
    for tok in _tokenize.generate_tokens(io.StringIO(testo).readline):
        if tok.type == _token.COMMENT:
            continue
        if tok.type == _token.OP and tok.string in "([{":
            profondita += 1
        elif tok.type == _token.OP and tok.string in ")]}":
            profondita = max(0, profondita - 1)

        docstring = (tok.type == _token.STRING and profondita == 0
                     and attesa_docstring
                     and precedente in (_token.NEWLINE, _token.INDENT,
                                        _token.DEDENT))
        if tok.type not in (_token.NEWLINE, _token.NL, _token.INDENT,
                            _token.DEDENT, _token.ENDMARKER, _token.COMMENT):
            attesa_docstring = False
        if tok.type in (_token.NEWLINE, _token.INDENT, _token.DEDENT):
            attesa_docstring = True
        if tok.type not in (_token.NL,):
            precedente = tok.type
        if docstring:
            continue
        if tok.type in (_token.NEWLINE, _token.NL, _token.INDENT,
                        _token.DEDENT, _token.ENDMARKER):
            continue
        tenuti.append(tok)

    #: una tela di spazi larga quanto il file, e ogni token rimesso dov'era.
    #: Un token multiriga (una stringa fra tripli apici che NON è docstring)
    #: occupa le sue righe intere, e si ricopia com'è.
    tela = [[" "] * (len(r) + 1) for r in righe]
    for tok in tenuti:
        (r0, c0), (r1, _c1) = tok.start, tok.end
        if r1 != r0:
            for indice, pezzo in enumerate(tok.string.splitlines()):
                riga = r0 - 1 + indice
                if 0 <= riga < len(tela):
                    tela[riga] = list(pezzo)
            continue
        riga = tela[r0 - 1]
        for indice, carattere in enumerate(tok.string):
            if c0 + indice < len(riga):
                riga[c0 + indice] = carattere
            else:
                riga.append(carattere)
    return "\n".join("".join(r).rstrip() for r in tela)
