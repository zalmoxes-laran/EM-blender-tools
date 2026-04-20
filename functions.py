import xml.etree.ElementTree as ET
import bpy # type: ignore
import os
import re
import json
import shutil
import bpy.props as prop # type: ignore
from bpy.props import (BoolProperty, # type: ignore
                       FloatProperty,
                       StringProperty,
                       EnumProperty,
                       CollectionProperty,
                       IntProperty
                       )

from urllib.parse import urlparse

from s3dgraphy.utils.utils import get_material_color
from s3dgraphy.nodes.link_node import LinkNode
from s3dgraphy import load_graph_from_file, get_graph

import platform
from pathlib import Path

# ✅ AGGIUNGERE questa import
from .operators.addon_prefix_helpers import (
    node_name_to_proxy_name,
    proxy_name_to_node_name,
    get_proxy_from_node,
    get_active_graph_code
)

# ============================
# LOGGING UTILITIES
# ============================

def em_log(message, level="INFO"):
    """
    Conditional logging based on addon preferences.

    Args:
        message: The message to log
        level: "DEBUG", "INFO", "WARNING", "ERROR"

    Behavior:
        - WARNING and ERROR: Always printed
        - INFO and DEBUG: Only if verbose_logging is enabled in preferences

    Usage:
        em_log("Processing 10 nodes", "DEBUG")
        em_log("Import completed successfully", "INFO")
        em_log("Missing file", "WARNING")
        em_log("Critical failure", "ERROR")
    """
    # Sempre mostra WARNING ed ERROR
    if level in ["WARNING", "ERROR"]:
        prefix = f"[EM {level}]"
        print(f"{prefix} {message}")
        return

    # INFO e DEBUG solo se verbose è attivo
    try:
        prefs = bpy.context.preferences.addons.get(__package__.split('.')[0])
        if prefs and hasattr(prefs.preferences, 'verbose_logging') and prefs.preferences.verbose_logging:
            prefix = f"[EM {level}]"
            print(f"{prefix} {message}")
    except:
        # Fallback silenzioso se non riusciamo ad accedere alle preferences
        # (es. durante l'inizializzazione dell'addon)
        pass

def clean_value_for_ui(value):
    """
    Clean string values for UI display.
    Removes newlines and extra whitespace that could break UI layouts.

    Args:
        value: String value to clean (or None)

    Returns:
        Cleaned string value
    """
    if value is None:
        return ""

    # Convert to string if not already
    value_str = str(value)

    # Replace newlines with spaces
    value_str = value_str.replace('\n', ' ').replace('\r', ' ')

    # Remove excessive whitespace
    value_str = ' '.join(value_str.split())

    return value_str

def get_compatible_icon(icon_name):
    """Return the appropriate icon name based on Blender version"""
    version = bpy.app.version
    
    # Mapping of old icons to new icons for Blender 4.4+
    icon_mappings = {
        'SEQUENCE_COLOR_01': 'STRIP_COLOR_01',
        'SEQUENCE_COLOR_02': 'STRIP_COLOR_02',
        'SEQUENCE_COLOR_03': 'STRIP_COLOR_03',
        'SEQUENCE_COLOR_04': 'STRIP_COLOR_04',
        'SEQUENCE_COLOR_05': 'STRIP_COLOR_05',
        'SEQ_SEQUENCER': 'SEQ_SEQUENCER',
        'LIGHTPROBE_PLANAR': 'LIGHTPROBE_PLANE',
        # Add more mappings as needed
    }
    
    # Check if we're on Blender 4.4 or later
    if version[0] > 4 or (version[0] == 4 and version[1] >= 4):
        return icon_mappings.get(icon_name, icon_name)
    else:
        return icon_name

def ensure_valid_index(collection_property, index_property_name, context=None, show_popup=True, data_object=None):
    """
    Ensures that the index for a collection property is valid.

    Args:
        collection_property: The collection property
        index_property_name: The name of the index property
        context: Blender context (optional)
        show_popup: Whether to show a popup when correcting the index
        data_object: Optional PropertyGroup that contains the index property (for nested properties)
    """
    # Get the owner object that contains both properties
    # If data_object is provided, use it (for nested PropertyGroups)
    # Otherwise, use id_data (for Scene-level properties)
    owner = data_object if data_object is not None else collection_property.id_data

    # Get current index value
    current_index = getattr(owner, index_property_name)
    
    # Check if collection is empty
    if len(collection_property) == 0:
        # Set index to -1 for empty collections
        setattr(owner, index_property_name, -1)
        print(f"Collection is empty, reset {index_property_name} to -1")
        return False
    
    # Check if index is out of range
    if current_index < 0 or current_index >= len(collection_property):
        # Reset to a valid index (first item)
        setattr(owner, index_property_name, 0)
        print(f"Index {current_index} out of range for collection (size {len(collection_property)}), reset to 0")
        
        # Report if context is provided AND show_popup is True
        if context and show_popup:
            import bpy
            bpy.context.window_manager.popup_menu(
                lambda self, ctx: self.layout.label(text=f"Reset {index_property_name} to valid value"),
                title="Index Out of Range",
                icon='INFO'
            )
            
    return True

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
    from s3dgraphy import get_all_graph_ids
    
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
    from s3dgraphy import get_graph
    
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
        graph = get_graph(graphml.name)
        
        return bool(graph), graph
    except Exception as e:
        print(f"Error accessing graph: {str(e)}")
        return False, None

def resolve_propagative_property(context, node_id, rule_id, default=None):
    """Resolve a DP-32 propagative property for a node on the active graph.

    Returns ``(value, source_level)`` where ``source_level`` is one of
    ``"node"``, ``"swimlane"``, ``"graph"`` or ``None`` (when the default
    was used). Safe to call from any panel draw(): on failure returns
    ``(default, None)`` without raising.

    Args:
        context: Blender context
        node_id: s3Dgraphy node id (UUID string) to resolve against
        rule_id: One of the registered rule ids ("author", "license",
            "embargo", "absolute_time_start", "absolute_time_end").
        default: Value to return when nothing resolves.
    """
    try:
        ok, graph = is_graph_available(context)
        if not ok or graph is None:
            return default, None
        node = graph.find_node_by_id(node_id)
        if node is None:
            return default, None
        from s3dgraphy.resolvers import resolve_with_source, get_rule
        value, source = resolve_with_source(
            graph, node, get_rule(rule_id), default=default
        )
        return value, source
    except Exception:
        return default, None


def draw_propagative_metadata(layout, context, node_id, *,
                              include_time=True,
                              include_author=True,
                              include_license=True,
                              include_embargo=True,
                              title="Metadata",
                              collapsible=True):
    """Draw a 'Propagative metadata' subsection in a panel.

    When ``collapsible=True`` (the default, used by the Stratigraphy
    Manager) the section is folded behind a TRIA_RIGHT/TRIA_DOWN toggle
    driven by ``scene.em_tools.show_propagative_metadata`` (closed by
    default). The Epoch Manager and Document Manager pass
    ``collapsible=False`` so the section renders inline without a toggle
    — for those panels the subsection is always visible and the
    information is compact enough that hiding it adds no value.

    For each enabled property the box shows the resolved value and the
    source level tag (``[node]`` / ``[swimlane]`` / ``[graph]``) so the
    user can see where the value is coming from. Works for EpochNode,
    US, Document and any other node type that makes sense as a resolver
    context.
    """
    em_tools = getattr(context.scene, "em_tools", None)

    box = layout.box()
    header = box.row(align=True)

    if collapsible and em_tools is not None:
        expanded = bool(getattr(em_tools, "show_propagative_metadata", False))
        header.prop(
            em_tools, "show_propagative_metadata",
            text=title,
            icon='TRIA_DOWN' if expanded else 'TRIA_RIGHT',
            emboss=False,
        )
        if not expanded:
            return
    else:
        header.label(text=title, icon='INFO')

    rows = []
    if include_time:
        rows.append(("Start", "absolute_time_start"))
        rows.append(("End",   "absolute_time_end"))
    if include_author:
        rows.append(("Author",  "author"))
    if include_license:
        rows.append(("License", "license"))
    if include_embargo:
        rows.append(("Embargo", "embargo"))

    any_resolved = False
    for caption, rule_id in rows:
        value, source = resolve_propagative_property(context, node_id, rule_id)
        r = box.row(align=True)
        r.label(text=f"{caption}:")
        if value is None:
            r.label(text="—", icon='NONE')
            continue
        any_resolved = True
        # Format numeric times without stray ".0"
        if rule_id in ("absolute_time_start", "absolute_time_end") and isinstance(value, (int, float)):
            text = str(int(value)) if float(value).is_integer() else str(value)
        else:
            text = str(value)
        r.label(text=text)
        if source:
            tag = r.row()
            tag.alignment = 'RIGHT'
            tag.label(text=f"[{source}]")

    if not any_resolved:
        box.label(text="(no propagative metadata for this node)", icon='NONE')


def get_us_document_nodes(graph, us_node_id):
    """
    Return all Document nodes connected to a given stratigraphic unit.
    Supports legacy and current edge types that link an US to its documents.
    """
    if not graph or not us_node_id:
        return []

    document_edge_types = {
        "has_documentation",       # ✅ v1.5.3: semantic edge type (created directly by EM Setup)
        "generic_connection",      # fallback for unknown node types (refined before export)
        "is_documented_by",        # possible reversed semantics
        "extracted_from",          # ExtractorNode → DocumentNode
    }

    doc_ids = set()
    doc_nodes = []

    for edge in getattr(graph, "edges", []):
        if edge.edge_type not in document_edge_types:
            continue

        candidate_id = None
        if edge.edge_source == us_node_id:
            candidate_id = edge.edge_target
        elif edge.edge_target == us_node_id:
            candidate_id = edge.edge_source

        if not candidate_id or candidate_id in doc_ids:
            continue

        node = graph.find_node_by_id(candidate_id)
        if node and hasattr(node, "node_type") and str(node.node_type).lower() == "document":
            doc_ids.add(candidate_id)
            doc_nodes.append(node)

    return doc_nodes

def is_valid_url(url_string):
    parsed_url = urlparse(url_string)
    return bool(parsed_url.scheme) or bool(parsed_url.netloc)

def menu_func(self, context):
    self.layout.separator()


def is_reconstruction_us(node):
    """
    Determine if a node represents a reconstruction unit.
    Compatible with both direct node objects and s3Dgraphy nodes.
    
    Args:
        node: The node to check
        
    Returns:
        bool: True if the node is a reconstruction unit, False otherwise
    """
    # Caso 1: Il nodo ha un attributo 'shape' diretto
    if hasattr(node, 'shape'):
        return node.shape in ["parallelogram", "ellipse", "hexagon", "octagon"]
    
    # Caso 2: Il nodo ha un attributo 'attributes' con una chiave 'shape'
    if hasattr(node, 'attributes') and isinstance(node.attributes, dict) and 'shape' in node.attributes:
        return node.attributes['shape'] in ["parallelogram", "ellipse", "hexagon", "octagon"]
    
    # Caso 3: Il nodo ha un attributo 'node_type'
    if hasattr(node, 'node_type'):
        # Alcuni tipi di nodi sono sempre ricostruttivi
        return node.node_type in ['USVs', 'USVn', 'VSF', 'SF']
    
    # Caso 4: controllo sul border_style per casi speciali
    if hasattr(node, 'border_style'):
        return node.border_style in ['#D8BD30', '#B19F61']  # Colori per SF e VSF
    
    # Se non riusciamo a determinare il tipo, assumiamo che non sia ricostruttivo
    print(f"Warning: Could not determine if node {getattr(node, 'name', 'unknown')} is reconstructive")
    return False


### #### #### #### #### #### #### #### ####
##### functions to switch menus in UI  ####
### #### #### #### #### #### #### #### ####

def sync_Switch_em(self, context):
    scene = context.scene
    em_settings = scene.em_tools.settings
    if scene.em_tools.settings.em_proxy_sync is True:
        scene.em_tools.settings.em_proxy_sync2 = False
        scene.em_tools.settings.em_proxy_sync2_zoom = False
    return

def sync_update_epoch_soloing(self, context):
    scene = context.scene
    soling = False
    epochs = scene.em_tools.epochs.list
    for epoch in epochs:
        if epoch.epoch_soloing is True:
            soloing_epoch = epoch
            soloing = True
    if soloing is True:
        for epoch in epochs:
            if epoch is not soloing_epoch:
                pass
    return

def sync_Switch_proxy(self, context):
    scene = context.scene
    em_settings = scene.em_tools.settings
    if scene.em_tools.settings.em_proxy_sync2 is True:
        scene.em_tools.settings.em_proxy_sync = False
    return

## #### #### #### #### #### #### #### #### #### #### ####
##### Functions to check properties of scene objects ####
## #### #### #### #### #### #### #### #### #### #### ####

def get_em_list_path(scene, list_name):
    """
    Get the correct path to an EM list, handling both legacy and current architecture.

    Args:
        scene: Blender scene
        list_name: Name of the list (e.g., 'em_extractors_list')

    Returns:
        str: Path to use with eval() (e.g., 'scene.em_tools.em_extractors_list')
    """
    # Handle both old and new paths for compatibility
    if hasattr(scene, list_name):
        # Legacy path: scene.em_extractors_list
        return "scene." + list_name
    else:
        # New path: scene.em_tools.em_extractors_list
        return "scene.em_tools." + list_name


def check_if_current_obj_has_brother_inlist(obj_name, list_type):
    scene = bpy.context.scene
    list_cmd = get_em_list_path(scene, list_type)

    is_brother = False
    for element_list in eval(list_cmd):
        # Check if element_list has a 'name' attribute before comparing
        if hasattr(element_list, 'name') and element_list.name == obj_name:
            is_brother = True
            return is_brother
    return is_brother

def select_3D_obj(node_name, context=None, graph=None):
    """
    Seleziona un oggetto 3D a partire dal nome del nodo.
    
    ✅ MODIFICATO: ora accetta il nome pulito del nodo e gestisce il prefisso internamente
    
    Args:
        node_name: Il nome del nodo (senza prefisso)
        context: Contesto Blender (opzionale)
        graph: Istanza del grafo (opzionale)
    """
    
    if context is None:
        context = bpy.context

    # Converti il nome del nodo nel nome del proxy (aggiunge prefisso se necessario)
    proxy_name = node_name_to_proxy_name(node_name, context=context, graph=graph)
    
    # Seleziona l'oggetto
    bpy.ops.object.select_all(action="DESELECT")
    # ✅ OPTIMIZED: Use object cache
    from .object_cache import get_object_cache
    obj = get_object_cache().get_object(proxy_name)
    
    if obj:
        activated_collections = []

        # Ensure object collections are active in current View Layer
        try:
            from .stratigraphy_manager.operators import activate_collection_fully
            for collection in obj.users_collection:
                try:
                    if activate_collection_fully(context, collection):
                        activated_collections.append(collection.name)
                except Exception:
                    pass
        except Exception:
            pass

        # Make object visible/selectable before selection
        if obj.hide_viewport:
            obj.hide_viewport = False
        if obj.hide_get():
            try:
                obj.hide_set(False)
            except RuntimeError:
                pass
        if obj.hide_select:
            obj.hide_select = False

        try:
            obj.select_set(True)
            context.view_layer.objects.active = obj
        except RuntimeError as e:
            show_popup_message(
                context,
                "Selection Error",
                f"Could not select object '{proxy_name}'.\n{e}",
                'ERROR'
            )
            return

        if activated_collections:
            show_popup_message(
                context,
                "Collections Activated",
                "The following collections have been activated:\n" + "\n".join(sorted(set(activated_collections))),
                'INFO'
            )
    else:
        print(f"Warning: Object '{proxy_name}' not found in scene")

def select_list_element_from_obj_proxy(obj, list_type, context=None, graph=None):
    """
    Seleziona l'elemento nella lista a partire dal proxy 3D.
    
    Args:
        obj: L'oggetto 3D Blender
        list_type: Il tipo di lista (es. "em_list")
        context: Contesto Blender (opzionale)
        graph: Istanza del grafo (opzionale)
    """
    
    if context is None:
        context = bpy.context
        
    scene = context.scene
    
    # Ottieni il nome del nodo dal nome del proxy (rimuove prefisso)
    node_name = proxy_name_to_node_name(obj.name, context=context, graph=graph)
    
    # Mappa delle liste supportate -> (getter lista, oggetto che contiene l'indice, nome attributo indice)
    list_registry = {
        "em_list": (lambda sc: sc.em_tools.stratigraphy.units, lambda sc: sc.em_tools.stratigraphy, "units_index"),
        "em_reused": (lambda sc: sc.em_tools.stratigraphy.reused, lambda sc: sc.em_tools.stratigraphy, "reused_index"),
        "em_sources_list": (lambda sc: sc.em_tools.em_sources_list, lambda sc: sc.em_tools, "em_sources_list_index"),
        "em_properties_list": (lambda sc: sc.em_tools.em_properties_list, lambda sc: sc.em_tools, "em_properties_list_index"),
        "em_extractors_list": (lambda sc: sc.em_tools.em_extractors_list, lambda sc: sc.em_tools, "em_extractors_list_index"),
        "em_combiners_list": (lambda sc: sc.em_tools.em_combiners_list, lambda sc: sc.em_tools, "em_combiners_list_index"),
        "em_v_sources_list": (lambda sc: sc.em_tools.em_v_sources_list, lambda sc: sc.em_tools, "em_v_sources_list_index"),
        "em_v_properties_list": (lambda sc: sc.em_tools.em_v_properties_list, lambda sc: sc.em_tools, "em_v_properties_list_index"),
        "em_v_extractors_list": (lambda sc: sc.em_tools.em_v_extractors_list, lambda sc: sc.em_tools, "em_v_extractors_list_index"),
        "em_v_combiners_list": (lambda sc: sc.em_tools.em_v_combiners_list, lambda sc: sc.em_tools, "em_v_combiners_list_index"),
        # Epoch list now stored under em_tools
        "epoch_list": (lambda sc: sc.em_tools.epochs.list, lambda sc: sc.em_tools.epochs, "list_index"),
    }

    list_getter, index_owner_getter, index_attr = list_registry.get(
        list_type,
        (None, None, None),
    )

    if not list_getter:
        print(f"Warning: list_type '{list_type}' not recognized in select_list_element_from_obj_proxy")
        return

    collection = list_getter(scene)
    index_owner = index_owner_getter(scene)

    # Reset containment/chain filters when selecting from 3D viewport
    if list_type == "em_list":
        strat = scene.em_tools.stratigraphy
        if strat.filter_by_containment or strat.filter_by_instance_chain:
            strat.filter_by_containment = False
            strat.containment_filter_node_id = ""
            strat.filter_by_instance_chain = False
            strat.instance_chain_filter_node_ids = ""
            # Reload full list so the element can be found
            try:
                bpy.ops.em.reset_filters()
            except Exception:
                pass
            collection = list_getter(scene)

    found = False
    for idx, item in enumerate(collection):
        if node_name == item.name:
            try:
                setattr(index_owner, index_attr, idx)
            except Exception as e:
                print(f"Warning: could not set index for {list_type}: {e}")
            found = True
            break
    
    # ✅ NUOVO: Se non troviamo una corrispondenza, mostra popup
    if not found:
        # Ottieni il nome del grafo attivo
        graph_name = "Unknown"
        if graph:
            graph_name = graph.attributes.get('graph_code', 'Unknown')
            if not graph_name or graph_name in ["", "site_ID"]:
                graph_name = getattr(graph, 'name', 'Unknown')
        else:
            # Prova a ottenere il nome del grafo dal context
            em_tools = scene.em_tools
            if em_tools.active_file_index >= 0 and em_tools.active_file_index < len(em_tools.graphml_files):
                graphml = em_tools.graphml_files[em_tools.active_file_index]
                graph_name = graphml.name
        
        show_popup_message(
            context,
            "No Corresponding US Found",
            f"Object '{obj.name}' does not have a corresponding US in graph '{graph_name}'",
            'ERROR'
        )

## diverrà deprecata !
def add_sceneobj_to_epochs():
    """
    Assegna oggetti 3D alle epoche basandosi sulla lista stratigrafica.

    ✅ CLEAN VERSION: Usa solo scene.em_tools.stratigraphy paths
    """
    scene = bpy.context.scene
    strat = scene.em_tools.stratigraphy  # ✅ Nuovo

    bpy.ops.object.select_all(action='DESELECT')

    epochs = scene.em_tools.epochs.list

    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            for USS in strat.units:  # ✅ Nuovo path
                if obj.name == USS.name:
                    for idx, epoch in enumerate(epochs):
                        if epoch.name == USS.epoch:
                            obj.select_set(True)
                            bpy.ops.epoch_manager.add_to_group(group_em_idx=idx)
                            obj.select_set(False)
                                                
### #### #### #### #### #### #### #### #### #### ####
#### Functions to extract data from GraphML file ####
### #### #### #### #### #### #### #### #### #### ####

def EM_list_clear(context, list_type):
    """
    Pulisce una lista in Blender.

    ✅ CLEAN VERSION: No dual-sync, single path only
    """
    scene = context.scene

    if list_type == "em_list":
        # ✅ SOLO nuova lista centralizzata
        scene.em_tools.stratigraphy.units.clear()

    elif list_type == "em_reused":
        # ✅ SOLO nuova lista centralizzata
        scene.em_tools.stratigraphy.reused.clear()

    # Paradata lists (non-streaming)
    elif list_type == "em_sources_list":
        scene.em_tools.em_sources_list.clear()
    elif list_type == "em_properties_list":
        scene.em_tools.em_properties_list.clear()
    elif list_type == "em_extractors_list":
        scene.em_tools.em_extractors_list.clear()
    elif list_type == "em_combiners_list":
        scene.em_tools.em_combiners_list.clear()

    # Paradata lists (streaming/versioned)
    elif list_type == "em_v_sources_list":
        scene.em_tools.em_v_sources_list.clear()
    elif list_type == "em_v_properties_list":
        scene.em_tools.em_v_properties_list.clear()
    elif list_type == "em_v_extractors_list":
        scene.em_tools.em_v_extractors_list.clear()
    elif list_type == "em_v_combiners_list":
        scene.em_tools.em_v_combiners_list.clear()

    # Other lists
    elif list_type == "edges_list":
        scene.em_tools.edges_list.clear()
    elif list_type == "emviq_error_list":
        scene.em_tools.emviq_error_list.clear()
    elif list_type == "epoch_list":
        # ✅ Epochs migrati a em_tools.epochs.list, ma alcune parti della UI usano ancora scene.epoch_list
        scene.em_tools.epochs.list.clear()
        if hasattr(scene, "epoch_list"):
            scene.epoch_list.clear()

    else:
        # Legacy fallback - should not be reached
        print(f"Warning: WARNING: EM_list_clear called with unknown list_type: {list_type}")

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

def create_derived_lists(node, graph=None):
    """
    Crea le liste derivate di proprietà per un nodo.
    
    ✅ MODIFICATO: aggiunto supporto per graph
    
    Args:
        node: Il nodo per cui creare le liste
        graph: Istanza del grafo (opzionale)
    """
    
    context = bpy.context
    scene = context.scene
    prop_index = 0
    EM_list_clear(context, "em_v_properties_list")

    is_property = False
    
    # Debug info
    print(f"\nRicerca proprietà per il nodo {node.name} (ID: {node.id_node})")
    
    # Get the active graph
    if graph is None:
        graph_exists, graph = is_graph_available(context)
        if not graph_exists:
            print("Error: Graph not available")
            return
    
    # Verify if the node ID exists in the graph
    found_node = graph.find_node_by_id(node.id_node)
    if not found_node:
        print(f"WARNING: Node with ID {node.id_node} not found in the graph!")
        return
    else:
        print(f"Node found in graph: {found_node.name} (ID: {found_node.node_id})")
    
    # Get properties using has_property edges
    # ✅ OPTIMIZED: Use edge index for O(1) lookup instead of O(E)
    from .graph_index import get_or_create_graph_index

    index = get_or_create_graph_index(graph)
    property_nodes = index.get_target_nodes(
        source_id=node.id_node,
        edge_type="has_property",
        node_type_filter='property'
    )

    # Debug output
    for prop_node in property_nodes:
        print(f"Trovata proprietà: {prop_node.name} (ID: {prop_node.node_id}) via has_property")

    is_property = len(property_nodes) > 0
    
    # Aggiorniamo la lista delle proprietà - ✅ SENZA prefisso
    if property_nodes:
        for i, prop_node in enumerate(property_nodes):
            scene.em_tools.em_v_properties_list.add()
            property_item = scene.em_tools.em_v_properties_list[i]

            # USA SEMPRE IL NOME PULITO
            property_item.name = prop_node.name

            property_item.description = prop_node.description if hasattr(prop_node, 'description') else ""
            property_item.url = prop_node.value if hasattr(prop_node, 'value') else ""
            property_item.id_node = prop_node.node_id
            property_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(prop_node.name, graph=graph)
            property_item.icon_url = "WORLD" if property_item.url else "WORLD_DATA"
            prop_index += 1

    print(f"Trovate {prop_index} proprietà per il nodo {node.id_node}")

    # Reset property index if needed
    if scene.em_tools.em_v_properties_list_index >= len(scene.em_tools.em_v_properties_list):
        scene.em_tools.em_v_properties_list_index = 0 if len(scene.em_tools.em_v_properties_list) > 0 else -1

def create_derived_combiners_list(passed_property_item):
    context = bpy.context
    scene = context.scene
    comb_index = 0
    is_combiner = False
    EM_list_clear(context, "em_v_combiners_list")

    print(f"La proprietà: {passed_property_item.name} ha id_nodo: {passed_property_item.id_node}")
    
    # Recuperiamo il grafo corrente
    graph_exists, graph = is_graph_available(context)
    
    if not graph_exists:
        print("Errore: Grafo non disponibile")
        return False
    
    # Cerchiamo combinatori collegati alla proprietà
    # ✅ OPTIMIZED: Use edge index for O(1) lookup instead of O(E)
    from .graph_index import get_or_create_graph_index

    index = get_or_create_graph_index(graph)

    # Get all edges from property (any edge type) to combiners
    combiner_nodes = index.get_target_nodes(
        source_id=passed_property_item.id_node,
        edge_type="has_combiner",  # Primary edge type
        node_type_filter='combiner'
    )

    # Fallback: some graphs may use different edge types, get all targets and filter
    if not combiner_nodes:
        # Get all edge types from this property
        edge_types = index.get_edge_types_from_source(passed_property_item.id_node)
        for edge_type in edge_types:
            nodes = index.get_target_nodes(
                source_id=passed_property_item.id_node,
                edge_type=edge_type,
                node_type_filter='combiner'
            )
            combiner_nodes.extend(nodes)

    # Debug output
    for comb_node in combiner_nodes:
        print(f"Trovato combinatore: {comb_node.name} (ID: {comb_node.node_id})")

    is_combiner = len(combiner_nodes) > 0
    
    # Aggiorniamo la lista dei combinatori - senza aggiungere prefissi
    if combiner_nodes:
        for i, comb_node in enumerate(combiner_nodes):
            scene.em_tools.em_v_combiners_list.add()
            combiner_item = scene.em_tools.em_v_combiners_list[i]

            # Use the original name without prefixing
            combiner_item.name = comb_node.name

            combiner_item.description = comb_node.description if hasattr(comb_node, 'description') else ""
            combiner_item.url = comb_node.sources[0] if hasattr(comb_node, 'sources') and comb_node.sources else ""
            combiner_item.id_node = comb_node.node_id
            combiner_item.icon_url = "WORLD" if combiner_item.url else "WORLD_DATA"
            combiner_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(combiner_item.name)
            comb_index += 1

    if is_combiner:
        if scene.em_tools.comb_paradata_streaming_mode:
            selected_combiner_node = scene.em_tools.em_v_combiners_list[scene.em_tools.em_v_combiners_list_index]
            create_derived_sources_list(selected_combiner_node)
        else:
            for v_list_combiner in scene.em_tools.em_v_combiners_list:
                create_derived_sources_list(v_list_combiner)
    else:
        EM_list_clear(context, "em_v_sources_list")
        EM_list_clear(context, "em_v_extractors_list")

    return is_combiner

def create_derived_extractors_list(passed_property_item, graph=None):
    """
    Crea la lista di extractors collegati a una proprietà.
    
    ✅ MODIFICATO: rimosso l'aggiunta manuale del prefisso
    
    Args:
        passed_property_item: L'item della proprietà selezionata
        graph: Istanza del grafo (opzionale)
    """
    
    context = bpy.context
    scene = context.scene
    extr_index = 0
    is_extractor = False
    EM_list_clear(context, "em_v_extractors_list")

    print(f"La proprietà: {passed_property_item.name} ha id_nodo: {passed_property_item.id_node}")
    
    # Recuperiamo il grafo corrente
    if graph is None:
        graph_exists, graph = is_graph_available(context)
        if not graph_exists:
            print("Errore: Grafo non disponibile")
            return False
    
    # Cerchiamo estrattori collegati alla proprietà
    # ✅ OPTIMIZED: Use edge index for O(1) lookup instead of O(E)
    from .graph_index import get_or_create_graph_index

    index = get_or_create_graph_index(graph)

    # Get extractors connected to this property
    extractor_nodes = index.get_target_nodes(
        source_id=passed_property_item.id_node,
        edge_type="has_extractor",  # Primary edge type
        node_type_filter='extractor'
    )

    # Fallback: try all edge types if none found
    if not extractor_nodes:
        edge_types = index.get_edge_types_from_source(passed_property_item.id_node)
        for edge_type in edge_types:
            nodes = index.get_target_nodes(
                source_id=passed_property_item.id_node,
                edge_type=edge_type,
                node_type_filter='extractor'
            )
            extractor_nodes.extend(nodes)

    # Debug output
    for extr_node in extractor_nodes:
        print(f"Trovato estrattore: {extr_node.name} (ID: {extr_node.node_id})")

    is_extractor = len(extractor_nodes) > 0

    # ✅ MODIFICATO: usa sempre il nome pulito (senza prefisso)
    if extractor_nodes:
        for i, extr_node in enumerate(extractor_nodes):
            scene.em_tools.em_v_extractors_list.add()
            extractor_item = scene.em_tools.em_v_extractors_list[i]

            # USA SEMPRE IL NOME PULITO
            extractor_item.name = extr_node.name

            extractor_item.description = extr_node.description if hasattr(extr_node, 'description') else ""
            extractor_item.url = extr_node.source if hasattr(extr_node, 'source') else ""
            extractor_item.id_node = extr_node.node_id
            extractor_item.icon_url = "WORLD" if extractor_item.url else "WORLD_DATA"
            extractor_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(extractor_item.name, graph=graph)
            extr_index += 1

    return is_extractor


def create_derived_sources_list(passed_extractor_item, graph=None):
    """
    Crea la lista di documenti collegati a un estrattore.
    
    ✅ MODIFICATO: rimosso l'aggiunta manuale del prefisso
    
    Args:
        passed_extractor_item: L'item dell'estrattore selezionato
        graph: Istanza del grafo (opzionale)
    """
    
    context = bpy.context
    scene = context.scene
    sour_index = 0
    EM_list_clear(context, "em_v_sources_list")
    
    print(f"passed_extractor_item: {passed_extractor_item.name} con id: {passed_extractor_item.id_node}")
    
    # Recuperiamo il grafo corrente
    if graph is None:
        graph_exists, graph = is_graph_available(context)
        if not graph_exists:
            print("Errore: Grafo non disponibile")
            return
    
    # Cerchiamo fonti collegate all'estrattore
    # ✅ OPTIMIZED: Use edge index for O(1) lookup instead of O(E)
    from .graph_index import get_or_create_graph_index

    index = get_or_create_graph_index(graph)

    # Get document nodes connected to this extractor
    source_nodes = index.get_target_nodes(
        source_id=passed_extractor_item.id_node,
        edge_type="has_source",  # Primary edge type
        node_type_filter='document'
    )

    # Fallback: try all edge types if none found
    if not source_nodes:
        edge_types = index.get_edge_types_from_source(passed_extractor_item.id_node)
        for edge_type in edge_types:
            nodes = index.get_target_nodes(
                source_id=passed_extractor_item.id_node,
                edge_type=edge_type,
                node_type_filter='document'
            )
            source_nodes.extend(nodes)

    # Debug output
    for src_node in source_nodes:
        print(f"Trovata fonte: {src_node.name} (ID: {src_node.node_id})")

    # ✅ MODIFICATO: usa sempre il nome pulito (senza prefisso)
    if source_nodes:
        for i, src_node in enumerate(source_nodes):
            scene.em_tools.em_v_sources_list.add()
            source_item = scene.em_tools.em_v_sources_list[i]

            # USA SEMPRE IL NOME PULITO
            source_item.name = src_node.name

            source_item.description = src_node.description if hasattr(src_node, 'description') else ""
            source_item.url = src_node.url if hasattr(src_node, 'url') else ""
            source_item.id_node = src_node.node_id
            source_item.icon_url = "WORLD" if source_item.url else "WORLD_DATA"
            source_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(source_item.name, graph=graph)
            sour_index += 1

    print(f"sources: {sour_index}")

def switch_paradata_lists(self, context):
    """
    Aggiorna paradata lists in base all'US selezionata.

    ✅ CLEAN VERSION: Usa solo scene.em_tools.stratigraphy paths
    """
    scene = context.scene
    strat = scene.em_tools.stratigraphy  # ✅ Nuovo

    # ✅ Usa nuovo path
    if strat.units_index >= 0 and strat.units_index < len(strat.units):
        selected_item = strat.units[strat.units_index]

        # Clear paradata lists
        EM_list_clear(context, "em_v_properties_list")
        EM_list_clear(context, "em_v_extractors_list")
        EM_list_clear(context, "em_v_combiners_list")
        EM_list_clear(context, "em_v_sources_list")

        # Verifica se c'è un grafo attivo prima di chiamare l'operatore
        if scene.em_tools.paradata_streaming_mode:
            # Controlla se c'è un file GraphML attivo
            em_tools = scene.em_tools
            if em_tools.active_file_index >= 0 and len(em_tools.graphml_files) > 0:
                try:
                    # Verifica se il grafo esiste
                    from s3dgraphy import get_graph
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

    return

## #### #### #### #### #### #### #### #### #### #### #### ####
#### Check the presence-absence of US against the graph.  ####
## #### #### #### #### #### #### #### #### #### #### #### ####

def check_objs_in_scene_and_provide_icon_for_list_element(node_name, graph=None, context=None):
    """
    Verifica se esiste un oggetto 3D in scena corrispondente al nodo e fornisce l'icona appropriata.
    
    ✅ FIXED per Blender 4.5: rimossa list comprehension che causava stack overflow
    """

    '''
    # 🔍 DEBUG: Stampa informazioni sul graph
    print(f"\nDEBUG check_objs - node_name: {node_name}")
    print(f"DEBUG check_objs - graph: {graph}")
    print(f"DEBUG check_objs - graph type: {type(graph)}")
    
    if graph:
        print(f"DEBUG check_objs - hasattr 'attributes': {hasattr(graph, 'attributes')}")
        if hasattr(graph, 'attributes'):
            print(f"DEBUG check_objs - graph.attributes: {graph.attributes}")
            print(f"DEBUG check_objs - graph_code in attributes: {'graph_code' in graph.attributes}")
            if 'graph_code' in graph.attributes:
                print(f"DEBUG check_objs - graph_code value: '{graph.attributes['graph_code']}'")
    '''

    # ✅ Converti il nome del nodo nel nome del proxy (aggiunge prefisso se necessario)
    proxy_name = node_name_to_proxy_name(node_name, context=context, graph=graph)
    
    #print(f"🔍 DEBUG check_objs - proxy_name result: '{proxy_name}'")
    
    # ✅ OPTIMIZED: Use object cache instead of bpy.data.objects.get()
    from .object_cache import get_object_cache
    cache = get_object_cache()
    obj = cache.get_object(proxy_name)
    
    #print(f"🔍 DEBUG check_objs - obj found: {obj is not None}")
    
    # ✅ FIX per Blender 4.5: rimossa la list comprehension problematica
    # Questa iterazione causava stack overflow con nomi multi-linea
    # La rimuoviamo completamente perché non è essenziale e causava il crash
    #if not obj:
        # Se proprio necessario, si può cercare in modo più sicuro:
        # - Limitando il numero di oggetti da controllare
        # - Usando un approccio iterativo invece di list comprehension
        # - Sanitizzando il node_name prima del confronto
        
        # Versione sicura (opzionale, commentata di default):
        # similar_objects = []
        # clean_node_name = node_name.replace('\n', '').replace('\r', '').strip()
        # for o in list(bpy.data.objects)[:100]:  # Limita a 100 oggetti
        #     try:
        #         if clean_node_name in o.name:
        #             similar_objects.append(o.name)
        #     except:
        #         pass
        # print(f"🔍 DEBUG check_objs - similar objects in scene: {similar_objects}")
        
        #print(f"🔍 DEBUG check_objs - object not found, skipping similarity check")
    
    # Restituisci l'icona appropriata
    if obj:
        return "LINKED"  # Oggetto esiste in scena
    else:
        return "UNLINKED"  # Oggetto non esiste

def update_icons(context, list_type):
    """
    Aggiorna le icone di una lista in base alla presenza degli oggetti 3D in scena.

    ✅ CLEAN VERSION: Usa i nuovi path centralizzati
    """

    #print(f"\n🔍 DEBUG update_icons - Starting for list_type: {list_type}")

    scene = context.scene

    # ✅ Map legacy list_type to new paths
    if list_type == "em_list":
        target_list = scene.em_tools.stratigraphy.units
    elif list_type == "em_reused":
        target_list = scene.em_tools.stratigraphy.reused
    elif list_type == "epoch_list":
        target_list = scene.em_tools.epochs.list
    else:
        # Handle paradata lists with em_tools prefix
        if "." in list_type:
            # Already has the full path (e.g., "em_tools.stratigraphy.units")
            list_path = "scene." + list_type
        elif list_type.startswith("em_v_") or list_type in ["em_extractors_list", "em_sources_list", "em_combiners_list", "em_properties_list"]:
            # Paradata lists need em_tools prefix
            list_path = "scene.em_tools." + list_type
        else:
            # Legacy format
            list_path = "scene." + list_type
        target_list = eval(list_path)

    # ✅ Ottieni il grafo attivo
    graph_exists, graph = is_graph_available(context)

    #print(f"🔍 DEBUG update_icons - graph_exists: {graph_exists}")
    #print(f"🔍 DEBUG update_icons - graph: {graph}")

    # Se il grafo non esiste, usa None (funzionerà comunque per oggetti senza prefisso)
    active_graph = graph if graph_exists else None

    # Aggiorna l'icona per ogni elemento
    element_count = 0
    for element in target_list:
        element_count += 1
        
        old_icon = element.icon
        #print(f"\n🔍 DEBUG update_icons - Element #{element_count}: {element.name}")
        #print(f"🔍 DEBUG update_icons - Old icon: {old_icon}")
        
        new_icon = check_objs_in_scene_and_provide_icon_for_list_element(
            element.name, 
            graph=active_graph,
            context=context
        )
        
        #print(f"🔍 DEBUG update_icons - New icon returned: {new_icon}")
        
        element.icon = new_icon
        
        #print(f"🔍 DEBUG update_icons - Icon after assignment: {element.icon}")
        #print(f"🔍 DEBUG update_icons - Assignment successful: {element.icon == new_icon}")
    
    #print(f"\n🔍 DEBUG update_icons - Completed. Updated {element_count} elements")
    
    return

## #### #### #### #### #### #### #### ####                       
 #### General functions for materials ####
## #### #### #### #### #### #### #### ####

def update_property_materials_alpha(alpha_value):
    """
    Update alpha for all property-based materials.
    ✅ OPTIMIZED: Uses material cache for 100× speedup (O(M×N) → O(M))
    """
    from .material_cache import get_material_cache

    scene = bpy.context.scene
    cache = get_material_cache()

    # ✅ OPTIMIZED: Get cached property materials (O(1) instead of O(M))
    property_materials = cache.get_property_materials()

    print(f"[OPTIMIZED] Found {len(property_materials)} property materials (cached)")
    if len(property_materials) > 0:
        print(f"  Sample materials: {[mat.name for mat in property_materials[:5]]}")

    # Update alpha for all property materials
    updated_count = 0

    for mat in property_materials:
        # ✅ OPTIMIZED: Get cached Principled node (O(1) instead of O(N))
        principled_node = cache.get_principled_node(mat)

        if principled_node:
            # Update alpha channel
            if 'Alpha' in principled_node.inputs:
                principled_node.inputs['Alpha'].default_value = alpha_value

            # Update base color alpha component
            current_color = principled_node.inputs['Base Color'].default_value
            if len(current_color) >= 3:
                new_color = (*current_color[:3], alpha_value)
                principled_node.inputs['Base Color'].default_value = new_color

            # Set appropriate blend mode
            if alpha_value < 1.0:
                mat.blend_method = 'BLEND'
            else:
                mat.blend_method = getattr(scene, 'proxy_blend_mode', 'OPAQUE')

            updated_count += 1

    print(f"[OPTIMIZED] Updated alpha to {alpha_value} for {updated_count}/{len(property_materials)} materials")
    return updated_count

def update_display_mode(self, context):
    """Updated display mode function with better error handling"""
    scene = bpy.context.scene
    
    try:
        if scene.em_tools.proxy_display_mode == "EM":
            bpy.ops.emset.emmaterial()
        elif scene.em_tools.proxy_display_mode == "Epochs":
            bpy.ops.emset.epochmaterial()
        elif scene.em_tools.proxy_display_mode == "Properties":
            # Prima aggiorna l'alpha dei materiali esistenti
            update_property_materials_alpha(scene.em_tools.proxy_display_alpha)
            
            # Poi riapplica i colori se necessario
            if (hasattr(scene, 'selected_property') and scene.selected_property and
                hasattr(scene, 'property_values') and len(scene.property_values) > 0):
                try:
                    bpy.ops.visual.apply_colors()
                except Exception as e:
                    print(f"Warning: Could not reapply property colors: {e}")
    except Exception as e:
        print(f"Error in update_display_mode: {e}")


def apply_property_colors_legacy_compatibility(context):
    """
    Legacy compatibility function for code that might still call old functions.
    This simply redirects to the new visual manager system.
    """
    scene = context.scene
    
    if not hasattr(scene, 'selected_property') or not scene.selected_property:
        print("No property selected for legacy compatibility function")
        return False
    
    try:
        bpy.ops.visual.apply_colors()
        return True
    except Exception as e:
        print(f"Error in legacy compatibility function: {e}")
        return False
    
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


def consolidate_EM_material_presence(overwrite_mats):
    EM_mat_list = ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'TSU', 'UL', 'serSU', 'serUSD', 'serUSVn', 'serUSVs']
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
    mat.blend_method = scene.em_tools.proxy_blend_mode
    links = mat.node_tree.links
    nodes = mat.node_tree.nodes
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (0, 0)
    mainNode = nodes.new('ShaderNodeBsdfPrincipled')
    mainNode.inputs['Base Color'].default_value = (R, G, B, A)
    mainNode.location = (-800, 50)
    mainNode.name = "diffuse"
    mainNode.inputs['Alpha'].default_value = scene.em_tools.proxy_display_alpha
    links.new(mainNode.outputs[0], output.inputs[0])


def set_materials_using_EM_list(context):
    """
    Set materials for proxies based on EM node types.
    ✅ FIXED: Now handles prefixed proxy names
    """
    from .operators.addon_prefix_helpers import node_name_to_proxy_name
    
    # Ottieni il grafo attivo
    graph_exists, graph = is_graph_available(context)
    active_graph = graph if graph_exists else None
    
    strat = context.scene.em_tools.stratigraphy  # ✅ Nuovo
    em_list_lenght = len(strat.units)
    counter = 0
    while counter < em_list_lenght:
        current_ob_em_list = strat.units[counter]
        overwrite_mats = True
        consolidate_EM_material_presence(overwrite_mats)
        
        if current_ob_em_list.icon == 'LINKED':
            # ✅ MODIFICATO: Converti il nome con prefisso
            proxy_name = node_name_to_proxy_name(
                current_ob_em_list.name,
                context=context,
                graph=active_graph
            )
            
            # ✅ MODIFICATO: Usa get() per gestire oggetti mancanti
            current_ob_scene = context.scene.objects.get(proxy_name)
            
            if not current_ob_scene:
                print(f"Warning: Warning: Object '{proxy_name}' not found")
                counter += 1
                continue
            
            ob_material_name = 'US'  # Default
            
            # Resto della logica invariata...
            if hasattr(current_ob_em_list, 'node_type') and current_ob_em_list.node_type:
                if current_ob_em_list.node_type in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'TSU', 'UL', 'serSU', 'serUSD', 'serUSVn', 'serUSVs']:
                    ob_material_name = current_ob_em_list.node_type
            else:
                # Fallback con shape/border
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
                    if current_ob_em_list.border_style == '#D8BD30':
                        ob_material_name = 'SF'
                    elif current_ob_em_list.border_style == '#B19F61':
                        ob_material_name = 'VSF'
                    else:
                        ob_material_name = 'VSF'
                elif current_ob_em_list.shape == 'roundrectangle':
                    ob_material_name = 'USD'
                
            mat = bpy.data.materials[ob_material_name]
            current_ob_scene.data.materials.clear()
            current_ob_scene.data.materials.append(mat)
        counter += 1

def proxy_shader_mode_function(self, context):
    scene = context.scene
    if scene.em_tools.proxy_shader_mode is True:
        scene.em_tools.proxy_blend_mode = "OPAQUE"
    else:
        scene.em_tools.proxy_blend_mode = "BLEND"
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
    """
    Set materials for proxies based on their epoch assignments.
    ✅ FIXED: Now handles prefixed proxy names
    """
    from .operators.addon_prefix_helpers import node_name_to_proxy_name
    
    # Ottieni il grafo attivo
    graph_exists, graph = is_graph_available(context)
    active_graph = graph if graph_exists else None
    
    scene = context.scene 
    mat_prefix = "ep_"
    
    epochs = scene.em_tools.epochs.list
    for epoch in epochs:
        matname = mat_prefix + epoch.name
        mat = consolidate_epoch_material_presence(matname)
        R = epoch.epoch_RGB_color[0]
        G = epoch.epoch_RGB_color[1]
        B = epoch.epoch_RGB_color[2]
        em_setup_mat_cycles(matname, R, G, B)
        
        strat = scene.em_tools.stratigraphy  # ✅ Nuovo
        for em_element in strat.units:
            if em_element.icon == "LINKED":
                if em_element.epoch == epoch.name:
                    # ✅ MODIFICATO: Converti il nome con prefisso
                    proxy_name = node_name_to_proxy_name(
                        em_element.name,
                        context=context,
                        graph=active_graph
                    )
                    
                    # ✅ OPTIMIZED: Use object cache
                    from .object_cache import get_object_cache
                    obj = get_object_cache().get_object(proxy_name)
                    
                    if obj:
                        obj.data.materials.clear()
                        obj.data.materials.append(mat)
                    else:
                        print(f"Warning: Warning: Object '{proxy_name}' not found")



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
    scene.em_tools.emviq_error_list.add()
    ultimorecord = len(scene.em_tools.emviq_error_list)-1
    scene.em_tools.emviq_error_list[ultimorecord].name = ob.name
    scene.em_tools.emviq_error_list[ultimorecord].description = description
    scene.em_tools.emviq_error_list[ultimorecord].material = mat.name
    scene.em_tools.emviq_error_list[ultimorecord].texture_type = tex_type


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

def inspect_load_dosco_files_on_graph(graph_instance, dosco_dir):
    """
    Versione che aggiorna direttamente i nodi del grafo invece delle liste UI.

    Hybrid-C Phase 1b: every attribute override (``node.url``) is
    recorded via ``record_attribute_override`` and frozen with
    ``freeze_aux_value``, and every enrichment child (LinkNode + its
    ``has_linked_resource`` edge) is tagged with ``injected_by``. On a
    subsequent volatile GraphML save the exporter can revert the URL
    and strip the LinkNodes automatically; on bake they are promoted
    to graph-native.
    """
    if not dosco_dir or not os.path.exists(dosco_dir):
        print(f"DosCo directory invalid: {dosco_dir}")
        return 0

    # Hybrid-C primitives (optional import: older s3dgraphy builds
    # without transforms.aux_tracking keep the old behaviour).
    try:
        from s3dgraphy.transforms import (
            record_attribute_override, freeze_aux_value, push_orphan)
        _AUX_AVAILABLE = True
        _INJECTOR_ID = f"DosCo:{dosco_dir}"
    except ImportError:
        _AUX_AVAILABLE = False
        _INJECTOR_ID = None

    # Get graph code for prefix handling
    graph_code = None
    if hasattr(graph_instance, 'attributes') and 'graph_code' in graph_instance.attributes:
        graph_code = graph_instance.attributes['graph_code']

    updated_count = 0

    # Trova tutti i nodi documento/extractor/combiner nel grafo
    relevant_nodes = [
        node for node in graph_instance.nodes
        if hasattr(node, 'node_type') and node.node_type in ['document', 'extractor', 'combiner']
    ]

    print(f"Found {len(relevant_nodes)} relevant nodes to process")

    # Track which DosCo files ended up matched; leftovers become orphans.
    matched_files = set()

    for node in relevant_nodes:
        node_name = node.name

        # CRITICAL FIX: Handle graph code prefix like the original function
        base_name = node_name
        if graph_code and (node_name.startswith(f"{graph_code}.") or node_name.startswith(f"{graph_code}_")):
            if f"{graph_code}." in node_name:
                base_name = node_name.split(f"{graph_code}.", 1)[1]
            elif f"{graph_code}_" in node_name:
                base_name = node_name.split(f"{graph_code}_", 1)[1]

        # Try finding the file with the prefixed name first
        file_path = find_file_in_dosco(dosco_dir, node_name)

        # If not found and we have a different base name (prefix removed), try that
        if not file_path and base_name != node_name:
            file_path = find_file_in_dosco(dosco_dir, base_name)

        if file_path:
            rel_path = os.path.relpath(file_path, dosco_dir)
            matched_files.add(os.path.abspath(file_path))

            # Hybrid-C: record the pre-aux url so volatile save can revert it.
            if _AUX_AVAILABLE:
                record_attribute_override(
                    node, "url",
                    injector_id=_INJECTOR_ID,
                    original_value=getattr(node, "url", None))
            node.url = rel_path
            if _AUX_AVAILABLE:
                freeze_aux_value(node, "url")

            # Crea il nodo link corrispondente (tagged as injected inside
            # update_or_create_link_node when an injector id is provided).
            try:
                update_or_create_link_node(
                    graph_instance, node, rel_path,
                    injector_id=_INJECTOR_ID if _AUX_AVAILABLE else None)
                print(f"Created/updated link node for {node.name}")
            except Exception as e:
                print(f"Warning: Could not create link node for {node.name}: {e}")

            updated_count += 1
            print(f"Updated URL for {node.name}: {rel_path}")
        else:
            print(f"No file found for {node.name} (also tried {base_name})")

    # Orphan files: anything physically in dosco_dir that was not matched
    # to a host node. They do NOT grow the graph (per the Hybrid-C corrected
    # mental model); they land in graph.attributes['aux_orphans'] so the
    # UI can surface them for manual "create host node" actions.
    if _AUX_AVAILABLE:
        try:
            for root, _dirs, files in os.walk(dosco_dir):
                for fname in files:
                    full = os.path.abspath(os.path.join(root, fname))
                    if full in matched_files:
                        continue
                    if fname.startswith("."):
                        continue  # skip .DS_Store etc.
                    rel = os.path.relpath(full, dosco_dir)
                    push_orphan(
                        graph_instance,
                        injector_id=_INJECTOR_ID,
                        key_id=os.path.splitext(fname)[0],
                        payload={"filename": fname, "rel_path": rel},
                    )
        except Exception as e:
            print(f"Warning: orphan file scan failed: {e}")

    print(f"Updated {updated_count} node URLs in graph")
    return updated_count

def inspect_load_dosco_files():
    """
    Scans the DosCo directory and updates URLs for document, extractor, and combiner nodes
    to point to their corresponding files. Handles graph code prefixes appropriately.
    """
    scene = bpy.context.scene
    em_tools = scene.em_tools
    em_settings = bpy.context.window_manager.em_addon_settings
    
    # Check if we have a valid active GraphML file
    if em_tools.active_file_index < 0 or not em_tools.graphml_files:
        print("No active GraphML file to process DosCo files for")
        return 0
        
    graphml = em_tools.graphml_files[em_tools.active_file_index]
    
    # Get the DosCo directory
    dosco_dir = graphml.dosco_dir
    if not dosco_dir:
        print("No DosCo directory specified for this GraphML")
        return 0
        
    # Normalize the path
    dosco_dir = bpy.path.abspath(dosco_dir)
    if not os.path.exists(dosco_dir):
        print(f"DosCo directory doesn't exist: {dosco_dir}")
        return 0
    
    # Get the graph code for prefix handling
    graph_code = graphml.graph_code if hasattr(graphml, 'graph_code') else None
    
    # Get graph instance for creating link nodes
    from s3dgraphy.s3dgmanager import get_graph
    graph_instance = get_graph(graphml.name)

    # Hybrid-C injector id for this DosCo registration — used to tag
    # LinkNodes / has_linked_resource edges created below so a volatile
    # GraphML save can strip them cleanly.
    _dosco_injector_id = f"DosCo:{dosco_dir}"

    # Track updated nodes for reporting
    updated_count = 0
    skipped_web_urls = 0
    not_found_count = 0
    
    # Process documents, extractors, and combiners
    for list_name in ["em_sources_list", "em_extractors_list", "em_combiners_list"]:
        node_list = getattr(scene, list_name)
        list_type = list_name.split('_')[1]  # sources, extractors, combiners
        
        for node in node_list:
            # Skip if it's already a web URL and preserve_web_url is True
            if em_settings.preserve_web_url and is_valid_url(node.url):
                skipped_web_urls += 1
                continue
                
            # Get the node name
            node_name = node.name
            
            # If the node name has the graph code prefix, extract the base name
            base_name = node_name
            if graph_code and (node_name.startswith(f"{graph_code}.") or node_name.startswith(f"{graph_code}_")):
                # Remove the prefix (both dot and underscore separators)
                if f"{graph_code}." in node_name:
                    base_name = node_name.split(f"{graph_code}.", 1)[1]
                elif f"{graph_code}_" in node_name:
                    base_name = node_name.split(f"{graph_code}_", 1)[1]
            
            # Try finding the file with the prefixed name first
            file_path = find_file_in_dosco(dosco_dir, node_name)
            
            # If not found and we have a different base name (prefix removed), try that
            if not file_path and base_name != node_name:
                file_path = find_file_in_dosco(dosco_dir, base_name)
            
            # If file found, update the URL
            if file_path:
                # Get the relative path from the DosCo directory
                rel_path = os.path.relpath(file_path, dosco_dir)
                node.url = rel_path
                
                # ✅ AGGIUNTA: Crea il nodo link corrispondente se abbiamo accesso al grafo
                if graph_instance:
                    # Trova il nodo corrispondente nel grafo
                    graph_node = None
                    for gnode in graph_instance.nodes:
                        if hasattr(gnode, 'name') and gnode.name == node.name:
                            graph_node = gnode
                            break
                    
                    if graph_node:
                        try:
                            update_or_create_link_node(
                                graph_instance, graph_node, rel_path,
                                injector_id=_dosco_injector_id)
                            print(f"Created/updated link node for {node.name}")
                        except Exception as e:
                            print(f"Warning: Could not create link node for {node.name}: {e}")
                
                updated_count += 1
                print(f"Updated URL for {node_name}: {rel_path}")
            else:
                not_found_count += 1
                print(f"No file found for {node_name} or {base_name} in DosCo directory")
    
    print(f"Updated {updated_count} node URLs from DosCo directory")
    print(f"Skipped {skipped_web_urls} web URLs")
    print(f"Could not find {not_found_count} files")
    
    return updated_count

def find_file_in_dosco(dosco_dir, node_name):
    """
    Searches for a file in the DosCo directory that matches the node identifier.
    Makes a distinction between node IDs like "D.01" and "D.01.01".

    Args:
        dosco_dir (str): Path to the DosCo directory
        node_name (str): Name of the node to search for (like "D.01" or "C.05")

    Returns:
        str or None: Full path to the found file, or None if not found
    """
    matches = []

    # Define a more precise pattern matching to distinguish between node IDs
    # For example, D.01 should match "D.01 mia fonte.jpg" but NOT "D.01.01 estrattore.jpg"
    # The key is to NOT accept '.' as a delimiter since it's used for sub-levels
    for root, _, files in os.walk(dosco_dir):
        for file in files:
            # Check if file starts with the exact node name followed by:
            # - a space, underscore, or hyphen (NOT a dot!)
            # This ensures D.01 matches "D.01 file.jpg" but not "D.01.01 file.jpg"
            if file.startswith(node_name):
                # Get the character immediately after the node name
                if len(file) > len(node_name):
                    next_char = file[len(node_name)]
                    # Accept only space, underscore, or hyphen as delimiters
                    # Do NOT accept '.' to avoid matching sub-nodes like D.01.01
                    if next_char in [' ', '_', '-']:
                        matches.append(os.path.join(root, file))
                # If filename is exactly the node name (edge case)
                elif len(file) == len(node_name):
                    matches.append(os.path.join(root, file))
    
    # If we found multiple matches, prioritize by common file types
    if matches:
        # Define priority of file extensions
        priority_extensions = ['.jpg', '.jpeg', '.png', '.pdf', '.doc', '.docx', '.txt', '.svg', '.mp4', '.mov']
        
        # Sort matches by extension priority
        def get_priority(file_path):
            ext = os.path.splitext(file_path)[1].lower()
            try:
                return priority_extensions.index(ext)
            except ValueError:
                return len(priority_extensions)  # Lower priority for unknown extensions
        
        sorted_matches = sorted(matches, key=get_priority)
        return sorted_matches[0]  # Return the highest priority match
    
    # No matches found
    return None

def update_or_create_link_node(graph, source_node, url, preserve_existing=True,
                               injector_id=None):
    """
    Aggiorna un nodo link esistente o ne crea uno nuovo.

    Args:
        graph: Il grafo s3dgraphy
        source_node: Il nodo sorgente (documento, estrattore o combiner)
        url: L'URL o percorso da assegnare
        preserve_existing: Se True, preserva i link esistenti con URL web
        injector_id: Hybrid-C injector id (e.g. "DosCo:/path"). When
            provided, the newly-created LinkNode and its
            ``has_linked_resource`` edge are tagged as injected so a
            volatile GraphML save can strip them cleanly.
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
        edge_created = False
        if not graph.find_edge_by_id(edge_id):
            graph.add_edge(
                edge_id=edge_id,
                edge_source=source_node.node_id,
                edge_target=link_node.node_id,
                edge_type="has_linked_resource"
            )
            edge_created = True

        # Hybrid-C: tag enrichment child + edge as injected so the
        # volatile save can strip them without touching the host.
        if injector_id:
            try:
                from s3dgraphy.transforms import mark_as_injected
                mark_as_injected(link_node, injector_id)
                if edge_created:
                    for e in graph.edges:
                        if e.edge_id == edge_id:
                            mark_as_injected(e, injector_id)
                            break
            except ImportError:
                pass  # aux_tracking unavailable on this s3dgraphy build


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
        
    # ✅ OPTIMIZED: Use object cache for batch lookups
    from .object_cache import get_object_cache
    cache = get_object_cache()

    for item in list_items:
        obj = cache.get_object(item.name)
        if obj:
            item.is_visible = not obj.hide_viewport

def check_and_activate_collection(node_name, context=None, graph=None):
    """
    Verifica se un oggetto è in una collection nascosta e la attiva.
    
    ✅ MODIFICATO: ora gestisce il prefisso internamente
    
    Args:
        node_name: Nome del nodo (senza prefisso)
        context: Blender context (optional)
        graph: Graph instance (optional)
        
    Returns:
        tuple: (bool, list) where bool indicates if any collections were activated,
               and list contains the names of activated collections
    """
    import bpy
    
    # Converti il nome del nodo nel nome del proxy
    proxy_name = node_name_to_proxy_name(node_name, context=context, graph=graph)
    
    activated_collections = []
    # ✅ OPTIMIZED: Use object cache
    from .object_cache import get_object_cache
    obj = get_object_cache().get_object(proxy_name)
    
    if not obj:
        return False, []
    
    # Find all collections containing this object
    for collection in bpy.data.collections:
        if obj.name in collection.objects and collection.hide_viewport:
            collection.hide_viewport = False
            activated_collections.append(collection.name)
            
    return bool(activated_collections), activated_collections

def update_em_list_with_visibility_info(context, graph=None):
    """
    Aggiorna lo stato di visibilità di tutti gli elementi in em_list.
    
    ✅ MODIFICATO: ora usa le funzioni helper
    
    Args:
        context: Blender context
        graph: Graph instance (optional)
    """
    import bpy
    
    scene = context.scene
    strat = scene.em_tools.stratigraphy  # ✅ Nuovo

    # ✅ OPTIMIZED: Use object cache for batch lookups
    from .object_cache import get_object_cache
    cache = get_object_cache()

    for item in strat.units:
        # Converti il nome del nodo nel nome del proxy
        proxy_name = node_name_to_proxy_name(item.name, context=context, graph=graph)
        obj = cache.get_object(proxy_name)

        if obj:
            item.is_visible = not obj.hide_viewport


def generate_blender_object_name(node, context=None):
    """
    Genera un nome univoco per un oggetto Blender basato sul nodo.
    
    ✅ MODIFICATO: ora usa la funzione helper centralizzata
    
    Args:
        node: Il nodo per cui generare il nome
        context: Contesto Blender (opzionale)
        
    Returns:
        str: Il nome univoco per l'oggetto Blender (con prefisso se necessario)
    """
    # Se il nodo ha un grafo associato, usa quello
    graph = None
    if hasattr(node, 'graph'):
        graph = node.graph
    elif hasattr(node, 'attributes') and 'graph_code' in node.attributes:
        # Crea un oggetto fittizio per passare il graph_code
        class TempGraph:
            def __init__(self, code):
                self.attributes = {'graph_code': code}
        graph = TempGraph(node.attributes['graph_code'])
    
    # Usa la funzione helper per aggiungere il prefisso
    return node_name_to_proxy_name(node.name, context=context, graph=graph)

def get_proxy_from_list_item(item, context=None, graph=None):
    """
    Ottiene l'oggetto 3D proxy corrispondente a un elemento di lista.

    ✅ NUOVA FUNZIONE
    ✅ OPTIMIZED: Uses object cache for O(1) lookup

    Args:
        item: L'elemento della lista (con .name attribute)
        context: Contesto Blender (opzionale)
        graph: Istanza del grafo (opzionale)

    Returns:
        bpy.types.Object or None: L'oggetto proxy se trovato, None altrimenti
    """
    from .object_cache import get_object_cache

    # Converti il nome del nodo nel nome del proxy
    proxy_name = node_name_to_proxy_name(item.name, context=context, graph=graph)
    return get_object_cache().get_object(proxy_name)
