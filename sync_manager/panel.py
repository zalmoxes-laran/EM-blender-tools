"""Panel for the live-sync bridge and the room (tab "EM").

**C4 · il modo si DICHIARA, e comanda.**

Fino a stanotte questo pannello *riferiva* il modo: i tre chip erano disegnati
disabilitati, perché il modo era derivato («sei in Hub perché sei in una
stanza») e un controllo che pretendesse altro avrebbe lasciato scegliere «Hub»
senza essere in nessuna stanza. Era onesto e non bastava: i due modi non erano
esclusivi — Hub non spegneva il sidecar, e i due drenavano la stessa coda —
quindi il referto descriveva uno stato che non c'era.

Adesso il modo è dichiarato e la dichiarazione ESEGUE (`operators.applica_modo`).
I chip mostrano ancora il modo **attivo**, cioè la realtà; ma sono premibili,
perché adesso premerli la cambia. E quando dichiarato e reale divergono — una
stanza che cade, una porta occupata — il pannello lo DICE, invece di far vincere
in silenzio uno dei due.

**C5 · l'ordine è quanto spesso una cosa cambia davvero.**

Dall'alto in basso: il **modo attivo** (a ogni sessione, ed è la prima domanda);
la **stanza** e il suo esito (a ogni sessione); i **permessi** — cosa accetto,
e se EM Studio può modellare qui — presentati come permessi e non come
impostazioni, ognuno con la riga che dice cosa consente; il **server** e la
lista (ogni tanto). La porta e «materializza all'adozione» non sono più qui: non
cambiano quasi mai, e sono diventate preferenze dell'add-on (**EM ▸ Settings**).

Sotto il modo attivo compare solo ciò che quel modo rende pertinente.

**I nomi sono quelli di EM Studio**: Standalone · Sidecar · Hub. Un vocabolario
solo fra le due applicazioni. Il *posto* resta una stanza («in {room} · N
present»), il *modo* è Hub: la stanza è dove sta il lavoro, l'hub è il servizio
che lo tiene.
"""

from __future__ import annotations

import bpy  # type: ignore

from . import operators as ops

#: label · icon · what it means, in the words the tooltip uses.
_MODES = (
    (ops.MODE_STANDALONE, "Standalone", "MESH_CIRCLE",
     "This Blender alone: no bridge served, no room joined."),
    (ops.MODE_SIDECAR, "Sidecar", "LINKED",
     "Paired with EMStudio over the local bridge — two screens, one person."),
    (ops.MODE_HUB, "Hub", "WORLD",
     "In a room on an StratiGraph Server: the EM Data Tree is that room's container."),
)


class VIEW3D_PT_em_sync(bpy.types.Panel):
    bl_label = "EMStudio Sync"
    bl_idname = "VIEW3D_PT_em_sync"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM Bridge"
    bl_order = 4
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        running = ops.is_running()
        status = ops.room_status(context)
        mode = ops.session_mode(context)

        self._modo(layout, context, mode, running)
        self._allineamento(layout, context)
        self._ultimo_in_ingresso(layout)
        if mode == ops.MODE_HUB:
            self._in_stanza(layout, context, status)
        self._permessi(layout, context, running)
        self._dove(layout, context, status, running)

    # ── 1 · IL MODO, in testa ───────────────────────────────────────────────

    def _modo(self, layout, context, mode, running):
        """I tre chip. C4 · adesso si premono, e premerli fa la transizione."""
        row = layout.row(align=True)
        for value, label, icon, _tip in _MODES:
            cell = row.row(align=True)
            cell.operator("em.set_mode", text=label, icon=icon,
                          depress=(value == mode)).mode = value
        current = next(m for m in _MODES if m[0] == mode)
        layout.label(text=current[3], icon="INFO")

        # LA DIVERGENZA · dichiarato e reale non coincidono. Non si "ripara"
        # scrivendo la property da qui — scrivere mentre si disegna sporca il
        # file da solo, e soprattutto cancellerebbe la prova che qualcosa è
        # andato storto. Si dice.
        scarto = ops.divergenza(context)
        if scarto:
            riga = layout.box()
            riga.alert = True
            riga.label(text=scarto, icon="ERROR")
            riga.label(text="The declaration did not take: the panel shows "
                            "what is actually true.", icon="BLANK1")

        # L'ESITO DELL'ULTIMA TRANSIZIONE. Un rifiuto («Hub vuole una stanza»)
        # da un `update` callback non ha un operatore in cui atterrare, quindi
        # finirebbe solo in console — invisibile a chi ha appena scelto.
        ultima = ops.ULTIMA_TRANSIZIONE
        if ultima.get("message"):
            riga = layout.row()
            riga.alert = not ultima.get("ok", True)
            riga.label(text=str(ultima["message"])[:70],
                       icon="INFO" if ultima.get("ok") else "CANCEL")

    # ── 2 · C1 · i due capi guardano lo stesso documento? ───────────────────

    def _allineamento(self, layout, context):
        """Un avviso, non un errore: lavorare su documenti diversi con il canale
        aperto è legittimo (uno modella, l'altra scrive la narrazione). Non
        saperlo no — perché il sintomo è lo stesso di un canale chiuso.

        Compare SOLO quando l'altro capo ha dichiarato qualcosa di diverso: se
        non ha dichiarato niente non si conclude nulla e non si scrive nulla, e
        un «forse» permanente è la prima cosa che si impara a ignorare.
        """
        allineamento = ops.disallineamento(context)
        if allineamento["allineati"]:
            return
        avviso = layout.box()
        avviso.alert = True
        avviso.label(text="Different documents", icon="ERROR")
        avviso.label(text=allineamento["frase"], icon="BLANK1")
        avviso.label(text="A node id from over there will not be found here.",
                     icon="INFO")

    # ── 3 · NIGHT-RIM/C1 · l'ultimo messaggio in ingresso ───────────────────

    def _ultimo_in_ingresso(self, layout):
        """Gli scarti loggano, ma la console la guarda chi sviluppa: chi USA
        vede solo che la selezione non arriva. Questa riga rende la diagnosi
        visibile dove il problema si manifesta, e compare solo quando c'è
        qualcosa da dire."""
        ultimo = ops.ULTIMO_MESSAGGIO
        if not ultimo.get("esito"):
            return
        box = layout.box()
        testa = box.row(align=True)
        testa.label(text="Last inbound", icon="IMPORT")
        testa.label(text=ultimo["ora"])
        riga = box.row(align=True)
        #: `alert` solo per un'eccezione: uno scarto legittimo (il nostro eco,
        #: il cancello chiuso) non è un errore, e colorarlo di rosso
        #: insegnerebbe a non leggere il rosso.
        riga.alert = ultimo["esito"].startswith("ECCEZIONE")
        riga.label(text=f"{ultimo['tipo']}: {ultimo['esito']}")
        if ultimo.get("chiavi"):
            box.label(text=f"payload keys: {ultimo['chiavi']}", icon="BLANK1")

    # ── 4 · in una stanza: cosa mostra l'albero, e cosa puoi fare ───────────

    def _in_stanza(self, layout, context, status):
        box = layout.box()
        box.label(text=f"In {status['room_id']} · "
                       f"{status['members']} present", icon="COMMUNITY")
        if status.get("author"):
            box.label(text=f"As {status['author']}", icon="USER")
        else:
            box.label(text="No identity in the token: edits are dated, "
                           "not signed", icon="INFO")
        # THE ROLE, believed rather than assumed. A panel that offered editing
        # the server refuses would read as a broken addon instead of as a study
        # somebody let you read (same rule as EMStudio's badge).
        role = status.get("role")
        if status.get("can_write") is False:
            box.label(text=f"Read-only here ({role or 'viewer'}): the room "
                           f"refuses edits from this Blender", icon="LOCKED")
        elif role:
            box.label(text=f"Role: {role}", icon="CHECKMARK")
        box.label(text="The EM Data Tree is this room's container.",
                  icon="OUTLINER")
        # DP-76, consuming half. An ACTION and not a consequence of joining:
        # adopting a document is reading, downloading somebody's meshes into
        # your file is more.
        geo = box.column(align=True)
        geo.operator("em.materialise_geometry",
                     text="Materialise geometry from the store", icon="IMPORT")
        # C5 · «…anche all'adozione» non è più qui: è una preferenza
        # dell'add-on, perché si decide una volta e non a ogni sessione.
        geo.label(text="Only what lives in the store; an embargoed model is "
                       "skipped with a reason.", icon="INFO")

        self._archivio(box)

    def _archivio(self, box):
        """L'altra direzione, e un tipo di cosa DIVERSO: sopra si pubblica un
        bene di record, qui si tiene una copia opaca dell'officina. Disegnato
        nel blocco stanza perché passa dall'autenticazione della stanza, e
        piegato in una sua scatola perché non fa parte dello studio — niente,
        qui, è citabile."""
        safe = box.box()
        safe.label(text="Blend backups (safety, opaque)", icon="FILE_BACKUP")
        head = safe.row(align=True)
        head.operator("em.blend_backup_archive", text="Archive this .blend",
                      icon="EXPORT")
        head.operator("em.blend_backup_list", text="", icon="FILE_REFRESH")
        if bpy.data.is_dirty:
            safe.label(text="Unsaved changes: a snapshot keeps the file on "
                            "disk.", icon="ERROR")
        try:
            from . import backups as _backups
            snapshots, why = _backups.listing(), _backups.note()
        except Exception:  # noqa: BLE001 — a list that will not read is empty
            snapshots, why = [], ""
        if why:
            safe.label(text=why, icon="ERROR")
        for snap in snapshots[:8]:
            line = safe.row(align=True)
            sha = str(snap.get("sha256") or "")
            name = str(snap.get("label") or snap.get("filename") or "")
            line.label(text=f"{(name or sha[:12])[:28]} · "
                            f"{str(snap.get('created_at') or '')[:10]}")
            line.operator("em.blend_backup_restore", text="",
                          icon="IMPORT").sha256 = sha
        if snapshots:
            safe.label(text="Restore lands BESIDE this file — it never "
                            "replaces what you are working in.", icon="INFO")
        else:
            safe.label(text="Yours only: a room-mate's working file is not "
                            "yours to read.", icon="INFO")

    # ── 5 · C5 · I PERMESSI, e sono permessi ───────────────────────────────

    def _permessi(self, layout, context, running):
        """Non «impostazioni»: **permessi**, e ognuno con la riga che dice cosa
        consente. Solo mentre c'è un canale da governare — un permesso su un
        canale che non c'è è mobilia."""
        if not running:
            return
        box = layout.box()
        box.label(text="Permissions", icon="CHECKMARK")

        # C2 · UN CANCELLO SOLO, E STA DA CHI RICEVE.
        col = box.column(align=True)
        col.label(text="What EMStudio may land here", icon="IMPORT")
        col.prop(context.scene, "em_sync_accept", expand=True)
        col.label(text="Nothing leaves this side gated: what you do not send "
                       "looks lost.", icon="INFO")
        col.label(text="Refusing on arrival is something you can see yourself "
                       "doing.")

        # …E COSA RIFIUTA L'ALTRO CAPO. È la metà che rende vera la regola: un
        # cancello in ingresso è meglio di uno in uscita solo se chi sta
        # dall'altra parte può saperlo. Compare solo se l'ha dichiarato.
        suo = ops.dichiarazione_del_pari().get("accept")
        if suo and suo != "everything":
            riga = col.row()
            riga.alert = True
            riga.label(text=f"EMStudio accepts: {suo}", icon="CANCEL")
            col.label(text="What you send is arriving and being refused there "
                           "— not lost here.", icon="BLANK1")
        elif suo:
            col.label(text=f"EMStudio accepts: {suo}", icon="CHECKMARK")

        # CMD1 · il consenso ai comandi: un permesso più forte e separato —
        # questo lascia che EM Studio MODELLI IN QUESTA SCENA. Spento di
        # default, e mai implicato dal fatto che il canale sia aperto.
        cmd = box.column(align=True)
        cmd.prop(context.scene, "em_accept_commands",
                 text="EMStudio may model in this scene")
        if context.scene.em_accept_commands:
            cmd.label(text="It may create proxies and import geometry here.",
                      icon="CHECKMARK")
        else:
            cmd.label(text="Commands are refused (and EMStudio is told).",
                      icon="LOCKED")

    # ── 6 · dove sta questo Blender: la stanza (ogni sessione), il server ───

    def _dove(self, layout, context, status, running):
        acts = layout.box()
        acts.label(text="Where this Blender is", icon="PREFERENCES")

        if running:
            acts.label(text=f"ws://localhost:{ops.porta_sidecar()} · "
                            f"{ops.client_count()} client(s)", icon="URL")
        # C5 · la porta non si imposta più qui: non cambia quasi mai, e sta
        # nelle preferenze dell'add-on. Detto, con la strada per arrivarci —
        # una impostazione che sparisce senza una riga è una impostazione che
        # sembra rimossa.
        porta = acts.row(align=True)
        porta.label(text=f"Sidecar port {ops.porta_sidecar()}", icon="PLUGIN")
        porta.operator("em.open_addon_preferences", text="", icon="PREFERENCES")

        # THE LINK FIRST, because it is the way in that needs nothing typed:
        # `stratigraph://open?server=&room=` carries the place, EMtools signs in
        # for itself, and the fields below become the fallback rather than the
        # route.
        if not status["joined"]:
            acts.operator("em.room_open_link", text="Open room from link…",
                          icon="URL")

        col = acts.column(align=True)
        col.enabled = not status["joined"]
        col.label(text="…or by hand:", icon="GREASEPENCIL")
        # C5 · LA STANZA PRIMA DEL SERVER: il nome della stanza cambia a ogni
        # sessione, l'indirizzo del server ogni tanto. L'ordine è quello.
        col.prop(context.scene, "em_room_id", text="Room")
        col.prop(context.scene, "em_room_url", text="Server")
        # WHERE IS IT · a saved list (this installation's, not the .blend's) and
        # a probe. A URL somebody typed is a hope; `/v1/health` makes it a fact.
        # mDNS browsing is absent and NOT simulated — Blender's Python has no
        # `zeroconf`.
        find = col.row(align=True)
        find.operator("em.server_discover", text="Find", icon="VIEWZOOM")
        find.operator("em.server_probe", text="Probe", icon="CHECKMARK")
        try:
            from . import servers as _servers
            known = _servers.saved()
        except Exception:  # noqa: BLE001 — a list that will not read is empty
            known = []
        for entry in known[:6]:
            line = col.row(align=True)
            line.operator("em.server_use", text=entry.get("label") or entry["url"],
                          icon="WORLD").url = entry["url"]
            line.operator("em.server_forget", text="", icon="X").url = entry["url"]
        acts.operator(
            "em.room_join",
            text="Leave the room" if status["joined"] else "Join a room (Hub)…",
            icon="UNLINKED" if status["joined"] else "LINKED",
            depress=status["joined"])
        # ROUND-TRIP (emit-only): the same room, in EMStudio. Only while joined.
        if status["joined"]:
            acts.operator("em.room_open_elsewhere",
                          text="Open room in EMStudio", icon="WINDOW")
        if status.get("error"):
            acts.label(text=str(status["error"])[:60], icon="ERROR")


class EM_OT_mode_explain(bpy.types.Operator):
    """C4 · Restava da quando i chip erano un REFERTO: adesso sono premibili e
    chiamano `em.set_mode`. Tenuto registrato perché la frase che diceva è
    diventata la descrizione di quell'operatore, e perché un `bl_idname` che
    sparisce rompe un keymap di chi l'aveva legato."""

    bl_idname = "em.mode_explain"
    bl_label = "What this mode means"
    bl_description = ("Standalone / Sidecar / Hub — choosing one DOES it: "
                      "Sidecar starts the bridge, Standalone stops it, Hub "
                      "needs a room you have already joined.")

    mode: bpy.props.StringProperty(default="")  # type: ignore

    def execute(self, context):
        tip = next((m[3] for m in _MODES if m[0] == self.mode), "")
        self.report({"INFO"}, tip or self.bl_description)
        return {"FINISHED"}


def register():
    bpy.utils.register_class(EM_OT_mode_explain)
    bpy.utils.register_class(VIEW3D_PT_em_sync)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_em_sync)
    bpy.utils.unregister_class(EM_OT_mode_explain)
