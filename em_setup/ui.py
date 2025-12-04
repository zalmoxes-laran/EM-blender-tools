import bpy
import os
from bpy.props import EnumProperty

# Relative imports from parent modules
from ..import_operators.importer_graphml import EM_import_GraphML
from .. import icons_manager
from ..populate_lists import clear_lists, populate_blender_lists_from_graph
from ..functions import get_compatible_icon
from ..thumb_utils import reload_doc_previews_from_cache, has_doc_thumbs
from ..operators.graphml_converter import GRAPHML_OT_convert_borders

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


# ============================================================================
# UI CLASSES
# ============================================================================

class AUXILIARY_UL_files(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)

            # Menu contestuale
            #op = row.operator("auxiliary.context_menu",
            #                text="",
            #                icon='DOWNARROW_HLT',
            #                emboss=False)

            # Tipo file icon




            if item.file_type == "emdb_xlsx":
                row.label(text="", icon_value=icons_manager.get_icon_value("EMdb_logo"))

            if item.file_type == "pyarchinit":
                row.label(text="", icon_value=icons_manager.get_icon_value("pyarchinit"))

            if item.file_type == "generic_xlsx":
                row.label(text="", icon='SPREADSHEET')

            # Nome file
            row.prop(item, "name", text="", emboss=False)

            # Stato del file
            if item.filepath:
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
                # Pulsante per aprire nel Graph Editor (accanto a import.em_graphml)
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

    bl_label = f"EM Data Ingestion {get_em_tools_version()}"
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
            activemode_label = "Switch to Basic 3D GIS"
            active_label = "Active Mode: Advanced EM"
        else:
            activemode_label = "Switch to Advanced EM"
            active_label = "Active Mode: Basic 3D GIS"

        # Disegna il pulsante
        col.label(text=active_label)
        col = split.column()
        col.operator("emtools.switch_mode", text=activemode_label)

        if not em_tools.mode_em_advanced and len(em_tools.graphml_files) > 0:
            row = box.row()
            row.alert = True  # Imposta il colore rosso
            row.label(text=" Warning: Starting from a blank file is strongly recommended", icon='ERROR')
            row = box.row()
            row.alert = True
            row.label(text="when working in Basic 3D GIS mode with existing Advanced EM graphs.")

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

                # US/USV count
                col = split.column()
                col.label(text="US/USV")
                us_count = len(em_tools.stratigraphy.units) if hasattr(em_tools, 'stratigraphy') else 0
                col.label(text=str(us_count), icon='OUTLINER_OB_MESH')

                # Separatore verticale
                col.separator()

                # Epochs count
                col = split.column()
                col.label(text="Epochs")
                epoch_count = len(em_tools.epochs.list) if hasattr(em_tools, 'epochs') else 0
                col.label(text=str(epoch_count), icon='TIME')

                # Properties count
                col = split.column()
                col.label(text="Properties")
                props_count = len(scene.em_properties_list) if hasattr(scene, 'em_properties_list') else 0
                col.label(text=str(props_count), icon='PROPERTIES')

                # Sources count
                col = split.column()
                col.label(text="Sources")
                sources_count = len(scene.em_sources_list) if hasattr(scene, 'em_sources_list') else 0
                col.label(text=str(sources_count), icon='FILE_TEXT')


                ####################################################

                # Se abbiamo un codice per il grafo, mostriamolo come non modificabile
                warning_found = False

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

                # Se ci sono warning, mostra il box di warning
                if graph_code_warning or epochs_date_warning:
                    warning_box = layout.box()
                    warning_box.label(text="GraphML Warning:", icon='ERROR')

                    if graph_code_warning:
                        warning_box.label(text="- Please add a proper site ID in the header")

                    if epochs_date_warning:
                        warning_box.label(text="- Update the epochs placeholder dates (xx)")

                    op = warning_box.operator("wm.url_open", text="Quick guide", icon="HELP")
                    op.url = "https://docs.extendedmatrix.org/en/1.5.0dev/data_funnel.html#important-considerations"

                box = layout.box()
                em_settings = bpy.context.window_manager.em_addon_settings

                box.prop(em_settings, "dosco_options", text="DosCo Folder", icon="TRIA_DOWN" if em_settings.dosco_options else "TRIA_RIGHT", emboss=False)

                if em_settings.dosco_options:
                    # Path to DosCo folder
                    box.prop(active_file, "dosco_dir", text="Set Path")

                    if em_tools.experimental_features:
                        box.prop(em_settings, "dosco_advanced_options", text="More options", icon="TRIA_DOWN" if em_settings.dosco_advanced_options else "TRIA_RIGHT", emboss=False)

                        if em_settings.dosco_advanced_options:
                            box.label(text="Populate extractors, documents and combiners using DosCo files:")
                            row = box.row()
                            row.prop(em_settings, 'overwrite_url_with_dosco_filepath', text="Overwrite paths with DosCo files")

                            # Add a more informative tooltip
                            subbox = box.box()
                            subbox.label(text="When enabled, node paths will be linked to files in DosCo")
                            subbox.label(text="Examples:")
                            subbox.label(text="Node GT16.D.01 → Searches for GT16.D.01 and D.01 in DosCo")

                            row = box.row()
                            row.prop(em_settings, 'preserve_web_url', text="Preserve web URLs (don't overwrite http/https)")

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

                        # File path e tipo
                        row = box.row()
                        row.prop(aux_file, "filepath", text="Path")
                        row.prop(aux_file, "file_type", text="Type")


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
                                        warn_row = warn_box.row()
                                        warn_row.label(text="Use relative path (// prefix) for cross-PC compatibility",
                                                    icon='ERROR')
                                        warn_row = warn_box.row()
                                        warn_row.label(text="Example: //Resources or //../../SharedFolder/Resources")

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

                            # Mostra info sul mapping selezionato
                            if aux_file.pyarchinit_mapping != "none":
                                desc_box = box.box()
                                desc_box.label(text="Mapping Info:")
                                mapping_data = get_mapping_description(aux_file.pyarchinit_mapping, "pyarchinit")
                                if mapping_data:
                                    row = desc_box.row()
                                    row.label(text=f"Name: {mapping_data['name']}")
                                    if "description" in mapping_data:
                                        desc_box.label(text=mapping_data["description"])
                                    if "table_settings" in mapping_data:
                                        desc_box.label(text=f"Table: {mapping_data['table_settings']['table_name']}")

            # Advanced Tools section
            box = layout.box()
            box.prop(em_tools, "show_advanced_tools",
                    text="Utilities & Settings",
                    icon="TRIA_DOWN" if em_tools.show_advanced_tools else "TRIA_RIGHT",
                    emboss=False)

            if em_tools.show_advanced_tools:
                # Convert Legacy GraphML
                row = box.row()
                row.operator(GRAPHML_OT_convert_borders.bl_idname,
                            text="Convert legacy GraphML (1.x->1.5)",
                            icon='FILE_REFRESH')

                # Collection Manager
                collection_box = box.box()
                collection_box.prop(em_tools, "show_collection_manager",
                                text="Collection Manager",
                                icon="TRIA_DOWN" if em_tools.show_collection_manager else "TRIA_RIGHT",
                                emboss=False)

                if em_tools.show_collection_manager:
                    col = collection_box.column(align=True)
                    col.operator("create.collection",
                                text="Create Standard Collections",
                                icon="COLLECTION_NEW")

                    # Info box sulle collezioni
                    info_box = collection_box.box()
                    info_box.label(text="Standard Collections:")
                    info_col = info_box.column(align=True)
                    #info_col.label(text="• EM - Extended Matrix nodes/proxies")
                    info_col.label(text="• Proxy - 3D proxy models")
                    info_col.label(text="• RM - Representation models")
                    info_col.label(text="• CAMS - Cameras and related labels")

                # Manage Object Prefixes
                row = box.row()
                row.operator("em.manage_object_prefixes",
                            text="Manage Proxies' Prefixes",
                            icon='SYNTAX_ON')

                # Experimental features section
                if em_tools.experimental_features:
                    exp_box = box.box()
                    exp_box.label(text="Experimental Tools:", icon="EXPERIMENTAL")

                    row = exp_box.row()
                    row.operator("em.rebuild_graph_indices",
                                text="Rebuild Graph Indices",
                                icon="FILE_REFRESH")

                    row = exp_box.row()
                    row.operator("em.benchmark_property_functions",
                                text="Benchmark Property Functions",
                                icon="TIME")

                row = box.row()
                row.prop(em_tools, "experimental_features", text="Enable Experimental Features", icon="EXPERIMENTAL")

                if em_tools.experimental_features:
                    warning_box = box.box()
                    warning_box.alert = True
                    warning_box.label(text="Warning: these features are experimental.", icon='ERROR')
                    warning_box.label(text="They should not be used in a production environment.")

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
                options_box.prop(em_tools, "generic_xlsx_file", text="Excel File")
                options_box.prop(em_tools, "xlsx_sheet_name", text="Sheet Name")
                options_box.prop(em_tools, "xlsx_id_column", text="ID Column")

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
