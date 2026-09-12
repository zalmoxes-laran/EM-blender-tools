import bpy
import os
import textwrap
from bpy.props import EnumProperty

# Relative imports from parent modules
from ..import_operators.importer_graphml import EM_import_GraphML
from .. import icons_manager
from ..populate_lists import clear_lists, populate_blender_lists_from_graph
from ..functions import get_compatible_icon
from ..thumb_utils import reload_doc_previews_from_cache, has_doc_thumbs
from ..operators.graphml_converter import GRAPHML_OT_convert_borders
from ..import_operators.geom_georef import classify_georef_state, STATE_CONFIGURED
# XLSX_OT_to_graphml kept registered for F3 access but no longer used in panel UI
# from ..operators.xlsx_to_graphml import XLSX_OT_to_graphml

from s3dgraphy import get_graph, get_all_graph_ids


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_em_tools_version():
    """Legge la versione corrente dal manifest o da version.json come fallback"""
    try:
        # Prima prova a leggere dal manifest (che sarà sempre presente nel .blext)
        addon_dir = os.path.dirname(os.path.dirname(__file__))
        manifest_file = os.path.join(addon_dir, "blender_manifest.toml")

        if os.path.exists(manifest_file):
            with open(manifest_file, 'r') as f:
                manifest_content = f.read()

            # Cerca la versione principale nel manifest (non blender_version_min o altre versioni)
            # Pattern migliorato per catturare solo la versione principale
            import re
            version_match = re.search(r'^version\s*=\s*"([^"]+)"', manifest_content, re.MULTILINE)
            if version_match:
                return version_match.group(1)

        # Fallback su version.json (solo durante lo sviluppo)
        import json
        version_file = os.path.join(addon_dir, "version.json")

        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                config = json.load(f)

            # Genera la stringa di versione basata sul mode
            major = config.get('major', 1)
            minor = config.get('minor', 5)
            patch = config.get('patch', 0)
            mode = config.get('mode', 'dev')

            base = f"{major}.{minor}.{patch}"

            if mode == 'dev':
                dev_build = config.get('dev_build', 0)
                return f"{base}-dev.{dev_build}"
            elif mode == 'rc':
                rc_build = config.get('rc_build', 1)
                return f"{base}-rc.{rc_build}"
            else:  # stable
                return base

    except Exception as e:
        print(f"Error reading version information: {e}")

    # Fallback statico se non riesce a leggere
    return "unknown"


def validate_enum_value(obj, prop_name, get_items_func, context):
    """
    Valida che il valore di un EnumProperty esista ancora nella lista items.
    Se non esiste, lo resetta al default 'none'.

    Args:
        obj: Oggetto che contiene la proprietà (em_tools, graphml_file, aux_file)
        prop_name: Nome della proprietà (es: 'emdb_mapping')
        get_items_func: Funzione che genera gli items
        context: Blender context
    """
    try:
        if not hasattr(obj, prop_name):
            return False

        current_value = getattr(obj, prop_name)

        # Se è già 'none', ok
        if not current_value or current_value == 'none':
            return False

        # Ottieni la lista valida di items
        try:
            if callable(get_items_func):
                # Passa self e context alla funzione
                valid_items = get_items_func(obj, context)
            else:
                valid_items = get_items_func
        except Exception as e:
            print(f"[EMSetup] Error getting valid items for {prop_name}: {e}")
            return False

        # Estrai gli ID validi
        valid_ids = [item[0] for item in valid_items if len(item) > 0]

        # Se il valore corrente non è nella lista, resetta
        if current_value not in valid_ids:
            print(f"[EMSetup] Invalid {prop_name} value: '{current_value}' (not in {valid_ids}) - resetting to 'none'")
            setattr(obj, prop_name, 'none')
            return True  # Indica che c'è stata una modifica

        return False

    except Exception as e:
        print(f"Error validating {prop_name}: {e}")
        return False


def validate_all_mapping_enums(context):
    """
    Validates all EnumProperties that use dynamic mappings.
    Searches all locations where mappings may be stored.
    """
    from .properties import get_emdb_mappings, get_pyarchinit_mappings

    modified_count = 0

    try:
        if not hasattr(context, 'scene') or not hasattr(context.scene, 'em_tools'):
            print("[EMSetup] Cannot validate mappings: em_tools not found")
            return

        em_tools = context.scene.em_tools

        # 1. Valida le proprietà globali su em_tools
        print("Validating global mapping properties...")
        if validate_enum_value(em_tools, 'emdb_mapping', get_emdb_mappings, context):
            modified_count += 1
        if validate_enum_value(em_tools, 'pyarchinit_mapping', get_pyarchinit_mappings, context):
            modified_count += 1

        # 2. Valida i mapping nei GraphML files (se presenti)
        if hasattr(em_tools, 'graphml_files'):
            print(f"Validating {len(em_tools.graphml_files)} GraphML files...")
            for i, graphml_file in enumerate(em_tools.graphml_files):
                # 3. Valida gli auxiliary files
                if hasattr(graphml_file, 'auxiliary_files'):
                    print(f"  GraphML {i}: checking {len(graphml_file.auxiliary_files)} auxiliary files...")
                    for j, aux_file in enumerate(graphml_file.auxiliary_files):
                        if validate_enum_value(aux_file, 'emdb_mapping', get_emdb_mappings, context):
                            print(f"    - Reset auxiliary file {j} emdb_mapping")
                            modified_count += 1
                        if validate_enum_value(aux_file, 'pyarchinit_mapping', get_pyarchinit_mappings, context):
                            print(f"    - Reset auxiliary file {j} pyarchinit_mapping")
                            modified_count += 1

        if modified_count > 0:
            print(f"[EMSetup] Mapping validation complete: {modified_count} invalid values reset")
        else:
            print("[EMSetup] Mapping validation complete: all values valid")

    except Exception as e:
        print(f"Error in validate_all_mapping_enums: {e}")
        import traceback
        traceback.print_exc()


def get_mapping_description(mapping_file, mapping_type="emdb"):
    """Recupera la descrizione del mapping dal registry."""
    try:
        from s3dgraphy.mappings import mapping_registry

        # Usa il mapping type corretto
        registry_type = "emdb" if mapping_type == "emdb" else "pyarchinit"

        mapping_data = mapping_registry.load_mapping(mapping_file, registry_type)
        return mapping_data
    except Exception as e:
        print(f"Error loading mapping description: {str(e)}")
        return None


def _draw_wrapped_text(layout, context, text, icon=None, first_prefix="", next_prefix=""):
    """Draw text wrapped to current sidebar width."""
    region_width = getattr(context.region, "width", 320)
    # Approximate characters that fit in the N-panel width.
    wrap_width = max(32, min(110, int((region_width - 90) / 6.6)))

    wrapped_lines = textwrap.wrap(
        text.strip(),
        width=wrap_width,
        break_long_words=False,
        break_on_hyphens=False,
    )

    if not wrapped_lines:
        return

    for idx, wrapped in enumerate(wrapped_lines):
        prefix = first_prefix if idx == 0 else next_prefix
        line_text = f"{prefix}{wrapped}"
        if icon and idx == 0:
            layout.label(text=line_text, icon=icon)
        else:
            layout.label(text=line_text)


#: How many individual lines a warning family shows before collapsing into a
#: "… and N more of the same" tail. The point of the panel is that the author
#: recognises the PROBLEM; the exhaustive list belongs to the console.
_MAX_WARNINGS_PER_GROUP = 8


def _imported_warnings(active_file):
    """The import warnings for ``active_file``: records where the source knew
    what a warning was about, plain strings for the rest.

    The two are MERGED, not chosen between. Only the state families come with a
    record; the free-form warnings a source also emits — a duplicate extractor
    name, a malformed field — have none, and preferring the records alone would
    quietly drop them. ``digest_warnings`` takes the mixture and files each by
    kind or by text as appropriate.
    """
    records = []
    raw = getattr(active_file, "import_warning_records", "") or ""
    if raw:
        try:
            import json
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                records = [r for r in parsed if isinstance(r, dict)]
        except (ValueError, TypeError):
            records = []  # malformed cache: fall back to the strings alone

    covered = {(r.get("message") or "").strip() for r in records}
    text = getattr(active_file, "import_warnings", "") or ""
    extra = [line.strip() for line in text.split("\n")
             if line.strip() and line.strip() not in covered]
    return records + extra


def _draw_warning_row(layout, context, message, record):
    """One warning line, with a reveal button when it points somewhere.

    The button carries the element id, and — for a degraded connection — the
    relations the datamodel would allow, in its tooltip. Those are shown as
    INFORMATION: which relation the edge should have carried is an authorial
    decision taken in the source graph, never something a click here rewrites.
    """
    node_id = record.get("node_id") if isinstance(record, dict) else None
    if not node_id:
        _draw_wrapped_warning(layout, context, message)
        return
    row = layout.row(align=True)
    op = row.operator("em.reveal_warning_node", text="",
                      icon='RESTRICT_SELECT_OFF', emboss=False)
    op.node_id = node_id
    candidates = record.get("candidates") or []
    if candidates:
        op.candidates = ", ".join(str(c) for c in candidates)
    _draw_wrapped_warning(row.column(align=True), context, message)


def _format_version_banner(active_file):
    """S6 version banner for ``active_file`` — the versions recorded at import.

    Returns "" when nothing is known, in which case the panel draws no banner
    at all rather than a row of dashes.
    """
    from .version_banner import format_banner
    source = ""
    fmt = getattr(active_file, "file_format", "") or ""
    if fmt:
        source = "em.json" if str(fmt).upper() == "EMJSON" else "GraphML"
    return format_banner(
        {
            "emjson_schema": getattr(active_file, "emjson_schema_version", ""),
            "em_datamodel": getattr(active_file, "em_datamodel_version", ""),
            "stratigraph": getattr(active_file, "stratigraph_version", ""),
        },
        source_label=source,
    )


def _draw_wrapped_warning(layout, context, text, bullet="- "):
    """Draw warning text wrapped to current sidebar width."""
    _draw_wrapped_text(
        layout,
        context,
        text,
        first_prefix=bullet,
        next_prefix="  ",
    )


def _draw_experimental_notice(layout, context):
    """Draw compact note for experimental sections."""
    note_box = layout.box()
    _draw_wrapped_text(
        note_box,
        context,
        "Sections marked with the Experimental symbol are experimental: \\" 
        "only use them on files with backups.",
        icon='INFO',
    )

def _draw_graphml_wizard(layout, context, em_tools):
    """Legacy GraphML wizard (stratigraphy + em_paradata two-file flow).

    **No UI currently calls this function**, and it has not for some time: the panel
    that used to (``VIEW3D_PT_graphml_wizard_bridge``) was renamed and repointed at
    the StratiMiner panel, which SM3 has now removed with the rest of that flow.
    Kept rather than deleted because what it draws — stratigraphy.xlsx + paradata →
    GraphML — is an IMPORT path, not StratiMiner authoring, and reviving it is a
    decision about the legacy two-file format rather than about this cut.

    Its "AI Extraction Prompt" block is gone: that was the same
    ``get_ai_prompt`` authoring that moved to EMStudio (SM1/SM2), and it referenced
    ``xlsx_wizard_prompt_part_a``…``_d``, which are declared nowhere in
    ``em_props`` — so the block would have raised the first time it was drawn.
    """
    graphml_box = layout.box()
    row = graphml_box.row(align=True)
    row.prop(
        em_tools,
        "exp_create_graphml_expanded",
        text="GraphML Wizard (Experimental)",
        icon="TRIA_DOWN" if em_tools.exp_create_graphml_expanded else "TRIA_RIGHT",
        emboss=False
    )
    row.label(text="", icon='EXPERIMENTAL')
    help_op = row.operator("em.help_popup", text="", icon='QUESTION')
    help_op.title = "Create a GraphML"
    help_op.text = (
        "Legacy wizard for creating an Extended Matrix\n"
        "GraphML from a stratigraphy Excel. The unified\n"
        "em_data.xlsx flow in the EM Bridge panel is the\n"
        "preferred path."
    )
    help_op.url = "tutorials/16-mapping-tool-excel.html"

    if not em_tools.exp_create_graphml_expanded:
        return

    # ── STEP 1: Convert Stratigraphy ──
    step1_box = graphml_box.box()
    row = step1_box.row(align=True)
    row.label(text="Step 1: Convert Stratigraphy", icon='IMPORT')
    help_op = row.operator("em.help_popup", text="", icon='QUESTION')
    help_op.title = "Step 1 — Convert Stratigraphy"
    help_op.text = (
        "Load a stratigraphy.xlsx file and convert it\n"
        "to an s3dgraphy graph in memory. The Excel must\n"
        "follow the 24-column template. Download the\n"
        "template using the button below."
    )
    help_op.url = "tutorials/16-mapping-tool-excel.html"
    step1_box.prop(em_tools, "xlsx_wizard_strat_file", text="Excel File")
    step1_box.prop(em_tools, "xlsx_wizard_mapping", text="Mapping")

    can_convert = bool(em_tools.xlsx_wizard_strat_file)
    row = step1_box.row()
    row.scale_y = 1.3
    row.enabled = can_convert
    row.operator(
        "xlsx_wizard.convert_stratigraphy",
        text="Convert to Graph",
        icon='GRAPH'
    )

    has_graph = bool(em_tools.xlsx_wizard_graph_id)
    if has_graph:
        # Show graph stats from memory
        try:
            from s3dgraphy import get_graph as _get_graph
            _g = _get_graph(em_tools.xlsx_wizard_graph_id)
            if _g:
                step1_box.label(
                    text=f"Graph in memory: {len(_g.nodes)} nodes, {len(_g.edges)} edges",
                    icon='CHECKMARK'
                )
            else:
                step1_box.label(text="Graph expired — re-run Step 1", icon='ERROR')
                has_graph = False
        except Exception:
            step1_box.label(text="Graph loaded", icon='CHECKMARK')

    # ── STEP 2: Export GraphML (experimental — write-back not production-ready) ──
    if em_tools.experimental_features:
        step3_box = graphml_box.box()
        step3_box.enabled = has_graph
        row = step3_box.row(align=True)
        row.label(text="Step 2: Export GraphML", icon='EXPORT')
        help_op = row.operator("em.help_popup", text="", icon='QUESTION')
        help_op.title = "Step 2 — Export GraphML"
        help_op.text = (
            "Save the in-memory graph as a GraphML file.\n"
            "Then import it via File > Import EM file to\n"
            "populate the Blender lists and scene."
        )
        help_op.url = "tutorials/16-mapping-tool-excel.html"
        step3_box.prop(em_tools, "xlsx_wizard_output_path", text="Output Path")

        can_export = has_graph and bool(em_tools.xlsx_wizard_output_path)
        row = step3_box.row()
        row.scale_y = 1.3
        row.enabled = can_export
        row.operator(
            "xlsx_wizard.export_graphml",
            text="Export GraphML",
            icon='FILE_TICK'
        )

    # ── Wizard Warnings ──
    if em_tools.xlsx_wizard_warnings:
        warnings_list = [w for w in em_tools.xlsx_wizard_warnings.split("\n") if w.strip()]
        if warnings_list:
            graphml_box.separator(factor=0.5)
            warn_box = graphml_box.box()
            warn_box.alert = True
            header_row = warn_box.row(align=True)
            icon = 'TRIA_DOWN' if em_tools.xlsx_wizard_show_warnings else 'TRIA_RIGHT'
            header_row.prop(
                em_tools, "xlsx_wizard_show_warnings",
                text=f"Wizard Warnings ({len(warnings_list)})",
                icon=icon,
                emboss=False
            )
            header_row.label(text="", icon='ERROR')
            header_row.operator("xlsx_wizard.clear_warnings", text="", icon='X')
            if em_tools.xlsx_wizard_show_warnings:
                warn_col = warn_box.column(align=True)
                for w in warnings_list:
                    _draw_wrapped_warning(warn_col, context, w)

    # ── Templates ──
    graphml_box.separator(factor=0.5)
    row = graphml_box.row(align=True)
    row.label(text="Templates:", icon='FILE_NEW')
    help_op = row.operator("em.help_popup", text="", icon='QUESTION')
    help_op.title = "Excel Templates"
    help_op.text = (
        "Download empty Excel templates to fill manually\n"
        "or use as reference for AI-assisted extraction.\n"
        "stratigraphy.xlsx: 24-column stratigraphic data.\n"
        "em_paradata.xlsx: per-property provenance data."
    )
    help_op.url = "tutorials/16-mapping-tool-excel.html"
    row = graphml_box.row(align=True)
    row.scale_y = 0.9
    row.operator(
        "emtools.save_stratigraphy_template",
        text="Save Stratigraphy Template",
        icon='FILE_TICK'
    )
    row.operator(
        "emtools.save_em_paradata_template",
        text="Save Paradata Template",
        icon='FILE_TICK'
    )


# ============================================================================
# UI CLASSES
# ============================================================================

class AUXILIARY_UL_files(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)


            if item.file_type == "emdb_xlsx":
                row.label(text="", icon_value=icons_manager.get_icon_value("EMdb_logo"))

            elif item.file_type == "pyarchinit":
                row.label(text="", icon_value=icons_manager.get_icon_value("pyarchinit"))

            elif item.file_type == "dosco":
                row.label(text="", icon_value=icons_manager.get_icon_value("em_logo"))

            elif item.file_type == "source_list":
                row.label(text="", icon='TEXT')

            elif item.file_type == "generic_xlsx":
                row.label(text="", icon='SPREADSHEET')

            elif item.file_type == "resource_collection":
                row.label(text="", icon='FILE_FOLDER')

            # Nome file
            row.prop(item, "name", text="", emboss=False)

            # Stato del file
            if item.file_type == "resource_collection":
                # Resource collections need resource_folder, not filepath
                if item.resource_folder:
                    row.label(text="", icon='CHECKMARK')
                else:
                    row.label(text="", icon='ERROR')
            elif item.filepath or item.dosco_folder:
                row.label(text="", icon='CHECKMARK')
            else:
                row.label(text="", icon='ERROR')

            # Quick actions
            #row.operator("auxiliary.reload", text="", icon="FILE_REFRESH", emboss=False).file_index = index
            row.operator("auxiliary.import_now", text="", icon="FILE_REFRESH", emboss=False)

           # ✅ NUOVO: Icona toggle per auto-reload
            icon_auto = 'CHECKBOX_HLT' if item.auto_reload_on_em_update else 'CHECKBOX_DEHLT'
            row.prop(item, "auto_reload_on_em_update", text="", icon=icon_auto, emboss=False)


class EMTOOLS_UL_files(bpy.types.UIList):
    """UIList to display the GraphML files with icons to indicate graph presence and actions"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        """Disegna un elemento nella lista dei GraphML."""

        # Prova tutti gli ID possibili per trovare il grafo
        graph_data = None
        if item.name:
            graph_data = get_graph(item.name)

        # Se non riesce a trovare il grafo con il nome attuale, prova con l'ID originale
        if not graph_data and hasattr(item, 'original_id') and item.original_id:
            graph_data = get_graph(item.original_id)

        is_graph_present = bool(graph_data and hasattr(graph_data, 'nodes') and len(graph_data.nodes) > 0)

        status_icon = get_compatible_icon('SEQUENCE_COLOR_04') if is_graph_present else get_compatible_icon('SEQUENCE_COLOR_01')

#        # Aggiungi checkbox per pubblicabilità
#        row = layout.row()
#        row.prop(item, "is_publishable", text="")

        # Mostra il nome del file nella lista
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Mostra il codice del grafo (graph_code) invece del nome (UUID)
            graph_code = item.graph_code if hasattr(item, 'graph_code') and item.graph_code else item.name

            # Mostra il graph_code con icona NODE_SOCKET colorata per rimando visivo
            try:
                from ..stratigraphy_manager.ui import _get_graph_icon
                socket_icon = _get_graph_icon(graph_code)
            except ImportError:
                socket_icon = 'NODE_SOCKET_OBJECT'
            layout.label(text=graph_code, icon=socket_icon)

            # Mostra l'icona di stato
            row = layout.row()
            row.label(text="", icon=status_icon)

            # Pulsante per ricaricare il grafo (icona FILE_REFRESH) — dispatch
            # sul formato dell'entry: em.json usa l'importer em.json, altrimenti
            # GraphML. Senza questo, ricaricare un entry em.json lo parserebbe
            # come XML ("not well-formed").
            row = layout.row(align=True)
            if getattr(item, "file_format", "GRAPHML") == "EMJSON":
                op = row.operator("import.em_emjson", text="", icon="FILE_REFRESH", emboss=False)
                op.file_index = index
            else:
                op = row.operator("import.em_graphml", text="", icon="FILE_REFRESH", emboss=False)
                op.graphml_index = index

            # Disabilita il pulsante se l'icona è rossa (grafo non esistente)
            if is_graph_present:
                # Pulsante per aprire nel Graph Viewer (experimental only)
                if hasattr(context.scene, 'em_tools') and context.scene.em_tools.experimental_features:
                    row = layout.row(align=True)
                    op = row.operator("graphedit.draw_graph", text="", icon='NODETREE', emboss=False)
                    op.graphml_index = index  # Passa l'indice del graphml

                # Pulsante per aggiornare le liste (con icona FILE_REFRESH)
                row = layout.row(align=True)
                op = row.operator("em_tools.populate_lists", text="", icon="SEQ_SEQUENCER", emboss=False)
                op.graphml_index = index  # Passa l'indice corretto per aggiornare le liste

                row = layout.row(align=True)
                # Flag pubblicabile (come in rm_manager)
                if hasattr(item, 'is_publishable'):
                    row.prop(item, "is_publishable", text="", icon_value=icons_manager.get_icon_value("em_publish") if item.is_publishable else icons_manager.get_icon_value("em_no_publish"))

                else:
                    # Se la proprietà non esiste ancora, mostra un pulsante disabilitato
                    row.label(text="", icon='QUESTION')
            else:
                # NODETREE placeholder: solo se experimental, per simmetria col bottone attivo (riga 530)
                if hasattr(context.scene, 'em_tools') and context.scene.em_tools.experimental_features:
                    row = layout.row()
                    row.enabled = False
                    row.label(text="", icon='NODETREE')
                row = layout.row()
                row.enabled = False  # Disabilita il layout (grigio)
                row.label(text="", icon="SEQ_SEQUENCER")  # Usa un'icona per mostrare un pulsante disabilitato
                row = layout.row()
                row.enabled = False
                if hasattr(item, 'is_publishable'):
                    row.prop(item, "is_publishable", text="", icon_value=icons_manager.get_icon_value("em_publish") if item.is_publishable else icons_manager.get_icon_value("em_no_publish"))
                else:
                    # Se la proprietà non esiste ancora, mostra un pulsante disabilitato
                    row.label(text="", icon='QUESTION')



        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=graph_code)


# NIGHT-RIM/A5 · `EM_OT_promotion_step_info` è cancellato, e con esso
# `em_setup/promotion_scale.py`. Erano il tooltip e le parole della scala di
# promozione, non raggiungibili da nessun pannello da quando E.D. ha
# eliminato l'EM Overview (UX3/A). Git li ricorda; una prova impedisce che
# tornino per sbaglio.

#: I due valori che `graph_code` prende quando un codice vero non c'è.
#: `MISSINGCODE` lo assegna s3Dgraphy quando il GraphML non ne porta uno
#: (`importer/import_graphml.py`); `site_id` è il segnaposto del template.
#: Il banner di warning più sotto li elenca, e la lista sta in un posto solo.
GRAPH_CODE_SEGNAPOSTO = ("site_id", "MISSINGCODE")


def _grafi_caricati(em_tools):
    """`[(etichetta, grafo), …]` per le entry con un grafo DAVVERO caricato.

    Serve a `EM_SetupPanel._catena` per sapere quanti grafi sono caricati in
    tutto — cioè se la guida a tre passi va mostrata (solo per il primo
    grafo) o no.

    Due cose prese dalla UIList dei grafi (`EMTOOLS_UL_files.draw_item`),
    perché questo pannello e quella lista devono dire la stessa cosa:

    * il **ripiego su `original_id`** quando `get_graph(nome)` non trova
      nulla: dopo un rename l'entry non trova più il grafo col nome nuovo, e
      contare un grafo in meno in silenzio è peggio che copiare due righe;
    * l'**etichetta**, che è `graph_code` e non `name` — dopo un import
      `name` è l'UUID del grafo. Un `graph_code` SEGNAPOSTO non fa da
      etichetta: con due entry senza codice si leggeva due volte
      «MISSINGCODE», che non distingue niente.

    NIGHT-RIM/A5: questa definizione è stata cancellata per sbaglio insieme
    all'operatore della scala che le stava accanto, e l'ha ripresa la prova
    strutturale di UX3 (`test_OGNI_FUNZIONE_DI_MODULO_CHIAMATA_ESISTE`) —
    la seconda volta che quell'errore capita e la prima che qualcuno lo
    prende al posto mio.
    """
    from s3dgraphy import get_graph
    fuori = []
    for gf in getattr(em_tools, "graphml_files", ()) or ():
        g = get_graph(gf.name)
        if not g and getattr(gf, "original_id", ""):
            g = get_graph(gf.original_id)
        if g is not None and getattr(g, "nodes", None):
            codice = getattr(gf, "graph_code", "")
            if codice in GRAPH_CODE_SEGNAPOSTO:
                codice = ""
            fuori.append((codice or gf.name, g))
    return fuori


class EM_SetupPanel(bpy.types.Panel):

    bl_label = "EM Data Tree"
    bl_idname = "VIEW3D_PT_EM_Tools_Setup"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM"
    bl_order = 1


    # ── C3 (EM16-UX2) · LA VERSIONE A DESTRA, E IL TITOLO INTERO ─────────
    #
    # B4 aveva tolto la versione dal titolo e messa in `draw_header`. Sbagliato
    # a video: `draw_header` disegna nella striscia PRIMA del titolo, quindi la
    # versione finiva a sinistra, troncata, davanti al nome — `⧗ 1.6.0-de… EM
    # Data Tree`. Con `alignment = 'RIGHT'` si allinea dentro quella striscia,
    # che resta a sinistra del titolo: allineare non sposta.
    #
    # `draw_header_preset` è la striscia a DESTRA (quella dove i pannelli
    # nativi mettono i preset), e non contende spazio al titolo. Se a pannello
    # stretto Blender taglia, taglia la versione e non il nome del pannello —
    # che è il comportamento che si vuole.
    #
    # E via l'icona. Era `template_icon(icon_value=get_icon_value("em_logo"))`,
    # che E.D. legge come «una clessidra che non significa niente». Misurato:
    # `em_logo` È nell'elenco delle icone caricate (`icons_manager.py:54` →
    # `em_logo_small.png`, presente), e `template_icon` ha `scale` di default
    # 1.0 — quindi né icona mancante né icona sovradimensionata. La causa vera
    # del glifo non l'ho identificata da un Blender in background (gli
    # `icon_id` delle preview valgono 0 senza GUI), e non l'ho inventata: qui
    # si fa quello che la revisione chiede, cioè togliere. Se la si vuole
    # rimettere, la forma giusta è quella che questo stesso file usa alla riga
    # 483 — `label(text="", icon_value=…)`, che disegna a dimensione icona.
    def draw_header_preset(self, context):
        layout = self.layout
        layout.label(text=get_em_tools_version())


    # ══════════════════════════════════════════════════════════════════
    # UX3/B · la catena «aggiungi → path → carica», e i pezzi che la dicono
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _kw_icona(custom, builtin):
        """Gli argomenti-icona per `label`/`operator`: la nostra se c'è.

        `icons_manager.get_icon_value()` torna **0** quando la collezione
        previews non è caricata o il file manca, e `icon_value=0` disegna il
        vuoto — non un ripiego. Quindi lo zero va controllato qui, e in quel
        caso si passa l'icona di Blender.

        REGRESSIONE DA NON RIFARE: UX3 aveva portato via questo metodo per
        sbaglio, insieme al `_draw_promotion_scale` che gli stava accanto.
        `_draw_graph_info` lo chiama, quindi aprire `Graph info` sollevava
        `AttributeError` a metà del disegno e Blender smetteva di disegnare
        lì: a video si vedeva l'etichetta `US/USV` e poi il pannello finiva,
        senza Epochs, Properties, Documents, EM Warnings e Auxiliary
        Resources. C'è una prova che adesso verifica che ogni `self._x(`
        chiamato in una classe sia DEFINITO in quella classe.
        """
        if custom:
            valore = icons_manager.get_icon_value(custom)
            if valore:
                return {"icon_value": valore}
        return {"icon": builtin}

    @staticmethod
    def _catena(context, em_tools):
        """Dove siamo nella catena. Un dizionario, letto da tutto il resto.

        Lo stato lo calcolo UNA volta per ridisegno e lo passo in giro: se
        ogni pezzo se lo ricalcolasse, i pezzi potrebbero non essere
        d'accordo fra loro — ed è esattamente il modo in cui un'interfaccia
        a stati si contraddice.

        `caricato` usa lo stesso test della UIList dei grafi (grafo presente
        E con nodi), ripiego su `original_id` compreso: un grafo «presente»
        ma vuoto non è caricato, e `em_tools.populate_lists` lo rifiuta per
        la stessa ragione.
        """
        files = getattr(em_tools, "graphml_files", None)
        idx = getattr(em_tools, "active_file_index", -1)
        attivo = None
        if files and 0 <= idx < len(files):
            attivo = files[idx]

        stato = {
            "ha_grafo": bool(files and len(files)),
            "attivo": attivo,
            "indice": idx,
            "ha_path": bool(attivo and getattr(attivo, "graphml_path", "")),
            "caricato": False,
            "emjson": (attivo is not None
                       and getattr(attivo, "file_format", "GRAPHML") == "EMJSON"),
            # Quanti grafi sono caricati IN TUTTO, non solo l'attivo: è ciò
            # che distingue «non ho ancora mai visto un contenuto» da «ne ho
            # già uno e sto aggiungendo il secondo».
            #
            # È DERIVATO dallo stato vivo, e questa è la parte che conta: un
            # flag «l'utente ha già visto la guida» salvato da qualche parte
            # sarebbe stato che può mentire — resta acceso dopo che il grafo
            # è stato rimosso, non segue un file .blend che cambia mano, e
            # quando mente non c'è modo di accorgersene guardando. Contare i
            # grafi caricati non può desincronizzarsi da niente, perché non è
            # una memoria: è una domanda fatta ogni volta.
            "grafi_caricati": len(_grafi_caricati(em_tools)),
        }
        if attivo is not None:
            try:
                from s3dgraphy import get_graph
                g = get_graph(attivo.name)
                if not g and getattr(attivo, "original_id", ""):
                    g = get_graph(attivo.original_id)
                stato["caricato"] = bool(
                    g is not None and getattr(g, "nodes", None))
            except Exception:                       # noqa: BLE001
                stato["caricato"] = False
        return stato

    @staticmethod
    def _guida_richiesta():
        """La guida è accesa nelle preferenze? In dubbio, SÌ.

        Il ripiego su `True` non è pigrizia: è il comportamento che c'era
        prima della preferenza, e una preferenza che non si riesce a leggere
        non deve cambiare quello che l'utente vede. L'accessore sta nella
        radice del pacchetto perché da un sottomodulo `__package__` non è la
        chiave giusta — vedi `get_addon_preferences`.
        """
        try:
            from .. import get_addon_preferences
            prefs = get_addon_preferences()
        except Exception:                           # noqa: BLE001
            return True
        if prefs is None:
            return True
        return bool(getattr(prefs, "show_setup_guide", True))

    @staticmethod
    def _guida(layout, stato):
        """I tre passi numerati, col loro stato.

        `ui_helpers.draw_requirement_row` esiste già e fa esattamente questo
        — numero, icona di stato, hint, riga dimmata per i passi non ancora
        valutabili — quindi non ne scrivo una seconda: `inactive` è il
        parametro che distingue «sbagliato» da «tocca più tardi», che è la
        distinzione che rende una lista di passi leggibile.
        """
        from ..ui_helpers import draw_requirement_row
        box = layout.box()
        box.label(text="To see a content:", icon='INFO')
        draw_requirement_row(
            box, 1, "Add graph", stato["ha_grafo"],
            hint="Press + to create an EM graph slot")
        draw_requirement_row(
            box, 2, "Set path", stato["ha_path"],
            hint="Point Path to a .graphml or .em.json file",
            inactive=not stato["ha_grafo"])
        draw_requirement_row(
            box, 3, "Load", stato["caricato"],
            hint="Press Load to read the file into the graph",
            inactive=not stato["ha_path"])

    @staticmethod
    def _op_carica(layout, stato, testo=""):
        """Il comando di caricamento, col dispatch sul formato.

        Due importer e non uno: un entry `em.json` passato all'importer
        GraphML verrebbe parsato come XML («not well-formed»). È lo stesso
        dispatch che fa la UIList sul bottone FILE_REFRESH — e il nome della
        proprietà dell'indice è diverso fra i due (`file_index` contro
        `graphml_index`), che è la ragione per cui questo pezzo sta in una
        funzione sola invece che copiato nei due punti che lo usano.
        """
        if stato["emjson"]:
            op = layout.operator("import.em_emjson", text=testo,
                                 icon='IMPORT' if testo else 'FILE_REFRESH')
            op.file_index = stato["indice"]
        else:
            op = layout.operator("import.em_graphml", text=testo,
                                 icon='IMPORT' if testo else 'FILE_REFRESH')
            op.graphml_index = stato["indice"]
        return op

    def _riga_comandi(self, context, layout, em_tools, scene, stato):
        """I sei comandi sui file EM, tutti della stessa dimensione.

        La larghezza piena la dà `grid_flow(columns=…, even_columns=True)`:
        un bottone icona-sola (`text=""`) in un `row()` piatto prende la sua
        larghezza NATURALE — quadrata — e la riga non gli passa lo spazio che
        avanza. Misurato a video in UX2, dopo che togliere `ui_units_x` non
        era bastato. `scale_y` per l'altezza.

        Restano icona-sola: i tooltip fanno da etichetta e sono quelli degli
        operatori (`bl_description`), tutti parlanti. Dove il bottone è
        spento la ragione la dice `poll_message_set` nei poll di
        `export.em_save` / `export.em_saveas`: spento con la ragione insegna,
        spento muto fa sembrare l'add-on rotto.

        Il separatore stacca Remove graph, che è l'unico distruttivo (e
        conserva la sua conferma), dagli altri.
        """
        # Sette celle: sei comandi più Reload, che UX3 ha portato nella riga
        # (a grafo caricato il caricamento è un'azione ripetibile, non un
        # passo da fare).
        #
        # Il separatore di Remove sta DENTRO la sua cella e non è una cella
        # sua: come cella ottava mandava la riga a capo su due righe —
        # misurato a video, `grid_flow` decideva quattro colonne e ne
        # impilava tre sotto.
        cmd = layout.grid_flow(row_major=True, columns=7,
                               even_columns=True, even_rows=False,
                               align=True)
        cmd.scale_y = 1.3
        cmd.row(align=True).operator('em_tools.add_file', text="",
                                     icon='ADD')

        # Reload: a grafo caricato il comando di caricamento vive QUI, come
        # icona, perché è un'azione ripetibile e non più un passo da fare.
        ricarica = cmd.row(align=True)
        ricarica.enabled = stato["ha_path"]
        self._op_carica(ricarica, stato)

        cmd.row(align=True).operator('export.em_save', text="",
                                     icon='FILE_TICK')
        cmd.row(align=True).operator('export.em_saveas', text="",
                                     icon='FILE_NEW')

        # Multigraph Mode: è un comando sui file EM come gli altri. Lo stato
        # lo rende l'icona (WORLD accesa / WORLD_DATA spenta, con `depress`),
        # non una parola.
        _loaded = []
        for _gf in getattr(em_tools, "graphml_files", ()) or ():
            if getattr(_gf, 'is_graph', False):
                _loaded.append(_gf)
            else:
                from s3dgraphy import get_graph as _gg
                if _gg(_gf.name):
                    _loaded.append(_gf)
        _attiva = getattr(scene, 'landscape_mode_active', False)
        multi = cmd.row(align=True)
        multi.enabled = _attiva or len(_loaded) >= 2
        _op = multi.operator("em.toggle_landscape_mode", text="",
                             icon='WORLD' if _attiva else 'WORLD_DATA',
                             depress=_attiva)
        _op.enable = not _attiva

        _iop = cmd.row(align=True).operator("wm.call_menu", text="",
                                            icon='INFO')
        _iop.name = "EM_MT_LandscapeInfo"

        # …e per ultimo il distruttivo, staccato dal separatore che sta
        # nella sua stessa cella.
        via = cmd.row(align=True)
        via.separator()
        via.operator('em_tools.remove_file', text="", icon='REMOVE')

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_tools = scene.em_tools

        # ========================================================================
        # WHOSE DOCUMENT IS THIS? (the room, when there is one)
        # ========================================================================
        # The design turn: the room is the primitive and **the tree IS the room's
        # container** when you are in one (EM_design_room-come-workspace §3). The
        # adopt already fills it; this says so at the top, because a tree that
        # looks local while it is somebody's shared room is a tree you edit with
        # the wrong expectations. Leave the room and the line disappears — the
        # tree is local again, which is also true.
        try:
            from ..sync_manager import operators as _sync_ops
            _room = _sync_ops.room_status(context)
            if _room.get("joined"):
                room_box = layout.box()
                room_box.label(
                    text=f"In {_room.get('room_id')} · "
                         f"{_room.get('members', 0)} present"
                         + (f" · as {_room['author']}" if _room.get("author") else ""),
                    icon="COMMUNITY")
                if _room.get("can_write") is False:
                    room_box.label(
                        text=f"Read-only ({_room.get('role') or 'viewer'}) — "
                             f"the room refuses edits from here", icon="LOCKED")
        except Exception:  # noqa: BLE001 — the tree must draw without the bridge
            pass

        # ========================================================================
        # WORKING METHODS SECTION
        # ========================================================================

        box = layout.box()
        row = box.row(align=True)
        split = row.split()
        col = split.column()

        activemode_label = ""
        active_label = ""
        # Cambia l'etichetta del pulsante in base alla modalità attiva
        if em_tools.mode_em_advanced:
            activemode_label = "Switch to 3D GIS"
            active_label = "Active Mode: EM"
        else:
            activemode_label = "Switch to EM"
            active_label = "Active Mode: 3D GIS"

        # Disegna il pulsante
        col.label(text=active_label)
        col = split.column()
        col.operator("emtools.switch_mode", text=activemode_label)

        if not em_tools.mode_em_advanced and len(em_tools.graphml_files) > 0:
            warn_col = box.column(align=True)
            warn_col.alert = True
            _draw_wrapped_text(
                warn_col,
                context,
                "Warning: Starting from a blank file is strongly recommended",
                icon='ERROR',
            )
            _draw_wrapped_text(
                warn_col,
                context,
                "when working in Basic 3D GIS mode with existing Advanced EM graphs.",
            )

        # ========================================================================
        # SEZIONE LANDSCAPE MODE - (in advanced mode)
        # ========================================================================

        if em_tools.mode_em_advanced:

            # ── UX3/B · LA VIA PIÙ CORTA PER VEDERE UN CONTENUTO ─────────
            #
            # La sequenza vera è: aggiungi un grafo → dai il path → carica.
            # L'interfaccia non la diceva: su una scena vuota si vedevano sei
            # bottoni icona uguali, un campo Path e nessun ordine.
            #
            # Il principio non è spiegare la sequenza, è fare in modo che a
            # ogni passo l'unica cosa accesa sia quella giusta.
            _stato = self._catena(context, em_tools)

            # PASSO 0 · la guida, e SOLO per il primo grafo.
            #
            # Prima compariva ogni volta che l'ATTIVO non era caricato,
            # quindi tornava quando si aggiungeva il secondo grafo — e lì è
            # pleonastica: la sequenza la si è appena fatta. La condizione è
            # «nessun grafo caricato in tutto», cioè «non ho ancora mai visto
            # un contenuto».
            #
            # Il secondo grafo non resta senza indicazioni: i comandi spenti
            # dicono la ragione nel tooltip (`poll_message_set`) e il `Load`
            # in evidenza compare comunque appena c'è un path.
            if not _stato["grafi_caricati"] and self._guida_richiesta():
                self._guida(layout, _stato)

            # List of GraphML files
            row = layout.row()
            row.template_list("EMTOOLS_UL_files", "", em_tools, "graphml_files", em_tools, "active_file_index", rows=2)

            if not _stato["ha_grafo"]:
                # STATO VUOTO · zero grafi, una strada sola. La riga dei sei
                # bottoni NON si disegna: con la lista vuota cinque su sei non
                # hanno nulla su cui agire, e sei icone uguali di cui una sola
                # funziona sono un indovinello.
                vuoto = layout.row()
                vuoto.scale_y = 1.5
                vuoto.operator('em_tools.add_file', text="Add graph",
                               icon='ADD')
            else:
                self._riga_comandi(context, layout, em_tools, scene, _stato)


            # Save / Export / Merge buttons (experimental — GraphML write-back not production-ready)
            if em_tools.experimental_features:
                row = layout.row(align=True)
                row.operator('export.graphml_update', text="Save GraphML", icon="FILE_TICK")
                row.operator('export.graphml_saveas', text="Save As...", icon="FILE_NEW")
                row.operator('em.merge_xlsx_start', text="Merge XLSX...", icon="AUTOMERGE_ON")

                # Hybrid-C Phase 4: Bake auxiliary → GraphML. Shown only
                # when the active graph carries any injected content
                # (nodes/edges tagged ``injected_by``, attribute
                # overrides, or orphan entries). One-way op: the
                # enrichment layer becomes graph-native in the file.
                try:
                    from ..operators.aux_lifecycle import has_injected_content
                    from s3dgraphy import get_graph as _sg_get_graph
                    _bake_available = False
                    if em_tools.active_file_index >= 0 and em_tools.graphml_files:
                        _gf = em_tools.graphml_files[em_tools.active_file_index]
                        _g = _sg_get_graph(_gf.name)
                        _bake_available = has_injected_content(_g)
                except ImportError:
                    _bake_available = False
                if _bake_available:
                    bake_row = layout.row(align=True)
                    bake_row.alert = True
                    bake_row.operator(
                        'em.aux_bake_to_graphml',
                        text="Bake Auxiliaries → GraphML",
                        icon='FILE_TICK')

            # (Multigraph Mode è nella riga di icone sopra — B3.)

            # Details for selected GraphML file (codice esistente)
            if em_tools.active_file_index >= 0 and em_tools.graphml_files:

                layout.separator()

                active_file = em_tools.graphml_files[em_tools.active_file_index]

                # Path to GraphML
                row = layout.row(align=True)
                row.prop(active_file, "graphml_path", text="Path")

                # PASSO 3 · il caricamento, in evidenza e CON IL TESTO, finché
                # il grafo non è caricato. A grafo caricato torna icona nella
                # riga (come `Reload`), che è dove stava e dove basta che sia.
                #
                # Sta DOPO il Path e non prima: la catena si legge lista →
                # path → carica, e a video il bottone sopra il campo che deve
                # riempire prima invertiva l'ordine dei due passi.
                if _stato["ha_path"] and not _stato["caricato"]:
                    carica = layout.row()
                    carica.scale_y = 1.5
                    self._op_carica(carica, _stato, testo="Load")

                # UX3/A · la scala NON sta più qui: è diventata il pannello
                # `EM Overview`, primo del tab. Il motivo è di scope — i suoi
                # quattro numeri venivano da posti diversi (scena / grafo
                # attivo) e in multigrafo due cambiavano e due no. Vedi
                # `VIEW3D_PT_EM_Overview` sopra.

                # ── B2 (EM16-UX) · «Graph info», collassabile e chiuso ────
                #
                # Da qui al banner di versione: US/USV, Epochs, Properties,
                # Author, License, Embargo, `GraphML · EM 1.5.4`. Erano sempre
                # aperti in cima al pannello d'ingresso, e sono informazioni di
                # servizio.
                #
                # «Graph info» e non «Info»: quei numeri riguardano il GRAFO,
                # non la scena — ed è precisamente la distinzione che il
                # riquadro della scala, qui sopra, rischia di confondere.
                gi_box = layout.box()
                gi_head = gi_box.row(align=True)
                gi_head.prop(
                    em_tools, "show_graph_info", text="Graph info",
                    icon="TRIA_DOWN" if em_tools.show_graph_info else "TRIA_RIGHT",
                    emboss=False)
                if em_tools.show_graph_info:
                    self._draw_graph_info(context, gi_box, active_file)

                # I warning NON entrano nel collassabile: un avviso che si può
                # chiudere resta chiuso, ed è lo stesso motivo per cui la riga
                # della scala sta fuori.
                self._draw_graph_warnings(context, layout, em_tools, active_file)

                # I file ausiliari, che erano in coda a questo blocco.
                self._draw_auxiliary_files(context, layout, active_file)

        else:
            # La modalità 3D GIS, estratta per la stessa ragione delle
            # altre: `draw` era un metodo di trecento righe, e il ramo
            # `else` di un `if` così lontano dal suo `if` non si legge.
            self._draw_3dgis_mode(context, layout, em_tools)

    def _draw_graph_info(self, context, layout, active_file):
        """B2 · i numeri e i metadati del grafo attivo."""
        ############# box con le statistiche del file ##################
        box = layout.box()
        row = box.row(align=True)
        split = row.split()

        # PERCHÉ QUI LE ICONE NOSTRE SONO SOLO UNA
        #
        # Il primo giro le aveva messe tutte e tre (`US`, `property`,
        # `document`). Misurate le immagini: `US.png` è **253×128** e
        # `property.png` **225×99** — sono i glifi della palette del grafo, i
        # rettangoli in stile yEd, non icone. In uno slot quadrato Blender li
        # schiaccia, e a dimensione d'etichetta `US` si legge come una
        # barretta rossa e `property` come una macchia. `document.png` invece
        # è 64×64, cioè un'icona vera, e resta.
        #
        # Quindi US/USV e Properties tornano alle icone di Blender. Il disegno
        # autentico non è stato scartato per gusto: è inservibile a 16px
        # finché non esiste una versione quadrata, e quella è una cosa da
        # disegnare, non da programmare.
        #
        # UX3/C · US/USV prende `proxies_rows` (64×64, quadrata), che è la
        # stessa che lo Stratigraphy Manager mostra accanto a «Total Rows»
        # (`stratigraphy_manager/ui.py:216`): è già il segno di casa per
        # «unità stratigrafiche», e a differenza di `US.png` è un'icona e non
        # un glifo di palette. Sostituisce il `MESH_CUBE` di UX2, che era un
        # ripiego preso dal contatore `US:` del Document Manager.
        #
        # `Epochs` resta con `TIME` perché un'icona di epoca in `icons/` non
        # c'è, e non ne ho riusata una di un altro nodo.

        # US/USV count - legge il valore cached
        col = split.column()
        col.label(text="US/USV")
        col.label(text=str(active_file.stratigraphic_count),
                  **self._kw_icona("proxies_rows", 'MESH_CUBE'))

        # Separatore verticale
        col.separator()

        # Epochs count - legge il valore cached
        col = split.column()
        col.label(text="Epochs")
        col.label(text=str(active_file.epoch_count), icon='TIME')

        # Properties count - legge il valore cached
        col = split.column()
        col.label(text="Properties")
        col.label(text=str(active_file.property_count), icon='PROPERTIES')

        # Documents count - legge il valore cached
        col = split.column()
        col.label(text="Documents")
        col.label(text=str(active_file.document_count),
                  **self._kw_icona("document", 'FILE_TEXT'))

        # Metadata row: Author, License, Embargo
        has_meta = (active_file.graph_author or active_file.graph_license
                    or active_file.graph_embargo)
        if has_meta:
            meta_row = box.row(align=True)
            meta_split = meta_row.split()

            if active_file.graph_author:
                col = meta_split.column()
                col.label(text="Author")
                if active_file.graph_author_orcid:
                    op = col.operator("em.open_author_url",
                                      text=active_file.graph_author,
                                      icon='USER')
                    op.url = active_file.graph_author_orcid
                else:
                    col.label(text=active_file.graph_author, icon='USER')

            if active_file.graph_license:
                col = meta_split.column()
                col.label(text="License")
                if active_file.graph_license_url:
                    op = col.operator("em.open_license_url",
                                      text=active_file.graph_license,
                                      icon='COPY_ID')
                    op.url = active_file.graph_license_url
                else:
                    col.label(text=active_file.graph_license, icon='COPY_ID')

            if active_file.graph_embargo:
                col = meta_split.column()
                col.label(text="Embargo")
                col.label(text=active_file.graph_embargo, icon='LOCKED')

        ####################################################


        # …e il banner di versione: sapere con quale versione del
        # linguaggio stai lavorando è informazione del grafo, non un
        # avviso — quindi sta qui dentro e non fuori.

        # S6 — version banner. Shown whether or not there are warnings:
        # knowing which language version you are working with is not
        # conditional on something having gone wrong.
        _banner = _format_version_banner(active_file)
        if _banner:
            banner_row = layout.row()
            banner_row.label(text=_banner, icon='FILE_TEXT')

    def _draw_graph_warnings(self, context, layout, em_tools, active_file):
        """I warning del grafo, FUORI dal collassabile.

        Un avviso che si può chiudere resta chiuso: è lo stesso motivo
        per cui la riga della scala di promozione sta fuori.
        """
        # Controllo se ci sono warning da mostrare
        graph_code_warning = False
        epochs_date_warning = False

        if hasattr(active_file, 'graph_code'):
            if active_file.graph_code in GRAPH_CODE_SEGNAPOSTO:
                graph_code_warning = True

        # Controllo per date delle epoche non valide
        if hasattr(em_tools, "epochs") and len(em_tools.epochs.list) > 0:
            for epoch in em_tools.epochs.list:
                if epoch.start_time == 10000 or epoch.end_time == 10000:
                    epochs_date_warning = True
                    break

        warning_messages = []

        if graph_code_warning:
            warning_messages.append("Please add a proper site ID in the header")

        if epochs_date_warning:
            warning_messages.append("Update the epochs placeholder dates (xx)")

        # Prefer the structured records: they carry the s3Dgraphy `kind`,
        # so the digest files them exactly instead of matching English.
        # The flat strings are the fallback — for a GraphML source, whose
        # importer emits richer prose than the state families can, and
        # for anything loaded before the records existed.
        warning_messages.extend(_imported_warnings(active_file))

        warning_count = len(warning_messages)

        # Se ci sono warning, mostra il box di warning
        if warning_count > 0:
            from .warning_digest import digest_warnings, summarise
            groups = digest_warnings(warning_messages)

            warning_box = layout.box()
            header_row = warning_box.row(align=True)
            icon = 'TRIA_DOWN' if active_file.show_warnings_section else 'TRIA_RIGHT'
            header_row.prop(
                active_file,
                "show_warnings_section",
                text=f"EM Warnings ({warning_count}):",
                icon=icon,
                emboss=False,
            )
            header_row.label(text="", icon='ERROR')
            help_op = header_row.operator("em.help_popup", text="", icon='QUESTION')
            help_op.title = "EM Warnings"
            help_op.text = (
                "Issues raised while reading this graph,\n"
                "whatever its source (GraphML or em.json).\n"
                "Common causes:\n"
                "- Missing site ID in the swimlane header\n"
                "- Epochs with placeholder dates (xx)\n"
                "- Nodes whose shape/colour matches no EM type\n"
                "- Groups with no palette colour, hence no role\n"
                "- Connections degraded to generic_connection\n"
                "Nothing here is guessed for you: fix the SOURCE\n"
                "graph, then reload."
            )
            help_op.url = "panels/em_setup.html#em-warnings"
            help_op.project = 'em_tools'

            # Collapsed: one line saying what the bulk of it is, so the
            # panel is informative without being opened.
            if not active_file.show_warnings_section:
                digest = summarise(groups)
                if digest:
                    _draw_wrapped_text(warning_box, context, digest,
                                       icon='INFO')

            if active_file.show_warnings_section:
                # Grouped by problem, biggest first. A flat list of ~100
                # near-identical lines is unreadable, and unread warnings
                # fix nothing.
                for group in groups:
                    grp_box = warning_box.box()
                    grp_box.label(
                        text=f"{group.label} ({group.count})",
                        icon=group.icon)
                    warning_col = grp_box.column(align=True)
                    shown = group.messages[:_MAX_WARNINGS_PER_GROUP]
                    for i, warning_msg in enumerate(shown):
                        # A warning that names an element gets a button
                        # that goes there: reading it and going to look
                        # are the same gesture. A warning with no record
                        # (a free-form line) simply has no button.
                        record = (group.records[i]
                                  if i < len(group.records) else None)
                        _draw_warning_row(warning_col, context,
                                          warning_msg, record)
                    hidden = group.count - _MAX_WARNINGS_PER_GROUP
                    if hidden > 0:
                        # Never let a cap read as "that was all of them".
                        warning_col.label(
                            text=f"… and {hidden} more of the same "
                                 f"(see the console for the full list)",
                            icon='DOT')

                op = warning_box.operator("em.open_docs", text="Data Funnel guide", icon="URL")
                op.url = "data_funnel.html#important-considerations"
                op.project = 'em'

        # DEPRECATED: DosCo is now integrated as an Auxiliary Resource type
        # The legacy DosCo section has been removed. DosCo is now managed
        # through the Auxiliary Resources UIList with file_type="dosco"
        # Legacy properties (dosco_dir on GraphMLFileItem) are kept for backward compatibility


    def _draw_auxiliary_files(self, context, layout, active_file):
        """I file ausiliari del grafo attivo (era in coda a `draw`)."""
        # Expanded settings
        box = layout.box()
        box.prop(active_file, "expanded", icon="TRIA_DOWN" if active_file.expanded else "TRIA_RIGHT", emboss=False)

        if active_file.expanded:
            # Lista dei file ausiliari
            row = box.row()
            row.template_list("AUXILIARY_UL_files", "", active_file, "auxiliary_files",
                            active_file, "active_auxiliary_index", rows=3)

            # Bottoni per aggiungere/rimuovere file ausiliari
            row = box.row(align=True)
            row.operator('auxiliary.add_file', text="Add", icon="ADD")
            row.operator('auxiliary.remove_file', text="Remove", icon="REMOVE")

            # Se c'è un file ausiliario selezionato
            if active_file.active_auxiliary_index >= 0 and active_file.auxiliary_files:
                aux_file = active_file.auxiliary_files[active_file.active_auxiliary_index]

                # Tipo (sempre visibile)
                row = box.row()
                row.prop(aux_file, "file_type", text="Type")

                # Path: mostra filepath solo per tipi che lo richiedono
                if aux_file.file_type not in ("dosco", "resource_collection"):
                    row = box.row()
                    row.prop(aux_file, "filepath", text="Path")

                # EMdb mapping
                if aux_file.file_type == "emdb_xlsx":
                    row = box.row()
                    row.prop(aux_file, "emdb_mapping", text="Format")
                    row.operator("emtools.open_mapping_preferences",
                                text="",
                                icon='PREFERENCES')

                elif aux_file.file_type == "pyarchinit":
                    row = box.row()
                    row.prop(aux_file, "pyarchinit_mapping", text="Table Mapping")
                    row.operator("emtools.open_mapping_preferences",
                                text="",
                                icon='PREFERENCES')
                    row = box.row()
                    row.prop(aux_file, "pyarchinit_import_geometries")
                    if aux_file.pyarchinit_import_geometries:
                        sub = box.row()
                        sub.alignment = 'RIGHT'
                        sub.prop(aux_file, "pyarchinit_geom_force_update")
                        if classify_georef_state(context.scene.em_georef) != STATE_CONFIGURED:
                            warn = box.row()
                            warn.label(
                                text="Set shift in Georeferencing panel first",
                                icon='ERROR',
                            )

                    # Mapping details (collapsible to reduce clutter)
                    if aux_file.pyarchinit_mapping != "none":
                        toggle_row = box.row(align=True)
                        icon = 'TRIA_DOWN' if aux_file.show_pyarchinit_mapping_info else 'TRIA_RIGHT'
                        toggle_row.prop(
                            aux_file,
                            "show_pyarchinit_mapping_info",
                            text="Mapping Info",
                            icon=icon,
                            emboss=False
                        )

                        if aux_file.show_pyarchinit_mapping_info:
                            desc_box = box.box()
                            mapping_data = get_mapping_description(aux_file.pyarchinit_mapping, "pyarchinit")
                            if mapping_data:
                                desc_box.label(text=f"Name: {mapping_data['name']}")
                                if "description" in mapping_data:
                                    desc_box.label(text=mapping_data["description"])
                                if "table_settings" in mapping_data:
                                    desc_box.label(text=f"Table: {mapping_data['table_settings']['table_name']}")

                elif aux_file.file_type == "dosco":
                    # DosCo folder path
                    row = box.row()
                    row.prop(aux_file, "dosco_folder", text="Set Path")

                    # Help button
                    op = row.operator("em.open_docs", text="", icon="HELP")
                    op.url = "panels/em_setup.html#emsetup"
                    op.project = 'em_tools'

                    # DosCo options
                    dosco_box = box.box()
                    _draw_wrapped_text(
                        dosco_box,
                        context,
                        "Populate extractors, documents and combiners using DosCo files:",
                    )

                    row = dosco_box.row()
                    row.prop(aux_file, "dosco_overwrite_paths", text="Overwrite paths with DosCo files")

                    row = dosco_box.row()
                    row.prop(aux_file, "dosco_preserve_web_urls", text="Preserve web URLs (don't overwrite http/https)")

                    # Info box with examples
                    info_box = dosco_box.box()
                    _draw_wrapped_text(
                        info_box,
                        context,
                        "When enabled, node paths will be linked to files in DosCo",
                    )
                    info_box.label(text="Examples:")
                    _draw_wrapped_text(
                        info_box,
                        context,
                        "Node GT16.D.01 -> Searches for GT16.D.01 and D.01 in DosCo",
                    )

                elif aux_file.file_type == "source_list":
                    # Source List - simple filepath
                    source_box = box.box()
                    _draw_wrapped_text(
                        source_box,
                        context,
                        "Source List updates descriptions for Document nodes",
                    )
                    _draw_wrapped_text(
                        source_box,
                        context,
                        "Excel file must contain a 'sources' sheet with:",
                    )
                    _draw_wrapped_text(
                        source_box,
                        context,
                        "Column 'Name': node name to match",
                    )
                    _draw_wrapped_text(
                        source_box,
                        context,
                        "Column 'Description': description to set",
                    )

                elif aux_file.file_type == "resource_collection":
                    # Resource Collection - standalone resource folder
                    row = box.row()
                    row.prop(aux_file, "resource_folder", text="Resources Folder")

                    # Warning if absolute path
                    if aux_file.resource_folder:
                        if os.path.isabs(aux_file.resource_folder) and not aux_file.resource_folder.startswith('//'):
                            warn_box = box.box()
                            warn_box.alert = True
                            warn_col = warn_box.column(align=True)
                            _draw_wrapped_text(
                                warn_col,
                                context,
                                "Use relative path (// prefix) for cross-PC compatibility",
                                icon='ERROR',
                            )
                            _draw_wrapped_text(
                                warn_col,
                                context,
                                "Example: //Resources or //../../SharedFolder/Resources",
                            )

                    # Target node types and scan mode
                    row = box.row()
                    row.prop(aux_file, "target_node_types", text="Target Nodes")

                    row = box.row()
                    row.prop(aux_file, "scan_mode", text="Scan Mode")

                    # Scan & Link button
                    row = box.row()
                    row.scale_y = 1.2
                    row.operator("auxiliary.import_now", text="Scan & Link Resources", icon='VIEWZOOM')

                    # Thumbnails section
                    box.separator()
                    box.label(text="Thumbnails Generation:")

                    thumb_row = box.row(align=True)

                    # Thumbnail status indicator
                    if has_doc_thumbs():
                        thumb_row.label(text="", icon='KEYTYPE_JITTER_VEC')
                    else:
                        thumb_row.label(text="", icon='KEYTYPE_KEYFRAME_VEC')

                    # Thumbnail action buttons
                    thumb_row.operator("emtools.build_doc_thumbs", text="(Re)generate")
                    thumb_row.operator("emtools.open_doc_thumbs_folder", text="", icon='FILE_FOLDER')
                    op = thumb_row.operator("em.open_docs", text="", icon="HELP")
                    op.url = "panels/em_setup.html#setting-up-resource-folders"
                    op.project = 'em_tools'

                    # Thumbnails path (collapsible)
                    path_box = box.box()
                    path_row = path_box.row(align=True)
                    path_icon = 'TRIA_DOWN' if aux_file.show_thumbs_path_section else 'TRIA_RIGHT'
                    path_row.prop(aux_file, "show_thumbs_path_section",
                                  text="Thumbnails Path",
                                  icon=path_icon,
                                  emboss=False)

                    if aux_file.show_thumbs_path_section:
                        path_col = path_box.column()
                        path_row = path_col.row()
                        path_row.prop(aux_file, "custom_thumbs_path", text="")

                        if not aux_file.custom_thumbs_path:
                            info_row = path_col.row()
                            info_row.label(text="Path will be auto-generated on first use", icon='INFO')

                # ── Hybrid-C lifecycle: attached count, orphan
                # list, revert-this-aux (Phase 2). Only shown
                # when there is live injector data on the graph
                # for this auxiliary file. ──
                try:
                    from ..operators.aux_lifecycle import (
                        compute_injector_id_for_aux,
                        count_attached,
                        iter_orphans_for,
                    )
                    from s3dgraphy import get_graph as _sg_get_graph
                except ImportError:
                    compute_injector_id_for_aux = None

                if compute_injector_id_for_aux:
                    injector_id = compute_injector_id_for_aux(aux_file)
                    _graph = _sg_get_graph(active_file.name) if injector_id else None
                    attached = count_attached(_graph, injector_id) if injector_id else 0
                    orphan_entries = list(iter_orphans_for(_graph, injector_id)) \
                        if injector_id else []
                    if injector_id and (attached or orphan_entries):
                        life_box = box.box()
                        header_row = life_box.row(align=True)
                        header_row.label(
                            text=(f"Lifecycle — "
                                  f"{attached} attached"
                                  f"{', ' + str(len(orphan_entries)) + ' orphans' if orphan_entries else ''}"),
                            icon='FILE_REFRESH')
                        revert_op = header_row.operator(
                            "em.aux_revert_injector",
                            text="", icon='LOOP_BACK')
                        revert_op.injector_id = injector_id

                        if orphan_entries:
                            orph_row = life_box.row(align=True)
                            orph_icon = ('TRIA_DOWN'
                                         if aux_file.show_aux_orphans
                                         else 'TRIA_RIGHT')
                            orph_row.prop(
                                aux_file, "show_aux_orphans",
                                text=f"Orphan rows ({len(orphan_entries)})",
                                icon=orph_icon, emboss=False)
                            if aux_file.show_aux_orphans:
                                for entry in orphan_entries:
                                    kid = str(entry.get("key_id", "?"))
                                    entry_row = life_box.row(align=True)
                                    entry_row.label(
                                        text=kid, icon='ERROR')
                                    create_op = entry_row.operator(
                                        "em.aux_create_host_for_orphan",
                                        text="Create host",
                                        icon='ADD')
                                    create_op.injector_id = injector_id
                                    create_op.key_id = kid

            # ── B5 · HDT-O È USCITA ───────────────────────────────────
            # È un pannello suo (`graph_info/ui.py::VIEW3D_PT_EM_GraphInfo`),
            # subito dopo questo nel tab EM e chiuso di default. Il renderer
            # della sezione resta e non è stato duplicato: quel pannello chiama
            # lo stesso `_draw_body`.
            #
            # ── B6 · DTC È USCITA E NON TORNA ─────────────────────────────
            # La stessa funzione (`dtc_authoring.ui.draw_dtc_section`) la
            # disegna già il pannello `Resources & Shelf`, e là resta — in sola
            # consultazione. La ragione non è di spazio: il DTC è il grafo
            # dello STORAGE, non dell'interpretazione. L'authoring va a EM
            # Studio; Blender registra ciò che consuma.
            #
            # ── LA SEZIONE UTILS È USCITA ─────────────────────────────────
            # Convert 1.x→1.5, Create, Proxy Prefixes, Experimental e gli
            # strumenti sperimentali stanno nel menu EM in testata
            # (`em_header_menu.py` → EM ▸ Utils): sono comandi RARI e GLOBALI,
            # e un menu è il posto giusto per quelli. Un pannello d'ingresso
            # non è un cassetto degli attrezzi.
        ################################################################################
        # 3D GIS MODE SECTION
        ################################################################################


    def _draw_3dgis_mode(self, context, layout, em_tools):
        """La modalità 3D GIS di base — l'altro ramo di `mode_em_advanced`."""
        # UI per modalità 3D GIS
        box = layout.box()

        # Menu a tendina per il tipo di import
        row = box.row()
        row.prop(em_tools, "mode_3dgis_import_type",
                text="Import Type",
                expand=True)

        # Box specifico per le opzioni del tipo selezionato
        options_box = box.box()

        if em_tools.mode_3dgis_import_type == "generic_xlsx":
            options_box.label(text="Generic Excel Import Settings:")

            # File Excel
            options_box.prop(em_tools, "generic_xlsx_file", text="Excel File")

            # Sheet dropdown (solo se file è selezionato e proprietà esiste)
            if em_tools.generic_xlsx_file and hasattr(em_tools, 'generic_xlsx_sheet'):
                options_box.prop(em_tools, "generic_xlsx_sheet", text="Sheet Name")

                # Colonna ID (solo se sheet è selezionato)
                if (hasattr(em_tools, 'generic_xlsx_sheet') and
                    em_tools.generic_xlsx_sheet and
                    em_tools.generic_xlsx_sheet != "none" and
                    hasattr(em_tools, 'xlsx_id_column')):
                    options_box.prop(em_tools, "xlsx_id_column", text="ID Column")

                    # Colonna descrizione opzionale (solo se ID è selezionato)
                    if (hasattr(em_tools, 'xlsx_id_column') and
                        em_tools.xlsx_id_column and
                        em_tools.xlsx_id_column != "none" and
                        hasattr(em_tools, 'generic_xlsx_desc_column')):
                        options_box.prop(em_tools, "generic_xlsx_desc_column", text="Description Column (Optional)")

        elif em_tools.mode_3dgis_import_type == "pyarchinit":
            options_box.label(text="pyArchInit Import Settings:")
            options_box.prop(em_tools, "pyarchinit_connection_mode",
                             text="Connection", expand=True)
            if em_tools.pyarchinit_connection_mode == "postgres":
                pg_box = options_box.box()
                pg_box.prop(em_tools, "pyarchinit_pg_host", text="Host")
                pg_box.prop(em_tools, "pyarchinit_pg_port", text="Port")
                pg_box.prop(em_tools, "pyarchinit_pg_dbname", text="Database")
                pg_box.prop(em_tools, "pyarchinit_pg_user", text="User")
                pg_box.prop(em_tools, "pyarchinit_pg_password", text="Password")
                creds = pg_box.row(align=True)
                creds.operator("emtools.pyarchinit_pg_save_password",
                               text="Save to keychain", icon='LOCKED')
                creds.operator("emtools.pyarchinit_pg_forget_password",
                               text="Forget", icon='UNLOCKED')
            else:
                options_box.prop(em_tools, "pyarchinit_db_path",
                                 text="SQLite Database")
            options_box.prop(em_tools, "pyarchinit_mapping", text="Select Mapping")
            options_box.operator("emtools.open_mapping_preferences",
                        text="",
                        icon='PREFERENCES')
            row = options_box.row()
            row.prop(em_tools, "pyarchinit_import_geometries")
            if em_tools.pyarchinit_import_geometries:
                sub = options_box.row()
                sub.alignment = 'RIGHT'
                sub.prop(em_tools, "pyarchinit_geom_force_update")
                if classify_georef_state(context.scene.em_georef) != STATE_CONFIGURED:
                    warn = options_box.row()
                    warn.label(
                        text="Set shift in Georeferencing panel first",
                        icon='ERROR',
                    )

            # Mostra info sul mapping selezionato
            if em_tools.pyarchinit_mapping != "none":
                desc_box = options_box.box()
                desc_box.label(text="Mapping Info:")
                mapping_data = get_mapping_description(em_tools.pyarchinit_mapping, "pyarchinit")
                if mapping_data:
                    row = desc_box.row()
                    row.label(text=f"Name: {mapping_data['name']}")
                    if "description" in mapping_data:
                        desc_box.label(text=mapping_data["description"])
                    if "table_settings" in mapping_data:
                        desc_box.label(text=f"Table: {mapping_data['table_settings']['table_name']}")

            # Dynamic filter dropdowns (populated by the mapping's
            # ``is_filter`` columns — see s3dgraphy 1.6).
            active_filters = [
                i for i in range(1, 6)
                if em_tools.get(f"pyarchinit_filter_{i}_column")
            ]
            if active_filters:
                filter_box = options_box.box()
                filter_box.label(text="Filter rows by:", icon='FILTER')
                for i in active_filters:
                    label = em_tools.get(
                        f"pyarchinit_filter_{i}_label", f"Filter {i}"
                    )
                    required = em_tools.get(
                        f"pyarchinit_filter_{i}_required", False
                    )
                    text = label + (" *" if required else "")
                    row = filter_box.row()
                    row.prop(em_tools, f"pyarchinit_filter_{i}", text=text)

        elif em_tools.mode_3dgis_import_type == "emdb_xlsx":
            options_box.label(text="EMdb Excel Import Settings:")
            options_box.prop(em_tools, "emdb_xlsx_file", text="EMdb Excel File")
            options_box.prop(em_tools, "emdb_mapping", text="EMdb Format")
            options_box.operator("emtools.open_mapping_preferences",
                        text="",
                        icon='PREFERENCES')

            # Mostra una descrizione del formato selezionato
            if em_tools.emdb_mapping != "none":
                desc_box = options_box.box()
                desc_box.label(text="Format Description:")
                mapping_data = get_mapping_description(em_tools.emdb_mapping)
                if mapping_data:
                    # Header
                    row = desc_box.row()
                    row.label(text=f"Name: {mapping_data['name']}")

                    # Description
                    if "description" in mapping_data:
                        desc_box.label(text=mapping_data["description"])

                    # Required Excel columns
                    if "required_columns" in mapping_data:
                        col_box = desc_box.box()
                        col_box.label(text="Required Excel columns:")
                        for col in mapping_data["required_columns"]:
                            col_box.label(text=f"- {col}")

        # Tasto Import con operatore unificato
        row = box.row(align=True)
        row.scale_y = 1.5  # Bottone più grande

        # Validazione campi obbligatori per abilitare il pulsante Import
        can_import = False

        if em_tools.mode_3dgis_import_type == "generic_xlsx":
            # Richiede: file, sheet, ID column
            can_import = bool(
                em_tools.generic_xlsx_file and
                hasattr(em_tools, 'generic_xlsx_sheet') and
                em_tools.generic_xlsx_sheet and
                em_tools.generic_xlsx_sheet != "none" and
                hasattr(em_tools, 'xlsx_id_column') and
                em_tools.xlsx_id_column and
                em_tools.xlsx_id_column != "none"
            )
        elif em_tools.mode_3dgis_import_type == "pyarchinit":
            # Richiede un mapping e una connessione valida: in SQLite
            # il file DB, in PostgreSQL host+db+user (la password è
            # verificata all'avvio dell'import, non qui — #27 Sub-2).
            conn_mode = getattr(em_tools, "pyarchinit_connection_mode", "sqlite")
            if conn_mode == "postgres":
                conn_ok = bool(
                    (em_tools.pyarchinit_pg_host or "").strip() and
                    (em_tools.pyarchinit_pg_dbname or "").strip() and
                    (em_tools.pyarchinit_pg_user or "").strip()
                )
            else:
                conn_ok = bool(em_tools.pyarchinit_db_path)
            can_import = bool(
                conn_ok and
                em_tools.pyarchinit_mapping != "none"
            )
        elif em_tools.mode_3dgis_import_type == "emdb_xlsx":
            # Richiede: file, mapping
            can_import = bool(
                em_tools.emdb_xlsx_file and
                em_tools.emdb_mapping != "none"
            )

        row.enabled = can_import
        op = row.operator("em.import_3dgis_database",
                        text="Import Database",
                        icon='IMPORT')
        # Impostiamo le proprietà dell'operatore
        op.auxiliary_mode = False  # Modalità 3DGIS standard
        op.graphml_index = -1  # Non applicabile in modalità 3DGIS
        op.auxiliary_index = -1  # Non applicabile in modalità 3DGIS


class AUXILIARY_MT_context_menu(bpy.types.Menu):
    bl_idname = "AUXILIARY_MT_context_menu"
    bl_label = "Auxiliary File Specials"

    def draw(self, context):
        layout = self.layout
        em_tools = context.scene.em_tools
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        aux_file = graphml.auxiliary_files[graphml.active_auxiliary_index]

        layout.operator("auxiliary.reload", text="Reload File")
        layout.operator("auxiliary.import_now", text="Import Now")
        layout.separator()

        # Sottomenu per il tipo di file
        layout.prop(aux_file, "file_type", text="Change Type")

        if aux_file.file_type == "emdb_xlsx":
            layout.prop(aux_file, "emdb_mapping", text="Change Format")


# ============================================================================
# CLASSES TUPLE (UI classes only, not helper functions)
# ============================================================================

classes = (
    AUXILIARY_UL_files,
    EMTOOLS_UL_files,
    EM_SetupPanel,
    AUXILIARY_MT_context_menu,
)


# ============================================================================
# REGISTER/UNREGISTER
# ============================================================================

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"Error unregistering {cls.__name__}: {e}")


if __name__ == "__main__":
    register()
