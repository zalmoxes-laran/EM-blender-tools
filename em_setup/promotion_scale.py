"""La scala di promozione dell'EM Data Tree: i quattro conteggi e le parole.

EM16-UX (B1) l'ha introdotta come una riga sola; EM16-UX2 (C2) l'ha rifatta a
**riquadro di celle**, in **inglese**, e spostata **sotto il Path** — subito
sopra `Graph info`, di cui è il parente visivo.

    ┌───────────┬───────────┬───────────┬───────────┐
    │ Scene     │ RMs       │ Groups    │ Docs      │
    │  🔲 223   │  🔲 12    │  🔲 3     │  📄 19    │
    └───────────┴───────────┴───────────┴───────────┘

## PERCHÉ LE CELLE E NON UNA RIGA

A video la riga si troncava alle due estremità — `203 in sce… → 0 modelli → 3
gruppi → 19 docum…` — cioè proprio i due numeri che più contano. Ogni cella su
**due righe** (etichetta piccola sopra, icona e numero sotto) è la forma che non
si tronca: il numero è l'elemento grande e l'etichetta non gli contende la
larghezza. È anche il linguaggio visivo di casa: il vecchio blocco statistiche
di questo pannello (`US/USV 103 · Epochs 3 · Properties 44 · Documents 19`) era
fatto così e funzionava.

## LA FRECCIA NON C'È, E CI SONO VOLUTE TRE MISURE PER CONCLUDERLO

Tre tecniche, tutte guardate a video in un Blender vero, nessuna dedotta.

1. **Prefisso dell'etichetta, parole lunghe** (`→ Documents`): l'etichetta si
   abbreviava — `→ Docu…`.
2. **Prefisso dell'etichetta, parole corte** (`→ RMs`, `→ Groups`, `→ Docs`):
   `→ RMs` e `→ Docs` ci stanno, **`→ Groups` no** — a video `→ Grou…`. Il
   glifo `→` più lo spazio costano quanto due caratteri, e con la freccia il
   budget di una cella a larghezza normale (280 unità di interfaccia) è di
   cinque lettere.
3. **Freccia nella riga del numero**, prima dell'icona: sembrava la via
   d'uscita, perché il numero è corto. A video **è sparito il numero**: le
   celle 2-4 mostravano `→` e l'icona, e lo `0` era tagliato. Peggio del
   difetto di partenza, perché il numero è la cosa che il pannello esiste per
   dire.

Conclusione misurata: a quattro colonne su questa larghezza la cella non
porta insieme una freccia e il suo contenuto. Quindi la freccia non c'è, e
l'imbuto lo dicono **l'ordine** delle celle (che si legge da sinistra a
destra comunque) e i **tooltip**, che dicono per ognuna da dove viene il
numero. `FRECCIA` resta definita perché la usa `testo()`, che è una riga sola
e ha lo spazio.

## L'INGLESE

L'interfaccia di questo add-on è in inglese, tooltip compresi. La prima
versione era in italiano perché l'esempio del prompt lo era. Questa docstring
resta in italiano di proposito: è per chi sviluppa, non per chi usa.

## IL QUARTO GRADINO SONO I DOCUMENTI CON UN 3D, E PRIMA ERA UN DOPPIONE

Ha cambiato insieme due volte, e la seconda perché la prima era sbagliata.

Era `scene.doc_list` intero. Misurato: `doc_list` si popola dai nodi `document`
del grafo (`document_manager/data.py`) ed è **lo stesso insieme** che
`Graph info` conta come `document_count` (`populate_lists.py:387`). Lo stesso
numero due volte nello stesso pannello, sotto la stessa parola.

Poi è stato `scene.rmdoc_list`, e **non era quello che serviva**: `rmdoc_list`
è *object-centric* — un elemento per quad in scena — e gli RMDoc sono una cosa
loro, come gli RMSF. Il gradino invece conta DOCUMENTI.

Adesso è il criterio che il Document Manager ha già: gli elementi di
`doc_list` con `has_quad` vero, cioè i documenti per cui esiste in scena
l'oggetto quad (`em_doc_node_id`). È esattamente il filtro «With 3D Only»
(`filter_with_3d`, la cui descrizione dice «documents that have a 3D
representation»), quindi il numero del pannello e quel filtro dicono la stessa
cosa — e se un giorno cambia il criterio, cambia in un posto.

## E IL CONTEGGIO STA QUI, SENZA `bpy`

Come `rm_manager/epoch_edges.py` e `rm_manager/group_nodes.py`: così si misura
fuori da Blender. Il disegno sta nel pannello, dove serve il layout; i numeri e
le parole stanno qui, dove si possono provare.
"""

from __future__ import annotations

#: La freccia dell'imbuto, usata come PREFISSO dell'etichetta.
FRECCIA = "→"          # →

#: I quattro gradini: chiave, etichetta, icona NOSTRA, icona di Blender di
#: ripiego, tooltip.
#:
#: Due icone e non una perché le nostre stanno in una `bpy.utils.previews` che
#: può non essere caricata (`get_icon_value` torna 0) e un `icon_value=0`
#: disegna il vuoto: il ripiego di Blender è ciò che si vede in quel caso.
#: `None` come prima icona vuol dire «qui l'icona di Blender è quella giusta» —
#: `In scene` conta oggetti di Blender, non nodi del grafo.
#:
#: Il tooltip su *3D docs* dice le due cose che il numero da solo nasconde:
#: che NON è il conteggio dei documenti del grafo (quello è il «Documents» di
#: `Graph info`) e che non sono nemmeno gli RMDoc o gli RMSF, che sono liste
#: di oggetti in scena — qui si contano documenti.
GRADINI = (
    ("in_scene", "Scene", None, "OUTLINER_OB_MESH",
     "Objects in this .blend that could become a representation model "
     "(MESH, CURVE, or an EMPTY that is not a collection instance) — the "
     "same test rm_manager.containers.is_rm_candidate applies. This is a "
     "SCENE number: it does not depend on which graph is active."),
    ("rms", "RMs", "show_all_RMs", "MESH_DATA",
     "RepresentationModel nodes, summed over ALL loaded graphs — not just "
     "the active one. The objects already promoted to a model, so they "
     "exist in a graph and not only in the scene."),
    ("groups", "Groups", "container_on", "OUTLINER_COLLECTION",
     "RM containers (scene.rm_containers): the named sets — «Survey "
     "2015», «Reconstruction» — that group several models under one "
     "document. This is a SCENE number."),
    ("docs", "Docs", "document", "FILE_TEXT",
     "Document nodes, summed over ALL loaded graphs — not just the active "
     "one. These are the sources you have CHOSEN to cite, so the number is "
     "a decision and not an inventory, and being lower than the others is "
     "not a gap."),
)


def conta(*, oggetti_scena=(), is_candidato=None,
          rms=0, rm_containers=0, docs=0) -> dict:
    """I quattro numeri della scala, nella forma che il pannello disegna.

    `in_scene` è l'unico che questa funzione CALCOLA, ed è l'unico che si
    possa calcolare senza `bpy`: `is_candidato` è il predicato vero
    (`rm_manager.containers.is_rm_candidate`) iniettato da chi chiama, così il
    criterio NON viene riscritto qui.

    Gli altri tre arrivano già sommati. È un cambio rispetto a UX2, dove
    questa funzione riceveva i nodi del grafo ATTIVO e li contava: da UX3 i
    modelli e i documenti sono la somma su TUTTI i grafi caricati, e la somma
    la fa chi ha `bpy` in mano usando `Graph.get_nodes_by_type()`, che è
    O(1) sull'indice di s3Dgraphy. Passare qui la concatenazione dei nodi di
    tutti i grafi avrebbe voluto dire scorrerli tutti a ogni ridisegno, cioè
    buttare via proprio quell'indice.
    """
    if is_candidato is None:
        def is_candidato(_o):                         # pragma: no cover
            return False
    in_scene = sum(1 for o in oggetti_scena if is_candidato(o))
    return {"in_scene": in_scene, "rms": int(rms),
            "groups": int(rm_containers), "docs": int(docs)}


def ripartizione(coppie) -> str:
    """«GT16: 12 · Shelf: 7» da [(nome, numero), …].

    Serve ai tooltip: la cella mostra la SOMMA, e il dettaglio per grafo non
    si perde — finisce nella spiegazione. Senza `bpy`, quindi si prova.

    Le coppie a zero restano: «Shelf: 0» dice che quel grafo è caricato e non
    ha nulla di quel tipo, che è un'informazione diversa dal non comparire.
    """
    return " · ".join(f"{nome}: {numero}" for nome, numero in coppie)


def testo(numeri: dict) -> str:
    """La scala come una riga sola — usata dalle prove e dai log.

    Il pannello NON usa questa: disegna le celle. Resta perché è il modo più
    compatto di far dire a una prova «la scala legge questo».
    """
    pezzi = [f"{numeri.get(k, 0)} {etichetta}"
             for k, etichetta, _c, _i, _t in GRADINI]
    #: qui la freccia SEPARA i gradini: in una riga sola lo spazio c'è, ed è
    #: l'unico posto dove l'imbuto si può scrivere senza mangiare nulla.
    return f"  {FRECCIA}  ".join(pezzi)


def tooltip_di(chiave: str) -> str:
    """Il tooltip di un gradino, per chiave. "" se la chiave non è una."""
    for k, _etichetta, _custom, _icona, tip in GRADINI:
        if k == chiave:
            return tip
    return ""


def modelli_a_zero_sospetto(numeri: dict) -> bool:
    """True quando `rms` è a zero E ci sono candidati in scena.

    È il caso misurato sul file di lavoro di E.D.: 203 candidati in scena e 0
    nodi RM, perché quel grafo viene da import GraphML — che per disegno non
    trasporta i representation model. NON è un guasto, quindi la cella prende
    un'icona di INFORMAZIONE e non un allarme, e il suo tooltip lo spiega.

    Zero candidati e zero modelli non è sospetto: è una scena vuota.
    """
    return bool(numeri.get("in_scene")) and not numeri.get("rms")
