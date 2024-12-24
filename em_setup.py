import bpy
from .s3Dgraphy import get_graph, remove_graph
from .s3Dgraphy.nodes.stratigraphic_node import StratigraphicNode

from . import sqlite_io
from .__init__ import get_bl_info

from .import_operators.importer_graphml import EM_import_GraphML

from .populate_lists import *

from bpy.props import (BoolProperty, # type: ignore
                       FloatProperty,
                       StringProperty,
                       EnumProperty,
                       CollectionProperty,
                       IntProperty,
                       PointerProperty,
                       FloatVectorProperty,
                       )
from bpy.types import Operator # type: ignore

from .import_operators.import_EMdb import *



class AuxiliaryFileProperties(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="File Name") # type: ignore
    filepath: bpy.props.StringProperty(
        name="File Path",
        subtype='FILE_PATH'
    ) # type: ignore
    file_type: bpy.props.EnumProperty(
        name="File Type",
        items=[
            ("generic_xlsx", "Generic Excel", "Import from generic Excel file"),
            ("pyarchinit", "pyArchInit", "Import from pyArchInit SQLite DB"),
            ("emdb_xlsx", "EMdb Excel", "Import from EMdb Excel format")
        ],
        default="emdb_xlsx"
    ) # type: ignore
    emdb_mapping: bpy.props.EnumProperty(
        name="EMdb Format",
        items=lambda self, context: get_emdb_mappings(),
        description="Select EMdb format"
    ) # type: ignore
    expanded: bpy.props.BoolProperty(
        name="Show Details",
        default=False
    ) # type: ignore

class EMToolsProperties(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="GraphML File") # type: ignore
    expanded: bpy.props.BoolProperty(name="Auxiliary files", default=False) # type: ignore
    graphml_path: bpy.props.StringProperty(name="GraphML Path", subtype='FILE_PATH')   # type: ignore # Aggiungiamo il campo per il percorso
    dosco_dir: bpy.props.StringProperty(name="DosCo Directory", subtype='DIR_PATH') # type: ignore
    xlsx_filepath: bpy.props.StringProperty(name="Source File (xlsx)", subtype='FILE_PATH') # type: ignore
    xlsx_3DGIS_database_file: bpy.props.StringProperty(
        name="3D GIS Database File", 
        description="Path to the 3D GIS database Excel file",
        subtype='FILE_PATH'
    )     # type: ignore
    emdb_filepath: bpy.props.StringProperty(name="EMdb File (sqlite)", subtype='FILE_PATH') # type: ignore
    is_graph: bpy.props.BoolProperty(name="Graph Exists", default=False)  # type: ignore # Aggiungi questa riga

    auxiliary_files: bpy.props.CollectionProperty(type=AuxiliaryFileProperties) # type: ignore
    active_auxiliary_index: bpy.props.IntProperty() # type: ignore

class AUXILIARY_UL_files(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            
            # Menu contestuale
            op = row.operator("auxiliary.context_menu", 
                            text="", 
                            icon='DOWNARROW_HLT',
                            emboss=False)
            
            # Nome file
            row.prop(item, "name", text="", emboss=False)
            
            # Tipo file icon
            icon = 'SPREADSHEET' if item.file_type == "emdb_xlsx" else 'FILE_VOLUME'
            row.label(text="", icon=icon)
            
            # Stato del file
            if item.filepath:
                row.label(text="", icon='CHECKMARK')
            else:
                row.label(text="", icon='ERROR')

            # Quick actions
            row.operator("auxiliary.reload", text="", icon="FILE_REFRESH", emboss=False).file_index = index
            row.operator("auxiliary.import_now", text="", icon="IMPORT", emboss=False)

def get_emdb_mappings():
    """Funzione per ottenere i mapping EMdb disponibili"""
    mappings = []
    mapping_dir = os.path.join(os.path.dirname(__file__), "emdbjson")
    
    # Verifica se la directory esiste
    if not os.path.exists(mapping_dir):
        os.makedirs(mapping_dir)
        return [("none", "No mappings found", "")]
    
    try:
        for file in os.listdir(mapping_dir):
            if file.endswith('.json'):
                file_path = os.path.join(mapping_dir, file)
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        if not content.strip():  # Se il file è vuoto
                            print(f"Warning: Empty mapping file: {file}")
                            continue
                            
                        try:
                            data = json.loads(content)
                            name = data.get("name", os.path.splitext(file)[0])
                            mappings.append((file, name, data.get("description", "")))
                        except json.JSONDecodeError as e:
                            print(f"Error decoding JSON from {file}: {str(e)}")
                            continue
                except IOError as e:
                    print(f"Error reading file {file}: {str(e)}")
                    continue
                    
    except Exception as e:
        print(f"Error scanning mapping directory: {str(e)}")
        
    return mappings if mappings else [("none", "No mappings found", "")]

class EMToolsSettings(bpy.types.PropertyGroup):
    graphml_files: bpy.props.CollectionProperty(type=EMToolsProperties) # type: ignore
    active_file_index: bpy.props.IntProperty() # type: ignore
    mode_switch: bpy.props.BoolProperty(
        name="Modalità EM Avanzata",
        description="Switch tra modalità 3D GIS e modalità EM avanzata",
        default=True
    ) # type: ignore


    mode_3dgis_import_type: bpy.props.EnumProperty(
        name="Import Type",
        items=[
            ("generic_xlsx", "Generic Excel", "Import from generic Excel file"),
            ("pyarchinit", "pyArchInit", "Import from pyArchInit SQLite DB"),
            ("emdb_xlsx", "EMdb Excel", "Import from EMdb Excel format")
        ],
        default="generic_xlsx"
    ) # type: ignore

    # Generic Excel properties
    generic_xlsx_file: bpy.props.StringProperty(
        name="Excel File",
        description="Path to generic Excel file",
        subtype='FILE_PATH'
    ) # type: ignore
    xlsx_sheet_name: bpy.props.StringProperty(
        name="Sheet Name",
        description="Name of the Excel sheet containing the data",
        default="Sheet1"
    ) # type: ignore

    xlsx_id_column: bpy.props.StringProperty(
        name="ID Column",
        description="Name of the column containing unique IDs",
        default="ID"
    ) # type: ignore

    # pyArchInit properties
    pyarchinit_db_path: bpy.props.StringProperty(
        name="SQLite Database",
        description="Path to pyArchInit SQLite database",
        subtype='FILE_PATH'
    ) # type: ignore

    pyarchinit_table: bpy.props.StringProperty(
        name="Table Name",
        description="Name of the table to import",
        default="us_table"
    ) # type: ignore

    # EMdb properties
    emdb_xlsx_file: bpy.props.StringProperty(
        name="EMdb Excel File",
        description="Path to EMdb Excel file",
        subtype='FILE_PATH'
    ) # type: ignore


    emdb_mapping: bpy.props.EnumProperty(
            name="EMdb Format",
            items=lambda self, context: get_emdb_mappings(),
            description="Select EMdb format"
        ) # type: ignore

class EMTOOLS_UL_files(bpy.types.UIList):
    """UIList to display the GraphML files with icons to indicate graph presence and actions"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        graph_data = get_graph(item.name)
        # Aggiungiamo stampe di debug
        #print(f"Checking graph '{item.name}':")
        #print(f"Graph data exists: {bool(graph_data)}")
        if graph_data:
            print(f"Number of nodes: {len(graph_data.nodes)}")
            print(f"First few nodes: {[node.node_id for node in graph_data.nodes[:3]]}")
        is_graph_present = bool(graph_data and len(graph_data.nodes) > 0)
        #print(f"Is graph present: {is_graph_present}")

        # Mostra il nome del file nella lista
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=False)

            # Creare un'area per i pulsanti
            split = layout.split(factor=0.5, align=True)

            # Bottone per indicare se il grafo esiste o meno
            if is_graph_present:
                status_icon = 'SEQUENCE_COLOR_04'  # Icona verde se il grafo esiste
                #print(f"Setting green icon for {item.name}")
            else:
                status_icon = 'SEQUENCE_COLOR_01'  # Icona rossa se il grafo non esiste
                #print(f"Setting red icon for {item.name}")

            # Mostra semplicemente l'icona dello stato
            row = split.row()
            row.label(text="", icon=status_icon)

            # Pulsante per ricaricare il file GraphML (con icona FILE_REFRESH)
            row = layout.row(align=True)
            op = row.operator("import.em_graphml", text="", icon="FILE_REFRESH", emboss=False)
            op.graphml_index = index  # Passa l'indice corretto per caricare il GraphML


            # Disabilita il pulsante se l'icona è rossa (grafo non esistente)
            if is_graph_present:
                # Pulsante per aggiornare le liste (con icona FILE_REFRESH)
                row = layout.row(align=True)
                op = row.operator("em_tools.populate_lists", text="", icon="SEQ_SEQUENCER", emboss=False)
                op.graphml_index = index  # Passa l'indice corretto per aggiornare le liste
            else:
                row = layout.row()
                row.enabled = False  # Disabilita il layout (grigio)
                row.label(text="", icon="SEQ_SEQUENCER")  # Usa un'icona per mostrare un pulsante disabilitato

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name)

# Definisci la classe per memorizzare i file GraphML e lo stato del grafo
class GraphMLFileItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="File Name") # type: ignore
    is_graph: bpy.props.BoolProperty(name="Graph Exists", default=False) # type: ignore

class EMToolsSwitchModeOperator(bpy.types.Operator):
    bl_idname = "emtools.switch_mode"
    bl_label = "Switch Mode"
    
    def execute(self, context):
        em_tools = context.scene.em_tools
        
        # Alterna tra le due modalità
        em_tools.mode_switch = not em_tools.mode_switch
        
        # Messaggio per informare l'utente
        if em_tools.mode_switch:
            self.report({'INFO'}, "Switched to Advanced EM Mode")
        else:
            self.report({'INFO'}, "Switched to 3D GIS Mode")
        
        return {'FINISHED'}

class EM_SetupPanel(bpy.types.Panel):
    bl_info = get_bl_info()
    devel_version = bl_info.get('devel_version', 'Unknown version')
    bl_label = "EM setup " + devel_version
    bl_idname = "VIEW3D_PT_EM_Tools_Setup"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_tools = scene.em_tools

        box = layout.box()
        row = box.row(align=True)
        #row = layout.row(align=True)
        split = row.split()
        col = split.column()

        activemode_label = ""
        active_label = ""
        # Cambia l'etichetta del pulsante in base alla modalità attiva
        if em_tools.mode_switch:
            activemode_label = "Switch to 3D GIS"
            active_label = "Advanced EM Mode active"
        else:
            activemode_label = "Switch to Advanced EM"
            active_label = "3D GIS Mode active"
        
        # Disegna il pulsante
        
        col.label(text=active_label)
        col = split.column()
        col.operator("emtools.switch_mode", text=activemode_label)

        if em_tools.mode_switch:
            # List of GraphML files
            row = layout.row()
            row.template_list("EMTOOLS_UL_files", "", em_tools, "graphml_files", em_tools, "active_file_index", rows=3)

            row = layout.row(align=True)
            row.operator('em_tools.add_file', text="Add UT", icon="ADD")
            row.operator('em_tools.remove_file', text="Remove UT", icon="REMOVE")

            # Details for selected GraphML file
            if em_tools.active_file_index >= 0 and em_tools.graphml_files:
                active_file = em_tools.graphml_files[em_tools.active_file_index]

                # Path to GraphML
                row = layout.row(align=True)
                row.prop(active_file, "graphml_path", text="Path")

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

                    box = layout.box()
                    # Path to DosCo folder
                    box.prop(active_file, "dosco_dir", text="DosCo Directory")

                    em_settings = bpy.context.window_manager.em_addon_settings
                    #box.prop(em_settings, "dosco_advanced_options", 

                    box.prop(em_settings, "dosco_advanced_options", text="DosCo advanced options", icon="TRIA_DOWN" if em_settings.dosco_advanced_options else "TRIA_RIGHT", emboss=False)

                    if em_settings.dosco_advanced_options:
                        #row = box.row()
                        box.label(text="Populate extractors, documents and combiners using DosCo files:")
                        #row = box.row()
                        box.prop(em_settings, 'overwrite_url_with_dosco_filepath', text = "Overwrite paths")
                        box.prop(em_settings, 'preserve_web_url', text = "Preserve web urls (if any)")

                    '''
                    # source XLSX file
                    box.prop(active_file, "xlsx_filepath", text="Source File (xlsx)")
                    # EMdb file
                    box.prop(active_file, "emdb_filepath", text="EMdb File (sqlite)")
                    '''

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
                options_box.prop(em_tools, "pyarchinit_table", text="Table Name")
                
            elif em_tools.mode_3dgis_import_type == "emdb_xlsx":
                options_box.label(text="EMdb Excel Import Settings:")
                options_box.prop(em_tools, "emdb_xlsx_file", text="EMdb Excel File")
                options_box.prop(em_tools, "emdb_mapping", text="EMdb Format")
                
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
            
            # Import button con icona
            row = box.row(align=True)
            row.scale_y = 1.5  # Bottone più grande
            row.operator("em.import_3dgis_database", 
                        text="Import 3D GIS Database", 
                        icon='IMPORT')


        ############# box con le statistiche del file ##################
        box = layout.box()
        row = box.row(align=True)
        #row = layout.row(align=True)
        split = row.split()
        col = split.column()
        col.label(text="US/USV")
        #col = split.column()
        col.prop(scene, "em_list", text='')
        col = split.column()
        col.label(text="Periods")
        #col = split.column()
        col.prop(scene, "epoch_list", text='')

        col = split.column()
        col.label(text="Properties")
        #col = split.column()
        col.prop(scene, "em_properties_list", text='')

        col = split.column()
        col.label(text="Sources")
        #col = split.column()
        col.prop(scene, "em_sources_list", text='')


def get_mapping_description(mapping_file):
    """Recupera la descrizione del mapping dal file JSON."""
    mapping_path = os.path.join(os.path.dirname(__file__), "emdbjson", mapping_file)
    try:
        with open(mapping_path) as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading mapping description: {str(e)}")
        return None

class EM_OT_import_3dgis_database(bpy.types.Operator):
    """Import operator for both 3D GIS mode and advanced EM mode"""
    bl_idname = "em.import_3dgis_database"
    bl_label = "Import Database"
    bl_description = "Import data from selected database format"
    bl_options = {'REGISTER', 'UNDO'}

    # Per gestire import da auxiliary files
    auxiliary_mode: bpy.props.BoolProperty(default=False) # type: ignore
    graphml_index: bpy.props.IntProperty(default=-1) # type: ignore
    auxiliary_index: bpy.props.IntProperty(default=-1) # type: ignore

    def get_import_settings(self, context):
        """Recupera le impostazioni di import in base alla modalità"""
        em_tools = context.scene.em_tools

        if self.auxiliary_mode:
            # Modalità EM avanzata - auxiliary file
            graphml = em_tools.graphml_files[self.graphml_index]
            aux_file = graphml.auxiliary_files[self.auxiliary_index]
            return {
                'import_type': aux_file.file_type,
                'filepath': aux_file.filepath,
                'mapping': aux_file.emdb_mapping if aux_file.file_type == "emdb_xlsx" else None,
                'sheet_name': em_tools.xlsx_sheet_name,
                'id_column': em_tools.xlsx_id_column,
                'parent_graphml': graphml
            }
        else:
            # Modalità 3D GIS
            return {
                'import_type': em_tools.mode_3dgis_import_type,
                'filepath': em_tools.xlsx_3DGIS_database_file,
                'mapping': em_tools.emdb_mapping if em_tools.mode_3dgis_import_type == "emdb_xlsx" else None,
                'sheet_name': em_tools.xlsx_sheet_name,
                'id_column': em_tools.xlsx_id_column,
                'parent_graphml': None
            }

    def create_importer(self, settings):
        """Crea l'importer appropriato basato sulle impostazioni"""
        from .s3Dgraphy.importer import create_importer

        if settings['import_type'] == "emdb_xlsx":
            return create_importer(
                filepath=settings['filepath'],
                format_type='xlsx',
                mapping_name=settings['mapping'],
                overwrite=True
            )
        elif settings['import_type'] == "generic_xlsx":
            return create_importer(
                filepath=settings['filepath'],
                format_type='xlsx',
                id_column=settings['id_column'],
                overwrite=True
            )
        elif settings['import_type'] == "pyarchinit":
            # TODO: Implementare PyArchInit importer
            pass

    def execute(self, context):
        try:
            # Ottieni impostazioni
            settings = self.get_import_settings(context)
            
            # Verifica file path
            if not settings['filepath']:
                self.report({'ERROR'}, "No file path specified")
                return {'CANCELLED'}

            # Crea e configura importer
            importer = self.create_importer(settings)
            if not importer:
                self.report({'ERROR'}, "Failed to create importer")
                return {'CANCELLED'}

            # Esegui import
            graph = importer.parse()

            # Gestisci risultati in base alla modalità
            if self.auxiliary_mode and settings['parent_graphml']:
                # Collega i dati importati al GraphML parent
                self.link_to_graphml(graph, settings['parent_graphml'])
            else:
                # Modalità 3D GIS - popola le liste di Blender
                from .populate_lists import populate_blender_lists_from_graph
                populate_blender_lists_from_graph(context, graph)

            # Mostra warning se presenti
            if importer.warnings:
                for warning in importer.warnings:
                    self.report({'WARNING'}, warning)

            self.report({'INFO'}, "Import completed successfully")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {str(e)}")
            return {'CANCELLED'}

    def link_to_graphml(self, imported_graph, parent_graphml):
        """Collega i dati importati al grafo GraphML parent"""
        # Qui implementeremo la logica di collegamento
        # basata sul mapping quando lo definiremo
        pass

class EMToolsAddFile(bpy.types.Operator):
    bl_idname = "em_tools.add_file"
    bl_label = "Add GraphML File"

    def execute(self, context):
        em_tools = context.scene.em_tools
        new_file = em_tools.graphml_files.add()
        new_file.name = "New GraphML File"
        em_tools.active_file_index = len(em_tools.graphml_files) - 1
        return {'FINISHED'}

class EMToolsRemoveFile(bpy.types.Operator):
    bl_idname = "em_tools.remove_file"
    bl_label = "Remove GraphML File"

    def execute(self, context):
        em_tools = context.scene.em_tools
        if em_tools.active_file_index >= 0:
            graphml = em_tools.graphml_files[em_tools.active_file_index]
            remove_graph(graphml.name)

            em_tools.graphml_files.remove(em_tools.active_file_index)
            em_tools.active_file_index = min(max(0, em_tools.active_file_index - 1), len(em_tools.graphml_files) - 1)

        return {'FINISHED'}

class EM_InvokePopulateLists(bpy.types.Operator):
    bl_idname = "em_tools.populate_lists"
    bl_label = "Activate EM"
    bl_description = "Activate and show this EM in the lists below"
    bl_options = {"REGISTER", "UNDO"}

    # Aggiungiamo una proprietà per passare l'indice del file GraphML selezionato
    graphml_index: bpy.props.IntProperty() # type: ignore

    def execute(self, context):
        # Ottieni il GraphML attivo dal contesto
        scene = context.scene
        em_tools = scene.em_tools

        if self.graphml_index >= 0 and em_tools.graphml_files[self.graphml_index]:
            # Ottieni il file GraphML selezionato
            graphml_file = em_tools.graphml_files[self.graphml_index]

            # Recupero il grafo
            graph_instance = get_graph(graphml_file.name)

            # Clear Blender Lists
            clear_lists(context)

            # Istanzia l'operatore `EM_import_GraphML`
            populate_blender_lists_from_graph(context, graph_instance)

            self.report({'INFO'}, "Populated Blender lists from GraphML")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "No valid GraphML file selected")
            return {'CANCELLED'}


class AUXILIARY_OT_add_file(bpy.types.Operator):
    bl_idname = "auxiliary.add_file"
    bl_label = "Add Auxiliary File"
    bl_description = "Add a new auxiliary file to the selected GraphML"

    def execute(self, context):
        em_tools = context.scene.em_tools
        if em_tools.active_file_index >= 0:
            graphml = em_tools.graphml_files[em_tools.active_file_index]
            new_file = graphml.auxiliary_files.add()
            new_file.name = "New Auxiliary File"
            graphml.active_auxiliary_index = len(graphml.auxiliary_files) - 1
            return {'FINISHED'}
        return {'CANCELLED'}

class AUXILIARY_OT_remove_file(bpy.types.Operator):
    bl_idname = "auxiliary.remove_file"
    bl_label = "Remove Auxiliary File"
    bl_description = "Remove selected auxiliary file"

    def execute(self, context):
        em_tools = context.scene.em_tools
        if em_tools.active_file_index >= 0:
            graphml = em_tools.graphml_files[em_tools.active_file_index]
            if graphml.active_auxiliary_index >= 0:
                graphml.auxiliary_files.remove(graphml.active_auxiliary_index)
                graphml.active_auxiliary_index = min(max(0, graphml.active_auxiliary_index - 1), 
                                                   len(graphml.auxiliary_files) - 1)
            return {'FINISHED'}
        return {'CANCELLED'}

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

class AUXILIARY_OT_context_menu_invoke(bpy.types.Operator):
    bl_idname = "auxiliary.context_menu"
    bl_label = "Auxiliary File Context Menu"
    
    def execute(self, context):
        bpy.ops.wm.call_menu(name="AUXILIARY_MT_context_menu")
        return {'FINISHED'}

class AUXILIARY_OT_reload_file(bpy.types.Operator):
    bl_idname = "auxiliary.reload"
    bl_label = "Reload Auxiliary File"
    bl_description = "Reload the auxiliary file data"

    file_index: bpy.props.IntProperty()

    def execute(self, context):
        em_tools = context.scene.em_tools
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        aux_file = graphml.auxiliary_files[self.file_index]

        # Qui andrà la logica di ricaricamento del file
        # che riutilizzerà gli importers esistenti
        self.report({'INFO'}, f"Reloading {aux_file.name}")
        return {'FINISHED'}

class AUXILIARY_OT_import_now(bpy.types.Operator):
    bl_idname = "auxiliary.import_now"
    bl_label = "Import Auxiliary File"
    bl_description = "Import the auxiliary file data now"

    def execute(self, context):
        em_tools = context.scene.em_tools
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        aux_file = graphml.auxiliary_files[graphml.active_auxiliary_index]

        # Qui andrà la logica di import che riutilizzerà
        # gli importers esistenti
        self.report({'INFO'}, f"Importing {aux_file.name}")
        return {'FINISHED'}



# Lista delle classi da registrare
classes = [
    AuxiliaryFileProperties,
    EMToolsProperties,
    EMToolsSettings,
    EMTOOLS_UL_files,
    EM_SetupPanel,
    EMToolsAddFile,
    EMToolsRemoveFile,
    EM_InvokePopulateLists,
    GraphMLFileItem,
    EMToolsSwitchModeOperator,
    EM_OT_import_3dgis_database,
    AUXILIARY_UL_files,
    AUXILIARY_OT_add_file,
    AUXILIARY_OT_remove_file,
    AUXILIARY_MT_context_menu,
    AUXILIARY_OT_context_menu_invoke,
    AUXILIARY_OT_reload_file,
    AUXILIARY_OT_import_now
]

def register():
    # Itera sulla lista per registrare le classi
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.em_tools = bpy.props.PointerProperty(type=EMToolsSettings)

def unregister():
    # Itera sulla lista per cancellare la registrazione delle classi
    for cls in reversed(classes):  # Usa reversed per evitare problemi di dipendenze
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.em_tools

if __name__ == "__main__":
    register()
