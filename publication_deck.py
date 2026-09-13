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

#: **D1 · la riga è l'ASSET, non la distribuzione.** La decisione «questo va
#: pubblicato» riguarda LA COSA, non il formato: un tileset con il suo zip e il
#: suo albero servito sono due distribuzioni e **una sola decisione**, e come
#: due righe avrebbero due spunte che si accendono insieme — incomprensibile.
#: Le distribuzioni si vedono nella scheda.
#:
#: L'ordine in cui uno stato di distribuzione diventa lo stato dell'asset. Il
#: primo presente vince, e il criterio è **quanto lavoro resta**: un asset con
#: una stantia è stantio anche se ha altre due distribuzioni a posto, perché
#: quella stantia è il lavoro; un asset con una pubblicata e uno zip ancora
#: locale è `baked`, perché qualcosa non è ancora uscito. `master` per ultimo:
#: un asset fatto di soli master non ha niente sulla soglia.
ORDINE_RIASSUNTO = ("stale", "baked", "unresolved", "published", "orphan",
                    "master")

#: I tipi di media che il deck distingue a colpo d'occhio. È il PRIMO colpo
#: d'occhio della riga — prima ancora dello stato — perché «di che cosa stiamo
#: parlando» viene prima di «a che punto è».
MEDIA = ("mesh", "tileset", "pointcloud", "image", "document", "other")

#: Le estensioni che decidono il media quando `url_type` non basta. Non è un
#: elenco chiuso di ciò che si può pubblicare (quello sarebbe il difetto che
#: `canConsumeResource` evita di proposito): è solo l'icona da mostrare, e chi
#: non è riconosciuto prende `other` senza perdere nessun diritto.
_ESTENSIONI_MEDIA = {
    "gltf": "mesh", "glb": "mesh", "obj": "mesh", "fbx": "mesh",
    "ply": "pointcloud", "las": "pointcloud", "laz": "pointcloud",
    "e57": "pointcloud", "pcd": "pointcloud",
    "jpg": "image", "jpeg": "image", "png": "image", "tif": "image",
    "tiff": "image", "webp": "image", "exr": "image",
    "pdf": "document", "doc": "document", "docx": "document",
    "odt": "document", "txt": "document", "md": "document",
    "csv": "document", "xlsx": "document",
}

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


def _media(dati: dict) -> str:
    """Di che cosa stiamo parlando: mesh, tileset, nuvola, immagine, documento.

    È il primo colpo d'occhio della riga, e si legge da DUE fonti che dicono
    cose diverse: `url_type` è la categoria dichiarata dal modello
    (`3d_model`, `image`, `document`) e l'estensione è il formato vero. La
    categoria vince dove c'è, perché è ciò che l'autore ha dichiarato; sotto
    `3d_model` l'estensione decide fra mesh, tileset e nuvola, che il modello
    non distingue e che a video sono tre cose diversissime.
    """
    url = _testo(dati.get("url"))
    basso = url.lower().split("?")[0]
    if basso.endswith("tileset.json") or _testo(dati.get("packaging")) == "archive" \
            and "tileset" in basso:
        return "tileset"
    tipo = _testo(dati.get("url_type")).lower()
    estensione = _formato(dati)
    if tipo == "3d_model" or url.startswith("blend://"):
        #: un `blend://` è un datablock: una mesh, finché il modello non dice
        #: altro. Nessuna estensione da leggere, e inventarne una sarebbe una
        #: misura al posto di un'assenza.
        return _ESTENSIONI_MEDIA.get(estensione, "mesh")
    per_estensione = _ESTENSIONI_MEDIA.get(estensione)
    if per_estensione:
        return per_estensione
    if tipo in ("image", "document"):
        return tipo
    return "other"


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
            #: LA CHIAVE DELL'ASSET. Il container quando c'è, altrimenti l'RM,
            #: altrimenti la risorsa stessa (un'orfana è un asset di una riga:
            #: nessuno la raggiunge, e appenderla a un proprietario inventato
            #: la nasconderebbe proprio dove il deck deve mostrarla).
            "asset_id": (gruppo or {}).get("id") or rm_id or rid,
            "rm_id": rm_id or "",
            "media": _media(dati),
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

    assets = per_asset(fuori)
    return {"righe": fuori, "assets": assets, "sommario": sommario(assets)}


def per_asset(righe_) -> list:
    """**D1 · da una riga per distribuzione a una riga per ASSET.**

    La decisione «questo va pubblicato» riguarda LA COSA, non il formato. Un
    tileset con il suo zip e il suo albero servito sono due distribuzioni e una
    sola decisione: come due righe avrebbero due spunte che si accendono
    insieme, che non vuol dire niente. Le distribuzioni restano, intere, dentro
    l'asset — la scheda le mostra.

    Effetto collaterale, e non è il motivo ma si sente: su un progetto vero le
    righe crollano, e la lista dei nomi si vede tutta.

    L'ordine degli asset è quello che il deck vuole far leggere: prima ciò che
    manca (`ORDINE_RIASSUNTO`), poi il nome. Un elenco ordinato per id sarebbe
    ordinato per un fatto che non interessa a nessuno.
    """
    per_chiave = {}
    for r in righe_ or []:
        per_chiave.setdefault(r["asset_id"], []).append(r)

    fuori = []
    for chiave, distribuzioni in per_chiave.items():
        distribuzioni = sorted(distribuzioni, key=lambda d: (d["tier"] != "distribution",
                                                            d["nome"]))
        stati = {d["stato"] for d in distribuzioni}
        stato = next((s for s in ORDINE_RIASSUNTO if s in stati),
                     distribuzioni[0]["stato"])
        prima = distribuzioni[0]
        #: il nome dell'asset è quello del PROPRIETARIO — il container o l'RM —
        #: perché è la cosa di cui si sta decidendo. Un'orfana non ha un
        #: proprietario e allora porta il proprio nome: è un asset di una riga.
        nome = (prima["etichetta_proprietario"]
                if prima["etichetta_proprietario"] not in ("", "—")
                else prima["nome"])
        pubblicabili_qui = [d for d in distribuzioni if d["pubblicabile"]["si"]]
        ragioni = [d["pubblicabile"]["perche"] for d in distribuzioni
                   if not d["pubblicabile"]["si"] and d["pubblicabile"]["perche"]]
        fuori.append({
            "id": chiave,
            "nome": nome,
            "media": _media_dell_asset(distribuzioni),
            "stato": stato,
            "granularita": prima["granularita"],
            "membri": prima["membri"],
            "rm_id": prima["rm_id"],
            "distribuzioni": distribuzioni,
            "pubblicabili": [d["id"] for d in pubblicabili_qui],
            #: la ragione si dice UNA volta per asset, e solo quando NESSUNA
            #: delle sue distribuzioni si può pubblicare: con una pubblicabile
            #: e una no, il «no» è un dettaglio della scheda, non il verdetto
            #: dell'asset
            "perche_no": ("" if pubblicabili_qui
                          else (ragioni[0] if ragioni else "")),
            "tier": ("master" if all(d["tier"] == "master" for d in distribuzioni)
                     else "distribution"),
            "pubblicata_il": max((d["pubblicata_il"] for d in distribuzioni), default=""),
            "cosa_e_cambiato": next((d["cosa_e_cambiato"] for d in distribuzioni
                                     if d["cosa_e_cambiato"]), ""),
            "pronto_per": _pronto_dell_asset(distribuzioni),
        })
    ordine = {s: i for i, s in enumerate(ORDINE_RIASSUNTO)}
    fuori.sort(key=lambda a: (ordine.get(a["stato"], 99), a["nome"].lower()))
    return fuori


def _media_dell_asset(distribuzioni) -> str:
    """Il media dell'asset: quello della distribuzione che lo rappresenta.

    Si preferisce una `distribution` al master, perché è la cosa che esce; fra
    più distribuzioni vince il media più specifico (un tileset con dentro delle
    mesh è un tileset, non una mesh), e l'ordine di specificità è quello di
    `MEDIA`.
    """
    candidate = [d for d in distribuzioni if d["tier"] != "master"] or list(distribuzioni)
    rango = {m: i for i, m in enumerate(MEDIA)}
    return min((d["media"] for d in candidate), key=lambda m: rango.get(m, 99))


def _pronto_dell_asset(distribuzioni) -> dict:
    """«Pronto per» dell'asset: `{destinazione: {state, why}}`.

    Basta **una** distribuzione che la destinazione sappia aprire: è
    esattamente ciò che `getLinkFromRepresentationModel` fa dall'altra parte —
    raccoglie le candidate e ne sceglie una. Un asset con uno zip che Heriverse
    non scompatta e un albero servito che carica è pronto, e dirlo «no» per lo
    zip sarebbe rispondere di una distribuzione invece che della cosa.
    """
    nomi = set()
    for d in distribuzioni:
        nomi.update(d["pronto_per"])
    fuori = {}
    for nome in sorted(nomi):
        verdetti = [d["pronto_per"].get(nome) or {} for d in distribuzioni
                    if nome in d["pronto_per"]]
        if any(v.get("ok") for v in verdetti):
            fuori[nome] = {"state": "yes", "why": ""}
            continue
        #: fra i no, si riporta lo stato MENO definitivo: un «non lo so» detto
        #: accanto a un «no» resta un non lo so, e appiattirlo su «no» sarebbe
        #: la bugia di T3 rifatta un livello più su
        for stato in ("unknown", "no", "n/a"):
            scelto = next((v for v in verdetti if v.get("state") == stato), None)
            if scelto:
                fuori[nome] = {"state": stato, "why": scelto.get("why", "")}
                break
        else:
            primo = verdetti[0] if verdetti else {}
            fuori[nome] = {"state": str(primo.get("state") or "no"),
                           "why": primo.get("why", "")}
    return fuori


def sommario(assets) -> dict:
    """*N assets · M published · K stale*, e i conti che la testa mostra.

    Conta **asset**, non distribuzioni, da quando la riga è l'asset: «19 assets»
    e «26 distributions» sono due numeri veri e uno solo risponde alla domanda
    «quante cose devo decidere».

    `K` è il numero che conta: quando è diverso da zero, è la cosa più
    importante del pannello.
    """
    assets = list(assets or [])
    per_stato = {}
    for a in assets:
        per_stato[a["stato"]] = per_stato.get(a["stato"], 0) + 1
    return {
        "assets": len(assets),
        "distribuzioni": sum(len(a["distribuzioni"]) for a in assets),
        "published": per_stato.get("published", 0),
        "stale": per_stato.get("stale", 0),
        "per_stato": per_stato,
        #: quanti si possono pubblicare adesso: è ciò che un bottone
        #: «Publish» può davvero fare, e dirlo evita di offrire un gesto che
        #: poi rifiuta riga per riga
        "pubblicabili": sum(1 for a in assets if a["pubblicabili"]),
        "blocchi": blocchi(assets),
    }


def blocchi(assets) -> list:
    """Le ragioni per cui NON si pubblica, contate. → `[(ragione, quanti), …]`.

    **D5 · una ragione che vale per tutti si dice una volta in testa, non
    diciannove volte nelle righe.** Quando tutti gli asset di un progetto
    riportano la stessa frase, quella frase non è un fatto sull'asset: è un
    fatto sul progetto — e diciannove copie della stessa riga non lo rendono
    più vero, lo rendono illeggibile.

    Ordinato per quanti ne tiene fermi: chi ne blocca di più va letto per primo.
    """
    conta = {}
    for a in assets or []:
        if a["pubblicabili"] or not a["perche_no"]:
            continue
        conta[a["perche_no"]] = conta.get(a["perche_no"], 0) + 1
    return sorted(conta.items(), key=lambda kv: (-kv[1], kv[0]))


def riga_di_sintesi(s: dict) -> str:
    """La riga in testa, sempre visibile. In inglese come tutta l'interfaccia."""
    return (f"{s['assets']} assets · {s['published']} published · "
            f"{s['stale']} stale")
