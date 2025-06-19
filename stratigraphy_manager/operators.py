"""
Operators for the Stratigraphy Manager
This module contains all the operators needed for interacting with
stratigraphic units in the 3D viewport and in the UI lists.
"""

import bpy
from bpy.props import StringProperty, IntProperty, BoolProperty
from bpy.types import Operator

from ..functions import check_material_presence, em_setup_mat_cycles, update_icons
from ..functions import select_3D_obj, select_list_element_from_obj_proxy

class EM_strat_toggle_visibility(Operator):
    bl_idname = "em.strat_toggle_visibility"
    bl_label = "Toggle Stratigraphy Visibility"
    bl_description = "Toggle visibility of the selected proxy in the scene"
    bl_options = {"REGISTER", "UNDO"}
    
    index: IntProperty(default=-1)  # -1 means use the active index
    
    def execute(self, context):
        scene = context.scene
        index = self.index if self.index >= 0 else scene.em_list_index
        
        if index >= 0 and index < len(scene.em_list):
            item = scene.em_list[index]
            obj = bpy.data.objects.get(item.name)
            
            if obj:
                # Toggle visibility
                obj.hide_viewport = not obj.hide_viewport
                item.is_visible = not obj.hide_viewport
                
                # If the object is hidden in a collection, activate it
                if not obj.hide_viewport:
                    self.activate_object_collections(obj, context)
                    
                return {'FINISHED'}
            else:
                self.report({'WARNING'}, f"Object '{item.name}' not found in scene")
        
        return {'CANCELLED'}
    
    def is_in_hidden_collection(self, obj, context):
        """Check if the object is in a hidden collection."""
        for collection in bpy.data.collections:
            if obj.name in collection.objects and collection.hide_viewport:
                return True
        return False
    
    def activate_object_collections(self, obj, context):
        """Activate all collections containing the object."""
        activated_collections = []
        
        for collection in bpy.data.collections:
            if obj.name in collection.objects and collection.hide_viewport:
                collection.hide_viewport = False
                activated_collections.append(collection.name)
        
        if activated_collections:
            self.show_activation_message(", ".join(activated_collections))
    
    def show_activation_message(self, collection_names):
        def draw(self, context):
            self.layout.label(text="The following collections have been activated:")
            self.layout.label(text=collection_names)
        
        bpy.context.window_manager.popup_menu(draw, title="Collections Activated", icon='INFO')

class EM_strat_sync_visibility(Operator):
    bl_idname = "em.strat_sync_visibility"
    bl_label = "Sync Stratigraphy Visibility"
    bl_description = "Synchronize visibility of proxies and RM objects with the current selections"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        
        # Handle proxy visibility sync
        if scene.sync_list_visibility:
            self.sync_proxy_visibility(context)
            
        # Handle RM visibility sync
        if scene.sync_rm_visibility:
            self.sync_rm_visibility(context)
            
        return {'FINISHED'}
    
    def sync_proxy_visibility(self, context):
        """Synchronize proxy object visibility with the em_list"""
        scene = context.scene
        
        # Create a set of proxy names that should be visible
        visible_proxy_names = {item.name for item in scene.em_list}
        
        # Find all proxy objects - need to include ALL mesh objects from proxy collections
        # plus any objects with matching names
        proxy_objects = []
        proxy_objects_set = set()  # To avoid duplicates
        activated_collections = []
        
        # Strategy: Look for collections that contain objects matching our em_list names
        # and treat those entire collections as "proxy collections"
        proxy_collections = set()
        
        # First pass: identify which collections contain objects from em_list
        all_em_list_names = {item.name for item in scene.em_list}
        for collection in bpy.data.collections:
            for obj in collection.objects:
                if obj.name in all_em_list_names and obj.type == 'MESH':
                    proxy_collections.add(collection)
                    break
        
        # Add the original "Proxy" collection if it exists (for backward compatibility)
        proxy_collection = bpy.data.collections.get('Proxy')
        if proxy_collection:
            proxy_collections.add(proxy_collection)
        
        # Second pass: add ALL mesh objects from identified proxy collections
        for collection in proxy_collections:
            contains_visible_proxy = False
            
            for obj in collection.objects:
                if obj.type == 'MESH' and obj not in proxy_objects_set:
                    proxy_objects.append(obj)
                    proxy_objects_set.add(obj)
                    
                    # Check if this collection should be activated
                    if obj.name in visible_proxy_names:
                        contains_visible_proxy = True
            
            # Activate collection if it contains visible proxies and is currently hidden
            if contains_visible_proxy and collection.hide_viewport:
                collection.hide_viewport = False
                activated_collections.append(collection.name)
        
        # Also add any objects with matching names that might not be in proxy collections
        for obj_name in all_em_list_names:
            obj = bpy.data.objects.get(obj_name)
            if obj and obj.type == 'MESH' and obj not in proxy_objects_set:
                proxy_objects.append(obj)
                proxy_objects_set.add(obj)
        
        # Hide/Show proxy objects based on the list
        hidden_count = 0
        shown_count = 0
        
        for obj in proxy_objects:
            if obj.name in visible_proxy_names:
                if obj.hide_viewport:
                    obj.hide_viewport = False
                    shown_count += 1
            else:
                if not obj.hide_viewport:
                    obj.hide_viewport = True
                    hidden_count += 1
        
        # Update visibility icons in the em_list
        for item in scene.em_list:
            obj = bpy.data.objects.get(item.name)
            if obj:
                item.is_visible = not obj.hide_viewport
        
        # Report results
        message = f"Proxy visibility synchronized: {shown_count} shown, {hidden_count} hidden"
        if activated_collections:
            message += f". Activated collections: {', '.join(activated_collections)}"
        
        self.report({'INFO'}, message)
    def sync_rm_visibility(self, context):
        """Synchronize RM object visibility based on active epoch"""
        scene = context.scene
        
        # Check if we have an active epoch
        if scene.epoch_list_index < 0 or scene.epoch_list_index >= len(scene.epoch_list):
            self.report({'WARNING'}, "No active epoch selected")
            return
            
        active_epoch = scene.epoch_list[scene.epoch_list_index]
        active_epoch_name = active_epoch.name
        
        # Get RM objects from the RM list
        rm_objects = []
        
        # Find objects in the scene that are registered as RM in the rm_list
        for item in scene.rm_list:
            obj = bpy.data.objects.get(item.name)
            if obj and obj.type == 'MESH':
                rm_objects.append((obj, item))
        
        # Also check for objects in the RM collection
        rm_collection = bpy.data.collections.get('RM')
        if rm_collection:
            for obj in rm_collection.objects:
                if obj.type == 'MESH' and not any(o[0] == obj for o in rm_objects):
                    # Try to find matching RM item
                    rm_item = None
                    for item in scene.rm_list:
                        if item.name == obj.name:
                            rm_item = item
                            break
                    
                    if rm_item:
                        rm_objects.append((obj, rm_item))
        
        # Hide/Show RM objects based on epoch association
        hidden_count = 0
        shown_count = 0
        
        for obj, rm_item in rm_objects:
            # Check if this RM belongs to the active epoch
            belongs_to_active_epoch = False
            
            # Check the first epoch and any additional epochs
            if rm_item.first_epoch == active_epoch_name:
                belongs_to_active_epoch = True
            else:
                # Check additional epochs
                for epoch_item in rm_item.epochs:
                    if epoch_item.name == active_epoch_name:
                        belongs_to_active_epoch = True
                        break
            
            # Handle visibility
            if belongs_to_active_epoch:
                if obj.hide_viewport:
                    obj.hide_viewport = False
                    shown_count += 1
            else:
                if not obj.hide_viewport:
                    obj.hide_viewport = True
                    hidden_count += 1
        
        self.report({'INFO'}, f"RM visibility synchronized: {shown_count} shown, {hidden_count} hidden for epoch '{active_epoch_name}'")

class EM_strat_activate_collections(Operator):
    bl_idname = "em.strat_activate_collections"
    bl_label = "Activate Stratigraphy Collections"
    bl_description = "Activate all collections containing proxies in the current list"
    bl_options = {"REGISTER", "UNDO"}
    
    def execute(self, context):
        scene = context.scene
        
        # Create a set of names that are in the list
        proxy_names = {item.name for item in scene.em_list}
        activated_collections = []
        
        # Process all collections
        for collection in bpy.data.collections:
            contains_proxy = False
            
            for obj in collection.objects:
                if obj.name in proxy_names:
                    contains_proxy = True
                    break
            
            if contains_proxy and collection.hide_viewport:
                collection.hide_viewport = False
                activated_collections.append(collection.name)
        
        if activated_collections:
            self.show_activation_message(", ".join(activated_collections))
            self.report({'INFO'}, f"Activated {len(activated_collections)} collections")
        else:
            self.report({'INFO'}, "No hidden collections with proxies found")
        
        return {'FINISHED'}
    
    def show_activation_message(self, collection_names):
        def draw(self, context):
            self.layout.label(text="The following collections have been activated:")
            self.layout.label(text=collection_names)
        
        bpy.context.window_manager.popup_menu(draw, title="Collections Activated", icon='INFO')

class EM_listitem_OT_to3D(Operator):
    bl_idname = "listitem.toobj"
    bl_label = "Use element's name from the list above to rename selected 3D object"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty()

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None:
            pass
        else:
            return (obj.type in ['MESH'])

    def execute(self, context):
        scene = context.scene
        item_name_picker_cmd = "scene."+self.list_type+"[scene."+self.list_type+"_index]"
        item = eval(item_name_picker_cmd)
        context.active_object.name = item.name
        update_icons(context, self.list_type)
        if self.list_type == "em_list":
            if scene.proxy_display_mode == "EM":
                bpy.ops.emset.emmaterial()
            else:
                bpy.ops.emset.epochmaterial()
        return {'FINISHED'}

class EM_update_icon_list(Operator):
    bl_idname = "list_icon.update"
    bl_label = "Update only the icons"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty()

    def execute(self, context):
        if self.list_type == "all":
            lists = ["em_list","epoch_list","em_sources_list","em_properties_list","em_extractors_list","em_combiners_list","em_v_sources_list","em_v_properties_list","em_v_extractors_list","em_v_combiners_list"]
            for single_list in lists:
                update_icons(context, single_list)
        else:
            update_icons(context, self.list_type)
        return {'FINISHED'}

class EM_select_list_item(Operator):
    bl_idname = "select.listitem"
    bl_label = "Select element in the list above from a 3D proxy"
    bl_description = "Select the row in the stratigraphy manager corresponding to the active proxy in the scene"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty()

    def execute(self, context):
        scene = context.scene
        obj = context.object
        select_list_element_from_obj_proxy(obj, self.list_type)
        return {'FINISHED'}

class EM_select_from_list_item(Operator):
    bl_idname = "select.fromlistitem"
    bl_label = "Select 3D obj from the list above"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty()
    specific_item: StringProperty(default="")  # Add this line

    def execute(self, context):
        scene = context.scene
        if self.specific_item:
            # Use the specific item name passed from the UI
            select_3D_obj(self.specific_item)
        else:
            # Fallback to the old behavior using the active index
            list_type_cmd = "scene."+self.list_type+"[scene."+self.list_type+"_index]"
            list_item = eval(list_type_cmd)
            select_3D_obj(list_item.name)
        return {'FINISHED'}

class EM_not_in_matrix(Operator):
    bl_idname = "notinthematrix.material"
    bl_label = "Helper for proxies visualization"
    bl_description = "Apply a custom material to proxies not yet present in the matrix"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        EM_mat_list = ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD']
        EM_mat_name = "mat_NotInTheMatrix"
        R = 1.0
        G = 0.0
        B = 1.0
        if not check_material_presence(EM_mat_name):
            newmat = bpy.data.materials.new(EM_mat_name)
            em_setup_mat_cycles(EM_mat_name,R,G,B)

        for ob in bpy.data.objects:
            if ob.type == 'MESH':
                if ob.data.materials:
                    if ob.material_slots[0].material.name in EM_mat_list or ob.material_slots[0].material.name.startswith('ep_'):
                        matrix_mat = True
                    else:
                        matrix_mat = False
                    not_in_matrix = True
                    for item in context.scene.em_list:
                        if item.name == ob.name:
                            not_in_matrix = False
                    if matrix_mat and not_in_matrix:
                        ob.data.materials.clear()
                        notinmatrix_mat = bpy.data.materials[EM_mat_name]
                        ob.data.materials.append(notinmatrix_mat)

        return {'FINISHED'}

class EM_set_EM_materials(Operator):
    bl_idname = "emset.emmaterial"
    bl_label = "Change proxy materials EM"
    bl_description = "Change proxy materials using EM standard palette"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        context.scene.proxy_display_mode = "EM"
        update_icons(context, "em_list")
        bpy.ops.set_materials.using_em_list()
        return {'FINISHED'}

class EM_set_epoch_materials(Operator):
    bl_idname = "emset.epochmaterial"
    bl_label = "Change proxy Epochs"
    bl_description = "Change proxy materials using Epochs"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        context.scene.proxy_display_mode = "Epochs"
        update_icons(context, "em_list")
        bpy.ops.set_materials.using_epoch_list()
        return {'FINISHED'}

class SET_materials_using_em_list(Operator):
    bl_idname = "set_materials.using_em_list"
    bl_label = "Set Materials Using EM List"
    bl_description = "Set materials based on EM node types"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ..functions import consolidate_EM_material_presence, em_setup_mat_cycles
        
        # Prepare EM materials
        overwrite_mats = True
        consolidate_EM_material_presence(overwrite_mats)
        
        # Apply materials based on node types
        em_list_lenght = len(context.scene.em_list)
        counter = 0
        while counter < em_list_lenght:
            current_ob_em_list = context.scene.em_list[counter]
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
        
        return {'FINISHED'}

class SET_materials_using_epoch_list(Operator):
    bl_idname = "set_materials.using_epoch_list"
    bl_label = "Set Materials Using Epoch List"
    bl_description = "Set materials based on epoch assignments"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ..functions import (
            check_material_presence, 
            em_setup_mat_cycles, 
            consolidate_epoch_material_presence
        )
        
        scene = context.scene 
        mat_prefix = "ep_"
        
        # Create/update epoch materials
        for epoch in scene.epoch_list:
            matname = mat_prefix + epoch.name
            mat = consolidate_epoch_material_presence(matname)
            R = epoch.epoch_RGB_color[0]
            G = epoch.epoch_RGB_color[1]
            B = epoch.epoch_RGB_color[2]
            em_setup_mat_cycles(matname, R, G, B)
            
            # Apply materials to objects in this epoch
            for em_element in scene.em_list:
                if em_element.icon == "RESTRICT_INSTANCED_OFF":
                    if em_element.epoch == epoch.name:
                        obj = bpy.data.objects[em_element.name]
                        obj.data.materials.clear()
                        obj.data.materials.append(mat)
        
        return {'FINISHED'}


class EM_debug_filters(Operator):
    bl_idname = "em.debug_filters"
    bl_label = "Debug Filters"
    bl_description = "Print debug information about the current graph and connections"
    bl_options = {"REGISTER", "UNDO"}
    
    debug_mode: bpy.props.EnumProperty(
        items=[
            ('FULL', "Full Graph", "Debug the entire graph structure"),
            ('CURRENT', "Current Node", "Debug only the currently selected node")
        ],
        default='CURRENT',
        name="Debug Mode"
    )
    
    max_depth: bpy.props.IntProperty(
        name="Max Recursion Depth",
        description="Maximum recursion depth for graph traversal",
        default=5,
        min=1,
        max=20
    )
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "debug_mode")
        layout.prop(self, "max_depth")
    
    def execute(self, context):
        scene = context.scene
        
        # Get current graph
        from ..functions import is_graph_available as check_graph
        graph_exists, graph = check_graph(context)
        
        if not graph_exists:
            self.report({'WARNING'}, "No active graph found. Please load a GraphML file first.")
            return {'CANCELLED'}
        
        try:
            # Import debug_graph_structure
            from ..s3Dgraphy.utils.utils import debug_graph_structure
            
            if self.debug_mode == 'FULL':
                # Debug full graph
                debug_graph_structure(graph, max_depth=self.max_depth)
                self.report({'INFO'}, "Full graph debug information printed to console")
            else:
                # Debug current node
                if scene.em_list_index >= 0 and len(scene.em_list) > 0:
                    node_id = scene.em_list[scene.em_list_index].id_node
                    debug_graph_structure(graph, node_id, max_depth=self.max_depth)
                    self.report({'INFO'}, f"Node debug information printed to console for {scene.em_list[scene.em_list_index].name}")
                else:
                    # Fallback to full graph if no node is selected
                    self.report({'WARNING'}, "No node selected, showing full graph information")
                    debug_graph_structure(graph, max_depth=self.max_depth)
            
            return {'FINISHED'}
            
        except RecursionError as e:
            self.report({'ERROR'}, f"Recursion error in debug function. Try reducing the max depth: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error during debug: {str(e)}")
            import traceback
            traceback.print_exc()  
            return {'CANCELLED'}


def register_operators():
    """Register all operator classes."""
    operators = [
        EM_strat_toggle_visibility,
        EM_strat_sync_visibility,
        EM_strat_activate_collections,
        EM_listitem_OT_to3D,
        EM_update_icon_list,
        EM_select_list_item,
        EM_select_from_list_item,
        EM_not_in_matrix,
        EM_set_EM_materials,
        EM_set_epoch_materials,
        SET_materials_using_em_list,
        SET_materials_using_epoch_list,
        EM_debug_filters
    ]
    
    for cls in operators:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Class might already be registered
            pass

def unregister_operators():
    """Unregister all operator classes."""
    operators = [
        EM_debug_filters,
        SET_materials_using_epoch_list,
        SET_materials_using_em_list,
        EM_set_epoch_materials,
        EM_set_EM_materials,
        EM_not_in_matrix,
        EM_select_from_list_item,
        EM_select_list_item,
        EM_update_icon_list,
        EM_listitem_OT_to3D,
        EM_strat_activate_collections,
        EM_strat_sync_visibility,
        EM_strat_toggle_visibility,
    ]
    
    for cls in reversed(operators):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            # Class might already be unregistered
            pass