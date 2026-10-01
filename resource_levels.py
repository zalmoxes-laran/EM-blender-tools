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

#: NIGHT-FIN/T1 · il suffisso della SECONDA distribuzione, quella che viaggia.
#:
#: Dallo stesso insieme di master nascono due distribution con id distinti e
#: stabili: l'albero servito (`_link`, che Heriverse carica) e l'archivio
#: (`_archive`, che viaggia e si archivia). Non sono in alternativa e non sono
#: due versioni della stessa: sono due **forme** della stessa cosa, ciascuna
#: col suo checksum, e ogni consumatore prende quella che sa aprire.
#:
#: `_link` resta il suffisso di prima di proposito: cambiarlo trasformerebbe
#: in orfano il nodo di ogni grafo già scritto.
SUFFISSO_ARCHIVIO = "_archive"


def _resource_digest():
    """`resource_digest` (dtcstamp, la ruota installata), dentro l'add-on
    come pacchetto e nei test come modulo di primo livello."""
    try:
        from . import resource_digest
    except ImportError:
        import resource_digest  # type: ignore
    return resource_digest


def _resource_revisions():
    """`resource_revisions`, come `_resource_digest`."""
    try:
        from . import resource_revisions
    except ImportError:
        import resource_revisions  # type: ignore
    return resource_revisions


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


#: Il prefisso delle impronte strutturali. Serve a distinguerle a occhio da
#: quelle vecchie `mtime:…:size:…` senza doverle interpretare: un confronto fra
#: due impronte di famiglie diverse non significa niente, e chi legge deve
#: potersene accorgere.
PREFISSO_STRUTTURALE = "struct:"

#: Quanto si arrotonda il bounding box. Un micron: sotto c'è il rumore in
#: virgola mobile di una trasformazione, e un'impronta che cambia perché
#: qualcuno ha ruotato e riportato indietro un oggetto è di nuovo rumore.
DECIMALI_BBOX = 6


def impronta_strutturale(misure) -> str:
    """L'impronta STRUTTURALE di un modello, dalle sue misure. → `"struct:…"`.

    NIGHT-RES/R5 · decisione 17 di E.D. Sostituisce `impronta_sorgente` come
    impronta del bake, e la ragione è che quella era conservativa fino a non
    dire più niente: `mtime:<int>:size:<int>` è del FILE, quindi **ogni
    salvataggio del .blend rendeva stantie tutte le derivate**. In un file su
    cui si lavora tutto il giorno, a fine giornata il numero delle stantie è
    uguale al numero delle derivate — cioè l'informazione è zero.

    Questa distingue «ho salvato il file» da «ho toccato questo modello».
    Costa O(1) per oggetto: conteggi (`len`), otto vertici di bounding box, i
    nomi dei materiali. Non serializza niente.

    **NON è crittografica, e va scritto dove qualcuno potrebbe crederlo.** Due
    mesh diverse con lo stesso numero di vertici, facce, ingombro e materiali
    danno la stessa impronta: spostare un vertice *dentro* il bounding box non
    si vede. Il suo mestiere non è dimostrare l'identità — è **spegnere il
    rumore** perché il segnale che resta si possa leggere. Per l'identità c'è
    lo sha256 dei byte prodotti, che il verbale scrive già.

    `misure` è un dizionario e non un oggetto Blender di proposito: così i
    conti si provano fuori da Blender, e chi li raccoglie (`bpy`) è un'altra
    funzione, altrove.
    """
    misure = dict(misure or {})
    if not misure:
        #: nessuna misura ≠ misure a zero. Chi legge deve poter distinguere
        #: «non so» da «diverso», che è la stessa regola di `impronta_sorgente`.
        return ""
    pezzi = []
    for chiave in sorted(misure):
        valore = misure[chiave]
        if isinstance(valore, (list, tuple)):
            pezzi.append(f"{chiave}=" + ",".join(_numero(v) for v in valore))
        else:
            pezzi.append(f"{chiave}={_numero(valore)}")
    return PREFISSO_STRUTTURALE + ":".join(pezzi)


def _numero(valore) -> str:
    """Un valore in forma canonica: gli interi interi, i float arrotondati.

    Senza l'arrotondamento due export della stessa scena darebbero impronte
    diverse per l'ultima cifra di un float, e la staleness tornerebbe a essere
    rumore — per una ragione diversa ma con lo stesso effetto.
    """
    if isinstance(valore, bool) or isinstance(valore, int):
        return str(int(valore))
    if isinstance(valore, float):
        arrotondato = round(valore, DECIMALI_BBOX)
        #: `-0.0` e `0.0` sono lo stesso ingombro e devono scriversi uguale
        if arrotondato == 0:
            arrotondato = 0.0
        return f"{arrotondato:.{DECIMALI_BBOX}f}"
    return str(valore)


def impronta_insieme(imprints) -> str:
    """L'impronta di un INSIEME di sorgenti — il caso N:1 del tileset.

    Un tileset fa le veci di un container: accorpa N mesh in un'entità rigida,
    quindi è stantio se cambia **una qualunque** delle N. L'impronta è quella
    dell'insieme, ordinata perché l'ordine in cui l'export incontra i membri
    non è un fatto sul modello.

    Una sorgente che non si è saputa misurare (`""`) **non viene saltata**:
    entra come `?`. Saltarla darebbe la stessa impronta a un insieme di tre e a
    uno di tre di cui uno sconosciuto, cioè direbbe «uguale» su una differenza
    vera.
    """
    pezzi = sorted((i or "?") for i in (imprints or []))
    if not pezzi:
        return ""
    import hashlib
    digest = hashlib.sha256("|".join(pezzi).encode("utf-8")).hexdigest()[:16]
    return f"{PREFISSO_STRUTTURALE}set={len(pezzi)}:h={digest}"


def assicura_master(graph, *, master_id, url, name=None, link_to=None,
                    packaging=None, misure=None, source_id=None):
    """NIGHT-RES/R2 · il MASTER di una catena: lo crea, o lo allinea.

    Il master è ciò che si tiene perché è la fonte da cui si fanno le altre.
    Perderlo è perdere qualcosa: nessuno lo rifà.

    **Un master senza monte è legittimo** — un proxy nasce in Blender e non
    viene da nessuna parte — e va DICHIARATO tale invece di lasciargli una
    provenienza vuota che sembra un dato mancante. `source_id` esiste per la
    catena dell'RMDoc, dove il master spaziale (il quad con la sua camera) è a
    sua volta legato all'immagine da cui è fatto.

    **Non si usa il nodo US come master**: un nodo di conoscenza non ha byte, e
    metterlo da quella parte della derivazione direbbe che un'unità
    stratigrafica è un file.

    Torna `(ok, messaggio)`. Non solleva: come `registra_derivata`, un export
    non deve fallire perché un nodo non si è potuto scrivere, ma deve dirlo.
    """
    try:
        from s3dgraphy import api as _s3d_api
    except ImportError as e:
        # decisione 14: si cattura ciò che si sa gestire, e si dice cosa manca
        return False, f"s3dgraphy.api non disponibile ({e}): master non scritto"
    if not url:
        return False, f"{master_id}: nessun locator, master non scritto"
    #: un master `blend://` è un DATABLOCK: lo si dichiara, come fa la
    #: risorsa interna di `ensure_rm_and_internal_resource`
    if packaging is None and str(url).startswith("blend://"):
        packaging = "datablock"

    nodo = graph.find_node_by_id(master_id)
    if nodo is None:
        nodo = _s3d_api.add_resource(graph, resource_id=master_id,
                                     name=name or master_id, kind="3d_model",
                                     files=[{"url": url}])
    else:
        nodo.data["url"] = url
        if name:
            nodo.name = name
    #: il tier si DICHIARA anche su un nodo che esisteva già: era nato prima
    #: che l'asse esistesse, e lasciarlo muto costringerebbe ogni consumatore a
    #: dedurlo — che è esattamente ciò che questa notte toglie di mezzo
    if hasattr(nodo, "set_tier"):
        nodo.set_tier("master")
        nodo.set_residency("resident")
    else:                                   # pragma: no cover — modello vecchio
        nodo.data["tier"] = "master"
    if packaging and hasattr(nodo, "set_packaging"):
        nodo.set_packaging(packaging)
    if misure and hasattr(nodo, "set_measures"):
        nodo.set_measures(primitives={k: v for k, v in misure.items()
                                      if isinstance(v, int)})
    _arco(graph, link_to, master_id, "has_linked_resource")
    if source_id and graph.find_node_by_id(source_id) is not None:
        #: la derivazione fra due master (l'artefatto spaziale dell'RMDoc e
        #: l'immagine da cui prende la texture): un arco DTC, non una copia
        _arco(graph, master_id, source_id, "dtc_derived_from")
    return True, ""


def _arco(graph, sorgente, destinazione, tipo):
    """Un arco, una volta sola. Id derivato dai due estremi e dal tipo, come
    ogni altro id di queste notti: è ciò che rende il secondo export un
    no-op invece di un duplicato."""
    if not sorgente or not destinazione:
        return
    if graph.find_node_by_id(sorgente) is None:
        return
    edge_id = f"{sorgente}_{tipo}_{destinazione}"
    if graph.find_edge_by_id(edge_id) is None:
        graph.add_edge(edge_id=edge_id, edge_source=sorgente,
                       edge_target=destinazione, edge_type=tipo)


def archivio_servito(sorgente, cartella, nome):
    """L'archivio di un tileset come lo si serve: COPIATO, con la sua estensione.

    Un `.3tz` resta un `.3tz` (prima diventava `X.zip`: stessi byte, un nome che
    mente su cosa sono), uno zip resta uno zip. La copia si rifà quando manca
    o quando i byte della sorgente non sono più quelli copiati — la guardia di
    prima (`not isfile`) teneva la copia vecchia e la registrava col suo sha.
    → `(percorso, url, copiato)`.
    """
    import shutil
    estensione = os.path.splitext(sorgente)[1].lower() or ".zip"
    percorso = os.path.join(cartella, f"{nome}{estensione}")
    url = f"tilesets/{nome}{estensione}"
    copiato = False
    if not os.path.isfile(percorso) or (
            os.path.getsize(percorso) != os.path.getsize(sorgente)
            or sha256_del_file(percorso) != sha256_del_file(sorgente)):
        shutil.copy2(sorgente, percorso)
        copiato = True
    return percorso, url, copiato


def specifiche_del_file_set(url, file_esportato, membri):
    """I `files` di `api.add_resource` per un export di più file (glTF separato).

    La porta è il file esportato (`entry_point`, al suo `url`); ogni membro è
    un `{path, file}` relativo alla porta (`resource_digest.gltf_members`), con
    l'url costruito accanto a quello della porta. Ognuno porta il SUO digest e
    il suo peso: un membro che su disco non c'è non entra, e lo si dice.
    → `(specifiche, mancanti)`.
    """
    import posixpath
    cartella = posixpath.dirname(url)
    specifiche = [{"path": posixpath.basename(url), "url": url,
                   "checksum": sha256_del_file(file_esportato),
                   "size_bytes": os.path.getsize(file_esportato),
                   "role": "entry_point"}]
    mancanti = []
    for m in membri or []:
        if not os.path.isfile(m["file"]):
            mancanti.append(m["path"])
            continue
        specifiche.append({"path": m["path"],
                           "url": posixpath.join(cartella, m["path"]) if cartella else m["path"],
                           "checksum": sha256_del_file(m["file"]),
                           "size_bytes": os.path.getsize(m["file"]),
                           "role": "member"})
    return specifiche, mancanti


def _gli_stessi_file(graph, res_id, specifiche) -> bool:
    """La risorsa ha esattamente questi file (percorso, ruolo, digest)?"""
    from s3dgraphy import api as _s3d_api
    attuali = {(f["path"], f["role"], (f["node"].data or {}).get("checksum"))
               for f in _s3d_api.resource_files(graph, res_id) if not f["implicit"]}
    return attuali == {(f["path"], f["role"], f["checksum"]) for f in specifiche}


def _scrivi_i_file(graph, derivata_id, specifiche):
    """I file di una distribuzione `file_set`. → bool, se il nodo ora descrive
    QUESTI byte (e il suo digest è quindi la lista canonica di `specifiche`).

    * nodo nuovo: `api.add_resource(packaging="file_set", files=…)`;
    * nodo con gli stessi file: niente da fare;
    * nodo di un grafo di prima, registrato come un file solo (il `.gltf` col
      suo digest) e con la stessa porta: gli stessi byte descritti per intero,
      non una revisione — il primo `add_file` sposta url e digest della porta
      nel suo nodo (una volta sola), gli altri aggiungono i membri;
    * altrimenti i byte sono cambiati, e il nodo non si tocca qui (False).
    """
    from s3dgraphy import api as _s3d_api
    nodo = graph.find_node_by_id(derivata_id)
    if nodo is None:
        _s3d_api.add_resource(graph, resource_id=derivata_id, name=derivata_id,
                              kind="3d_model", packaging="file_set",
                              files=specifiche)
        return True
    if _gli_stessi_file(graph, derivata_id, specifiche):
        return True
    attuali = _s3d_api.resource_files(graph, derivata_id)
    if attuali and attuali[0]["implicit"] and \
            (nodo.data.get("checksum") or "") == specifiche[0]["checksum"]:
        for spec in specifiche[1:]:
            _s3d_api.add_file(graph, derivata_id, **spec)
        return True
    return False


def registra_derivata(graph, *, derivata_id, url, source_id=None,
                      source_ids=None, link_to=None, name=None,
                      file_esportato="", impronta_del_grezzo="",
                      packaging=None, misure=None, checksum_of=None,
                      membri=None, contenuto=None, peso_contenuto=None):
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

    `source_ids` è il caso **N a 1**: un tileset Cesium fa le veci di un RM
    container, accorpando N mesh in un'entità rigida, quindi la sua genesi ha N
    ingressi ed è stantio se cambia **una qualunque** delle N. Il DTC regge un
    processo con più ingressi nativamente; `source_id` resta la scorciatoia per
    il caso a una sorgente sola.

    `packaging` e `misure` sono i fatti dichiarati che rendono la distribuzione
    **scegliibile** (R1). Un tileset che viaggia come zip deve dire
    `packaging="archive"`: leggerlo dall'estensione funziona finché qualcuno non
    serve un archivio senza `.zip` nel nome, e allora fallisce in silenzio.

    `checksum_of` dice **su cosa** è stato preso il digest quando non copre
    tutto. Un albero servito non ha un digest solo — per averlo servirebbe
    percorrere migliaia di file, cioè precisamente il costo che impacchettare
    esiste per evitare — quindi si digerisce la sua PORTA (`tileset.json`) e
    lo si **dichiara**. Assente vuol dire «copre l'intera risorsa», che è il
    caso normale di un file e di un archivio. Un checksum parziale non
    dichiarato sarebbe un checksum che mente su cosa verifica.

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

    #: R1 · il peso è un fatto misurato, ed è metà di come un consumatore
    #: sceglie fra due distribuzioni ugualmente valide
    peso = None
    if file_esportato and os.path.isfile(file_esportato):
        peso = os.path.getsize(file_esportato)

    #: MICRO risorsa-file · un export di PIÙ file (glTF separato: `.gltf` +
    #: `.bin` + texture) è UNA risorsa `file_set`: i suoi file con i loro
    #: digest, e come digest della risorsa la lista canonica di dtcstamp. Prima
    #: era registrato come un file solo col digest del solo `.gltf`, cioè un
    #: checksum che non verificava i byte che contano di più.
    #:
    #: Il `url` della risorsa resta quello della porta: è dove Heriverse guarda
    #: (`canConsumeResource` legge `data.url`), e Heriverse non si tocca.
    from s3dgraphy import api as _s3d_api
    #: MICRO risorsa-file · SOSTITUIRE, NON SOVRASCRIVERE. Il verbale si
    #: scrive sulla revisione CORRENTE della distribuzione (`{rm}_link` è
    #: l'id della prima: le revisioni hanno un id derivato). Se i byte sono
    #: cambiati, si fa una revisione (`replace_file`); chi citava la vecchia
    #: non si sposta da solo — lo chiede il pannello (`resource_revisions`).
    bersaglio = derivata_id
    if graph.find_node_by_id(derivata_id) is not None:
        try:
            bersaglio = _s3d_api.current_revision(graph, derivata_id)
        except ValueError as e:
            return False, f"{derivata_id}: {e}"

    avvisi = []
    specifiche = None
    descritta = False
    if membri is not None:
        specifiche, mancanti = specifiche_del_file_set(url, file_esportato, membri)
        if mancanti:
            avvisi.append(f"{len(mancanti)} file nominati dal glTF non ci sono: "
                          f"{', '.join(mancanti[:5])}")
        descritta = _scrivi_i_file(graph, bersaglio, specifiche)
        digest = _resource_digest().members_digest(specifiche)
        peso = sum(int(f["size_bytes"]) for f in specifiche)
        packaging = "file_set"
        checksum_of = "members"

    #: MICRO risorsa-file, parte 3 · un ALBERO (un tileset, in cartella o in
    #: `.3tz`) si identifica col suo `content_digest` di dtcstamp: lo stesso per
    #: la cartella e per l'archivio. La forma `directory` ha COME digest il
    #: contenuto — prima era quello della sola porta, con `checksum_of:
    #: entry-point` a dirlo —; la forma `archive` ha lo sha256 del file, e il
    #: `content_digest` accanto.
    porta = digest
    if contenuto and packaging == "directory":
        digest = contenuto
        if peso_contenuto is not None:
            peso = peso_contenuto
        checksum_of = None

    revisione = None
    nodo = graph.find_node_by_id(bersaglio)
    if nodo is not None:
        dati = nodo.data or {}
        vecchio = str(dati.get("checksum") or "")
        if specifiche is not None:
            cambiato = not descritta
        elif dati.get("checksum_of") == "entry-point" and contenuto:
            #: un albero registrato ieri col digest della porta: se la porta è
            #: la stessa, sono gli stessi byte descritti meglio (non una
            #: revisione); il `checksum_of` di ieri non vale più
            cambiato = bool(vecchio) and vecchio != porta
            if not cambiato:
                dati.pop("checksum_of", None)
        else:
            cambiato = bool(vecchio) and vecchio != digest
        if cambiato:
            import posixpath
            _rr = _resource_revisions()
            revisione = _rr.revise_files(
                graph, bersaglio,
                specifiche or [{"path": posixpath.basename(url), "url": url,
                                #: un albero si descrive con la sua porta:
                                #: il file è `tileset.json`, il contenuto è
                                #: il digest della risorsa
                                "checksum": porta,
                                "size_bytes": (os.path.getsize(file_esportato)
                                               if contenuto else peso)}],
                force=bool(contenuto))
            if revisione["new_resource_id"]:
                bersaglio = revisione["new_resource_id"]
                citanti, _catena = _rr.split_pointers(revisione["pointing_at_old"])
                avvisi.append(
                    f"i byte sono cambiati: revisione {bersaglio} di "
                    f"{derivata_id}; "
                    f"{len(citanti)} citazioni restano sulla vecchia finché "
                    f"non le si sposta (Resources → Revisions)")

    try:
        promote_resource(
            graph, bersaglio,
            url=url, sha256=digest,
            source_id=source_id,
            source_ids=source_ids,
            #: una revisione NON si lega da sola a chi citava la vecchia: è
            #: la domanda che il pannello fa
            link_to=link_to if revisione is None or not revisione["new_resource_id"] else None,
            name=name,
            residency="resident",
            #: R1 · una derivata del bake è una DISTRIBUTION per definizione:
            #: è fatta perché qualcun altro la consumi, e si rifà premendo un
            #: bottone. «Pubblicata» sarà uno stato suo, non un terzo tier.
            tier="distribution",
            packaging=packaging,
            size_bytes=peso,
            primitives=({k: v for k, v in (misure or {}).items()
                         if isinstance(v, int)} or None),
        )
    except Exception as e:                          # noqa: BLE001
        return False, f"promote_resource ha rifiutato: {e}"

    #: l'impronta del grezzo AL MOMENTO DEL BAKE: è l'unico dato che rende
    #: «stantia» calcolabile invece che sospettabile (B4). Sta sulla
    #: derivata, perché è lei a ricordare da cosa è stata fatta e quando.
    nodo = graph.find_node_by_id(bersaglio)
    if nodo is not None and impronta_del_grezzo:
        nodo.data["source_fingerprint"] = impronta_del_grezzo
    if nodo is not None and checksum_of:
        nodo.data["checksum_of"] = str(checksum_of)
    if nodo is not None and contenuto:
        nodo.data["content_digest"] = str(contenuto)
    return True, "; ".join(avvisi)
