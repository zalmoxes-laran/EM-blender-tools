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
SETUP = (_REPO / "em_setup" / "ui.py").read_text()
MENU = (_REPO / "em_header_menu.py").read_text()


def _carica(nome, rel):
    """Carica per PERCORSO un modulo dell'addon: i suoi `__init__.py`
    importano bpy e fuori da Blender non si caricano."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(nome, _REPO / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _promotion_scale():
    return _carica("_ps", "em_setup/promotion_scale.py")


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
    il `Settings` di Surface Areas, meno i doppi), più due: il contenitore
    `EM_PT_proxy_surface_tools` e `VIEW3D_PT_EM_GraphInfo` (HDT-O, che torna
    pannello). Nessuno via — verificato contandoli, non stimandoli.
    """
    assert len(PANNELLI) == 32, sorted(PANNELLI)


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

def test_C2_LA_SCALA_STA_SOTTO_IL_PATH_e_sopra_Graph_info():
    """AGGIORNATA da EM16-UX2/C2, e la posizione È il requisito nuovo.

    B1 la metteva in testa al pannello, sopra Author; la revisione a video l'ha
    spostata dopo la riga di comandi e dopo il Path, subito sopra `Graph info`
    di cui è il parente visivo. Quel che NON cambia — e che questa prova
    continua a recintare — è che sta fuori da ogni collassabile.
    """
    assert "_draw_promotion_scale" in SETUP
    i_path = SETUP.index('"graphml_path", text="Path"')
    i_scala = SETUP.index("self._draw_promotion_scale(context, layout)")
    i_info = SETUP.index('"show_graph_info", text="Graph info"')
    assert i_path < i_scala < i_info, (
        "l'ordine deve essere Path → scala → Graph info")
    #: …e NON è dentro un `if em_tools.show_…`: un riquadro che si può chiudere
    #: resterebbe chiuso, ed è l'unica cosa nel pannello che insegna la regola
    prima = SETUP[:i_scala].splitlines()[-14:]
    assert not any("show_" in r and r.lstrip().startswith("if") for r in prima), prima


def test_B1_IL_TOOLTIP_E_UN_DESCRIPTION_DINAMICO_non_un_bl_description():
    """Un `layout.label` non ha tooltip, e un bottone operatore lo prende da
    `bl_description` — che è UNO per classe. Quattro gradini con quattro
    spiegazioni vogliono quindi un `description()` dinamico, che è il
    meccanismo che Blender offre per questo. Senza, i quattro numeri avrebbero
    avuto lo stesso tooltip, cioè nessuna spiegazione — e senza testo il
    tooltip è l'unica etichetta che resta.

    Verificato in un Blender vero: i quattro tooltip sono diversi.
    """
    assert "class EM_OT_promotion_step_info" in SETUP
    assert "def description(cls, context, properties)" in SETUP
    assert 'op.step = chiave' in SETUP
    #: …e NON si usa `em.help_popup`, il cui tooltip sarebbe lo stesso per tutti
    i = SETUP.index("def _draw_promotion_scale")
    j = SETUP.index("def draw(self, context)", i)
    assert "em.help_popup" not in SETUP[i:j]
    #: …e l'operatore è registrato PRIMA del pannello che lo usa
    assert SETUP.index("EM_OT_promotion_step_info,\n    EM_SetupPanel") > 0


def test_C2_I_QUATTRO_GRADINI_sono_in_INGLESE_e_sono_PAROLE_INTERE():
    """AGGIORNATA DUE VOLTE, e la seconda per una misura che mi ha smentito.

    · **Inglese**, tooltip compresi: l'interfaccia di questo add-on è inglese,
      e la prima versione era in italiano perché l'esempio del prompt lo era.
    · **Cinque campi per gradino**: chiave, etichetta, icona NOSTRA, icona di
      Blender di ripiego, tooltip. Due icone perché le nostre stanno in una
      `previews` e `get_icon_value()` torna 0 quando non è caricata, e un
      `icon_value=0` disegna il vuoto.
    · **`Models` si chiama `RMs`** e il quarto gradino `3D docs`: il quarto ha
      cambiato *insieme* due volte, e la seconda perché la prima era
      sbagliata — vedi la prova sui conteggi qui sotto.
    · **La freccia NON sta più nelle etichette.** Era il prefisso — `→ Models`
      — e la prova lo asseriva. A video quel prefisso era *la causa del
      troncamento*: `→ Mod…`, `→ Grou…`, `→ Docu…`, mentre nel blocco
      `Graph info`, alla stessa larghezza, `Properties` e `Documents` stanno
      interi. Misurato due volte: non era il contenitore (rifatto identico a
      `Graph info`, si abbreviavano ancora), è la freccia, che come glifo costa
      quanto due o tre caratteri.

      L'imbuto resta in `testo()`, dove la freccia SEPARA i gradini e lo spazio
      c'è. Quindi la prova asserisce adesso parole intere nelle etichette e la
      freccia nella riga compatta.
    """
    ps = _promotion_scale()

    chiavi = [k for k, _l, _c, _i, _t in ps.GRADINI]
    assert chiavi == ["in_scene", "rms", "groups", "docs3d"], chiavi

    etichette = [l for _k, l, _c, _i, _t in ps.GRADINI]
    assert etichette == ["In scene", "RMs", "Groups", "3D docs"], etichette
    #: nessuna freccia nelle etichette: è ciò che le troncava
    assert not any(ps.FRECCIA in e for e in etichette), (
        "la freccia nell'etichetta la fa abbreviare: → Mod…")
    #: …ma l'imbuto non è perso, sta nella riga compatta
    assert ps.FRECCIA in ps.testo({k: 1 for k in chiavi})

    #: ogni gradino ha un'icona di Blender valida e un tooltip vero
    for k, _l, custom, icona, tip in ps.GRADINI:
        assert icona and icona.isupper(), f"{k}: ripiego {icona!r}"
        assert len(tip) >= 60, f"{k}: troppo corto per essere un tooltip"
        #: …e in inglese: nessuna delle parole italiane che c'erano prima
        for italiana in ("Oggetti", "della scena", "Nodi", "gli insiemi",
                         "Le fonti", "hai SCELTO"):
            assert italiana not in tip, f"{k}: ancora italiano ({italiana})"

    #: le tre icone di NODO sono le nostre, non approssimazioni di Blender;
    #: `In scene` no, perché conta oggetti di Blender e non nodi del grafo
    nostre = dict((k, c) for k, _l, c, _i, _t in ps.GRADINI)
    assert nostre["in_scene"] is None, "In scene conta oggetti, non nodi"
    assert nostre["rms"] == "show_all_RMs", nostre["rms"]
    assert nostre["groups"] == "container_on", nostre["groups"]
    #: `document` e NON `show_all_RMDoc`: qui si contano DOCUMENTI, e l'RMDoc
    #: è un'altra cosa (una lista di oggetti in scena, come gli RMSF)
    assert nostre["docs3d"] == "document", nostre["docs3d"]

    #: e nessun gradino usa un glifo RETTANGOLARE della palette del grafo:
    #: `US.png` è 253×128 e a 16px Blender lo schiaccia in una barretta
    for k, c in nostre.items():
        assert c not in ("US", "USVs", "USVn", "USD", "SF", "VSF",
                         "property"), f"{k}: {c} è un glifo di palette, non un'icona"

    #: …e quello di RMDocs dice la cosa che il numero nasconde: che NON è il
    #: numero dei documenti del grafo, e che essere molti meno è normale
    tip_doc = dict((k, t) for k, _l, _c, _i, t in ps.GRADINI)["docs3d"]
    assert "3D REPRESENTATION" in tip_doc, tip_doc
    assert "has_quad" in tip_doc, tip_doc
    #: dice le due cose che NON è
    assert "neither the RMDoc list nor the" in tip_doc, tip_doc
    assert "NOT the «Documents» of Graph info" in tip_doc, tip_doc
    assert "not a gap" in tip_doc, "non dice che un numero più basso non è una mancanza"


def test_C2_IL_QUARTO_CONTEGGIO_SONO_I_DOCUMENTI_CON_UN_3D():
    """AGGIORNATA DUE VOLTE: il quarto gradino ha cambiato INSIEME, non nome.

    EM16-UX2 dichiarava `conta()` fuori scope («cambiano le stringhe, non i
    conteggi»), e il quarto numero era `scene.doc_list`. Poi E.D. ha notato che
    «Documents così è duplicato»: misurato, `doc_list` si popola dai nodi
    `document` del grafo (`document_manager/data.py`) ed è lo **stesso
    insieme** che `Graph info` conta come `document_count`
    (`populate_lists.py:387`) — lo stesso numero due volte nello stesso
    pannello.

    Il primo rimedio era `scene.rmdoc_list`, ed era **sbagliato**:
    `rmdoc_list` è object-centric (un elemento per quad in scena) e gli RMDoc
    sono una cosa loro, come gli RMSF. Il gradino conta DOCUMENTI.

    Adesso il criterio è quello che il Document Manager ha già: gli elementi di
    `doc_list` con `has_quad`, cioè il filtro «With 3D Only»
    (`filter_with_3d`, «documents that have a 3D representation»). Una
    definizione, due lettori.
    """
    ps = _promotion_scale()

    class O:
        def __init__(s, t, i="NONE"):
            s.type, s.instance_type = t, i

    def cand(o):
        return (o.type in ("MESH", "CURVE")
                or (o.type == "EMPTY" and o.instance_type != "COLLECTION"))

    class N:
        node_type = "representation_model"

    n = ps.conta(oggetti_scena=[O("MESH")] * 203 + [O("LIGHT")] * 5,
                 nodi_grafo=[N()] * 0, rm_containers=3, docs_con_3d=4,
                 is_candidato=cand)
    assert n == {"in_scene": 203, "rms": 0, "groups": 3, "docs3d": 4}
    assert ps.testo(n) == ("203 In scene  →  0 RMs  →  3 Groups  "
                           "→  4 3D docs")

    #: e `doc_list` non è più un argomento: chi lo passasse si accorgerebbe
    import pytest
    with pytest.raises(TypeError):
        ps.conta(oggetti_scena=(), doc_list=19, is_candidato=cand)

    #: il pannello conta i documenti con has_quad, NON una lista di oggetti
    i = SETUP.index("def _draw_promotion_scale")
    j = SETUP.index("def draw(self, context)", i)
    corpo = SETUP[i:j]
    assert 'if getattr(d, "has_quad", False)' in corpo, (
        "il criterio deve essere has_quad, come filter_with_3d")
    #: …e NON una lista di oggetti. Sul codice spogliato dei commenti: questo
    #: metodo PARLA di `rmdoc_list` per dire perché non la usa (la regola del
    #: pagliaio, imparata il 4 ottobre e ricascataci qui).
    assert "rmdoc_list" not in _codice(corpo), (
        "rmdoc_list è object-centric: qui si contano documenti")
    #: `doc_list=len(` da solo NON basta come aghi: è sottostringa di
    #: `rmdoc_list=len(` e la prova si mordeva la coda. Serve il confine.
    assert not re.search(r"(?<![a-z_])doc_list=len\(", corpo), (
        "il doppione è tornato: il pannello legge di nuovo doc_list")


def test_C2_IL_CASO_ZERO_MODELS_e_un_avviso_e_non_un_allarme():
    """Sul file di E.D.: 203 candidati in scena e 0 nodi RM. Non è un guasto —
    quel grafo viene da import GraphML, che per disegno non porta i nodi RM."""
    ps = _promotion_scale()
    assert ps.modelli_a_zero_sospetto({"in_scene": 203, "rms": 0}) is True
    #: una scena vuota NON è sospetta
    assert ps.modelli_a_zero_sospetto({"in_scene": 0, "rms": 0}) is False
    #: …e nemmeno un grafo che ha i suoi modelli
    assert ps.modelli_a_zero_sospetto({"in_scene": 203, "rms": 34}) is False

    #: nel pannello: icona INFO, e MAI rosso
    i = SETUP.index("def _draw_promotion_scale")
    j = SETUP.index("def draw(self, context)", i)
    corpo = SETUP[i:j]
    assert "modelli_a_zero_sospetto" in corpo
    assert 'info = (chiave == "rms" and zero_sospetto)' in corpo
    assert '{"icon": \'INFO\'} if info' in corpo
    assert "alert" not in corpo, "il rosso è l'errore, e questo non è un errore"


def test_C2_E_LA_FRASE_DEL_CASO_ZERO_E_QUELLA_DI_EM16_UX_E():
    """«Riusa quella stringa, non scriverne una seconda»: una frase, un posto.

    AGGIORNATA perché la prova di prima NON misurava il requisito: asseriva
    che `no_rm_nodes_yet()` esiste e compone bene, e da quello io avevo
    concluso — a torto — che il tooltip della cella la usasse. Non la usava:
    la chiamava solo `rmcontainer.project`, e la cella mostrava la sua
    spiegazione generica. Il requisito era scoperto e la prova verde.

    Adesso la prova segue la strada vera: il gradino a zero passa per
    `EM_OT_promotion_step_info._frase`, che è l'unico punto da cui escono sia
    il tooltip (`description`) sia il popup (`execute`), e che nel caso zero
    ritorna la frase di `group_nodes`.
    """
    gn = _group_nodes()
    frase = gn.no_rm_nodes_yet(98, 3)
    assert "98 mesh(es) in 3 container(s)" in frase
    assert "excluded from GraphML by design" in frase

    #: la frase generica (senza conteggi) è quella che la cella mostra
    nuda = gn.no_rm_nodes_yet()
    assert "excluded from GraphML by design" in nuda
    assert "Promote the meshes first" in nuda

    #: e il pannello la prende da LÀ, nel caso zero e solo lì
    i = SETUP.index("class EM_OT_promotion_step_info")
    j = SETUP.index("def _wrap(", i)
    corpo = SETUP[i:j]
    assert "group_nodes as gn" in corpo, "la frase non viene da group_nodes"
    assert "gn.no_rm_nodes_yet()" in corpo
    assert 'if zero and step == "rms"' in corpo, (
        "la frase del caso zero deve valere SOLO per la cella a zero")
    #: tooltip e popup escono dalla stessa funzione, sennò tornano due
    assert corpo.count("_frase(") >= 3, (
        "description ed execute devono chiamare lo stesso _frase")
    #: …e chi disegna gli dice se è il caso zero
    k = SETUP.index("def _draw_promotion_scale")
    l = SETUP.index("def draw(self, context)", k)
    assert "op.zero = info" in SETUP[k:l]
    assert "Promote to RM" in frase, "non dice il comando da eseguire prima"
    #: senza conteggi resta vera e non stampa zeri finti
    nuda = gn.no_rm_nodes_yet()
    assert "0 mesh" not in nuda
    assert "excluded from GraphML by design" in nuda

    #: …e l'operatore la CHIAMA invece di ricomporla
    ops = (_REPO / "rm_manager" / "container_operators.py").read_text()
    assert "no_rm_nodes_yet(" in ops
    assert "excluded from GraphML by design" not in ops, (
        "l'operatore ha ancora la sua copia della frase")


def test_B1_IL_CRITERIO_DI_CANDIDATURA_non_e_riscritto():
    """Si passa `is_rm_candidate`, quello vero: riscriverlo sarebbe la seconda
    copia da tenere allineata."""
    assert "from ..rm_manager.containers import is_rm_candidate" in SETUP
    ps = (_REPO / "em_setup" / "promotion_scale.py").read_text()
    corpo = ps.split('"""', 2)[2]
    for spia in ("instance_type", "'MESH'", '"MESH"'):
        assert spia not in corpo, f"promotion_scale riscrive il criterio ({spia})"


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
    `columns=6, even_columns=True` dà a ognuno un sesto esatto della riga, e
    nello scatto successivo i sei bottoni arrivano da bordo a bordo. È lo
    stesso meccanismo delle quattro celle della scala (C2), che nello stesso
    scatto riempivano già la larghezza. Quindi la prova asserisce ADESSO il
    contenitore, non solo l'assenza di `ui_units_x`.
    """
    i = SETUP.index("cmd = layout.grid_flow(")
    j = SETUP.index('_iop.name = "EM_MT_LandscapeInfo"', i)
    blocco = SETUP[i:j]

    assert "ui_units_x" not in blocco, (
        "ui_units_x fissa la larghezza: i bottoni non riempiono più la riga")
    #: il contenitore a celle, che è ciò che DAVVERO riempie la riga
    assert "columns=6" in blocco, "sei comandi, sei celle"
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
    #: …e nessuna etichetta di testo è tornata
    for morto in ('text="Add graph"', 'text="Remove graph"', 'text="Save As…"',
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
    i = SETUP.index("def draw_header_preset")
    j = SETUP.index("def _draw_promotion_scale", i)
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
    """Il sorgente senza commenti: la regola imparata il 4 ottobre.

    Questo file PARLA di `draw_dtc_section` nei suoi commenti — spiega perché
    il DTC è uscito — e un'asserzione sull'assenza di quel nome morderebbe un
    commento onesto invece del codice.
    """
    return "\n".join(r for r in testo.splitlines()
                     if not r.lstrip().startswith("#"))


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
