"""P4 · «Pronto per chi» — le destinazioni, e le loro capacità dichiarate.

«Pubblicabile» non lo decide Blender: lo decide il **consumatore**. Il grafo
dichiara fatti (formato, `tier`, `packaging`, peso); ogni destinazione dichiara
cosa sa aprire; il deck mette le due cose una accanto all'altra.

**LA SPARTIZIONE, che è la parte che conta.** Qui NON si riscrive la regola di
nessuno:

* cosa una risorsa **richiede** è una proprietà della risorsa, e la decide
  questo modulo (un `.zip` richiede di saper scompattare, un `tileset.json`
  richiede 3D Tiles);
* cosa una destinazione **possiede** è una proprietà sua, e la dichiara lei —
  Heriverse in `src/Heriverse.js`, `Heriverse.CAPABILITIES`.

Il giudizio è l'incontro fra le due. Ricopiare qui le capacità di Heriverse
darebbe due fonti per lo stesso fatto, destinate a divergere alla prima riga
cambiata di là: è la stessa ragione per cui `rm_links` è stata cancellata.

**E SE NON SI RIESCE A LEGGERE?** Si dice `unknown` **con la ragione e con il
posto dove guardare** — la lezione di T3, applicata un livello più su.
Dichiarare `no` per una capacità che non si è potuta interrogare sarebbe la
stessa bugia piccola, spostata.

**N DESTINAZIONI DALL'INIZIO.** Heriverse è la prima e la stanza StratiGraph è
già la seconda. Una struttura fatta per una sola destinazione è il genere di
cosa che non si rifattorizza più.
"""

from __future__ import annotations

import os
import re

#: I tre stati di una capacità — gli stessi nomi che Heriverse usa
#: (`Heriverse.CAPABILITY`), perché un vocabolario che cambia attraversando un
#: confine è un vocabolario che si traduce male.
YES, NO, UNKNOWN = "yes", "no", "unknown"

#: **Il quarto verdetto, che non è una capacità.** `yes`/`no`/`unknown` dicono
#: cosa una destinazione SA fare; `n/a` dice che la domanda non si pone — un
#: pdf verso un viewer di modelli non è «non pronto», è fuori dal discorso.
#: Serve un nome suo perché `no` in quella colonna sembra un lavoro da fare, e
#: diciannove documenti marcati «no» manderebbero qualcuno a cercare un guasto
#: che non c'è.
NA = "n/a"

#: Dove cercare il checkout di Heriverse, relativo a questo add-on. Un elenco e
#: non un percorso: chi tiene i repo affiancati (la disposizione di casa) lo
#: trova al primo tentativo, e chi non ce l'ha ottiene `unknown` con la ragione.
POSTI_DI_HERIVERSE = (
    os.path.join("..", "Heriverse"),
    os.path.join("..", "heriverse"),
)


def _tipi_consumati(testo: str) -> list:
    """Quali `url_type` la destinazione accetta, letti dal suo GUARDIANO.

    **D5 · il difetto che questa funzione esiste per chiudere.** Il giudizio
    qui rispondeva `ready = yes` a ogni pdf di un progetto, perché un pdf non
    chiede nessuna capacità nota e la regola di chiusura dice che un locator
    sconosciuto è un endpoint. Ma la prima riga di `canConsumeResource`, di là,
    è

        if (data.url_type !== "3d_model") return {ok:false, why:"not a 3d model"}

    e quella riga non era stata letta. Cioè esattamente la malattia contro cui
    il commento in testa a questo modulo mette in guardia — due fonti per un
    fatto solo — comparsa una notte dopo averla scritta. Il rimedio non è
    ricopiare «3d_model» qui: è **leggere anche il guardiano**.

    → la lista dei tipi accettati, o `[]` quando la forma non si riconosce (e
    allora non si filtra niente, invece di dedurre un elenco sbagliato).
    """
    import re as _re
    return [m for m in _re.findall(
        r"""data\.url_type\s*!==\s*["']([^"']+)["']""", testo)]


def _estensione(url: str) -> str:
    coda = str(url or "").split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    return coda.rsplit(".", 1)[-1].lower() if "." in coda else ""


def capacita_richieste(dati: dict) -> list:
    """Cosa questa risorsa CHIEDE a chi la vuole aprire. → lista di nomi.

    È una proprietà della risorsa, non della destinazione, ed è per questo che
    sta qui: un archivio richiede di saper scompattare **chiunque** lo debba
    aprire, e quel fatto non cambia con il consumatore.
    """
    dati = dict(dati or {})
    url = str(dati.get("url") or "")
    richieste = []
    packaging = str(dati.get("packaging") or "")
    if packaging == "archive" or _estensione(url) == "zip":
        richieste.append("unpackArchive")
    if url.lower().split("?")[0].endswith("tileset.json"):
        richieste.append("tiles3d")
    elif _estensione(url) in ("gltf", "glb"):
        richieste.append("gltf")
    return richieste


def leggi_capacita_heriverse(radice=None) -> dict:
    """Le capacità DICHIARATE da Heriverse, lette dal suo sorgente.

    → `{"capacita": {nome: stato}, "da": <percorso>, "perche": ""}` oppure
    `{"capacita": {}, "da": "", "perche": "<frase>"}`.

    **Si LEGGE, non si ricopia.** La fonte resta `Heriverse.CAPABILITIES`; qui
    c'è solo il modo di arrivarci. La lettura è una regex su un letterale
    delimitato, quindi è fragile — e il modo in cui è fragile è quello giusto:
    se la forma cambia, questa funzione non trova niente e il deck dice
    `unknown` con la ragione, invece di dedurre un valore sbagliato.

    Accetta i tre stati e anche i booleani di prima, come fa
    `Heriverse.capabilityState`.
    """
    qui = os.path.dirname(os.path.abspath(__file__))
    candidati = [radice] if radice else [os.path.join(qui, p)
                                         for p in POSTI_DI_HERIVERSE]
    for base in candidati:
        if not base:
            continue
        sorgente = os.path.join(base, "src", "Heriverse.js")
        if not os.path.isfile(sorgente):
            continue
        try:
            with open(sorgente, "r", encoding="utf-8") as f:
                testo = f.read()
        except OSError as exc:
            return {"capacita": {}, "tipi": [], "da": "",
                    "perche": f"Heriverse.js found but unreadable ({exc})"}
        blocco = re.search(r"Heriverse\.CAPABILITIES\s*=\s*\{(.*?)\n\};",
                           testo, re.S)
        if not blocco:
            return {"capacita": {}, "tipi": [], "da": sorgente,
                    "perche": ("Heriverse.js does not declare CAPABILITIES in "
                               "the shape this reader knows — look at "
                               "Heriverse.CAPABILITIES")}
        capacita = {}
        for nome, valore in re.findall(
                r"^\s*(\w+)\s*:\s*([^,\n]+),?\s*$", blocco.group(1), re.M):
            v = valore.strip()
            if v.endswith("CAPABILITY.YES") or v == "true":
                capacita[nome] = YES
            elif v.endswith("CAPABILITY.NO") or v == "false":
                capacita[nome] = NO
            else:
                capacita[nome] = UNKNOWN
        if not capacita:
            return {"capacita": {}, "tipi": [], "da": sorgente,
                    "perche": "CAPABILITIES is declared but empty"}
        return {"capacita": capacita, "tipi": _tipi_consumati(testo),
                "da": sorgente, "perche": ""}
    return {"capacita": {}, "tipi": [], "da": "",
            "perche": ("no Heriverse checkout beside this add-on — "
                       "its capabilities are declared in "
                       "Heriverse/src/Heriverse.js")}


class _ComeNodo:
    """Un guscio con `.data`, perché `publication_gesture._tier` legge un NODO
    e qui si ha un dizionario. Un guscio e non una copia della regola: il tier
    si legge in un posto solo."""

    def __init__(self, dati):
        self.data = dict(dati or {})


def _come_nodo(dati):
    return _ComeNodo(dati)


def giudice(capacita: dict, mancante: str = "", tipi=None) -> callable:
    """Un giudice per una destinazione, dalle sue capacità. → `(dati) -> {ok, why}`.

    `mancante` è la ragione per cui le capacità non si sono potute leggere: se
    c'è, ogni risposta è un `unknown` che la riporta. Un giudice senza
    informazioni non dice `no`: dice che non sa, e dove guardare.

    `tipi` sono gli `url_type` che la destinazione accetta, letti dal suo
    guardiano (`_tipi_consumati`). Una lista vuota vuol dire «non dichiarato»
    e **non filtra**: dedurre un elenco da un guardiano che non si è
    riconosciuto sarebbe peggio del difetto che questo parametro chiude.
    """
    capacita = dict(capacita or {})
    tipi = [str(t) for t in (tipi or [])]

    def giudica(dati):
        # D5 · LA PORTA D'INGRESSO, che qui mancava. Un pdf non chiede nessuna
        # capacità nota, quindi la regola di chiusura lo faceva passare per un
        # endpoint e la colonna diceva `ready = yes` a diciannove documenti —
        # mentendo esattamente dove doveva aiutare. La destinazione dichiara
        # cosa consuma; ciò che sta fuori da quell'elenco non è «non pronto»,
        # è fuori dal discorso, e il verdetto ha un nome suo.
        tipo = str(dict(dati or {}).get("url_type") or "")
        if tipi and tipo not in tipi:
            comodo = tipi[0].replace("_", " ") + "s"
            return {"ok": False, "state": NA,
                    "why": f"this destination only takes {comodo}"}
        # UN MASTER NON È PRONTO PER NESSUNO, e non è un difetto suo: è ciò da
        # cui le distribution vengono fatte. Sta qui e non in
        # `capacita_richieste` perché è una proprietà del TIER e non del
        # formato: un master `.obj` su un disco esterno non è servibile per la
        # stessa ragione per cui non lo è un `blend://`, e quella ragione non
        # è l'estensione.
        #
        # Misurato: senza questa riga un `blend://` risultava «ready=yes»,
        # perché non chiede nessuna capacità nota e la regola di chiusura dice
        # che un locator sconosciuto è un endpoint. Giusto per un endpoint,
        # falso per una fonte.
        from . import publication_gesture
        if publication_gesture._tier(_come_nodo(dati)) == "master":
            return {"ok": False, "state": NO,
                    "why": "a master is not served — its distribution is"}
        richieste = capacita_richieste(dati)
        if not richieste:
            #: nessuna capacità speciale richiesta: un locator che non è né un
            #: archivio né un formato noto è un endpoint, e rifiutarlo
            #: renderebbe questa funzione un elenco chiuso di nomi di file
            return {"ok": True, "why": ""}
        if mancante:
            return {"ok": False, "state": UNKNOWN,
                    "why": f"cannot tell — {mancante}"}
        for nome in richieste:
            stato = capacita.get(nome, UNKNOWN)
            if stato == YES:
                continue
            if stato == NO:
                return {"ok": False, "state": NO,
                        "why": f"this destination declares it cannot handle "
                               f"«{nome}»"}
            return {"ok": False, "state": UNKNOWN,
                    "why": f"«{nome}» is declared unknown by this destination "
                           f"— it has not been verified, not refused"}
        return {"ok": True, "why": ""}

    return giudica


def destinazioni(radice_heriverse=None) -> dict:
    """Il registro: `{nome: {"giudice", "da", "perche"}}`.

    Un dizionario **dall'inizio**, con dentro una destinazione sola e la
    seconda già nominata. La stanza StratiGraph non ha ancora una
    dichiarazione di capacità da leggere — e quindi compare come `unknown` con
    la sua ragione, che è esattamente il comportamento che si vuole quando una
    destinazione non ha ancora detto cosa sa fare.
    """
    heri = leggi_capacita_heriverse(radice_heriverse)
    return {
        "heriverse": {
            "giudice": giudice(heri["capacita"], heri["perche"],
                               heri.get("tipi")),
            "da": heri["da"],
            "perche": heri["perche"],
            "capacita": heri["capacita"],
            "tipi": heri.get("tipi") or [],
        },
        "room": {
            "giudice": giudice({}, "the StratiGraph room does not declare its "
                                   "capabilities yet"),
            "da": "",
            "perche": "the StratiGraph room does not declare its capabilities yet",
            "capacita": {},
            #: la stanza non dichiara nemmeno CHE COSA consuma: nessun filtro,
            #: e la ragione la porta già `mancante`
            "tipi": [],
        },
    }
