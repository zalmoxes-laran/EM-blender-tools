"""R3 · Come un container si pubblica: membri singoli, oppure un tileset unico.

**Non è un concetto nuovo.** E.D. quel gesto lo fa già: aggiunge il tileset in
scena e rende *non pubblicabile* la mesh equivalente, una per una. Oggi è un
flag per oggetto ripetuto N volte, con tutto ciò che ne segue — si dimentica
una riga e il viewer riceve il doppione.

Qui diventa una **proprietà del container**, detta una volta sola:

* `members` — ogni membro produce la sua distribuzione. È il comportamento
  storico ed è il default;
* `tileset` — il container viaggia come **un** tileset, e i membri **non**
  producono distribuzioni proprie.

**Sono alternative, non cumulabili**, perché il tileset SOSTITUISCE i singoli:
è la regola che evita il doppione al viewer, ed è l'unica ragione per cui
questa proprietà vale più di N flag.

**Non si deduce.** È una scelta di chi lavora, e dipende da quanto pesa il
rilievo e da come lo vuole servire: un container di tre muri si serve benissimo
a pezzi, uno di quattromila tile no. Nessuna euristica sul numero dei membri —
sarebbe una decisione presa al posto di qualcuno, e sbagliata la prima volta
che un rilievo piccolo va servito come tileset per ragioni di pipeline.

**Retro-compatibilità, e nel verso giusto**: un container che non dichiara
niente continua a rispettare i flag `is_publishable` per oggetto, che **non
vengono riscritti**. Migrare quei flag in una strategia vorrebbe dire
interpretare la volontà di qualcuno e poi cancellarne la prova.

Nessun `bpy` qui: la regola si prova fuori da Blender, e chi la applica (il
lato Blender) legge la property e chiama queste funzioni.
"""

from __future__ import annotations

#: Le due strategie. Una coppia, come `tier`: se un terzo caso si presenta si
#: dichiara, non si infila a un call site.
STRATEGIE = ("members", "tileset")

#: Quella che vale quanto il comportamento di prima di questa proprietà.
STRATEGIA_PREDEFINITA = "members"


def normalizza(dichiarata) -> str:
    """La strategia da USARE. Una parola sconosciuta vale il default.

    Non solleva, al contrario dei setter di s3Dgraphy, e la differenza è
    voluta: là si sta scrivendo nel documento (una parola inventata diventa un
    dato che nessun filtro incontrerà mai), qui si sta leggendo una property di
    scena per decidere cosa esportare. Fermare un export per una parola storta
    farebbe perdere il lavoro di qualcuno; ripiegare sul comportamento storico
    no.
    """
    testo = str(dichiarata or "").strip().lower()
    return testo if testo in STRATEGIE else STRATEGIA_PREDEFINITA


def membri_pubblicabili(strategia, membri, flag_per_oggetto) -> list:
    """Quali membri di un container producono una distribuzione.

    Args:
        strategia: quella dichiarata sul container.
        membri: i nomi degli oggetti membri, nell'ordine del container.
        flag_per_oggetto: mappa nome → `is_publishable`, come sta oggi in
            `scene.rm_list`. Un nome assente vale **pubblicabile**: è il default
            della property, e assumere il contrario nasconderebbe un oggetto
            che nessuno ha escluso.

    Con `tileset` la risposta è la lista vuota, e non perché i membri siano
    stati esclusi uno per uno: è il tileset a stare al loro posto. I flag per
    oggetto restano scritti dove sono e tornano a contare il giorno che la
    strategia torna a `members` — nessuno li ha riscritti.
    """
    if normalizza(strategia) == "tileset":
        return []
    flag = dict(flag_per_oggetto or {})
    return [nome for nome in (membri or []) if flag.get(nome, True)]


def il_tileset_sostituisce(strategia) -> bool:
    """Il container viaggia come una cosa sola?"""
    return normalizza(strategia) == "tileset"


def sorgenti_del_tileset(membri, master_per_membro) -> list:
    """Gli id dei master che un tileset di container accorpa — la derivazione N:1.

    Un tileset Cesium **fa le veci di un RM container**: accorpa in un'entità
    rigida un insieme di tile che singolarmente sono mesh editabili. Quindi la
    sorgente non è un singolo RM, è **l'insieme**, e il DTC regge nativamente un
    processo con più ingressi.

    Un membro di cui non si conosce il master **non entra e non viene finto**:
    un ingresso inventato renderebbe la genesi una bugia, e la staleness un
    conto su una sorgente che non c'è. L'ordine è quello del container,
    de-duplicato, perché l'ordine in cui l'export incontra i membri non è un
    fatto sul modello.
    """
    mappa = dict(master_per_membro or {})
    fuori = []
    for nome in (membri or []):
        master = str(mappa.get(nome) or "").strip()
        if master and master not in fuori:
            fuori.append(master)
    return fuori
