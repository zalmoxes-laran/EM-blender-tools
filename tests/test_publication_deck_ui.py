"""P2/D2-D6 · Le convenzioni del pannello, difese strutturalmente.

Un pannello **va guardato**, e lo è stato: tre screenshot in istanza isolata a
**280, 202 e 149 unità** di interfaccia, allegati al referto. Questo file
difende ciò che uno screenshot vede una volta e poi smette di guardare — e in
particolare la regola che a video è costata sei correzioni: **le celle non si
troncano**.

**LA LARGHEZZA STRETTA SI VEDE, e la notte scorsa aveva detto il contrario.**
Il referto di NIGHT-DECK dichiarava impossibile stringere la sidebar dopo
cinque tentativi, mentre la ricetta era già scritta da EM16-UX2 e stava in
`.claude/wip/context/misure-e-tecniche-note.md`: `Region.width` è readonly, e
quello che funziona è **spezzare l'area 3D** (`area_split`) e guardare l'area
NUOVA, la più a destra. Stanotte ha funzionato al primo colpo, con due
inciampi misurati e risolti: lo scatto arriva dal framebuffer e dopo lo split
contiene ancora il disegno di prima (si forzano dei `redraw_timer`), e la
categoria dei pannelli va scelta **dopo** che l'area nuova ha disegnato almeno
una volta, perché quelle categorie sono generate a runtime.

**IL BUDGET DI CARATTERI, e da dove viene.** Non è un'opinione: **38** caratteri
a 280 unità e **14** a 149, misurati a video. Fra i due punti il pannello
interpola (`_quanti_caratteri`) e manda a capo invece di troncare, perché a 149
unità qualunque frase inglese utile è più lunga di quattordici caratteri: o si
manda a capo, o si rinuncia a dirla.

Il budget delle costanti resta a 40 perché quelle stringhe sono scritte per la
larghezza normale; le frasi lunghe passano da `_frase`, che le spezza.
"""

from __future__ import annotations

import ast
import pathlib
import re

from spoglia import codice as _codice

_REPO = pathlib.Path(__file__).resolve().parent.parent
_UI = _REPO / "publication_deck_ui" / "ui.py"
_SORGENTE = _UI.read_text(errors="replace")

#: MISURATI: 55 caratteri si troncano a 280 unità, 36 entrano; il budget vero
#: a quella larghezza è 38.
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


# ── D2/D3 · UIList più scheda ───────────────────────────────────────────────

def test_c_e_una_UIList_e_la_scheda_sta_sotto():
    """La forma che Blender usa per gli elenchi lunghi, e che il RM Manager già
    usa in casa. Il box-per-risorsa faceva quasi trecento righe di pannello su
    un progetto vero."""
    assert "class EM_UL_publication_deck" in _SORGENTE
    assert "template_list(" in _SORGENTE
    assert "def _scheda(" in _SORGENTE


def test_la_riga_della_lista_NON_porta_frasi():
    """Le frasi stanno nella scheda. Una riga che le porta è una riga che si
    tronca, ed è il difetto che questa forma esiste per togliere."""
    i = _SORGENTE.index("def draw_item(")
    corpo = _SORGENTE[i:_SORGENTE.index("class VIEW3D_PT_", i)]
    for vietato in ("_SPIEGA_STATO", "perche", "pronto_perche",
                    "cosa_e_cambiato"):
        assert vietato not in corpo, f"«{vietato}» non va nella riga"


def test_la_riga_porta_l_icona_del_MEDIA():
    i = _SORGENTE.index("def draw_item(")
    corpo = _SORGENTE[i:_SORGENTE.index("class VIEW3D_PT_", i)]
    assert "_ICONA_MEDIA" in corpo


def test_ogni_media_ha_la_sua_icona():
    from importlib.util import module_from_spec, spec_from_file_location
    import sys, types
    pkg = types.ModuleType("emt_pd2"); pkg.__path__ = [str(_REPO)]
    sys.modules["emt_pd2"] = pkg
    for n in ("resource_audit", "publication_gesture", "publication_deck"):
        sp = spec_from_file_location(f"emt_pd2.{n}", _REPO / f"{n}.py")
        m = module_from_spec(sp); sys.modules[f"emt_pd2.{n}"] = m
        sp.loader.exec_module(m)
    media = set(sys.modules["emt_pd2.publication_deck"].MEDIA)
    assert set(_stringhe_di("_ICONA_MEDIA")) == media


# ── D4 · la spunta È il flag che esiste già ─────────────────────────────────

def test_la_spunta_e_l_intenzione_dell_ASSET_non_il_flag_dell_exporter():
    """**Questa prova è cambiata di bersaglio, e la ragione è la decisione 35.**

    DECK2 asseriva che la spunta fosse `RMItem.is_publishable`: giusto nello
    spirito — non inventare uno stato di UI parallelo a uno che esiste — e
    sbagliato nel bersaglio. `is_publishable` lo legge l'**exporter Heriverse**
    e significa «questo RM entra nel bundle»: un'inclusione per un consumatore.
    Un documento DosCo non è un RM, quindi non poteva portarla, e su un
    progetto di diciannove documenti diciannove righe erano senza casella.

    Adesso la spunta è l'intenzione di pubblicare — un fatto dell'asset,
    identico per un pdf e per un glb — e sta in `scene.em_publication_flags`.
    """
    assert 'prop(item, "pubblica"' in _SORGENTE
    assert 'is_publishable' not in _codice(_UI), (
        "il flag dell'exporter non si disegna più nella riga del deck")


def test_il_deck_NON_scrive_is_publishable_da_nessuna_parte():
    """Il flag dell'exporter resta **intatto**: sono due concetti, e il giorno
    che il deck cominciasse a scriverlo tornerebbero a essere uno."""
    import pathlib as _pl
    for f in sorted((_REPO / "publication_deck_ui").glob("*.py")):
        codice = _codice(f)
        assert "is_publishable =" not in codice, f
        assert '"is_publishable"' not in codice or f.name == "ui.py", f


def test_la_spunta_NON_ha_una_memoria_PROPRIA():
    """La prova che il terzo flag non è tornato dalla finestra: `pubblica` è un
    booleano con `get` e `set` — una **finestra** sulla collezione della scena,
    non una copia. Due memorie dello stesso fatto divergono al primo Refresh,
    e le righe del deck sono una cache che si svuota ogni volta."""
    props = _codice(_REPO / "publication_deck_ui" / "properties.py")
    i = props.index("pubblica: BoolProperty(")
    #: fino alla parentesi che chiude, contate: ancorarsi a `# type: ignore`
    #: non si può più, perché `spoglia` toglie i commenti — ed è giusto che li
    #: tolga
    profondita, fine = 0, i
    for fine in range(i, len(props)):
        if props[fine] == "(":
            profondita += 1
        elif props[fine] == ")":
            profondita -= 1
            if profondita == 0:
                break
    dichiarazione = props[i:fine]
    assert "get=" in dichiarazione and "set=" in dichiarazione
    assert "default=" not in dichiarazione, (
        "un default è una memoria, e questa property non ne deve avere una")
    for vietato in ("selezionata", "selected", "scelta:", "da_pubblicare"):
        assert vietato not in props, f"«{vietato}» è un terzo flag"


def test_il_numero_sta_NEL_bottone():
    """Mai un «publish selected» che agisce su una selezione invisibile perché
    si è scrollato: è il modo in cui si pubblica ciò che non si voleva."""
    assert 'text=(f"Publish {deck.spuntati} flagged"' in _SORGENTE


# ── D2 · le frasi vanno a capo, non si troncano ────────────────────────────

def _ui_modulo():
    """Il modulo del pannello caricato SENZA `bpy`: qui si prova `_frase`, che
    è una funzione di stringhe e non ha bisogno di Blender."""
    import sys, types
    from importlib.util import module_from_spec, spec_from_file_location
    if "bpy" not in sys.modules:
        sys.modules["bpy"] = types.ModuleType("bpy")
        sys.modules["bpy"].types = types.SimpleNamespace(
            UIList=type("UIList", (), {}), Panel=type("Panel", (), {}))
    sp = spec_from_file_location("emt_ui_frase", _UI)
    m = module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def test_una_frase_lunga_va_a_capo_e_ogni_riga_sta_nel_budget():
    """A 149 unità entrano quattordici caratteri: qualunque frase inglese utile
    è più lunga. O si manda a capo, o si rinuncia a dirla."""
    class FintaColonna:
        def __init__(s): s.righe = []
        def column(s, **k): return s
        def label(s, text="", icon='NONE'): s.righe.append(text)
    c = FintaColonna()
    ui = _ui_modulo()
    ui._frase(c, "the bytes are not where the locator says", 14)
    assert len(c.righe) > 1
    assert all(len(r) <= 14 for r in c.righe), c.righe
    assert " ".join(c.righe) == "the bytes are not where the locator says"


def test_una_parola_piu_lunga_del_budget_non_sparisce():
    class FintaColonna:
        def __init__(s): s.righe = []
        def column(s, **k): return s
        def label(s, text="", icon='NONE'): s.righe.append(text)
    c = FintaColonna()
    _ui_modulo()._frase(c, "supercalifragilistico", 8)
    assert c.righe == ["supercalifragilistico"]


def test_il_budget_viene_dalle_MISURE_e_non_da_un_numero_a_caso():
    """Due punti misurati a video: 280 unità → 38 caratteri, 149 → 14."""
    ui = _ui_modulo()
    assert ui._caratteri_per(280) == 38
    assert ui._caratteri_per(149) == 14
    #: e a 202 unità — la terza foto — sta in mezzo, come deve
    assert 20 < ui._caratteri_per(202) < 30


# ── D1 · la destinazione non governa più ───────────────────────────────────

def test_la_destinazione_ANNOTA_e_non_spegne_niente():
    """**Decisione 34.** Il verbo del deck è mettere i byte fuori con un
    indirizzo e un'impronta: un fatto sull'asset, identico per un pdf e per un
    glb. «Heriverse sa caricarlo?» è un fatto su una coppia asset-lettore, e
    non deve disabilitare nessun comando.

    Si guarda che nessun `enabled` dipenda dal verdetto del lettore.
    """
    codice = _codice(_UI)
    #: si guardano gli `enabled`, non i rami: scegliere QUALE annotazione
    #: mostrare in base al verdetto è giusto, spegnere un comando no
    for riga in codice.splitlines():
        if ".enabled" in riga or riga.strip().startswith("enabled"):
            assert "pronto" not in riga, riga
    #: l'unico `enabled` del pannello guarda quanto c'è da pubblicare, che è
    #: un fatto sull'asset
    assert "enabled = bool(riga.n_pubblicabili)" in codice


def test_l_enum_del_lettore_si_chiama_per_quello_che_fa():
    props = _codice(_REPO / "publication_deck_ui" / "properties.py")
    assert 'name="Readable by"' in props
    assert 'name="Ready for"' not in props


# ── D5 · il glifo sparisce quando non distingue ────────────────────────────

def test_il_glifo_si_disegna_solo_quando_gli_stati_DIFFERISCONO():
    """Su un progetto di soli documenti è identico su tutte e diciannove le
    righe: una colonna il cui valore non varia mai costa larghezza e non dice
    niente."""
    i = _SORGENTE.index("def draw_item(")
    corpo = _SORGENTE[i:_SORGENTE.index("class VIEW3D_PT_", i)]
    assert "stati_differiscono" in corpo
    #: e l'icona del media resta SEMPRE: è il primo colpo d'occhio
    assert "_ICONA_MEDIA" in corpo


# ── D6 · la riga del grafo è in sola lettura ───────────────────────────────

def test_la_riga_del_grafo_non_ha_verbi():
    """Il deck mostra lo stato del grafo e non lo pubblica: quel gesto è il
    push nella stanza e vive altrove. Un secondo posto da cui spingere sarebbe
    un secondo posto da cui sbagliare."""
    i = _SORGENTE.index("if deck.grafo_frase:")
    pezzo = _SORGENTE[i:i + 300]
    assert "operator(" not in pezzo and "prop(" not in pezzo


def test_il_pannello_NON_apre_connessioni():
    """Le informazioni vengono da quello che la sessione di sync già sa: un
    pannello che apre un socket per disegnarsi blocca Blender quando la rete è
    lenta."""
    codice = _codice(_UI)
    for vietato in ("socket", "urlopen", "requests", "WsClient", "SESSION.join"):
        assert vietato not in codice, vietato


# ── D4 · il disboscamento ──────────────────────────────────────────────────

def test_i_fatti_di_una_distribuzione_stanno_su_UNA_riga():
    """La griglia due-per-due con l'etichetta sopra il valore erano otto righe
    per quattro fatti, uno dei quali vuoto (`Size / —`): due righe per dire
    che non si sa quanto pesa."""
    i = _SORGENTE.index("def _distribuzioni(")
    corpo = _SORGENTE[i:_SORGENTE.index("    def _verbi(", i)]
    assert "_cella(" not in corpo, "le celle a due righe non stanno più qui"
    assert 'join(x for x in fatti if x)' in corpo, (
        "i campi vuoti non si disegnano affatto")


def test_i_verbi_della_scheda_hanno_un_ETICHETTA_quando_ci_sta():
    """A video erano quattro icone mute: il tooltip c'è, ma va cercato col
    mouse fermo, e un verbo che si scopre solo passandoci sopra non si usa."""
    i = _SORGENTE.index("def _verbi(")
    corpo = _SORGENTE[i:i + 1800]
    for verbo in ("Reveal", "Copy URI", "Re-bake", "Publish"):
        assert f'"{verbo}"' in corpo, verbo


def test_la_lista_CRESCE_col_contenuto_fino_a_un_tetto():
    assert "rows=min(max(len(deck.righe)" in _SORGENTE


def test_il_filtro_sta_in_UN_posto_solo():
    """Lo legge la lista che disegna e lo legge l'operatore che scrive in
    blocco: due copie della stessa intenzione divergono al primo cambiamento."""
    ops = _codice(_REPO / "publication_deck_ui" / "operators.py")
    ui = _codice(_UI)
    #: la LISTA filtra davvero (non basta disegnare il campo di ricerca: la
    #: prima versione lo disegnava e la lista mostrava tutto lo stesso)
    assert "def filter_items(" in ui
    assert "publication_flags" in ui and "in_vista(" in ui
    #: e l'operatore chiama la STESSA funzione, non una copia della regola
    assert "in_vista(" in ops
