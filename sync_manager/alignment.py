"""C1 · I due capi si dicono QUALE DOCUMENTO hanno aperto, e il confronto.

Il difetto che questo modulo esiste per chiudere non è un bug del gestore in
ingresso — quello funziona, misurato il 12-09-2026 in sidecar vero. È che
**quando i due capi non guardano lo stesso documento il risultato è lo stesso
silenzio** di un canale chiuso o di un grafo non in memoria: tre cause
diversissime, un solo sintomo.

Tre regole, e sono tutte e tre sul *non sapere*:

* **L'identità è l'id del grafo, non il nome del file.** Due persone possono
  avere lo stesso `TempluMare.em.json` su due dischi e non essere sullo stesso
  documento; lo stesso grafo può arrivare da un socket e non avere nessun file.
  Il nome resta, ma come ETICHETTA da mostrare, mai come confronto.
* **Non sapere non è un allarme.** Un capo che non dichiara niente — una EM
  Studio di prima di stanotte, un Blender senza grafo caricato — non è
  «disallineato»: è muto. Dirgli che sta guardando altrove sarebbe inventare un
  fatto, e insegnerebbe a ignorare l'avviso.
* **Non è un errore.** Lavorare su documenti diversi con il canale aperto è
  legittimo (uno modella, l'altra scrive la narrazione). Non saperlo no.

Nessun `bpy` qui: si prova senza Blender, e le due frasi che l'utente legge
sono un valore di ritorno invece che una stringa costruita dentro un `draw`.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

#: Cosa dichiara ciascun capo, con le chiavi che viaggiano sul filo. Una
#: costante e non una stringa ripetuta: le due parti la devono scrivere uguale,
#: e un refuso qui è un disallineamento che non si vede.
CHIAVE_ID = "graph_id"
CHIAVE_NOME = "graph_name"
#: …e tutti gli id caricati, perché Blender è multigrafo: il capo che ha
#: l'altro documento APERTO IN UNA SCHEDA non è nella stessa situazione di chi
#: non ce l'ha affatto, e la cura è diversa (cambia scheda / apri il file).
CHIAVE_TUTTI = "graph_ids"


def _testo(valore: Any) -> str:
    return str(valore or "").strip()


def etichetta(ident: str, nome: str = "") -> str:
    """Come si nomina un documento a chi legge: il nome se c'è, l'id sennò.

    L'id è ciò che si CONFRONTA, il nome è ciò che si LEGGE — e un uuid in un
    avviso è un avviso che non aiuta nessuno.
    """
    nome, ident = _testo(nome), _testo(ident)
    if nome and ident and nome != ident:
        return f"{nome} ({ident[:8]})"
    return nome or ident


def confronta(mio: Optional[Dict[str, Any]],
              suo: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """I due descrittori a confronto. → dict, mai un'eccezione.

    ``{'noto': bool, 'allineati': bool, 'anche_aperto': bool, 'frase': str,
       'mio': str, 'suo': str}``

    * ``noto`` — entrambi hanno dichiarato un id. Se è falso non si conclude
      niente: ``allineati`` resta ``True`` perché l'assenza di prova non è
      prova del contrario, e ``frase`` è vuota.
    * ``anche_aperto`` — il suo documento è fra quelli che ho caricati io. Non
      siamo allineati, ma la cura è una scheda da cambiare e non un file da
      trovare, e vale la pena dirlo.
    """
    mio, suo = dict(mio or {}), dict(suo or {})
    mio_id, suo_id = _testo(mio.get(CHIAVE_ID)), _testo(suo.get(CHIAVE_ID))
    mia, sua = (etichetta(mio_id, _testo(mio.get(CHIAVE_NOME))),
                etichetta(suo_id, _testo(suo.get(CHIAVE_NOME))))
    esito: Dict[str, Any] = {"noto": bool(mio_id and suo_id), "allineati": True,
                             "anche_aperto": False, "frase": "",
                             "mio": mia, "suo": sua}
    if not esito["noto"] or mio_id == suo_id:
        return esito
    esito["allineati"] = False
    tutti = mio.get(CHIAVE_TUTTI)
    esito["anche_aperto"] = bool(
        isinstance(tutti, (list, tuple)) and suo_id in [_testo(x) for x in tutti])
    # La frase è nella forma che il prompt chiede — «tu hai aperto X, io Y» —
    # e il «tu» è sempre l'altro capo, perché la frase la costruisce ognuno
    # per sé e la legge chi la costruisce.
    esito["frase"] = f"you have {sua} open, I have {mia}"
    if esito["anche_aperto"]:
        esito["frase"] += " — and I have theirs loaded too: switch to it"
    return esito
