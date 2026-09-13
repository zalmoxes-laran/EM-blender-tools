"""I verbi del deck — e il fatto che NON riscrivono niente.

Il principale è **Bake & publish** sulla selezione. Tre pezzi, tutti già
esistenti e provati:

1. il bake è l'export che c'è (`export.heriverse`) — se qui ricomparisse la
   logica dell'export, vorrebbe dire essersi persi;
2. la registrazione è `publication.promote_resource`, in s3Dgraphy;
3. la pubblicazione è `em.publish_distribution`, provata contro un MinIO vero
   la notte scorsa.

Il deck li **mette in fila** su una selezione e riporta cosa è successo a
ciascuno. Vale la regola 24: un difetto di programmazione emerge, un elemento
che fallisce si dichiara fallito e l'insieme prosegue.

**NESSUNA PUBBLICAZIONE AUTOMATICA.** È un atto deliberato come la promozione
a documento: se diventa automatica, il deck smette di dire qualcosa. L'unica
cortesia automatica ammessa è di sola lettura — accorgersi che qualcosa è
diventato stantio, che è il mestiere di Refresh.
"""

from __future__ import annotations

import os
import time

import bpy  # type: ignore
from bpy.types import Operator

from ..functions import em_log, is_graph_available

#: Come la regola 24: i difetti del CODICE non diventano un messaggio.
DIFETTI_DI_PROGRAMMAZIONE = (NameError, AttributeError, TypeError, ImportError)


# ─────────────────────────────────────────────────────────────────────────────
# il conto
# ─────────────────────────────────────────────────────────────────────────────

def _impronta_attuale(nodo):
    """L'impronta ATTUALE della sorgente di una derivata. → `""` se non si sa.

    Qui si paga il filesystem, ed è la ragione per cui tutto questo sta in un
    operatore e non in un `draw`.
    """
    from ..rm_manager.containers import impronta_di, percorso_del_grezzo
    from .. import resource_levels

    dati = getattr(nodo, "data", None) or {}
    url = str(dati.get("url") or "")
    if url.startswith("blend://"):
        #: un grezzo dentro un .blend: l'impronta è quella dell'OGGETTO, che è
        #: ciò che il bake ha misurato
        try:
            from s3dgraphy.resources.resolver import parse_blend_locator
        except ImportError as exc:
            em_log(f"[deck] blend:// non leggibile ({exc}): staleness non "
                   f"calcolabile per {getattr(nodo, 'node_id', '?')}", "WARNING")
            return ""
        try:
            _file, _tipo, nome = parse_blend_locator(url)
        except (ValueError, TypeError):
            return ""
        oggetto = bpy.data.objects.get(nome)
        return impronta_di(oggetto) if oggetto is not None else ""
    percorso = percorso_del_grezzo(nodo)
    return resource_levels.impronta_sorgente(percorso) if percorso else ""


def _container_di(context):
    """`(rm_node_id) -> {"id","label","membri"}` — iniettato nel calcolo puro.

    I container vivono in una property di scena, che `publication_deck` non
    deve conoscere per restare provabile fuori da Blender.

    Una passata sola sui container, e la mappa si interroga per id: la prima
    versione risolveva ogni RM scorrendo TUTTI i membri di TUTTI i container e
    richiedeva il grafo a ogni giro — con venti container e venti membri erano
    quattrocento risoluzioni per un conto che ne vuole venti.
    """
    from ..rm_manager.containers import resolve_rm_node_id

    scene = context.scene
    ok, graph = is_graph_available(context)
    if not ok or graph is None:
        return lambda _rm: None

    mappa = {}
    for indice, container in enumerate(getattr(scene, "rm_containers", ()) or ()):
        info = {
            "id": getattr(container, "group_node_id", "") or f"container-{indice}",
            "label": getattr(container, "label", "") or f"Container {indice}",
            "membri": len(container.mesh_names),
            "indice": indice,
        }
        for voce in container.mesh_names:
            oggetto = bpy.data.objects.get(voce.name)
            if oggetto is None:
                continue
            #: l'id dell'RM è l'identificatore, il nome dell'oggetto è
            #: un'etichetta (NIGHT-RIM/A)
            rid = resolve_rm_node_id(graph, oggetto, scene=scene, migra=False)
            if rid:
                mappa.setdefault(rid, info)

    return mappa.get


def _esiste(context):
    """Il fornitore «i byte ci sono?», che risolve i locator RELATIVI.

    **D5 · il difetto che questa funzione chiude.** Prima qui passava
    `os.path.isfile` nudo, che risolve un percorso relativo contro la cartella
    di lavoro del PROCESSO — mai quella giusta. Su un progetto di diciannove
    documenti DosCo il deck riportava diciannove volte «the bytes are not where
    the locator says»: non un fatto del progetto, un difetto del controllo.

    Le basi sono quelle che il modello dichiara (`basi_dei_locator`); senza
    nessuna base il fornitore risponde `None`, che vuol dire «non ho potuto
    guardare» e non «non ci sono».
    """
    from ..rm_manager.containers import basi_dei_locator
    from .. import publication_gesture

    return publication_gesture.esistenza(basi_dei_locator(context))


def _calcola(context):
    """Il conto intero, fuori dal draw. → `(esito, destinazione_nota)`."""
    from .. import publication_deck, publication_targets

    ok, graph = is_graph_available(context)
    if not ok or graph is None:
        return None, ""
    deck = context.scene.em_publication_deck
    registro = publication_targets.destinazioni()
    scelta = deck.destinazione
    info = registro.get(scelta) or {}
    esito = publication_deck.righe(
        list(graph.nodes), list(graph.edges),
        impronta_attuale=_impronta_attuale,
        container_di=_container_di(context),
        destinazioni={scelta: info.get("giudice")},
        esiste=_esiste(context))
    return esito, info.get("perche", "")


def _stato_del_grafo() -> dict:
    """D6 · lo stato del grafo rispetto alla stanza. → `{"stato", "frase"}`.

    Legge la sessione di sync **che già esiste**: nessuna connessione nuova e
    nessun client di database, come il prompt chiede e come il buon senso
    vuole — un pannello che apre un socket per disegnarsi è un pannello che
    blocca Blender quando la rete è lenta.
    """
    from .. import publication_room
    try:
        from ..sync_manager.room_session import SESSION
    except ImportError as exc:
        #: decisione 14: un ImportError si dichiara, non si ingoia. E lo stato
        #: che ne esce è `unknown` con la ragione, non «nessuna stanza»: non
        #: saper leggere non è la stessa cosa di non esserci.
        em_log(f"[deck] sessione di stanza non leggibile ({exc})", "WARNING")
        return {"stato": "unknown",
                "frase": "the sync session could not be read"}
    return publication_room.dalla_sessione(SESSION)


def _flag_per_rm(context) -> dict:
    """`{rm_node_id: indice in scene.rm_list}` — **dove sta la spunta del deck**.

    D4 · La spunta del deck non è un flag nuovo: è `RMItem.is_publishable`,
    che governa già cosa l'export fa. Qui si trova soltanto **dove** sta, e la
    UIList disegna quella property. Due impostazioni per lo stesso fatto sono
    la malattia dei cancelli del sync, ed è costata due giorni.

    Un RM senza voce in `rm_list` non ottiene una casella finta: torna `-1`, e
    la scheda dice che nessun flag lo governa.
    """
    per_id, per_nome = {}, {}
    for indice, voce in enumerate(getattr(context.scene, "rm_list", ()) or ()):
        if getattr(voce, "node_id", ""):
            per_id.setdefault(voce.node_id, indice)
        per_nome.setdefault(voce.name, indice)
    return per_id, per_nome


class EM_OT_deck_refresh(Operator):
    """Ricalcola il deck. È l'unica cortesia automatica ammessa — **di sola
    lettura**: accorgersi che qualcosa è diventato stantio, mai pubblicarlo."""

    bl_idname = "em.deck_refresh"
    bl_label = "Refresh"
    bl_description = ("Recompute what is on the threshold. This reads the "
                      "filesystem, so it runs when you ask and not while the "
                      "panel draws")

    def execute(self, context):
        from .. import publication_deck, publication_gesture

        deck = context.scene.em_publication_deck
        inizio = time.perf_counter()
        esito, nota_destinazione = _calcola(context)
        deck.righe.clear()
        deck.blocchi.clear()
        if esito is None:
            deck.calcolato_alle = time.strftime("%H:%M")
            deck.sintesi = ""
            deck.nota = "No graph loaded."
            deck.stale = deck.pubblicabili = deck.spuntati = 0
            self.report({'WARNING'}, "No graph loaded")
            return {'CANCELLED'}

        scelta = deck.destinazione
        per_id, per_nome = _flag_per_rm(context)
        indice_container = {
            (getattr(c, "group_node_id", "") or f"container-{i}"): i
            for i, c in enumerate(getattr(context.scene, "rm_containers", ()) or ())}
        basi = _basi(context)

        for a in esito["assets"]:
            voce = deck.righe.add()
            voce.name = a["nome"]
            voce.asset_id = a["id"]
            voce.media = a["media"]
            voce.stato = a["stato"]
            voce.proprietario = a["nome"]
            voce.granularita = a["granularita"]
            voce.membri = a["membri"]
            voce.tier = a["tier"]
            voce.pubblicata_il = a["pubblicata_il"]
            voce.cosa_e_cambiato = a["cosa_e_cambiato"]
            voce.perche_no = a["perche_no"]
            voce.n_pubblicabili = len(a["pubblicabili"])
            voce.flag_indice = per_id.get(a["rm_id"],
                                          per_nome.get(a["nome"], -1))
            voce.container_indice = indice_container.get(a["id"], -1)
            pronto = a["pronto_per"].get(scelta) or {}
            voce.pronto = str(pronto.get("state") or "")
            voce.pronto_perche = str(pronto.get("why") or "")

            for d in a["distribuzioni"]:
                riga = voce.distribuzioni.add()
                riga.name = d["nome"]
                riga.node_id = d["id"]
                riga.stato = d["stato"]
                riga.dove = d["dove"]
                riga.tier = d["tier"]
                riga.residency = d["residency"]
                riga.scope = d["scope"]
                riga.formato = d["formato"]
                riga.packaging = d["packaging"]
                riga.peso = d["peso"]
                riga.url = d["url"]
                riga.percorso = publication_gesture.risolvi(d["url"], basi)
                riga.pubblicata_il = d["pubblicata_il"]
                riga.cosa_e_cambiato = d["cosa_e_cambiato"]
                riga.pubblicabile = bool(d["pubblicabile"]["si"])
                riga.perche_no = d["pubblicabile"]["perche"]
                verdetto = d["pronto_per"].get(scelta) or {}
                riga.pronto = ("yes" if verdetto.get("ok")
                               else str(verdetto.get("state") or "no"))
                riga.pronto_perche = str(verdetto.get("why") or "")

        s = esito["sommario"]
        #: D5 · le ragioni che fermano PIÙ di un asset stanno in testa, una
        #: volta. Una che ne ferma uno solo è un fatto di quella riga e sta
        #: nella scheda, dove è già.
        for ragione, quanti in s["blocchi"]:
            if quanti < 2:
                continue
            blocco = deck.blocchi.add()
            blocco.name = ragione
            blocco.quanti = quanti

        deck.sintesi = publication_deck.riga_di_sintesi(s)
        deck.stale = s["stale"]
        deck.pubblicabili = s["pubblicabili"]
        deck.distribuzioni = s["distribuzioni"]
        deck.spuntati = _spuntati(context, deck)

        #: D5 · il glifo dello stato si mostra solo quando DISTINGUE. Su un
        #: progetto di soli documenti è identico su tutte le righe, e una
        #: colonna che non varia mai costa larghezza senza dire niente.
        deck.stati_differiscono = len({r.stato for r in deck.righe}) > 1

        #: D6 · lo stato del grafo, letto da quello che la sessione di sync già
        #: sa. Nessuna connessione nuova, nessun client di database.
        stanza = _stato_del_grafo()
        deck.grafo_stato = stanza["stato"]
        deck.grafo_frase = stanza["frase"]
        deck.calcolato_alle = time.strftime("%H:%M")
        deck.destinazione_nota = nota_destinazione
        deck.nota = ""
        if deck.riga_attiva >= len(deck.righe):
            deck.riga_attiva = 0
        costo = (time.perf_counter() - inizio) * 1000
        em_log(f"[deck] {len(deck.righe)} rows in {costo:.0f} ms", "INFO")
        self.report({'INFO'}, f"{deck.sintesi} · {costo:.0f} ms")
        return {'FINISHED'}


def _basi(context):
    from ..rm_manager.containers import basi_dei_locator
    return basi_dei_locator(context)


def _spuntati(context, deck) -> int:
    """Quanti asset sono spuntati **adesso**, letti dalla loro casa vera.

    Il numero finisce nel bottone, e si ricalcola al Refresh e dopo ogni
    pubblicazione. Si contano solo quelli che hanno davvero qualcosa da
    pubblicare: offrire «Publish 19» quando diciannove sono già pubblicati
    sarebbe un gesto che poi rifiuta riga per riga.
    """
    from . import flags

    scelti = flags.spuntati(context.scene)
    return sum(1 for r in deck.righe
               if r.asset_id in scelti and r.n_pubblicabili)


def _da_pubblicare(context, deck) -> list:
    """Gli asset spuntati, nell'ordine della lista."""
    from . import flags

    scelti = flags.spuntati(context.scene)
    return [r for r in deck.righe if r.asset_id in scelti]


def _pubblica_molti(operatore, context, righe):
    """Mette in fila `em.publish_distribution` e riporta cosa è successo a
    CIASCUNO. Non è un secondo baker e non riscrive niente.

    Regola 24: un difetto di programmazione emerge; un elemento che fallisce si
    dichiara fallito e l'insieme prosegue.
    """
    fatti, falliti, saltati = [], [], []

    # LO STORE SI CHIEDE UNA VOLTA SOLA, prima del giro.
    #
    # Misurato: senza store, dieci righe selezionate davano dieci fallimenti
    # identici («the object store is unavailable»). Dieci volte la stessa frase
    # non è un resoconto, è rumore — e nasconde che il problema è UNO e non
    # dieci.
    from ..resources_tab import resource_backend
    if not resource_backend.minio_supported():
        operatore.report({'ERROR'},
                         "The object store is unavailable: needs the dev "
                         "s3dgraphy (./em.sh s3d) and the 'minio' extra. "
                         "Nothing was published.")
        return {'CANCELLED'}

    lavoro = [(r, d) for r in righe for d in r.distribuzioni]
    wm = context.window_manager
    wm.progress_begin(0, len(lavoro) or 1)
    try:
        for indice, (riga, distribuzione) in enumerate(lavoro):
            wm.progress_update(indice)
            etichetta = f"{riga.name} · {distribuzione.name}"
            if not distribuzione.pubblicabile:
                #: SALTATO non è FALLITO: la scheda diceva già perché, e
                #: chiamarlo fallimento renderebbe il resoconto illeggibile
                saltati.append(f"{etichetta} ({distribuzione.perche_no})")
                continue
            try:
                esito = bpy.ops.em.publish_distribution(
                    resource_id=distribuzione.node_id)
            except DIFETTI_DI_PROGRAMMAZIONE:
                raise
            except Exception as exc:  # noqa: BLE001 — una riga storta
                falliti.append(f"{etichetta}: {exc}")
                continue
            if 'FINISHED' in esito:
                fatti.append(etichetta)
            else:
                falliti.append(f"{etichetta}: refused")
    finally:
        wm.progress_end()

    #: IL RESOCONTO ELENCA PER NOME. «3 riusciti» non dice a chi tornare;
    #: con i nomi, sì.
    for gruppo, etichetta in ((fatti, "published"), (falliti, "FAILED"),
                              (saltati, "skipped")):
        if gruppo:
            em_log(f"[deck] {etichetta}: {', '.join(gruppo)}", "INFO")
    print(f"=== Deck: {len(fatti)} published, {len(falliti)} failed, "
          f"{len(saltati)} skipped ===")
    if falliti:
        operatore.report({'WARNING'},
                         f"{len(fatti)} published, {len(falliti)} failed: "
                         + ", ".join(falliti[:3]))
    else:
        operatore.report({'INFO'},
                         f"{len(fatti)} published"
                         + (f", {len(saltati)} skipped" if saltati else ""))
    bpy.ops.em.deck_refresh()
    return {'FINISHED'}


# ─────────────────────────────────────────────────────────────────────────────
# i verbi
# ─────────────────────────────────────────────────────────────────────────────

class EM_OT_deck_flag_visible(Operator):
    """**D3 · flagga tutto quello che è IN VISTA. Additivo, e annullabile.**

    DECK2 aveva tolto i verbi collettivi perché un «seleziona tutto» che scrive
    una property di progetto cancella in un colpo le esclusioni messe a mano
    (decisione 31). Il ragionamento era giusto e la cura sbagliata: il rimedio
    a una scrittura massiva è **l'annullamento**, non l'amputazione — e
    diciannove documenti da spuntare a mano sono diciannove click.

    Quindi: **unisce e non toglie mai**, agisce su ciò che il filtro corrente
    lascia vedere e non sull'intero progetto, e porta `UNDO` così che Ctrl+Z
    riprenda davvero quelle scritture.
    """

    bl_idname = "em.deck_flag_visible"
    bl_label = "Flag all in view"
    bl_description = ("Add the publish flag to every asset the filter is "
                      "showing. It only adds: nothing already flagged is "
                      "cleared, and Ctrl+Z takes it back")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        deck = getattr(context.scene, "em_publication_deck", None)
        if deck is None or not len(deck.righe):
            cls.poll_message_set("Nothing in the deck yet")
            return False
        return True

    def execute(self, context):
        from .. import publication_flags
        from . import flags

        deck = context.scene.em_publication_deck
        ids = publication_flags.in_vista(deck.righe, deck.filtro)
        aggiunti = flags.aggiungi(context.scene, ids)
        deck.spuntati = _spuntati(context, deck)
        self.report({'INFO'}, f"{aggiunti} flagged ({len(ids)} in view)")
        return {'FINISHED'}


class EM_OT_deck_unflag_visible(Operator):
    """Il gesto opposto, **nominato per quello che fa**.

    Non è il rovescio silenzioso del precedente, e non si chiama «none»:
    toglie i flag di ciò che è in vista, lo dice, e si annulla come l'altro.
    Un verbo che cancella deve avere un nome che lo ammette.
    """

    bl_idname = "em.deck_unflag_visible"
    bl_label = "Clear flags in view"
    bl_description = ("Remove the publish flag from every asset the filter is "
                      "showing. Ctrl+Z takes it back")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        deck = getattr(context.scene, "em_publication_deck", None)
        if deck is None or not len(deck.righe):
            cls.poll_message_set("Nothing in the deck yet")
            return False
        return True

    def execute(self, context):
        from .. import publication_flags
        from . import flags

        deck = context.scene.em_publication_deck
        ids = publication_flags.in_vista(deck.righe, deck.filtro)
        tolti = flags.togli(context.scene, ids)
        deck.spuntati = _spuntati(context, deck)
        self.report({'INFO'}, f"{tolti} cleared ({len(ids)} in view)")
        return {'FINISHED'}


class EM_OT_deck_publish(Operator):
    """**Publish** su ciò che è SPUNTATO — e non è un secondo baker.

    Agisce su quello che la spunta dichiara, con il numero nel bottone. Mai un
    «publish selected» che agisce su una selezione invisibile perché si è
    scrollato: è il modo in cui si pubblica ciò che non si voleva.
    """

    bl_idname = "em.deck_publish"
    bl_label = "Publish flagged"
    bl_description = ("Upload the flagged assets to the store and record "
                      "address, checksum and provenance for each. Nothing is "
                      "published automatically: this is the gesture")

    @classmethod
    def poll(cls, context):
        deck = getattr(context.scene, "em_publication_deck", None)
        if deck is None or not deck.spuntati:
            cls.poll_message_set("Flag at least one asset first")
            return False
        return True

    def execute(self, context):
        deck = context.scene.em_publication_deck
        return _pubblica_molti(self, context, _da_pubblicare(context, deck))


class EM_OT_deck_publish_one(Operator):
    """**Publish** questo solo asset — il verbo della scheda.

    Esiste perché non tutto ha un flag: un documento DosCo non ha un
    `is_publishable` (nessuno gliel'ha mai dato), quindi non può essere
    spuntato e il verbo in batch non lo raggiunge. Senza questo, metà di un
    progetto di documenti sarebbe visibile e irraggiungibile.
    """

    bl_idname = "em.deck_publish_one"
    bl_label = "Publish this one"
    bl_description = "Upload this asset's distributions to the store"

    asset_id: bpy.props.StringProperty(default="")  # type: ignore

    def execute(self, context):
        deck = context.scene.em_publication_deck
        righe = [r for r in deck.righe if r.asset_id == self.asset_id]
        if not righe:
            self.report({'WARNING'}, f"{self.asset_id}: not in the deck")
            return {'CANCELLED'}
        return _pubblica_molti(self, context, righe)


class EM_OT_deck_rebake(Operator):
    """**Re-bake** sulle stantie — e il bake è l'export che c'è.

    Non si riscrive niente: si chiama `export.heriverse`, che è il baker, e
    poi si ricalcola. Il deck non sa esportare e non deve imparare.
    """

    bl_idname = "em.deck_rebake"
    bl_label = "Re-bake stale"
    bl_description = ("Run the Heriverse export again so the stale "
                      "distributions are remade from their sources")

    @classmethod
    def poll(cls, context):
        deck = getattr(context.scene, "em_publication_deck", None)
        if deck is None or not deck.stale:
            cls.poll_message_set("Nothing is stale")
            return False
        return True

    def execute(self, context):
        try:
            esito = bpy.ops.export.heriverse()
        except DIFETTI_DI_PROGRAMMAZIONE:
            raise
        except Exception as exc:  # noqa: BLE001
            self.report({'ERROR'}, f"Re-bake failed: {exc}")
            return {'CANCELLED'}
        bpy.ops.em.deck_refresh()
        self.report({'INFO'}, f"Re-bake: {esito}")
        return {'FINISHED'}


class EM_OT_deck_reveal(Operator):
    """**Reveal** — apri dove stanno i byte. Non è un gestore di file: apre la
    cartella e si ferma.

    Riceve il percorso **già risolto** (D5): un url relativo non dice dove sono
    i byte finché non si sa rispetto a cosa, e aprire la cartella sbagliata è
    peggio che non aprirne nessuna.
    """

    bl_idname = "em.deck_reveal"
    bl_label = "Reveal"
    bl_description = "Open the folder where these bytes are"

    percorso: bpy.props.StringProperty(default="")  # type: ignore

    def execute(self, context):
        if not self.percorso:
            self.report({'WARNING'},
                        "These bytes are not a file on this disk — "
                        "use Copy URI")
            return {'CANCELLED'}
        cartella = (os.path.dirname(self.percorso)
                    if os.path.isfile(self.percorso) else self.percorso)
        if not os.path.isdir(cartella):
            self.report({'WARNING'}, f"{cartella}: not on this disk")
            return {'CANCELLED'}
        bpy.ops.wm.path_open(filepath=cartella)
        return {'FINISHED'}


class EM_OT_deck_copy_uri(Operator):
    """**Copy URI** — per citare altrove. Il locator così com'è: un indirizzo
    riscritto per farlo sembrare più bello è un indirizzo che non risolve."""

    bl_idname = "em.deck_copy_uri"
    bl_label = "Copy URI"
    bl_description = "Copy this locator to the clipboard, to cite it elsewhere"

    url: bpy.props.StringProperty(default="")  # type: ignore

    def execute(self, context):
        if not self.url:
            self.report({'WARNING'}, "This asset has no locator")
            return {'CANCELLED'}
        context.window_manager.clipboard = self.url
        self.report({'INFO'}, self.url)
        return {'FINISHED'}


_CLASSI = (EM_OT_deck_refresh, EM_OT_deck_flag_visible,
           EM_OT_deck_unflag_visible, EM_OT_deck_publish,
           EM_OT_deck_publish_one, EM_OT_deck_rebake, EM_OT_deck_reveal,
           EM_OT_deck_copy_uri)


def register():
    for cls in _CLASSI:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSI):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001 — unregistering must not fail
            pass
