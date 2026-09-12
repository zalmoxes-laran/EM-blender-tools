"""P2 · Le convenzioni del pannello, difese strutturalmente.

Un pannello **va guardato**, e lo è stato: due screenshot in istanza isolata,
allegati al referto. Questo file difende ciò che uno screenshot vede una volta
e poi smette di guardare — e in particolare la regola che a video è costata
tre correzioni: **le celle non si troncano**.

**IL BUDGET DI CARATTERI, e da dove viene.** Non è un'opinione: a 280 unità di
UI — la larghezza che la sidebar ha nell'istanza di prova — una stringa di 55
caratteri è uscita troncata a metà parola («made, but its locat…ething on this
disk») e una di 36 è entrata intera. Il budget è fissato a 40 per le etichette
a tutta larghezza e a 20 per i valori nelle celle (che stanno in una griglia a
due colonne, quindi metà larghezza): il margine fra 40 e il vero limite è lo
spazio per una sidebar più stretta di quella misurata.

**Perché un budget e non un altro screenshot**: la sidebar NON si stringe da
uno script. Cinque leve provate stanotte e nessuna la muove sotto le 280
unità — `ui_scale` (si auto-dimensiona), `area_split`, `--window-geometry`
(macOS non porta la finestra sotto ~1045 px), `region_scale` in EXEC (è
modale, mossa dal mouse) e la geometria della finestra in punti logici. Un
budget asserito gira a ogni giro di prove; uno screenshot no.
"""

from __future__ import annotations

import ast
import pathlib
import re

from spoglia import codice as _codice

_REPO = pathlib.Path(__file__).resolve().parent.parent
_UI = _REPO / "publication_deck_ui" / "ui.py"
_SORGENTE = _UI.read_text(errors="replace")

#: MISURATI: 55 caratteri si troncano a 280 unità, 36 entrano.
BUDGET_LARGHEZZA_PIENA = 40
BUDGET_CELLA = 20


def _stringhe_di(nome_dizionario):
    albero = ast.parse(_SORGENTE)
    for nodo in albero.body:
        if not isinstance(nodo, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == nome_dizionario
                   for t in nodo.targets):
            continue
        return {k.value: v.value for k, v in zip(nodo.value.keys,
                                                 nodo.value.values)}
    return {}


def test_OGNI_etichetta_del_pannello_sta_nella_larghezza():
    """LA PROVA GENERALE, e le due che ha preso.

    La prima versione guardava solo `_SPIEGA_STATO` e lasciava passare le
    stringhe scritte in linea: a video sono uscite troncate «This graph has no
    re…a model, then export.» e la riga del Refresh. Adesso si guardano TUTTE
    le `label`/`operator`/`prop` del file.

    Si legge con `ast` e non con una regex: le stringhe adiacenti che Python
    concatena da sole (`"una " "frase"`) sono esattamente il modo in cui una
    riga lunga si nasconde da una regex — ed è così che quelle due erano
    passate.
    """
    albero = ast.parse(_SORGENTE)
    lunghe = []
    for nodo in ast.walk(albero):
        if not isinstance(nodo, ast.Call):
            continue
        if getattr(nodo.func, "attr", "") not in ("label", "operator", "prop"):
            continue
        for kw in nodo.keywords:
            if kw.arg not in ("text", "description"):
                continue
            v = kw.value
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                testo = v.value
            elif isinstance(v, ast.JoinedStr):
                #: di una f-string si misura la parte FISSA, che è il minimo
                #: che quella riga occuperà comunque
                testo = "".join(p.value for p in v.values
                                if isinstance(p, ast.Constant))
            else:
                continue
            if len(testo) > BUDGET_LARGHEZZA_PIENA:
                lunghe.append((nodo.lineno, len(testo), testo))
    assert not lunghe, lunghe


def test_le_spiegazioni_di_stato_stanno_nella_larghezza():
    """La regola che è costata una correzione a video: una spiegazione
    troncata è peggio di nessuna spiegazione, perché sembra un guasto."""
    troppo_lunghe = {k: v for k, v in _stringhe_di("_SPIEGA_STATO").items()
                     if len(v) > BUDGET_LARGHEZZA_PIENA}
    assert not troppo_lunghe, troppo_lunghe


def test_ogni_stato_ha_la_sua_spiegazione_e_la_sua_icona():
    from importlib.util import module_from_spec, spec_from_file_location
    import sys, types
    pkg = types.ModuleType("emt_pd"); pkg.__path__ = [str(_REPO)]
    sys.modules["emt_pd"] = pkg
    for n in ("resource_audit", "publication_gesture", "publication_deck"):
        sp = spec_from_file_location(f"emt_pd.{n}", _REPO / f"{n}.py")
        m = module_from_spec(sp); sys.modules[f"emt_pd.{n}"] = m
        sp.loader.exec_module(m)
    stati = set(sys.modules["emt_pd.publication_deck"].STATI)
    assert set(_stringhe_di("_SPIEGA_STATO")) == stati
    assert set(_stringhe_di("_ICONA_STATO")) == stati


def test_NIENTE_ROSSO_per_cio_che_non_e_un_errore():
    """In Blender `alert` è l'errore. Consumarlo per uno stantio — che è un
    lavoro da rifare, non un guasto — insegnerebbe a non leggere il rosso.

    Vale anche per le ICONE: `ERROR` e `CANCEL` sono rosse, e uno stato della
    scala non è nessuna delle due cose.
    """
    codice = _codice(_UI)
    assert ".alert" not in codice, "il deck non usa il rosso"
    icone = set(_stringhe_di("_ICONA_STATO").values())
    assert "ERROR" not in icone and "CANCEL" not in icone, icone


def test_i_bottoni_icona_riempiono_la_larghezza():
    """`grid_flow(even_columns=True)` e non una `row` piatta: misurato in
    EM16-UX2 che in una riga piatta i bottoni solo-icona NON si allargano."""
    assert "grid_flow(row_major=True" in _SORGENTE
    assert "even_columns=True" in _SORGENTE
    assert "ui_units_x" not in _codice(_UI), (
        "la larghezza si dà con grid_flow, non fissandola a mano")


def test_le_celle_sono_su_DUE_righe():
    """L'etichetta sopra, il valore sotto: su una riga sola, a pannello
    stretto, il valore si tronca."""
    i = _SORGENTE.index("def _cella(")
    corpo = _SORGENTE[i:_SORGENTE.index("\nclass ", i)]
    assert corpo.count("label(text=") == 2, (
        "una cella disegna DUE etichette: quella sopra e il valore sotto")


def test_il_pannello_NON_e_chiuso_di_default():
    """La riga di sintesi deve essere sempre visibile, e un pannello chiuso la
    nasconde."""
    assert "DEFAULT_CLOSED" not in _SORGENTE


def test_e_nel_tab_dei_ponti_e_per_primo():
    assert 'bl_category = "EM Bridge"' in _SORGENTE
    assert "bl_order = 0" in _SORGENTE


def test_il_draw_NON_calcola_niente():
    """LA REGOLA ARCHITETTURALE. Il `draw` disegna la cache; il conto costa un
    `os.stat` per derivata e un pannello si ridisegna a ogni movimento del
    mouse.

    Si guardano i nomi che porterebbero il filesystem o il calcolo dentro il
    disegno: se ricompaiono, la misura di stanotte (0,16 ms per draw) smette
    di valere e nessuno se ne accorge finché la scena non è grande.
    """
    codice = _codice(_UI)
    for vietato in ("os.stat", "os.path.isfile", "os.path.getsize",
                    "stato_risorse", "publication_deck.righe",
                    "impronta_", "sha256"):
        assert vietato not in codice, f"«{vietato}» non deve stare nel draw"


def test_l_interfaccia_e_in_inglese():
    """Interfaccia in inglese, tooltip compresi. Si guardano le stringhe che
    finiscono a video — non i commenti, che questo repo scrive in italiano di
    proposito (la regola del pagliaio)."""
    codice = _codice(_UI)
    italiane = []
    for stringa in re.findall(r'text=(?:f?)"([^"]{4,})"', codice):
        if re.search(r"\b(non|della|delle|questo|questa|perché|sono|che)\b",
                     stringa):
            italiane.append(stringa)
    assert not italiane, italiane
