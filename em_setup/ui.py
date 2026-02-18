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
            print(f"⚠️ Error getting valid items for {prop_name}: {e}")
            return False

        # Estrai gli ID validi
        valid_ids = [item[0] for item in valid_items if len(item) > 0]

        # Se il valore corrente non è nella lista, resetta
        if current_value not in valid_ids:
            print(f"⚠️ Invalid {prop_name} value: '{current_value}' (not in {valid_ids}) - resetting to 'none'")
            setattr(obj, prop_name, 'none')
            return True  # Indica che c'è stata una modifica

        return False

    except Exception as e:
        print(f"Error validating {prop_name}: {e}")
        return False


def validate_all_mapping_enums(context):
    """
    Valida tutti gli EnumProperty che usano mappings dinamici.
    Cerca in tutte le posizioni dove possono essere salvati i mapping.
    """
    from .properties import get_emdb_mappings, get_pyarchinit_mappings

    modified_count = 0

    try:
        if not hasattr(context, 'scene') or not hasattr(context.scene, 'em_tools'):
            print("⚠️ Cannot validate mappings: em_tools not found")
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
            print(f"✓ Mapping validation complete: {modified_count} invalid values reset")
        else:
            print("✓ Mapping validation complete: all values valid")

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
        "Le sezioni con il simbolo Experimental sono sperimentali: usale solo su file con backup.",
        icon='INFO',
    )


def _draw_graphml_wizard(layout, context, em_tools):
    """Draw GraphML Wizard content (used in EM Bridge panel)."""
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
        "3-step wizard for creating an Extended Matrix\n"
        "GraphML from Excel data (manually filled or\n"
        "AI-extracted). Optionally enrich with paradata\n"
        "provenance before exporting."
    )
    help_op.url = "creating_em.html#from-excel-standard-stratigraphy"

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
    help_op.url = "creating_em.html#from-excel-standard-stratigraphy"
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

    # ── STEP 2: Enrich with Paradata (optional) ──
    step2_box = graphml_box.box()
    step2_box.enabled = has_graph
    row = step2_box.row(align=True)
    row.label(text="Step 2: Enrich with Paradata", icon='PROPERTIES')
    help_op = row.operator("em.help_popup", text="", icon='QUESTION')
    help_op.title = "Step 2 — Enrich with Paradata"
    help_op.text = (
        "Optional. Load em_paradata.xlsx to add per-property\n"
        "provenance chains (extractor text + source document)\n"
        "to the in-memory graph. Requires Step 1 first."
    )
    help_op.url = "creating_em.html#from-excel-standard-stratigraphy"
    step2_box.prop(em_tools, "xlsx_wizard_paradata_file", text="Paradata File")
    step2_box.prop(em_tools, "xlsx_wizard_overwrite_properties")

    can_enrich = has_graph and bool(em_tools.xlsx_wizard_paradata_file)
    row = step2_box.row()
    row.scale_y = 1.3
    row.enabled = can_enrich
    row.operator(
        "xlsx_wizard.enrich_paradata",
        text="Enrich Graph",
        icon='MODIFIER'
    )

    # ── STEP 3: Export GraphML ──
    step3_box = graphml_box.box()
    step3_box.enabled = has_graph
    row = step3_box.row(align=True)
    row.label(text="Step 3: Export GraphML", icon='EXPORT')
    help_op = row.operator("em.help_popup", text="", icon='QUESTION')
    help_op.title = "Step 3 — Export GraphML"
    help_op.text = (
        "Save the in-memory graph as a GraphML file.\n"
        "Then import it via File > Import EM file to\n"
        "populate the Blender lists and scene."
    )
    help_op.url = "creating_em.html#from-excel-standard-stratigraphy"
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
    help_op.url = "creating_em.html#from-excel-standard-stratigraphy"
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

    # ── AI Extraction Prompt ──
    graphml_box.separator(factor=0.5)
    row = graphml_box.row(align=True)
    row.label(text="AI Extraction Prompt:", icon='FILE_TEXT')
    help_op = row.operator("em.help_popup", text="", icon='QUESTION')
    help_op.title = "AI-Assisted Extraction"
    help_op.text = (
        "Copy a ready-to-use prompt to paste into Claude,\n"
        "ChatGPT, or Gemini alongside your archaeological\n"
        "documents. The AI will produce the two Excel files\n"
        "needed by Steps 1 and 2."
    )
    help_op.url = "creating_em.html#ai-assisted-extraction"
    graphml_box.prop(em_tools, "xlsx_wizard_prompt_language", text="Language")
    row = graphml_box.row()
    row.scale_y = 1.1
    row.operator(
        "xlsx_wizard.copy_ai_prompt",
        text="Copy AI Prompt to Clipboard",
        icon='COPYDOWN'
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

            # Nome file
            row.prop(item, "name", text="", emboss=False)

            # Stato del file
            if item.filepath or item.dosco_folder:
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

            # Mostra il graph_code come testo non modificabile invece di un campo editabile
            layout.label(text=graph_code)

            # Mostra l'icona di stato
            row = layout.row()
            row.label(text="", icon=status_icon)

            # Pulsante per ricaricare il file GraphML (con icona FILE_REFRESH)
            row = layout.row(align=True)
            op = row.operator("import.em_graphml", text="", icon="FILE_REFRESH", emboss=False)
            op.graphml_index = index  # Passa l'indice corretto per caricare il GraphML

            # Disabilita il pulsante se l'icona è rossa (grafo non esistente)
            if is_graph_present:
                # Pulsante per aprire nel Graph Viewer (accanto a import.em_graphml)
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
                row = layout.row()
                row.enabled = False  # Disabilita il layout (grigio)
                row.label(text="", icon='NODETREE')  # Draw graph disabilitato
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


class EM_SetupPanel(bpy.types.Panel):

    bl_label = f"EM Data Tree {get_em_tools_version()}"
    bl_idname = "VIEW3D_PT_EM_Tools_Setup"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM"


    def draw_header(self, context):
        layout = self.layout
        # visualizza un'icona prima del titolo
        layout.template_icon(icon_value=icons_manager.get_icon_value("em_logo"))


    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_tools = scene.em_tools

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
        # SEZIONE LANDSCAPE MODE - (in experimental mode)
        # ========================================================================

        if em_tools.experimental_features:

            # Conta i grafi caricati e validi
            loaded_graphs = []
            if em_tools.graphml_files:
                for graph_file in em_tools.graphml_files:
                    # Controlla se il grafo è effettivamente caricato
                    if hasattr(graph_file, 'is_graph') and graph_file.is_graph:
                        loaded_graphs.append(graph_file)
                    else:
                        # Fallback: controlla se il grafo esiste nel sistema
                        from s3dgraphy import get_graph
                        if get_graph(graph_file.name):
                            loaded_graphs.append(graph_file)

            # Mostra controlli Landscape sempre (con info se non disponibile)
            #layout.separator()

            # Box per Landscape Mode - COMPATTO
            landscape_box = layout.box()

            # Riga unica con tutto
            row = landscape_box.row(align=True)

            # Pulsante info
            info_op = row.operator("wm.call_menu", text="", icon='INFO')
            info_op.name = "EM_MT_LandscapeInfo"

            # Label
            row.label(text="Multigraph Mode")

            # Stato attuale e pulsante toggle
            is_landscape_active = getattr(scene, 'landscape_mode_active', False)
            can_enable_landscape = len(loaded_graphs) >= 2

            if is_landscape_active:
                # Attivo: pulsante per disattivare
                disable_op = row.operator("em.toggle_landscape_mode",
                                        text="Disable",
                                        icon='CANCEL')
                disable_op.enable = False  # Per disattivare
            else:
                # Non attivo: pulsante per attivare
                # Crea un sub-row per poter disabilitare solo il pulsante
                button_row = row.row()
                button_row.enabled = can_enable_landscape  # ✅ CORRETTO: disabilita il row

                enable_op = button_row.operator("em.toggle_landscape_mode",
                                               text="Enable",
                                               icon='FILE_VOLUME')
                enable_op.enable = True  # Per attivare


        # ========================================================================
        # END OF LANDSCAPE MODE SECTION
        # ========================================================================


        if em_tools.mode_em_advanced:

            # List of GraphML files
            row = layout.row()
            row.template_list("EMTOOLS_UL_files", "", em_tools, "graphml_files", em_tools, "active_file_index", rows=2)

            row = layout.row(align=True)
            row.operator('em_tools.add_file', text="Add GraphML", icon="ADD")
            row.operator('em_tools.remove_file', text="Remove GraphML", icon="REMOVE")

            # Details for selected GraphML file (codice esistente)
            if em_tools.active_file_index >= 0 and em_tools.graphml_files:

                layout.separator()

                active_file = em_tools.graphml_files[em_tools.active_file_index]

                # Path to GraphML
                row = layout.row(align=True)
                row.prop(active_file, "graphml_path", text="Path")

                ############# box con le statistiche del file ##################
                box = layout.box()
                row = box.row(align=True)
                split = row.split()

                # US/USV count - legge il valore cached
                col = split.column()
                col.label(text="US/USV")
                col.label(text=str(active_file.stratigraphic_count), icon='OUTLINER_OB_MESH')

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
                col.label(text=str(active_file.document_count), icon='FILE_TEXT')


                ####################################################

                # Controllo se ci sono warning da mostrare
                graph_code_warning = False
                epochs_date_warning = False

                if hasattr(active_file, 'graph_code'):
                    if active_file.graph_code in ["site_id","MISSINGCODE"]:
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

                if hasattr(active_file, 'import_warnings') and active_file.import_warnings:
                    for line in active_file.import_warnings.split("\n"):
                        stripped = line.strip()
                        if stripped:
                            warning_messages.append(stripped)

                warning_count = len(warning_messages)

                # Se ci sono warning, mostra il box di warning
                if warning_count > 0:
                    warning_box = layout.box()
                    header_row = warning_box.row(align=True)
                    icon = 'TRIA_DOWN' if active_file.show_warnings_section else 'TRIA_RIGHT'
                    header_row.prop(
                        active_file,
                        "show_warnings_section",
                        text=f"GraphML Warning ({warning_count}):",
                        icon=icon,
                        emboss=False,
                    )
                    header_row.label(text="", icon='ERROR')

                    if active_file.show_warnings_section:
                        warning_col = warning_box.column(align=True)
                        for warning_msg in warning_messages:
                            _draw_wrapped_warning(warning_col, context, warning_msg)

                        op = warning_box.operator("wm.url_open", text="Quick guide", icon="HELP")
                        op.url = "https://docs.extendedmatrix.org/en/1.5.0dev/data_funnel.html#important-considerations"

                # DEPRECATED: DosCo is now integrated as an Auxiliary Resource type
                # The legacy DosCo section has been removed. DosCo is now managed
                # through the Auxiliary Resources UIList with file_type="dosco"
                # Legacy properties (dosco_dir on GraphMLFileItem) are kept for backward compatibility

                # ── Enrich GraphML section (experimental) ──
                if em_tools.experimental_features:
                    enrich_box = layout.box()
                    enrich_header = enrich_box.row(align=True)
                    enrich_header.alert = True
                    enrich_icon = 'TRIA_DOWN' if active_file.enrich_expanded else 'TRIA_RIGHT'
                    enrich_header.prop(
                        active_file, "enrich_expanded",
                        text="Enrich GraphML (Experimental)",
                        icon=enrich_icon,
                        emboss=False
                    )
                    enrich_header.label(text="", icon='EXPERIMENTAL')
                    help_op = enrich_header.operator("em.help_popup", text="", icon='QUESTION')
                    help_op.title = "Enrich GraphML"
                    help_op.text = (
                        "Bake EM Tables into the loaded GraphML file.\n"
                        "EM Paradata Table adds deep provenance chains\n"
                        "(extractor + document per property).\n"
                        "A rotating backup is created automatically."
                    )
                    help_op.url = "creating_em.html#enriching-graphml"

                    if active_file.enrich_expanded:
                        # Check if graph is loaded
                        _graph_loaded = False
                        try:
                            from s3dgraphy import get_graph as _sg_get_graph
                            _g = _sg_get_graph(active_file.name)
                            _graph_loaded = bool(_g and hasattr(_g, 'nodes') and len(_g.nodes) > 0)
                        except Exception:
                            pass

                        if not _graph_loaded:
                            warn_row = enrich_box.row()
                            warn_row.label(
                                text="Load the GraphML first (click reload icon)",
                                icon='ERROR'
                            )

                        # ── EM Paradata Table ──
                        para_box = enrich_box.box()
                        row = para_box.row(align=True)
                        row.label(text="EM Paradata Table", icon='PROPERTIES')
                        help_op = row.operator("em.help_popup", text="", icon='QUESTION')
                        help_op.title = "EM Paradata Table"
                        help_op.text = (
                            "Long-table Excel format (em_paradata.xlsx) with one\n"
                            "row per property per US. Adds deep provenance chains:\n"
                            "PropertyNode -> ExtractorNode -> DocumentNode.\n"
                            "Use the AI prompt to generate this file automatically."
                        )
                        help_op.url = "creating_em.html#em-paradata-table"

                        para_box.prop(active_file, "enrich_paradata_file", text="File")
                        para_box.prop(active_file, "enrich_paradata_overwrite")

                        can_bake = _graph_loaded and bool(active_file.enrich_paradata_file)
                        row = para_box.row()
                        row.scale_y = 1.3
                        row.enabled = can_bake
                        row.operator(
                            "enrich.bake_paradata",
                            text="Bake Paradata into GraphML",
                            icon='MODIFIER'
                        )

                        # Info label
                        enrich_box.separator(factor=0.3)
                        info_row = enrich_box.row()
                        info_row.label(
                            text="Changes are saved to the GraphML file. Backup is automatic.",
                            icon='INFO'
                        )

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

                        # Path: mostra filepath solo per tipi non-DosCo
                        if aux_file.file_type != "dosco":
                            row = box.row()
                            row.prop(aux_file, "filepath", text="Path")

                        # EMdb mapping se necessario
                        if aux_file.file_type == "emdb_xlsx":
                            row = box.row()
                            row.prop(aux_file, "emdb_mapping", text="Format")
                            row.operator("emtools.open_mapping_preferences",
                                        text="",
                                        icon='PREFERENCES')
                            # SEZIONE COLLASSABILE DOCUMENT RESOURCES
                            resources_box = box.box()

                            # Header con triangolino
                            header_row = resources_box.row(align=True)
                            icon = 'TRIA_DOWN' if aux_file.show_resources_section else 'TRIA_RIGHT'
                            header_row.prop(aux_file, "show_resources_section",
                                        text=f"Document Resources for {aux_file.name}",
                                        icon=icon,
                                        emboss=False)

                            # Mostra contenuto solo se espanso
                            if aux_file.show_resources_section:
                                # Cartella risorse
                                col = resources_box.column()
                                row = col.row()
                                row.prop(aux_file, "resource_folder", text="Resources Folder")

                                # Warning se path assoluto
                                if aux_file.resource_folder:
                                    if os.path.isabs(aux_file.resource_folder) and not aux_file.resource_folder.startswith('//'):
                                        warn_box = col.box()
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

                                # Sezione thumbnails
                                col.separator()
                                col.label(text="Thumbnails Generation:")

                                thumb_row = col.row(align=True)

                                # Indicatore esistenza thumbs (ICONE ORIGINALI!)
                                if has_doc_thumbs():
                                    thumb_row.label(text="", icon='KEYTYPE_JITTER_VEC')  # Verde
                                else:
                                    thumb_row.label(text="", icon='KEYTYPE_KEYFRAME_VEC')  # Rosso

                                # Pulsanti thumbnails
                                thumb_row.operator("emtools.build_doc_thumbs", text="(Re)generate")
                                thumb_row.operator("emtools.open_doc_thumbs_folder", text="", icon='FILE_FOLDER')
                                op = thumb_row.operator("wm.url_open", text="", icon="HELP")
                                op.url = "https://docs.extendedmatrix.org/projects/EM-tools/en/1.5.0/EMstructure.html#setting-up-resource-folders"

                                # THUMBNAILS PATH - Sotto triangolino collassabile
                                path_box = col.box()
                                path_row = path_box.row(align=True)

                                # Triangolino per espandere/collassare
                                path_icon = 'TRIA_DOWN' if aux_file.show_thumbs_path_section else 'TRIA_RIGHT'
                                path_row.prop(aux_file, "show_thumbs_path_section",
                                            text="Thumbnails Path",
                                            icon=path_icon,
                                            emboss=False)

                                # Mostra il campo path solo se espanso
                                if aux_file.show_thumbs_path_section:
                                    path_col = path_box.column()
                                    path_row = path_col.row()
                                    path_row.prop(aux_file, "custom_thumbs_path", text="")

                                    # Se non c'è path custom, mostra info
                                    if not aux_file.custom_thumbs_path:
                                        info_row = path_col.row()
                                        info_row.label(text="Path will be auto-generated on first use", icon='INFO')

                        elif aux_file.file_type == "pyarchinit":
                            row = box.row()
                            row.prop(aux_file, "pyarchinit_mapping", text="Table Mapping")
                            row.operator("emtools.open_mapping_preferences",
                                        text="",
                                        icon='PREFERENCES')

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

                            # SEZIONE COLLASSABILE DOCUMENT RESOURCES (come per EMdb)
                            resources_box = box.box()

                            # Header con triangolino
                            header_row = resources_box.row(align=True)
                            icon = 'TRIA_DOWN' if aux_file.show_resources_section else 'TRIA_RIGHT'
                            header_row.prop(aux_file, "show_resources_section",
                                        text=f"Document Resources for {aux_file.name}",
                                        icon=icon,
                                        emboss=False)

                            # Mostra contenuto solo se espanso
                            if aux_file.show_resources_section:
                                # Cartella risorse
                                col = resources_box.column()
                                row = col.row()
                                row.prop(aux_file, "resource_folder", text="Resources Folder")

                                # Warning se path assoluto
                                if aux_file.resource_folder:
                                    if os.path.isabs(aux_file.resource_folder) and not aux_file.resource_folder.startswith('//'):
                                        warn_box = col.box()
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

                                # Sezione thumbnails
                                col.separator()
                                col.label(text="Thumbnails Generation:")

                                thumb_row = col.row(align=True)

                                # Indicatore esistenza thumbs (ICONE ORIGINALI!)
                                if has_doc_thumbs():
                                    thumb_row.label(text="", icon='KEYTYPE_JITTER_VEC')  # Verde
                                else:
                                    thumb_row.label(text="", icon='KEYTYPE_KEYFRAME_VEC')  # Rosso

                                # Pulsanti thumbnails
                                thumb_row.operator("emtools.build_doc_thumbs", text="(Re)generate")
                                thumb_row.operator("emtools.open_doc_thumbs_folder", text="", icon='FILE_FOLDER')
                                op = thumb_row.operator("wm.url_open", text="", icon="HELP")
                                op.url = "https://docs.extendedmatrix.org/projects/EM-tools/en/1.5.0/EMstructure.html#setting-up-resource-folders"

                                # THUMBNAILS PATH - Sotto triangolino collassabile
                                path_box = col.box()
                                path_row = path_box.row(align=True)

                                # Triangolino per espandere/collassare
                                path_icon = 'TRIA_DOWN' if aux_file.show_thumbs_path_section else 'TRIA_RIGHT'
                                path_row.prop(aux_file, "show_thumbs_path_section",
                                            text="Thumbnails Path",
                                            icon=path_icon,
                                            emboss=False)

                                # Mostra il campo path solo se espanso
                                if aux_file.show_thumbs_path_section:
                                    path_col = path_box.column()
                                    path_row = path_col.row()
                                    path_row.prop(aux_file, "custom_thumbs_path", text="")

                                    # Se non c'è path custom, mostra info
                                    if not aux_file.custom_thumbs_path:
                                        info_row = path_col.row()
                                        info_row.label(text="Path will be auto-generated on first use", icon='INFO')

                        elif aux_file.file_type == "dosco":
                            # DosCo folder path
                            row = box.row()
                            row.prop(aux_file, "dosco_folder", text="Set Path")

                            # Help button
                            op = row.operator("wm.url_open", text="", icon="HELP")
                            op.url = "https://docs.extendedmatrix.org/projects/EM-tools/en/1.5.0/EMstructure.html#em-setup"

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

            # Advanced Tools section
            box = layout.box()
            header = box.row(align=True)
            header.prop(
                em_tools,
                "show_advanced_tools",
                text="Utils",
                icon="TRIA_DOWN" if em_tools.show_advanced_tools else "TRIA_RIGHT",
                emboss=False
            )

            if em_tools.show_advanced_tools:
                tools_col = box.column(align=True)

                # Main utility actions (compact 2x2 grid)
                row = tools_col.row(align=True)
                row.scale_y = 0.9
                split = row.split(factor=0.5, align=True)
                split.operator(
                    GRAPHML_OT_convert_borders.bl_idname,
                    text="Convert 1.x->1.5",
                    icon='FILE_REFRESH'
                )
                split.operator(
                    "create.collection",
                    text="Create",
                    icon="COLLECTION_NEW"
                )

                row = tools_col.row(align=True)
                row.scale_y = 0.9
                split = row.split(factor=0.5, align=True)
                split.operator(
                    "em.manage_object_prefixes",
                    text="Proxy Prefixes",
                    icon='SYNTAX_ON'
                )
                exp_toggle = split.row(align=True)
                exp_toggle.alert = em_tools.experimental_features
                exp_toggle.prop(
                    em_tools,
                    "experimental_features",
                    text="Experimental",
                    toggle=True,
                    icon="EXPERIMENTAL"
                )

                if em_tools.experimental_features:
                    _draw_experimental_notice(tools_col, context)

                    exp_box = tools_col.box()
                    exp_box.label(text="Experimental tools", icon="EXPERIMENTAL")

                    row = exp_box.row(align=True)
                    row.scale_y = 0.9
                    row.operator(
                        "em.rebuild_graph_indices",
                        text="Rebuild Indices",
                        icon='FILE_REFRESH'
                    )
                    help_op = row.operator("em.help_popup", text="", icon='QUESTION')
                    help_op.title = "Rebuild Graph Indices"
                    help_op.text = (
                        "Regenerates cached indices for faster lookups.\n"
                        "Useful after large edits to the GraphML."
                    )
                    help_op.url = "EMstructure.html#em-setup"

                    row = exp_box.row(align=True)
                    row.scale_y = 0.9
                    row.operator(
                        "em.benchmark_property_functions",
                        text="Benchmark Props",
                        icon="TIME"
                    )
                    help_op = row.operator("em.help_popup", text="", icon='QUESTION')
                    help_op.title = "Benchmark Property Functions"
                    help_op.text = (
                        "Runs internal performance checks for property\n"
                        "handlers. Expect temporary UI stalls during run."
                    )
                    help_op.url = "EMstructure.html#em-setup"
                    info_row = exp_box.row(align=True)
                    info_row.label(text="GraphML Wizard moved to EM Bridge", icon='INFO')

        ################################################################################
        # 3D GIS MODE SECTION
        ################################################################################

        else:
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
                options_box.prop(em_tools, "pyarchinit_db_path", text="SQLite Database")
                options_box.prop(em_tools, "pyarchinit_mapping", text="Select Mapping")
                options_box.operator("emtools.open_mapping_preferences",
                            text="",
                            icon='PREFERENCES')

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
                # Richiede: db path, mapping
                can_import = bool(
                    em_tools.pyarchinit_db_path and
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


class VIEW3D_PT_graphml_wizard_bridge(bpy.types.Panel):
    """GraphML Wizard in EM Bridge tab (experimental only)."""
    bl_label = "GraphML Wizard (Experimental)"
    bl_idname = "VIEW3D_PT_graphml_wizard_bridge"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM Bridge'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return (
            hasattr(context.scene, 'em_tools') and
            context.scene.em_tools.mode_em_advanced and
            context.scene.em_tools.experimental_features
        )

    def draw_header(self, context):
        self.layout.label(text="", icon='EXPERIMENTAL')

    def draw(self, context):
        layout = self.layout
        em_tools = context.scene.em_tools

        _draw_experimental_notice(layout, context)
        _draw_graphml_wizard(layout, context, em_tools)


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
    VIEW3D_PT_graphml_wizard_bridge,
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
