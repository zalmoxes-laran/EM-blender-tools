"""Le prove STRUTTURALI estese ai file toccati stanotte (NIGHT-SYNC).

`test_ux_panels_layout.py` ha due prove `ast` nate da tre guasti veri: un
metodo `self._x()` chiamato e non definito, e una funzione di modulo chiamata
dopo che una rimozione ne aveva portato via la definizione. In tutti e tre i
casi il sintomo è lo stesso e non lo prende nessun compilatore: **Blender
smette di disegnare al punto dell'eccezione** e il pannello finisce a metà,
senza dire niente.

Qui la stessa idea, sulla forma che stanotte ho INTRODOTTO: `sync_manager/
panel.py` non chiama funzioni di modulo proprie, chiama `ops.<nome>` su
`operators` importato come modulo, e `em_header_menu.py` fa lo stesso con
`sync_ops.<nome>`. Un rinominamento di là rompe il disegno di qua, e
`py_compile` non se ne accorge perché è un `AttributeError` a tempo di
DISEGNO.

La prima prova è quella che avrebbe preso il guasto; le altre due sono su
quello che C2 e C4 hanno rimosso, perché un nome morto lasciato indietro è
esattamente come sono nate le tre `AttributeError` di cui sopra.
"""

from __future__ import annotations

import ast
import pathlib

_REPO = pathlib.Path(__file__).resolve().parent.parent
_OPERATORS = _REPO / "sync_manager" / "operators.py"

#: chi legge `operators` come modulo, e con che nome
_CONSUMATORI = {
    "sync_manager/panel.py": "ops",
    "em_header_menu.py": "sync_ops",
}


def _codice(percorso: pathlib.Path) -> str:
    """Il sorgente senza commenti NÉ docstring — la regola del pagliaio.

    Presa in faccia una quarta volta scrivendo proprio questo file: `operators.py`
    SPIEGA in due docstring perché `em_sync_direction` e `_sends()` se ne sono
    andati, e un'asserzione «quel nome non c'è più» mordeva la spiegazione
    invece del codice. Un commento onesto non deve poter far fallire una prova
    sull'assenza di un nome.

    Qui si usa `tokenize` e non il taglio a stati riga per riga di
    `test_ux_panels_layout._codice`: quello riceve FETTE di file, che non si
    parsano; questo riceve file interi, dove il tokenizzatore non sbaglia mai.
    Le stringhe NON-docstring restano, perché `getattr(sc, "em_sync_direction")`
    è codice vero anche se il nome sta fra virgolette.
    """
    import io as _io
    import token as _token
    import tokenize as _tokenize

    testo = percorso.read_text(errors="replace")
    fuori, attesa_docstring = [], True
    precedente = None
    for tok in _tokenize.generate_tokens(_io.StringIO(testo).readline):
        if tok.type == _token.COMMENT:
            continue
        if tok.type == _token.STRING and attesa_docstring:
            continue                    # è una docstring: via
        if tok.type == _token.STRING and precedente in (_token.INDENT,
                                                        _token.NEWLINE,
                                                        _token.NL):
            continue                    # docstring di modulo/funzione/classe
        if tok.type not in (_token.NEWLINE, _token.NL, _token.INDENT,
                            _token.DEDENT, _token.ENDMARKER):
            attesa_docstring = False
        if tok.type in (_token.INDENT, _token.NEWLINE, _token.NL):
            attesa_docstring = True
        precedente = tok.type
        fuori.append(tok.string)
    return "\n".join(fuori)


def _nomi_di_modulo(percorso: pathlib.Path) -> set:
    """Tutto ciò che quel modulo espone a livello di modulo."""
    albero = ast.parse(percorso.read_text(errors="replace"))
    nomi = set()
    for n in albero.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nomi.add(n.name)
        elif isinstance(n, ast.Assign):
            nomi |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            nomi.add(n.target.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            nomi |= {(a.asname or a.name).split(".")[0] for a in n.names}
    #: i `global X` di una funzione dichiarano un nome di modulo anche quando
    #: l'assegnazione sta dentro la funzione
    for n in ast.walk(albero):
        if isinstance(n, ast.Global):
            nomi |= set(n.names)
    return nomi


def test_ogni_ops_PUNTO_nome_usato_dal_pannello_esiste_in_operators():
    """LA PROVA CHE PRENDEREBBE IL GUASTO DI STANOTTE.

    Il pannello riscritto legge sette cose da `operators` (`session_mode`,
    `divergenza`, `ULTIMA_TRANSIZIONE`, `disallineamento`,
    `dichiarazione_del_pari`, `porta_sidecar`, `ULTIMO_MESSAGGIO`) e il menu EM
    altre tre. Nessuna di queste è un import che fallisce all'avvio: sono
    attributi risolti mentre Blender disegna, quindi un rinominamento non si
    vede finché qualcuno non apre il pannello.
    """
    esposti = _nomi_di_modulo(_OPERATORS)
    problemi = []
    for rel, alias in _CONSUMATORI.items():
        albero = ast.parse((_REPO / rel).read_text(errors="replace"))
        for n in ast.walk(albero):
            if not (isinstance(n, ast.Attribute)
                    and isinstance(n.value, ast.Name)
                    and n.value.id == alias):
                continue
            if n.attr.startswith("__"):
                continue
            if n.attr not in esposti:
                problemi.append(f"{rel}:{n.lineno} · {alias}.{n.attr} "
                                f"non esiste in sync_manager/operators.py")
    assert not problemi, "\n".join(problemi)


def test_il_vocabolario_della_direzione_non_e_rimasto_indietro():
    """C2 · la DIREZIONE non esiste più: è diventata una politica di ingresso.

    Un nome morto lasciato in un `prop()` o in un `getattr` è esattamente il
    guasto invisibile che le prove `ast` esistono per prendere — e qui in più
    sarebbe una property che non è registrata da nessuno, cioè un pannello che
    solleva mentre disegna.
    """
    morti = ("em_sync_direction", "_sends(", "_receives(", "SYNC_DIRECTIONS")
    problemi = []
    for f in sorted((_REPO / "sync_manager").rglob("*.py")):
        #: solo il CODICE: questo repo SPIEGA in commenti E DOCSTRING perché la
        #: direzione se n'è andata, e un'asserzione sull'assenza del nome
        #: morderebbe la spiegazione invece del codice (la regola del pagliaio)
        codice = _codice(f)
        for nome in morti:
            if nome in codice:
                problemi.append(f"{f.name}: «{nome}» è ancora nel codice")
    assert not problemi, "\n".join(problemi)


def test_le_due_impostazioni_ricollocate_non_sono_piu_property_di_scena():
    """C5 · porta e «materializza all'adozione» sono preferenze dell'add-on.

    Se restassero registrate anche sulla scena ci sarebbero due verità sullo
    stesso fatto, e quella che vince dipenderebbe da quale riga legge chi.
    """
    for f in sorted((_REPO / "sync_manager").rglob("*.py")):
        codice = _codice(f).replace("\n", "")
        assert "bpy.types.Scene.em_sync_port" not in codice, f.name
        assert "bpy.types.Scene.em_materialise_on_adopt" not in codice, f.name
    prefs = (_REPO / "mapping_preferences.py").read_text()
    assert "sync_port:" in prefs and "materialise_on_adopt:" in prefs, (
        "…e devono esistere DA QUALCHE PARTE: spostare non è cancellare")


def test_ogni_property_di_scena_del_sync_e_registrata_e_cancellata():
    """La simmetria register/unregister, che stanotte ho toccato tre volte.

    Una property registrata e non cancellata sopravvive a un reload dell'addon
    e la volta dopo `hasattr` è vero: la definizione nuova non viene applicata
    e si sviluppa contro quella vecchia senza saperlo.
    """
    testo = _OPERATORS.read_text(errors="replace")
    reg = testo[testo.index("\ndef register("):testo.index("\ndef unregister(")]
    unreg = testo[testo.index("\ndef unregister("):]
    registrate = {r.split("bpy.types.Scene.")[1].split(" ")[0].split("=")[0]
                  for r in reg.splitlines() if "bpy.types.Scene.em_" in r}
    cancellate = {r.split("bpy.types.Scene.")[1].split(")")[0].split(" ")[0]
                  for r in unreg.splitlines() if "bpy.types.Scene.em_" in r}
    assert registrate, "nessuna property trovata: la prova si è disallineata"
    assert registrate <= cancellate, (
        f"registrate e mai cancellate: {sorted(registrate - cancellate)}")


def test_lo_spogliatore_non_mangia_il_codice():
    """La prova della prova: uno stripper troppo avido rende verdi per niente
    le due asserzioni sopra, che è il modo in cui una prova smette di valere
    senza che nessuno se ne accorga.

    Il criterio è preciso: le stringhe NON-docstring devono restare, perché
    `getattr(scene, "em_sync_accept")` è codice vero anche se il nome sta fra
    virgolette — ed è proprio la forma che le due asserzioni devono poter
    mordere.
    """
    spoglio = _codice(_OPERATORS)
    #: nomi che nel file esistono SOLO dentro una stringa di codice
    assert '"em_sync_accept"' in spoglio.replace("\n", ""), (
        "una stringa di codice è stata mangiata: l'asserzione sull'assenza "
        "di un nome non morderebbe più un `getattr`")
    #: …e quelli che esistono solo dentro docstring devono essere spariti
    assert "em_sync_direction" in _OPERATORS.read_text()
    assert "em_sync_direction" not in spoglio, (
        "…e le docstring che SPIEGANO la rimozione non devono contare")
    #: e non è sparito tutto
    assert "def" in spoglio and len(spoglio) > 10_000
