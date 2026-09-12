"""Il pannello del Publication Deck (tab EM Bridge).

Il tab dei ponti verso l'esterno, e il deck è il posto che guarda la soglia.
`bl_order = 0`: sta **prima** dell'Export Manager perché risponde alla domanda
che viene prima di esportare — cosa manca — e chi apre questo tab con un dubbio
in testa ha quel dubbio, non un bottone da premere.

**IL `draw` NON CALCOLA NIENTE.** Disegna la cache
(`scene.em_publication_deck`), riempita da `em.deck_refresh`. È l'unica regola
architetturale di questo file, e viene da una misura: `stato_risorse` costa un
`os.stat` per derivata e un pannello si ridisegna a ogni movimento del mouse.

Convenzioni di casa, già decise e qui rispettate:

* celle su **due righe** che non si troncano — il valore sotto l'etichetta,
  come il Graph Info, invece di una riga sola che a pannello stretto diventa
  `mod…`;
* **sezioni collassabili la cui intestazione porta il sommario**, così
  chiudere non nasconde il numero;
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

#: Cosa vuol dire ogni stato, in una frase. Sta nel tooltip della riga perché
#: la parola da sola è un gergo che si impara una volta e si dimentica.
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

_ICONA_PRONTO = {"yes": "CHECKMARK", "no": "CANCEL", "unknown": "QUESTION"}


def _cella(colonna, etichetta, valore, icona="NONE"):
    """Una cella su DUE righe: l'etichetta sopra, il valore sotto.

    È la forma decisa in EM16-UX2 dopo averla misurata: su una riga sola, a
    pannello stretto, il valore si tronca e diventa `mod…`. Su due, l'etichetta
    è corta per costruzione e il valore ha tutta la larghezza della colonna.
    """
    box = colonna.column(align=True)
    box.label(text=etichetta)
    box.label(text=valore or "—", icon=icona)


class VIEW3D_PT_em_publication_deck(bpy.types.Panel):
    bl_label = "Publication Deck"
    bl_idname = "VIEW3D_PT_em_publication_deck"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM Bridge"
    bl_order = 0
    #: APERTO di default, al contrario degli altri pannelli di questo tab.
    #: La riga di sintesi deve essere **sempre visibile**, e un pannello
    #: chiuso la nasconde: chiudere non deve nascondere il numero, ed è la
    #: stessa convenzione che le sezioni interne rispettano portando il conto
    #: nell'intestazione.

    def draw(self, context):
        layout = self.layout
        deck = getattr(context.scene, "em_publication_deck", None)
        if deck is None:
            layout.label(text="The deck is not registered.", icon='INFO')
            return

        self._testa(layout, deck)
        if not deck.calcolato_alle:
            #: MAI CALCOLATO ≠ NIENTE DA PUBBLICARE. Due situazioni diverse,
            #: due frasi diverse: la prima si risolve premendo un bottone, la
            #: seconda è una risposta.
            box = layout.box()
            box.label(text="Nothing counted yet.", icon='INFO')
            box.label(text="Refresh reads the disk,")
            box.label(text="so it runs when you ask.")
            return
        if deck.nota:
            layout.box().label(text=deck.nota, icon='INFO')
            return
        if not len(deck.righe):
            self._vuoto(layout)
            return
        self._destinazione(layout, deck)
        self._comandi(layout, deck)
        self._righe(layout, deck)

    # ── la testa: la sintesi, e quando è stata presa ───────────────────────

    def _testa(self, layout, deck):
        """*N assets · M published · K stale* — sempre visibile.

        Quando K non è zero, quel numero è la cosa più importante del
        pannello. **Senza rosso**: si vede perché ha una riga sua, un'icona di
        tempo e un verbo accanto — non perché è colorato come un errore, che
        errore non è.
        """
        testa = layout.row(align=True)
        testa.label(text=deck.sintesi or "—", icon='EXPORT')
        aggiorna = testa.row(align=True)
        aggiorna.operator("em.deck_refresh", text="", icon='FILE_REFRESH')

        if deck.calcolato_alle:
            #: L'ORA DEL CONTO, accanto ai numeri. Un numero vecchio che dice
            #: di essere vecchio è informazione.
            layout.label(text=f"as of {deck.calcolato_alle}", icon='BLANK1')

        if deck.stale:
            #: LA RIGA CHE CONTA, e si vede perché è SUA — non perché è rossa.
            #:
            #: L'etichetta ha una riga tutta per sé e il verbo sta sotto: a
            #: video, con il bottone accanto, la frase usciva troncata
            #: («1 stale — remade from their sour…»). Un numero importante che
            #: si tronca smette di essere importante.
            box = layout.box()
            box.label(text=f"{deck.stale} stale", icon='TEMP')
            box.label(text="their sources changed after the bake",
                      icon='BLANK1')
            box.operator("em.deck_rebake", icon='FILE_REFRESH')

    # ── lo stato vuoto ─────────────────────────────────────────────────────

    def _vuoto(self, layout):
        """Un deck senza niente da pubblicare lo dice in una riga, e non mostra
        una tabella vuota con le intestazioni — lo stesso principio dell'EM
        Data Tree a scena vuota."""
        box = layout.box()
        box.label(text="Nothing on the threshold.", icon='CHECKMARK')
        box.label(text="No resources to publish yet:")
        box.label(text="promote a model, then export.")

    # ── per chi ────────────────────────────────────────────────────────────

    def _destinazione(self, layout, deck):
        riga = layout.row(align=True)
        riga.prop(deck, "destinazione", text="")
        if deck.destinazione_nota:
            #: T3, un livello più su: una capacità che non si è potuta leggere
            #: si dice `unknown` CON la ragione, non `no`.
            layout.label(text=deck.destinazione_nota, icon='QUESTION')

    # ── i comandi ──────────────────────────────────────────────────────────

    def _comandi(self, layout, deck):
        """Una riga di bottoni icona che riempie la larghezza.

        `grid_flow(even_columns=True)` e non una `row` piatta: misurato in
        EM16-UX2 che in una riga piatta i bottoni solo-icona NON si allargano,
        e restano schiacciati a sinistra qualunque sia la larghezza.
        """
        cmd = layout.grid_flow(row_major=True, columns=4, even_columns=True,
                               even_rows=False, align=True)
        cmd.scale_y = 1.2
        for quali, icona in (("all", 'CHECKBOX_HLT'), ("stale", 'TEMP'),
                             ("none", 'CHECKBOX_DEHLT')):
            cmd.row(align=True).operator(
                "em.deck_select", text="", icon=icona).quali = quali
        pubblica = cmd.row(align=True)
        pubblica.operator("em.deck_publish", text="", icon='EXPORT')

        scelte = sum(1 for r in deck.righe if r.selezionata)
        if scelte:
            layout.label(text=f"{scelte} selected of {deck.pubblicabili} "
                              f"publishable", icon='BLANK1')

    # ── le righe ───────────────────────────────────────────────────────────

    def _righe(self, layout, deck):
        """Una sezione per stato, e l'intestazione porta il conto.

        **Chiudere non nasconde il numero**: è la convenzione di casa, e qui
        conta il doppio, perché la sezione che uno chiude per prima è quella
        con dentro il lavoro da fare.
        """
        per_stato = {}
        for riga in deck.righe:
            per_stato.setdefault(riga.stato, []).append(riga)

        #: l'ordine è la distanza dal fuori: prima quello che manca
        for stato in ("stale", "baked", "unresolved", "orphan", "published",
                      "master"):
            righe = per_stato.get(stato)
            if not righe:
                continue
            if stato == "master" and not deck.mostra_master:
                continue
            box = layout.box()
            testa = box.row(align=True)
            testa.label(text=f"{stato} · {len(righe)}",
                        icon=_ICONA_STATO.get(stato, 'DOT'))
            if stato == "master":
                testa.prop(deck, "mostra_master", text="", icon='HIDE_OFF')
            box.label(text=_SPIEGA_STATO.get(stato, ""), icon='BLANK1')
            for riga in righe:
                self._riga(box, deck, riga)

    def _riga(self, layout, deck, riga):
        box = layout.box()

        # ── chi è, e di chi è ──────────────────────────────────────────────
        testa = box.row(align=True)
        if riga.pubblicabile:
            testa.prop(riga, "selezionata", text="")
        else:
            #: niente casella dove non si può fare niente: una casella che si
            #: spunta e poi viene saltata è una promessa che non si mantiene
            testa.label(text="", icon='BLANK1')
        testa.label(text=riga.name)

        #: LE DUE GRANULARITÀ. La riga di un tileset dice a quale container
        #: appartiene e quanti membri accorpa, e non finge di essere un
        #: modello: un rilievo di quattromila tile non è una mesh.
        if riga.granularita == "container":
            box.label(text=f"{riga.proprietario} · {riga.membri} members",
                      icon='OUTLINER_COLLECTION')
        else:
            box.label(text=riga.proprietario, icon='MESH_DATA')

        # ── i fatti, in celle a due righe ─────────────────────────────────
        griglia = box.grid_flow(row_major=True, columns=2, even_columns=True,
                                even_rows=False, align=False)
        _cella(griglia, "Bytes are", riga.dove)
        _cella(griglia, "Format", f"{riga.formato}"
               + (f" · {riga.packaging}" if riga.packaging else ""))
        _cella(griglia, "Tier", riga.tier)
        _cella(griglia, "Size", riga.peso)
        if riga.residency or riga.scope:
            _cella(griglia, "Residency", riga.residency)
            _cella(griglia, "Scope", riga.scope)
        if riga.pubblicata_il:
            #: SOLO IL GIORNO. Con l'ora, la cella si tronca
            #: («2026-09-10 17:…») e si perde proprio la parte che distingue
            #: due pubblicazioni. Alla granularità di questo pannello — «è
            #: aggiornata?» — il giorno basta, e sta.
            _cella(griglia, "Published", riga.pubblicata_il[:10])

        # ── sulle stantie, COSA è cambiato ────────────────────────────────
        if riga.cosa_e_cambiato:
            nota = box.row(align=True)
            nota.label(text=riga.cosa_e_cambiato, icon='TEMP')

        # ── pronto per la destinazione scelta ─────────────────────────────
        pronto = box.row(align=True)
        pronto.label(text=f"ready for {deck.destinazione}: {riga.pronto}",
                     icon=_ICONA_PRONTO.get(riga.pronto, 'QUESTION'))
        if riga.pronto_perche:
            box.label(text=riga.pronto_perche, icon='BLANK1')

        # ── perché non si può pubblicare, quando non si può ───────────────
        if not riga.pubblicabile and riga.perche_no:
            box.label(text=riga.perche_no, icon='INFO')

        # ── i verbi secondari ─────────────────────────────────────────────
        verbi = box.grid_flow(row_major=True, columns=2, even_columns=True,
                              even_rows=False, align=True)
        verbi.row(align=True).operator(
            "em.deck_reveal", text="", icon='FILE_FOLDER').url = riga.url
        verbi.row(align=True).operator(
            "em.deck_copy_uri", text="", icon='COPYDOWN').url = riga.url


_CLASSI = (VIEW3D_PT_em_publication_deck,)


def register():
    for cls in _CLASSI:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSI):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001 — unregistering must not fail
            pass
