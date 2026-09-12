"""R6 · Il gesto che mancava: portare una distribution nello store.

Il modello ha tre stati e solo due erano raggiungibili. Il master nasce alla
promozione (B2), la distribution al bake (R2) — e la **pubblicata** non la
produceva nessun gesto: l'export scrive distribuzioni con un url relativo e si
ferma lì. «Pubblicata» non è un tier: è lo stato di una distribution il cui
locator risolve a qualcosa di raggiungibile e che porta un checksum.

Mezzo pezzo esisteva già — la promozione a MinIO di `resources_tab` — e
l'altro mezzo è `s3Dgraphy/publication.py::promote_resource`, che sa già
scrivere locator, checksum e l'evento D7. Qui non si riscrive né l'uno né
l'altro: si dice **quali** distribuzioni sono pubblicabili e perché le altre no.

Nessun `bpy`: la regola si prova fuori da Blender. E **nessun pannello** — il
Publication Deck è un'altra notte.
"""

from __future__ import annotations

#: I tipi che contano come risorsa, col nome vecchio accettato in lettura (un
#: grafo caricato senza passare dall'importer porta ancora `link`).
TIPI_RISORSA = ("resource", "link")

#: Gli schemi che sono già un indirizzo raggiungibile: chi ce l'ha è già
#: pubblicato, e ripubblicarlo sposterebbe i byte senza che nessuno l'abbia
#: chiesto.
SCHEMI_REMOTI = ("http://", "https://", "s3://")


def _dati(nodo) -> dict:
    d = getattr(nodo, "data", None)
    return d if isinstance(d, dict) else {}


def _tier(nodo) -> str:
    """Il tier letto, col ripiego di `ResourceNode.effective_tier`. Scritto qui
    perché questa funzione deve girare anche su nodi che quella classe non la
    hanno (un grafo degradato a `Node` da un import con avvisi)."""
    letto = getattr(nodo, "tier", None)
    if callable(letto):
        dichiarato = letto()
        if dichiarato:
            return dichiarato
    dichiarato = _dati(nodo).get("tier")
    if dichiarato:
        return str(dichiarato)
    url = str(_dati(nodo).get("url") or "")
    return "master" if url.startswith("blend://") else "distribution"


def stato_di_pubblicazione(nodo, esiste=None) -> dict:
    """Questa risorsa si può pubblicare? → `{'si': bool, 'perche': str}`.

    `esiste(percorso) -> bool` è il fornitore iniettato che dice se i byte
    locali ci sono. Senza di lui il file non si guarda e la risposta è
    sull'indirizzo soltanto — che è già metà del lavoro e non richiede un
    disco.

    Le ragioni sono frasi e non codici: questa funzione esiste perché
    l'interfaccia possa dire **perché** un bottone è spento, e «no» da solo è
    indistinguibile da un guasto.
    """
    dati = _dati(nodo)
    url = str(dati.get("url") or "")
    if getattr(nodo, "node_type", "") not in TIPI_RISORSA:
        return {"si": False, "perche": "non è una risorsa"}
    if _tier(nodo) == "master":
        # Un master si può archiviare, ma non è questo il gesto: pubblicare
        # vuol dire mettere a disposizione ciò che gli altri consumano, e un
        # master è ciò da cui quello si fa. Sono due atti diversi con due
        # ragioni diverse, e confonderli metterebbe un originale
        # fotogrammetrico in un bucket pubblico per sbaglio.
        return {"si": False, "perche": "è un master: si archivia, non si pubblica"}
    if not url:
        return {"si": False, "perche": "non ha un locator"}
    if url.startswith("blend://"):
        return {"si": False, "perche": "vive dentro un .blend"}
    if url.lower().startswith(SCHEMI_REMOTI):
        gia = bool(dati.get("checksum"))
        return {"si": False,
                "perche": ("già pubblicata" if gia else
                           "ha già un indirizzo remoto, ma nessun checksum: "
                           "è una promessa, non un fatto")}
    if esiste is not None and not esiste(url):
        return {"si": False, "perche": "i byte non sono dove il locator dice"}
    return {"si": True, "perche": ""}


def pubblicabili(nodi, esiste=None) -> dict:
    """Il conto, per un pannello che ancora non c'è.

    → `{'si': [id…], 'no': {id: perché…}}`. Due basket e non una lista
    filtrata: chi guarda deve poter chiedere «e le altre?» e ricevere una
    risposta, non un silenzio.
    """
    si, no = [], {}
    for nodo in nodi or []:
        if getattr(nodo, "node_type", "") not in TIPI_RISORSA:
            continue
        esito = stato_di_pubblicazione(nodo, esiste)
        if esito["si"]:
            si.append(nodo.node_id)
        else:
            no[nodo.node_id] = esito["perche"]
    return {"si": sorted(si), "no": no}
