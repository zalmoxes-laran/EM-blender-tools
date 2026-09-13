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

_ICONA_PRONTO = {"yes": "CHECKMARK", "no": "CANCEL", "unknown": "QUESTION",
                 #: `n/a` non è un rifiuto: la domanda non si pone, e un'icona
                 #: di rifiuto manderebbe qualcuno a cercare un guasto
                 "n/a": "BLANK1"}


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

        #: A LARGHEZZA FISSA TUTTO TRANNE IL NOME. Misurato tre volte, e ogni
        #: giro ha tolto un'ipotesi: in una `row` le voci si spartiscono lo
        #: spazio in parti UGUALI (il nome finiva a un terzo di riga);
        #: `ui_units_x` sulle sotto-righe non lo cambia; e un CAMPO di testo,
        #: sotto una certa larghezza, smette di disegnare il testo del tutto —
        #: a 149 unità restavano due icone mute. Con `split` le proporzioni
        #: sono dichiarate e restano quelle a ogni larghezza.
        #:
        #: **E A PANNELLO STRETTO IL GLIFO DELLO STATO SE NE VA.** A 149 unità
        #: la riga è di nove caratteri: due icone e una spunta se li mangiano
        #: tutti, e un nome ridotto a «v» non è un nome. Lo stato lo dicono già
        #: il conto in testa e la scheda; l'icona del media no, ed è quella che
        #: E.D. ha chiesto — quindi è quella che resta.
        if stretto:
            riga = layout.split(factor=0.82)
        else:
            fuori = layout.split(factor=0.12)
            fuori.label(text="", icon=_ICONA_STATO.get(item.stato, 'DOT'))
            riga = fuori.split(factor=0.86)

        #: il nome porta l'icona del media, così quella non consuma una voce
        #: sua. Una `label` e non un campo: una label tronca, un campo sparisce.
        #: E la cella è allineata a SINISTRA: con `align=True` sulla `split`
        #: il contenuto si centra, e il nome perdeva a sinistra lo spazio che
        #: gli serviva a destra.
        cella = riga.row()
        cella.alignment = 'LEFT'
        cella.label(text=item.name,
                    icon=_ICONA_MEDIA.get(item.media, 'DOT'))

        coda = riga.row(align=True)
        elenco = getattr(context.scene, "rm_list", None)
        if elenco is not None and 0 <= item.flag_indice < len(elenco):
            coda.prop(elenco[item.flag_indice], "is_publishable", text="")
        else:
            #: nessun flag governa questo asset (un documento non ne ha uno):
            #: niente casella, perché una casella che si spunta e poi non
            #: cambia niente è una promessa che non si mantiene. La scheda
            #: dice perché.
            coda.label(text="", icon='BLANK1')


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
        """
        _frase(layout, deck.sintesi or "—", larghezza, icona='EXPORT')

        if deck.calcolato_alle:
            #: L'ORA DEL CONTO, accanto ai numeri. Un numero vecchio che dice
            #: di essere vecchio è informazione.
            #: IL REFRESH STA QUI, non accanto alla sintesi e non
            #: nell'intestazione. Misurato: accanto alla sintesi le rubava la
            #: larghezza e a 149 unità usciva «9 assets …»; nell'intestazione
            #: si sovrapponeva al titolo, che a quella larghezza è già
            #: troncato. Sulla riga dell'ora non dà fastidio a nessuno.
            quando = f"as of {deck.calcolato_alle}"
            if deck.distribuzioni and larghezza >= 20:
                quando += f" · {deck.distribuzioni} files"
            #: `split` e non `row`: in una `row` il bottone si prende metà
            #: della riga e l'ora esce «as of 17:…»
            riga = layout.split(factor=0.78, align=True)
            _frase(riga, quando, int(larghezza * 0.78), icona='BLANK1')
            riga.operator("em.deck_refresh", text="", icon='FILE_REFRESH')

        if deck.stale:
            #: LA RIGA CHE CONTA, e si vede perché è SUA — non perché è rossa.
            box = layout.box()
            box.label(text=f"{deck.stale} stale", icon='TEMP')
            _frase(box, "sources changed", larghezza)
            #: senza icona: a 149 unità l'icona si mangiava due caratteri e il
            #: verbo usciva «Re-bake st…»
            box.operator("em.deck_rebake")

        # D5 · UNA RAGIONE CHE VALE PER TUTTI SI DICE UNA VOLTA, IN TESTA.
        # Diciannove righe che ripetono la stessa frase non la rendono più
        # vera: la rendono illeggibile, e nascondono che il problema è UNO.
        for blocco in deck.blocchi:
            box = layout.box()
            box.label(text=f"{blocco.quanti} held back:", icon='INFO')
            _frase(box, blocco.name, larghezza)

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
        layout.template_list("EM_UL_publication_deck", "",
                             deck, "righe", deck, "riga_attiva", rows=6)

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
        locator, le date, la ragione quando non è pronta — più l'elenco delle
        sue distribuzioni e i verbi che riguardano quel singolo asset.
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

        if riga.pronto:
            box.label(text=f"ready: {riga.pronto}",
                      icon=_ICONA_PRONTO.get(riga.pronto, 'QUESTION'))
            _frase(box, riga.pronto_perche, larghezza, icona='BLANK1')

        _frase(box, riga.cosa_e_cambiato, larghezza, icona='TEMP')
        _frase(box, riga.perche_no, larghezza, icona='INFO')
        if riga.flag_indice < 0:
            #: niente spunta su questa riga, e si dice perché: un controllo
            #: assente senza una ragione sembra un guasto
            _frase(box, "no publish flag governs this", larghezza,
                   icona='BLANK1')

        self._distribuzioni(box, riga, larghezza)
        self._verbi(box, riga)

    def _distribuzioni(self, layout, riga, larghezza):
        """Le distribuzioni dell'asset: i FILE, dove la riga è la COSA.

        Un tileset ha il suo zip (per viaggiare) e il suo albero servito (per
        essere caricato): due file, due checksum, e una sola decisione. È
        questa la ragione per cui stanno qui e non nella lista.
        """
        for d in riga.distribuzioni:
            box = layout.box()
            _frase(box, d.name, larghezza,
                   icona=_ICONA_STATO.get(d.stato, 'DOT'))
            griglia = box.grid_flow(row_major=True, columns=2,
                                    even_columns=True, even_rows=False,
                                    align=False)
            _cella(griglia, "Bytes are", d.dove)
            _cella(griglia, "Format", f"{d.formato}"
                   + (f" · {d.packaging}" if d.packaging else ""))
            _cella(griglia, "Tier", d.tier)
            _cella(griglia, "Size", d.peso)
            if d.residency or d.scope:
                _cella(griglia, "Residency", d.residency)
                _cella(griglia, "Scope", d.scope)
            if d.pubblicata_il:
                #: SOLO IL GIORNO. Con l'ora, la cella si tronca
                #: («2026-09-10 17:…») e si perde proprio la parte che
                #: distingue due pubblicazioni.
                _cella(griglia, "Published", d.pubblicata_il[:10])
            if d.url:
                _frase(box, d.url.rsplit("/", 1)[-1], larghezza, icona='URL')

    def _verbi(self, layout, riga):
        """I verbi del singolo asset: una riga di bottoni icona che riempie la
        larghezza.

        `grid_flow(even_columns=True)` e non una `row` piatta: misurato in
        EM16-UX2 che in una riga piatta i bottoni solo-icona NON si allargano,
        e restano schiacciati a sinistra qualunque sia la larghezza.
        """
        principale = riga.distribuzioni[0] if len(riga.distribuzioni) else None
        verbi = layout.grid_flow(row_major=True, columns=4, even_columns=True,
                                 even_rows=False, align=True)
        verbi.scale_y = 1.2
        url = principale.url if principale else ""
        percorso = principale.percorso if principale else ""
        verbi.row(align=True).operator(
            "em.deck_reveal", text="", icon='FILE_FOLDER').percorso = percorso
        verbi.row(align=True).operator(
            "em.deck_copy_uri", text="", icon='COPYDOWN').url = url
        verbi.row(align=True).operator(
            "em.deck_rebake", text="", icon='FILE_REFRESH')
        uno = verbi.row(align=True)
        uno.enabled = bool(riga.n_pubblicabili)
        uno.operator("em.deck_publish_one", text="",
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
