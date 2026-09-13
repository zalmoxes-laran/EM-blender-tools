"""D2 · La casa dell'intenzione di pubblicare, lato scena.

Tre righe di traduzione fra `publication_flags` (puro, provabile) e una
`CollectionProperty` sulla scena. La regola sta di là; qui c'è solo dove i
byte di quella regola si posano, e il fatto che si posino nel **.blend** —
perché «voglio pubblicare questo» è una decisione di chi lavora e non deve
evaporare alla chiusura del file.

**È PROVVISORIO E LO DICE.** Il posto giusto sarebbe un campo dichiarato sul
nodo del grafo, così l'intenzione viaggia con l'em.json invece di restare in
un .blend che solo Blender apre. Quello è un cambiamento del contratto, cioè
s3Dgraphy, e non si fa stanotte.
"""

from __future__ import annotations

import bpy  # type: ignore
from bpy.props import CollectionProperty, StringProperty
from bpy.types import PropertyGroup

from .. import publication_flags


class EM_PublicationFlag(PropertyGroup):
    """Un asset che qualcuno ha deciso di pubblicare. `name` è il suo id.

    Una collezione di id e non un booleano per riga: le righe del deck sono una
    **cache** che si svuota a ogni Refresh, e un'intenzione che vive in una
    cache è un'intenzione che si perde. Gli id invece sono stabili — l'id del
    container, del nodo RM, o della risorsa — e restano veri anche mentre il
    deck non è mai stato calcolato.
    """

    name: StringProperty(default="")  # type: ignore


def spuntati(scene) -> set:
    """Gli id spuntati in questa scena."""
    return publication_flags.insieme(getattr(scene, "em_publication_flags", ()))


def _riscrivi(scene, nuovi: set) -> None:
    elenco = scene.em_publication_flags
    elenco.clear()
    for chiave in sorted(nuovi):
        elenco.add().name = chiave


def imposta(scene, asset_id, acceso: bool) -> None:
    """Accende o spegne **un** flag."""
    _riscrivi(scene, publication_flags.scegli(spuntati(scene), asset_id, acceso))


def aggiungi(scene, ids) -> int:
    """Additivo: unisce. → quanti ne ha aggiunti davvero."""
    prima = spuntati(scene)
    dopo = publication_flags.aggiungi(prima, ids)
    _riscrivi(scene, dopo)
    return len(dopo) - len(prima)


def togli(scene, ids) -> int:
    """Il verbo opposto, nominato. → quanti ne ha tolti davvero."""
    prima = spuntati(scene)
    dopo = publication_flags.togli(prima, ids)
    _riscrivi(scene, dopo)
    return len(prima) - len(dopo)


def _leggi(self) -> bool:
    """Il getter della spunta di riga: guarda la scena, non la cache.

    `self.id_data` è la scena che possiede questo gruppo di proprietà, e usarla
    invece di `bpy.context.scene` è quello che fa funzionare la spunta anche
    quando il pannello si disegna per una scena che non è quella attiva.
    """
    return publication_flags.normalizza(self.asset_id) in spuntati(self.id_data)


def _scrivi(self, valore) -> None:
    imposta(self.id_data, self.asset_id, bool(valore))


def register():
    bpy.utils.register_class(EM_PublicationFlag)
    if not hasattr(bpy.types.Scene, "em_publication_flags"):
        bpy.types.Scene.em_publication_flags = CollectionProperty(
            type=EM_PublicationFlag)


def unregister():
    if hasattr(bpy.types.Scene, "em_publication_flags"):
        del bpy.types.Scene.em_publication_flags
    try:
        bpy.utils.unregister_class(EM_PublicationFlag)
    except Exception:  # noqa: BLE001 — unregistering must not fail
        pass
