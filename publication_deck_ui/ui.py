"""Il pannello del Publication Deck (tab EM Bridge).

Il tab dei ponti verso l'esterno, e il deck è il posto che guarda la soglia.
`bl_order = 0`: sta **prima** dell'Export Manager perché risponde alla domanda
che viene prima di esportare — cosa manca — e chi apre questo tab con un dubbio
in testa ha quel dubbio, non un bottone da premere.

**IL `draw` NON CALCOLA NIENTE.** Disegna la cache
(`scene.em_publication_deck`), riempita da `em.deck_refresh`. È l'unica regola
architetturale di questo file, e viene da una misura: `stato_risorse` costa un
`os.stat` per derivata e un pannello si ridisegna a ogni movimento del mouse.

**D1-D3 · UIList PIÙ SCHEDA**, che è la forma che Blender usa per gli elenchi
lunghi e che il RM Manager già usa in casa. Il box-per-risorsa di prima, su un
progetto vero, faceva diciannove box da quindici righe l'uno: quasi trecento
righe di pannello per dire quattro cose, e la lista dei nomi non si vedeva mai
tutta. Adesso:

* la **riga** è un asset e sta su UNA riga — icona del media, glifo dello
  stato, nome (l'elemento elastico), e la spunta all'estremo destro. Niente
  frasi: le frasi stanno nella scheda;
* la **scheda** è sotto e riguarda la riga attiva: i fatti, le distribuzioni,
  e i verbi che riguardano quel singolo asset.

Convenzioni di casa, già decise e qui rispettate:

* celle su **due righe** che non si troncano — il valore sotto l'etichetta,
  come il Graph Info, invece di una riga sola che a pannello stretto diventa
  `mod…`;
* righe di bottoni icona che **riempiono la larghezza**
  (`grid_flow(even_columns=True)`, mai `ui_units_x`): misurato in EM16-UX2 che
  in una `row` piatta i bottoni solo-icona NON si allargano;
* **tooltip come etichetta** dove il bottone è solo icona;
* **niente rosso** per ciò che non è un errore: in Blender `alert` è l'errore,
  e consumarlo per uno stantio insegnerebbe a non leggere il rosso;
* interfaccia in **inglese**, tooltip compresi.
"""

from __future__ import annotations

import bpy  # type: ignore

#: Icona per stato. Nessuna di queste è `ERROR`: uno stantio non è un errore,
#: è un lavoro da rifare.
_ICONA_STATO = {
    "published": "CHECKMARK",
    "baked": "FILE_TICK",
    "stale": "TEMP",            # un orologio: è una questione di TEMPO
    "master": "LOCKED",         # non si pubblica: si conserva
    "unresolved": "QUESTION",
    "orphan": "UNLINKED",
}

#: Cosa vuol dire ogni stato, in una frase. Sta nella SCHEDA, sotto il nome,
#: perché la parola da sola è un gergo che si impara una volta e si dimentica.
#: MISURATE a video e accorciate: a 280 unità di UI — la larghezza normale
#: della sidebar — Blender tronca a metà parola e la frase esce come
#: «made, but its locat…ething on this disk». Una spiegazione troncata è
#: peggio di nessuna spiegazione: sembra un guasto.
_SPIEGA_STATO = {
    "published": "reachable outside, with a checksum",
    "baked": "made, but local to this disk",
    "stale": "its source changed after the bake",
    "master": "a source: archived, never published",
    "unresolved": "it does not know where its bytes are",
    "orphan": "nothing points at it",
}

#: **D2 · l'icona del tipo di media, il primo colpo d'occhio della riga.**
#: Prima ancora dello stato, perché «di che cosa stiamo parlando» viene prima
#: di «a che punto è» — ed è la distinzione che su un progetto di soli
#: documenti si vede a colpo d'occhio senza leggere una parola.
_ICONA_MEDIA = {
    "mesh": "MESH_DATA",
    "tileset": "MESH_GRID",
    "pointcloud": "OUTLINER_OB_POINTCLOUD",
    "image": "IMAGE_DATA",
    "document": "FILE_TEXT",
    "other": "DOT",
}

#: D6 · lo stato del grafo rispetto alla stanza. Nessuna è `ERROR`: non essere
#: in una stanza non è un guasto, è la situazione in cui vive la maggior parte
#: degli studi.
_ICONA_GRAFO = {"no_room": "UNLINKED", "aligned": "LINKED",
                "room_ahead": "IMPORT", "unknown": "QUESTION"}

_ICONA_PRONTO = {"yes": "CHECKMARK", "no": "CANCEL", "unknown": "QUESTION",
                 #: `n/a` non è un rifiuto: la domanda non si pone, e un'icona
                 #: di rifiuto manderebbe qualcuno a cercare un guasto. Ma
                 #: nemmeno `BLANK1`: a video quella riga usciva rientrata e
                 #: senza glifo, e sembrava la continuazione della frase sopra
                 #: invece di un'annotazione sua. `HIDE_ON` è un occhio chiuso:
                 #: questo lettore non guarda questa roba, e non c'è niente da
                 #: aggiustare.
                 "n/a": "HIDE_ON"}


#: **Quanti caratteri entrano, per unità di interfaccia.** Due misure prese a
#: video in questa istanza, e la seconda ha corretto la prima: a **280 unità**
#: (la larghezza normale della sidebar) entrano ~38 caratteri; a **149 unità**
#: — la più stretta che si ottiene spezzando l'area 3D, che è la ricetta di
#: EM16-UX2 — ne entrano ~14. Il primo giro ne aveva stimati 17 e a video le
#: righe uscivano ancora tagliate («where the l…»): il margine fra la stima e
#: il vero si vede solo guardando.
#:
#: Non è una misura fine e non deve esserlo: serve a decidere DOVE mandare a
#: capo, e sbagliare di un carattere costa uno spazio, non una frase tagliata.
_CARATTERI_PER_UNITA = 0.1832
_CARATTERI_BASE = -13.3
_CARATTERI_MINIMI = 8


def _caratteri_per(unita) -> int:
    """La retta, in una funzione sua — così la prova la misura invece di
    ricopiarla. Si ARROTONDA e non si tronca: a 280 unità l'interpolazione dà
    37,996 e un `int()` restituiva 37, cioè un carattere in meno dei 38
    misurati. La prova l'ha preso, ed è il genere di errore che a video si
    vedrebbe come una parola in meno per riga e non come un difetto.
    """
    return max(_CARATTERI_MINIMI,
               round(unita * _CARATTERI_PER_UNITA + _CARATTERI_BASE))


def _quanti_caratteri(contesto) -> int:
    """La larghezza della regione, in caratteri. **Gratis**: `Region.width` è
    un intero già in memoria, non un conto e non un giro sul filesystem — la
    regola di questo file vieta l'uno e l'altro, non la lettura di un numero
    che Blender ha già.

    Senza regione (un disegno fuori contesto) si torna il budget dei 280, che
    è la larghezza che la sidebar ha per default.
    """
    regione = getattr(contesto, "region", None)
    scala = getattr(contesto.preferences.system, "ui_scale", 1.0) or 1.0
    if regione is None:
        return 38
    return _caratteri_per(regione.width / scala)


def _frase(layout, testo, caratteri, icona='NONE'):
    """Una frase che **va a capo** invece di troncarsi.

    Blender non manda a capo le `label`: le taglia, e una frase tagliata a
    metà parola («made, but its locat…ething on this disk») sembra un guasto.
    A 149 unità entrano diciassette caratteri: qualunque frase inglese utile è
    più lunga, quindi o si manda a capo o si rinuncia a dirla.

    Il taglio è per PAROLE e si fa qui, dove la larghezza si conosce: non nel
    conto, che non sa quanto è larga la sidebar, e non a mano nelle costanti,
    che dovrebbero indovinarla.
    """
    testo = str(testo or "").strip()
    if not testo:
        return
    riga, righe = "", []
    for parola in testo.split():
        if riga and len(riga) + 1 + len(parola) > caratteri:
            righe.append(riga)
            riga = parola
        else:
            riga = f"{riga} {parola}".strip()
    if riga:
        righe.append(riga)
    colonna = layout.column(align=True)
    for indice, r in enumerate(righe):
        if indice == 0:
            colonna.label(text=r, icon=icona)
        else:
            #: il rientro delle righe successive vale solo se la prima aveva
            #: un'icona: allinearsi a un'icona che non c'è vuol dire buttare
            #: via un carattere su quattordici, e a 149 unità si vede
            colonna.label(text=r, icon='BLANK1' if icona != 'NONE' else 'NONE')


def _cella(colonna, etichetta, valore, icona="NONE"):
    """Una cella su DUE righe: l'etichetta sopra, il valore sotto.

    È la forma decisa in EM16-UX2 dopo averla misurata: su una riga sola, a
    pannello stretto, il valore si tronca e diventa `mod…`. Su due, l'etichetta
    è corta per costruzione e il valore ha tutta la larghezza della colonna.
    """
    box = colonna.column(align=True)
    box.label(text=etichetta)
    box.label(text=valore or "—", icon=icona)


class EM_UL_publication_deck(bpy.types.UIList):
    """**D2 · una riga sola per asset.**

    A larghezza fissa tutto tranne il nome, che è l'elemento elastico e si
    accorcia per ultimo: l'icona del media, il glifo dello stato, il nome, e
    all'estremo destro la spunta.

    **La spunta È `is_publishable`** — la property di `scene.rm_list` che
    governa l'export, disegnata da qui. Non una copia, non un riflesso: la
    stessa property. Se il deck si facesse una spunta propria ci sarebbero due
    impostazioni per lo stesso fatto, che è la malattia dei cancelli del sync.

    Niente colore per dire lo stato: in Blender il rosso è l'errore.
    """

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        stretto = _quanti_caratteri(context) < 22
        #: **D5 · il glifo dello stato si mostra solo quando DISTINGUE.** Su un
        #: progetto di soli documenti è identico su tutte e diciannove le
        #: righe: una colonna il cui valore non varia mai costa larghezza e non
        #: dice niente, e quella cosa la dice meglio — e una volta sola — la
        #: riga di sintesi. L'icona del media resta sempre.
        glifo = getattr(data, "stati_differiscono", True) and not stretto

        #: A LARGHEZZA FISSA TUTTO TRANNE IL NOME. Misurato tre volte, e ogni
        #: giro ha tolto un'ipotesi: in una `row` le voci si spartiscono lo
        #: spazio in parti UGUALI (il nome finiva a un terzo di riga);
        #: `ui_units_x` sulle sotto-righe non lo cambia; e un CAMPO di testo,
        #: sotto una certa larghezza, smette di disegnare il testo del tutto —
        #: a 149 unità restavano due icone mute. Con `split` le proporzioni
        #: sono dichiarate e restano quelle a ogni larghezza.
        if glifo:
            fuori = layout.split(factor=0.12)
            fuori.label(text="", icon=_ICONA_STATO.get(item.stato, 'DOT'))
            riga = fuori.split(factor=0.86)
        else:
            riga = layout.split(factor=0.86 if not stretto else 0.82)

        #: il nome porta l'icona del media, così quella non consuma una voce
        #: sua. Una `label` e non un campo: una label tronca, un campo sparisce.
        #: E la cella è allineata a SINISTRA: con `align=True` sulla `split`
        #: il contenuto si centra, e il nome perdeva a sinistra lo spazio che
        #: gli serviva a destra.
        cella = riga.row()
        cella.alignment = 'LEFT'
        cella.label(text=item.name,
                    icon=_ICONA_MEDIA.get(item.media, 'DOT'))

        #: **D2 · LA SPUNTA, e stavolta ce l'hanno tutti.** È una finestra su
        #: `scene.em_publication_flags`, non su `is_publishable`: quello resta
        #: dell'exporter e vuol dire «questo RM entra nel bundle», che è un
        #: altro fatto. Adesso anche un documento può portarla, ed è per questo
        #: che diciannove righe non sono più senza casella.
        coda = riga.row(align=True)
        coda.prop(item, "pubblica", text="")

    def filter_items(self, context, data, nome_proprieta):
        """**Il filtro, applicato dove si guarda.**

        Senza questo il campo di ricerca c'era e non faceva niente: la lista
        mostrava tutto e l'operatore in blocco agiva su ciò che il filtro
        diceva. Due letture della stessa intenzione che non coincidono — e chi
        avesse filtrato per «US_0» avrebbe premuto «Flag in view» vedendo
        diciannove righe e flaggandone due. Se ne è accorta la prova che
        chiedeva che il filtro stesse in un posto solo.

        La regola di cosa è in vista sta in `publication_flags.in_vista`, ed è
        la **stessa** che l'operatore chiama: qui si traduce soltanto in
        maschera di bit, che è la forma che Blender vuole.
        """
        from .. import publication_flags

        righe = getattr(data, nome_proprieta)
        filtro = str(getattr(data, "filtro", "") or "")
        if not filtro:
            return [], []
        visibili = set(publication_flags.in_vista(righe, filtro))
        maschera = [
            self.bitflag_filter_item
            if (r.asset_id or r.name) in visibili else 0
            for r in righe]
        return maschera, []


class VIEW3D_PT_em_publication_deck(bpy.types.Panel):
    bl_label = "Publication Deck"
    bl_idname = "VIEW3D_PT_em_publication_deck"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM Bridge"
    bl_order = 0
    #: APERTO di default, al contrario degli altri pannelli di questo tab.
    #: La riga di sintesi deve essere **sempre visibile**, e un pannello
    #: chiuso la nasconde.

    def draw(self, context):
        layout = self.layout
        larghezza = _quanti_caratteri(context)
        deck = getattr(context.scene, "em_publication_deck", None)
        if deck is None:
            layout.label(text="The deck is not registered.", icon='INFO')
            return

        self._testa(layout, deck, larghezza)
        if not deck.calcolato_alle:
            #: MAI CALCOLATO ≠ NIENTE DA PUBBLICARE. Due situazioni diverse,
            #: due frasi diverse: la prima si risolve premendo un bottone, la
            #: seconda è una risposta.
            box = layout.box()
            _frase(box, "Nothing counted yet.", larghezza, icona='INFO')
            _frase(box, "Refresh reads the disk, so it runs when you ask.",
                   larghezza)
            return
        if deck.nota:
            _frase(layout.box(), deck.nota, larghezza, icona='INFO')
            return
        if not len(deck.righe):
            self._vuoto(layout, larghezza)
            return
        self._destinazione(layout, deck, larghezza)
        self._lista(layout, deck)
        self._comandi(layout, deck, larghezza)
        self._scheda(layout, deck, larghezza)

    # ── la testa: la sintesi, e quando è stata presa ───────────────────────

    def _testa(self, layout, deck, larghezza):
        """*N assets · M published · K stale* — sempre visibile.

        Quando K non è zero, quel numero è la cosa più importante del
        pannello. **Senza rosso**: si vede perché ha una riga sua, un'icona di
        tempo e un verbo accanto — non perché è colorato come un errore, che
        errore non è.

        **D4 · il Refresh è il controllo meno usato del pannello** e si
        prendeva metà della sua riga. Adesso è icona sola in una cella stretta
        di una `split` — non di una `row`, dove le voci si dividono lo spazio
        in parti uguali qualunque cosa contengano.
        """
        _frase(layout, deck.sintesi or "—", larghezza, icona='EXPORT')

        if deck.calcolato_alle:
            #: L'ORA DEL CONTO, accanto ai numeri. Un numero vecchio che dice
            #: di essere vecchio è informazione.
            quando = f"as of {deck.calcolato_alle}"
            if deck.distribuzioni and larghezza >= 20:
                quando += f" · {deck.distribuzioni} files"
            #: la cella del bottone è una frazione, quindi a pannello stretto
            #: vale meno pixel: a 149 unità con 0,88 l'ora usciva «as of 20:…».
            #: Misurato, e corretto con la frazione e non con una frase più
            #: corta — l'ora è già la cosa più corta che si possa dire.
            fattore = 0.88 if larghezza >= 20 else 0.78
            riga = layout.split(factor=fattore, align=True)
            _frase(riga, quando, int(larghezza * fattore), icona='BLANK1')
            riga.operator("em.deck_refresh", text="", icon='FILE_REFRESH')

        if deck.stale:
            #: LA RIGA CHE CONTA, e si vede perché è SUA — non perché è rossa.
            #: D4 · una riga e il verbo, non una scatola di tre. A pannello
            #: stretto il conto e il verbo NON stanno sulla stessa riga: con
            #: la `split` a 0,45 il numero usciva «1…», e perdere la cifra è
            #: perdere tutto — è il numero più importante del pannello.
            if larghezza >= 20:
                riga = layout.split(factor=0.45, align=True)
                riga.label(text=f"{deck.stale} stale", icon='TEMP')
                riga.operator("em.deck_rebake", text="Re-bake")
            else:
                colonna = layout.column(align=True)
                colonna.label(text=f"{deck.stale} stale", icon='TEMP')
                colonna.operator("em.deck_rebake", text="Re-bake")

        # D5/D4 · UNA RAGIONE CHE VALE PER TUTTI SI DICE UNA VOLTA, IN TESTA —
        # e in UNA RIGA, non in una scatola da centottanta pixel per un
        # messaggio che riguarda due righe su diciannove.
        for blocco in deck.blocchi:
            _frase(layout, f"{blocco.quanti} held back: {blocco.name}",
                   larghezza, icona='INFO')

        # D6 · LO STATO DEL GRAFO, in sola lettura e senza verbi. Il grafo è
        # ciò che dice cosa un glb rappresenta; il deck lo mostra e non lo
        # pubblica, perché quel gesto è il push nella stanza e vive altrove.
        if deck.grafo_frase:
            _frase(layout, deck.grafo_frase, larghezza,
                   icona=_ICONA_GRAFO.get(deck.grafo_stato, 'QUESTION'))

    # ── lo stato vuoto ─────────────────────────────────────────────────────

    def _vuoto(self, layout, larghezza):
        """Un deck senza niente da pubblicare lo dice in una riga, e non mostra
        una tabella vuota con le intestazioni — lo stesso principio dell'EM
        Data Tree a scena vuota."""
        box = layout.box()
        _frase(box, "Nothing on the threshold.", larghezza, icona='CHECKMARK')
        _frase(box, "No resources to publish yet: promote a model, "
                    "then export.", larghezza)

    # ── per chi ────────────────────────────────────────────────────────────

    def _destinazione(self, layout, deck, larghezza):
        riga = layout.row(align=True)
        riga.prop(deck, "destinazione", text="")
        if deck.destinazione_nota:
            #: T3, un livello più su: una capacità che non si è potuta leggere
            #: si dice `unknown` CON la ragione, non `no`.
            _frase(layout, deck.destinazione_nota, larghezza, icona='QUESTION')

    # ── la lista ───────────────────────────────────────────────────────────

    def _lista(self, layout, deck):
        """**D4 · la lista cresce con il contenuto, fino a un tetto.**

        Sei righe fisse mentre la scheda ne occupava venti erano un pannello
        che dedicava il 20% dell'altezza alla domanda («quali asset ho») e il
        63% alla risposta su uno solo — misurato, e il conto di E.D. sullo
        stesso progetto diceva 19% e 42%.

        **Il tetto è dieci**, e non è un numero tondo a caso: a 280 unità, in
        una sidebar da 1734 px, dieci righe lasciano ancora vedere l'inizio
        della scheda. A quattordici la scheda finiva sotto il bordo, e cliccare
        una riga voleva dire scrollare per vederne la risposta — cioè rompere
        proprio il gesto che la lista serve a rendere veloce.
        """
        layout.prop(deck, "filtro", text="", icon='VIEWZOOM')
        layout.template_list("EM_UL_publication_deck", "",
                             deck, "righe", deck, "riga_attiva",
                             rows=min(max(len(deck.righe), 5), 10))

    # ── i comandi in batch ─────────────────────────────────────────────────

    def _comandi(self, layout, deck, larghezza):
        """Il verbo in batch agisce su ciò che è SPUNTATO, con il numero nel
        bottone.

        Mai un «publish selected» che agisce su una selezione invisibile
        perché si è scrollato: è il modo in cui si pubblica ciò che non si
        voleva. Le UIList di Blender non hanno multi-selezione, quindi la
        spunta è anche il modo di scegliere — ed è la stessa spunta che
        governa l'export, non una seconda.
        """
        #: D3 · i verbi collettivi, ADDITIVI e annullabili. Icone sole in una
        #: `grid_flow`, che è l'unico modo misurato perché riempiano la riga.
        collettivi = layout.grid_flow(row_major=True, columns=2,
                                      even_columns=True, even_rows=False,
                                      align=True)
        collettivi.row(align=True).operator(
            "em.deck_flag_visible", icon='CHECKBOX_HLT',
            text="Flag in view" if larghezza >= 20 else "")
        collettivi.row(align=True).operator(
            "em.deck_unflag_visible", icon='CHECKBOX_DEHLT',
            text="Clear in view" if larghezza >= 20 else "")

        riga = layout.row(align=True)
        riga.scale_y = 1.2
        #: IL NUMERO NEL BOTTONE non si perde mai: è la parte che dice su cosa
        #: si sta per agire. A pannello stretto cade la parola, non la cifra.
        riga.operator("em.deck_publish", icon='EXPORT',
                      text=(f"Publish {deck.spuntati} flagged"
                            if larghezza >= 20 else f"Publish {deck.spuntati}"))

    # ── la scheda della riga attiva ────────────────────────────────────────

    def _scheda(self, layout, deck, larghezza):
        """**D3 · quello che stava nel box, per UNA riga sola.**

        Dove stanno i byte, formato, impacchettamento, tier, dimensione,
        locator, le date, l'annotazione del lettore — più l'elenco delle sue
        distribuzioni e i verbi che riguardano quel singolo asset.

        **D4 · e in molte meno righe.** La scheda si prendeva il 42%
        dell'altezza del pannello: la griglia due-per-due con l'etichetta sopra
        il valore erano otto righe per quattro fatti, e uno era vuoto.
        """
        if not (0 <= deck.riga_attiva < len(deck.righe)):
            return
        riga = deck.righe[deck.riga_attiva]
        box = layout.box()

        _frase(box, riga.name, larghezza,
               icona=_ICONA_MEDIA.get(riga.media, 'DOT'))
        _frase(box, _SPIEGA_STATO.get(riga.stato, ""), larghezza,
               icona=_ICONA_STATO.get(riga.stato, 'DOT'))

        #: LE DUE GRANULARITÀ. Un container dice quanti membri accorpa e non
        #: finge di essere un modello: un rilievo di quattromila tile non è
        #: una mesh.
        if riga.granularita == "container":
            _frase(box, f"{riga.proprietario} · {riga.membri} members",
                   larghezza, icona='OUTLINER_COLLECTION')
            elenco = getattr(bpy.context.scene, "rm_containers", None)
            if elenco is not None and 0 <= riga.container_indice < len(elenco):
                #: l'ALTRA impostazione che governa cosa l'export farà, qui
                #: dov'è utile leggerla — e non una copia
                box.prop(elenco[riga.container_indice],
                         "publication_strategy", text="")

        # D4 · **UNA sola negazione**, non tre. `ready: n/a` + «this
        # destination only takes 3d models» + «no publish flag governs this»
        # dicevano la stessa cosa in tre modi, e il terzo adesso non esiste
        # nemmeno più (D2: la spunta ce l'hanno tutti). Resta quella che
        # aggiunge informazione: COSA quel lettore non sa fare — e non
        # impedisce niente, perché il deck pubblica byte.
        if riga.pronto and riga.pronto != "yes":
            _frase(box, riga.pronto_perche or f"not readable: {riga.pronto}",
                   larghezza, icona=_ICONA_PRONTO.get(riga.pronto, 'QUESTION'))
        elif riga.pronto == "yes":
            box.label(text=f"readable by {deck.destinazione}",
                      icon='CHECKMARK')

        _frase(box, riga.cosa_e_cambiato, larghezza, icona='TEMP')
        _frase(box, riga.perche_no, larghezza, icona='INFO')

        self._distribuzioni(box, riga, larghezza)
        self._verbi(box, riga, larghezza)

    def _distribuzioni(self, layout, riga, larghezza):
        """Le distribuzioni dell'asset: i FILE, dove la riga è la COSA.

        Un tileset ha il suo zip (per viaggiare) e il suo albero servito (per
        essere caricato): due file, due checksum, e una sola decisione. È
        questa la ragione per cui stanno qui e non nella lista.

        **D4 · i fatti su UNA riga**, `disk · pdf · distribution · 39 KB`, e i
        campi vuoti non si disegnano affatto. La griglia a due colonne con
        l'etichetta sopra il valore costava otto righe per dire quattro cose,
        una delle quali era `Size / —`: cioè due righe per dire che non si sa
        quanto pesa.
        """
        for d in riga.distribuzioni:
            box = layout.box()
            _frase(box, d.name, larghezza,
                   icona=_ICONA_STATO.get(d.stato, 'DOT'))
            fatti = [d.dove, d.formato, d.packaging, d.tier, d.peso,
                     d.residency, d.scope]
            _frase(box, " · ".join(x for x in fatti if x), larghezza,
                   icona='BLANK1')
            if d.pubblicata_il:
                #: SOLO IL GIORNO. Con l'ora la riga si allunga e si perde
                #: proprio la parte che distingue due pubblicazioni.
                box.label(text=f"published {d.pubblicata_il[:10]}",
                          icon='BLANK1')
            coda = d.url.rsplit("/", 1)[-1]
            if coda and coda != d.name:
                #: il nome del file solo quando AGGIUNGE qualcosa: per un
                #: documento la distribuzione si chiama già `US_001.pdf`, e
                #: scriverlo due volte di fila è una riga che non dice niente
                _frase(box, coda, larghezza, icona='URL')

    def _verbi(self, layout, riga, larghezza):
        """I verbi del singolo asset, e **con un'etichetta** quando ci sta.

        D4 · a video erano quattro icone mute: il tooltip c'è (è la
        `bl_description` dell'operatore) ma va cercato col mouse fermo, e un
        verbo che si scopre solo passandoci sopra è un verbo che non si usa.
        Sotto le 20 unità-carattere restano icone, perché lì un'etichetta si
        troncherebbe e un verbo troncato è peggio di un'icona.
        """
        principale = riga.distribuzioni[0] if len(riga.distribuzioni) else None
        con_testo = larghezza >= 20
        verbi = layout.grid_flow(row_major=True, columns=2 if con_testo else 4,
                                 even_columns=True, even_rows=False, align=True)
        verbi.scale_y = 1.2
        url = principale.url if principale else ""
        percorso = principale.percorso if principale else ""
        verbi.row(align=True).operator(
            "em.deck_reveal", text="Reveal" if con_testo else "",
            icon='FILE_FOLDER').percorso = percorso
        verbi.row(align=True).operator(
            "em.deck_copy_uri", text="Copy URI" if con_testo else "",
            icon='COPYDOWN').url = url
        verbi.row(align=True).operator(
            "em.deck_rebake", text="Re-bake" if con_testo else "",
            icon='FILE_REFRESH')
        uno = verbi.row(align=True)
        uno.enabled = bool(riga.n_pubblicabili)
        uno.operator("em.deck_publish_one",
                     text="Publish" if con_testo else "",
                     icon='EXPORT').asset_id = riga.asset_id


_CLASSI = (EM_UL_publication_deck, VIEW3D_PT_em_publication_deck)


def register():
    for cls in _CLASSI:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSI):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001 — unregistering must not fail
            pass
