import xml.etree.ElementTree as ET
import bpy
import os
import re
import json
import shutil
import bpy.props as prop
from bpy.props import (BoolProperty,
                       FloatProperty,
                       StringProperty,
                       EnumProperty,
                       CollectionProperty,
                       IntProperty
                       )

from urllib.parse import urlparse

from .s3Dgraphy.utils.utils import get_material_color
from .s3Dgraphy.nodes.link_node import LinkNode
from .s3Dgraphy import load_graph_from_file, get_graph

import platform
from pathlib import Path

def convert_material_to_principled(material):
    """
    Convert a material using old shaders (like Diffuse BSDF) to use Principled BSDF
    Preserves texture connections from the original shader
    Returns True if conversion was needed, False otherwise
    """
    if not material or not material.use_nodes:
        return False
        
    # Check if already using Principled BSDF connected to output
    output_node = None
    principled_node = None
    
    for node in material.node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL':
            output_node = node
        elif node.type == 'BSDF_PRINCIPLED':
            principled_node = node
            
    # If we already have a properly connected Principled BSDF, no need to convert
    if output_node and principled_node:
        for link in material.node_tree.links:
            if link.from_node == principled_node and link.to_node == output_node:
                return False
    
    # Store the original texture nodes
    texture_nodes = []
    for node in material.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            texture_nodes.append({
                'node': node,
                'image': node.image,
                'location': node.location.copy()
            })
    
    # Find the output node
    if not output_node:
        for node in material.node_tree.nodes:
            if node.type == 'OUTPUT_MATERIAL':
                output_node = node
                output_location = node.location.copy()
                break
    else:
        output_location = output_node.location.copy()
    
    # If still no output node, we'll need to create one
    if not output_node:
        output_location = (300, 0)
    
    # Clear all nodes - we'll rebuild from scratch
    material.node_tree.nodes.clear()
    
    # Create the output node
    output_node = material.node_tree.nodes.new('ShaderNodeOutputMaterial')
    output_node.location = output_location
    
    # Create the Principled BSDF node
    principled = material.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    principled.location = (output_location[0] - 300, output_location[1])
    
    # Connect Principled to Output
    material.node_tree.links.new(principled.outputs['BSDF'], output_node.inputs['Surface'])
    
    # Recreate and reconnect texture nodes
    for tex_info in texture_nodes:
        tex_node = material.node_tree.nodes.new('ShaderNodeTexImage')
        tex_node.location = tex_info['location']
        tex_node.image = tex_info['image']
        
        # Connect to Base Color by default
        material.node_tree.links.new(tex_node.outputs['Color'], principled.inputs['Base Color'])
        print(f"Connected texture {tex_info['image'].name} to Base Color of Principled BSDF")
    
    return True

def normalize_path(path):
    """
    Normalizza un percorso per renderlo compatibile con il sistema operativo corrente.
    Gestisce correttamente i percorsi relativi espandendoli.
    
    Args:
        path (str): Percorso da normalizzare
        
    Returns:
        str: Percorso normalizzato assoluto
    """
    if not path:
        return ""
    
    # Prima espandi il percorso relativo a un percorso assoluto usando bpy.path.abspath
    abs_path = bpy.path.abspath(path)
    
    # Poi converti in oggetto Path per normalizzare i separatori di percorso
    path_obj = Path(abs_path)
    
    return str(path_obj)

def create_directory(path):
    """
    Crea una directory se non esiste.
    
    Args:
        path (str): Percorso della directory da creare
        
    Returns:
        str: Percorso normalizzato della directory creata
        
    Raises:
        OSError: Se non è possibile creare la directory
    """
    if not path:
        raise ValueError("Path cannot be empty")
        
    # Normalizza il percorso
    norm_path = normalize_path(path)
    
    # Crea la directory se non esiste
    os.makedirs(norm_path, exist_ok=True)
    
    return norm_path

def check_export_path(context, show_message=True):
    """
    Verifica che il percorso di export sia valido e accessibile.
    
    Args:
        context (bpy.context): Contesto Blender
        show_message (bool): Se True, mostra un messaggio di errore
        
    Returns:
        bool: True se il percorso è valido, False altrimenti
    """
    scene = context.scene
    
    # Verifica se esiste un percorso di export
    if not scene.heriverse_export_path:
        if show_message:
            show_popup_message(
                context,
                "Export path not specified",
                "Please set an export path in the Heriverse Export panel",
                'ERROR'
            )
        return False
    
    # Normalizza e verifica il percorso
    try:
        export_path = normalize_path(scene.heriverse_export_path)
        
        # Verifica se la directory esiste o può essere creata
        if not os.path.exists(export_path):
            try:
                os.makedirs(export_path, exist_ok=True)
            except Exception as e:
                if show_message:
                    show_popup_message(
                        context,
                        "Export directory error",
                        f"Cannot create export directory: {str(e)}",
                        'ERROR'
                    )
                return False
        
        # Verifica se abbiamo permessi di scrittura
        if not os.access(export_path, os.W_OK):
            if show_message:
                show_popup_message(
                    context,
                    "Permission error",
                    f"Cannot write to export directory: {export_path}",
                    'ERROR'
                )
            return False
            
        return True
        
    except Exception as e:
        if show_message:
            show_popup_message(
                context,
                "Path error",
                f"Invalid export path: {str(e)}",
                'ERROR'
            )
        return False

def check_graph_loaded(context, show_message=True):
    """
    Verifica che almeno un grafo sia caricato.
    
    Args:
        context (bpy.context): Contesto Blender
        show_message (bool): Se True, mostra un messaggio di errore
        
    Returns:
        bool: True se almeno un grafo è caricato, False altrimenti
    """
    from .s3Dgraphy import get_all_graph_ids
    
    graph_ids = get_all_graph_ids()
    
    if not graph_ids:
        if show_message:
            show_popup_message(
                context,
                "No graph loaded",
                "Please load a GraphML file first in the EM Setup panel",
                'ERROR'
            )
        return False
    
    return True

def check_active_graph(context, show_message=True):
    """
    Verifica che ci sia un grafo attivo.
    
    Args:
        context (bpy.context): Contesto Blender
        show_message (bool): Se True, mostra un messaggio di errore
        
    Returns:
        tuple: (bool, graph) dove bool indica se c'è un grafo attivo,
               e graph è l'oggetto grafo o None
    """
    from .s3Dgraphy import get_graph
    
    em_tools = context.scene.em_tools
    
    # Verifica se c'è un file GraphML attivo
    if em_tools.active_file_index < 0 or em_tools.active_file_index >= len(em_tools.graphml_files):
        if show_message:
            show_popup_message(
                context,
                "No active GraphML file",
                "Please select a GraphML file in the EM Setup panel",
                'ERROR'
            )
        return False, None
    
    # Prova a ottenere il grafo attivo
    graphml = em_tools.graphml_files[em_tools.active_file_index]
    graph = get_graph(graphml.name)
    
    if not graph:
        if show_message:
            show_popup_message(
                context,
                "Graph not loaded",
                f"Graph '{graphml.name}' is not properly loaded. Try reloading it.",
                'ERROR'
            )
        return False, None
    
    return True, graph

def show_popup_message(context, title, message, icon='INFO'):
    """
    Mostra un messaggio popup all'utente.
    
    Args:
        context (bpy.context): Contesto Blender
        title (str): Titolo del popup
        message (str): Messaggio da mostrare
        icon (str): Icona da mostrare (INFO, ERROR, WARNING, etc.)
    """
    def draw(self, context):
        lines = message.split('\n')
        for line in lines:
            self.layout.label(text=line)
    
    context.window_manager.popup_menu(draw, title=title, icon=icon)


##################

def is_graph_available(context):
    """
    Check if a valid graph is available in the current context.
    
    Args:
        context: Blender context
        
    Returns:
        tuple: (bool, graph) where bool indicates if a graph is available,
               and graph is the actual graph object or None
    """
    if not hasattr(context.scene, 'em_tools'):
        return False, None
        
    em_tools = context.scene.em_tools
    
    # Check if graphml_files collection exists and has items
    if not hasattr(em_tools, 'graphml_files') or len(em_tools.graphml_files) == 0:
        return False, None
        
    # Check if active_file_index is valid
    if em_tools.active_file_index < 0 or em_tools.active_file_index >= len(em_tools.graphml_files):
        return False, None
        
    try:
        # Get the active graphml file
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        
        # Try to get the actual graph
        from .s3Dgraphy import get_graph
        graph = get_graph(graphml.name)
        
        return bool(graph), graph
    except Exception as e:
        print(f"Error accessing graph: {str(e)}")
        return False, None


def is_valid_url(url_string):
    parsed_url = urlparse(url_string)
    return bool(parsed_url.scheme) or bool(parsed_url.netloc)

def menu_func(self, context):
    self.layout.separator()

def is_reconstruction_us(node):
    is_rec = False
    if node.shape in ["parallelogram", "ellipse", "hexagon", "octagon"]:
        is_rec = True

    return is_rec

### #### #### #### #### #### #### #### ####
##### functions to switch menus in UI  ####
### #### #### #### #### #### #### #### ####

def sync_Switch_em(self, context):
    scene = context.scene
    em_settings = scene.em_settings
    if scene.em_settings.em_proxy_sync is True:
        scene.em_settings.em_proxy_sync2 = False
        scene.em_settings.em_proxy_sync2_zoom = False
    return

def sync_update_epoch_soloing(self, context):
    scene = context.scene
    soling = False
    for epoch in scene.epoch_list:
        if epoch.epoch_soloing is True:
            soloing_epoch = epoch
            soloing = True
    if soloing is True:
        for epoch in scene.epoch_list:
            if epoch is not soloing_epoch:
                pass
    return

def sync_Switch_proxy(self, context):
    scene = context.scene
    em_settings = scene.em_settings
    if scene.em_settings.em_proxy_sync2 is True:
        scene.em_settings.em_proxy_sync = False
    return

## #### #### #### #### #### #### #### #### #### #### ####
##### Functions to check properties of scene objects ####
## #### #### #### #### #### #### #### #### #### #### ####

def check_if_current_obj_has_brother_inlist(obj_name, list_type):
    scene = bpy.context.scene
    list_cmd = ("scene."+ list_type)
    for element_list in eval(list_cmd):
        if element_list.name == obj_name:
            is_brother = True
            return is_brother
    is_brother = False
    return is_brother

def select_3D_obj(name):
    #scene = bpy.context.scene
    bpy.ops.object.select_all(action="DESELECT")
    object_to_select = bpy.data.objects[name]
    object_to_select.select_set(True)
    bpy.context.view_layer.objects.active = object_to_select

def select_list_element_from_obj_proxy(obj, list_type):
    scene = bpy.context.scene
    index_list = 0
    list_cmd = ("scene."+ list_type)
    list_index_cmd = ("scene."+ list_type+"_index = index_list")
    for i in eval(list_cmd):
        if obj.name == i.name:
            exec(list_index_cmd)
            pass
        index_list += 1

## diverrà deprecata !
def add_sceneobj_to_epochs():
    scene = bpy.context.scene
    #deselect all objects
    selection_names = bpy.context.selected_objects
    bpy.ops.object.select_all(action='DESELECT')
    #looking through all objects
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            for USS in scene.em_list:
                if obj.name == USS.name:
                    #print("ho trovato un oggetto in scena chiamato "+ str(obj.name)+ " ed un nodo US chiamato: " + str(USS.name))
                    idx = 0
                    for i in scene.epoch_list:
                        if i.name == USS.epoch:
                            #print("found "+str(USS.epoch)+ " corrispondende all'indice"+str(idx))
                            obj.select_set(True)
                            bpy.ops.epoch_manager.add_to_group(group_em_idx=idx)
                            obj.select_set(False)
                        idx +=1
                                                
### #### #### #### #### #### #### #### #### #### ####
#### Functions to extract data from GraphML file ####
### #### #### #### #### #### #### #### #### #### ####

def EM_list_clear(context, list_type):
    scene = bpy.context.scene
    list_cmd1 = "scene."+list_type+".update()"
    list_cmd2 = "len(scene."+list_type+")"
    list_cmd3 = "scene."+list_type+".remove(0)"
    eval(list_cmd1)
    list_lenght = eval(list_cmd2)
    for x in range(list_lenght):
        eval(list_cmd3)
    return

def stream_properties(self, context):
    """
    Funzione chiamata quando l'utente cambia elemento nella lista properties.
    Aggiorna le liste di combiner ed extractor filtrandole per la proprietà selezionata.
    """
    bpy.ops.em.update_paradata_lists()
    return

def stream_combiners(self, context):
    """
    Funzione chiamata quando l'utente cambia elemento nella lista combiners.
    Aggiorna la lista degli extractors filtrandoli per il combiner selezionato.
    """
    bpy.ops.em.update_paradata_lists()
    return

def stream_extractors(self, context):
    """
    Funzione chiamata quando l'utente cambia elemento nella lista extractors.
    Aggiorna la lista dei documenti filtrandoli per l'extractor selezionato.
    """
    bpy.ops.em.update_paradata_lists()
    return

def create_derived_lists(node):
    context = bpy.context
    scene = context.scene
    prop_index = 0
    EM_list_clear(context, "em_v_properties_list")

    is_property = False
    
    # Debug info
    print(f"\nRicerca proprietà per il nodo {node.name} (ID: {node.id_node})")

    # Recuperiamo il grafo corrente
    from .functions import is_graph_available as check_graph
    graph_exists, graph = check_graph(context)
    
    if not graph_exists:
        print("Errore: Grafo non disponibile")
        return
    
    # Utilizziamo direttamente il grafo per trovare le relazioni has_property
    property_nodes = []
    
    # Cerchiamo tutti gli archi che partono dal nodo corrente
    for edge in graph.edges:
        if edge.edge_source == node.id_node:
            edge_type = edge.edge_type
            target_node = graph.find_node_by_id(edge.edge_target)
            
            # Verifica se l'arco è di tipo has_property o has_data_provenance e il target è una proprietà
            if target_node and hasattr(target_node, 'node_type') and target_node.node_type == 'property':
                if edge_type in ['has_property', 'has_data_provenance']:
                    print(f"Trovata proprietà: {target_node.name} (ID: {target_node.node_id}) via {edge_type}")
                    property_nodes.append(target_node)
                    is_property = True
    
    # Aggiorniamo la lista delle proprietà
    if property_nodes:
        for i, prop_node in enumerate(property_nodes):
            scene.em_v_properties_list.add()
            property_item = scene.em_v_properties_list[i]
            property_item.name = prop_node.name
            property_item.description = prop_node.description
            property_item.url = prop_node.value if hasattr(prop_node, 'value') else ""
            property_item.id_node = prop_node.node_id
            prop_index += 1

    print(f"Trovate {prop_index} proprietà per il nodo {node.id_node}")

    if is_property:
        if scene.prop_paradata_streaming_mode:
            selected_property_node = scene.em_v_properties_list[scene.em_v_properties_list_index]
            is_combiner = create_derived_combiners_list(selected_property_node)
            if not is_combiner:
                create_derived_extractors_list(selected_property_node)
        else:
            for v_list_property in scene.em_v_properties_list:
                is_combiner = create_derived_combiners_list(v_list_property)
                if not is_combiner:
                    create_derived_extractors_list(v_list_property)                

    else:
        EM_list_clear(context, "em_v_extractors_list")
        EM_list_clear(context, "em_v_sources_list")
        EM_list_clear(context, "em_v_combiners_list")

    return

def create_derived_combiners_list(passed_property_item):
    context = bpy.context
    scene = context.scene
    comb_index = 0
    is_combiner = False
    EM_list_clear(context, "em_v_combiners_list")

    print(f"La proprietà: {passed_property_item.name} ha id_nodo: {passed_property_item.id_node}")
    
    # Recuperiamo il grafo corrente
    from .functions import is_graph_available as check_graph
    graph_exists, graph = check_graph(context)
    
    if not graph_exists:
        print("Errore: Grafo non disponibile")
        return False
    
    # Cerchiamo combinatori collegati alla proprietà
    combiner_nodes = []
    
    for edge in graph.edges:
        if edge.edge_source == passed_property_item.id_node:
            target_node = graph.find_node_by_id(edge.edge_target)
            if target_node and hasattr(target_node, 'node_type') and target_node.node_type == 'combiner':
                print(f"Trovato combinatore: {target_node.name} (ID: {target_node.node_id})")
                combiner_nodes.append(target_node)
                is_combiner = True
    
    # Aggiorniamo la lista dei combinatori
    if combiner_nodes:
        for i, comb_node in enumerate(combiner_nodes):
            scene.em_v_combiners_list.add()
            combiner_item = scene.em_v_combiners_list[i]
            combiner_item.name = comb_node.name
            combiner_item.description = comb_node.description
            combiner_item.url = comb_node.sources[0] if hasattr(comb_node, 'sources') and comb_node.sources else ""
            combiner_item.id_node = comb_node.node_id
            combiner_item.icon_url = "CHECKBOX_HLT" if combiner_item.url else "CHECKBOX_DEHLT"
            comb_index += 1

    if is_combiner:
        if scene.comb_paradata_streaming_mode:
            selected_combiner_node = scene.em_v_combiners_list[scene.em_v_combiners_list_index]
            create_derived_sources_list(selected_combiner_node)
        else:
            for v_list_combiner in scene.em_v_combiners_list:
                create_derived_sources_list(v_list_combiner)
    else:
        EM_list_clear(context, "em_v_sources_list")
        EM_list_clear(context, "em_v_extractors_list")

    return is_combiner

def create_derived_extractors_list(passed_property_item):
    context = bpy.context
    scene = context.scene
    extr_index = 0
    is_extractor = False
    EM_list_clear(context, "em_v_extractors_list")

    print(f"La proprietà: {passed_property_item.name} ha id_nodo: {passed_property_item.id_node}")
    
    # Recuperiamo il grafo corrente
    from .functions import is_graph_available as check_graph
    graph_exists, graph = check_graph(context)
    
    if not graph_exists:
        print("Errore: Grafo non disponibile")
        return False
    
    # Cerchiamo estrattori collegati alla proprietà
    extractor_nodes = []
    
    for edge in graph.edges:
        if edge.edge_source == passed_property_item.id_node:
            target_node = graph.find_node_by_id(edge.edge_target)
            if target_node and hasattr(target_node, 'node_type') and target_node.node_type == 'extractor':
                print(f"Trovato estrattore: {target_node.name} (ID: {target_node.node_id})")
                extractor_nodes.append(target_node)
                is_extractor = True

    # Aggiorniamo la lista degli estrattori
    if extractor_nodes:
        for i, extr_node in enumerate(extractor_nodes):
            scene.em_v_extractors_list.add()
            extractor_item = scene.em_v_extractors_list[i]
            extractor_item.name = extr_node.name
            extractor_item.description = extr_node.description
            extractor_item.url = extr_node.source if hasattr(extr_node, 'source') else ""
            extractor_item.id_node = extr_node.node_id
            extractor_item.icon_url = "CHECKBOX_HLT" if extractor_item.url else "CHECKBOX_DEHLT"
            extr_index += 1

    if is_extractor:
        if scene.extr_paradata_streaming_mode:
            selected_extractor_node = scene.em_v_extractors_list[scene.em_v_extractors_list_index]
            create_derived_sources_list(selected_extractor_node)
        else:
            for v_list_extractor in scene.em_v_extractors_list:
                create_derived_sources_list(v_list_extractor)
    else:
        EM_list_clear(context, "em_v_sources_list")

    return is_extractor

def create_derived_sources_list(passed_extractor_item):
    context = bpy.context
    scene = context.scene
    sour_index = 0
    EM_list_clear(context, "em_v_sources_list")
    
    print(f"passed_extractor_item: {passed_extractor_item.name} con id: {passed_extractor_item.id_node}")
    
    # Recuperiamo il grafo corrente
    from .functions import is_graph_available as check_graph
    graph_exists, graph = check_graph(context)
    
    if not graph_exists:
        print("Errore: Grafo non disponibile")
        return
    
    # Cerchiamo fonti collegate all'estrattore
    source_nodes = []
    
    for edge in graph.edges:
        if edge.edge_source == passed_extractor_item.id_node:
            target_node = graph.find_node_by_id(edge.edge_target)
            if target_node and hasattr(target_node, 'node_type') and target_node.node_type == 'document':
                print(f"Trovata fonte: {target_node.name} (ID: {target_node.node_id})")
                source_nodes.append(target_node)

    # Aggiorniamo la lista delle fonti
    if source_nodes:
        for i, src_node in enumerate(source_nodes):
            scene.em_v_sources_list.add()
            source_item = scene.em_v_sources_list[i]
            source_item.name = src_node.name
            source_item.description = src_node.description
            source_item.url = src_node.url if hasattr(src_node, 'url') else ""
            source_item.id_node = src_node.node_id
            source_item.icon_url = "CHECKBOX_HLT" if source_item.url else "CHECKBOX_DEHLT"
            sour_index += 1

    print(f"sources: {sour_index}")

def switch_paradata_lists(self, context):
    """
    Funzione chiamata quando l'utente cambia elemento nella lista US/USV.
    Aggiorna tutte le liste di paradata in base all'elemento selezionato.
    """
    scene = context.scene
    
    # Verifica se c'è un grafo attivo prima di chiamare l'operatore
    if scene.paradata_streaming_mode:
        # Controlla se c'è un file GraphML attivo
        em_tools = scene.em_tools
        if em_tools.active_file_index >= 0 and len(em_tools.graphml_files) > 0:
            try:
                # Verifica se il grafo esiste
                from .s3Dgraphy import get_graph
                graphml = em_tools.graphml_files[em_tools.active_file_index]
                graph = get_graph(graphml.name)
                
                if graph:
                    # Il grafo esiste, aggiorna le liste
                    bpy.ops.em.update_paradata_lists()
                else:
                    print(f"Grafo '{graphml.name}' non trovato, impossibile aggiornare le liste")
            except Exception as e:
                print(f"Errore durante la verifica del grafo: {str(e)}")
        else:
            print("Nessun file GraphML attivo, impossibile aggiornare le liste")
    
    # Il resto del codice...
    return

## #### #### #### #### #### #### #### #### #### #### #### ####
#### Check the presence-absence of US against the GraphML ####
## #### #### #### #### #### #### #### #### #### #### #### ####

def check_objs_in_scene_and_provide_icon_for_list_element(list_element_name):
    data = bpy.data
    icon_check = 'RESTRICT_INSTANCED_ON'
    for ob in data.objects:
        if ob.name == list_element_name:
            icon_check = 'RESTRICT_INSTANCED_OFF'
    return icon_check

def update_icons(context,list_type):
    scene = context.scene
    list_path = "scene."+list_type
    for element in eval(list_path):
        element.icon = check_objs_in_scene_and_provide_icon_for_list_element(element.name)
    return

## #### #### #### #### #### #### #### ####                       
 #### General functions for materials ####
## #### #### #### #### #### #### #### ####

def update_display_mode(self, context):
    if bpy.context.scene.proxy_display_mode == "EM":
        bpy.ops.emset.emmaterial()
    if bpy.context.scene.proxy_display_mode == "Periods":
        bpy.ops.emset.epochmaterial()

    
def check_material_presence(matname):
    mat_presence = False
    for mat in bpy.data.materials:
        if mat.name == matname:
            mat_presence = True
            return mat_presence
    return mat_presence

#  #### #### #### #### #### #### ####
#### Functions materials for EM  ####
#  #### #### #### #### #### #### ####


from .s3Dgraphy.utils.utils import get_material_color

def consolidate_EM_material_presence(overwrite_mats):
    EM_mat_list = ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD']
    for EM_mat_name in EM_mat_list:
        if not check_material_presence(EM_mat_name):
            EM_mat = bpy.data.materials.new(name=EM_mat_name)
            overwrite_mats = True
        if overwrite_mats == True:
            scene = bpy.context.scene
            color_values = get_material_color(EM_mat_name)
            if color_values is not None:
                R, G, B, A = color_values
                em_setup_mat_cycles(EM_mat_name, R, G, B, A)

def em_setup_mat_cycles(matname, R, G, B, A=1.0):
    scene = bpy.context.scene
    mat = bpy.data.materials[matname]
    mat.diffuse_color[0] = R
    mat.diffuse_color[1] = G
    mat.diffuse_color[2] = B 
    mat.diffuse_color[3] = A
    mat.show_transparent_back = False
    mat.use_backface_culling = False
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    mat.blend_method = scene.proxy_blend_mode
    links = mat.node_tree.links
    nodes = mat.node_tree.nodes
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (0, 0)
    mainNode = nodes.new('ShaderNodeBsdfPrincipled')
    mainNode.inputs['Base Color'].default_value = (R, G, B, A)
    mainNode.location = (-800, 50)
    mainNode.name = "diffuse"
    mainNode.inputs['Alpha'].default_value = scene.proxy_display_alpha
    links.new(mainNode.outputs[0], output.inputs[0])


def set_materials_using_EM_list(context):
    em_list_lenght = len(context.scene.em_list)
    counter = 0
    while counter < em_list_lenght:
        current_ob_em_list = context.scene.em_list[counter]
        overwrite_mats = True
        consolidate_EM_material_presence(overwrite_mats)
        if current_ob_em_list.icon == 'RESTRICT_INSTANCED_OFF':
            current_ob_scene = context.scene.objects[current_ob_em_list.name]
            ob_material_name = 'US'  # Default
            
            # Check the node_type first (most reliable method)
            if hasattr(current_ob_em_list, 'node_type') and current_ob_em_list.node_type:
                if current_ob_em_list.node_type in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD']:
                    ob_material_name = current_ob_em_list.node_type
            else:
                # Fallback to shape + border style
                if current_ob_em_list.shape == 'rectangle':
                    ob_material_name = 'US'
                elif current_ob_em_list.shape == 'ellipse_white':
                    ob_material_name = 'US'
                elif current_ob_em_list.shape == 'ellipse':
                    ob_material_name = 'USVn'
                elif current_ob_em_list.shape == 'parallelogram':
                    ob_material_name = 'USVs'
                elif current_ob_em_list.shape == 'hexagon':
                    ob_material_name = 'USVn'
                elif current_ob_em_list.shape == 'octagon':
                    # Check border style for octagon shapes
                    if current_ob_em_list.border_style == '#D8BD30':
                        ob_material_name = 'SF'
                    elif current_ob_em_list.border_style == '#B19F61':
                        ob_material_name = 'VSF'
                    else:
                        # Default for octagon without recognized border
                        ob_material_name = 'VSF'
                elif current_ob_em_list.shape == 'roundrectangle':
                    ob_material_name = 'USD'
                
            mat = bpy.data.materials[ob_material_name]
            current_ob_scene.data.materials.clear()
            current_ob_scene.data.materials.append(mat)
        counter += 1

def proxy_shader_mode_function(self, context):
    scene = context.scene
    if scene.proxy_shader_mode is True:
        scene.proxy_blend_mode = "ADD"
    else:
        scene.proxy_blend_mode = "BLEND"
    update_display_mode(self, context)

def hex_to_rgb(value):
    gamma = 2.2
    value = value.lstrip('#')
    lv = len(value)
    fin = list(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))
    r = pow(fin[0] / 255, gamma)
    g = pow(fin[1] / 255, gamma)
    b = pow(fin[2] / 255, gamma)
    fin.clear()
    fin.append(r)
    fin.append(g)
    fin.append(b)
    #fin.append(1.0)
    return tuple(fin)

# #### #### #### #### #### ####
#### materials for epochs  ####
# #### #### #### #### #### ####

def consolidate_epoch_material_presence(matname):
    if not check_material_presence(matname):
        epoch_mat = bpy.data.materials.new(name=matname)
    else:
        epoch_mat = bpy.data.materials[matname]
    return epoch_mat

def set_materials_using_epoch_list(context):
    scene = context.scene 
    mat_prefix = "ep_"
    for epoch in scene.epoch_list:
        matname = mat_prefix + epoch.name
        mat = consolidate_epoch_material_presence(matname)
        R = epoch.epoch_RGB_color[0]
        G = epoch.epoch_RGB_color[1]
        B = epoch.epoch_RGB_color[2]
        em_setup_mat_cycles(matname,R,G,B)
        for em_element in scene.em_list:
            if em_element.icon == "RESTRICT_INSTANCED_OFF":
                if em_element.epoch == epoch.name:
                    #print(em_element.name + " element is in epoch "+epoch.name)
                    obj = bpy.data.objects[em_element.name]
                    obj.data.materials.clear()
                    obj.data.materials.append(mat)


class OBJECT_OT_CenterMass(bpy.types.Operator):
    bl_idname = "center.mass"
    bl_label = "Center Mass"
    bl_options = {"REGISTER", "UNDO"}

    center_to: StringProperty()

    def execute(self, context):
    #        bpy.ops.object.select_all(action='DESELECT')
        if self.center_to == "mass":
            selection = context.selected_objects
            # translate objects in SCS coordinate
            for obj in selection:
                obj.select_set(True)
                bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS')
        elif self.center_to == "cursor":
            ob_active = context.active_object
            bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

        return {'FINISHED'}


class OBJECT_OT_labelonoff(bpy.types.Operator):
    bl_idname = "label.onoff"
    bl_label = "Label on / off"
    bl_options = {"REGISTER", "UNDO"}

    onoff: BoolProperty()

    def execute(self, context):
        selection = context.selected_objects
        for obj in selection:
            obj.select_set(True)
            obj.show_name = self.onoff
        return {'FINISHED'}


#############################################
## funzioni per esportare obj e textures 
#############################################

def get_principled_node(mat):
    for node in mat.node_tree.nodes:
        if node.name == 'Principled BSDF':
            return node

def get_connected_input_node(node, input_link):
    node_input = node.inputs[input_link].links[0].from_node
    return node_input

def extract_image_paths_from_mat(ob, mat):
    node = get_principled_node(mat)
    relevant_input_links = ['Base Color', 'Roughness', 'Metallic', 'Normal']
    found_paths = []
    image_path = ''
    context = bpy.context
    for input_link in relevant_input_links:
        if node.inputs[input_link].is_linked:
            node_input = get_connected_input_node(node, input_link)
            if node_input.type == 'TEX_IMAGE':
                image_path = node_input.image.filepath_from_user() 
                found_paths.append(image_path)
            else:
                # in case of normal map
                if input_link == 'Normal' and node_input.type == 'NORMAL_MAP':
                    if node_input.inputs['Color'].is_linked:
                        node_input_input = get_connected_input_node(node_input, 'Color')
                        image_path = node_input_input.image.filepath_from_user() 
                        found_paths.append(image_path)
                    else:
                        found_paths.append('None')
                        emviq_error_record_creator(ob, "missing image node", mat, input_link)

                else:
                    found_paths.append('None')
                    emviq_error_record_creator(ob, "missing image node", mat, input_link)
                                      
        else:
            found_paths.append('None')
            emviq_error_record_creator(ob, "missing image node", mat, input_link)
    
    return found_paths

def emviq_error_record_creator(ob, description, mat, tex_type):
    scene = bpy.context.scene
    scene.emviq_error_list.add()
    ultimorecord = len(scene.emviq_error_list)-1
    scene.emviq_error_list[ultimorecord].name = ob.name
    scene.emviq_error_list[ultimorecord].description = description
    scene.emviq_error_list[ultimorecord].material = mat.name
    scene.emviq_error_list[ultimorecord].texture_type = tex_type


def copy_tex_ob(ob, destination_path):
    # remove old mtl files
    mtl_file = os.path.join(destination_path, ob.name+".mtl")
    os.remove(mtl_file)
    #creating a new custom mtl file
    f = open(mtl_file, 'w', encoding='utf-8')     
    for mat in ob.material_slots:
        f.write("%s %s\n" % ("newmtl", mat.material.name))
        image_file_path = extract_image_paths_from_mat(ob, mat.material)
        number_type = 0
        for current_file_path in image_file_path:
            if current_file_path != 'None':
                current_path_splitted = os.path.split(current_file_path)
                suffix = set_tex_type_name(number_type)
                current_image_file = os.path.splitext(current_path_splitted[1])
                #current_image_file_with_suffix = (current_image_file[0] + '_' + suffix + current_image_file[1])
                current_image_file_with_suffix = (mat.name + '_' + suffix + current_image_file[1])
                if number_type == 0:
                    f.write("%s %s\n" % ("map_Kd", current_image_file_with_suffix))
                destination_file = os.path.join(destination_path, current_image_file_with_suffix)
                shutil.copyfile(current_file_path, destination_file)
            number_type += 1
    f.close()

def set_tex_type_name(number_type):
    if number_type == 0:
        string_type = 'ALB'
    if number_type == 1:
        string_type = 'ROU'
    if number_type == 2:
        string_type = 'MET'
    if number_type == 3:
        string_type = 'NOR'
    return string_type

def substitue_with_custom_mtl(ob, export_sub_folder):
    mtl_file = os.path.join(export_sub_folder+ob.name+".mtl")
    os.remove(mtl_file)
    f = open(mtl_file, 'w', encoding='utf-8')
    for mat in ob.material_slots:
        f.write("%s %s\n" % ("newmtl", mat.material.name))
        f.write("%s %s\n" % ("map_Kd", mat.material.name+"_ALB"))
        mat.material.name

    f.close() 

#create_collection

class em_create_collection(bpy.types.Operator):
    bl_idname = "create.collection"
    bl_label = "Create Collection"
    bl_description = "Create Collection"
    bl_options = {'REGISTER', 'UNDO'}

    def create_collection(target_collection):
        context = bpy.context
        if bpy.data.collections.get(target_collection) is None:
            currentCol = bpy.context.blend_data.collections.new(name= target_collection)
            bpy.context.scene.collection.children.link(currentCol)
        else:
            currentCol = bpy.data.collections.get(target_collection)
        return currentCol

def identify_node(name):
    #import re
    extractor_pattern = re.compile(r"D\.\d+\.\d+")
    node_type = ""
    if  name.match(extractor_pattern):
        node_type = "Extractor"
    elif name.startswith("C."):
        node_type = "Combiner"
    elif name.startswith("D."):
        node_type = "Document"
    
    return node_type

def inspect_load_dosco_files():
    context = bpy.context
    scene = context.scene
    em_tools = scene.em_tools
    em_settings = bpy.context.window_manager.em_addon_settings

    if (em_tools.active_file_index >= 0 and 
        em_tools.graphml_files[em_tools.active_file_index]):
        
        # Ottieni il grafo attivo
        graph_id = em_tools.graphml_files[em_tools.active_file_index].name
        graph = get_graph(graph_id)
        if not graph:
            return

        dir_path = em_tools.graphml_files[em_tools.active_file_index].dosco_dir
        abs_dir_path = bpy.path.abspath(dir_path)

        extractor_pattern = re.compile(r"D\.\d+\.\d+")

        for entry in os.listdir(abs_dir_path):
            file_path = os.path.join(abs_dir_path, entry)
            if os.path.isfile(file_path):
                # Gestione estrattori
                if extractor_pattern.match(entry):
                    counter = 0
                    for extractor_element in scene.em_extractors_list:
                        if entry.startswith(extractor_element.name):
                            if em_settings.preserve_web_url and is_valid_url(scene.em_extractors_list[counter].url):
                                pass
                            else:
                                # Aggiorna la lista Blender
                                scene.em_extractors_list[counter].url = entry
                                scene.em_extractors_list[counter].icon_url = "CHECKBOX_HLT"
                                
                                # Aggiorna/crea nodo link nel grafo
                                extractor_node = graph.find_node_by_id(extractor_element.id_node)
                                if extractor_node:
                                    update_or_create_link_node(graph, extractor_node, entry, em_settings.preserve_web_url)
                        counter += 1

                # Gestione combiners
                elif entry.startswith("C."):
                    counter = 0
                    for combiner_element in scene.em_combiners_list:
                        if entry.startswith(combiner_element.name):
                            if not em_settings.preserve_web_url and not is_valid_url(scene.em_combiners_list[counter].url):
                                # Aggiorna la lista Blender
                                scene.em_combiners_list[counter].url = entry
                                scene.em_combiners_list[counter].icon_url = "CHECKBOX_HLT"
                                
                                # Aggiorna/crea nodo link nel grafo
                                combiner_node = graph.find_node_by_id(combiner_element.id_node)
                                if combiner_node:
                                    update_or_create_link_node(graph, combiner_node, entry, em_settings.preserve_web_url)
                        counter += 1

                # Gestione documenti
                elif entry.startswith("D."):
                    counter = 0
                    for document_element in scene.em_sources_list:
                        if entry.startswith(document_element.name):
                            if em_settings.preserve_web_url and is_valid_url(scene.em_sources_list[counter].url):
                                pass
                            else:
                                # Aggiorna la lista Blender
                                scene.em_sources_list[counter].url = entry
                                scene.em_sources_list[counter].icon_url = "CHECKBOX_HLT"
                                
                                # Aggiorna/crea nodo link nel grafo
                                document_node = graph.find_node_by_id(document_element.id_node)
                                if document_node:
                                    update_or_create_link_node(graph, document_node, entry, em_settings.preserve_web_url)
                        counter += 1
    return

def update_or_create_link_node(graph, source_node, url, preserve_existing=True):
    """
    Aggiorna un nodo link esistente o ne crea uno nuovo.
    
    Args:
        graph: Il grafo s3Dgraphy
        source_node: Il nodo sorgente (documento, estrattore o combiner)
        url: L'URL o percorso da assegnare
        preserve_existing: Se True, preserva i link esistenti con URL web
    """
    link_node_id = f"{source_node.node_id}_link"
    existing_link = graph.find_node_by_id(link_node_id)
    
    if existing_link:
        if preserve_existing and is_valid_url(existing_link.data.get("url", "")):
            return
        # Aggiorna l'URL del nodo link esistente
        existing_link.url = url
    else:
        # Crea un nuovo nodo link
        
        link_node = LinkNode(
            node_id=link_node_id,
            name=f"Link to {source_node.name}",
            description=f"Link to {source_node.description}" if source_node.description else "",
            url=url
        )
        graph.add_node(link_node)
        
        # Crea l'edge
        edge_id = f"{source_node.node_id}_has_linked_resource_{link_node_id}"
        if not graph.find_edge_by_id(edge_id):
            graph.add_edge(
                edge_id=edge_id,
                edge_source=source_node.node_id,
                edge_target=link_node.node_id,
                edge_type="has_linked_resource"
            )


def is_graph_available(context):
    """
    Check if a valid graph is available in the current context.
    
    Args:
        context: Blender context
        
    Returns:
        tuple: (bool, graph) where bool indicates if a graph is available,
               and graph is the actual graph object or None
    """
    if not hasattr(context.scene, 'em_tools'):
        return False, None
        
    em_tools = context.scene.em_tools
    
    # Check if graphml_files collection exists and has items
    if not hasattr(em_tools, 'graphml_files') or len(em_tools.graphml_files) == 0:
        return False, None
        
    # Check if active_file_index is valid
    if em_tools.active_file_index < 0 or em_tools.active_file_index >= len(em_tools.graphml_files):
        return False, None
        
    try:
        # Get the active graphml file
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        
        # Try to get the actual graph
        from .s3Dgraphy import get_graph
        graph = get_graph(graphml.name)
        
        return bool(graph), graph
    except Exception as e:
        print(f"Error accessing graph: {str(e)}")
        return False, None

def update_visibility_icons(context, list_type="em_list"):
    """
    Updates the visibility icons for all items in the list.
    
    Args:
        context: Blender context
        list_type: Type of list to update
    """
    scene = context.scene
    list_items = getattr(scene, list_type, None)
    
    if not list_items:
        return
        
    for item in list_items:
        obj = bpy.data.objects.get(item.name)
        if obj:
            item.is_visible = not obj.hide_viewport

def check_and_activate_collection(obj_name):
    """
    Checks if an object is in a hidden collection and activates it.
    
    Args:
        obj_name: Name of the object to check
        
    Returns:
        tuple: (bool, list) where bool indicates if any collections were activated,
               and list contains the names of activated collections
    """
    import bpy
    activated_collections = []
    obj = bpy.data.objects.get(obj_name)
    
    if not obj:
        return False, []
    
    # Find all collections containing this object
    for collection in bpy.data.collections:
        if obj.name in collection.objects and collection.hide_viewport:
            collection.hide_viewport = False
            activated_collections.append(collection.name)
            
    return bool(activated_collections), activated_collections

def update_em_list_with_visibility_info(context):
    """
    Update the visibility status of all items in the em_list.
    
    Args:
        context: Blender context
    """
    scene = context.scene
    
    for item in scene.em_list:
        obj = bpy.data.objects.get(item.name)
        if obj:
            item.is_visible = not obj.hide_viewport


def generate_blender_object_name(node):
    """
    Genera un nome univoco per un oggetto Blender basato sul nodo.
    
    Args:
        node: Il nodo per cui generare il nome
        
    Returns:
        str: Il nome univoco per l'oggetto Blender
    """
    # Se il nome è già prefissato, usalo direttamente
    if '_' in node.name:
        return node.name
    
    # Altrimenti, costruisci il nome con il prefisso
    prefix = ""
    graph_code = node.attributes.get('graph_code')
    
    if graph_code:
        prefix = f"{graph_code}_"
    else:
        # Prova a ricavare il codice dal graph_id
        graph_id = node.attributes.get('graph_id')
        if graph_id:
            # Usa le prime lettere dell'ID per un prefisso sintetico
            prefix = f"{graph_id[:5]}_"
    
    # Se non abbiamo un prefisso, usa il nome direttamente
    if not prefix:
        return node.name
    
    # Assicurati che il nome non superi i limiti di Blender
    max_name_length = 60 - len(prefix)
    safe_name = node.name[:max_name_length]
    
    return f"{prefix}{safe_name}"