"""P1 · Il Publication Deck — il DATO, fuori dal `draw`.

Il deck risponde a **una domanda sola**: *cosa manca perché questo em.json sia
consumabile fuori da Blender?* Guarda la soglia fra il dentro e il fuori. Non è
un gestore di asset, non è un browser di file, non importa niente.

Questo modulo è la metà che si calcola. Non importa `bpy`, come
`resource_audit` e `publication_gesture`, e per la stessa ragione: una riga di
tabella è un fatto, e i fatti si provano senza aprire Blender.

**PERCHÉ NON SI CHIAMA NEL `draw`.** `stato_risorse` costa un `os.stat` per
derivata — misurato in NIGHT-RIM3 — e un pannello Blender si ridisegna a ogni
movimento del mouse. Il conto si fa su richiesta, finisce in una cache, e il
pannello disegna la cache **dicendo a che ora è stata presa**. Un numero
vecchio che dice di essere vecchio è informazione; un numero vecchio che si
spaccia per fresco è il difetto che questa settimana è passata a togliere.

**DUE GRANULARITÀ**, ed è il punto che richiede attenzione: alcune
distribuzioni appartengono a un singolo RM, altre — il tileset — a un
**container** (strategia di pubblicazione, N a 1). Le righe non sono tutte
della stessa specie, e una riga di tileset che fingesse di essere un modello
direbbe che un rilievo di quattromila tile è una mesh.
"""

from __future__ import annotations

from . import resource_audit
from . import publication_gesture

#: Gli stati di una risorsa nella scala, in ordine di distanza dal fuori.
#: Non è vocabolario nuovo: sono i nomi che il modello già usa (`tier`,
#: `residency`, il checksum) letti insieme. L'unica parola che questo modulo
#: conia è `stale`, e `resource_audit` la calcolava già.
STATI = ("unresolved", "master", "baked", "published", "stale", "orphan")

#: Le due specie di riga.
GRANULARITA = ("rm", "container")

#: L'arco che lega una risorsa a ciò che rappresenta.
EDGE_RISORSA = "has_linked_resource"


def _dati(nodo) -> dict:
    d = getattr(nodo, "data", None)
    return d if isinstance(d, dict) else {}


def _testo(v) -> str:
    return str(v or "").strip()


def _formato(dati: dict) -> str:
    """Il formato, dal locator. Il `url_type` del modello dice la CATEGORIA
    (`3d_model`, `image`), non il formato: per scegliere serve l'estensione,
    ed è quello che un consumatore guarda."""
    url = _testo(dati.get("url")).split("?")[0].rstrip("/")
    if url.startswith("blend://"):
        #: un locator interno non ha un'estensione da leggere: il formato È
        #: il datablock dentro un .blend, e dirlo «?» nasconderebbe che
        #: quella riga è proprio la fonte che non si può servire
        return "blend"
    coda = url.rsplit("/", 1)[-1]
    if "." in coda:
        return coda.rsplit(".", 1)[-1].lower()
    return _testo(dati.get("url_type")) or "?"


def _peso_leggibile(byte) -> str:
    """Un peso che si legge. Assente resta assente: uno `0 B` inventato
    direbbe «file vuoto», che è una misura e non un'assenza."""
    if byte is None:
        return ""
    try:
        n = float(byte)
    except (TypeError, ValueError):
        return ""
    for unita in ("B", "KB", "MB", "GB"):
        if n < 1024 or unita == "GB":
            return f"{n:.0f} {unita}" if unita == "B" else f"{n:.1f} {unita}"
        n /= 1024
    return ""


def _dove_stanno_i_byte(dati: dict) -> str:
    """blend / disk / store — e con il vocabolario che esiste già.

    Si LEGGE da `residency` e dal kind del locator, non si conia un sinonimo:
    `resident` e `reference` sono i due valori del modello, e questa funzione
    dice soltanto *dove*, che è la domanda della riga.
    """
    url = _testo(dati.get("url"))
    if url.startswith("blend://"):
        return "blend"
    if url.lower().startswith(("s3://", "http://", "https://")):
        return "store"
    return "disk" if url else "?"


def _stato(nodo, dati: dict, *, stantia: bool, orfana: bool,
           irrisolvibile: bool) -> str:
    """Dove sta questa risorsa nella scala. Un ordine di precedenza, e ognuno
    ha una ragione:

    * `unresolved` per primo: una risorsa che non sa dove sono i suoi byte non
      è né fresca né stantia, e chiamarla in un altro modo sarebbe rispondere
      a una domanda che non si può porre;
    * `orphan` subito dopo: nessuno la raggiunge, quindi il suo stato nella
      catena non vuol dire niente;
    * `master` prima di tutti gli stati di distribuzione, perché un master non
      si pubblica — si archivia, che è un altro gesto (`publication_gesture`);
    * `stale` prima di `published`: una pubblicata stantia è **il caso che il
      deck esiste per mostrare**, e dirla «published» la nasconderebbe.
    """
    if irrisolvibile:
        return "unresolved"
    if orfana:
        return "orphan"
    if publication_gesture._tier(nodo) == "master":
        return "master"
    if stantia:
        return "stale"
    return "published" if dati.get("checksum") and _dove_stanno_i_byte(dati) == "store" \
        else "baked"


def _quando_pubblicata(nodo_processo) -> str:
    """La data dell'ultima pubblicazione, dal timbro editoriale del processo
    D7. Non è un campo della risorsa: la risorsa dice *cosa è*, l'evento dice
    *quando è successo*, ed è giusto che stiano in due posti diversi."""
    d = _dati(nodo_processo)
    return _testo(d.get("modified_at") or d.get("created_at"))


def _cosa_e_cambiato(al_bake: str, adesso: str) -> str:
    """Sulle stantie, la differenza in una frase leggibile.

    Le impronte sono due stringhe canoniche (`struct:v=…:f=…`): confrontarle
    campo per campo dice *cosa* è cambiato, mentre mostrarle intere direbbe
    soltanto che sono diverse — che è ciò che l'utente già sa, visto che è per
    quello che la riga è lì.
    """
    def campi(s):
        s = _testo(s)
        for pezzo in s.split(":"):
            if "=" in pezzo:
                k, _, v = pezzo.partition("=")
                yield k, v
    prima, dopo = dict(campi(al_bake)), dict(campi(adesso))
    if not prima or not dopo:
        #: famiglie diverse (una `mtime:`, una `struct:`) o un'impronta vuota:
        #: non si confrontano campo per campo, e fingere di farlo direbbe una
        #: cosa precisa su un confronto che non si può fare
        return "the fingerprint changed shape — re-bake to compare again"
    nomi = {"v": "vertices", "f": "faces", "bb": "bounding box",
            "mat": "materials", "ev": "modifiers", "set": "members",
            "h": "contents"}
    pezzi = []
    for chiave in sorted(set(prima) | set(dopo)):
        a, b = prima.get(chiave), dopo.get(chiave)
        if a == b:
            continue
        etichetta = nomi.get(chiave, chiave)
        if chiave in ("v", "f", "set") and a and b:
            pezzi.append(f"{etichetta} {a} → {b}")
        else:
            pezzi.append(f"{etichetta} changed")
    return ", ".join(pezzi) or "the source changed"


def righe(nodi=(), archi=(), *, impronta_attuale=None, container_di=None,
          destinazioni=None, esiste=None) -> dict:
    """Tutto ciò che il deck mostra, calcolato una volta. → `{righe, sommario}`.

    Args:
        nodi / archi: il grafo.
        impronta_attuale: il fornitore iniettato di `stato_risorse` — è QUI che
            si paga il filesystem, ed è la ragione per cui questa funzione non
            va chiamata in un `draw`.
        container_di: `(rm_node_id) -> {"id","label","membri"}` oppure `None`
            per gli RM che non stanno in un container. Iniettato perché i
            container vivono in una property di scena (`bpy`), e questo modulo
            non la deve conoscere per essere provabile.
        destinazioni: `{nome: (dati_risorsa) -> {"ok", "why"}}` — «pronto per
            chi». Un dizionario e non un parametro singolo **fin dall'inizio**:
            Heriverse è la prima, la stanza StratiGraph è già la seconda, e
            aggiungere la seconda a una struttura fatta per una sola è il
            genere di refactor che non si fa più.
        esiste: passato a `publication_gesture` per dire se i byte ci sono.

    Nessuna riga per i nodi che non sono risorse, e nessuna per i master?
    **No**: i master ci sono, e con lo stato `master`. Il deck guarda la
    soglia, e sapere che una catena ha la sua fonte al sicuro è metà della
    risposta alla domanda «cosa manca».
    """
    nodi, archi = list(nodi), list(archi)
    per_id = {n.node_id: n for n in nodi}
    stato = resource_audit.stato_risorse(nodi, archi,
                                         impronta_attuale=impronta_attuale)
    stantie = {s["derivata"]: s for s in stato["stantie"]}
    orfane = set(stato["orfane"])
    irrisolvibili = set(stato["irrisolvibili"])

    # ── chi possiede una risorsa, e da quale processo viene ────────────────
    proprietario = {}
    for e in archi:
        if _testo(getattr(e, "edge_type", "")) == EDGE_RISORSA:
            proprietario.setdefault(getattr(e, "edge_target", None),
                                    getattr(e, "edge_source", None))
    processo_di = {}
    for e in archi:
        if _testo(getattr(e, "edge_type", "")) == resource_audit.EDGE_OUTPUT:
            processo_di[getattr(e, "edge_target", None)] = \
                getattr(e, "edge_source", None)
    ingressi_di = {}
    for e in archi:
        if _testo(getattr(e, "edge_type", "")) == resource_audit.EDGE_INPUT:
            ingressi_di.setdefault(getattr(e, "edge_source", None), []).append(
                getattr(e, "edge_target", None))

    fuori = []
    for rid, nodo in sorted(per_id.items()):
        if _testo(getattr(nodo, "node_type", "")) not in \
                publication_gesture.TIPI_RISORSA:
            continue
        dati = _dati(nodo)
        rm_id = proprietario.get(rid)
        rm = per_id.get(rm_id)
        gruppo = container_di(rm_id) if (callable(container_di) and rm_id) else None
        processo = per_id.get(processo_di.get(rid))
        info_stantia = stantie.get(rid)

        riga = {
            "id": rid,
            "nome": _testo(getattr(nodo, "name", "")) or rid,
            "appartiene_a": rm_id or "",
            "etichetta_proprietario": (
                (gruppo or {}).get("label")
                or _testo(getattr(rm, "name", "")) or rm_id or "—"),
            "granularita": "container" if gruppo else "rm",
            "membri": int((gruppo or {}).get("membri") or 0),
            "tier": publication_gesture._tier(nodo),
            "residency": _testo(dati.get("residency")),
            "scope": _testo(dati.get("scope")),
            "dove": _dove_stanno_i_byte(dati),
            "formato": _formato(dati),
            "packaging": _testo(dati.get("packaging")),
            "peso": _peso_leggibile(dati.get("size_bytes")),
            "peso_byte": dati.get("size_bytes"),
            "url": _testo(dati.get("url")),
            "checksum": _testo(dati.get("checksum")),
            "checksum_of": _testo(dati.get("checksum_of")),
            "pubblicata_il": _quando_pubblicata(processo),
            "sorgenti": sorted(
                x for x in ingressi_di.get(processo_di.get(rid), []) if x),
            "cosa_e_cambiato": (
                _cosa_e_cambiato(info_stantia["al_bake"], info_stantia["adesso"])
                if info_stantia else ""),
        }
        riga["stato"] = _stato(nodo, dati, stantia=bool(info_stantia),
                               orfana=rid in orfane,
                               irrisolvibile=rid in irrisolvibili)
        riga["pubblicabile"] = publication_gesture.stato_di_pubblicazione(
            nodo, esiste=esiste)
        riga["pronto_per"] = {
            nome: (giudice(dati) if callable(giudice)
                   else {"ok": False, "why": "no judge for this destination"})
            for nome, giudice in (destinazioni or {}).items()}
        fuori.append(riga)

    return {"righe": fuori, "sommario": sommario(fuori)}


def sommario(righe_) -> dict:
    """*N assets · M published · K stale*, e i conti che la testa mostra.

    `K` è il numero che conta: quando è diverso da zero, è la cosa più
    importante del pannello.
    """
    righe_ = list(righe_ or [])
    per_stato = {}
    for r in righe_:
        per_stato[r["stato"]] = per_stato.get(r["stato"], 0) + 1
    return {
        "assets": len(righe_),
        "published": per_stato.get("published", 0),
        "stale": per_stato.get("stale", 0),
        "per_stato": per_stato,
        #: quanti si possono pubblicare adesso: è ciò che un bottone
        #: «Bake & publish» può davvero fare, e dirlo evita di offrire un
        #: gesto che poi rifiuta riga per riga
        "pubblicabili": sum(1 for r in righe_ if r["pubblicabile"]["si"]),
    }


def riga_di_sintesi(s: dict) -> str:
    """La riga in testa, sempre visibile. In inglese come tutta l'interfaccia."""
    return (f"{s['assets']} assets · {s['published']} published · "
            f"{s['stale']} stale")
