"""
Utility functions for Visualization Modules
This module contains utility functions for material management and cleanup.
"""

import bpy
from bpy.types import Operator

# Standardized node prefixes for easy identification and cleanup
NODE_PREFIXES = {
    'EM': 'EM_',           # Extended Matrix nodes
    'M': 'M_',             # Material modification nodes  
    'CLIP': 'CLIP_',       # Clipping related nodes
    'TRANS': 'TRANS_',     # Transparency nodes
    'OVERLAY': 'OVERLAY_', # Color overlay nodes
}

def clean_all_materials():
    """
    Clean all materials by removing visualization module nodes and restoring
    standard Principled BSDF connections.
    
    Returns:
        dict: Summary of cleaning operations performed
    """
    summary = {
        'materials_processed': 0,
        'nodes_removed': 0,
        'connections_restored': 0,
        'errors': []
    }
    
    print("\n=== CLEANING ALL MATERIALS ===")
    
    for material in bpy.data.materials:
        if not material.use_nodes:
            continue
            
        material_modified = False
        nodes_to_remove = []
        
        # Find nodes with our prefixes
        for node in material.node_tree.nodes:
            for prefix_name, prefix in NODE_PREFIXES.items():
                if node.name.startswith(prefix):
                    nodes_to_remove.append(node)
                    material_modified = True
                    print(f"Found {prefix_name} node to remove: {node.name}")
                    break
        
        if material_modified:
            summary['materials_processed'] += 1
            
            # Store original connections before cleanup
            principled_node = None
            output_node = None
            
            for node in material.node_tree.nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    principled_node = node
                elif node.type == 'OUTPUT_MATERIAL':
                    output_node = node
            
            # Remove identified nodes
            for node in nodes_to_remove:
                try:
                    material.node_tree.nodes.remove(node)
                    summary['nodes_removed'] += 1
                except Exception as e:
                    summary['errors'].append(f"Error removing node {node.name}: {str(e)}")
            
            # Restore basic Principled BSDF -> Output connection if needed
            if principled_node and output_node:
                # Check if they're already connected
                connected = False
                for link in material.node_tree.links:
                    if (link.from_node == principled_node and 
                        link.to_node == output_node and
                        link.to_socket.name == 'Surface'):
                        connected = True
                        break
                
                if not connected:
                    try:
                        material.node_tree.links.new(
                            principled_node.outputs['BSDF'], 
                            output_node.inputs['Surface']
                        )
                        summary['connections_restored'] += 1
                        print(f"Restored connection in material: {material.name}")
                    except Exception as e:
                        summary['errors'].append(f"Error restoring connection in {material.name}: {str(e)}")
    
    print(f"Cleaning complete: {summary['materials_processed']} materials processed")
    print(f"Removed {summary['nodes_removed']} nodes, restored {summary['connections_restored']} connections")
    
    if summary['errors']:
        print(f"Errors encountered: {len(summary['errors'])}")
        for error in summary['errors']:
            print(f"  - {error}")
    
    return summary

def get_visualization_materials():
    """
    Get all materials that have been modified by visualization modules.
    
    Returns:
        list: List of materials with visualization nodes
    """
    modified_materials = []
    
    for material in bpy.data.materials:
        if not material.use_nodes:
            continue
            
        for node in material.node_tree.nodes:
            for prefix in NODE_PREFIXES.values():
                if node.name.startswith(prefix):
                    modified_materials.append(material)
                    break
            else:
                continue
            break
    
    return modified_materials

def create_node_with_prefix(node_tree, node_type, prefix_key, base_name):
    """
    Create a node with standardized prefix for easy identification.
    
    Args:
        node_tree: The material node tree
        node_type: Type of node to create
        prefix_key: Key from NODE_PREFIXES dict
        base_name: Base name for the node
        
    Returns:
        Created node
    """
    prefix = NODE_PREFIXES.get(prefix_key, '')
    node_name = f"{prefix}{base_name}"
    
    node = node_tree.nodes.new(node_type)
    node.name = node_name
    node.label = node_name
    
    return node

def backup_material_state(material):
    """
    Create a backup of material's current state before modifications.
    
    Args:
        material: The material to backup
        
    Returns:
        dict: Backup data
    """
    if not material.use_nodes:
        return None
        
    backup = {
        'material_name': material.name,
        'nodes': [],
        'links': []
    }
    
    # Backup node positions and properties
    for node in material.node_tree.nodes:
        node_data = {
            'name': node.name,
            'type': node.type,
            'location': tuple(node.location),
            'inputs': {}
        }
        
        # Backup input values for key node types
        if node.type == 'BSDF_PRINCIPLED':
            for input_socket in node.inputs:
                if not input_socket.is_linked:
                    try:
                        node_data['inputs'][input_socket.name] = input_socket.default_value[:]
                    except:
                        try:
                            node_data['inputs'][input_socket.name] = input_socket.default_value
                        except:
                            pass
        
        backup['nodes'].append(node_data)
    
    # Backup links
    for link in material.node_tree.links:
        link_data = {
            'from_node': link.from_node.name,
            'from_socket': link.from_socket.name,
            'to_node': link.to_node.name,
            'to_socket': link.to_socket.name
        }
        backup['links'].append(link_data)
    
    return backup

def get_em_objects():
    """
    Get objects that are part of the EM system (proxies, etc.).
    
    Returns:
        list: List of EM objects
    """
    em_objects = []
    scene = bpy.context.scene
    
    # Get objects from em_list if available
    if hasattr(scene, 'em_list'):
        for em_item in scene.em_list:
            obj = bpy.data.objects.get(em_item.name)
            if obj and obj.type == 'MESH':
                em_objects.append(obj)
    
    # Also include objects in EM collections
    em_collections = ['EM', 'Proxy', 'RM']
    for collection_name in em_collections:
        collection = bpy.data.collections.get(collection_name)
        if collection:
            for obj in collection.objects:
                if obj.type == 'MESH' and obj not in em_objects:
                    em_objects.append(obj)
    
    return em_objects

class VISUAL_OT_clean_all_materials(Operator):
    """Clean all materials from visualization modifications"""
    bl_idname = "visual.clean_all_materials"
    bl_label = "Clean All Materials"
    bl_description = "Remove all visualization module modifications from materials"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            summary = clean_all_materials()
            
            message = (f"Cleaned {summary['materials_processed']} materials, "
                      f"removed {summary['nodes_removed']} nodes")
            
            if summary['errors']:
                self.report({'WARNING'}, f"{message}. {len(summary['errors'])} errors occurred.")
            else:
                self.report({'INFO'}, message)
                
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error cleaning materials: {str(e)}")
            return {'CANCELLED'}

def register_utils():
    """Register utility operators."""
    bpy.utils.register_class(VISUAL_OT_clean_all_materials)

def unregister_utils():
    """Unregister utility operators."""
    bpy.utils.unregister_class(VISUAL_OT_clean_all_materials)
