"""EM16-UX · dove sta ogni pannello, e le regole che il riordino ha fissato.

Le decisioni sono di E.D. (11-09-2026). Queste prove le recintano, e il criterio
che recintano è quello dichiarato nel prompt:

  · i **manager** registrano e curano entità del grafo → in alto;
  · gli **strumenti** producono geometria → annidati sotto un contenitore;
  · la **lente** non crea e non registra, cambia come vedi → accanto a ciò che
    mostra.

Le prove leggono i SORGENTI e non Blender, per una ragione: `bl_category` e
`bl_order` sono DICHIARAZIONI, e ciò che si vuole recintare è la dichiarazione —
un pannello che si sposta perché qualcuno ha cambiato l'ordine di registrazione
è esattamente il guasto che questo riordino chiude. La resa a schermo è stata
verificata in un Blender vero e sta nel referto.
"""

import ast
import pathlib
import re

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent

#: `build/` è un artefatto: contiene una copia di ogni file, e senza escluderla
#: ogni pannello si conterebbe due volte.
_ESCLUSI = ("__pycache__", ".venv", "build/", "tests/", "wheels/")


def _sorgenti():
    for f in sorted(_REPO.rglob("*.py")):
        rel = str(f.relative_to(_REPO))
        if any(x in rel for x in _ESCLUSI):
            continue
        yield rel, f


def _pannelli():
    """Ogni Panel dei sorgenti → categoria, order, parent, label."""
    out = {}
    for rel, f in _sorgenti():
        t = f.read_text(errors="replace")
        if "bl_category" not in t and "bl_parent_id" not in t:
            continue
        for m in re.finditer(r'^class\s+(\w+)\s*\([^)]*Panel[^)]*\)\s*:', t, re.M):
            fine = t.find("\nclass ", m.end())
            corpo = t[m.end(): fine if fine > 0 else len(t)]

            def v(k, _c=corpo):
                mm = re.search(rf'^\s+{k}\s*=\s*(.+)$', _c, re.M)
                if not mm:
                    return ""
                return mm.group(1).split("#")[0].strip().strip("\"'")

            out[m.group(1)] = {
                "file": rel, "categoria": v("bl_category"),
                "order": v("bl_order"), "parent": v("bl_parent_id"),
                "label": v("bl_label"),
            }
    return out


PANNELLI = _pannelli()

#: il sorgente del pannello d'ingresso, che è dove atterra la maggior parte
#: di questi giri. Le prove ne prendono FETTE fra marcatori.
SETUP = (_REPO / "em_setup" / "ui.py").read_text()
#: il menu EM in testata alla 3D View (EM16-UX punto C)
MENU = (_REPO / "em_header_menu.py").read_text()


def _senza_overview():
    """Il pannello `VIEW3D_PT_EM_Overview` NON deve esistere.

    UX3/A l'aveva creato per portarci la scala di promozione. E.D. l'ha
    guardato e l'ha eliminato: «il pannello overview non ha senso per me,
    eliminalo per ora». Questo aiuto esiste perché la rimozione sia
    *asserita* e non solo fatta: se un giorno torna, torna di proposito.
    """
    assert "class VIEW3D_PT_EM_Overview" not in SETUP
    return SETUP


def _carica(nome, rel):
    """Carica per PERCORSO un modulo dell'addon: i suoi `__init__.py`
    importano bpy e fuori da Blender non si caricano."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(nome, _REPO / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _group_nodes():
    return _carica("_gn_ux", "rm_manager/group_nodes.py")


# ═══ A · TRE TAB, NON QUATTRO ════════════════════════════════════════════════

def test_LA_TAB_EM_SHELF_NON_ESISTE_PIU():
    """Il suo pannello si è trasferito, non è sparito: vedi la prova dopo."""
    orfani = {n: p["file"] for n, p in PANNELLI.items()
              if p["categoria"] == "EM Shelf"}
    assert orfani == {}, orfani


def test_E_LE_TAB_SONO_ESATTAMENTE_TRE():
    cat = {p["categoria"] for p in PANNELLI.values() if p["categoria"]}
    assert cat == {"EM", "EM Scene", "EM Bridge"}, sorted(cat)


def test_OGNI_PANNELLO_DICHIARA_LA_SUA_TAB():
    """Nessun pannello senza `bl_category`: l'ordine non deve più dipendere
    dall'ordine di registrazione, ed è la ragione del riordino."""
    muti = {n: p["file"] for n, p in PANNELLI.items()
            if not p["categoria"] and not p["parent"]}
    assert muti == {}, muti


@pytest.mark.parametrize("classe,categoria", [
    # EM · il grafo e come lo guardi
    ("EM_SetupPanel", "EM"),
    ("VIEW3D_PT_EM_GraphInfo", "EM"),
    ("VIEW3D_PT_ToolsPanel", "EM"),
    ("VIEW3D_PT_BasePanel", "EM"),
    ("CF_PT_CronoFilterPanel", "EM"),
    ("VIEW3D_PT_activity_manager", "EM"),
    ("VIEW3D_PT_ParadataPanel", "EM"),
    ("VIEW3D_PT_visual_panel", "EM"),
    ("VIEW3D_PT_proxy_projection_panel", "EM"),
    ("VIEW3D_PT_graphedit_sync", "EM"),
    ("EMTOOLS_PT_conflict_resolution", "EM"),
    # EM Scene · ciò che ha un corpo
    ("VIEW3D_PT_3DDocumentManager", "EM Scene"),
    ("VIEW3D_PT_RM_Manager", "EM Scene"),
    ("VIEW3D_PT_Anastylosis_Manager", "EM Scene"),
    ("VIEW3D_PT_RMDoc_Manager", "EM Scene"),
    ("EM_PT_resources", "EM Scene"),
    ("EM_PT_shelf", "EM Scene"),
    ("EM_PT_proxy_surface_tools", "EM Scene"),
    ("PROXYBOX_PT_main_panel", "EM Scene"),
    ("VIEW3D_PT_SurfaceAreale", "EM Scene"),
    ("VIEW3D_PT_ProxyInflatePanel", "EM Scene"),
    ("EM_PT_georef", "EM Scene"),
    # EM Bridge · i ponti
    ("VIEW3D_PT_ExportPanel", "EM Bridge"),
    ("EM_PT_ExportPanel", "EM Bridge"),
    ("TAPESTRY_PT_main_panel", "EM Bridge"),
    ("VIEW3D_PT_em_sync", "EM Bridge"),
    ("VIEW3D_PT_ServerPanel", "EM Bridge"),
])
def test_OGNI_PANNELLO_E_DOVE_IL_PROMPT_DICE(classe, categoria):
    assert classe in PANNELLI, f"{classe} non esiste più: sparito nel trasloco?"
    assert PANNELLI[classe]["categoria"] == categoria, PANNELLI[classe]


def test_NESSUN_PANNELLO_E_SPARITO_NEL_TRASLOCO():
    """Il conto, perché un trasloco perde le cose in silenzio.

    30 pannelli prima (i 28 di primo livello più i 4 figli del graph editor e
    il `Settings` di Surface Areas, meno i doppi), più due da EM16-UX: il
    contenitore `EM_PT_proxy_surface_tools` e `VIEW3D_PT_EM_GraphInfo`
    (HDT-O, che torna pannello). UX3 ne aveva aggiunto un terzo,
    `VIEW3D_PT_EM_Overview`, e E.D. l'ha eliminato: quindi si torna a 32.
    Nessuno via per sbaglio — verificato contandoli, non stimandoli.
    """
    assert len(PANNELLI) == 32, sorted(PANNELLI)
    assert "VIEW3D_PT_EM_Overview" not in PANNELLI


# ═══ A1 · IL CONTENITORE DEGLI STRUMENTI ═════════════════════════════════════

def test_PROXY_E_SURFACE_TOOLS_e_un_contenitore_con_TRE_figli():
    assert "EM_PT_proxy_surface_tools" in PANNELLI
    cont = PANNELLI["EM_PT_proxy_surface_tools"]
    assert cont["label"] == "Proxy & surface tools"
    assert cont["categoria"] == "EM Scene"
    assert not cont["parent"], "il contenitore non è figlio di nessuno"

    figli = {n for n, p in PANNELLI.items()
             if p["parent"] == "EM_PT_proxy_surface_tools"}
    assert figli == {"PROXYBOX_PT_main_panel", "VIEW3D_PT_SurfaceAreale",
                     "VIEW3D_PT_ProxyInflatePanel"}, figli


def test_PROXY_INFLATE_NON_E_PIU_FIGLIO_DEL_VISUAL_MANAGER():
    """La regola: gonfia geometria, quindi è uno strumento. Il Visual Manager
    è la lente — colora proprietà del grafo — e colorare non è questo."""
    assert PANNELLI["VIEW3D_PT_ProxyInflatePanel"]["parent"] == \
        "EM_PT_proxy_surface_tools"


def test_MA_LA_PROIEZIONE_RESTA_FIGLIA_DEL_VISUAL_MANAGER():
    """L'altra metà della stessa regola: proietta COLORI e non fa geometria,
    quindi resta con la lente."""
    assert PANNELLI["VIEW3D_PT_proxy_projection_panel"]["parent"] == \
        "VIEW3D_PT_visual_panel"


def test_E_IL_VISUAL_MANAGER_RESTA_NEL_TAB_EM():
    """Non per abitudine: colora proprietà del grafo, non oggetti — la mesh è
    la superficie su cui il grafo si rende visibile."""
    assert PANNELLI["VIEW3D_PT_visual_panel"]["categoria"] == "EM"


def test_E_CRONOFILTER_E_ADIACENTE_A_EPOCHS():
    """In multigrafo CronoFilter prende il posto di Epochs: adiacenti, e la
    fusione è una fase successiva (fuori scope, dichiarato)."""
    assert int(PANNELLI["CF_PT_CronoFilterPanel"]["order"]) == \
        int(PANNELLI["VIEW3D_PT_BasePanel"]["order"]) + 1


def test_E_IL_DOCUMENT_MANAGER_E_PRIMO_in_EM_Scene():
    """La sequenza è la scala documenti → modelli → gruppi."""
    ordini = {n: int(p["order"]) for n, p in PANNELLI.items()
              if p["categoria"] == "EM Scene" and p["order"] and not p["parent"]}
    assert min(ordini, key=ordini.get) == "VIEW3D_PT_3DDocumentManager", ordini


# ═══ A2 · RESOURCES & SHELF ══════════════════════════════════════════════════

def test_IL_PANNELLO_NON_SI_CHIAMA_PIU_COME_LA_SUA_TAB():
    p = PANNELLI["EM_PT_resources"]
    assert p["label"] == "Resources & Shelf", p["label"]
    assert p["label"] != p["categoria"]


def test_LO_SHELF_E_UN_FIGLIO_e_conserva_la_sua_UIList():
    """Assorbito come pannello FIGLIO e non come sezione, e la scelta è per la
    UIList col filtro: un `template_list` annidato in un box perde spazio, e il
    funnel del filtro è la prima cosa che lo perde."""
    p = PANNELLI["EM_PT_shelf"]
    assert p["parent"] == "EM_PT_resources", p
    assert p["categoria"] == "EM Scene"
    src = (_REPO / "shelf_tool" / "ui.py").read_text()
    assert 'template_list("SHELF_UL_resources"' in src, "la UIList è sparita"


def test_LE_DUE_SEZIONI_CARTELLO_sono_sparite():
    """Dicevano solo «managed in the Document Manager panel». Un pannello tiene
    solo ciò che possiede."""
    src = (_REPO / "resources_tab" / "ui.py").read_text()
    for morto in ("_draw_documents", "_draw_rm", "show_documents", "show_rm"):
        assert morto not in src, f"{morto} è ancora là"
    assert "Managed in the Document Manager panel" not in src


# ═══ B · L'EM DATA TREE ══════════════════════════════════════════════════════

def test_A5_LA_SCALA_DI_PROMOZIONE_E_CANCELLATA():
    """NIGHT-RIM/A5 · `promotion_scale.py` e `EM_OT_promotion_step_info` sono
    cancellati, e con loro le sei prove che li misuravano.

    Erano codice non raggiungibile dalla rimozione del pannello Overview
    (UX3/A, decisa da E.D. guardandolo). UX3 li aveva lasciati sul disco
    perché «per ora» diceva che la decisione era reversibile, e una prova
    dichiarava quello stato di limbo. A5 chiude il limbo: «cancellali, con le
    prove che li dichiaravano. Git li ricorda.»

    Questa prova resta a impedire che tornino per sbaglio: se un giorno la
    scala serve di nuovo, si riprende da git di proposito.
    """
    assert not (_REPO / "em_setup" / "promotion_scale.py").exists()
    #: sul codice spogliato: il commento che spiega la cancellazione NOMINA
    #: le cose cancellate, ed è giusto che lo faccia (la regola del pagliaio)
    assert "promotion_scale" not in _codice(SETUP)
    assert "promotion_step_info" not in _codice(SETUP)


def test_A_IL_PANNELLO_EM_OVERVIEW_E_STATO_RIMOSSO():
    """Storia intera, perché è la parte che si dimentica.

    UX3/A aveva creato `VIEW3D_PT_EM_Overview`, primo del tab `EM` e aperto,
    per portarci la scala di promozione con la somma su tutti i grafi
    caricati. La ragione era buona (i quattro numeri venivano da scope
    diversi e in multigrafo due cambiavano e due no), e le prove di quel giro
    asserivano pannello, ordine, somme e tooltip.

    E.D. l'ha guardato a video e l'ha eliminato: «il pannello overview non ha
    senso per me, eliminalo per ora». Quindi le prove del pannello sono
    andate via con lui, e resta questa, che asserisce la rimozione.

    La scala NON è stata rimessa nell'EM Data Tree, da cui UX3 l'aveva tolta:
    rimetterla lì sarebbe reintrodurre in un altro posto la cosa eliminata.
    """
    _senza_overview()
    assert "VIEW3D_PT_EM_Overview," not in SETUP, "ancora registrato"
    #: e l'operatore della scala non c'è più affatto (A5)
    assert "promotion_step_info" not in _codice(SETUP)
    #: …e il conto dei pannelli torna a 32
    assert len(PANNELLI) == 32, sorted(PANNELLI)
    assert "VIEW3D_PT_EM_Overview" not in PANNELLI


def test_B2_GRAPH_INFO_e_collassabile_chiuso_e_si_chiama_cosi():
    assert '"show_graph_info"' in SETUP
    assert 'text="Graph info"' in SETUP
    props = (_REPO / "em_props.py").read_text()
    m = re.search(r'show_graph_info: BoolProperty\((.*?)\)  # type: ignore',
                  props, re.S)
    assert m, "la proprietà non c'è"
    assert "default=False" in m.group(1), "aperto di default"
    assert "not of the scene" in m.group(1).lower(), (
        "la descrizione non dice la distinzione fra grafo e scena")


def test_C1_LA_RIGA_DI_COMANDI_RIEMPIE_LA_RIGA():
    """AGGIORNATA DUE VOLTE, e la seconda per una misura che mi ha smentito.

    B3 asseriva la PRESENZA di `ui_units_x`: quello fissava la larghezza di
    ogni bottone, e a video erano sei quadratini ammucchiati a sinistra con
    mezza riga di vuoto a destra. Via `ui_units_x`, quindi, e la prova ne
    asseriva l'assenza — con la motivazione che «i bottoni di una riga si
    spartiscono da soli la larghezza».

    Quella motivazione è FALSA, e lo dice lo scatto del pannello in un Blender
    vero: togliere `ui_units_x` non ha cambiato nulla, i sei bottoni erano
    ancora ammucchiati a sinistra. Un bottone icona-sola (`text=""`) prende la
    sua larghezza naturale — quadrata — e un `row()` piatto non gli passa lo
    spazio che avanza.

    Quello che la distribuisce è un contenitore a CELLE: `grid_flow` con
    `even_columns=True` dà a ognuno la stessa frazione della riga, e nello
    scatto successivo i sei bottoni arrivano da bordo a bordo. È lo stesso
    meccanismo delle quattro celle della scala (C2), che nello stesso scatto
    riempivano già la larghezza.

    AGGIORNATA da UX3/B: le colonne sono **sette** e non sei, perché il
    separatore che stacca il comando distruttivo (Remove graph) occupa una
    cella come gli altri. Con `columns=6` la riga andrebbe a capo — ed è il
    genere di cosa che si vede solo guardando.
    """
    i = SETUP.index("cmd = layout.grid_flow(")
    #: fino alla fine del metodo: da UX3 Remove viene DOPO il separatore,
    #: cioè dopo il menu INFO che prima chiudeva la riga.
    j = SETUP.index("    def draw(self, context):", i)
    blocco = SETUP[i:j]

    assert "ui_units_x" not in blocco, (
        "ui_units_x fissa la larghezza: i bottoni non riempiono più la riga")
    #: il contenitore a celle, che è ciò che DAVVERO riempie la riga
    assert "columns=7" in blocco, "sei comandi più il separatore, sette celle"
    assert "even_columns=True" in blocco, (
        "senza even_columns le celle si dimensionano sul contenuto e i "
        "bottoni tornano stretti")
    #: ogni bottone in una cella sua, sennò finiscono tutti nella prima
    assert blocco.count("cmd.row(align=True)") >= 5, (
        "un bottone per cella: `cmd.operator(...)` diretto li impila in una")
    assert "cmd.scale_y" in blocco, "senza scale_y i bottoni sono bassi"
    #: i sei comandi, tutti icona-sola
    for idname in ("em_tools.add_file", "em_tools.remove_file",
                   "export.em_save", "export.em_saveas",
                   "em.toggle_landscape_mode", "wm.call_menu"):
        assert idname in blocco, idname
    assert 'text=""' in blocco
    #: il separatore stacca il distruttivo, che viene per ULTIMO — e sta
    #: DENTRO la sua cella: come cella a sé mandava la riga a capo su due
    #: righe (misurato: `grid_flow` decideva quattro colonne e ne impilava
    #: tre sotto).
    assert "via.separator()" in blocco, "Remove non è staccato"
    assert "cmd.separator()" not in blocco, (
        "il separatore come CELLA manda la riga a capo")
    assert blocco.index("via.separator()") < blocco.index("em_tools.remove_file")
    assert blocco.index("em_tools.add_file") < blocco.index("via.separator()")

    #: …e nessuna etichetta di testo è tornata nella RIGA (lo stato vuoto ha
    #: il suo bottone con il testo, ed è un'altra cosa: vedi le prove B)
    for morto in ('text="Remove graph"', 'text="Save As…"',
                  'text="Multigraph'):
        assert morto not in blocco, f"{morto} è tornato"


def test_C1_E_I_TOOLTIP_VENGONO_DAGLI_OPERATORI_non_da_una_tupla_morta():
    """B3 portava una tupla di descrizioni scritte a mano che NON venivano mai
    usate: `layout.operator` non accetta un tooltip, e quelle stringhe erano
    dati morti. Misurato in Blender che tutti e cinque gli operatori hanno un
    `bl_description` parlante, quindi la tupla è andata via e i tooltip veri
    restano — senza testo sono l'unica etichetta."""
    i = SETUP.index("cmd = layout.grid_flow(")
    j = SETUP.index('_iop.name = "EM_MT_LandscapeInfo"', i)
    blocco = SETUP[i:j]
    #: nessun ciclo su una tupla di descrizioni
    assert "descrizione" not in blocco
    assert "for idname, icona" not in blocco
    #: …e gli operatori sono chiamati direttamente, uno per cella (C1 li ha
    #: spostati da `cmd.operator(...)` a `cmd.row(align=True).operator(...)`)
    assert blocco.count(".operator(") >= 5


def test_C3_LA_VERSIONE_E_A_DESTRA_col_titolo_intero():
    """AGGIORNATA da EM16-UX2/C3, e la ragione è che B4 era sbagliata a video.

    B4 metteva la versione in `draw_header` con `alignment = 'RIGHT'`. Ma
    `draw_header` disegna nella striscia PRIMA del titolo: allineare a destra
    dentro quella striscia non la sposta a destra del pannello, e il risultato
    era `⧗ 1.6.0-de… EM Data Tree` — la versione troncata davanti al nome.

    `draw_header_preset` è la striscia a destra, quella dove i pannelli nativi
    mettono i preset, e non contende spazio al titolo.
    """
    assert 'bl_label = "EM Data Tree"' in SETUP
    assert 'bl_label = f"EM Data Tree' not in SETUP
    assert "def draw_header_preset" in SETUP
    #: la fetta finiva a `_draw_promotion_scale`, che UX3 ha portato via.
    #: Adesso il marcatore è il `draw_header_preset` dell'EM Data Tree, che
    #: è il SECONDO del file: il primo è quello dell'Overview (UX3/A), e
    #: prendere il primo misurerebbe il pannello sbagliato.
    i = SETUP.index("def draw_header_preset",
                    SETUP.index("class EM_SetupPanel"))
    j = SETUP.index("def _catena", i)
    preset = SETUP[i:j]
    assert "get_em_tools_version()" in preset
    #: …e la clessidra è andata via
    assert "template_icon" not in preset
    #: …e non c'è più un `draw_header` che disegna a sinistra del titolo
    assert "def draw_header(self" not in SETUP


def test_B5_HDT_O_E_UN_PANNELLO_PROPRIO_subito_dopo_il_data_tree():
    p = PANNELLI["VIEW3D_PT_EM_GraphInfo"]
    assert p["categoria"] == "EM"
    assert p["order"] == "2", p
    assert PANNELLI["EM_SetupPanel"]["order"] == "1"
    src = (_REPO / "graph_info" / "ui.py").read_text()
    assert "'DEFAULT_CLOSED'" in src, "aperto di default"
    assert "draw_graph_info_section" not in _codice(SETUP), \
        "ancora disegnato inline dal Data Tree"


def test_B5_E_IL_RENDERER_NON_E_DUPLICATO():
    """Un corpo, due cornici possibili: il pannello chiama lo stesso
    `_draw_body` della sezione."""
    src = (_REPO / "graph_info" / "ui.py").read_text()
    assert src.count("def _draw_body") == 1
    assert "_draw_body(self.layout, context, p)" in src
    assert "_purge_stale_panel" not in src, (
        "il purge cancellerebbe il pannello che questo modulo registra")


def _codice(testo):
    """Il sorgente senza commenti NÉ docstring: la regola del pagliaio.

    Imparata il 4 ottobre sui commenti — questo file PARLA di
    `draw_dtc_section` per spiegare perché il DTC è uscito, e un'asserzione
    sull'assenza di quel nome morderebbe un commento onesto invece del
    codice. ALLARGATA da UX3 alle **docstring**, dopo averci ricascato due
    volte: `ui.py` spiega in una docstring che NON scorre `graph.nodes`, e
    l'asserzione «`graph.nodes` non c'è» mordeva quella spiegazione.

    Le stringhe normali NON si toccano: un'asserzione come «`rmdoc_list` non
    compare» deve poter mordere un `getattr(scene, "rmdoc_list")`, che è
    codice vero anche se il nome è fra virgolette.

    Il taglio delle docstring è a stati sui `\"\"\"`, non via `ast`: questa
    funzione riceve FETTE di file (il corpo di un metodo, il blocco fra due
    marcatori) e una fetta non si parsa.
    """
    fuori, dentro = [], False
    for r in testo.splitlines():
        spoglio = r.strip()
        if dentro:
            if spoglio.endswith('\"\"\"') or spoglio == '\"\"\"':
                dentro = False
            continue
        if spoglio.startswith("#"):
            continue
        if spoglio.startswith('\"\"\"') or spoglio.startswith('r\"\"\"'):
            #: docstring su una riga sola: apre e chiude qui
            corpo = spoglio.lstrip("r")
            if not (len(corpo) > 6 and corpo.endswith('\"\"\"')):
                dentro = True
            continue
        fuori.append(r)
    return "\n".join(fuori)


def test_B6_IL_DTC_E_USCITO_dal_data_tree_e_resta_in_resources():
    assert "draw_dtc_section" in SETUP, "la prosa non spiega più l'uscita?"
    assert "draw_dtc_section" not in _codice(SETUP), \
        "il DTC è ancora disegnato dal Data Tree"
    res = (_REPO / "resources_tab" / "ui.py").read_text()
    assert "draw_dtc_section" in res, "il DTC è sparito anche da Resources"


def test_LA_SEZIONE_UTILS_E_USCITA_dal_pannello():
    codice = _codice(SETUP)
    assert 'text="Utils"' not in codice
    assert "show_advanced_tools" not in codice


def test_B7_NESSUN_BOX_ROSSO_ripete_piu_la_stessa_frase():
    """Cinque punti disegnavano la stessa frase su quattro righe. Adesso una
    riga e il resto dietro il `?`, e l'helper sta in UN posto."""
    ripetizioni = [rel for rel, f in _sorgenti()
                   if 'label(text="The bundled s3dgraphy is out of date.")'
                   in f.read_text(errors="replace")]
    assert ripetizioni == [], ripetizioni
    helpers = (_REPO / "ui_helpers.py").read_text()
    assert "def draw_s3dgraphy_too_old" in helpers
    usanti = [rel for rel, f in _sorgenti()
              if "draw_s3dgraphy_too_old(" in f.read_text(errors="replace")
              and rel != "ui_helpers.py"]
    assert len(usanti) >= 4, usanti


def test_B7_E_IL_ROSSO_E_UN_ARGOMENTO_non_un_default():
    """Il rosso in Blender è l'errore. Una funzione OPZIONALE che non c'è non
    è un errore, e l'helper lo rende una scelta di chi chiama."""
    helpers = (_REPO / "ui_helpers.py").read_text()
    assert "alert=True" in helpers
    res = (_REPO / "resources_tab" / "ui.py").read_text()
    assert "alert=False" in res, "nessun chiamante usa il ramo non-rosso"


# ═══ C · IL MENU EM IN TESTATA ═══════════════════════════════════════════════

def test_C_IL_MENU_SI_AGGANCIA_ALLA_TESTATA_e_si_stacca():
    assert "VIEW3D_MT_editor_menus.append" in MENU
    assert "VIEW3D_MT_editor_menus.remove" in MENU, "non si stacca"


def test_C_LE_TRE_VOCI():
    menu = {n.name for n in ast.walk(ast.parse(MENU))
            if isinstance(n, ast.ClassDef)
            and any(getattr(b, "attr", "") == "Menu" for b in n.bases)}
    assert {"EM_MT_header", "EM_MT_utils", "EM_MT_settings",
            "EM_MT_about"} <= menu, menu
    for voce in ("EM_MT_utils", "EM_MT_settings", "EM_MT_about"):
        assert f'layout.menu("{voce}"' in MENU, voce


def test_C_UTILS_PORTA_i_comandi_che_erano_nel_pannello():
    for op in ("graphml.convert_borders", "create.collection",
               "em.manage_object_prefixes"):
        assert op in MENU, op


def test_C_LO_STATO_LO_RENDE_BLENDER_non_lo_costruiamo_noi():
    """`layout.prop` sul booleano: in un menu Blender rende già la spunta di
    attivo, e costruirla a mano darebbe due verità sullo stesso stato."""
    assert 'layout.prop(em_tools, "experimental_features"' in MENU
    assert "toggle=True" not in MENU
    assert "CHECKBOX" not in MENU


def test_C_ABOUT_dice_DUE_versioni_e_le_URL_vengono_da_version_json():
    assert "get_em_tools_version()" in MENU
    assert "_s3dgraphy_version" in MENU
    assert "version.json" in MENU
    corpo = MENU.split('"""', 2)[2]
    assert "https://" not in corpo, "URL cablata nel codice invece di version.json"


def test_C_E_LE_URL_ESISTONO_DAVVERO_in_version_json():
    import json
    docs = json.loads((_REPO / "version.json").read_text()).get("docs") or {}
    assert docs.get("em_tools", {}).get("url_base", "").startswith("https://")
    assert docs.get("em", {}).get("url_base", "").startswith("https://")


# ═══ D · L'ICONA, NON LA PAROLA ══════════════════════════════════════════════

def test_D_NESSUN_TITOLO_DICE_PIU_EXPERIMENTAL():
    colpe = {n: p["label"] for n, p in PANNELLI.items()
             if "Experimental" in (p["label"] or "")}
    assert colpe == {}, colpe


@pytest.mark.parametrize("rel,classe", [
    ("em_statistics/ui.py", "EM_PT_ExportPanel"),
    ("proxy_to_rm_projection/ui.py", "VIEW3D_PT_proxy_projection_panel"),
    ("tapestry_integration/ui.py", "TAPESTRY_PT_main_panel"),
    ("graph_editor/ui.py", "GRAPHEDIT_PT_main_panel"),
    ("graph_editor/ui.py", "VIEW3D_PT_graphedit_sync"),
])
def test_D_MA_L_ICONA_C_E_nell_header(rel, classe):
    """L'icona c'era GIÀ in tutti e cinque: la parola nel titolo era un
    duplicato. Questa prova tiene la metà che resta."""
    t = (_REPO / rel).read_text()
    m = re.search(rf'^class\s+{classe}\s*\(', t, re.M)
    fine = t.find("\nclass ", m.end())
    corpo = t[m.end(): fine if fine > 0 else len(t)]
    assert "def draw_header" in corpo, f"{classe} non ha draw_header"
    assert "EXPERIMENTAL" in corpo, f"{classe} non mostra l'icona"


def test_D_E_NIENTE_ROSSO_per_sperimentale():
    """In Blender il rosso è l'errore, e questo repository lo usa sul serio nei
    box di indisponibilità. Estenderlo a «sperimentale» insegnerebbe a non
    leggere il rosso, e il giorno dopo si perde un errore vero."""
    for rel, classe in (("em_statistics/ui.py", "EM_PT_ExportPanel"),
                        ("tapestry_integration/ui.py", "TAPESTRY_PT_main_panel")):
        t = (_REPO / rel).read_text()
        m = re.search(rf'^class\s+{classe}\s*\(', t, re.M)
        i = t.index("def draw_header", m.end())
        j = t.index("def draw", i + 10)
        assert "alert" not in t[i:j], f"{classe}: rosso nell'header"


# ═══ E · UN MESSAGGIO SOLO ═══════════════════════════════════════════════════

OPS = (_REPO / "rm_manager" / "container_operators.py").read_text()


def test_E_UN_GRAFO_SENZA_NODI_RM_da_UN_messaggio_non_N():
    """`rmcontainer.project` su un grafo che viene da import GraphML trova zero
    nodi RM — per disegno: `graphml_patcher.INTERNAL_NODE_TYPES` li esclude.
    Novantotto volte la stessa frase non è informazione: è rumore che nasconde
    le altre."""
    assert "has no RM nodes yet" in OPS
    #: il comando da eseguire prima sta nella frase condivisa, che l'operatore
    #: chiama invece di ricomporre (EM16-UX2/C2 l'ha estratta per riusarla nel
    #: tooltip della cella `Models`).
    assert "no_rm_nodes_yet(" in OPS
    assert "Promote to RM" in _group_nodes().no_rm_nodes_yet(1, 1)
    #: e NON elenca un warning per mesh
    cont = (_REPO / "rm_manager" / "containers.py").read_text()
    assert "nessun nodo con questo id nel grafo" not in cont, (
        "torna a fare un warning per mesh")
    assert 'esito["unknown_containers"] += 1' in cont


def test_E_E_NON_CREA_NIENTE_implicitamente():
    i = OPS.index("has no RM nodes yet")
    finestra = OPS[i - 900: i + 900]
    assert "Nothing was created" in finestra
    assert "{'CANCELLED'}" in finestra


def test_E_MA_NEL_CASO_MISTO_la_frase_resta_vera():
    """Se QUALCOSA è stato scritto, «nothing was created» sarebbe falsa: si
    dicono le due cose."""
    i = OPS.index("has no RM nodes yet")
    finestra = OPS[i - 1200: i + 1400]
    assert "Caso misto" in finestra
    assert "But {manca}" in finestra


# ═══ UX3/B · LA VIA PIÙ CORTA PER VEDERE UN CONTENUTO ════════════════════════

def _data_tree():
    """Il corpo della classe `EM_SetupPanel`, senza la tupla `classes`."""
    i = SETUP.index("class EM_SetupPanel")
    return SETUP[i:SETUP.index("classes = (", i)]


def test_B_STATO_VUOTO_una_strada_sola_e_col_testo():
    """Con zero grafi la riga dei sei bottoni NON si disegna.

    Cinque su sei non hanno nulla su cui agire, e sei icone uguali di cui una
    sola funziona sono un indovinello. Al suo posto un bottone largo CON IL
    TESTO: è l'unico punto del pannello dove il testo torna, perché è l'unica
    cosa da fare e non c'è una riga da riempire.
    """
    corpo = _data_tree()
    assert 'if not _stato["ha_grafo"]:' in corpo
    i = corpo.index('if not _stato["ha_grafo"]:')
    j = corpo.index("else:", i)
    vuoto = corpo[i:j]
    assert 'text="Add graph"' in vuoto, "lo stato vuoto vuole il TESTO"
    assert "em_tools.add_file" in vuoto
    #: e la riga dei sei sta nell'`else`, cioè non si disegna quando è vuoto
    assert "_riga_comandi" in corpo[j:j + 200]
    assert "_riga_comandi" not in vuoto


def test_B_LA_GUIDA_USA_draw_requirement_row_e_SPARISCE():
    """Tre passi numerati, col loro stato, e `inactive` per quelli non ancora
    valutabili — che è la distinzione fra «sbagliato» e «tocca più tardi».

    `ui_helpers.draw_requirement_row` esiste già e fa esattamente questo:
    scriverne una seconda vorrebbe dire tenerne allineate due.
    """
    corpo = _data_tree()
    #: AGGIORNATA: la condizione non è più «l'attivo non è caricato» ma
    #: «nessun grafo caricato in tutto», cioè SOLO PER IL PRIMO GRAFO. Con la
    #: condizione di prima la guida tornava quando si aggiungeva il secondo
    #: grafo, e lì è pleonastica: la sequenza la si è appena fatta.
    assert 'if not _stato["grafi_caricati"] and self._guida_richiesta():' in corpo
    i = corpo.index('if not _stato["grafi_caricati"]')
    assert "self._guida(layout, _stato)" in corpo[i:i + 200]
    assert 'if not _stato["caricato"]:' not in corpo, (
        "la guida non deve tornare per il secondo grafo")

    i = corpo.index("def _guida")
    j = corpo.index("def _op_carica", i)
    guida = corpo[i:j]
    assert "from ..ui_helpers import draw_requirement_row" in guida, (
        "la guida deve riusare l'aiuto che esiste")
    #: tre chiamate. L'`import` non ha la parentesi, quindi non conta qui.
    assert guida.count("draw_requirement_row(") == 3, "tre passi"
    #: i tre passi, nell'ordine della catena
    for n, etichetta in ((1, '"Add graph"'), (2, '"Set path"'), (3, '"Load"')):
        assert f"{n}, {etichetta}" in guida, f"passo {n}"
    #: …e i passi 2 e 3 si dimmano finché il precedente non è fatto
    assert 'inactive=not stato["ha_grafo"]' in guida
    assert 'inactive=not stato["ha_path"]' in guida


def test_B_IL_CARICAMENTO_E_IN_EVIDENZA_finche_non_e_fatto():
    """Con il path dato e il grafo non caricato, Load è a tutta larghezza e
    col testo; a grafo caricato torna icona nella riga, come Reload."""
    corpo = _data_tree()
    assert 'if _stato["ha_path"] and not _stato["caricato"]:' in corpo
    i = corpo.index('if _stato["ha_path"] and not _stato["caricato"]:')
    evidenza = corpo[i:i + 400]
    assert 'testo="Load"' in evidenza
    assert "scale_y" in evidenza, "in evidenza vuol dire anche più alto"
    #: …e DOPO il Path, che è l'ordine in cui si legge la catena: a video il
    #: bottone sopra il campo da riempire prima invertiva i due passi
    assert corpo.index('"graphml_path", text="Path"') < i

    #: e nella riga, senza testo (quindi icona)
    i = corpo.index("def _riga_comandi")
    j = corpo.index("    def draw(self, context):", i)
    riga = corpo[i:j]
    #: nella riga, senza `testo=` — quindi icona
    assert "self._op_carica(ricarica, stato)" in riga
    assert "testo=" not in riga, "nella riga il caricamento è icona, non testo"


def test_B_IL_DISPATCH_DEL_CARICAMENTO_STA_IN_UN_POSTO_SOLO():
    """Due importer e non uno: un entry `em.json` passato all'importer GraphML
    verrebbe parsato come XML. E il nome della proprietà dell'indice è
    DIVERSO fra i due (`file_index` contro `graphml_index`), che è la ragione
    per cui il dispatch sta in una funzione sola invece che copiato nei due
    punti che lo usano."""
    corpo = _data_tree()
    i = corpo.index("def _op_carica")
    j = corpo.index("def _riga_comandi", i)
    op = corpo[i:j]
    assert "import.em_emjson" in op and "import.em_graphml" in op
    assert "op.file_index" in op and "op.graphml_index" in op
    #: e nessun altro punto del pannello chiama gli importer a mano
    resto = corpo[:i] + corpo[j:]
    assert "import.em_graphml" not in _codice(resto)


def test_B_SPENTO_CON_LA_RAGIONE_non_spento_muto():
    """`poll_message_set` è il modo di Blender per dire nel tooltip PERCHÉ un
    bottone è spento, e in casa era già usato
    (`stratigraphy_manager/operators.py`). I poll di Save/Save As già
    spegnevano i bottoni; non dicevano la ragione."""
    src = (_REPO / "export_operators" / "exporter_emjson.py").read_text()
    assert src.count("cls.poll_message_set(") == 2, (
        "Save e Save As, entrambi")
    assert "add a graph, set its Path, then Load" in src, (
        "il messaggio deve dire la SEQUENZA, non solo che manca qualcosa")


def test_B_LO_STATO_DELLA_CATENA_SI_CALCOLA_UNA_VOLTA():
    """Se ogni pezzo se lo ricalcolasse, i pezzi potrebbero non essere
    d'accordo fra loro — ed è il modo in cui un'interfaccia a stati si
    contraddice a video."""
    corpo = _data_tree()
    assert corpo.count("self._catena(") == 1, "un solo calcolo per ridisegno"
    i = corpo.index("def _catena")
    j = corpo.index("def _guida", i)
    catena = corpo[i:j]
    #: `caricato` usa lo stesso test della UIList: presente E con nodi
    assert "original_id" in catena, "ripiego della UIList dopo un rename"
    assert 'getattr(g, "nodes", None)' in catena, (
        "un grafo presente ma VUOTO non è caricato: lo dice anche "
        "em_tools.populate_lists, che lo rifiuta")
    for chiave in ("ha_grafo", "ha_path", "caricato", "emjson"):
        assert f'"{chiave}"' in catena, chiave


# ═══ UX3/C · L'ICONA DELLE US ════════════════════════════════════════════════

def test_C_US_USV_USA_proxies_rows_il_segno_di_casa():
    """`proxies_rows` (64×64, quadrata) è la stessa che lo Stratigraphy
    Manager mostra accanto a «Total Rows», quindi è già il segno di casa per
    «unità stratigrafiche». Sostituisce il `MESH_CUBE` di UX2, che era un
    ripiego preso dal contatore `US:` del Document Manager.

    E NON `US.png`, che è un glifo di palette 253×128: schiacciato in uno
    slot quadrato si legge come una barretta rossa — misurato in UX2.
    """
    i = SETUP.index("def _draw_graph_info")
    j = SETUP.index("\nclass ", i)
    gi = SETUP[i:j]
    assert '_kw_icona("proxies_rows"' in gi
    assert '_kw_icona("US"' not in gi, "il glifo di palette non torna"
    #: le altre celle sistemate in UX2 non si toccano
    assert "icon='TIME'" in gi, "Epochs resta TIME: un'epoca in icons/ non c'è"
    assert "icon='PROPERTIES'" in gi
    assert '_kw_icona("document"' in gi

    #: e il file è davvero quadrato, altrimenti è lo stesso errore di prima
    from struct import unpack
    d = (_REPO / "icons" / "proxies_rows.png").read_bytes()[:33]
    w, h = unpack(">II", d[16:24])
    assert w == h, f"proxies_rows è {w}x{h}: non è un'icona"


# ═══ UX3/D · LA CATENA DEL DOCUMENTO ════════════════════════════════════════

DOCUI = (_REPO / "document_manager" / "ui.py").read_text()


def test_D_TRE_FASCE_nello_stesso_ordine_col_titolo_anche_se_vuote():
    """Il pannello è il posto dove si impara la struttura, perché la mostra su
    un caso concreto. Perché insegni deve leggersi SEMPRE UGUALE.

    Il titolo c'è anche a fascia vuota, ed è il punto: una fascia vuota che
    porta il titolo insegna che quel posto esiste e che lì manca qualcosa.
    Prima i blocchi comparivano e sparivano a seconda del documento, e due
    documenti diversi davano due pannelli di forma diversa.
    """
    i = DOCUI.index("UX3/D · TRE FASCE")
    j = DOCUI.index("# DP-32 propagative metadata", i)
    corpo = DOCUI[i:j]

    #: l'ordine, che è il senso della cosa
    a = corpo.index('text="What it is"')
    b = corpo.index('text="What it documents"')
    c = corpo.index('text="What represents it"')
    assert a < b < c, "cosa è → cosa documenta → cosa lo rappresenta"

    #: i titoli NON sono dentro un `if`: si disegnano sempre
    for titolo in ('text="What it is"', 'text="What it documents"',
                   'text="What represents it"'):
        riga = corpo[:corpo.index(titolo)].rsplit("\n", 1)[-1]
        assert riga.strip().startswith(("f1.", "f2.", "f3.")), riga

    #: e ogni fascia che può essere vuota lo DICE
    assert "No stratigraphic unit cites this document" in corpo
    assert "No RM container wraps this document" in corpo
    assert "Not placed in space (no quad)" in corpo


def test_D_I_CONTATORI_DUPLICATI_SONO_VIA():
    """`RM: n · RMDoc: n · RMSF: n · US: n` se ne va: quei numeri appartengono
    ai rispettivi pannelli, e ripetuti qui potevano CONTRADDIRE l'EM
    Overview — la scala conta i nodi `representation_model` dei grafi, questa
    riga contava `len(scene.rm_list)`, che sono oggetti di scena: sul file di
    E.D. 0 e 99 nello stesso momento."""
    codice = _codice(DOCUI)
    for morto in ('f"RM: {rm_count}"', 'f"RMDoc: {rmdoc_count}"',
                  'f"RMSF: {rmsf_count}"', 'f"US: {docs_with_us}"'):
        assert morto not in codice, f"{morto} è ancora lì"
    assert "rmsf_count" not in codice and "docs_with_us" not in codice

    #: resta il sommario della SUA lista
    assert 'f"{total} Documents"' in codice
    assert 'f"Canonicals: {canonicals}"' in codice
    #: …e il conteggio PER DOCUMENTO, che non è duplicato da nessuno
    assert "Linked RMs: " in codice


def test_D_LA_RISALITA_dal_container_al_documento():
    """Si impara un grafo percorrendolo nei due versi; in un verso solo resta
    un albero. L'operatore NON è nuovo: `em.rmdoc_jump_to_document` esiste e
    fa esattamente questo."""
    src = (_REPO / "rm_manager" / "ui.py").read_text()
    assert "em.rmdoc_jump_to_document" in src
    i = src.index("UX3/D · LA RISALITA")
    j = src.index("SECTION 2 (MIDDLE)", i)
    blocco = src[i:j]
    assert "salta.doc_node_id = ac.doc_node_id" in blocco
    #: senza documento non c'è dove andare: un trattino, non un bottone morto
    assert 'if ac.doc_node_id:' in blocco
    assert 'text="—"' in blocco
    #: e il `doc:` non è più dentro la stessa label degli altri due pezzi
    assert 'f"doc: {ac.doc_name' not in src

    #: l'operatore riusato è registrato
    ops = (_REPO / "document_manager" / "operators.py").read_text()
    assert "RMDOC_OT_jump_to_document," in ops, "non registrato"


# ═══ UX3/E · IL COLLASSO DELLA SEZIONE RDF ══════════════════════════════════

def test_E_RDF_SI_COLLASSA_COL_MECCANISMO_CHE_CE_GIA():
    """Non c'è un secondo meccanismo, e non ne ho scritto uno.

    `export_manager/panel.py` cerca `f"{provider.id}_expanded"` su ExportVars
    e, SE la proprietà esiste, disegna il triangolino; se non esiste tiene la
    sezione sempre aperta (`expanded = True`). Al provider `rdf` mancava solo
    quella riga — ed è per questo che srotolava formato, path, base URI, box
    IRI, opzioni avanzate, bottone e le tre righe di «Workflow after export»,
    più di uno schermo, mentre Tabular si chiudeva.
    """
    panel = (_REPO / "export_manager" / "panel.py").read_text()
    assert 'expand_attr = f"{provider.id}_expanded"' in panel, (
        "il meccanismo generico è quello, e non si tocca")

    init = (_REPO / "__init__.py").read_text()
    i = init.index("rdf_expanded: BoolProperty(")
    j = init.index(")", init.index("default=", i))
    prop = init[i:j]
    assert "default=False" in prop, "chiusa di default"

    #: e l'id del provider è quello che la proprietà nomina
    rdf = (_REPO / "export_manager" / "providers" / "rdf" / "__init__.py").read_text()
    assert 'id="rdf"' in rdf


def test_B_LA_GUIDA_E_SOLO_PER_IL_PRIMO_GRAFO_e_lo_stato_e_DERIVATO():
    """La parte che decide se questo assetto infragilisce la UI o no.

    Il conteggio dei grafi caricati è **derivato** dallo stato vivo a ogni
    ridisegno, non memorizzato. Un flag «l'utente ha già visto la guida»
    salvato da qualche parte sarebbe stato che può mentire: resta acceso dopo
    che il grafo è stato rimosso, non segue un .blend che cambia mano, e
    quando mente non c'è modo di accorgersene guardando. Contare i grafi
    caricati non può desincronizzarsi, perché non è una memoria — è una
    domanda fatta ogni volta.

    Questa prova recinta proprio quello: nessuna proprietà di scena, nessun
    contatore, nessun «già visto» da nessuna parte.
    """
    corpo = _data_tree()
    i = corpo.index("def _catena")
    j = corpo.index("def _guida_richiesta", i)
    catena = corpo[i:j]
    assert '"grafi_caricati": len(_grafi_caricati(em_tools))' in catena, (
        "il conteggio si deriva dalla stessa funzione che usa l'Overview")
    #: e NON c'è memoria da nessuna parte
    for memoria in ("guida_vista", "guide_seen", "already_seen",
                    "guida_mostrata", "first_run"):
        assert memoria not in _codice(SETUP), (
            f"{memoria}: uno stato memorizzato è uno stato che può mentire")


def test_B_LA_GUIDA_SI_SPEGNE_DALLE_PREFERENZE_e_in_dubbio_resta_accesa():
    """La preferenza c'è, è raggiungibile, e il ripiego è il comportamento
    di prima: una preferenza che non si riesce a leggere non deve cambiare
    ciò che l'utente vede."""
    prefs = (_REPO / "mapping_preferences.py").read_text()
    i = prefs.index("show_setup_guide: BoolProperty(")
    j = prefs.index(")", prefs.index("default=", i))
    prop = prefs[i:j]
    assert "default=True" in prop, (
        "accesa di default: è il comportamento che c'è, e chi apre l'add-on "
        "per la prima volta è chi ne ha bisogno")
    #: …e si trova, cioè è disegnata nelle preferenze
    assert 'ui_box.prop(self, "show_setup_guide")' in prefs

    corpo = _data_tree()
    i = corpo.index("def _guida_richiesta")
    j = corpo.index("def _guida(", i)
    lettore = corpo[i:j]
    assert "from .. import get_addon_preferences" in lettore, (
        "l'accessore deve venire dalla RADICE del pacchetto")
    assert lettore.count("return True") == 2, (
        "due ripieghi: eccezione e prefs assenti, entrambi verso «come prima»")


def test_B_LE_PREFERENZE_SI_LEGGONO_DA_UN_ACCESSORE_SOLO():
    """È il punto in cui questa cosa si romperebbe, quindi ha una prova sua.

    `context.preferences.addons[<chiave>].preferences` vuole il pacchetto
    RADICE, quello su cui `EMToolsMappingPreferences` mette
    `bl_idname = __package__`. Da un sottomodulo `__package__` è
    `…EM-blender-tools.em_setup`, e quella chiave non esiste: `KeyError`.
    Spezzarlo sul punto non aiuta — come add-on la radice è un segmento
    (`EM-blender-tools`), come estensione sono tre
    (`bl_ext.<repo>.EM-blender-tools`).
    """
    root = (_REPO / "__init__.py").read_text()
    assert "def get_addon_preferences(" in root
    i = root.index("def get_addon_preferences(")
    j = root.index("\n\n\n", i)
    acc = root[i:j]
    assert "addons[__package__].preferences" in acc
    assert "except (KeyError, AttributeError)" in acc, (
        "deve tornare None, non sollevare: una preferenza illeggibile non "
        "deve spegnere un pannello")
    assert "return None" in acc

    #: e nessun sottomodulo se lo rifà da sé
    for f in ("em_setup/ui.py", "document_manager/ui.py", "rm_manager/ui.py"):
        src = (_REPO / f).read_text()
        assert "addons[__package__]" not in _codice(src), (
            f"{f}: da un sottomodulo __package__ non è la chiave giusta")


# ═══ LA PROVA CHE AVREBBE PRESO IL GUASTO DI OGGI ════════════════════════════

def test_OGNI_self_METODO_CHIAMATO_ESISTE_NELLA_SUA_CLASSE():
    """Due volte nello stesso giro ho rotto il disegno così, e a video il
    sintomo è lo stesso: Blender **smette di disegnare** al punto
    dell'eccezione e il pannello finisce a metà, senza dire niente.

    Il primo caso: togliendo `_draw_promotion_scale` da `EM_SetupPanel` la
    fetta si è portata via anche `_kw_icona`, che le stava accanto.
    `_draw_graph_info` lo chiama, quindi aprire `Graph info` sollevava
    `AttributeError` e a video restava l'etichetta `US/USV` e poi il vuoto —
    via Epochs, Properties, Documents, EM Warnings, Auxiliary Resources.

    Il secondo: rimuovendo il pannello Overview è sparita la definizione di
    `_grafi_caricati`, che `_catena` chiama per decidere se mostrare la guida.

    Nessuna prova se ne accorgeva, perché tutte misuravano il TESTO del
    sorgente («`_kw_icona("proxies_rows"` compare») e non la struttura. Questa
    legge le classi con `ast` e verifica che ogni `self._nome(` chiamato sia
    definito nella stessa classe o in una sua antenata del file.
    """
    import ast
    problemi = []
    for rel, f in _sorgenti():
        try:
            albero = ast.parse(f.read_text(errors="replace"))
        except SyntaxError:
            continue
        for cls in [n for n in ast.walk(albero) if isinstance(n, ast.ClassDef)]:
            definiti = {n.name for n in cls.body
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            definiti |= {t.id for n in cls.body
                         if isinstance(n, ast.Assign)
                         for t in n.targets if isinstance(t, ast.Name)}
            #: le annotazioni (le PropertyGroup di Blender: `step: StringProperty`)
            definiti |= {n.target.id for n in cls.body
                         if isinstance(n, ast.AnnAssign)
                         and isinstance(n.target, ast.Name)}
            #: gli ATTRIBUTI assegnati da qualunque metodo contano come
            #: definiti: `self._timer = None` in `execute` è legittimo, e una
            #: prova che lo segnalasse sarebbe rumore
            for nodo in ast.walk(cls):
                if (isinstance(nodo, ast.Assign)
                        and any(isinstance(t, ast.Attribute)
                                and isinstance(t.value, ast.Name)
                                and t.value.id == "self" for t in nodo.targets)):
                    definiti |= {t.attr for t in nodo.targets
                                 if isinstance(t, ast.Attribute)}

            #: e si guardano solo le CHIAMATE `self._x(...)`, che è la forma
            #: che rompe il disegno
            for nodo in ast.walk(cls):
                if not (isinstance(nodo, ast.Call)
                        and isinstance(nodo.func, ast.Attribute)
                        and isinstance(nodo.func.value, ast.Name)
                        and nodo.func.value.id == "self"):
                    continue
                nome = nodo.func.attr
                #: solo i nostri, cioè quelli con l'underscore: il resto lo
                #: mette Blender sulla classe base (`layout`, `report`, …)
                if not nome.startswith("_") or nome.startswith("__"):
                    continue
                if nome not in definiti:
                    problemi.append(f"{rel}: {cls.name}.self.{nome}() "
                                    f"chiamato ma non definito nella classe")
    assert not problemi, "\n".join(problemi)


def test_OGNI_FUNZIONE_DI_MODULO_CHIAMATA_ESISTE(  ):
    """La gemella della precedente per le funzioni di modulo: `_catena`
    chiamava `_grafi_caricati()` dopo che la rimozione del pannello Overview
    ne aveva portato via la definizione. `py_compile` non se ne accorge —
    è un `NameError` a tempo di esecuzione, cioè a tempo di DISEGNO.

    Recintata su `em_setup/ui.py`, che è il file dove è capitato e dove i
    pannelli si dividono gli aiuti a livello di modulo.
    """
    import ast
    albero = ast.parse(SETUP)
    definiti = {n.name for n in albero.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    definiti |= {t.id for n in albero.body if isinstance(n, ast.Assign)
                 for t in n.targets if isinstance(t, ast.Name)}
    #: i nomi importati contano come definiti
    for n in ast.walk(albero):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            definiti |= {(a.asname or a.name).split(".")[0] for a in n.names}

    mancanti = set()
    for n in ast.walk(albero):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id.startswith("_")
                and not n.func.id.startswith("__")
                and n.func.id not in definiti):
            mancanti.add(n.func.id)
    assert not mancanti, f"chiamate a nomi non definiti nel modulo: {mancanti}"
