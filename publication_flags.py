"""D2 · L'intenzione di pubblicare, e perché non poteva stare dove stava.

DECK2 aveva legato la spunta del deck a `RMItem.is_publishable`, con
l'argomento giusto — **non inventare uno stato di UI parallelo a uno che
esiste** — e il bersaglio sbagliato. `is_publishable` vive su `RMItem`
(`rm_manager/data.py`) e chi lo legge è l'**exporter Heriverse**
(`export_operators/heriverse/operator.py`, `json_export.py`): il suo
significato reale è *«questo RM entra nel bundle dell'export»*, cioè
un'**inclusione per un consumatore**.

Sono due fatti diversi (decisione 35):

* *questo RM entra nel bundle di Heriverse* — una proprietà della coppia
  modello-consumatore, che l'exporter legge e che resta **intatta**;
* *voglio che questi byte stiano fuori, con un indirizzo e un'impronta* — una
  proprietà dell'**asset**, identica per un pdf e per un glb.

La prova che erano due: su un progetto di diciannove documenti, nessun
documento poteva portare il primo — `is_publishable` sta su `RMItem` e un
documento DosCo non è un RM — quindi diciannove righe non avevano casella e il
deck era «corretto e inutile».

## DOVE STA, E PERCHÉ QUI

Serve un posto che **ogni** asset possa raggiungere: un RM, un container, un
documento, una derivata orfana. Gli RM hanno `scene.rm_list`, i container
`scene.rm_containers`, i documenti **niente** lato scena — esistono solo come
nodi del grafo. Quindi non c'è nessuna collezione di scena esistente che li
copra tutti, e l'unica proprietà comune è l'**identificatore dell'asset**, che
il deck già calcola.

Quindi: un insieme di id sulla **scena**, chiavato per asset. Sopravvive a
salva-e-riapri perché le property di scena stanno nel .blend, copre ogni tipo
di asset perché è chiavata sull'id e non sul tipo, e non tocca né
`is_publishable` né il documento.

**IL POSTO GIUSTO SAREBBE IL GRAFO** — un campo dichiarato sul nodo, così
l'intenzione viaggia con l'em.json e gli altri strumenti la vedono invece di
doverla indovinare. Quello è un cambiamento del contratto, cioè s3Dgraphy, e
stanotte s3Dgraphy non si tocca: questo modulo è **provvisorio** e lo dichiara.
Il giorno che il campo esiste, `flag_di` e `imposta` cambiano di dentro e
nessun chiamante se ne accorge — è per questo che sono due funzioni e non due
righe sparse.

Nessun `bpy` qui: la regola si prova fuori da Blender, e la parte che tocca la
scena sta in `publication_deck_ui/flags.py`.
"""

from __future__ import annotations


def normalizza(asset_id) -> str:
    """L'id come chiave. Vuoto = nessun asset, e non si scrive."""
    return str(asset_id or "").strip()


def insieme(ids) -> set:
    """L'insieme degli id spuntati, da una collezione di voci con `.name`."""
    return {normalizza(getattr(v, "name", v)) for v in (ids or ())
            if normalizza(getattr(v, "name", v))}


def scegli(spuntati, asset_id, acceso: bool) -> set:
    """L'insieme dopo aver acceso o spento **un** flag. Funzione pura.

    Torna un insieme nuovo invece di mutare: così la regola si prova senza una
    scena, e il chiamante che tocca Blender resta un traduttore di tre righe.
    """
    chiave = normalizza(asset_id)
    fuori = set(spuntati or ())
    if not chiave:
        return fuori
    if acceso:
        fuori.add(chiave)
    else:
        fuori.discard(chiave)
    return fuori


def aggiungi(spuntati, candidati) -> set:
    """**Additivo, e solo additivo** (D3): aggiunge flag, non ne toglie mai.

    DECK2 aveva tolto i verbi collettivi perché un «seleziona tutto» che scrive
    una property di progetto cancella in un colpo le esclusioni messe a mano
    (decisione 31). Il ragionamento era giusto e la cura sbagliata: il rimedio
    a una scrittura massiva è **l'annullamento**, non l'amputazione — e
    diciannove documenti da spuntare a mano sono diciannove click.

    Quindi il verbo collettivo **unisce**, e chi vuole togliere lo chiede con
    un gesto che si chiama come quello che fa.
    """
    return set(spuntati or ()) | {normalizza(c) for c in (candidati or ())
                                  if normalizza(c)}


def togli(spuntati, candidati) -> set:
    """Il gesto opposto, **nominato per quello che fa**: toglie i flag di ciò
    che gli si passa. Non è il rovescio silenzioso di `aggiungi`: è un verbo
    suo, che in interfaccia si chiama «Clear flags in view» e non «none»."""
    return set(spuntati or ()) - {normalizza(c) for c in (candidati or ())
                                  if normalizza(c)}


def in_vista(righe, filtro) -> list:
    """Gli asset che il filtro corrente lascia vedere. → lista di id.

    **I verbi collettivi agiscono su ciò che è in vista, non sull'intero
    progetto**: chi ha filtrato per «US_0» sta guardando quelli, e un verbo che
    tocca anche il resto agisce su cose che in quel momento non sono sullo
    schermo. Il confronto è sul nome, senza maiuscole, come ogni ricerca.

    Il filtro sta in **un posto solo** — la property del deck — e lo leggono sia
    la lista che disegna sia l'operatore che scrive. Due letture della stessa
    intenzione, da due copie, divergono al primo cambiamento.
    """
    testo = str(filtro or "").strip().lower()
    fuori = []
    for r in righe or ():
        nome = str(getattr(r, "name", "") or "")
        if testo and testo not in nome.lower():
            continue
        fuori.append(normalizza(getattr(r, "asset_id", "") or nome))
    return [x for x in fuori if x]
