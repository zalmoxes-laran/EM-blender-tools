# export_operators/heriverse/operator.py
"""Monolithic Heriverse export operator (EXPORT_OT_heriverse).

This class is intentionally kept as a single large operator for now: its
methods are tightly coupled via shared state. Splitting it further is a
separate concern.
"""

import os
import shutil
import uuid

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy.types import Operator

from s3dgraphy import get_graph, get_all_graph_ids
from s3dgraphy.exporter.json_exporter import JSONExporter
# NIGHT-RES/R2 · qui c'era l'import di `ResourceNode` (col ripiego su
# `LinkNode` per s3Dgraphy pre-1.6, NIGHT-RIM/A1). Non serve più: **nessuno dei
# sei siti di questo file conia più un nodo risorsa a mano.** Passano tutti per
# `_registra_bake`, e la classe la importa `resource_levels.assicura_master`,
# che è anche il posto dove un ImportError viene DETTO invece che ingoiato.
from s3dgraphy.nodes.representation_node import RepresentationModelDocNode

from ...functions import *
from ...graph_updaters import *
from ...us_types import ALL_US_TYPES

from .dissemination import (
    predicate_available, publishable_stratigraphic_names)
from .utils import clean_filename, find_layer_collection, get_collection_for_object
from .gltf import export_gltf_with_animation_support


class EXPORT_OT_heriverse(Operator):
    """Export project in Heriverse format"""
    bl_idname = "export.heriverse"
    bl_label = "Export Heriverse Project"
    bl_description = "Export project in Heriverse format with models, proxies and documentation"
    bl_options = {'REGISTER', 'UNDO'}

    #: Gli esiti dell'export in corso. Attributi di CLASSE come default, così
    #: `_fallito` e `_saltato` non esplodono se qualcuno li chiama da un
    #: percorso che non è passato da `execute` — una prova, per esempio. Li
    #: rimpiazza `_azzera_esiti` con liste di istanza a ogni export.
    _esiti_falliti = ()
    _esiti_saltati = ()

    # ── NIGHT-FIN/T4 · FALLITO NON È SALTATO ───────────────────────────────
    #
    # Regola 24, nata dal ramo del tileset rimasto morto per un intero commit
    # range: `export_tilesets` usava `scene` senza averlo mai legato, il
    # `NameError` finiva nell'`except Exception` di turno e usciva come un
    # warning fra i warning. Nessuno se n'è accorto perché **non c'era niente
    # da accorgersi**: la riga diceva la stessa cosa che dice un tileset
    # legittimamente saltato.
    #
    # Due cose, e sono separate.
    #
    # (1) Le eccezioni di PROGRAMMAZIONE non vengono catturate: emergono.
    # (2) Il canale dei warning distingue «è fallito» da «l'ho saltato».

    #: I difetti del CODICE, che non sono condizioni del dato.
    #:
    #: Un `NameError` è sempre un bug. `AttributeError` e `TypeError` possono
    #: nascere anche da un dato storto (un nodo senza `.data`), quindi
    #: rilanciarli **è un compromesso e va detto**: un export che prima
    #: sopravviveva a un oggetto malformato adesso si ferma con un traceback.
    #: È il verso giusto — il gestore esterno di `execute` lo raccoglie e lo
    #: stampa per intero, quindi il difetto si vede invece di nascondersi — e
    #: la cura, quando morde su un dato, è mettere una guardia in QUEL punto,
    #: non rimettere il cappuccio su tutti.
    DIFETTI_DI_PROGRAMMAZIONE = (NameError, AttributeError, TypeError,
                                 ImportError)

    def _fallito(self, cosa, perche, exc=None):
        """Qualcosa si è ROTTO: doveva riuscire e non è riuscito."""
        self._esiti_falliti.append(str(cosa))
        messaggio = f"[export] FALLITO · {cosa}: {perche}"
        em_log(messaggio, "ERROR")
        self.report({'WARNING'}, messaggio)
        if exc is not None:
            import traceback
            traceback.print_exception(type(exc), exc, exc.__traceback__)

    def _saltato(self, cosa, perche, avvisa=False):
        """Qualcosa NON è stato fatto, e andava bene così: non pubblicabile,
        sostituito da un tileset, già estratto, nessun oggetto in scena.

        Voce diversa da `_fallito` perché è una notizia diversa: una la si
        legge e si va avanti, l'altra va guardata. Finché parlavano uguale,
        guardarle tutte costava troppo e non le guardava nessuno.

        `avvisa=True` è il terzo caso, che questa distinzione ha fatto
        emergere: **saltato, ma l'avevi chiesto tu**. Se manca Pillow, la
        compressione delle texture non si fa — non è rotto niente, ma chi ha
        acceso quella casella non deve scoprirlo dai byte. Resta un salto (non
        conta fra i fallimenti) e si fa sentire una volta."""
        self._esiti_saltati.append(str(cosa))
        em_log(f"[export] saltato · {cosa}: {perche}", "INFO")
        if avvisa:
            self.report({'WARNING'}, f"Skipped · {cosa}: {perche}")

    def _azzera_esiti(self):
        self._esiti_falliti = []
        self._esiti_saltati = []

    def _resoconto_esiti(self):
        """Il conto finale, SEMPRE visibile — e questo è il punto.

        MISURATO, e per poco non restava una dichiarazione (decisione 21: la
        strumentazione va provata come il codice). `_saltato` scrive a livello
        INFO, e `em_log` filtra INFO e DEBUG se `verbose_logging` è spento:
        alla prima corsa vera **nessuna delle righe «saltato» compariva**.
        Avevo costruito una distinzione invisibile, che è esattamente il
        difetto che T4 esisteva per togliere.

        Quindi il DETTAGLIO dei saltati resta a INFO — è roba da chi sta
        cercando un perché — ma il CONTO esce sempre, con `print`, che non
        passa da nessun filtro. «3 saltati» è un numero che si vede; tre righe
        in mezzo a duecento no.
        """
        print(f"=== Export: {len(self._esiti_falliti)} failed, "
              f"{len(self._esiti_saltati)} skipped on purpose ===")
        if self._esiti_falliti:
            self.report({'WARNING'},
                        f"Export finished with {len(self._esiti_falliti)} "
                        f"failure(s): {', '.join(self._esiti_falliti[:5])}"
                        + (" …" if len(self._esiti_falliti) > 5 else ""))
        if self._esiti_saltati:
            em_log(f"[export] skipped on purpose: "
                   f"{', '.join(self._esiti_saltati[:10])}", "INFO")

    # ── NIGHT-RES/R2 · IL BAKE, UNA VOLTA SOLA ─────────────────────────────
    #
    # Sei siti di questo file creavano una risorsa durante l'export, ognuno con
    # il suo `ResourceNode(...)` e il suo arco scritti a mano: sei copie della
    # stessa idea, divergenti al primo cambiamento. Adesso passano tutti di
    # qui, e ciò che li distingue è il CASO — chi è il master, e se ce n'è uno.
    #
    # La mappa dei sei casi, decisa con E.D.:
    #
    #   RM in glTF     master il datablock, distribution il file. 1:1.
    #   RM da istanza  il master sta nel .blend LINKATO, non in questo.
    #   proxy          master il datablock, SENZA monte: è nato in Blender.
    #   tileset        N:1 dal CONTAINER, e viaggia come `archive`.
    #   RMDoc          DUE catene: l'immagine e l'artefatto spaziale (il quad
    #                  con la sua camera), che si toccano sulla texture.
    #   RMSF           come l'RM.

    def _registra_bake(self, graph, model_node_id, obj, *, url,
                       file_esportato, etichetta,
                       source_ids=None, packaging=None,
                       oggetti_sorgente=None, con_master=True,
                       suffisso=None, checksum_of=None):
        """Un bake: assicura il master, registra la distribution, e lo dice.

        `con_master=False` è per il tileset esterno e per chi il master non ce
        l'ha in casa: una distribution senza sorgente è un fatto legittimo, e
        inventarle un master direbbe una cosa falsa su dove sono i byte.

        `suffisso` sceglie QUALE distribution si sta scrivendo. Dallo stesso
        insieme di master possono nascerne due — l'albero servito e l'archivio
        che viaggia (NIGHT-FIN/T1) — con id distinti e stabili, e il default
        resta quello di sempre perché cambiarlo renderebbe orfano il nodo di
        ogni grafo già scritto.

        Non solleva mai: un export non deve fallire perché un verbale non si è
        potuto scrivere — ma deve **dirlo**, e questa è la riga che lo dice.
        """
        from ... import resource_levels as _rl
        from ...rm_manager.containers import (
            SUFFISSO_RISORSA_INTERNA as _SUF_MASTER, blend_locator_per,
            impronta_di, misura_oggetto)

        master_id = f"{model_node_id}{_SUF_MASTER}"
        sorgente_id = None
        if con_master and obj is not None:
            locator = blend_locator_per(obj)
            if locator:
                ok_m, perche_m = _rl.assicura_master(
                    graph, master_id=master_id, url=locator,
                    name=f"datablock for {obj.name}", link_to=model_node_id,
                    #: le stesse misure che entrano nell'impronta: dichiararle
                    #: anche sul master permette a chi legge di confrontarlo
                    #: con la sua distribution senza aprire Blender
                    misure=misura_oggetto(obj))
                if ok_m:
                    sorgente_id = master_id
                else:
                    em_log(f"[bake] master {master_id}: {perche_m}", "WARNING")
            else:
                # DETTO, non ingoiato: senza file salvato il locator non è
                # formabile, e la distribution resterà senza sorgente. È il
                # caso in cui la staleness non si può calcolare, e saperlo è
                # metà della cura.
                em_log(f"[bake] {model_node_id}: il file non è salvato, "
                       f"nessun master `blend://` e nessuna staleness "
                       f"calcolabile", "WARNING")

        # R5 · l'impronta STRUTTURALE, non il solo mtime del file. Per il caso
        # N:1 è quella dell'insieme: un tileset è stantio se cambia UNA
        # QUALUNQUE delle sue sorgenti.
        if oggetti_sorgente:
            impronta = _rl.impronta_insieme([impronta_di(o)
                                             for o in oggetti_sorgente])
        else:
            impronta = impronta_di(obj) if obj is not None else ""

        derivata_id = f"{model_node_id}{suffisso or _rl.SUFFISSO_DERIVATA}"
        ok, perche = _rl.registra_derivata(
            graph, derivata_id=derivata_id,
            url=url,
            source_id=sorgente_id,
            source_ids=source_ids,
            link_to=model_node_id,
            name=etichetta,
            file_esportato=file_esportato,
            impronta_del_grezzo=impronta,
            packaging=packaging,
            checksum_of=checksum_of,
            misure=(self._misure_insieme(oggetti_sorgente)
                    if oggetti_sorgente else None))
        if not ok:
            em_log(f"[bake] {derivata_id}: {perche}", "WARNING")
        return ok

    def _catena_immagine(self, graph, doc_node, export_folder):
        """R2/RMDoc · la catena dell'IMMAGINE. → l'id della distribution, o None.

        Master l'originale nel DosCo (la risorsa che il documento ha già),
        distribution la versione servita sotto `dosco/`. `export_dosco` copia
        l'albero con `copytree`, quindi il percorso relativo si conserva e
        l'indirizzo servito è deterministico.

        **La distribution si scrive solo se il file servito c'è davvero.**
        Scriverne una perché *dovrebbe* esserci sarebbe inventare un url —
        precisamente il difetto che `promote_resource` rifiuta quando manca il
        digest, e per la stessa ragione.
        """
        from ... import resource_levels as _rl

        originale = None
        for edge in graph.edges:
            if (edge.edge_type == "has_linked_resource"
                    and edge.edge_source == doc_node.node_id):
                candidato = graph.find_node_by_id(edge.edge_target)
                if candidato is not None and getattr(
                        candidato, "node_type", "") == "resource":
                    originale = candidato
                    break
        if originale is None:
            return None

        #: il MASTER si dichiara comunque: era nato prima che l'asse
        #: esistesse, e lasciarlo muto costringerebbe ogni consumatore a
        #: dedurre che l'originale nel DosCo è una fonte
        if hasattr(originale, "set_tier"):
            originale.set_tier("master")

        relativo = str((getattr(originale, "data", None) or {}).get("url") or "")
        if not relativo:
            return None
        servito = os.path.join(os.path.dirname(export_folder), "dosco", relativo)
        if not os.path.isfile(servito):
            em_log(f"[bake] {originale.node_id}: l'immagine servita non è "
                   f"(ancora) in {servito}; la catena dell'immagine resta al "
                   f"solo master", "DEBUG")
            return None

        distribuzione_id = f"{originale.node_id}{_rl.SUFFISSO_DERIVATA}"
        ok, perche = _rl.registra_derivata(
            graph, derivata_id=distribuzione_id,
            url=f"dosco/{relativo}",
            source_id=originale.node_id,
            link_to=doc_node.node_id,
            name=f"served image for {doc_node.name}",
            file_esportato=servito,
            packaging="file")
        if not ok:
            em_log(f"[bake] {distribuzione_id}: {perche}", "WARNING")
            return None
        return distribuzione_id

    @staticmethod
    def _registra_allineamento(graph, rmdoc_node_id, transform):
        """R2/RMDoc · la camera, sul MASTER spaziale.

        L'allineamento — dove sta la foto nello spazio, con che orientamento e
        che scala — non è geometria e non si ricalcola da niente: è il lavoro a
        mano di rimettere una foto storica nel punto da cui fu scattata. Sta
        sul master perché il master è ciò che non si rifà: la distribuzione si
        riesporta premendo un bottone, questo no.

        Il nodo RMDoc continua a portarlo com'è sempre stato — non si sposta
        niente, si AGGIUNGE dove serve. Due copie dello stesso fatto sarebbero
        un problema se una delle due fosse modificabile a parte; qui il master
        lo riceve dall'export insieme alla distribuzione, nello stesso atto.
        """
        from ...rm_manager.containers import SUFFISSO_RISORSA_INTERNA
        master = graph.find_node_by_id(f"{rmdoc_node_id}{SUFFISSO_RISORSA_INTERNA}")
        if master is None or not transform:
            return
        master.data["alignment"] = dict(transform)

    @staticmethod
    def _sostituito_dal_tileset(scene, nome_oggetto) -> bool:
        """R3 · questa mesh è coperta da un tileset di container?

        Retro-compatibile per costruzione: un container che non dichiara
        niente normalizza a `members` e questa funzione torna False, quindi
        l'export continua a decidere con i flag per oggetto — che è
        esattamente il comportamento storico.
        """
        from ...rm_manager import publication_strategy as _ps
        from ...rm_manager.containers import find_container_for_mesh

        indice = find_container_for_mesh(scene, nome_oggetto)
        if indice is None:
            return False
        container = scene.rm_containers[indice]
        if not _ps.il_tileset_sostituisce(
                getattr(container, "publication_strategy", "")):
            return False
        #: …e il tileset stesso non è un membro sostituito da sé
        oggetto = bpy.data.objects.get(nome_oggetto)
        return oggetto is not None and "tileset_path" not in oggetto

    def _due_distribuzioni_del_tileset(self, graph, obj, model_node_id, *,
                                       zip_sorgente, cartella_export,
                                       nome_tileset, url_albero, porta,
                                       sorgenti, membri_ogg):
        """NIGHT-FIN/T1 · un tileset ha DUE distribuzioni, non una.

        La notte scorsa `packaging="archive"` è stato giustamente rifiutato:
        questo export scompatta lo zip e serve un albero, e dichiarare un
        archivio sarebbe stata una bugia. Ma l'intenzione — *il tileset viaggia
        come zip, per non demolire dischi e banda con inflating e deflating* —
        riguarda il **trasporto e l'archiviazione**, non ciò che il viewer
        carica. Le due cose convivono, e il modello le regge già: dallo stesso
        insieme di master nascono due distribution con id distinti e stabili,
        ciascuna col suo checksum.

        * `…_link` — `directory`, l'albero servito, la porta è `tileset.json`.
          È quella che Heriverse carica.
        * `…_archive` — `archive`, lo zip, per viaggiare e per l'archivio.

        **COME SONO PRODOTTI I BYTE, dichiarato**: lo zip si **copia**, non si
        ricomprime dall'albero. Ricomprimere darebbe byte diversi per lo stesso
        contenuto a ogni export — compressori, timestamp, ordine delle voci —
        quindi un checksum diverso ogni volta, e con lui un nodo nuovo a ogni
        giro: addio idempotenza, che è la proprietà su cui si regge tutto il
        resto. Lo zip di partenza esiste già ed è esattamente quei byte.

        **NESSUNA DELLE DUE DICHIARA CIÒ CHE SU DISCO NON C'È**: ognuna si
        scrive solo dopo aver visto il proprio file. Se la copia non riesce,
        l'archivio non viene scritto e lo si dice.
        """
        import shutil
        from ... import resource_levels as _rl

        # ── (1) l'albero servito ───────────────────────────────────────────
        if os.path.isfile(porta):
            self._registra_bake(
                graph, model_node_id, obj,
                url=url_albero,
                #: il digest è quello della PORTA, non dell'albero intero:
                #: percorrere migliaia di file è precisamente il costo che
                #: impacchettare esiste per evitare. Dichiarato, perché un
                #: checksum parziale non dichiarato mente su cosa verifica.
                file_esportato=porta,
                checksum_of="entry-point",
                etichetta=f"Tileset for {obj.name}",
                source_ids=sorgenti, oggetti_sorgente=membri_ogg,
                packaging="directory", con_master=False)
        else:
            self._saltato(f"tileset {obj.name}",
                          f"l'albero servito non c'è ({porta}): nessuna "
                          f"distribuzione `directory` scritta")

        # ── (2) l'archivio che viaggia ─────────────────────────────────────
        zip_servito = os.path.join(cartella_export, f"{nome_tileset}.zip")
        if not os.path.isfile(zip_servito):
            try:
                shutil.copy2(zip_sorgente, zip_servito)
            except OSError as exc:
                # DETTO, e la distribuzione NON si scrive: un locator che punta
                # a un file che non c'è è peggio di un locator assente, perché
                # sembra un indirizzo.
                self._fallito(f"tileset {obj.name}",
                              f"copia dell'archivio fallita ({exc}): nessuna "
                              f"distribuzione `archive` scritta")
                return
        self._registra_bake(
            graph, model_node_id, obj,
            url=f"tilesets/{nome_tileset}.zip",
            file_esportato=zip_servito,
            etichetta=f"Tileset archive for {obj.name}",
            source_ids=sorgenti, oggetti_sorgente=membri_ogg,
            packaging="archive", con_master=False,
            suffisso=_rl.SUFFISSO_ARCHIVIO)

    def _sorgenti_del_tileset(self, context, graph, tileset_obj):
        """R2+R3 · i master che questo tileset accorpa, e gli oggetti membri.

        Torna `([], [])` quando il tileset **arriva da fuori** e non c'è un
        container che lo dichiari suo: è il caso frequente, ed è una
        distribution senza sorgente — un fatto legittimo, non un dato mancante.
        Inventarle degli ingressi renderebbe la genesi una bugia e la staleness
        un conto su sorgenti che non esistono.

        Le sorgenti si prendono SOLO quando il container dichiara la strategia
        `tileset`: è la dichiarazione a dire «questo sta al posto dei membri»,
        e senza di quella il tileset e le mesh sono due cose che convivono.
        """
        from ...rm_manager import publication_strategy as _ps
        from ...rm_manager.containers import (
            SUFFISSO_RISORSA_INTERNA as _SUF_MASTER, find_container_for_mesh,
            resolve_rm_node_id)

        scene = context.scene
        indice = find_container_for_mesh(scene, tileset_obj.name)
        if indice is None:
            return [], []
        container = scene.rm_containers[indice]
        if not _ps.il_tileset_sostituisce(
                getattr(container, "publication_strategy", "")):
            return [], []

        from ... import resource_levels as _rl
        from ...rm_manager.containers import blend_locator_per, misura_oggetto

        membri, master_per_membro = [], {}
        for voce in container.mesh_names:
            if voce.name == tileset_obj.name:
                continue                    # il tileset non è sorgente di sé
            membri.append(voce.name)
            altro = bpy.data.objects.get(voce.name)
            if altro is None:
                continue
            rm_id = resolve_rm_node_id(graph, altro, scene=scene)
            if not rm_id:
                continue
            master_id = f"{rm_id}{_SUF_MASTER}"
            # IL MASTER DEL MEMBRO LO SCRIVIAMO QUI, e la ragione è una buca
            # trovata misurando: con la strategia `tileset` il membro non
            # passa dal bake, quindi **nessuno gli dava il locator** — e il
            # processo N:1 finiva col nominare come ingressi dei nodi senza
            # indirizzo. Una genesi che cita sorgenti irraggiungibili è
            # peggio di una senza sorgenti: sembra completa.
            #
            # Che una mesh abbia i suoi byte in questo .blend è un fatto suo,
            # e non dipende da come il container sceglie di pubblicarsi.
            locator = blend_locator_per(altro)
            if locator:
                ok_m, perche_m = _rl.assicura_master(
                    graph, master_id=master_id, url=locator,
                    name=f"datablock for {altro.name}", link_to=rm_id,
                    misure=misura_oggetto(altro))
                if not ok_m:
                    em_log(f"[bake] master {master_id}: {perche_m}", "WARNING")
                    continue
            master_per_membro[voce.name] = master_id
        sorgenti = _ps.sorgenti_del_tileset(membri, master_per_membro)
        oggetti = [bpy.data.objects.get(n) for n in membri]
        return sorgenti, [o for o in oggetti if o is not None]

    @staticmethod
    def _misure_insieme(oggetti):
        """I conteggi sommati di N sorgenti — quanto pesa davvero un tileset.

        Sommati e non elencati: a chi sceglie serve sapere l'ordine di
        grandezza di ciò che sta per scaricare, non la distribuzione fra i
        membri, che è un fatto sul rilievo e non sulla distribuzione.
        """
        from ...rm_manager.containers import misura_oggetto
        totale = {"tiles": 0, "v": 0, "f": 0}
        for o in oggetti or []:
            m = misura_oggetto(o)
            totale["tiles"] += 1
            totale["v"] += int(m.get("v") or 0)
            totale["f"] += int(m.get("f") or 0)
        return totale if totale["tiles"] else None

    def get_stratigraphic_names_from_graphs(self, context, export_all_graphs=False):
        """
        Ottiene i nomi di tutti i nodi stratigrafici dai grafi caricati.
        Considera solo i grafi pubblicabili se export_all_graphs è True.
        
        Args:
            context: Blender context
            export_all_graphs: Se True, esporta da tutti i grafi pubblicabili, altrimenti solo da quello attivo
            
        Returns:
            set: Set di nomi di nodi stratigrafici
        """
        from s3dgraphy import get_graph, get_all_graph_ids
        
        stratigraphic_names = set()
        
        if export_all_graphs:
            # Itera su tutti i grafi caricati, ma considera solo quelli pubblicabili
            em_tools = context.scene.em_tools
            
            published_graph_ids = []
            for graphml_item in em_tools.graphml_files:
                # Controlla se il grafo è pubblicabile
                is_publishable = getattr(graphml_item, 'is_publishable', True)  # Default True se proprietà mancante
                if is_publishable:
                    published_graph_ids.append(graphml_item.name)
            
            em_log(f"Found {len(published_graph_ids)} publishable graphs: {published_graph_ids}", "DEBUG")
            
            for graph_id in published_graph_ids:
                graph = get_graph(graph_id)
                if graph:
                    names = self._extract_stratigraphic_names_from_graph(graph)
                    stratigraphic_names.update(names)
                    em_log(f"Graph '{graph_id}': found {len(names)} stratigraphic nodes", "DEBUG")
        else:
            # Solo il grafo attivo
            em_tools = context.scene.em_tools
            if em_tools.active_file_index >= 0 and len(em_tools.graphml_files) > 0:
                graphml = em_tools.graphml_files[em_tools.active_file_index]
                graph = get_graph(graphml.name)
                if graph:
                    names = self._extract_stratigraphic_names_from_graph(graph)
                    stratigraphic_names.update(names)
                    em_log(f"Active graph '{graphml.name}': found {len(names)} stratigraphic nodes", "DEBUG")
            else:
                em_log("No active graph found", "WARNING")
        
        return stratigraphic_names

    def _extract_stratigraphic_names_from_graph(self, graph):
        """
        Estrae i nomi dei nodi stratigrafici da un singolo grafo usando gli indici.
        
        Args:
            graph: Il grafo s3dgraphy
            
        Returns:
            list: Lista di nomi di nodi stratigrafici
        """
        # Questo elenco comanda quali proxy .glb finiscono nella scena, quindi
        # è una superficie di disseminazione quanto il grafo: i tombstone
        # restano fuori. Regola, predicato e limite stanno in
        # ``.dissemination`` — modulo separato perché senza ``bpy`` si può
        # misurare headless.
        names, removed = publishable_stratigraphic_names(graph, ALL_US_TYPES)

        if removed:
            em_log(f"Heriverse export: {removed} nodi rimossi (tombstone) "
                   f"esclusi dai proxy", "DEBUG")
        elif not predicate_available():
            em_log("s3dgraphy.dissemination non disponibile: i tombstone non "
                   "vengono filtrati dall'export Heriverse", "WARNING")

        return names


    def export_proxies(self, context, export_folder):
        """Export proxy models"""
        scene = context.scene
        export_vars = context.window_manager.export_vars

        # Get the active graph
        graph = None
        em_tools = context.scene.em_tools
        if em_tools.active_file_index >= 0 and len(em_tools.graphml_files) > 0:
            graphml = em_tools.graphml_files[em_tools.active_file_index]
            graph = get_graph(graphml.name)

        # Store original collection states
        collection_states = {}
        for collection in bpy.data.collections:
            layer_collection = find_layer_collection(context.view_layer.layer_collection, collection.name)
            if layer_collection:
                collection_states[collection.name] = {
                    'exclude': layer_collection.exclude,
                    'hide_viewport': collection.hide_viewport
                }

        # Store original object states
        object_states = {}
        for ob in bpy.data.objects:
            if ob.type == 'MESH':
                object_states[ob.name] = {
                    'hide_viewport': ob.hide_viewport,
                    'hide_select': ob.hide_select
                }

        try:
            # Make all collections visible
            for collection in bpy.data.collections:
                layer_collection = find_layer_collection(context.view_layer.layer_collection, collection.name)
                if layer_collection:
                    layer_collection.exclude = False
                collection.hide_viewport = False

            # Make all objects visible and selectable
            for ob in bpy.data.objects:
                if ob.type == 'MESH':
                    ob.hide_viewport = False
                    ob.hide_select = False

            # Deseleziona tutto prima di iniziare
            bpy.ops.object.select_all(action='DESELECT')

            # ⭐ MODIFICA PRINCIPALE: Usa i nomi dai grafi invece di em_list
            has_multiple_graphs = len(em_tools.graphml_files) > 1

            stratigraphic_names = self.get_stratigraphic_names_from_graphs(
                context,
                has_multiple_graphs  # True se multigrafo, False se singolo grafo
            )

            em_log(f"Found {len(stratigraphic_names)} stratigraphic nodes across graphs", "DEBUG")
            
            exported_count = 0
            skipped_count = 0

            # Debug: Lista tutti gli oggetti mesh disponibili
            all_mesh_objects = [obj.name for obj in bpy.data.objects if obj.type == 'MESH']
            em_log(f"Available mesh objects in scene: {len(all_mesh_objects)}", "DEBUG")

            # ✅ OPTIMIZATION: Add progress bar for long export operations
            wm = context.window_manager
            total_proxies = len(stratigraphic_names)
            wm.progress_begin(0, total_proxies)
            em_log(f"\n[EXPORT] Starting export of {total_proxies} proxies with progress bar...", "DEBUG")

            for idx, name in enumerate(stratigraphic_names):
                # Update progress bar (shows current/total in status bar)
                wm.progress_update(idx)
                em_log(f"\n[{idx+1}/{total_proxies}] Processing: {name}", "DEBUG")
                # Try exact match first
                proxy = bpy.data.objects.get(name)

                # If not found, try finding object with name ending with ".{stratigraphic_name}"
                # This handles cases where proxy has graph prefix (e.g., "DEMO25.US02")
                if not proxy:
                    suffix = f".{name}"
                    matching_objects = [obj for obj in bpy.data.objects
                                       if obj.type == 'MESH' and obj.name.endswith(suffix)]

                    if matching_objects:
                        # If multiple matches, take the first one
                        proxy = matching_objects[0]
                        if len(matching_objects) > 1:
                            em_log(f"  Warning: Multiple proxies found for '{name}': {[o.name for o in matching_objects]}", "WARNING")
                            em_log(f"           Using: {proxy.name}", "DEBUG")

                # Debug dettagliato
                if not proxy:
                    # T4 · un proxy che non c'è NON è un fallimento: il grafo
                    # nomina un'unità che in questa scena nessuno ha modellato,
                    # che è una situazione ordinaria a metà lavoro.
                    self._saltato(f"proxy {name}",
                                  "nessun oggetto in scena (né esatto né "
                                  f"«*.{name}»)")
                    skipped_count += 1
                    continue

                if proxy.type != 'MESH':
                    em_log(f"  Proxy '{proxy.name}': Found but not a MESH (type: {proxy.type})", "DEBUG")
                    skipped_count += 1
                    continue

                # Verifica se il proxy è pubblicabile (usa il nome reale dell'oggetto)
                is_publishable = True
                if hasattr(context.scene, 'rm_list'):
                    for rm_item in context.scene.rm_list:
                        if rm_item.name == proxy.name:  # Use actual object name, not stratigraphic name
                            is_publishable = rm_item.is_publishable
                            break

                if not is_publishable:
                    self._saltato(f"proxy {proxy.name}",
                                  "marcato non pubblicabile")
                    skipped_count += 1
                    continue

                em_log(f"  Proxy '{proxy.name}': Found and ready to export (strat node: '{name}')", "DEBUG")

                proxy.select_set(True)
                # Use stratigraphic name for export filename (without graph prefix)
                clean_name = clean_filename(name)
                export_file = os.path.join(export_folder, clean_name)

                try:
                    export_gltf_with_animation_support(
                        filepath=export_file,
                        export_vars=export_vars,
                        scene=scene,
                        use_selection=True,
                        format_file='GLB'
                    )
                    exported_count += 1
                    em_log(f"  Successfully exported proxy: {clean_name}.glb", "DEBUG")

                    # Update SemanticShapeNode URL and create LinkNode in the graph
                    # (SemanticShapeNode should already exist from update_graph_with_scene_data)
                    if graph:
                        from s3dgraphy.nodes.semantic_shape_node import SemanticShapeNode

                        # Find the existing SemanticShapeNode
                        shape_node_id = f"{name}_shape"
                        shape_node = graph.find_node_by_id(shape_node_id)

                        if shape_node:
                            # Update URL (should already be set, but update to be sure)
                            shape_node.set_url(f"proxies/{clean_name}.glb")
                            em_log(f"    Updated SemanticShape URL: {shape_node_id}", "DEBUG")

                            # ── NIGHT-RES/R2 · IL PROXY ───────────────────
                            #
                            # Master il datablock, **senza monte**: un proxy è
                            # nato in Blender e non viene da nessuna parte.
                            # Legittimo, e da DICHIARARE tale invece di
                            # lasciargli una provenienza vuota che sembra un
                            # dato mancante.
                            #
                            # E il master **non è il nodo US**: un nodo di
                            # conoscenza non ha byte, e metterlo da quella
                            # parte della derivazione direbbe che un'unità
                            # stratigrafica è un file. Il master è il
                            # datablock, appeso al `SemanticShape` che è la
                            # forma — che è esattamente ciò che il proxy è.
                            self._registra_bake(
                                graph, shape_node_id, proxy,
                                url=f"proxies/{clean_name}.glb",
                                #: il GLB esce con l'estensione attaccata dal
                                #: chiamante: `export_file` è il tronco
                                file_esportato=export_file + ".glb",
                                etichetta=f"Proxy for {name}")
                        else:
                            em_log(f"    Warning: SemanticShape node '{shape_node_id}' not found (should have been created by update_graph_with_scene_data)", "WARNING")

                except self.DIFETTI_DI_PROGRAMMAZIONE:
                    raise          # T4 · un difetto del codice non si maschera
                except Exception as e:
                    self._fallito(f"proxy {name}", str(e), e)

                proxy.select_set(False)

            # ✅ End progress bar
            wm.progress_end()

            em_log(f"\nProxy export summary:", "DEBUG")
            em_log(f"  - Total stratigraphic nodes: {len(stratigraphic_names)}", "DEBUG")
            em_log(f"  - Successfully exported: {exported_count}", "DEBUG")
            em_log(f"  - Skipped: {skipped_count}", "WARNING")

            self.report({'INFO'}, f"Exported {exported_count} proxies")
            return exported_count > 0
            
        finally:
            # Restore original collection states
            for collection_name, state in collection_states.items():
                collection = bpy.data.collections.get(collection_name)
                if collection:
                    layer_collection = find_layer_collection(context.view_layer.layer_collection, collection_name)
                    if layer_collection:
                        layer_collection.exclude = state['exclude']
                    collection.hide_viewport = state['hide_viewport']
            
            # Restore original object states
            for object_name, state in object_states.items():
                obj = bpy.data.objects.get(object_name)
                if obj:
                    obj.hide_viewport = state['hide_viewport']
                    obj.hide_select = state['hide_select']

    # Function to export tilesets
    def export_tilesets(self, context, export_folder):
        """Export Cesium tileset files"""
        em_log("\n--- Exporting Cesium Tilesets ---", "INFO")
        
        # Create tilesets directory if it doesn't exist
        os.makedirs(export_folder, exist_ok=True)
        
        # Get export variables
        export_vars = context.window_manager.export_vars
        
        # Ottieni il grafo attivo
        graph = None
        if hasattr(context.scene, 'em_tools') and context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        # Find all tileset objects
        tileset_objects = [obj for obj in bpy.data.objects if "tileset_path" in obj]
        
        # If no tilesets, return early
        if not tileset_objects:
            em_log("No tileset objects found in scene", "DEBUG")
            return 0
        
        exported_count = 0
        skipped_count = 0
        
        # Process each tileset
        for obj in tileset_objects:
            # Verifica se l'oggetto è pubblicabile
            is_publishable = True
            for rm_item in context.scene.rm_list:
                if rm_item.name == obj.name:
                    is_publishable = rm_item.is_publishable
                    break
            
            if not is_publishable:
                self._saltato(f"tileset {obj.name}", "marcato non pubblicabile")
                continue
                
            try:
                tileset_path = obj["tileset_path"]
                if not tileset_path:
                    self._saltato(f"tileset {obj.name}",
                                  "`tileset_path` vuoto")
                    continue
                    
                # Percorso assoluto
                abs_path = bpy.path.abspath(tileset_path)
                
                if not os.path.exists(abs_path):
                    self.report({'WARNING'}, f"Tileset file not found: {abs_path}")
                    continue
                    
                # Nome del file senza estensione
                filename = os.path.basename(abs_path)
                tileset_name = os.path.splitext(filename)[0]
                
                # Crea directory per questo tileset
                tileset_dir = os.path.join(export_folder, tileset_name)
                os.makedirs(tileset_dir, exist_ok=True)
                
                # Verifica se il tileset è già stato estratto
                tileset_json_path = os.path.join(tileset_dir, "tileset.json")
                tileset_extracted = False
                
                if export_vars.heriverse_skip_extracted_tilesets and os.path.exists(tileset_json_path):
                    self._saltato(f"tileset {filename}",
                                  "già estratto (le distribuzioni si scrivono "
                                  "lo stesso: i byte ci sono)")
                    skipped_count += 1
                    tileset_extracted = True
                else:
                    # Estrai il file ZIP
                    em_log(f"Extracting tileset '{filename}' - this may take some time...", "DEBUG")
                    import zipfile
                    with zipfile.ZipFile(abs_path, 'r') as zip_ref:
                        zip_ref.extractall(tileset_dir)
                    em_log(f"Extracted tileset: {obj.name} -> {tileset_dir}", "DEBUG")
                    exported_count += 1
                    tileset_extracted = True
                
                # Se il tileset è stato estratto correttamente (o era già estratto),
                # aggiorna o crea il nodo Link nel grafo
                if tileset_extracted and graph:
                    # NIGHT-RIM/A4 · l'id dell'RM viene da `resolve_rm_node_id`:
                    # legge `em_rm_node_id` e ripiega sull'eredità
                    # `f"{nome}_model"` migrandola una volta sola. Il nome
                    # dell'oggetto è un'etichetta, non un identificatore. Il
                    # ripiego finale sull'eredità resta per il caso in cui il
                    # nodo non sia (ancora) nel grafo: qui si sta per crearlo.
                    from ...rm_manager.containers import resolve_rm_node_id
                    # `context.scene` e non `scene`: in questo metodo `scene`
                    # non è mai stato legato, quindi qui si sollevava
                    # `NameError` e l'`except Exception` di sotto lo
                    # trasformava in un warning. Effetto: **il ramo del
                    # tileset non è mai girato** da d1868fd in poi — nessun
                    # nodo risorsa per nessun tileset, e il sintomo era una
                    # riga di log fra le altre. Trovato misurando, non
                    # leggendo.
                    model_node_id = (resolve_rm_node_id(graph, obj,
                                                        scene=context.scene)
                                     or f"{obj.name}_model")
                    model_node = graph.find_node_by_id(model_node_id)
                    
                    if model_node:
                        # Percorso relativo al tileset.json
                        relative_tileset_path = f"tilesets/{tileset_name}/tileset.json"
                        
                        # Aggiorna l'URL nel nodo RM
                        model_node.url = relative_tileset_path
                        
                        # Assicurati che ci sia la trasformazione per orientare correttamente il tileset
                        if not hasattr(model_node, 'data'):
                            model_node.data = {}

                        model_node.transform = model_node.data.get('transform', {})
                        model_node.transform['rotation'] = ["-1.57079632679", "0.0", "0.0"]
                        model_node.data['transform'] = model_node.transform
                        
                        # ── NIGHT-RES/R2 · IL TILESET ──────────────────────
                        #
                        # Un tileset Cesium **fa le veci di un RM container**:
                        # accorpa in un'entità rigida un insieme di tile che
                        # singolarmente sono mesh editabili. Due conseguenze,
                        # e sono tutte e due qui:
                        #
                        # (1) IMPACCHETTAMENTO — e qui la misura ha corretto
                        #     il disegno. Un tileset VIAGGIA come zip, ed è il
                        #     motivo per cui `archive` è cittadino di prima
                        #     classe: una cartella da migliaia di tile
                        #     massacra dischi e banda. Ma **questo export lo
                        #     scompatta** (`zip_ref.extractall`) e pubblica un
                        #     albero servito, con `tileset.json` come porta:
                        #     quindi ciò che il consumatore riceve è una
                        #     `directory`, non un archivio.
                        #
                        #     Dichiarare `archive` qui sarebbe esattamente la
                        #     bugia che l'asse esiste per impedire — e si
                        #     vedrebbe subito: Heriverse salta ciò che è
                        #     impacchettato in archivio, perché scompattare
                        #     non lo sa fare. Lo zip resta l'input, non la
                        #     forma della distribuzione.
                        #
                        #     Il giorno che la catena servirà lo zip senza
                        #     aprirlo, questa riga dirà `archive` e il
                        #     consumatore leggerà il vero.
                        #
                        # (2) DERIVAZIONE N:1 quando il container lo dichiara
                        #     (R3): la sorgente è l'insieme dei master dei
                        #     membri, non un singolo RM, e il DTC regge un
                        #     processo con più ingressi nativamente. Stantio se
                        #     cambia UNA QUALUNQUE delle N sorgenti.
                        #
                        # E il caso frequente e diverso: un tileset che **arriva
                        # da fuori** non ha master in casa. Distribution senza
                        # sorgente, e l'audit la conta fra quelle — un fatto
                        # legittimo, non un dato mancante.
                        sorgenti, membri_ogg = self._sorgenti_del_tileset(
                            context, graph, obj)
                        self._due_distribuzioni_del_tileset(
                            graph, obj, model_node_id,
                            zip_sorgente=abs_path,
                            cartella_export=export_folder,
                            nome_tileset=tileset_name,
                            url_albero=relative_tileset_path,
                            porta=tileset_json_path,
                            sorgenti=sorgenti, membri_ogg=membri_ogg)
                        
            except self.DIFETTI_DI_PROGRAMMAZIONE:
                # T4 · QUI è dove il `NameError` su `scene` è rimasto a
                # travestirsi da warning per un intero commit range. Adesso
                # emerge.
                raise
            except Exception as e:
                self._fallito(f"tileset {obj.name}", str(e), e)

        # Mostra un resoconto
        if exported_count > 0 or skipped_count > 0:
            self.report({'INFO'}, f"Tilesets: {exported_count} extracted, {skipped_count} skipped (already extracted)")
        
        return exported_count + skipped_count

    # Name of the panorama used as project-wide default (defaults.panorama)
    DEFAULT_PANORAMA_NAME = "defsky.jpg"

    def _addon_root(self):
        """Absolute path of the addon root.

        This file lives in <addon>/export_operators/heriverse/, so the root is
        three levels up: with only two the search fell inside export_operators/
        and never found resources/panorama/defsky.jpg.
        """
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Miglioramento della funzione export_panorama
    def export_panorama(self, context, project_path):
        """Export default panorama (defsky.jpg) to the project"""
        scene = context.scene
        
        if not scene.heriverse_export_panorama:
            return False
            
        try:
            # Create panorama directory
            panorama_path = os.path.join(project_path, "panorama")
            os.makedirs(panorama_path, exist_ok=True)
            
            # Get addon path to find resources
            addon_path = self._addon_root()
            resources_path = os.path.join(addon_path, "resources")

            # Cerca in diversi percorsi possibili per trovare defsky.jpg
            name = self.DEFAULT_PANORAMA_NAME
            possible_paths = [
                os.path.join(resources_path, "panorama", name),
                os.path.join(resources_path, name),
                os.path.join(addon_path, "panorama", name),
                os.path.join(addon_path, name)
            ]
            
            source_file = None
            for path in possible_paths:
                if os.path.exists(path):
                    source_file = path
                    break
                    
            if not source_file:
                # Se non troviamo il file, creiamo un'immagine di segnaposto
                self.report({'WARNING'}, "Default panorama file not found, creating placeholder")
                
                # Crea un'immagine vuota
                img = bpy.data.images.new("defsky", 1024, 512)
                img.filepath = os.path.join(panorama_path, self.DEFAULT_PANORAMA_NAME)
                img.file_format = 'JPEG'
                img.save()
                
                return True
                
            # Copy the file
            dest_file = os.path.join(panorama_path, self.DEFAULT_PANORAMA_NAME)
            shutil.copy2(source_file, dest_file)
            em_log(f"Copied default panorama from {source_file} to {dest_file}", "DEBUG")
            return True
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export panorama: {str(e)}")
            return False

    def export_epoch_panoramas(self, context, project_path):
        """Copy per-epoch HDR/panorama files into the project panorama folder.

        Returns a dict mapping epoch name -> relative panorama path (e.g.
        "panorama/my_hdr.hdr") for epochs that have custom lighting with a
        valid file.  Epochs without custom lighting are not included.
        """
        scene = context.scene
        epochs = scene.em_tools.epochs.list
        panorama_dir = os.path.join(project_path, "panorama")
        os.makedirs(panorama_dir, exist_ok=True)

        epoch_pano_map = {}
        # Destination names already taken inside the panorama folder.  The
        # default panorama is reserved up front so an epoch HDR that happens
        # to be called defsky.jpg cannot overwrite it.
        claimed = {self.DEFAULT_PANORAMA_NAME: None}
        for epoch in epochs:
            if not epoch.epoch_lighting_enabled or not epoch.epoch_hdr_path:
                continue
            abs_path = os.path.normpath(bpy.path.abspath(epoch.epoch_hdr_path))
            if not os.path.isfile(abs_path):
                self.report({'WARNING'},
                            f"Epoch '{epoch.name}': HDR file not found, skipping: {abs_path}")
                continue
            filename = self._claim_panorama_filename(claimed, abs_path)
            dest = os.path.join(panorama_dir, filename)
            if not os.path.isfile(dest) or not os.path.samefile(abs_path, dest):
                shutil.copy2(abs_path, dest)
                em_log(f"Copied epoch panorama '{filename}' for epoch '{epoch.name}'", "DEBUG")
            epoch_pano_map[epoch.name] = f"panorama/{filename}"
        return epoch_pano_map

    def _claim_panorama_filename(self, claimed, abs_path):
        """Return a free filename for abs_path inside the panorama folder.

        Two epochs can point to different HDR files sharing the same basename
        (or to a file named like the default panorama): the second one gets a
        numbered suffix instead of silently overwriting the first.  The same
        source file reused by several epochs keeps a single copy.
        """
        filename = os.path.basename(abs_path)
        stem, ext = os.path.splitext(filename)
        candidate = filename
        index = 1
        while candidate in claimed and claimed[candidate] != abs_path:
            index += 1
            candidate = f"{stem}_{index}{ext}"
        claimed[candidate] = abs_path
        return candidate

    def update_json_with_epoch_lighting(self, json_data, context, epoch_pano_map=None):
        """Inject per-epoch panorama/lighting data into the exported JSON.

        For each epoch node in the JSON that has custom lighting configured in
        Blender, adds panorama, panorama_rotation, and panorama_intensity
        to its data dict.  Epochs without custom lighting are left untouched
        (the consumer falls back to defaults.panorama).

        The paths come from epoch_pano_map, the map returned by
        export_epoch_panoramas: it is the only place that knows which file was
        actually written, including when a name had to be de-duplicated.
        """
        scene = context.scene
        epochs_bl = scene.em_tools.epochs.list
        epoch_pano_map = epoch_pano_map or {}

        # Build lookup: epoch name -> Blender epoch item
        bl_lookup = {ep.name: ep for ep in epochs_bl}

        if 'graphs' not in json_data:
            return json_data

        for graph_id, graph_data in json_data['graphs'].items():
            epoch_nodes = (graph_data.get('nodes') or {}).get('epochs')
            if not epoch_nodes:
                continue
            for node_id, node_data in epoch_nodes.items():
                node_name = node_data.get('name', '')
                bl_epoch = bl_lookup.get(node_name)
                if bl_epoch is None:
                    continue
                rel_path = epoch_pano_map.get(node_name)
                if not rel_path:
                    continue
                if 'data' not in node_data:
                    node_data['data'] = {}
                node_data['data']['panorama'] = rel_path
                node_data['data']['panorama_rotation'] = bl_epoch.epoch_hdr_rotation
                node_data['data']['panorama_intensity'] = bl_epoch.epoch_hdr_intensity

        return json_data

    def compress_textures_in_folder(self, folder_path, scene):
        """
        Compresses all textures in a folder and its subfolders in a single pass.
        
        Args:
            folder_path (str): Path to the folder containing textures to compress
            scene (bpy.types.Scene): Blender scene containing compression settings
        """
        if not scene.heriverse_enable_compression:
            return
            
        # Import required libraries
        import os
        
        try:
            # Import Pillow
            from PIL import Image
            
            em_log(f"\n=== Compressing all textures in {folder_path} ===", "INFO")
            
            # Settings
            max_res = scene.heriverse_texture_max_res
            quality = scene.heriverse_texture_quality
            
            # Track statistics
            total_processed = 0
            total_resized = 0
            total_size_before = 0
            total_size_after = 0
            
            # Process all image files in the directory and subdirectories
            for root, dirs, files in os.walk(folder_path):
                for filename in files:
                    if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.tga')):
                        file_path = os.path.join(root, filename)
                        
                        try:
                            # Get original file size
                            file_size_before = os.path.getsize(file_path)
                            total_size_before += file_size_before
                            
                            # Open the image with Pillow
                            img = Image.open(file_path)
                            
                            # Check if resizing is needed
                            width, height = img.size
                            needs_resize = max(width, height) > max_res
                            
                            if needs_resize:
                                # Calculate new dimensions while preserving aspect ratio
                                if width > height:
                                    new_width = max_res
                                    new_height = int(height * (max_res / width))
                                else:
                                    new_height = max_res
                                    new_width = int(width * (max_res / height))
                                    
                                # Use high-quality resampling
                                img = img.resize((new_width, new_height), Image.LANCZOS)
                                total_resized += 1
                            
                            # Save with appropriate format and compression
                            if img.mode == 'RGBA' and filename.lower().endswith('.png'):
                                # Save as PNG with compression for transparency
                                img.save(file_path, 'PNG', optimize=True)
                            else:
                                # Convert to RGB if needed and save as JPEG
                                if img.mode != 'RGB':
                                    img = img.convert('RGB')
                                img.save(file_path, 'JPEG', quality=quality, optimize=True)
                            
                            # Get new file size
                            file_size_after = os.path.getsize(file_path)
                            total_size_after += file_size_after
                            
                            total_processed += 1
                            
                        except Exception as e:
                            em_log(f"Error processing {filename}: {str(e)}", "ERROR")
            
            # Calculate size reduction
            size_reduction_mb = (total_size_before - total_size_after) / (1024 * 1024)
            percentage_reduction = ((total_size_before - total_size_after) / total_size_before * 100) if total_size_before > 0 else 0
            
            em_log(f"Texture compression summary:", "DEBUG")
            em_log(f"- Total textures processed: {total_processed}", "DEBUG")
            em_log(f"- Textures resized: {total_resized}", "DEBUG")
            em_log(f"- Size before: {total_size_before / (1024 * 1024):.2f} MB", "DEBUG")
            em_log(f"- Size after: {total_size_after / (1024 * 1024):.2f} MB", "DEBUG")
            em_log(f"- Size reduction: {size_reduction_mb:.2f} MB ({percentage_reduction:.1f}%)", "DEBUG")
            
            return total_processed
            
        except ImportError:
            self._saltato("texture compression",
                          "Pillow non è installato", avvisa=True)
            return 0
        except Exception as e:
            em_log(f"Error during texture compression: {str(e)}", "ERROR")
            import traceback
            traceback.print_exc()
            return 0

    # Modifica alla funzione export_rm per supportare GPU instances
    def export_rm(self, context, export_folder):
        """Export representation models with GPU instancing support"""
        scene = context.scene
        export_vars = context.window_manager.export_vars
        
        # Raggruppa gli oggetti per mesh condivisa
        mesh_groups = {}
        self.instanced_objects = set()
        self.exported_models = {}

        # Store original collection states
        collection_states = {}
        for collection in bpy.data.collections:
            layer_collection = find_layer_collection(context.view_layer.layer_collection, collection.name)
            if layer_collection:
                collection_states[collection.name] = {
                    'exclude': layer_collection.exclude,
                    'hide_viewport': collection.hide_viewport
                }

        # Store original object states
        object_states = {}
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                object_states[obj.name] = {
                    'hide_viewport': obj.hide_viewport,
                    'hide_select': obj.hide_select
                }

        # Save the active object so we can restore it after export
        original_active = context.view_layer.objects.active

        try:
            # Make all collections visible — handle BOTH the monitor icon (collection.hide_viewport,
            # disables in viewports across all layers) AND the eye icon (layer_collection.hide_viewport,
            # per-layer outliner hide). If only one is reset, an object can still end up un-selectable.
            for collection in bpy.data.collections:
                layer_collection = find_layer_collection(context.view_layer.layer_collection, collection.name)
                if layer_collection:
                    layer_collection.exclude = False
                    layer_collection.hide_viewport = False
                collection.hide_viewport = False
                collection.hide_select = False

            # Make all objects visible and selectable
            for obj in bpy.data.objects:
                if obj.type == 'MESH':
                    obj.hide_viewport = False
                    obj.hide_select = False
                    try:
                        obj.hide_set(False)  # local viewport hide (H key) — distinct from hide_viewport
                    except Exception:
                        pass

            # Deseleziona tutto prima di iniziare
            bpy.ops.object.select_all(action='DESELECT')

            # Step 1: Raccogli tutti gli oggetti RM pubblicabili
            publishable_rm_objects = []
            for obj in bpy.data.objects:
                # Skip oggetti che non sono mesh o non hanno epoche
                if not (obj.type == 'MESH' and hasattr(obj, "EM_ep_belong_ob") and len(obj.EM_ep_belong_ob) > 0):
                    continue
                    
                # Skip se oggetto è un tileset
                if "tileset_path" in obj:
                    continue
                    
                # ── R3 · LA STRATEGIA DEL CONTAINER, prima del flag ────
                #
                # Se il container di questa mesh dichiara di viaggiare come UN
                # tileset, il membro non produce una distribuzione propria: il
                # tileset sta al suo posto, ed è la regola che evita il
                # doppione al viewer.
                #
                # Il flag per oggetto **non viene letto né riscritto** in quel
                # caso: resta dov'è e torna a contare il giorno che la
                # strategia torna a `members`. Migrarlo vorrebbe dire
                # interpretare la volontà di qualcuno e poi cancellarne la
                # prova.
                if self._sostituito_dal_tileset(scene, obj.name):
                    self._saltato(obj.name,
                                  "il suo container si pubblica come UN "
                                  "tileset: il tileset sta al suo posto")
                    continue

                # Skip se oggetto non è pubblicabile
                is_publishable = True
                for rm_item in scene.rm_list:
                    if rm_item.name == obj.name:
                        is_publishable = rm_item.is_publishable
                        break
                        
                if not is_publishable:
                    continue
                    
                publishable_rm_objects.append(obj)

            # Step 2: Raggruppa per mesh condivisa (solo se GPU instancing è abilitato)
            if export_vars.heriverse_use_gpu_instancing:
                for obj in publishable_rm_objects:
                    if obj.data:
                        mesh_name = obj.data.name
                        if mesh_name not in mesh_groups:
                            mesh_groups[mesh_name] = []
                        mesh_groups[mesh_name].append(obj)
            else:
                # Se GPU instancing è disabilitato, ogni oggetto va da solo
                for obj in publishable_rm_objects:
                    mesh_name = f"{obj.name}_unique"
                    mesh_groups[mesh_name] = [obj]

            em_log(f"Found {len(mesh_groups)} different meshes in {len(publishable_rm_objects)} publishable RM objects", "DEBUG")

            # Ottieni il grafo attivo
            graph = None
            if context.scene.em_tools.active_file_index >= 0:
                graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                graph = get_graph(graphml.name)

            exported_count = 0

            # Step 3: Process each group
            for mesh_name, objects in mesh_groups.items():
                if len(objects) == 1 or not export_vars.heriverse_use_gpu_instancing:
                    # Single object, export normally
                    obj = objects[0]
                    try:
                        # Clear stale selection from previous iteration and make obj active,
                        # otherwise bpy.ops.export_scene.gltf(use_selection=True) writes an empty scene.
                        bpy.ops.object.select_all(action='DESELECT')
                        # Force per-object visibility (mirrors export_rmdoc) — the global
                        # unhide pass at the top can be defeated by nested layer_collections.
                        obj.hide_viewport = False
                        obj.hide_select = False
                        try:
                            obj.hide_set(False)
                        except Exception:
                            pass
                        obj.select_set(True)
                        context.view_layer.objects.active = obj
                        # Diagnostic: what will bpy.ops.export_scene.gltf actually see?
                        sel_view = [o.name for o in context.view_layer.objects if o.select_get()]
                        sel_ctx = [o.name for o in bpy.context.selected_objects]
                        in_vl = obj.name in context.view_layer.objects
                        verts = len(obj.data.vertices) if obj.data else 0
                        mods = [m.type for m in obj.modifiers]
                        em_log(f"RM '{obj.name}': in_view_layer={in_vl}, select_get={obj.select_get()}, "
                               f"verts={verts}, modifiers={mods}, "
                               f"sel_view={len(sel_view)}, sel_ctx={len(sel_ctx)}, "
                               f"hide_viewport={obj.hide_viewport}, hide_render={obj.hide_render}, hide_get={obj.hide_get()}", "DEBUG")
                        if not obj.select_get():
                            self.report({'WARNING'}, f"RM '{obj.name}' not selectable — collection probably not linked to active scene. Will produce empty GLTF.")
                        export_file = os.path.join(export_folder, clean_filename(obj.name))

                        export_gltf_with_animation_support(
                            filepath=export_file,
                            export_vars=export_vars,
                            scene=scene,
                            use_selection=True
                        )

                        # Post-export sanity check: warn loudly if we wrote an empty GLTF
                        produced = export_file + ".gltf"
                        if os.path.exists(produced):
                            try:
                                size = os.path.getsize(produced)
                                bin_path = export_file + ".bin"
                                has_bin = os.path.exists(bin_path)
                                if size < 500 or not has_bin:
                                    msg = f"[heriverse] EMPTY EXPORT for '{obj.name}': gltf={size}B, bin_exists={has_bin}"
                                    em_log(msg, "DEBUG")
                                    self.report({'WARNING'}, msg)
                            except Exception:
                                pass

                        # Crea o aggiorna il nodo Link
                        if graph:
                            # NIGHT-RIM/A4 · l'id dell'RM viene da `resolve_rm_node_id`:
                            # legge `em_rm_node_id` e ripiega sull'eredità
                            # `f"{nome}_model"` migrandola una volta sola. Il nome
                            # dell'oggetto è un'etichetta, non un identificatore. Il
                            # ripiego finale sull'eredità resta per il caso in cui il
                            # nodo non sia (ancora) nel grafo: qui si sta per crearlo.
                            from ...rm_manager.containers import resolve_rm_node_id
                            model_node_id = (resolve_rm_node_id(graph, obj, scene=scene)
                                             or f"{obj.name}_model")
                            model_node = graph.find_node_by_id(model_node_id)
                            
                            if model_node:
                                # Percorso relativo per l'export
                                gltf_path = f"models/{clean_filename(obj.name)}.gltf"
                                
                                # ── NIGHT-RIM3/B3.1 · IL BAKER SCRIVE IL VERBALE
                                #
                                # Questo export È il baker: produce le versioni
                                # ottimizzate. Prima coniava un nodo risorsa
                                # qualunque e gli metteva un url; adesso
                                # REGISTRA — id conservato, provenienza dal
                                # grezzo, digest dei byte prodotti, evento D7 —
                                # e lo fa chiamando `promote_resource`, che
                                # tutto questo lo sa già fare.
                                #
                                # DUE NODI, TRE STATI (decisione 10): il grezzo
                                # è la risorsa `blend://` nata alla promozione
                                # (B2) e NON si tocca; questa è la DERIVATA.
                                # Diventerà «pubblicata» quando il suo locator
                                # risolverà a un URI raggiungibile — non c'è un
                                # terzo nodo e non si conia vocabolario.
                                # NIGHT-RES/R2 · lo stesso verbale, ma scritto
                                # da `_registra_bake` invece che qui: era il
                                # primo dei sei casi a essere convertito e il
                                # modello su cui si sono misurati gli altri —
                                # adesso è uno dei sei e non un'eccezione.
                                #
                                # L'impronta è cambiata sotto (R5): era
                                # `mtime:<int>:size:<int>` del file che
                                # contiene il master, adesso è STRUTTURALE. La
                                # vecchia rendeva stantie tutte le derivate a
                                # ogni salvataggio del .blend.
                                self._registra_bake(
                                    graph, model_node_id, obj,
                                    url=gltf_path,
                                    file_esportato=export_file + ".gltf",
                                    etichetta=f"GLTF for {obj.name}")

                        # Deselect object
                        obj.select_set(False)
                        
                        exported_count += 1
                        em_log(f"Exported RM: {obj.name}", "DEBUG")
                        
                    except self.DIFETTI_DI_PROGRAMMAZIONE:
                        obj.select_set(False)
                        raise          # T4
                    except Exception as e:
                        self._fallito(f"RM {obj.name}", str(e), e)
                        obj.select_set(False)

                elif len(objects) > 1 and export_vars.heriverse_use_gpu_instancing:
                    # Multiple objects with same mesh - instancing enabled
                    try:
                        # Step 3.1: Deselect all
                        bpy.ops.object.select_all(action='DESELECT')
                        
                        # Step 3.2: Find most suitable primary object for this group
                        # Preferisci oggetti con nomi più corti o senza numeri alla fine
                        sorted_objects = sorted(objects, key=lambda obj: (len(obj.name), obj.name))
                        primary_obj = sorted_objects[0]
                        
                        # Step 3.3: Non è più necessario gestire hide_viewport perché tutti gli oggetti sono già visibili
                        
                        # Step 3.4: Seleziona e imposta active l'oggetto primario
                        primary_obj.select_set(True)
                        context.view_layer.objects.active = primary_obj
                        
                        # Step 3.5: Seleziona gli altri oggetti nel gruppo
                        for obj in objects:
                            if obj != primary_obj:
                                obj.select_set(True)
                                # Aggiungi alla lista di oggetti istanziati
                                self.instanced_objects.add(obj.name)
                        
                        # Step 3.6: Prepara il nome del file
                        export_file = os.path.join(export_folder, clean_filename(primary_obj.name))

                        # Diagnostic for instancing path
                        sel_view = [o.name for o in context.view_layer.objects if o.select_get()]
                        sel_ctx = [o.name for o in bpy.context.selected_objects]
                        primary_verts = len(primary_obj.data.vertices) if primary_obj.data else 0
                        em_log(f"INSTANCING '{primary_obj.name}': group_size={len(objects)}, "
                               f"primary_verts={primary_verts}, sel_view={len(sel_view)}, sel_ctx={len(sel_ctx)}, "
                               f"hide_render={primary_obj.hide_render}", "DEBUG")

                        # Step 3.7: Export with instancing enabled
                        export_gltf_with_animation_support(
                            filepath=export_file,
                            export_vars=export_vars,
                            scene=scene,
                            use_selection=True,
                            export_extras=True,
                            export_gpu_instances=True
                        )

                        # Post-export sanity check
                        produced = export_file + ".gltf"
                        if os.path.exists(produced):
                            try:
                                size = os.path.getsize(produced)
                                bin_path = export_file + ".bin"
                                has_bin = os.path.exists(bin_path)
                                if size < 500 or not has_bin:
                                    msg = f"[heriverse] EMPTY INSTANCED EXPORT '{primary_obj.name}': gltf={size}B, bin_exists={has_bin}"
                                    em_log(msg, "DEBUG")
                                    self.report({'WARNING'}, msg)
                            except Exception:
                                pass

                        # Crea o aggiorna il nodo Link per l'oggetto primario
                        if graph:
                            # NIGHT-RIM/A4 · l'id dell'RM viene da `resolve_rm_node_id`:
                            # legge `em_rm_node_id` e ripiega sull'eredità
                            # `f"{nome}_model"` migrandola una volta sola. Il nome
                            # dell'oggetto è un'etichetta, non un identificatore. Il
                            # ripiego finale sull'eredità resta per il caso in cui il
                            # nodo non sia (ancora) nel grafo: qui si sta per crearlo.
                            from ...rm_manager.containers import resolve_rm_node_id
                            model_node_id = (resolve_rm_node_id(graph, primary_obj, scene=scene)
                                             or f"{primary_obj.name}_model")
                            model_node = graph.find_node_by_id(model_node_id)
                            
                            if model_node:
                                # Percorso relativo per l'export
                                gltf_path = f"models/{clean_filename(primary_obj.name)}.gltf"

                                # ── NIGHT-RES/R2 · RM DA ISTANZA ───────────
                                #
                                # Il caso che cambia dove sta il master: NON è
                                # nel file aperto. È nel .blend linkato, e il
                                # locator deve citare QUEL file
                                # (`rilievo2015.blend#Object/tile10`) — lo
                                # studio aperto è contesto, non indirizzo.
                                # `blend_locator_per` guarda le tre forme del
                                # linking (oggetto, mesh, collection) in ordine
                                # di precisione.
                                #
                                # Se il file linkato si sposta il master
                                # diventa irrisolvibile. È informazione, non un
                                # guasto: l'audit lo conta fra le irrisolvibili
                                # e nessuno finge che i byte siano altrove.
                                self._registra_bake(
                                    graph, model_node_id, primary_obj,
                                    url=gltf_path,
                                    file_esportato=export_file + ".gltf",
                                    etichetta=f"GLTF for {primary_obj.name}")
                        
                        # Step 3.8: Registra il gruppo di istanze per l'esportazione JSON
                        self.exported_models[primary_obj.name] = [obj.name for obj in objects]
                        
                        em_log(f"Exported instanced group: {primary_obj.name} with {len(objects)} instances", "DEBUG")
                        exported_count += 1
                        
                    except self.DIFETTI_DI_PROGRAMMAZIONE:
                        raise          # T4
                    except Exception as e:
                        self._fallito(f"instanced group {mesh_name}", str(e), e)
                    
                    finally:
                        # Deselect all objects in group
                        for obj in objects:
                            obj.select_set(False)

            # Compress textures if enabled
            if exported_count > 0 and scene.heriverse_enable_compression:
                self.compress_textures_in_folder(export_folder, scene)
                em_log(f"Compressed textures for {exported_count} RM models", "DEBUG")

            self.report({'INFO'}, f"Exported {exported_count} RM models")
            return exported_count > 0

        finally:
            # Restore original collection states
            for collection_name, state in collection_states.items():
                collection = bpy.data.collections.get(collection_name)
                if collection:
                    layer_collection = find_layer_collection(context.view_layer.layer_collection, collection_name)
                    if layer_collection:
                        layer_collection.exclude = state['exclude']
                    collection.hide_viewport = state['hide_viewport']

            # Restore original object states
            for object_name, state in object_states.items():
                obj = bpy.data.objects.get(object_name)
                if obj:
                    obj.hide_viewport = state['hide_viewport']
                    obj.hide_select = state['hide_select']

            # Restore the original active object
            try:
                context.view_layer.objects.active = original_active
            except Exception:
                pass

    def get_y_up_transform():
        """Returns the standard transform for converting z-up to y-up models"""
        return {
            "position": ["0.0", "0.0", "0.0"],
            "rotation": ["-1.57079632679", "0.0", "0.0"],  # -90 degrees in radians around X axis
            "scale": ["1.0", "1.0", "1.0"]
        }

    def export_paradata_objects(self, context, export_folder):
        """Export paradata objects (documents, extractors, combiners) as RMDoc"""
        scene = context.scene
        export_vars = context.window_manager.export_vars
        
        # Se l'export degli RMDoc non è abilitato, esci
        if not export_vars.heriverse_export_rmdoc:
            return 0
        
        # Store original collection states
        collection_states = {}
        for collection in bpy.data.collections:
            # Get the layer collection
            layer_collection = find_layer_collection(context.view_layer.layer_collection, collection.name)
            if layer_collection:
                collection_states[collection.name] = {
                    'exclude': layer_collection.exclude,
                    'hide_viewport': collection.hide_viewport
                }
        
        # Store original object states
        object_states = {}
        for ob in bpy.data.objects:
            if ob.type == 'MESH':
                object_states[ob.name] = {
                    'hide_viewport': ob.hide_viewport,
                    'hide_select': ob.hide_select
                }
        
        try:
            # Make all collections visible
            for collection in bpy.data.collections:
                layer_collection = find_layer_collection(context.view_layer.layer_collection, collection.name)
                if layer_collection:
                    layer_collection.exclude = False
                collection.hide_viewport = False
            
            # Make all objects visible and selectable
            for ob in bpy.data.objects:
                if ob.type == 'MESH':
                    ob.hide_viewport = False
                    ob.hide_select = False
        
            # Ottieni il grafo attivo
            graph = None
            if context.scene.em_tools.active_file_index >= 0:
                graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                graph = get_graph(graphml.name)
            
            if not graph:
                return 0
            
            # Deseleziona tutto prima di iniziare
            bpy.ops.object.select_all(action='DESELECT')
            
            # Conta elementi esportati
            exported_count = 0
            
            # Lista di nodi paradata da controllare
            paradata_nodes = []
            # ✅ OPTIMIZATION: Use s3dgraphy indices instead of iterating graph.nodes 3 times
            # Single lookup for each type using indices (O(1) per type)
            paradata_nodes.extend(graph.indices.nodes_by_type.get('document', []))
            paradata_nodes.extend(graph.indices.nodes_by_type.get('extractor', []))
            paradata_nodes.extend(graph.indices.nodes_by_type.get('combiner', []))
            
            # Memorizza oggetto attivo originale
            original_active = context.view_layer.objects.active
            
            # Per ogni nodo paradata, controlla se esiste un oggetto corrispondente
            for paradata_node in paradata_nodes:
                obj = bpy.data.objects.get(paradata_node.name)
                
                if obj and obj.type == 'MESH':
                    try:
                        # Salva lo stato dell'oggetto
                        was_hidden = obj.hide_viewport
                        was_select = obj.hide_select
                        
                        # Assicurati che l'oggetto sia visibile e selezionabile
                        obj.hide_viewport = False
                        obj.hide_select = False
                        
                        # Salva la trasformazione originale
                        original_location = obj.location.copy()
                        original_rotation = obj.rotation_euler.copy() if obj.rotation_mode == 'XYZ' else obj.rotation_quaternion.copy()
                        original_rotation_mode = obj.rotation_mode
                        original_scale = obj.scale.copy()
                        
                        # Seleziona l'oggetto e rendilo attivo
                        obj.select_set(True)
                        context.view_layer.objects.active = obj
                        
                        # Salva la trasformazione per il nodo RMDoc
                        # Converti in stringhe per memorizzazione nel nodo
                        transform = {
                            "position": [f"{original_location.x}", f"{original_location.y}", f"{original_location.z}"],
                            "rotation": [],
                            "scale": [f"{original_scale.x}", f"{original_scale.y}", f"{original_scale.z}"]
                        }
                        
                        # Gestisci la rotazione in base alla modalità
                        if original_rotation_mode == 'XYZ':
                            transform["rotation"] = [f"{original_rotation.x}", f"{original_rotation.y}", f"{original_rotation.z}"]
                        else:
                            # Converti quaternione in euler per il nodo
                            euler = original_rotation.to_euler('XYZ')
                            transform["rotation"] = [f"{euler.x}", f"{euler.y}", f"{euler.z}"]
                        
                        # Azzera le trasformazioni per l'esportazione
                        obj.location = (0, 0, 0)
                        if obj.rotation_mode == 'XYZ':
                            obj.rotation_euler = (0, 0, 0)
                        else:
                            obj.rotation_quaternion = (1, 0, 0, 0)
                        obj.scale = (1, 1, 1)
                        
                        # Applica la trasformazione per sicurezza
                        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                        
                        # Prepara il nome file
                        export_file = os.path.join(export_folder, clean_filename(obj.name))
                        
                        # Convert any non-Principled BSDF materials before export
                        materials_converted = []
                        for mat_slot in obj.material_slots:
                            if mat_slot.material:
                                if convert_material_to_principled(mat_slot.material):
                                    materials_converted.append(mat_slot.material.name)
                                    
                        if materials_converted:
                            em_log(f"Converted materials to Principled BSDF for {obj.name}: {', '.join(materials_converted)}", "DEBUG")

                        # Esporta come GLTF
                        
                        export_gltf_with_animation_support(
                            filepath=export_file,
                            export_vars=export_vars,
                            scene=scene,
                            use_selection=True
                        )

                        # Crea nodo RMDoc e LinkNode se il grafo è disponibile
                        if graph:

                            # Percorso relativo per l'export
                            gltf_path = f"models_docs/{clean_filename(obj.name)}.gltf"
                            
                            # ID del nodo RMDoc
                            rmdoc_node_id = f"{paradata_node.node_id}_rm_doc"
                            
                            # Verifica se il nodo RMDoc esiste già
                            rmdoc_node = graph.find_node_by_id(rmdoc_node_id)
                            if not rmdoc_node:
                                # Crea il nodo RMDoc con la trasformazione salvata
                                rmdoc_node = RepresentationModelDocNode(
                                    node_id=rmdoc_node_id,
                                    name=f"RM for {paradata_node.name}",
                                    type="RM",
                                    transform=transform,
                                    description=f"Representation model for {paradata_node.node_type} {paradata_node.name}"
                                )
                                
                                # Imposta l'URL nel dizionario data
                                rmdoc_node.data["url"] = gltf_path
                                
                                # Aggiungi al grafo
                                graph.add_node(rmdoc_node)
                                
                                # Collega il nodo RMDoc al nodo paradata
                                edge_id = f"{paradata_node.node_id}_has_representation_model_doc_{rmdoc_node_id}"
                                if not graph.find_edge_by_id(edge_id):
                                    graph.add_edge(
                                        edge_id=edge_id,
                                        edge_source=paradata_node.node_id,
                                        edge_target=rmdoc_node_id,
                                        edge_type="has_representation_model_doc"
                                    )
                            else:
                                # Aggiorna il nodo esistente
                                rmdoc_node.transform = transform
                                rmdoc_node.data["transform"] = transform
                                rmdoc_node.data["url"] = gltf_path
                            
                            # ── NIGHT-RES/R2 · L'RMDoc, DUE CATENE ────────
                            #
                            # È il caso che non assomiglia agli altri: qui si
                            # incontrano due catene di natura diversa.
                            #
                            # (a) L'IMMAGINE — master l'originale nel DosCo,
                            #     distribution la versione servita.
                            #
                            # (b) L'ARTEFATTO SPAZIALE — master il datablock
                            #     del quad **con la sua camera**, distribution
                            #     il glb esportato.
                            #
                            # La camera non è geometria: è un **atto di
                            # allineamento**. Una foto storica rimessa nel
                            # punto da cui fu scattata, da traguardare in
                            # trasparenza contro il modello dell'environment.
                            # Non si ricalcola da niente — è un master a tutti
                            # gli effetti, e perderla vuol dire rifare a mano
                            # il lavoro di qualcuno.
                            #
                            # E le due catene SI TOCCANO: la texture della
                            # distribuzione spaziale deriva dalla distribuzione
                            # dell'immagine.
                            immagine = self._catena_immagine(
                                graph, paradata_node, export_folder)
                            self._registra_bake(
                                graph, rmdoc_node_id, obj,
                                url=gltf_path,
                                file_esportato=export_file + ".gltf",
                                etichetta=f"GLTF for {paradata_node.name}",
                                #: l'ingresso in più: da dove viene la texture
                                source_ids=[immagine] if immagine else None)
                            #: l'allineamento sta sul MASTER spaziale, che è
                            #: l'unico posto dove non si perde rifacendo il
                            #: bake — la distribution si rifà, lui no
                            self._registra_allineamento(
                                graph, rmdoc_node_id, transform)
                        
                        # Ripristina la trasformazione originale
                        obj.location = original_location
                        if original_rotation_mode == 'XYZ':
                            obj.rotation_euler = original_rotation
                        else:
                            obj.rotation_mode = original_rotation_mode
                            obj.rotation_quaternion = original_rotation
                        obj.scale = original_scale
                        
                        # Ripristina lo stato dell'oggetto
                        obj.hide_viewport = was_hidden
                        obj.hide_select = was_select
                        obj.select_set(False)
                        
                        exported_count += 1
                        em_log(f"Exported Paradata RM: {obj.name}", "DEBUG")
                        
                    except self.DIFETTI_DI_PROGRAMMAZIONE:
                        raise          # T4
                    except Exception as e:
                        self._fallito(f"paradata RM {obj.name}", str(e), e)
                        
                        # Tenta di ripristinare l'oggetto in caso di errore
                        try:
                            obj.location = original_location
                            if original_rotation_mode == 'XYZ':
                                obj.rotation_euler = original_rotation
                            else:
                                obj.rotation_mode = original_rotation_mode
                                obj.rotation_quaternion = original_rotation
                            obj.scale = original_scale
                        except:
                            pass
                        
                        # Deseleziona l'oggetto in caso di errore
                        obj.select_set(False)
            
            # Ripristina oggetto attivo originale
            context.view_layer.objects.active = original_active
            
            # Compressione texture
            if exported_count > 0:
                self.compress_paradata_textures(export_folder, scene)
            
            return exported_count
            
        finally:
            # Restore original collection states
            for collection_name, state in collection_states.items():
                collection = bpy.data.collections.get(collection_name)
                if collection:
                    layer_collection = find_layer_collection(context.view_layer.layer_collection, collection_name)
                    if layer_collection:
                        layer_collection.exclude = state['exclude']
                    collection.hide_viewport = state['hide_viewport']
            
            # Restore original object states
            for object_name, state in object_states.items():
                obj = bpy.data.objects.get(object_name)
                if obj:
                    obj.hide_viewport = state['hide_viewport']
                    obj.hide_select = state['hide_select']

    def compress_paradata_textures(self, folder_path, scene):
        """
        Comprime le texture degli oggetti ParaData
        
        Args:
            folder_path (str): Percorso della cartella contenente i modelli ParaData
            scene (bpy.types.Scene): Scena Blender con le impostazioni
        """
        # Verifica se PIL è disponibile
        try:
            from PIL import Image
            pil_available = True
        except ImportError:
            self._saltato("ParaData texture compression",
                          "Pillow non è installato", avvisa=True)
            return
        
        max_res = scene.heriverse_rmdoc_texture_max_res
        quality = scene.heriverse_rmdoc_texture_quality
        
        # Trova tutti i file texture nella cartella
        processed_count = 0
        total_size_before = 0
        total_size_after = 0
        
        # Percorri i file nella cartella cercando texture
        for root, dirs, files in os.walk(folder_path):
            for filename in files:
                if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    file_path = os.path.join(root, filename)
                    
                    try:
                        # Dimensione originale
                        file_size_before = os.path.getsize(file_path)
                        total_size_before += file_size_before
                        
                        # Apri l'immagine con PIL
                        img = Image.open(file_path)
                        width, height = img.size
                        
                        # Verifica se è necessario ridimensionare
                        needs_resize = max(width, height) > max_res
                        
                        if needs_resize:
                            # Mantieni proporzioni durante il ridimensionamento
                            if width > height:
                                new_width = max_res
                                new_height = int(height * (max_res / width))
                            else:
                                new_height = max_res
                                new_width = int(width * (max_res / height))
                            
                            # Ridimensiona con alta qualità
                            img = img.resize((new_width, new_height), Image.LANCZOS)
                        
                        # Salva con il livello di qualità specificato
                        if img.mode in ['RGBA', 'LA'] or (img.mode == 'P' and 'transparency' in img.info):
                            # Salva PNG per immagini con trasparenza
                            img.save(file_path, 'PNG', optimize=True)
                        else:
                            # Converti in RGB se necessario e salva come JPEG
                            if img.mode != 'RGB':
                                img = img.convert('RGB')
                            img.save(file_path, 'JPEG', quality=quality, optimize=True)
                        
                        # Dimensione dopo la compressione
                        file_size_after = os.path.getsize(file_path)
                        total_size_after += file_size_after
                        
                        processed_count += 1
                        
                    except Exception as e:
                        em_log(f"Error processing texture {filename}: {str(e)}", "ERROR")
        
        # Calcola statistiche
        if processed_count > 0:
            size_reduction_mb = (total_size_before - total_size_after) / (1024 * 1024)
            reduction_percent = (total_size_before - total_size_after) / total_size_before * 100 if total_size_before > 0 else 0
            
            em_log(f"ParaData texture compression: processed {processed_count} files", "DEBUG")
            em_log(f"Size before: {total_size_before / (1024 * 1024):.2f} MB", "DEBUG")
            em_log(f"Size after: {total_size_after / (1024 * 1024):.2f} MB", "DEBUG")
            em_log(f"Reduction: {size_reduction_mb:.2f} MB ({reduction_percent:.1f}%)", "DEBUG")

    def update_json_for_instancing(self, json_data):
        """
        Aggiorna i dati JSON per riflettere le relazioni di instancing.
        Da chiamare dopo l'esportazione del JSON principale.
        """
        # Verifica se abbiamo dati di istanziazione
        if not hasattr(self, 'instanced_objects') or not hasattr(self, 'exported_models'):
            return json_data
        
        if len(self.instanced_objects) == 0:
            return json_data
        
        # Itera attraverso tutti i grafi nel JSON
        if 'graphs' in json_data:
            for graph_id, graph_data in json_data['graphs'].items():
                # Modifica i nodi RM per riflettere l'instancing
                if 'nodes' in graph_data and 'representation_models' in graph_data['nodes']:
                    rm_nodes = graph_data['nodes']['representation_models']

                    # Per ogni modello primario, aggiungi informazioni sulle istanze
                    for primary_name, instances in self.exported_models.items():
                        if primary_name in rm_nodes:
                            primary_node = rm_nodes[primary_name]
                            
                            # Aggiungi informazioni sulle istanze
                            if 'data' not in primary_node:
                                primary_node['data'] = {}
                            
                            primary_node['data']['instances'] = instances
                            primary_node['data']['is_instance_group'] = True
                    
                    for rm_name, rm_node in rm_nodes.items():
                        if 'data' in rm_node and 'url' in rm_node['data']:
                            url = rm_node['data']['url']
                            if url and 'tileset.json' in url:
                                if 'transform' not in rm_node['data']:
                                    rm_node['data']['transform'] = {
                                        'rotation': ["-1.57079632679", "0.0", "0.0"]
                                    }
                    # Rimuovi i nodi assorbiti come istanze
                    for rm_name in list(rm_nodes.keys()):
                        if rm_name in self.instanced_objects:
                            del rm_nodes[rm_name]

                if 'edges' in graph_data:
                    for edge_type in graph_data['edges']:
                        # Lavora su una copia della lista per poterla modificare durante l'iterazione
                        edges_to_keep = []
                        for edge in graph_data['edges'][edge_type]:
                            # Mantieni l'edge solo se né from né to sono nei nodi saltati
                            if (edge['from'] not in self.instanced_objects and 
                                edge['to'] not in self.instanced_objects):
                                edges_to_keep.append(edge)
                        
                        # Sostituisci con la lista filtrata
                        graph_data['edges'][edge_type] = edges_to_keep

        return json_data

    def export_textures(self, obj, textures_dir, context):
        """Export textures for an object with optional compression"""
        scene = context.scene
        
        for mat_slot in obj.material_slots:
            if mat_slot.material and mat_slot.material.use_nodes:
                for node in mat_slot.material.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image:
                        try:
                            image = node.image
                            if image.packed_file:
                                image_path = os.path.join(textures_dir, clean_filename(image.name))
                                em_log(f"Exporting packed texture: {image.name}", "DEBUG")
                                
                                # If compression is enabled
                                if scene.heriverse_enable_compression:
                                    # Store original settings
                                    original_format = scene.render.image_settings.file_format
                                    original_quality = scene.render.image_settings.quality
                                    
                                    # Apply compression settings
                                    scene.render.image_settings.file_format = 'JPEG'
                                    scene.render.image_settings.quality = scene.heriverse_texture_quality
                                    
                                    # If image needs scaling
                                    needs_scaling = (image.size[0] > scene.heriverse_texture_max_res or 
                                                    image.size[1] > scene.heriverse_texture_max_res)
                                    
                                    if needs_scaling:
                                        # Create a temporary copy and scale it
                                        temp_image = image.copy()
                                        max_dim = max(temp_image.size[0], temp_image.size[1])
                                        scale_factor = scene.heriverse_texture_max_res / max_dim
                                        new_width = int(temp_image.size[0] * scale_factor)
                                        new_height = int(temp_image.size[1] * scale_factor)
                                        temp_image.scale(new_width, new_height)
                                        temp_image.save_render(image_path)
                                        bpy.data.images.remove(temp_image)
                                    else:
                                        # Just save with compression settings
                                        image.save_render(image_path)
                                        
                                    # Restore original settings
                                    scene.render.image_settings.file_format = original_format
                                    scene.render.image_settings.quality = original_quality
                                else:
                                    # Export without compression
                                    image.save_render(image_path)
                            elif image.filepath:
                                src_path = bpy.path.abspath(image.filepath)
                                if os.path.exists(src_path):
                                    dst_path = os.path.join(textures_dir, clean_filename(os.path.basename(image.filepath)))
                                    em_log(f"Copying external texture: {os.path.basename(image.filepath)}", "DEBUG")
                                    
                                    # If compression is enabled, load and process the image
                                    if scene.heriverse_enable_compression:
                                        # Create a temporary image
                                        temp_image = bpy.data.images.load(src_path)
                                        
                                        # Store original settings
                                        original_format = scene.render.image_settings.file_format
                                        original_quality = scene.render.image_settings.quality
                                        
                                        # Apply compression settings
                                        scene.render.image_settings.file_format = 'JPEG'
                                        scene.render.image_settings.quality = scene.heriverse_texture_quality
                                        
                                        # Check if scaling is needed
                                        needs_scaling = (temp_image.size[0] > scene.heriverse_texture_max_res or 
                                                        temp_image.size[1] > scene.heriverse_texture_max_res)
                                        
                                        if needs_scaling:
                                            max_dim = max(temp_image.size[0], temp_image.size[1])
                                            scale_factor = scene.heriverse_texture_max_res / max_dim
                                            new_width = int(temp_image.size[0] * scale_factor)
                                            new_height = int(temp_image.size[1] * scale_factor)
                                            temp_image.scale(new_width, new_height)
                                        
                                        # Save with compression
                                        temp_image.save_render(dst_path)
                                        
                                        # Clean up
                                        bpy.data.images.remove(temp_image)
                                        
                                        # Restore original settings
                                        scene.render.image_settings.file_format = original_format
                                        scene.render.image_settings.quality = original_quality
                                    else:
                                        # Simple copy without compression
                                        shutil.copy2(src_path, dst_path)
                        except self.DIFETTI_DI_PROGRAMMAZIONE:
                            raise          # T4
                        except Exception as e:
                            self._fallito(f"texture for {obj.name}", str(e), e)

    def export_dosco(self, context, graph_id, dosco_path):
        """Export DosCo files for a graph"""
        em_tools = context.scene.em_tools
        
        # Se non è specificato un graph_id, usa il file attivo
        if not graph_id and em_tools.active_file_index >= 0:
            graphml = em_tools.graphml_files[em_tools.active_file_index]
        else:
            # Trova il file GraphML corrispondente al graph_id
            graphml = None
            for gfile in em_tools.graphml_files:
                if gfile.name == graph_id:
                    graphml = gfile
                    break
        
        if not graphml or not graphml.dosco_dir:
            self.report({'WARNING'}, "No DosCo directory specified")
            return False
        
        src_path = bpy.path.abspath(graphml.dosco_dir)
        if not os.path.exists(src_path):
            self.report({'WARNING'}, f"DosCo path does not exist: {src_path}")
            return False
        
        try:
            shutil.copytree(src_path, dosco_path, dirs_exist_ok=True)
            em_log(f"Copied DosCo files from {src_path} to {dosco_path}", "DEBUG")
            return True
        except Exception as e:
            self.report({'ERROR'}, f"Failed to copy DosCo files: {str(e)}")
            return False

    def create_project_zip(self, project_path: str, zip_name: str = None):
        """Creates a ZIP archive of the exported project"""
        if zip_name is None:
            zip_name = os.path.basename(project_path)
            
        zip_path = os.path.join(os.path.dirname(project_path), f"{zip_name}.zip")
        
        if os.path.exists(zip_path):
            os.remove(zip_path)
            
        shutil.make_archive(
            os.path.splitext(zip_path)[0],
            'zip',
            project_path
        )
        
        return zip_path

    def export_rmsf_models(self, context, export_folder):
        """Export Special Find models (RMSF)"""
        scene = context.scene
        export_vars = context.window_manager.export_vars
        
        # Store original collection states
        collection_states = {}
        for collection in bpy.data.collections:
            # Get the layer collection
            layer_collection = find_layer_collection(context.view_layer.layer_collection, collection.name)
            if layer_collection:
                collection_states[collection.name] = {
                    'exclude': layer_collection.exclude,
                    'hide_viewport': collection.hide_viewport
                }
        
        # Store original object states
        object_states = {}
        for ob in bpy.data.objects:
            if ob.type == 'MESH':
                object_states[ob.name] = {
                    'hide_viewport': ob.hide_viewport,
                    'hide_select': ob.hide_select
                }
        
        try:
            # Make all collections visible
            for collection in bpy.data.collections:
                layer_collection = find_layer_collection(context.view_layer.layer_collection, collection.name)
                if layer_collection:
                    layer_collection.exclude = False
                collection.hide_viewport = False
            
            # Make all objects visible and selectable
            for ob in bpy.data.objects:
                if ob.type == 'MESH':
                    ob.hide_viewport = False
                    ob.hide_select = False
            
            # Deselect all objects first
            bpy.ops.object.select_all(action='DESELECT')
            
            # Get publishable anastylosis models
            publishable_models = [item for item in scene.em_tools.anastylosis.list if item.is_publishable]
            
            if not publishable_models:
                self.report({'INFO'}, "No publishable anastylosis models found")
                return False
            
            # Get the graph
            graph = None
            if context.scene.em_tools.active_file_index >= 0:
                graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                graph = get_graph(graphml.name)
                
            if not graph:
                self.report({'ERROR'}, "No active graph available")
                return False
            
            # Export each model
            exported_count = 0
            
            for item in publishable_models:
                # Important: Use item.name which refers to the actual 3D object
                obj = bpy.data.objects.get(item.name)
                if not obj:
                    self._saltato(f"anastylosis {item.name}",
                                  "oggetto non in scena")
                    continue
                
                em_log(f"Processing object '{item.name}' linked to SF/VSF '{item.sf_node_name}'", "DEBUG")
                    
                # Select object and make it active
                try:
                    obj.select_set(True)
                    context.view_layer.objects.active = obj
                except Exception as e:
                    em_log(f"Could not select object '{item.name}': {str(e)}", "WARNING")
                    continue
                
                # Save original object transform data
                original_location = obj.location.copy()
                original_rotation = obj.rotation_euler.copy() if obj.rotation_mode == 'XYZ' else obj.rotation_quaternion.copy()
                original_rotation_mode = obj.rotation_mode
                original_scale = obj.scale.copy()
                
                # Create the transform dictionary (like in RMDoc)
                transform = {
                    "position": [f"{original_location.x}", f"{original_location.y}", f"{original_location.z}"],
                    "scale": [f"{original_scale.x}", f"{original_scale.y}", f"{original_scale.z}"]
                }
                
                # Handle rotation based on mode
                if original_rotation_mode == 'XYZ':
                    transform["rotation"] = [f"{original_rotation.x}", f"{original_rotation.y}", f"{original_rotation.z}"]
                else:
                    # Convert quaternion to euler for the node
                    euler = original_rotation.to_euler('XYZ')
                    transform["rotation"] = [f"{euler.x}", f"{euler.y}", f"{euler.z}"]
                
                # Prepare file path
                export_file = os.path.join(export_folder, clean_filename(obj.name))
                
                # Export as GLTF
                try:
                    export_gltf_with_animation_support(
                        filepath=export_file,
                        export_vars=export_vars,
                        scene=scene,
                        use_selection=True
                    )

                    # Create/update nodes and edges in the graph
                    if graph:
                        # Get SF or VSF node if it's linked
                        sf_node = None
                        if item.sf_node_id:
                            sf_node = graph.find_node_by_id(item.sf_node_id)
                        
                        # Create or update RMSF node
                        rmsf_node_id = f"{item.name}_rmsf"
                        rmsf_node = graph.find_node_by_id(rmsf_node_id)
                        
                        if not rmsf_node:
                            # Create RepresentationModelSpecialFindNode
                            from s3dgraphy.nodes.representation_node import RepresentationModelSpecialFindNode
                            rmsf_node = RepresentationModelSpecialFindNode(
                                node_id=rmsf_node_id,
                                name=f"RMSF for {item.name}",
                                type="RM",
                                transform=transform,
                                description=f"Representation model for {item.sf_node_name or 'Special Find'}"
                            )
                            graph.add_node(rmsf_node)
                            em_log(f"Created RMSF node: {rmsf_node_id}", "DEBUG")
                        else:
                            # Update existing node
                            rmsf_node.transform = transform
                            if hasattr(rmsf_node, 'data'):
                                rmsf_node.data["transform"] = transform
                            em_log(f"Updated RMSF node: {rmsf_node_id}", "DEBUG")
                        
                        # Connect SF node to RMSF node if SF node exists
                        if sf_node:
                            edge_id = f"{sf_node.node_id}_has_representation_model_{rmsf_node_id}"
                            if not graph.find_edge_by_id(edge_id):
                                graph.add_edge(
                                    edge_id=edge_id,
                                    edge_source=sf_node.node_id,
                                    edge_target=rmsf_node_id,
                                    edge_type="has_representation_model"
                                )
                                em_log(f"Created edge: {sf_node.node_id} -> {rmsf_node_id}", "DEBUG")
                        
                        # ── NIGHT-RES/R2 · L'RMSF ─────────────────────────
                        #
                        # Come l'RM: master il datablock, distribution il file
                        # esportato, uno a uno.
                        #
                        # NOTA STORICA, e conta: è l'unico dei sei che **già
                        # oggi** crea una risorsa al COLLEGAMENTO e non
                        # all'export (`anastylosis_manager/operators_link.py`).
                        # Quel vantaggio non si perde — il nodo che c'è viene
                        # trovato e aggiornato, non ricreato, perché l'id è
                        # derivato dall'RMSF come prima. Qui si aggiunge quello
                        # che mancava: il master, il digest, il verbale.
                        gltf_path = f"models_sf/{clean_filename(obj.name)}.gltf"
                        self._registra_bake(
                            graph, rmsf_node_id, obj,
                            url=gltf_path,
                            file_esportato=export_file + ".gltf",
                            etichetta=f"GLTF for {item.name}")
                    
                    exported_count += 1
                    em_log(f"Successfully exported anastylosis model: {obj.name}", "DEBUG")
                    
                except self.DIFETTI_DI_PROGRAMMAZIONE:
                    raise          # T4
                except Exception as e:
                    self._fallito(f"anastylosis model {obj.name}", str(e), e)
                    
                # Deselect object
                obj.select_set(False)
            
            # Compress textures if enabled
            if exported_count > 0 and scene.heriverse_enable_compression:
                self.compress_textures_in_folder(export_folder, scene)
                em_log(f"Compressed textures for {exported_count} anastylosis models", "DEBUG")
            
            self.report({'INFO'}, f"Exported {exported_count} anastylosis models")
            return exported_count > 0
            
        finally:
            # Restore original collection states
            for collection_name, state in collection_states.items():
                collection = bpy.data.collections.get(collection_name)
                if collection:
                    layer_collection = find_layer_collection(context.view_layer.layer_collection, collection_name)
                    if layer_collection:
                        layer_collection.exclude = state['exclude']
                    collection.hide_viewport = state['hide_viewport']
            
            # Restore original object states
            for object_name, state in object_states.items():
                obj = bpy.data.objects.get(object_name)
                if obj:
                    obj.hide_viewport = state['hide_viewport']
                    obj.hide_select = state['hide_select']

    def execute(self, context):
        """Main export function"""
        self.instanced_objects = set()
        self.exported_models = {}
        self.stato_collezioni = {}
        self._azzera_esiti()          # T4 · fallito e saltato, contati a parte
        
        scene = context.scene
        export_vars = context.window_manager.export_vars

        # Import utility functions from the main module
        from ...functions import normalize_path, create_directory, check_export_path, check_graph_loaded, show_popup_message
        from ...graph_updaters import update_graph_with_scene_data
        import json
        
        try:
            em_log("\n=== Starting Heriverse Export ===", "INFO")
            
            # Check if at least one graph is loaded
            if not check_graph_loaded(context):
                return {'CANCELLED'}
            
            # Check if export path is valid
            if not check_export_path(context):
                return {'CANCELLED'}
            
            em_log(f"Export path: {scene.heriverse_export_path}", "DEBUG")
                
            # Setup dei percorsi (con normalizzazione)
            output_dir = normalize_path(scene.heriverse_export_path)
            project_name = scene.heriverse_project_name or os.path.splitext(os.path.basename(bpy.data.filepath))[0]
            project_name = f"{project_name}_multigraph"
            project_path = os.path.join(output_dir, project_name)
            
            em_log(f"Project path: {project_path}", "DEBUG")
            em_log(f"Project name: {project_name}", "DEBUG")
            em_log(f"Using GPU instancing: {export_vars.heriverse_use_gpu_instancing}", "DEBUG")
            
            # Crea la directory del progetto
            try:
                os.makedirs(project_path, exist_ok=True)
                em_log("Created project directory", "DEBUG")
            except Exception as e:
                show_popup_message(context, "Directory Error", f"Failed to create project directory: {str(e)}", 'ERROR')
                return {'CANCELLED'}

            # Salva lo stato delle collezioni
            collection_states = {}
            for collection in bpy.data.collections:
                layer_collection = find_layer_collection(context.view_layer.layer_collection, collection.name)
                if layer_collection:
                    collection_states[collection.name] = layer_collection.exclude

            try:
                # Update the graph(s) before exporting
                try:
                    # Always update all publishable graphs with scene data
                    # This ensures that SemanticShape, RM, RMSF nodes are created/updated
                    # before we add LinkNodes during the export process
                    em_log("Updating all publishable graphs with scene data...", "DEBUG")
                    update_graph_with_scene_data(update_all_graphs=True, context=context)

                    # Refine generic_connection edges to semantic types
                    # This transforms placeholder edges into proper semantic edges
                    # (e.g., generic_connection -> has_documentation for US -> DocumentNode)
                    from s3dgraphy import get_graph
                    em_tools = context.scene.em_tools
                    for graphml_item in em_tools.graphml_files:
                        is_publishable = getattr(graphml_item, 'is_publishable', True)
                        if is_publishable:
                            graph = get_graph(graphml_item.name)
                            if graph:
                                refined = graph.refine_generic_connections(verbose=True)
                                if refined > 0:
                                    em_log(f"  Graph '{graphml_item.name}': refined {refined} edges", "DEBUG")
                except Exception as e:
                    em_log(f"Warning: Could not update graph: {e}", "WARNING")
                # STEP 1 Export Cesium tilesets if requested
                tilesets_exported = False
                if export_vars.heriverse_export_rm:
                    em_log("\n--- Starting Tileset Export ---", "INFO")
                    tilesets_path = os.path.join(project_path, "tilesets")
                    os.makedirs(tilesets_path, exist_ok=True)
                    
                    count = self.export_tilesets(context, tilesets_path)
                    tilesets_exported = count > 0
                    if tilesets_exported:
                        em_log(f"Exported {count} tileset files", "DEBUG")
                    else:
                        em_log("No tilesets were exported", "DEBUG")

                # STEP 2: Esporta i proxy se richiesto
                if export_vars.heriverse_export_proxies:
                    em_log("\n--- Starting Proxy Export ---", "INFO")
                    proxy_path = os.path.join(project_path, "proxies")
                    os.makedirs(proxy_path, exist_ok=True)
                    
                    result = self.export_proxies(context, proxy_path)
                    if result:
                        em_log("Proxy export completed successfully", "DEBUG")
                    else:
                        em_log("No proxies were exported", "DEBUG")

                # STEP 3: Esporta i modelli RM se richiesto
                models_exported = False
                models_path = None
                models_docs_path = None
                if export_vars.heriverse_export_rm:
                    em_log("\n--- Starting RM Export ---", "INFO")
                    models_path = os.path.join(project_path, "models")
                    os.makedirs(models_path, exist_ok=True)
                    
                    # Make sure all collections containing RM objects are visible
                    rm_objects = [obj for obj in bpy.data.objects 
                                if hasattr(obj, "EM_ep_belong_ob") and len(obj.EM_ep_belong_ob) > 0]
                    
                    # Get all collections containing RM objects
                    rm_collections = set()
                    for obj in rm_objects:
                        for collection in bpy.data.collections:
                            if obj.name in collection.objects:
                                rm_collections.add(collection.name)
                    
                    # Make them all visible for export
                    for col_name in rm_collections:
                        layer_collection = find_layer_collection(context.view_layer.layer_collection, col_name)
                        if layer_collection:
                            layer_collection.exclude = False
                    
                    result = self.export_rm(context, models_path)
                    models_exported = result
                    if result:
                        em_log("RM export completed successfully", "DEBUG")
                    else:
                        em_log("No RM models were exported", "DEBUG")

                # STEP 3.1: Esporta i modelli RMDoc se richiesto
                if export_vars.heriverse_export_rmdoc:
                    em_log("\n--- Starting RM Export ---", "INFO")
                    models_docs_path = os.path.join(project_path, "models_docs")
                    os.makedirs(models_docs_path, exist_ok=True)

                    # Aggiungi l'export degli oggetti ParaData
                    em_log("\n--- Starting ParaData Objects Export ---", "INFO")
                    paradata_count = self.export_paradata_objects(context, models_docs_path)
                    if paradata_count > 0:
                        em_log(f"Exported {paradata_count} ParaData objects", "DEBUG")
                    else:
                        em_log("No ParaData objects were exported", "DEBUG")

                # STEP 3.2: Export SF models if requested
                sf_models_exported = False
                if export_vars.heriverse_export_rmsf:
                    em_log("\n--- Starting Special Finds Models Export ---", "INFO")
                    sf_models_path = os.path.join(project_path, "models_sf")
                    os.makedirs(sf_models_path, exist_ok=True)
                    
                    sf_models_exported = self.export_rmsf_models(context, sf_models_path)
                    if sf_models_exported:
                        em_log("Special Finds models export completed successfully", "DEBUG")
                    else:
                        em_log("No Special Finds models were exported", "DEBUG")

                # STEP 4: Esporta i file DosCo se richiesto
                if export_vars.heriverse_export_dosco:
                    em_log("\n--- Starting DosCo Export ---", "INFO")
                    active_graph_id = None
                    if not (len(context.scene.em_tools.graphml_files) > 1) and context.scene.em_tools.active_file_index >= 0:
                        active_file = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                        active_graph_id = active_file.name

                    dosco_path = os.path.join(project_path, "dosco")
                    result = self.export_dosco(context, active_graph_id, dosco_path)
                    if result:
                        em_log("DosCo export completed successfully", "DEBUG")
                    else:
                        em_log("DosCo export failed or was skipped", "ERROR")
                
                # STEP 5: Export panorama if requested
                if scene.heriverse_export_panorama:
                    em_log("\n--- Exporting Panorama ---", "INFO")
                    result = self.export_panorama(context, project_path)
                    if result:
                        em_log("Panorama export completed successfully", "DEBUG")
                    else:
                        em_log("Panorama export failed or was skipped", "ERROR")

                # STEP 5b: Export per-epoch panoramas (always runs — copies epoch HDR files)
                epoch_pano_map = self.export_epoch_panoramas(context, project_path)
                if epoch_pano_map:
                    em_log(f"Exported {len(epoch_pano_map)} per-epoch panorama(s)", "DEBUG")

                # STEP 6: Compress all textures at once if texture compression is enabled and RM models were exported
                if scene.heriverse_enable_compression and models_exported and models_path:
                    em_log("\n--- Starting Texture Compression ---", "INFO")
                    self.compress_textures_in_folder(models_path, scene)

                # STEP 7: Export JSON
                if export_vars.heriverse_overwrite_json:
                    # NOTE: Do NOT call update_graph_with_scene_data() again here!
                    # It was already called at the beginning and would erase LinkNodes created during export

                    # Esporta il JSON direttamente usando il nuovo JSONExporter
                    json_path = os.path.join(project_path, "project.json")
                    em_log(f"Exporting JSON to: {json_path}", "DEBUG")
                    
                    # Verifica che esista almeno un grafo valido
                    if not check_graph_loaded(context):
                        show_popup_message(context, "Export Error", "No valid graph found. Please load a GraphML file first.")
                        return {'CANCELLED'}
                    
                    # Usa l'operatore JSON con i parametri corretti
                    result = bpy.ops.export.heriversejson(
                        filepath=json_path,
                        use_file_dialog=False
                    )
                    
                    if result == {'FINISHED'}:
                        em_log("JSON export completed successfully", "DEBUG")

                        # Post-process JSON: instancing + per-epoch lighting
                        needs_rewrite = False

                        with open(json_path, 'r') as f:
                            json_data = json.load(f)

                        if hasattr(self, 'instanced_objects') and len(self.instanced_objects) > 0:
                            json_data = self.update_json_for_instancing(json_data)
                            em_log(f"Updated JSON with instancing information for {len(self.instanced_objects)} objects", "DEBUG")
                            needs_rewrite = True

                        # Inject per-epoch panorama/lighting data
                        json_data = self.update_json_with_epoch_lighting(
                            json_data, context, epoch_pano_map)
                        needs_rewrite = True

                        if needs_rewrite:
                            with open(json_path, 'w') as f:
                                json.dump(json_data, f, indent=4)

                    else:
                        self.report({'ERROR'}, "JSON export failed")
                        return {'CANCELLED'}

            finally:
                # Ripristina lo stato delle collezioni
                for collection_name, was_excluded in collection_states.items():
                    layer_collection = find_layer_collection(context.view_layer.layer_collection, collection_name)
                    if layer_collection:
                        layer_collection.exclude = was_excluded


            # STEP 8: Crea ZIP se richiesto
            if export_vars.heriverse_create_zip:
                em_log("\n--- Creating ZIP Archive ---", "INFO")
                zip_path = self.create_project_zip(project_path)
                em_log(f"ZIP archive created at: {zip_path}", "DEBUG")
                
                # Verifica che lo ZIP sia stato creato correttamente prima di cancellare
                if os.path.exists(zip_path) and os.path.getsize(zip_path) > 0:
                    try:
                        import shutil
                        shutil.rmtree(project_path)
                        em_log(f"Original folder deleted: {project_path}", "DEBUG")
                        self.report({'INFO'}, f"Export completed. ZIP created and original folder cleaned up.")
                    except Exception as e:
                        em_log(f"Warning: Could not delete original folder: {e}", "WARNING")
                        self.report({'WARNING'}, f"ZIP created but could not delete original folder: {str(e)}")
                else:
                    em_log("Warning: ZIP file not created properly, keeping original folder", "WARNING")
                    self.report({'WARNING'}, "ZIP creation failed, original folder preserved")


            # T4 · «completato» non vuol dire «tutto riuscito». Un export che
            # dice solo «completed» dopo tre fallimenti è come i warning che
            # non distinguevano fallito da saltato: vero e inutile.
            self._resoconto_esiti()
            print("\n=== Export Completed ===")
            self.report({'INFO'}, f"Export completed to {project_path}")
            
            return {'FINISHED'}

        except self.DIFETTI_DI_PROGRAMMAZIONE:
            # T4 · un difetto del CODICE non diventa un messaggio: emerge
            # intero, con il suo traceback, fino a chi sta guardando. È
            # esattamente ciò che non è successo al `NameError` di
            # `export_tilesets`, rimasto un warning fra i warning per un
            # intero commit range.
            em_log("\n!!! Export Failed — DIFETTO DI PROGRAMMAZIONE !!!", "ERROR")
            import traceback
            em_log(traceback.format_exc(), "ERROR")
            raise
        except Exception as e:
            em_log(f"\n!!! Export Failed !!!", "ERROR")
            em_log(f"Error: {str(e)}", "ERROR")
            import traceback
            em_log(traceback.format_exc(), "ERROR")
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            return {'CANCELLED'}




classes = (
    EXPORT_OT_heriverse,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
