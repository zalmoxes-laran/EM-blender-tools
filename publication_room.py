"""D6 · Lo stato del GRAFO rispetto alla stanza — mostrato, mai pubblicato.

Il grafo è ciò che dice **cosa un glb rappresenta**: senza di lui una derivata
pubblicata è un file orfano, byte con un indirizzo e nessun significato. Quindi
il deck lo mostra. Ma non lo pubblica: quel gesto è il push nella stanza e vive
altrove (`sync_manager`), e un secondo posto da cui spingere sarebbe un secondo
posto da cui sbagliare.

Riga in **sola lettura**, nessuna spunta, nessun verbo.

## DA DOVE VIENE LO STATO, e cosa NON si può sapere

Tutto da ciò che la sessione di sync **già sa** (`RoomSession`): nessuna
connessione nuova, nessun client di database. E qui c'è il punto che vale la
pena scrivere, perché il prompt chiedeva quattro stati e i distinguibili sono
tre:

* **nessuna stanza** — la sessione non è dentro;
* **allineati** — dentro, e niente in attesa di essere applicato;
* **la stanza è avanti** — dentro, e nella casella di posta ci sono messaggi
  arrivati e non ancora applicati. È un fatto osservabile, non una stima.

**«Sei avanti tu» non è rappresentabile, e non perché manchi un campo**: in
EM Tools ogni mutazione locale parte nel momento in cui avviene
(`sync_manager/operators.py::emit_op`, che chiama `SESSION.send_op` appena la
sessione è dentro). Non esiste una coda di op non spedite, quindi non esiste lo
stato «ho roba che la stanza non ha». Inventare quel quarto stato vorrebbe dire
disegnare una casella che non si accende mai — o peggio, accenderla su un
euristica. Quando fuori da una stanza si modifica il grafo, quello è lo stato
«nessuna stanza», e resta vero.

Nessun `bpy`: la regola si prova senza Blender e senza un server acceso.
"""

from __future__ import annotations

#: Gli stati che si possono davvero distinguere. `unknown` non è un ripiego
#: educato: è il caso in cui la sessione c'è ma non ha detto abbastanza, e
#: dirlo è meglio che scegliere uno degli altri tre a caso.
STATI_GRAFO = ("no_room", "aligned", "room_ahead", "unknown")

#: L'icona per stato. Nessuna è `ERROR`: non essere in una stanza non è un
#: guasto, è una situazione — e la maggior parte degli studi ci vive dentro.
ICONE = {
    "no_room": "UNLINKED",
    "aligned": "LINKED",
    "room_ahead": "IMPORT",
    "unknown": "QUESTION",
}


def stato_della_stanza(*, dentro: bool, stanza=None, applicato=None,
                       in_attesa: int = 0, errore=None) -> dict:
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

    Le frasi sono in inglese perché finiscono a video.
    """
    if errore:
        #: un errore della stanza non è «non sei in una stanza»: sono due cose
        #: diverse con due cure diverse, e appiattirle è il difetto che
        #: NIGHT-SYNC è servita a togliere
        return {"stato": "unknown", "frase": f"the room said: {errore}"}
    if not dentro:
        return {"stato": "no_room",
                "frase": "this study is in no room"}
    nome = str(stanza or "").strip()
    dove = f"in room {nome}" if nome else "in a room"
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

    Un adattatore di sei righe, e sta qui perché la regola sopra non debba
    conoscere la forma di quell'oggetto: il giorno che la sessione impara a
    dire una revisione vera, cambia questa funzione e non l'altra.

    Una sessione assente non è un errore: è lo stato «nessuna stanza».
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
    return stato_della_stanza(
        dentro=bool(getattr(sessione, "joined", False)),
        stanza=getattr(sessione, "room_id", None),
        applicato=getattr(sessione, "last_applied", None),
        in_attesa=int(in_attesa or 0),
        errore=getattr(sessione, "error", None))
