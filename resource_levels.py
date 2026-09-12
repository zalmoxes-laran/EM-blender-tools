"""I tre livelli di una risorsa, e chi scrive il verbale del bake.

NIGHT-RIM3/B3 · decisione 10 di E.D., che vale la pena rileggere prima di
toccare questo file:

* il **grezzo** è un nodo risorsa suo e **non sparisce mai** — l'insostituibile:
  il `blend://` interno creato alla promozione (B2), o il file originale del
  rilievo;
* la **derivata** è un **secondo nodo** — altri byte, altro formato, il glb
  ottimizzato per il web — legata al grezzo da `source_id`;
* la **pubblicata** **non è un terzo nodo**: è la derivata quando il suo
  locator risolve a un URI raggiungibile e porta checksum ed evento D7.

Quindi: **due nodi, tre stati**. Lo stato si legge da `residency` /
`effective_residency` e dal kind del locator — nessun vocabolario nuovo.

Questo modulo non importa `bpy` di proposito: i conti si provano fuori da
Blender, come `resource_audit.py`.
"""

from __future__ import annotations

import hashlib
import os

#: Il suffisso della derivata prodotta dal bake. Derivato dall'id dell'RM come
#: ogni altro id di queste notti: è ciò che permette all'export di TROVARE
#: invece di rifare, e per cui al secondo giro i nodi nuovi sono zero.
SUFFISSO_DERIVATA = "_link"


def sha256_del_file(percorso: str) -> str:
    """`sha256:<hex>` del file, o `""` se non c'è.

    L'algoritmo viaggia col valore perché è la convenzione di s3Dgraphy
    (`ResourceNode.checksum`): un hex nudo fra due anni non si sa più
    verificare.
    """
    if not percorso or not os.path.isfile(percorso):
        return ""
    h = hashlib.sha256()
    with open(percorso, "rb") as f:
        for blocco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(blocco)
    return f"sha256:{h.hexdigest()}"


def impronta_sorgente(percorso: str) -> str:
    """L'impronta del GREZZO al momento del bake: `mtime:<int>:size:<int>`.

    NIGHT-RIM3/B4 · per un grezzo che vive dentro un .blend non esiste
    un'impronta dei soli byte di quel datablock senza aprire il file e
    serializzare la mesh — costo che un export non può permettersi per
    oggetto. La coppia (mtime, dimensione) del FILE che lo contiene è
    onesta e a costo zero.

    È **conservativa**: segnala stantio anche per una modifica del .blend che
    non riguardava quel datablock. È il verso giusto in cui sbagliare — un
    falso «rifai il bake» costa un bottone, un falso «è aggiornato» costa una
    pubblicazione sbagliata.

    Torna `""` quando il file non c'è: chi legge distingue «non so» da
    «diverso», che sono due cose.
    """
    if not percorso or not os.path.isfile(percorso):
        return ""
    st = os.stat(percorso)
    return f"mtime:{int(st.st_mtime)}:size:{st.st_size}"


def registra_derivata(graph, *, derivata_id, url, source_id,
                      link_to=None, name=None, file_esportato="",
                      impronta_del_grezzo=""):
    """Il baker scrive il verbale: la derivata, la sua provenienza, il digest.

    Non crea un baker nuovo — l'export Heriverse **è** il baker. Questa
    funzione è il punto in cui quello che c'è smette di coniare un nodo
    qualunque e **registra**: id conservato, `source_id` verso il grezzo,
    `sha256` dei byte prodotti, evento D7. Tutto questo lo fa già
    `s3Dgraphy/publication.py::promote_resource`, che è la ragione per cui qui
    non c'è logica di grafo ma una chiamata.

    `residency="resident"`: i byte prodotti dal bake sono sul mio disco, e
    `resident` è precisamente questo nel vocabolario di `RESOURCE_NODE`
    (`RESIDENCIES = ("reference", "resident")`). `reference` — il default di
    `promote_resource` — sarebbe una bugia per un file locale.

    Torna `(ok, messaggio)`. Non solleva: un export non deve fallire perché
    il verbale non si è potuto scrivere, ma deve **dirlo**.
    """
    try:
        from s3dgraphy.publication import promote_resource
    except ImportError as e:
        # decisione 14: si cattura ciò che si sa gestire, e si dice cosa manca
        return False, (f"publication.promote_resource non disponibile ({e}): "
                       "derivata non registrata")

    digest = sha256_del_file(file_esportato)
    if not digest:
        #: senza digest il verbale non è verificabile, e `promote_resource`
        #: lo vuole. Meglio dirlo che scrivere un checksum finto.
        return False, (f"nessun file esportato da digerire ({file_esportato!r}): "
                       "derivata non registrata")

    try:
        promote_resource(
            graph, derivata_id,
            url=url, sha256=digest,
            source_id=source_id,
            link_to=link_to,
            name=name,
            residency="resident",
        )
    except Exception as e:                          # noqa: BLE001
        return False, f"promote_resource ha rifiutato: {e}"

    #: l'impronta del grezzo AL MOMENTO DEL BAKE: è l'unico dato che rende
    #: «stantia» calcolabile invece che sospettabile (B4). Sta sulla
    #: derivata, perché è lei a ricordare da cosa è stata fatta e quando.
    nodo = graph.find_node_by_id(derivata_id)
    if nodo is not None and impronta_del_grezzo:
        nodo.data["source_fingerprint"] = impronta_del_grezzo
    return True, ""
