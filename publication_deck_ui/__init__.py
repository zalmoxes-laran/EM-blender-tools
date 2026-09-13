"""publication_deck_ui — il Publication Deck (EM Bridge).

Il posto che risponde a **una domanda sola**: *cosa manca perché questo em.json
sia consumabile fuori da Blender?* Guarda la soglia fra il dentro e il fuori e
permette di attraversarla in un gesto.

**Cosa NON è**, e va tenuto fermo perché è il modo in cui questo pannello
potrebbe marcire: non è un gestore di file; non è un secondo posto dove si
importano asset (c'è lo Shelf); non è un posto dove si modifica la geometria;
non pubblica da solo; e non è un secondo baker — se qui dentro ricomparisse la
logica dell'export, vorrebbe dire che qualcuno si è perso.

Il calcolo sta fuori, senza `bpy`: `publication_deck.py` (le righe),
`publication_targets.py` (le destinazioni e le loro capacità),
`publication_flags.py` (l'intenzione di pubblicare) e `publication_room.py`
(lo stato del grafo rispetto alla stanza). Qui c'è la cache, il disegno e i
verbi — e i verbi **mettono in fila** roba che esiste già (l'export,
`promote_resource`, `em.publish_distribution`), non la riscrivono.

**IL DECK PUBBLICA BYTE** (decisione 34): il verbo è *mettere fuori questi byte
con un indirizzo e un'impronta*, che è un fatto sull'asset, identico per un pdf
e per un glb. «Heriverse sa caricarlo?» è un fatto su una coppia
asset-consumatore, e sta in una **annotazione di riga** — non governa più
niente. Ciò che un lettore non sa aprire resta pubblicabile.
"""

from __future__ import annotations

from . import flags, properties, operators, ui


def register():
    #: i flag PRIMA delle property: `EM_PublicationRow.pubblica` è una finestra
    #: su `scene.em_publication_flags`, e una finestra su una stanza che non
    #: c'è ancora si apre sul vuoto
    flags.register()
    properties.register()
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    properties.unregister()
    flags.unregister()
