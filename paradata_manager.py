import bpy # type: ignore
import xml.etree.ElementTree as ET
import os
import sys
import bpy.props as prop # type: ignore
import subprocess
from bpy.props import StringProperty # type: ignore
from bpy.types import Panel, UIList # type: ignore
from .functions import *

#####################################################################
#Paradata Section

class EM_ParadataPanel:
    bl_label = "Paradata Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        # Restituisce True se mode_switch è False, quindi il pannello viene mostrato solo in modalità 3D GIS
        return em_tools.mode_switch

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.object
        row = layout.row()

        # Define variables 
        if scene.paradata_streaming_mode:
            property_list_var = "em_v_properties_list"
            property_list_index_var = "em_v_properties_list_index"
            property_list_cmd = "scene.em_v_properties_list"
            property_list_index_cmd = "scene.em_v_properties_list_index"

            combiner_list_var = "em_v_combiners_list"
            combiner_list_index_var = "em_v_combiners_list_index"
            combiner_list_cmd = "scene.em_v_combiners_list"
            combiner_list_index_cmd = "scene.em_v_combiners_list_index"

            extractor_list_var = "em_v_extractors_list"
            extractor_list_index_var = "em_v_extractors_list_index"
            extractor_list_cmd = "scene.em_v_extractors_list"
            extractor_list_index_cmd = "scene.em_v_extractors_list_index"

            source_list_var = "em_v_sources_list"
            source_list_index_var = "em_v_sources_list_index"
            source_list_cmd = "scene.em_v_sources_list"
            source_list_index_cmd = "scene.em_v_sources_list_index"

        else:
            property_list_var = "em_properties_list"
            property_list_index_var = "em_properties_list_index"
            property_list_cmd = "scene.em_properties_list"
            property_list_index_cmd = "scene.em_properties_list_index"

            combiner_list_var = "em_combiners_list"
            combiner_list_index_var = "em_combiners_list_index"
            combiner_list_cmd = "scene.em_combiners_list"
            combiner_list_index_cmd = "scene.em_combiners_list_index"

            extractor_list_var = "em_extractors_list"
            extractor_list_index_var = "em_extractors_list_index"
            extractor_list_cmd = "scene.em_extractors_list"
            extractor_list_index_cmd = "scene.em_extractors_list_index"  

            source_list_var = "em_sources_list"
            source_list_index_var = "em_sources_list_index"
            source_list_cmd = "scene.em_sources_list"
            source_list_index_cmd = "scene.em_sources_list_index"           

        ###############################################################################
        ##          Properties
        ###############################################################################

        len_property_var = "len("+property_list_cmd+")"
        
        # Sezione Proprietà
        row = layout.row()
        row.label(text="Properties: (" + str(eval(len_property_var)) + ")")
        row.prop(scene, "prop_paradata_streaming_mode", text='', icon="SHORTDISPLAY")
        row = layout.row()
        row.template_list("EM_UL_properties_managers", "", scene, property_list_var, scene, property_list_index_var, rows=2)
        
        # Mostra sempre il box, anche se non ci sono elementi
        box = layout.box()
        if eval(len_property_var) > 0 and eval(property_list_index_cmd) >= 0:
            item_property = eval(property_list_cmd)[eval(property_list_index_cmd)]
            row = box.row()
            row.prop(item_property, "name", text="", icon='FILE_TEXT')
            row = box.row()
            row.prop(item_property, "description", text="", slider=True, emboss=True, icon='TEXT')
        else:
            row = box.row()
            row.label(text="Nessuna proprietà disponibile")

        ###############################################################################
        ##          Combiners
        ###############################################################################

        len_combiner_var = "len("+combiner_list_cmd+")"
        
        # Sezione Combiners
        row = layout.row()
        row.label(text="Combiners: (" + str(eval(len_combiner_var)) + ")")
        row.prop(scene, "comb_paradata_streaming_mode", text='', icon="SHORTDISPLAY")
        row = layout.row()
        row.template_list("EM_UL_combiners_managers", "", scene, combiner_list_var, scene, combiner_list_index_var, rows=1)
        
        # Mostra sempre il box, anche se non ci sono elementi
        box = layout.box()
        if eval(len_combiner_var) > 0 and eval(combiner_list_index_cmd) >= 0:
            item_property = eval(combiner_list_cmd)[eval(combiner_list_index_cmd)]
            row = box.row()
            row.prop(item_property, "name", text="", icon='FILE_TEXT')
            row = box.row()
            row.prop(item_property, "description", text="", slider=True, emboss=True, icon='TEXT')
            row = box.row()
            row.prop(item_property, "url", text="", slider=True, emboss=True, icon='URL')
            op = row.operator("open.file", icon="EMPTY_SINGLE_ARROW", text='')
            if op:  # Check if operator is valid
                op.node_type = combiner_list_var
        else:
            row = box.row()
            row.label(text="Nessun combiner disponibile")
        
        ###############################################################################
        ##          Extractors
        ###############################################################################

        len_extractor_var = "len("+extractor_list_cmd+")"
        
        # Sezione Extractors
        row = layout.row()
        row.label(text="Extractors: (" + str(eval(len_extractor_var)) + ")")
        row.prop(scene, "extr_paradata_streaming_mode", text='', icon="SHORTDISPLAY")
        row = layout.row()
        row.template_list("EM_UL_extractors_managers", "", scene, extractor_list_var, scene, extractor_list_index_var, rows=2)
        
        # Mostra sempre il box, anche se non ci sono elementi
        box = layout.box()
        if eval(len_extractor_var) > 0 and eval(extractor_list_index_cmd) >= 0:
            item_source = eval(extractor_list_cmd)[eval(extractor_list_index_cmd)]
            row = box.row()
            row.prop(item_source, "name", text="", icon='FILE_TEXT')
            op = row.operator("listitem.toobj", icon="PASTEDOWN", text='')
            if op:  # Check if operator is valid
                op.list_type = extractor_list_var
            
            if scene.em_list_index >= 0 and len(scene.em_list) > 0 and scene.em_list[scene.em_list_index].icon == 'RESTRICT_INSTANCED_OFF':
                op = row.operator("select.fromlistitem", text='', icon="MESH_CUBE")
                if op:  # Check if operator is valid
                    op.list_type = extractor_list_var
            else:
                row.label(text="", icon='MESH_CUBE')
            
            if obj and check_if_current_obj_has_brother_inlist(obj.name, extractor_list_var):
                op = row.operator("select.listitem", text='', icon="LONGDISPLAY")
                if op:  # Check if operator is valid
                    op.list_type = extractor_list_var
            else:
                row.label(text="", icon='LONGDISPLAY')   
            
            row = box.row()
            row.prop(item_source, "description", text="", slider=True, emboss=True, icon='TEXT')
            row = box.row()
            row.prop(item_source, "url", text="", slider=True, emboss=True, icon='URL')
            op = row.operator("open.file", icon="EMPTY_SINGLE_ARROW", text='')
            if op:  # Check if operator is valid
                op.node_type = extractor_list_var
        else:
            row = box.row()
            row.label(text="Nessun estrattore disponibile")
        
        ###############################################################################
        ##          Sources
        ###############################################################################

        len_source_var = "len("+source_list_cmd+")"
        
        # Sezione Documents
        row = layout.row()
        row.label(text="Docs: (" + str(eval(len_source_var)) + ")")
        row = layout.row()
        row.template_list("EM_UL_sources_managers", "", scene, source_list_var, scene, source_list_index_var, rows=2)
        
        # Mostra sempre il box, anche se non ci sono elementi
        box = layout.box()
        if eval(len_source_var) > 0 and eval(source_list_index_cmd) >= 0:
            item_source = eval(source_list_cmd)[eval(source_list_index_cmd)]
            row = box.row()
            row.prop(item_source, "name", text="", icon='FILE_TEXT')
            
            op = row.operator("listitem.toobj", icon="PASTEDOWN", text='')
            if op:  # Check if operator is valid
                op.list_type = source_list_var
            
            if scene.em_list_index >= 0 and len(scene.em_list) > 0 and scene.em_list[scene.em_list_index].icon == 'RESTRICT_INSTANCED_OFF':
                op = row.operator("select.fromlistitem", text='', icon="MESH_CUBE")
                if op:  # Check if operator is valid
                    op.list_type = source_list_var
            else:
                row.label(text="", icon='MESH_CUBE')
            
            if obj and check_if_current_obj_has_brother_inlist(obj.name, source_list_var):
                op = row.operator("select.listitem", text='', icon="LONGDISPLAY")
                if op:  # Check if operator is valid
                    op.list_type = source_list_var
            else:
                row.label(text="", icon='LONGDISPLAY')
            
            row = box.row()
            row.prop(item_source, "description", text="", slider=True, emboss=True, icon='TEXT')
            row = box.row()
            row.prop(item_source, "url", text="", slider=True, emboss=True, icon='URL')
            op = row.operator("open.file", icon="EMPTY_SINGLE_ARROW", text='')
            if op:  # Check if operator is valid
                op.node_type = source_list_var
        else:
            row = box.row()
            row.label(text="Nessun documento disponibile")
class VIEW3D_PT_ParadataPanel(Panel, EM_ParadataPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ParadataPanel"
    bl_context = "objectmode"

class EM_UL_sources_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.22, align = True)
        layout.label(text = item.name, icon = item.icon)
        layout.label(text = item.description, icon=item.icon_url)

class EM_UL_properties_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.4, align = True)
        layout.label(text = item.name)
        layout.label(text = item.description)

class EM_UL_combiners_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.25, align = True)
        layout.label(text = item.name)
        layout.label(text = item.description)

class EM_UL_extractors_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.25, align = True)
        layout.label(text = item.name, icon = item.icon)
        layout.label(text = item.description, icon=item.icon_url)

# Paradata section 
#####################################################################


#### da qui si definiscono le funzioni e gli operatori

class EM_files_opener(bpy.types.Operator):
    """If the button is grey, set the path to a DosCo folder in the EM setup panel above"""
    bl_idname = "open.file"
    bl_label = "Open a file using external software or a url using the default system browser"
    bl_options = {"REGISTER", "UNDO"}

    node_type: StringProperty() # type: ignore

    #@classmethod
    #def poll(cls, context):
        # The button works if DosCo and the url field are valorised
    #    return context.scene.EMDosCo_dir 

    def execute(self, context):
        scene = context.scene        
        file_res_path = eval("scene."+self.node_type+"[scene."+self.node_type+"_index].url")
        if is_valid_url(file_res_path): # nel caso nel nodo fonte ci sia una risorsa online
            print(file_res_path)
            bpy.ops.wm.url_open(url=file_res_path)

        else: # nel caso nel nodo fonte ci sia una risorsa locale
            basedir = bpy.path.abspath(scene.EMDosCo_dir)
            path_to_file = os.path.join(basedir, file_res_path)
            if os.path.exists(path_to_file):
                try:
                    if os.name == 'nt':  # Windows
                        os.startfile(path_to_file)
                    elif os.name == 'posix':  # macOS, Linux
                        opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
                        subprocess.run([opener, path_to_file])
                except Exception as e:
                    print("Error when opening the file:", e)
                    self.report({'WARNING'}, "Cannot open file: " + str(e))
                    return {'CANCELLED'}
            
        return {'FINISHED'}

class EM_OT_update_paradata_lists(bpy.types.Operator):
    bl_idname = "em.update_paradata_lists"
    bl_label = "Update Paradata Lists"
    bl_description = "Update all paradata lists based on streaming settings"
    
    def execute(self, context):
        scene = context.scene
        em_tools = context.scene.em_tools
        
        # Pulizia preventiva di tutte le liste
        scene.em_v_properties_list.clear()
        scene.em_v_combiners_list.clear()
        scene.em_v_extractors_list.clear()
        scene.em_v_sources_list.clear()
        
        try:
            # Verifica se c'è un file GraphML attivo
            if em_tools.active_file_index < 0 or not em_tools.graphml_files:
                print("Nessun file GraphML attivo, le liste rimarranno vuote")
                return {'FINISHED'}  # Non è un errore, semplicemente non facciamo nulla
            
            graphml = em_tools.graphml_files[em_tools.active_file_index]
            
            # Importa get_graph e debug_graph_structure
            from .s3Dgraphy import get_graph
            from .s3Dgraphy.utils import debug_graph_structure
            
            graph = get_graph(graphml.name)
            
            if not graph:
                print(f"Il grafo {graphml.name} non è stato trovato o è vuoto")
                return {'FINISHED'}  # Non è un errore, le liste rimarranno vuote
                
            # Debug della struttura del grafo
            debug_graph_structure(graph)
            
            # Determina il nodo di partenza (stratigrafico selezionato o tutti)
            strat_node_id = None
            if scene.paradata_streaming_mode and scene.em_list_index >= 0 and len(scene.em_list) > 0:
                strat_node_id = scene.em_list[scene.em_list_index].id_node
                # Debug delle relazioni del nodo selezionato
                debug_graph_structure(graph, strat_node_id)
            
            # Aggiorna la lista delle proprietà
            self.update_property_list(scene, graph, strat_node_id)
            
            # Se c'è una proprietà selezionata, aggiorna le liste dei combiner/extractor
            if scene.em_v_properties_list_index >= 0 and len(scene.em_v_properties_list) > 0:
                prop_node_id = scene.em_v_properties_list[scene.em_v_properties_list_index].id_node
                self.update_combiner_list(scene, graph, prop_node_id)
                self.update_extractor_list(scene, graph, prop_node_id)
                
                # Se c'è un extractor selezionato, aggiorna la lista dei documenti
                if scene.em_v_extractors_list_index >= 0 and len(scene.em_v_extractors_list) > 0:
                    ext_node_id = scene.em_v_extractors_list[scene.em_v_extractors_list_index].id_node
                    self.update_document_list(scene, graph, ext_node_id)
            
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error updating paradata lists: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

    def update_property_list(self, scene, graph, strat_node_id=None):
        """Aggiorna la lista delle proprietà"""
        scene.em_v_properties_list.clear()
        
        if strat_node_id:
            # Se c'è un nodo stratigrafico selezionato, filtra le proprietà
            prop_nodes = graph.get_property_nodes_for_node(strat_node_id)
            print(f"Trovate {len(prop_nodes)} proprietà per il nodo {strat_node_id}")
        else:
            # Altrimenti prendi tutte le proprietà
            prop_nodes = [node for node in graph.nodes if node.node_type == "property"]
            print(f"Trovate {len(prop_nodes)} proprietà totali")
        
        for prop_node in prop_nodes:
            item = scene.em_v_properties_list.add()
            item.name = prop_node.name
            item.description = prop_node.description if hasattr(prop_node, 'description') else ""
            item.url = prop_node.value if hasattr(prop_node, 'value') else ""
            item.icon = check_objs_in_scene_and_provide_icon_for_list_element(prop_node.name)
            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = prop_node.node_id

    def update_combiner_list(self, scene, graph, prop_node_id):
        """Aggiorna la lista dei combiner basata sulla proprietà selezionata"""
        scene.em_v_combiners_list.clear()
        
        if not scene.prop_paradata_streaming_mode:
            combiners = [node for node in graph.nodes if node.node_type == "combiner"]
        else:
            combiners = graph.get_combiner_nodes_for_property(prop_node_id)
        
        print(f"Trovati {len(combiners)} combiner per la proprietà {prop_node_id}")
        
        for combiner in combiners:
            item = scene.em_v_combiners_list.add()
            item.name = combiner.name
            item.description = combiner.description if hasattr(combiner, 'description') else ""
            item.url = combiner.url if hasattr(combiner, 'url') else ""
            item.icon = check_objs_in_scene_and_provide_icon_for_list_element(combiner.name)
            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = combiner.node_id

    def update_extractor_list(self, scene, graph, node_id):
        """Aggiorna la lista degli estrattori basata sul nodo selezionato"""
        scene.em_v_extractors_list.clear()
        
        extractors = []
        
        if scene.prop_paradata_streaming_mode:
            # Se è attivo lo streaming, usa il nodo_id passato (proprietà)
            property_extractors = graph.get_extractor_nodes_for_node(node_id)
            extractors.extend(property_extractors)
            print(f"Estrattori dalla proprietà: {len(property_extractors)}")
            
            # Se c'è un combiner selezionato, aggiungi anche i suoi estrattori
            if scene.comb_paradata_streaming_mode and scene.em_v_combiners_list_index >= 0 and len(scene.em_v_combiners_list) > 0:
                comb_node_id = scene.em_v_combiners_list[scene.em_v_combiners_list_index].id_node
                combiner_extractors = graph.get_extractor_nodes_for_node(comb_node_id)
                extractors.extend(combiner_extractors)
                print(f"Estrattori dal combiner: {len(combiner_extractors)}")
        else:
            # Altrimenti prendi tutti gli estrattori
            extractors = [node for node in graph.nodes if node.node_type == "extractor"]
            print(f"Tutti gli estrattori: {len(extractors)}")
        
        # Rimuovi duplicati
        seen = set()
        unique_extractors = [x for x in extractors if not (x.node_id in seen or seen.add(x.node_id))]
        print(f"Estrattori unici: {len(unique_extractors)}")
        
        # Popola la lista
        for extractor in unique_extractors:
            item = scene.em_v_extractors_list.add()
            item.name = extractor.name
            item.description = extractor.description if hasattr(extractor, 'description') else ""
            item.url = extractor.source if hasattr(extractor, 'source') else ""
            item.icon = check_objs_in_scene_and_provide_icon_for_list_element(extractor.name)
            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = extractor.node_id

    def update_document_list(self, scene, graph, extractor_id):
        """Aggiorna la lista dei documenti basata sull'estrattore selezionato"""
        scene.em_v_sources_list.clear()
        
        if scene.extr_paradata_streaming_mode:
            # Se è attivo lo streaming, filtra i documenti per l'estrattore
            documents = graph.get_document_nodes_for_extractor(extractor_id)
            print(f"Trovati {len(documents)} documenti per l'estrattore {extractor_id}")
        else:
            # Altrimenti prendi tutti i documenti
            documents = [node for node in graph.nodes if node.node_type == "document"]
            print(f"Trovati {len(documents)} documenti totali")
        
        for doc in documents:
            item = scene.em_v_sources_list.add()
            item.name = doc.name
            item.description = doc.description if hasattr(doc, 'description') else ""
            item.url = doc.url if hasattr(doc, 'url') else ""
            item.icon = check_objs_in_scene_and_provide_icon_for_list_element(doc.name)
            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = doc.node_id

classes = [
    VIEW3D_PT_ParadataPanel,
    EM_UL_properties_managers,
    EM_UL_sources_managers,
    EM_UL_extractors_managers,
    EM_UL_combiners_managers,
    EM_OT_update_paradata_lists
    ]

# Registration
def register():

    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
        
    for cls in classes:
        bpy.utils.unregister_class(cls)



