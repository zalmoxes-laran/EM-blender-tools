"""La CACHE del deck — e perché esiste.

`resource_audit.stato_risorse` costa un `os.stat` per derivata (misurato in
NIGHT-RIM3), e un pannello Blender si ridisegna a ogni movimento del mouse:
chiamarla nel `draw` vorrebbe dire battere il filesystem centinaia di volte al
secondo per mostrare un numero che cambia una volta all'ora.

Quindi il conto si fa **su richiesta** e finisce qui. E siccome un numero in
cache è un numero vecchio, la cache porta **l'ora in cui è stata presa** e il
pannello la mostra: «as of 14:32». Un numero vecchio che dice di essere vecchio
è informazione; un numero vecchio che si spaccia per fresco è il difetto che
questa settimana è passata a togliere.

**D1 · LA CACHE HA DUE LIVELLI, come il deck.** Una riga è un **asset** — la
cosa di cui si decide — e dentro porta le sue **distribuzioni**, che sono i
file. Erano una riga per distribuzione, e su un progetto vero facevano
diciannove box da quindici righe l'uno: quasi trecento righe di pannello per
dire quattro cose, e la sola lista dei nomi non si vedeva mai tutta.

Le righe stanno in un `CollectionProperty` perché è la forma che una `UIList`
sa disegnare, e la UIList è la forma che Blender usa per gli elenchi lunghi.
"""

from __future__ import annotations

import bpy  # type: ignore
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       IntProperty, StringProperty)
from bpy.types import PropertyGroup

from . import flags


class EM_PublicationDistribution(PropertyGroup):
    """Un file di un asset: **solo testo già calcolato**, come la riga.

    Sta nella scheda e non nella lista, perché un tileset con il suo zip e il
    suo albero servito è **una** decisione: come due righe avrebbe due spunte
    che si accendono insieme, e nessuno saprebbe cosa vuol dire spuntarne una.
    """

    name: StringProperty(default="")  # type: ignore
    node_id: StringProperty(default="")  # type: ignore
    stato: StringProperty(default="")  # type: ignore
    dove: StringProperty(default="")  # type: ignore
    tier: StringProperty(default="")  # type: ignore
    residency: StringProperty(default="")  # type: ignore
    scope: StringProperty(default="")  # type: ignore
    formato: StringProperty(default="")  # type: ignore
    packaging: StringProperty(default="")  # type: ignore
    peso: StringProperty(default="")  # type: ignore
    url: StringProperty(default="")  # type: ignore
    #: il locator RISOLTO contro le basi note (D5). Vuoto = non risolto, che
    #: non è la stessa cosa di «non c'è»: la frase la porta `perche_no`.
    percorso: StringProperty(default="")  # type: ignore
    pubblicata_il: StringProperty(default="")  # type: ignore
    cosa_e_cambiato: StringProperty(default="")  # type: ignore
    pubblicabile: BoolProperty(default=False)  # type: ignore
    perche_no: StringProperty(default="")  # type: ignore
    pronto: StringProperty(default="")  # type: ignore
    pronto_perche: StringProperty(default="")  # type: ignore


class EM_PublicationRow(PropertyGroup):
    """Un ASSET del deck: **solo testo già calcolato**.

    Nessun campo qui viene derivato mentre si disegna. È la regola che rende
    il `draw` gratuito, ed è anche il motivo per cui i campi sono stringhe già
    formattate invece dei numeri da cui vengono: formattare è lavoro, e il
    lavoro si fa una volta sola, quando si riempie la cache.
    """

    name: StringProperty(default="")  # type: ignore
    asset_id: StringProperty(default="")  # type: ignore

    #: il primo colpo d'occhio della riga: mesh, tileset, nuvola, immagine,
    #: documento. Prima ancora dello stato, perché «di che cosa parliamo»
    #: viene prima di «a che punto è».
    media: StringProperty(default="other")  # type: ignore
    stato: StringProperty(default="")  # type: ignore

    proprietario: StringProperty(default="")  # type: ignore
    granularita: StringProperty(default="rm")  # type: ignore
    membri: IntProperty(default=0)  # type: ignore
    tier: StringProperty(default="")  # type: ignore

    #: **D2 · LA SPUNTA, e stavolta su un fatto suo.** DECK2 la aveva legata a
    #: `RMItem.is_publishable`, che l'exporter legge come «questo RM entra nel
    #: bundle»: giusto nello spirito (non inventare uno stato di UI parallelo)
    #: e sbagliato nel bersaglio, perché un documento non è un RM e quindi non
    #: poteva portarla. Adesso l'intenzione di pubblicare è un fatto
    #: dell'ASSET, tenuto in `scene.em_publication_flags` e chiavato per id —
    #: e questo booleano è una **finestra** su quello, non una copia:
    #: `get`/`set` leggono e scrivono la scena, quindi non esiste un momento in
    #: cui i due possano dire cose diverse.
    pubblica: BoolProperty(
        name="Publish",
        description=("Put these bytes outside, with an address and a "
                     "checksum. This is about the asset, not about any one "
                     "reader: what a viewer cannot open stays publishable"),
        get=flags._leggi, set=flags._scrivi)  # type: ignore

    #: l'indice del container, quando l'asset è un container: la sua
    #: `publication_strategy` è l'altra impostazione che governa davvero cosa
    #: l'export farà, e la scheda la mostra così com'è.
    container_indice: IntProperty(default=-1)  # type: ignore
    #: e l'indice della voce di `scene.rm_list`, quando ce n'è una: serve alla
    #: scheda per mostrare `is_publishable` — che resta dell'exporter e non è
    #: più la spunta del deck
    flag_indice: IntProperty(default=-1)  # type: ignore

    pubblicata_il: StringProperty(default="")  # type: ignore
    cosa_e_cambiato: StringProperty(default="")  # type: ignore
    perche_no: StringProperty(default="")  # type: ignore
    n_pubblicabili: IntProperty(default=0)  # type: ignore

    pronto: StringProperty(default="")  # type: ignore
    pronto_perche: StringProperty(default="")  # type: ignore

    distribuzioni: CollectionProperty(type=EM_PublicationDistribution)  # type: ignore


class EM_PublicationBlocco(PropertyGroup):
    """Una ragione che ferma più asset, con quanti ne ferma.

    D5 · Quando tutti gli asset di un progetto riportano la stessa frase,
    quella frase non è un fatto sull'asset: è un fatto sul **progetto**, e va
    detta una volta in testa. Diciannove copie non la rendono più vera.
    """

    name: StringProperty(default="")  # type: ignore
    quanti: IntProperty(default=0)  # type: ignore


class EM_PublicationDeck(PropertyGroup):
    """Lo stato del deck per questa scena."""

    righe: CollectionProperty(type=EM_PublicationRow)  # type: ignore
    #: quale riga sto GUARDANDO. Effimera, e serve solo alla scheda: le UIList
    #: di Blender non hanno multi-selezione, quindi scegliere su cosa agire è
    #: mestiere della spunta, non di questa.
    riga_attiva: IntProperty(default=0)  # type: ignore

    blocchi: CollectionProperty(type=EM_PublicationBlocco)  # type: ignore

    #: L'ORA DEL CONTO. Vuota = mai calcolato, ed è uno stato diverso da «zero
    #: risorse»: il pannello li dice in due modi diversi perché sono due
    #: situazioni diverse.
    calcolato_alle: StringProperty(default="")  # type: ignore
    sintesi: StringProperty(default="")  # type: ignore
    stale: IntProperty(default=0)  # type: ignore
    pubblicabili: IntProperty(default=0)  # type: ignore
    distribuzioni: IntProperty(default=0)  # type: ignore
    #: quanti asset sono spuntati: il numero che sta NEL bottone, così non si
    #: pubblica mai una selezione invisibile perché si è scrollato
    spuntati: IntProperty(default=0)  # type: ignore
    nota: StringProperty(default="")  # type: ignore

    #: **D5 · il glifo dello stato si mostra solo quando DISTINGUE.** Su un
    #: progetto di soli documenti è identico su tutte e diciannove le righe:
    #: una colonna il cui valore non varia mai costa larghezza e non dice
    #: niente, e quella cosa la dice meglio — e una volta sola — la sintesi.
    stati_differiscono: BoolProperty(default=True)  # type: ignore

    #: **D3 · il filtro, in UN posto solo.** Lo legge la lista che disegna e lo
    #: legge l'operatore che scrive in blocco: due copie della stessa
    #: intenzione divergono al primo cambiamento.
    filtro: StringProperty(
        name="Filter",
        description="Show only assets whose name contains this",
        default="", options={'TEXTEDIT_UPDATE'})  # type: ignore

    #: **D6 · lo stato del GRAFO**, in sola lettura. Il grafo è ciò che dice
    #: cosa un glb rappresenta: senza di lui una derivata pubblicata è un file
    #: orfano. Il deck lo MOSTRA e non lo pubblica — quel gesto è il push nella
    #: stanza, e vive altrove.
    grafo_stato: StringProperty(default="")  # type: ignore
    grafo_frase: StringProperty(default="")  # type: ignore

    #: **D1 · quale LETTORE annota le righe** — e non più chi governa il
    #: pannello. Il verbo del deck è mettere i byte nello store con un
    #: indirizzo e un'impronta; che poi un certo visore sappia aprirli è un
    #: fatto sulla coppia asset-lettore, utile da vedere e mai un cancello.
    #: Resta un enum e non un booleano `heriverse`: i lettori sono N
    #: dall'inizio.
    destinazione: EnumProperty(
        name="Readable by",
        description=("Which reader the annotation on each row is about. It "
                     "never blocks publishing: what a reader cannot open "
                     "still goes to the store, with its address and its "
                     "checksum"),
        items=[("heriverse", "Heriverse", "The Heriverse web viewer"),
               ("room", "StratiGraph room", "A room on an StratiGraph Server")],
        default="heriverse")  # type: ignore
    destinazione_nota: StringProperty(default="")  # type: ignore


_CLASSI = (EM_PublicationDistribution, EM_PublicationRow,
           EM_PublicationBlocco, EM_PublicationDeck)


def register():
    for cls in _CLASSI:
        bpy.utils.register_class(cls)
    if not hasattr(bpy.types.Scene, "em_publication_deck"):
        bpy.types.Scene.em_publication_deck = bpy.props.PointerProperty(
            type=EM_PublicationDeck)


def unregister():
    if hasattr(bpy.types.Scene, "em_publication_deck"):
        del bpy.types.Scene.em_publication_deck
    for cls in reversed(_CLASSI):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001 — unregistering must not fail
            pass
