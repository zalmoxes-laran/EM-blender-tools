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

Le righe stanno in un `CollectionProperty` e non in un dizionario di modulo
perché il pannello deve poterle SELEZIONARE, e una selezione è stato che
Blender sa già disegnare (UIList, `prop` sul booleano). Lo stato di sessione
che non si seleziona — l'ora, il sommario — sta accanto, nello stesso gruppo.
"""

from __future__ import annotations

import bpy  # type: ignore
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       IntProperty, StringProperty)
from bpy.types import PropertyGroup


class EM_PublicationRow(PropertyGroup):
    """Una riga del deck: **solo testo già calcolato**.

    Nessun campo qui viene derivato mentre si disegna. È la regola che rende
    il `draw` gratuito, ed è anche il motivo per cui i campi sono stringhe già
    formattate invece dei numeri da cui vengono: formattare è lavoro, e il
    lavoro si fa una volta sola, quando si riempie la cache.
    """

    name: StringProperty(default="")  # type: ignore
    node_id: StringProperty(default="")  # type: ignore
    selezionata: BoolProperty(
        name="Select",
        description="Include this asset in the next Bake & publish",
        default=False)  # type: ignore

    proprietario: StringProperty(default="")  # type: ignore
    granularita: StringProperty(default="rm")  # type: ignore
    membri: IntProperty(default=0)  # type: ignore

    stato: StringProperty(default="")  # type: ignore
    dove: StringProperty(default="")  # type: ignore
    tier: StringProperty(default="")  # type: ignore
    residency: StringProperty(default="")  # type: ignore
    scope: StringProperty(default="")  # type: ignore
    formato: StringProperty(default="")  # type: ignore
    packaging: StringProperty(default="")  # type: ignore
    peso: StringProperty(default="")  # type: ignore
    pubblicata_il: StringProperty(default="")  # type: ignore
    cosa_e_cambiato: StringProperty(default="")  # type: ignore
    url: StringProperty(default="")  # type: ignore

    #: perché NON è pubblicabile, quando non lo è. La frase viaggia col no
    #: perché un bottone spento senza una ragione è un bottone che sembra rotto.
    perche_no: StringProperty(default="")  # type: ignore
    pubblicabile: BoolProperty(default=False)  # type: ignore

    #: «pronto per» la destinazione scelta: stato + ragione, già risolti
    pronto: StringProperty(default="")  # type: ignore
    pronto_perche: StringProperty(default="")  # type: ignore


class EM_PublicationDeck(PropertyGroup):
    """Lo stato del deck per questa scena."""

    righe: CollectionProperty(type=EM_PublicationRow)  # type: ignore
    riga_attiva: IntProperty(default=0)  # type: ignore

    #: L'ORA DEL CONTO. Vuota = mai calcolato, ed è uno stato diverso da «zero
    #: risorse»: il pannello li dice in due modi diversi perché sono due
    #: situazioni diverse.
    calcolato_alle: StringProperty(default="")  # type: ignore
    sintesi: StringProperty(default="")  # type: ignore
    stale: IntProperty(default=0)  # type: ignore
    pubblicabili: IntProperty(default=0)  # type: ignore
    nota: StringProperty(default="")  # type: ignore

    #: La destinazione di cui si mostra la colonna «pronto per». Un enum e non
    #: un booleano `heriverse`: le destinazioni sono N dall'inizio.
    destinazione: EnumProperty(
        name="Ready for",
        description=("Which consumer the readiness column is about. Each "
                     "destination declares what it can open; the graph "
                     "declares what a resource is"),
        items=[("heriverse", "Heriverse", "The Heriverse web viewer"),
               ("room", "StratiGraph room", "A room on an StratiGraph Server")],
        default="heriverse")  # type: ignore
    destinazione_nota: StringProperty(default="")  # type: ignore

    mostra_master: BoolProperty(
        name="Show masters",
        description=("Masters are the sources the distributions are made "
                     "from. They are never published — they are archived, "
                     "which is a different act — but seeing that a chain has "
                     "its source safe is half the answer to «what is missing»"),
        default=True)  # type: ignore


_CLASSI = (EM_PublicationRow, EM_PublicationDeck)


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
