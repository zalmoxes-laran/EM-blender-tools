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
    """
    from ..rm_manager.containers import resolve_rm_node_id

    scene = context.scene
    mappa = {}
    for indice, container in enumerate(getattr(scene, "rm_containers", ()) or ()):
        for voce in container.mesh_names:
            oggetto = bpy.data.objects.get(voce.name)
            if oggetto is None:
                continue
            mappa[voce.name] = {
                "id": getattr(container, "group_node_id", "") or f"container-{indice}",
                "label": getattr(container, "label", "") or f"Container {indice}",
                "membri": len(container.mesh_names),
                "oggetto": oggetto,
            }

    def per_rm(rm_node_id):
        #: si risale dal nodo RM all'oggetto: l'id dell'RM è l'identificatore,
        #: il nome dell'oggetto è un'etichetta (NIGHT-RIM/A)
        for nome, info in mappa.items():
            ok, graph = is_graph_available(context)
            if not ok:
                return None
            if resolve_rm_node_id(graph, info["oggetto"], scene=scene,
                                  migra=False) == rm_node_id:
                return info
        return None

    return per_rm


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
        esiste=os.path.isfile)
    return esito, info.get("perche", "")


class EM_OT_deck_refresh(Operator):
    """Ricalcola il deck. È l'unica cortesia automatica ammessa — **di sola
    lettura**: accorgersi che qualcosa è diventato stantio, mai pubblicarlo."""

    bl_idname = "em.deck_refresh"
    bl_label = "Refresh"
    bl_description = ("Recompute what is on the threshold. This reads the "
                      "filesystem, so it runs when you ask and not while the "
                      "panel draws")

    def execute(self, context):
        deck = context.scene.em_publication_deck
        inizio = time.perf_counter()
        esito, nota_destinazione = _calcola(context)
        deck.righe.clear()
        if esito is None:
            deck.calcolato_alle = time.strftime("%H:%M")
            deck.sintesi = ""
            deck.nota = "No graph loaded."
            deck.stale = deck.pubblicabili = 0
            self.report({'WARNING'}, "No graph loaded")
            return {'CANCELLED'}

        scelta = deck.destinazione
        for r in esito["righe"]:
            voce = deck.righe.add()
            voce.name = r["nome"]
            voce.node_id = r["id"]
            voce.proprietario = r["etichetta_proprietario"]
            voce.granularita = r["granularita"]
            voce.membri = r["membri"]
            voce.stato = r["stato"]
            voce.dove = r["dove"]
            voce.tier = r["tier"]
            voce.residency = r["residency"]
            voce.scope = r["scope"]
            voce.formato = r["formato"]
            voce.packaging = r["packaging"]
            voce.peso = r["peso"]
            voce.pubblicata_il = r["pubblicata_il"]
            voce.cosa_e_cambiato = r["cosa_e_cambiato"]
            voce.url = r["url"]
            voce.pubblicabile = bool(r["pubblicabile"]["si"])
            voce.perche_no = r["pubblicabile"]["perche"]
            pronto = r["pronto_per"].get(scelta) or {}
            voce.pronto = ("yes" if pronto.get("ok")
                           else str(pronto.get("state") or "no"))
            voce.pronto_perche = str(pronto.get("why") or "")

        from .. import publication_deck
        s = esito["sommario"]
        deck.sintesi = publication_deck.riga_di_sintesi(s)
        deck.stale = s["stale"]
        deck.pubblicabili = s["pubblicabili"]
        deck.calcolato_alle = time.strftime("%H:%M")
        deck.destinazione_nota = nota_destinazione
        deck.nota = ""
        costo = (time.perf_counter() - inizio) * 1000
        em_log(f"[deck] {len(deck.righe)} rows in {costo:.0f} ms", "INFO")
        self.report({'INFO'}, f"{deck.sintesi} · {costo:.0f} ms")
        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────────────────────
# i verbi
# ─────────────────────────────────────────────────────────────────────────────

class EM_OT_deck_select(Operator):
    """Seleziona tutto / niente / solo le stantie. Un operatore e non tre
    bottoni che scrivono la stessa property in tre modi."""

    bl_idname = "em.deck_select"
    bl_label = "Select"
    bl_description = "Change which assets the next Bake & publish will touch"

    quali: bpy.props.EnumProperty(
        items=[("all", "All", "Everything the deck can publish"),
               ("none", "None", "Clear the selection"),
               ("stale", "Stale", "Only what has gone stale since its bake")],
        default="all")  # type: ignore

    def execute(self, context):
        deck = context.scene.em_publication_deck
        for riga in deck.righe:
            if self.quali == "none":
                riga.selezionata = False
            elif self.quali == "stale":
                riga.selezionata = (riga.stato == "stale")
            else:
                #: «All» vuol dire tutto ciò che si PUÒ pubblicare: offrire di
                #: selezionare un master sarebbe offrire un gesto che poi
                #: rifiuta riga per riga
                riga.selezionata = riga.pubblicabile
        return {'FINISHED'}


class EM_OT_deck_publish(Operator):
    """**Bake & publish** sulla selezione — e non è un secondo baker.

    Mette in fila `em.publish_distribution` (che a sua volta usa la promozione
    allo store e `promote_resource`) su ogni riga selezionata, e riporta cosa è
    successo a **ciascuna**: un'operazione su molte righe non deve congelare
    Blender in silenzio.

    Regola 24: un difetto di programmazione emerge; un elemento che fallisce si
    dichiara fallito e l'insieme prosegue.
    """

    bl_idname = "em.deck_publish"
    bl_label = "Publish selected"
    bl_description = ("Upload the selected distributions to the store and "
                      "record address, checksum and provenance for each. "
                      "Nothing is published automatically: this is the gesture")

    @classmethod
    def poll(cls, context):
        deck = getattr(context.scene, "em_publication_deck", None)
        if deck is None or not any(r.selezionata for r in deck.righe):
            cls.poll_message_set("Select at least one asset first")
            return False
        return True

    def execute(self, context):
        deck = context.scene.em_publication_deck
        scelte = [r for r in deck.righe if r.selezionata]
        fatti, falliti, saltati = [], [], []

        # LO STORE SI CHIEDE UNA VOLTA SOLA, prima del giro.
        #
        # Misurato: senza store, dieci righe selezionate davano dieci
        # fallimenti identici («the object store is unavailable»). Dieci volte
        # la stessa frase non è un resoconto, è rumore — e nasconde il fatto
        # che il problema è UNO e non dieci. È la stessa regola per cui il
        # sommario dice quante righe sono pubblicabili: non si offre un gesto
        # che poi rifiuta riga per riga.
        from ..resources_tab import resource_backend
        if not resource_backend.minio_supported():
            self.report({'ERROR'},
                        "The object store is unavailable: needs the dev "
                        "s3dgraphy (./em.sh s3d) and the 'minio' extra. "
                        "Nothing was published.")
            return {'CANCELLED'}

        wm = context.window_manager
        wm.progress_begin(0, len(scelte))
        try:
            for indice, riga in enumerate(scelte):
                wm.progress_update(indice)
                if not riga.pubblicabile:
                    #: SALTATO non è FALLITO: la riga diceva già perché, e
                    #: chiamarlo fallimento renderebbe il resoconto illeggibile
                    saltati.append(f"{riga.name} ({riga.perche_no})")
                    continue
                try:
                    esito = bpy.ops.em.publish_distribution(
                        resource_id=riga.node_id)
                except DIFETTI_DI_PROGRAMMAZIONE:
                    raise
                except Exception as exc:  # noqa: BLE001 — una riga storta
                    falliti.append(f"{riga.name}: {exc}")
                    continue
                if 'FINISHED' in esito:
                    fatti.append(riga.name)
                else:
                    falliti.append(f"{riga.name}: refused")
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
            self.report({'WARNING'},
                        f"{len(fatti)} published, {len(falliti)} failed: "
                        + ", ".join(falliti[:3]))
        else:
            self.report({'INFO'},
                        f"{len(fatti)} published"
                        + (f", {len(saltati)} skipped" if saltati else ""))
        bpy.ops.em.deck_refresh()
        return {'FINISHED'}


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
    cartella e si ferma."""

    bl_idname = "em.deck_reveal"
    bl_label = "Reveal"
    bl_description = "Open the folder where these bytes are"

    url: bpy.props.StringProperty(default="")  # type: ignore

    def execute(self, context):
        percorso = bpy.path.abspath(self.url)
        if self.url.startswith(("blend://", "s3://", "http://", "https://")):
            self.report({'WARNING'},
                        "These bytes are not a file on this disk — "
                        "use Copy URI")
            return {'CANCELLED'}
        cartella = os.path.dirname(percorso) if os.path.isfile(percorso) else percorso
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


_CLASSI = (EM_OT_deck_refresh, EM_OT_deck_select, EM_OT_deck_publish,
           EM_OT_deck_rebake, EM_OT_deck_reveal, EM_OT_deck_copy_uri)


def register():
    for cls in _CLASSI:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSI):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001 — unregistering must not fail
            pass
