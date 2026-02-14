# em_setup/properties.py

import bpy
from bpy.props import (
    BoolProperty,
    StringProperty,
    EnumProperty,
    CollectionProperty,
    IntProperty,
    PointerProperty
)

from .excel_helpers import get_excel_sheets, get_excel_columns

# ============================================================================
# CACHE SYSTEM FOR EXCEL DROPDOWNS
# ============================================================================

_excel_cache = {
    'filepath': None,
    'sheets': [],
    'sheet_name': None,
    'columns': []
}

def _get_cached_sheets(filepath):
    """Ottieni fogli con cache per evitare letture ripetute"""
    global _excel_cache

    if filepath != _excel_cache['filepath']:
        # File cambiato, aggiorna cache
        _excel_cache['filepath'] = filepath
        _excel_cache['sheets'] = get_excel_sheets(filepath) if filepath else []
        # Reset cache colonne quando cambia file
        _excel_cache['sheet_name'] = None
        _excel_cache['columns'] = []

    return _excel_cache['sheets']

def _get_cached_columns(filepath, sheet_name):
    """Ottieni colonne con cache per evitare letture ripetute"""
    global _excel_cache

    if filepath != _excel_cache['filepath'] or sheet_name != _excel_cache['sheet_name']:
        # File o foglio cambiato, aggiorna cache
        _excel_cache['filepath'] = filepath
        _excel_cache['sheet_name'] = sheet_name
        _excel_cache['columns'] = get_excel_columns(filepath, sheet_name) if (filepath and sheet_name) else []

    return _excel_cache['columns']

def _clear_excel_cache():
    """Pulisce la cache (chiamata quando si cambia file)"""
    global _excel_cache
    _excel_cache['filepath'] = None
    _excel_cache['sheets'] = []
    _excel_cache['sheet_name'] = None
    _excel_cache['columns'] = []


def get_pyarchinit_mappings(self, context):
    """Get available pyArchInit mapping files from registry"""
    mappings = [("none", "No Mapping", "Select a mapping file")]

    try:
        from s3dgraphy.mappings import mapping_registry
        available_mappings = mapping_registry.list_available_mappings('pyarchinit')
        mappings.extend(available_mappings)
    except Exception as e:
        print(f"Error loading pyArchInit mappings: {str(e)}")

    return mappings


def get_excel_sheet_items(self, context):
    """Callback per EnumProperty: ritorna lista fogli disponibili nel file Excel (con cache)"""
    items = [("none", "Select Sheet", "Select an Excel sheet")]

    try:
        # Ottieni filepath dal contesto appropriato
        filepath = self.generic_xlsx_file

        if filepath:
            # ✅ USA CACHE invece di lettura diretta
            sheets = _get_cached_sheets(filepath)
            if sheets:
                items = [(sheet, sheet, f"Sheet: {sheet}") for sheet in sheets]
            else:
                items = [("error", "No sheets found", "Cannot read Excel file")]
    except Exception as e:
        print(f"Error getting Excel sheets: {e}")
        items = [("error", "Error reading file", str(e))]

    return items


def get_excel_id_column_items(self, context):
    """Callback per EnumProperty: ritorna lista colonne disponibili per ID (con cache)"""
    items = [("none", "Select ID Column", "Select the column containing unique IDs")]

    try:
        filepath = self.generic_xlsx_file
        sheet_name = self.generic_xlsx_sheet

        if filepath and sheet_name and sheet_name != "none":
            # ✅ USA CACHE invece di lettura diretta
            columns = _get_cached_columns(filepath, sheet_name)
            if columns:
                items = [(col, col, f"Column: {col}") for col in columns]
            else:
                items = [("error", "No columns found", "Cannot read sheet columns")]
    except Exception as e:
        print(f"Error getting Excel columns: {e}")
        items = [("error", "Error reading columns", str(e))]

    return items


def get_excel_desc_column_items(self, context):
    """Callback per EnumProperty: ritorna lista colonne disponibili per descrizione (con cache)"""
    items = [("none", "No Description", "Don't import description column")]

    try:
        filepath = self.generic_xlsx_file
        sheet_name = self.generic_xlsx_sheet

        if filepath and sheet_name and sheet_name != "none":
            # ✅ USA CACHE invece di lettura diretta
            columns = _get_cached_columns(filepath, sheet_name)
            if columns:
                # Aggiungi "none" come prima opzione, poi le colonne
                items.extend([(col, col, f"Column: {col}") for col in columns])
    except Exception as e:
        print(f"Error getting Excel columns for description: {e}")

    return items


def update_generic_xlsx_file(self, context):
    """
    Callback chiamato quando il filepath del Generic Excel cambia.
    Resetta i campi dipendenti e valida il file.
    """
    from .excel_helpers import validate_excel_file

    # ✅ PULISCI CACHE quando cambia file (importante per performance!)
    _clear_excel_cache()

    # Reset dei campi dipendenti
    self.generic_xlsx_sheet = "none"
    self.xlsx_id_column = "none"
    self.generic_xlsx_desc_column = "none"

    # Valida il file
    if self.generic_xlsx_file:
        is_valid, error_msg = validate_excel_file(self.generic_xlsx_file)
        if not is_valid:
            # Mostra popup di errore
            def draw_popup(popup_self, popup_context):
                popup_self.layout.label(text="Errore apertura Excel:", icon='ERROR')
                # Splitta il messaggio su più righe
                for line in error_msg.split('\n'):
                    popup_self.layout.label(text=line)

            context.window_manager.popup_menu(draw_popup, title="File Excel non accessibile", icon='ERROR')
        else:
            # ✅ PRE-CARICA i fogli in cache alla prima selezione del file
            # Questo avviene UNA SOLA VOLTA quando l'utente seleziona il file
            _get_cached_sheets(self.generic_xlsx_file)


def update_generic_xlsx_sheet(self, context):
    """
    Callback chiamato quando il foglio Excel selezionato cambia.
    Resetta le colonne dipendenti.
    """
    # Reset delle colonne quando cambia il foglio
    self.xlsx_id_column = "none"
    self.generic_xlsx_desc_column = "none"


def update_resource_folder(self, context):
    """
    Callback chiamato quando resource_folder viene modificato.
    Rimuove lo slash finale per garantire hash consistenti.
    """
    if self.resource_folder:
        # Normalizza i separatori
        path = self.resource_folder.replace('\\', '/')
        # Rimuovi slash finale (ma mantieni // se è un path relativo Blender)
        if path.endswith('/') and not path == '//':
            # Se è un path tipo "//folder/", rimuovi solo l'ultimo slash
            if path.startswith('//'):
                path = path.rstrip('/')
            # Se è un path tipo "/absolute/path/", rimuovi solo l'ultimo slash
            elif len(path) > 1:
                path = path.rstrip('/')

            # Aggiorna solo se è cambiato
            if path != self.resource_folder:
                self.resource_folder = path
                print(f"✅ Resource folder normalized: removed trailing slash")


def get_emdb_mappings(self=None, context=None):
    """
    Get available EMdb mapping files from registry.
    Accepts optional parameters for compatibility with EnumProperty callbacks.
    """
    try:
        from s3dgraphy.mappings import mapping_registry
        return mapping_registry.list_available_mappings('emdb')
    except Exception as e:
        print(f"Error loading EMdb mappings: {str(e)}")
        return [("none", "No Mapping", "Select a mapping file")]


class AuxiliaryFileProperties(bpy.types.PropertyGroup):
    """Properties for auxiliary files (EMdb, pyArchInit, etc.)"""

    name: StringProperty(name="File Name")  # type: ignore

    filepath: StringProperty(
        name="File Path",
        subtype='FILE_PATH',
        description="Path to the auxiliary file",
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    file_type: EnumProperty(
        name="File Type",
        items=[
            ("emdb_xlsx", "EMdb Excel", "Import from EMdb Excel format"),
            ("pyarchinit", "pyArchInit", "Import from pyArchInit SQLite DB"),
            ("dosco", "DosCo", "DosCo documentation folder for harvesting document files"),
            ("source_list", "Source List", "Excel file with sources descriptions for document/extractor/combiner nodes")
        ],
        default="emdb_xlsx"
    )  # type: ignore

    emdb_mapping: EnumProperty(
        name="EMdb Format",
        items=lambda self, context: get_emdb_mappings(),
        description="Select EMdb format"
    )  # type: ignore

    pyarchinit_mapping: EnumProperty(
        name="pyArchInit Mapping",
        items=get_pyarchinit_mappings,
        description="Select pyArchInit table mapping"
    )  # type: ignore

    resource_folder: StringProperty(
        name="Resource Folder",
        description="Parent folder to search for resources. Use relative path (// prefix) for cross-PC compatibility",
        subtype='DIR_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set(),
        update=update_resource_folder  # ✅ Rimuove automaticamente lo slash finale
    )  # type: ignore

    expanded: BoolProperty(
        name="Show Details",
        default=False
    )  # type: ignore

    auto_reload_on_em_update: BoolProperty(
        name="Auto-reload on EM Update",
        description="Automatically import this auxiliary file when the parent GraphML is loaded/reloaded",
        default=False
    )  # type: ignore

    custom_thumbs_path: StringProperty(
        name="Thumbnails Path",
        description="Custom path for thumbnails folder (leave empty for automatic)",
        subtype='DIR_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    show_resources_section: BoolProperty(
        name="Show Document Resources",
        description="Expand/collapse document resources section",
        default=False
    )  # type: ignore

    show_thumbs_path_section: BoolProperty(
        name="Show Thumbnails Path",
        description="Expand/collapse thumbnails path settings",
        default=False
    )  # type: ignore

    show_pyarchinit_mapping_info: BoolProperty(
        name="Show Mapping Info",
        description="Expand to see details for the selected pyArchInit mapping",
        default=False
    )  # type: ignore

    # DosCo-specific properties
    dosco_folder: StringProperty(
        name="DosCo Folder",
        description="Path to DosCo documentation folder for harvesting files",
        subtype='DIR_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    dosco_overwrite_paths: BoolProperty(
        name="Overwrite paths with DosCo files",
        description="Overwrite node paths with files found in DosCo folder",
        default=True
    )  # type: ignore

    dosco_preserve_web_urls: BoolProperty(
        name="Preserve web URLs",
        description="Don't overwrite http/https URLs when harvesting from DosCo",
        default=True
    )  # type: ignore


class EMToolsProperties(bpy.types.PropertyGroup):
    """Legacy PropertyGroup - kept for backward compatibility"""

    name: StringProperty(name="GraphML File")  # type: ignore
    expanded: BoolProperty(name="Auxiliary files", default=False)  # type: ignore

    graphml_path: StringProperty(
        name="GraphML Path",
        subtype='FILE_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    dosco_dir: StringProperty(
        name="DosCo Directory",
        subtype='DIR_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    xlsx_filepath: StringProperty(
        name="Source File (xlsx)",
        subtype='FILE_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    xlsx_3DGIS_database_file: StringProperty(
        name="3D GIS Database File",
        description="Path to the 3D GIS database Excel file",
        subtype='FILE_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    emdb_filepath: StringProperty(
        name="EMdb File (sqlite)",
        subtype='FILE_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    is_graph: BoolProperty(name="Graph Exists", default=False)  # type: ignore

    graph_code: StringProperty(
        name="Graph Code",
        description="Human-readable code for the graph (e.g. VDL16)",
        default=""
    )  # type: ignore

    auxiliary_files: CollectionProperty(type=AuxiliaryFileProperties)  # type: ignore
    active_auxiliary_index: IntProperty()  # type: ignore

    is_publishable: BoolProperty(
        name="Publishable",
        description="Include this graph in multigrafo exports",
        default=True
    )  # type: ignore


class EMToolsSettings(bpy.types.PropertyGroup):
    """Settings for import panel (Excel, pyArchInit, etc.)"""

    # Generic Excel import
    generic_xlsx_file: StringProperty(
        name="Excel File",
        description="Path to generic Excel file",
        subtype='FILE_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set(),
        update=update_generic_xlsx_file
    )  # type: ignore

    generic_xlsx_sheet: EnumProperty(
        name="Sheet Name",
        description="Select the Excel sheet to import",
        items=get_excel_sheet_items,
        update=update_generic_xlsx_sheet
    )  # type: ignore

    xlsx_id_column: EnumProperty(
        name="ID Column",
        description="Select the column containing unique identifiers",
        items=get_excel_id_column_items
    )  # type: ignore

    generic_xlsx_desc_column: EnumProperty(
        name="Description Column",
        description="Optional: Select a column for descriptions",
        items=get_excel_desc_column_items
    )  # type: ignore

    # pyArchInit import
    pyarchinit_db_path: StringProperty(
        name="pyArchInit DB",
        description="Path to pyArchInit SQLite database",
        subtype='FILE_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    pyarchinit_table: EnumProperty(
        name="Table",
        items=[
            ('US', 'US', 'Unità Stratigrafiche'),
            ('SITE', 'Site', 'Siti'),
            ('PERIODIZATION', 'Periodization', 'Periodizzazione')
        ],
        default='US'
    )  # type: ignore

    pyarchinit_mapping: EnumProperty(
        name="Mapping",
        items=get_pyarchinit_mappings,
        description="Select mapping configuration"
    )  # type: ignore

    # EMdb Excel import
    emdb_xlsx_file: StringProperty(
        name="EMdb File",
        description="Path to EMdb Excel file",
        subtype='FILE_PATH',
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    emdb_mapping: EnumProperty(
        name="EMdb Format",
        items=lambda self, context: get_emdb_mappings(),
        description="Select EMdb format"
    )  # type: ignore


class GraphMLFileItem(bpy.types.PropertyGroup):
    """Represents a GraphML file in the multi-graph manager"""

    name: StringProperty(
        name="Name",
        description="Display name for this GraphML file",
        default="New Graph"
    )  # type: ignore

    is_active: BoolProperty(
        name="Active",
        description="Whether this graph is currently active",
        default=False
    )  # type: ignore

    is_loaded: BoolProperty(
        name="Loaded",
        description="Whether this graph has been loaded",
        default=False
    )  # type: ignore

    graphml_path: StringProperty(
        name="GraphML Path",
        description="Full path to the GraphML file",
        subtype='FILE_PATH',
        default="",
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    expanded: BoolProperty(
        name="Auxiliary Resources",
        description="Show/hide file details",
        default=False
    )  # type: ignore

    dosco_dir: StringProperty(
        name="DosCo Directory",
        description="Path to DosCo documentation folder",
        subtype='DIR_PATH',
        default="",
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    xlsx_filepath: StringProperty(
        name="XLSX File",
        description="Path to Excel source file",
        subtype='FILE_PATH',
        default="",
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    emdb_filepath: StringProperty(
        name="EMdb File",
        description="Path to EMdb SQLite database",
        subtype='FILE_PATH',
        default="",
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()
    )  # type: ignore

    graph_code: StringProperty(
        name="Graph Code",
        description="Human-readable code for the graph (e.g., BAS_IUL)",
        default=""
    )  # type: ignore

    import_warnings: StringProperty(
        name="Import Warnings",
        description="Warnings generated during GraphML import (e.g., duplicate extractor names)",
        default=""
    )  # type: ignore

    auxiliary_files: CollectionProperty(type=AuxiliaryFileProperties)  # type: ignore
    active_auxiliary_index: IntProperty()  # type: ignore

    is_publishable: BoolProperty(
        name="Publishable",
        description="Include this graph in multigrafo exports",
        default=True
    )  # type: ignore

    # Graph statistics (cached counts)
    stratigraphic_count: IntProperty(
        name="Stratigraphic Nodes Count",
        description="Number of stratigraphic nodes in the graph",
        default=0
    )  # type: ignore

    epoch_count: IntProperty(
        name="Epochs Count",
        description="Number of epoch nodes in the graph",
        default=0
    )  # type: ignore

    property_count: IntProperty(
        name="Properties Count",
        description="Number of property nodes in the graph",
        default=0
    )  # type: ignore

    document_count: IntProperty(
        name="Documents Count",
        description="Number of document nodes in the graph",
        default=0
    )  # type: ignore


# Registration
# NOTE: AuxiliaryFileProperties and GraphMLFileItem are registered HERE
# and imported by em_props.py which uses them in EM_Tools
classes = (
    AuxiliaryFileProperties,
    GraphMLFileItem,
    EMToolsProperties,
    EMToolsSettings,
)


def register():
    """Register all PropertyGroups including AuxiliaryFileProperties and GraphMLFileItem"""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
