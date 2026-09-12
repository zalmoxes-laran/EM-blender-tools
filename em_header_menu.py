"""Il menu **EM** nella testata della 3D View (EM16-UX/C, 11-09-2026).

Accanto a `GIS` di BlenderGIS, che è il vicino di riferimento.

## COSA CI VA, E COSA NO

Ci va ciò che è **raro e globale** — non ciò che è raro e contestuale. La
distinzione è la ragione per cui questo menu esiste: **un menu è un posto dove
le cose spariscono**, e far sparire un comando che serve mentre si lavora su un
oggetto è peggio che lasciarlo in fondo a un pannello. Convert 1.x→1.5 lo lanci
una volta per progetto; il proxy lo disegni cento volte al giorno.

Tre voci:

* **Utils** — i comandi che stavano nella sezione Utils dell'EM Data Tree
  (Convert 1.x→1.5, Create, Proxy Prefixes, Experimental e gli strumenti
  sperimentali). Quella sezione è sparita dal pannello.
* **Settings** — le preferenze dell'addon e le mapping preferences, che oggi si
  raggiungono per vie traverse.
* **About** — la versione di EM Tools **e** quella di s3dgraphy sotto il cofano,
  più i link al manuale e al sito. Le URL vengono da `version.json`, non sono
  inventate qui.

## I COMANDI A STATO

`layout.prop` sul booleano, non un operatore che lo ribalta: dentro un menu
Blender **rende già la spunta di attivo**, e costruirla a mano darebbe due
verità sullo stesso stato.
"""

from __future__ import annotations

import bpy  # type: ignore


def _docs_urls():
    """Le due URL dichiarate in `version.json`. Nessuna inventata qui."""
    import json
    import os
    base = os.path.dirname(__file__)
    try:
        with open(os.path.join(base, "version.json"), "r", encoding="utf-8") as f:
            docs = (json.load(f).get("docs") or {})
    except Exception:                                  # noqa: BLE001
        return {}
    return {k: (v or {}).get("url_base", "") for k, v in docs.items()}


def _s3dgraphy_version() -> str:
    """La versione di s3dgraphy VERAMENTE caricata, non quella attesa.

    È l'informazione che serve in un About: dopo `./em.sh s3d` il wheel
    vendorizzato e il modulo importato possono divergere, e la seconda è quella
    che conta per capire cosa sta girando.
    """
    try:
        import s3dgraphy
        return getattr(s3dgraphy, "__version__", "?") or "?"
    except Exception:                                  # noqa: BLE001
        return "not loaded"


class EM_MT_utils(bpy.types.Menu):
    """EM ▸ Utils — i comandi rari e globali, ex sezione Utils del Data Tree."""

    bl_idname = "EM_MT_utils"
    bl_label = "Utils"

    def draw(self, context):
        layout = self.layout
        em_tools = getattr(context.scene, "em_tools", None)

        layout.operator("graphml.convert_borders", text="Convert 1.x → 1.5",
                        icon='FILE_REFRESH')
        layout.operator("create.collection", text="Create collections",
                        icon='COLLECTION_NEW')
        layout.operator("em.manage_object_prefixes", text="Proxy Prefixes…",
                        icon='SYNTAX_ON')

        if em_tools is None:
            return
        layout.separator()
        # La spunta la disegna Blender: `prop` in un menu rende già lo stato.
        # Un operatore-interruttore qui darebbe due verità sullo stesso stato.
        layout.prop(em_tools, "experimental_features", text="Experimental")

        if em_tools.experimental_features:
            layout.separator()
            layout.operator("em.rebuild_graph_indices",
                            text="Rebuild graph indices", icon='FILE_REFRESH')
            layout.operator("em.benchmark_property_functions",
                            text="Benchmark property functions", icon='TIME')


class EM_MT_mode(bpy.types.Menu):
    """EM ▸ Mode — Standalone · Sidecar · Hub (C4, 13-09-2026).

    Qui e non solo nel pannello perché è **raro e globale**, che è il criterio
    di questo menu: in che modo sto lavorando si sceglie una volta per sessione,
    e riguarda tutto il progetto e non l'oggetto selezionato.

    **Operatori e non `layout.prop` sull'enum**, contro l'abitudine del resto di
    questo file: `prop` in un menu disegna già la spunta, ma una dichiarazione
    di modo può essere RIFIUTATA (Hub senza una stanza), e un rifiuto ha bisogno
    di un posto dove atterrare. `prop` non ne ha uno. La spunta la disegniamo
    noi, e mostra il modo **reale** — se dichiarato e reale divergono, la riga
    sotto lo dice invece di far finta.
    """

    bl_idname = "EM_MT_mode"
    bl_label = "Mode"

    def draw(self, context):
        from .sync_manager import operators as sync_ops

        layout = self.layout
        vero = sync_ops.session_mode(context)
        for valore, etichetta, spiega in sync_ops.SESSION_MODES:
            riga = layout.row()
            op = riga.operator(
                "em.set_mode",
                text=("● " if valore == vero else "    ") + etichetta,
                icon=('RADIOBUT_ON' if valore == vero else 'RADIOBUT_OFF'))
            op.mode = valore
        scarto = sync_ops.divergenza(context)
        if scarto:
            layout.separator()
            layout.label(text=scarto, icon='ERROR')
        ultima = sync_ops.ULTIMA_TRANSIZIONE
        if ultima.get("message"):
            layout.separator()
            layout.label(text=str(ultima["message"])[:70],
                         icon='INFO' if ultima.get("ok") else 'CANCEL')


class EM_MT_settings(bpy.types.Menu):
    """EM ▸ Settings — le preferenze, che oggi si raggiungono per vie traverse."""

    bl_idname = "EM_MT_settings"
    bl_label = "Settings"

    def draw(self, context):
        layout = self.layout
        layout.operator("emtools.open_mapping_preferences",
                        text="Mapping preferences…", icon='PRESET')
        layout.operator("em.open_addon_preferences",
                        text="Add-on preferences…", icon='PREFERENCES')


class EM_MT_about(bpy.types.Menu):
    """EM ▸ About — le due versioni e i due link."""

    bl_idname = "EM_MT_about"
    bl_label = "About"

    def draw(self, context):
        layout = self.layout
        from .em_setup.ui import get_em_tools_version
        layout.label(text=f"EM Tools {get_em_tools_version()}", icon='INFO')
        # …e s3dgraphy SOTTO IL COFANO: è la libreria che fa il lavoro, e dopo
        # un `./em.sh s3d` sapere quale sta girando è la prima domanda.
        layout.label(text=f"s3dgraphy {_s3dgraphy_version()}", icon='SCRIPTPLUGINS')

        urls = _docs_urls()
        layout.separator()
        if urls.get("em_tools"):
            op = layout.operator("wm.url_open", text="EM Tools manual",
                                 icon='HELP')
            op.url = urls["em_tools"]
        if urls.get("em"):
            op = layout.operator("wm.url_open",
                                 text="Extended Matrix documentation",
                                 icon='URL')
            op.url = urls["em"]


class EM_MT_header(bpy.types.Menu):
    """Il menu **EM** stesso: tre sottomenu e nient'altro."""

    bl_idname = "EM_MT_header"
    bl_label = "EM"

    def draw(self, context):
        layout = self.layout
        layout.menu("EM_MT_mode", icon='LINKED')
        layout.menu("EM_MT_utils", icon='TOOL_SETTINGS')
        layout.menu("EM_MT_settings", icon='PREFERENCES')
        layout.menu("EM_MT_about", icon='INFO')


class EM_OT_open_addon_preferences(bpy.types.Operator):
    """Le preferenze dell'addon. Esisteva già la stessa riga in tre punti
    (`google_credentials.py`, `EMdb_excel.py`, `mapping_preferences.py`): qui
    serve un operatore perché un menu non può chiamare `bpy.ops` inline."""

    bl_idname = "em.open_addon_preferences"
    bl_label = "Add-on Preferences"
    bl_description = "Open EM Tools' add-on preferences"

    def execute(self, context):
        try:
            bpy.ops.preferences.addon_show(module=__package__)
        except Exception as exc:                       # noqa: BLE001
            self.report({'WARNING'}, f"Could not open preferences: {exc}")
            return {'CANCELLED'}
        return {'FINISHED'}


def _draw_in_header(self, context):
    """Appeso a `VIEW3D_MT_editor_menus`, come fa BlenderGIS col suo `GIS`."""
    if context.mode == 'OBJECT':
        self.layout.menu("EM_MT_header")


_CLASSES = (
    EM_OT_open_addon_preferences,
    EM_MT_utils,
    EM_MT_mode,
    EM_MT_settings,
    EM_MT_about,
    EM_MT_header,
)


def register():
    for cls in _CLASSES:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
    bpy.types.VIEW3D_MT_editor_menus.append(_draw_in_header)


def unregister():
    try:
        bpy.types.VIEW3D_MT_editor_menus.remove(_draw_in_header)
    except Exception:                                  # noqa: BLE001
        pass
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except (RuntimeError, ValueError):
            pass
