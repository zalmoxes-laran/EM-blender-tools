"""D6 · Lo stato del GRAFO rispetto alla stanza — mostrato, mai pubblicato.

Il grafo è ciò che dice **cosa un glb rappresenta**: senza di lui una derivata
pubblicata è un file orfano, byte con un indirizzo e nessun significato. Quindi
il deck lo mostra. Ma non lo pubblica: quel gesto è il push nella stanza e vive
altrove (`sync_manager`), e un secondo posto da cui spingere sarebbe un secondo
posto da cui sbagliare.

Riga in **sola lettura**, nessuna spunta, nessun verbo.

## DA DOVE VIENE LO STATO, e cosa NON si può sapere

Tutto da ciò che la sessione di sync **già sa** (`RoomSession`): nessuna
connessione nuova, nessun client di database. Gli stati:

* **nessuna stanza** — la sessione non è seduta in nessuna stanza;
* **senza rete** (`offline`) — seduta in una stanza, ma la connessione è
  caduta: le modifiche fatte qui aspettano (`RoomSession.waiting()`, le op che
  la stanza non ha ancora confermato) e ripartono al rientro. È il nome che le
  altre parti di EM Tools gli danno già (`RoomSession.offline`, `where.py`);
* **allineati** — dentro, e niente in attesa di essere applicato;
* **la stanza è avanti** — dentro, e nella casella di posta ci sono messaggi
  arrivati e non ancora applicati. È un fatto osservabile, non una stima.

**Il buio non è «nessuna stanza»** (misurato il 12 ott 2026, prova 8 del
tavolo): col proxy ucciso la sessione era `joined: false`, `seated: true`, 1
modifica in attesa, e questa riga diceva «this study is in no room». Chi la
legge va a cercare una stanza da cui è uscito, mentre è ancora dentro e deve
solo aspettare la rete. Le modifiche in attesa sono quello che, connessi, non
esiste: ogni mutazione parte nell'istante in cui avviene (`emit_op`), e «sei
avanti tu» si vede soltanto senza rete — è lì che lo si dice, con il numero.

Nessun `bpy`: la regola si prova senza Blender e senza un server acceso.
"""

from __future__ import annotations

#: Gli stati che si possono davvero distinguere. `unknown` non è un ripiego
#: educato: è il caso in cui la sessione c'è ma non ha detto abbastanza, e
#: dirlo è meglio che scegliere uno degli altri tre a caso.
STATI_GRAFO = ("no_room", "offline", "aligned", "room_ahead", "unknown")

#: L'icona per stato. Nessuna è `ERROR`: non essere in una stanza non è un
#: guasto, è una situazione — e la maggior parte degli studi ci vive dentro.
ICONE = {
    "no_room": "UNLINKED",
    #: non `UNLINKED`: quella è «nessuna stanza», e il buio non lo è
    "offline": "INTERNET_OFFLINE",
    "aligned": "LINKED",
    "room_ahead": "IMPORT",
    "unknown": "QUESTION",
}


def stato_della_stanza(*, dentro: bool, stanza=None, applicato=None,
                       in_attesa: int = 0, errore=None, seduti: bool = False,
                       da_confermare: int = 0) -> dict:
    """→ `{"stato", "frase"}`. Tutti i fatti sono INIETTATI.

    Args:
        dentro: la sessione è in una stanza (`RoomSession.joined`).
        stanza: l'id della stanza (`room_id`), quando lo si sa.
        applicato: fin dove questo client ha applicato (`last_applied`) — è il
            solo marcatore monotono che il filo porta. Non c'è un numero di
            revisione sul filo, quindi si mostra quello che c'è e si chiama
            con il suo nome.
        in_attesa: quanti messaggi sono arrivati e non sono ancora stati
            applicati (`inbox.qsize()`). Più di zero **è** «la stanza è
            avanti», osservato e non stimato.
        errore: l'ultimo errore che la stanza ha mandato, se c'è.
        seduti: la sessione ha una stanza anche se la connessione è caduta
            (`RoomSession.seated`). Seduti e non dentro è **senza rete**.
        da_confermare: le modifiche fatte qui che la stanza non ha ancora
            confermato (`RoomSession.waiting()`): senza rete, aspettano.

    Le frasi sono in inglese perché finiscono a video.
    """
    if errore:
        #: un errore della stanza non è «non sei in una stanza»: sono due cose
        #: diverse con due cure diverse, e appiattirle è il difetto che
        #: NIGHT-SYNC è servita a togliere
        return {"stato": "unknown", "frase": f"the room said: {errore}"}
    nome = str(stanza or "").strip()
    dove = f"in room {nome}" if nome else "in a room"
    if not dentro and seduti:
        n = int(da_confermare or 0)
        attesa = (f"{n} edit{'s' if n != 1 else ''} waiting" if n
                  else "nothing waiting")
        return {"stato": "offline", "frase": f"{dove}, no network — {attesa}"}
    if not dentro:
        return {"stato": "no_room",
                "frase": "this study is in no room"}
    if in_attesa:
        return {"stato": "room_ahead",
                "frase": f"{dove}: {in_attesa} changes not applied yet"}
    if applicato:
        return {"stato": "aligned",
                "frase": f"{dove}, up to {str(applicato)[:19]}"}
    #: dentro, niente in attesa e niente applicato = si è appena arrivati e si
    #: sta allo snapshot. È allineato, e dirlo così invece di «up to None»
    #: è la differenza fra un'informazione e un campo vuoto
    return {"stato": "aligned", "frase": f"{dove}, at the snapshot"}


def dalla_sessione(sessione) -> dict:
    """Lo stesso, leggendo una `RoomSession`. → `{"stato", "frase"}`.

    Un adattatore, e sta qui perché la regola sopra non debba
    conoscere la forma di quell'oggetto: il giorno che la sessione impara a
    dire una revisione vera, cambia questa funzione e non l'altra.

    Una sessione assente non è un errore: è lo stato «nessuna stanza».
    Seduta senza rete si legge da `offline` (o, se la sessione non lo dice,
    da `seated` e non `joined`), le modifiche in attesa da `waiting()`.
    """
    if sessione is None:
        return stato_della_stanza(dentro=False)
    coda = getattr(sessione, "inbox", None)
    try:
        in_attesa = coda.qsize() if coda is not None else 0
    except (AttributeError, NotImplementedError):
        #: `qsize` non è garantita su tutte le piattaforme: non saperlo è
        #: «non lo so», non «zero»
        in_attesa = 0
    dentro = bool(getattr(sessione, "joined", False))
    seduti = getattr(sessione, "offline", None)
    if seduti is None:
        seduti = bool(getattr(sessione, "seated", False)) and not dentro
    attese = getattr(sessione, "waiting", None)
    try:
        da_confermare = attese() if callable(attese) else int(attese or 0)
    except (TypeError, ValueError):
        da_confermare = 0
    return stato_della_stanza(
        dentro=dentro, seduti=bool(seduti), da_confermare=int(da_confermare or 0),
        stanza=getattr(sessione, "room_id", None),
        applicato=getattr(sessione, "last_applied", None),
        in_attesa=int(in_attesa or 0),
        errore=getattr(sessione, "error", None))
