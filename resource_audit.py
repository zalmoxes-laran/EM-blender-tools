"""Diagnosi dei nodi risorsa di un grafo — SOLA LETTURA.

NIGHT-RIM/A3 chiede di contare i nodi risorsa **orfani o duplicati** e di
riportarli, e dice esplicitamente di non bonificare: «sono dati dell'utente.
Se E.D. vorrà una bonifica sarà un gesto suo, esplicito, un'altra volta».
Questo modulo quindi **non cancella niente** e non ha nemmeno il codice per
farlo: non è una dimenticanza, è il confine.

Senza `bpy`, come `rm_manager/epoch_edges.py` e `rm_manager/group_nodes.py`:
così la logica si prova fuori da Blender, che è l'unico modo di provarla
davvero su grafi costruiti a mano.

## COSA CONTA COME DIFETTO, E PERCHÉ

**Orfano** — un nodo risorsa che nessun arco `has_linked_resource` raggiunge.
Sono i nodi che l'export coniava con `uuid.uuid4()` a ogni giro: il ramo di
aggiornamento non scattava mai, nessuno li rimuoveva (grep `remove_node` in
`export_operators/`: zero) e un commento diceva di non richiamare l'updater
per non cancellarli. Un grafo passato per N export porta N-1 di questi.

**Duplicato** — due o più risorse appese allo STESSO nodo sorgente con lo
STESSO url. Non è la stessa cosa di un orfano: qui l'arco c'è, ma la risorsa
è stata creata due volte perché l'id era coniato. Due risorse con url
diversi sullo stesso sorgente NON sono un duplicato — un modello può
legittimamente avere un gltf e un tileset.
"""

from __future__ import annotations

#: I due `node_type` che valgono come risorsa. `"link"` è il nome pre-1.6
#: (`LinkNode`), e i grafi già salvati ne sono pieni: una diagnosi che
#: guardasse solo `"resource"` direbbe «tutto a posto» proprio sui grafi
#: che il difetto ha sporcato.
TIPI_RISORSA = ("resource", "link")

ARCO_RISORSA = "has_linked_resource"


def diagnosi(nodi=(), archi=()) -> dict:
    """Conta orfani e duplicati. Non modifica niente.

    `nodi` e `archi` sono iterabili di oggetti con gli attributi di
    s3Dgraphy (`node_id`, `node_type`, `data`; `edge_source`, `edge_target`,
    `edge_type`). Bastano dei sosia con gli stessi attributi, ed è quello che
    rende questa funzione provabile.
    """
    risorse = {}
    for n in nodi:
        if getattr(n, "node_type", "") in TIPI_RISORSA:
            risorse[n.node_id] = n

    #: sorgente → [id risorsa], seguendo solo gli archi giusti
    per_sorgente = {}
    raggiunte = set()
    for e in archi:
        if getattr(e, "edge_type", "") != ARCO_RISORSA:
            continue
        tgt = getattr(e, "edge_target", None)
        if tgt in risorse:
            raggiunte.add(tgt)
            per_sorgente.setdefault(getattr(e, "edge_source", None), []).append(tgt)

    orfani = sorted(set(risorse) - raggiunte)

    duplicati = {}
    for sorgente, ids in per_sorgente.items():
        per_url = {}
        for rid in ids:
            n = risorse[rid]
            dati = getattr(n, "data", None) or {}
            url = dati.get("url", "") if isinstance(dati, dict) else ""
            if not url:
                url = getattr(n, "url", "") or ""
            per_url.setdefault(url, []).append(rid)
        for url, gruppo in per_url.items():
            if len(gruppo) > 1:
                duplicati[f"{sorgente} → {url or '(senza url)'}"] = sorted(gruppo)

    return {
        "risorse_totali": len(risorse),
        "orfani": orfani,
        "duplicati": duplicati,
        "tipi_visti": sorted({getattr(n, "node_type", "") for n in risorse.values()}),
    }


def riassunto(d: dict) -> str:
    """Una riga per la console e per il report."""
    if not d["risorse_totali"]:
        return "Resources: none in this graph."
    pezzi = [f"{d['risorse_totali']} resource node(s)"]
    if d["orfani"]:
        pezzi.append(f"{len(d['orfani'])} ORPHAN (no has_linked_resource edge)")
    if d["duplicati"]:
        quanti = sum(len(v) for v in d["duplicati"].values())
        pezzi.append(f"{quanti} DUPLICATE across {len(d['duplicati'])} source/url pair(s)")
    if not d["orfani"] and not d["duplicati"]:
        pezzi.append("no orphans, no duplicates")
    if "link" in d["tipi_visti"]:
        pezzi.append('some are pre-1.6 node_type "link"')
    return " · ".join(pezzi)


# ══════════════════════════════════════════════════════════════════════
# NIGHT-RIM3/B4 · «STANTIA», CALCOLABILE
# ══════════════════════════════════════════════════════════════════════
#
# Tre stati, e sono tre domande diverse:
#
# * **irrisolvibile** — la risorsa dice di non sapere dove sono i suoi byte.
#   Esiste già come stato: è il flag `unresolved` dei nodi nati alla
#   promozione quando il .blend non era ancora salvato (B2). Qui si conta e si
#   spiega, non si inventa.
# * **orfana** — nessun arco `has_linked_resource` la raggiunge. È la
#   diagnosi che c'era già (`diagnosi()` qui sopra).
# * **stantia** — la derivata porta l'impronta della sorgente **al momento
#   del bake** (`source_fingerprint`, scritta da `resource_levels`), e quella
#   impronta non corrisponde più. Questa è nuova.
#
# LA PROVENIENZA NON È UN CAMPO, È UN GIRO. `promote_resource` registra la
# derivazione come processo DTC (crmdig:D7): `processo --dtc_had_input-->
# grezzo` e `processo --dtc_had_output--> derivata`. Per sapere da cosa viene
# una derivata si risale quel giro, e per questo la funzione vuole anche gli
# ARCHI e non solo i nodi.
#
# L'IMPRONTA ARRIVA INIETTATA, come `is_candidato` in `promotion_scale.conta`
# di EM16: calcolarla vuole il filesystem, e questo modulo non lo tocca — è
# ciò che lo rende provabile su grafi costruiti a mano.

EDGE_INPUT = "dtc_had_input"
EDGE_OUTPUT = "dtc_had_output"


def stato_risorse(nodi=(), archi=(), impronta_attuale=None) -> dict:
    """Stantie, orfane e irrisolvibili. Non modifica niente.

    `impronta_attuale(nodo_grezzo) -> str` è il fornitore iniettato: torna
    l'impronta ATTUALE della sorgente, o `""` se non la sa. Una stringa vuota
    NON conta come «diversa»: non sapere e sapere-che-è-cambiato sono due
    cose, e confonderle direbbe «rifai il bake» ogni volta che un file non è
    raggiungibile.
    """
    nodi = list(nodi)
    archi = list(archi)
    per_id = {n.node_id: n for n in nodi}
    risorse = {n.node_id: n for n in nodi
               if getattr(n, "node_type", "") in TIPI_RISORSA}

    def dati(n):
        d = getattr(n, "data", None)
        return d if isinstance(d, dict) else {}

    # ── irrisolvibili ────────────────────────────────────────────────
    irrisolvibili = sorted(rid for rid, n in risorse.items()
                           if dati(n).get("unresolved"))

    # ── orfane, dalla diagnosi che c'era già ─────────────────────────
    orfane = diagnosi(nodi, archi)["orfani"]

    # ── il giro della derivazione: derivata → processo → grezzo ──────
    #
    # UNA DERIVATA PUÒ AVERE PIÙ PROCESSI, e ignorarlo era un difetto vero,
    # trovato dal Publication Deck (NIGHT-DECK) misurando e non leggendo:
    #
    #   il bake scrive un D7 (`processo --dtc_had_input--> grezzo`,
    #   `processo --dtc_had_output--> derivata`); la PUBBLICAZIONE ne scrive
    #   un secondo, che ha un output e **nessun ingresso** — perché l'atto è
    #   «questi byte vanno nello store», non «questi byte vengono da lì».
    #
    # Con un dizionario semplice vinceva l'ultimo arco visto: si prendeva il
    # processo di pubblicazione, non si trovava nessun grezzo, e la derivata
    # finiva fra le `derivate_senza_sorgente` invece che fra le stantie.
    # **Effetto: pubblicare una derivata stantia la faceva smettere di
    # risultare stantia** — cioè esattamente il «è aggiornato» sbagliato che
    # pubblica roba vecchia credendola fresca.
    #
    # Quindi si tengono TUTTI i processi di una derivata e TUTTI i loro
    # ingressi, e si giudica sulle sorgenti che si conoscono.
    processi_di_derivata = {}
    for e in archi:
        if getattr(e, "edge_type", "") == EDGE_OUTPUT:
            processi_di_derivata.setdefault(
                getattr(e, "edge_target", None), []).append(
                    getattr(e, "edge_source", None))
    grezzi_di_processo = {}
    for e in archi:
        if getattr(e, "edge_type", "") == EDGE_INPUT:
            grezzi_di_processo.setdefault(
                getattr(e, "edge_source", None), []).append(
                    getattr(e, "edge_target", None))

    def sorgenti_di(derivata_id):
        """Gli id delle sorgenti note di una derivata, senza ripetizioni."""
        fuori = []
        for processo in processi_di_derivata.get(derivata_id, []):
            for grezzo in grezzi_di_processo.get(processo, []):
                if grezzo and grezzo not in fuori:
                    fuori.append(grezzo)
        return fuori

    stantie, senza_sorgente = [], []
    for rid, n in sorted(risorse.items()):
        impronta_al_bake = dati(n).get("source_fingerprint")
        if not impronta_al_bake:
            continue                # non è una derivata registrata: non si giudica
        noti = [(gid, per_id[gid]) for gid in sorgenti_di(rid)
                if gid in per_id]
        if not noti:
            #: ha l'impronta ma nessuna sorgente si trova: è un difetto suo,
            #: diverso dallo stantio, e va detto invece di essere contato
            #: come «aggiornata»
            senza_sorgente.append(rid)
            continue
        #: basta UNA sorgente cambiata: un tileset accorpa N mesh ed è stantio
        #: se ne cambia una qualunque. Conservativo nel verso giusto.
        for grezzo_id, grezzo in noti:
            adesso = (impronta_attuale(grezzo) if callable(impronta_attuale)
                      else "")
            if adesso and adesso != impronta_al_bake:
                stantie.append({"derivata": rid, "grezzo": grezzo_id,
                                "al_bake": impronta_al_bake, "adesso": adesso})
                break

    return {
        "risorse_totali": len(risorse),
        "stantie": stantie,
        "orfane": orfane,
        "irrisolvibili": irrisolvibili,
        "derivate_senza_sorgente": senza_sorgente,
    }


def riassunto_stato(d: dict) -> str:
    """Una riga per la console e per il report."""
    pezzi = [f"{d['risorse_totali']} resource node(s)"]
    for chiave, parola in (("stantie", "STALE"), ("orfane", "orphan"),
                           ("irrisolvibili", "unresolved"),
                           ("derivate_senza_sorgente", "derived-without-source")):
        if d.get(chiave):
            pezzi.append(f"{len(d[chiave])} {parola}")
    if len(pezzi) == 1:
        pezzi.append("all fresh")
    return " · ".join(pezzi)
