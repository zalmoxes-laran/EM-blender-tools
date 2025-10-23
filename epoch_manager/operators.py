"""
Operators for the Epoch Manager
This module contains all the operators needed for interacting with
epochs in the 3D viewport and in the UI lists.
"""

import bpy # type: ignore
from bpy.props import StringProperty, IntProperty, BoolProperty # type: ignore
from bpy.types import Operator # type: ignore

from ..functions import is_graph_available
from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode

class EPOCH_OT_reset_index(Operator):
    bl_idname = "epoch_manager.reset_index"
    bl_label = "Reset Epoch Index"
    bl_description = "Reset the epoch list index to a valid value"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        # Set epoch_list_index to -1 if list is empty, or 0 if it has items
        scene.epoch_list_index = 0 if len(scene.epoch_list) > 0 else -1
        self.report({'INFO'}, "Reset epoch list index")
        return {'FINISHED'}

class EM_toggle_select(Operator):
    """Toggle select proxies in epoch"""
    bl_idname = "epoch_manager.toggle_select"
    bl_label = "Toggle Select"
    bl_description = "Toggle Select"
    bl_options = {'REGISTER', 'UNDO'}

    group_em_idx: IntProperty() # type: ignore

    def execute(self, context):
        from ..operators.addon_prefix_helpers import node_name_to_proxy_name
        from ..functions import is_graph_available
        
        scene = context.scene
        missing_objects = []
        
        # Ottieni il grafo attivo
        graph_exists, graph = is_graph_available(context)
        active_graph = graph if graph_exists else None
        
        if self.group_em_idx < len(scene.epoch_list):
            current_e_manager = scene.epoch_list[self.group_em_idx]
            
            for us in scene.em_list:
                if us.icon == "LINKED":
                    if current_e_manager.name == us.epoch:
                        # ✅ MODIFICATO: Converti il nome con prefisso
                        proxy_name = node_name_to_proxy_name(
                            us.name,
                            context=context,
                            graph=active_graph
                        )
                        
                        # ✅ MODIFICATO: Usa get() per gestire oggetti mancanti
                        object_to_select = bpy.data.objects.get(proxy_name)
                        
                        if object_to_select:
                            try:
                                object_to_select.select_set(True)
                            except RuntimeError as e:
                                if "can't be selected because it is not in View Layer" in str(e):
                                    missing_objects.append(proxy_name)
                                else:
                                    self.report({'ERROR'}, f"Error selecting object '{proxy_name}': {e}")
                                    return {'CANCELLED'}
                        else:
                            print(f"⚠️ Warning: Object '{proxy_name}' not found")
                            missing_objects.append(proxy_name)

        if missing_objects:
            self.report({'WARNING'}, f"The following objects cannot be selected because they are in inactive layers: {', '.join(missing_objects)}")
            self.show_message(", ".join(missing_objects))

        return {'FINISHED'}
    
    def show_message(self, missing_objects_str):
        def draw(self, context):
            self.layout.label(text="Some objects cannot be selected because they are in inactive layers:")
            self.layout.label(text=missing_objects_str)
        bpy.context.window_manager.popup_menu(draw, title="Warning", icon='INFO')

class EM_toggle_visibility(Operator):
    """Toggle visibility"""
    bl_idname = "epoch_manager.toggle_visibility"
    bl_label = "Toggle Visibility"
    bl_description = "Toggle Visibility"
    bl_options = {'REGISTER', 'UNDO'}

    group_em_vis_idx: IntProperty() # type: ignore
    
    def execute(self, context):
        from ..operators.addon_prefix_helpers import node_name_to_proxy_name
        from ..functions import is_graph_available
        
        scene = context.scene
        
        # Ottieni il grafo attivo
        graph_exists, graph = is_graph_available(context)
        active_graph = graph if graph_exists else None
        
        if self.group_em_vis_idx < len(scene.epoch_list):
            current_e_manager = scene.epoch_list[self.group_em_vis_idx]
            
            # Parsing the em list
            for us in scene.em_list:
                # Selecting only in-scene em elements
                if us.icon == "LINKED":
                    # Check if the us is in epoch
                    if current_e_manager.name == us.epoch:
                        # ✅ MODIFICATO: Converti il nome con prefisso
                        proxy_name = node_name_to_proxy_name(
                            us.name,
                            context=context,
                            graph=active_graph
                        )
                        
                        # ✅ MODIFICATO: Usa get() per gestire oggetti mancanti
                        object_to_set_visibility = bpy.data.objects.get(proxy_name)
                        
                        if object_to_set_visibility:
                            object_to_set_visibility.hide_viewport = current_e_manager.use_toggle
                        else:
                            print(f"⚠️ Warning: Object '{proxy_name}' not found")
                            
        current_e_manager.use_toggle = not current_e_manager.use_toggle
        return {'FINISHED'}

class EM_toggle_selectable(Operator):
    """Toggle select"""
    bl_idname = "epoch_manager.toggle_selectable"
    bl_label = "Toggle Selectable"
    bl_description = "Toggle Selectable"
    bl_options = {'REGISTER', 'UNDO'}

    group_em_idx: IntProperty() # type: ignore

    def execute(self, context):
        from ..operators.addon_prefix_helpers import node_name_to_proxy_name
        from ..functions import is_graph_available
        
        scene = context.scene
        
        # Ottieni il grafo attivo
        graph_exists, graph = is_graph_available(context)
        active_graph = graph if graph_exists else None
        
        if self.group_em_idx < len(scene.epoch_list):
            current_e_manager = scene.epoch_list[self.group_em_idx]
            
            for us in scene.em_list:
                if us.icon == "LINKED":
                    if current_e_manager.name == us.epoch:
                        # ✅ MODIFICATO: Converti il nome con prefisso
                        proxy_name = node_name_to_proxy_name(
                            us.name,
                            context=context,
                            graph=active_graph
                        )
                        
                        # ✅ MODIFICATO: Usa get() per gestire oggetti mancanti
                        object_to_set_visibility = bpy.data.objects.get(proxy_name)
                        
                        if object_to_set_visibility:
                            object_to_set_visibility.hide_select = current_e_manager.is_locked
                        else:
                            print(f"⚠️ Warning: Object '{proxy_name}' not found")
                            
        current_e_manager.is_locked = not current_e_manager.is_locked
        return {'FINISHED'}

class EM_select_epoch_rm(Operator):
    """Select RM for a given epoch"""
    bl_idname = "select_rm.given_epoch"
    bl_label = "Select RM for a given epoch"
    bl_description = "Select RM for a given epoch"
    bl_options = {'REGISTER', 'UNDO'}

    rm_epoch: StringProperty() # type: ignore

    def execute(self, context):
        #scene = context.scene
        for ob in bpy.data.objects:
            if len(ob.EM_ep_belong_ob) >= 0:
                for ob_tagged in ob.EM_ep_belong_ob:
                    if ob_tagged.epoch == self.rm_epoch:
                        ob.select_set(True)
        return {'FINISHED'}

class EM_add_remove_epoch_models(Operator):
    """Add and remove models from epochs"""
    bl_idname = "epoch_models.add_remove"
    bl_label = "Add and remove models from epochs"
    bl_description = "Add and remove models from epochs"
    bl_options = {'REGISTER', 'UNDO'}

    rm_epoch: StringProperty() # type: ignore
    rm_add: BoolProperty() # type: ignore

    def execute(self, context):
        scene = context.scene
        selected_objects = context.selected_objects

        for ob in selected_objects:
            if len(ob.EM_ep_belong_ob) >= 0:
                if self.rm_add:
                    if not self.rm_epoch in ob.EM_ep_belong_ob:
                        local_counter = len(ob.EM_ep_belong_ob)
                        ob.EM_ep_belong_ob.add()
                        ob.EM_ep_belong_ob[local_counter].epoch = self.rm_epoch
                else:
                    counter = 0
                    for ob_list in ob.EM_ep_belong_ob:
                        if ob_list.epoch == self.rm_epoch:
                            ob.EM_ep_belong_ob.remove(counter)  
                        counter +=1
            else:
                ob.EM_ep_belong_ob.add()
                ob.EM_ep_belong_ob[0].epoch = self.rm_epoch                   
        return {'FINISHED'}

class EM_change_selected_objects(Operator):
    bl_idname = "epoch_manager.change_selected_objects"
    bl_label = "Change Selected"
    bl_description = "Change Selected"
    bl_options = {'REGISTER', 'UNDO'}

    sg_objects_changer: StringProperty() # type: ignore
    sg_do_with_groups = [
        'COLOR_WIRE', 'DEFAULT_COLOR_WIRE', 'LOCKED', 'UNLOCKED']

    def execute(self, context):
        for obj in context.selected_objects:
            if self.sg_objects_changer == 'BOUND_SHADE':
                obj.display_type = 'BOUNDS'
                obj.show_wire = False
            elif self.sg_objects_changer == 'WIRE_SHADE':
                obj.display_type = 'WIRE'
                obj.show_wire = False
            elif self.sg_objects_changer == 'MATERIAL_SHADE':
                obj.display_type = 'TEXTURED'
                obj.show_wire = False
            elif self.sg_objects_changer == 'SHOW_WIRE':
                obj.display_type = 'TEXTURED'
                obj.show_wire = True
            elif self.sg_objects_changer == 'ONESIDE_SHADE':
                if obj.type == 'MESH':
                    obj.data.show_double_sided = False
            elif self.sg_objects_changer == 'TWOSIDE_SHADE':
                if obj.type == 'MESH':
                    obj.data.show_double_sided = True

        return {'FINISHED'}
    
class EM_UpdateUSListOperator(Operator):
    bl_idname = "epoch_manager.update_us_list"
    bl_label = "Update US List"

    def execute(self, context):
        scene = context.scene

        # Clear existing US list
        scene.selected_epoch_us_list.clear()

        # Verify that there is a selected epoch
        if scene.epoch_list_index < 0 or scene.epoch_list_index >= len(scene.epoch_list):
            self.report({'WARNING'}, "No epoch selected or invalid index")
            return {'CANCELLED'}

        # Get the active graph correctly
        graph_exists, graph_instance = is_graph_available(context)
        
        if not graph_exists:
            self.report({'ERROR'}, "Graph not available")
            return {'CANCELLED'}

        # Get the selected epoch
        selected_epoch = scene.epoch_list[scene.epoch_list_index]

        # Find the epoch node in the graph
        epoch_node = graph_instance.find_node_by_name(selected_epoch.name)

        if epoch_node:
            # Iterate over edges connected to the epoch node
            for edge in graph_instance.edges:
                if edge.edge_source == epoch_node.node_id or edge.edge_target == epoch_node.node_id:
                    # Determine the other node connected by the edge
                    if edge.edge_source == epoch_node.node_id:
                        other_node_id = edge.edge_target
                    else:
                        other_node_id = edge.edge_source

                    # Retrieve the other node
                    other_node = graph_instance.find_node_by_id(other_node_id)

                    # Check if the other node is a StratigraphicNode
                    if other_node and isinstance(other_node, StratigraphicNode):
                        # Determine status based on edge type
                        if edge.edge_type == "has_first_epoch":
                            status = "created"
                        elif edge.edge_type == "survive_in_epoch":
                            status = "re-used"
                        else:
                            continue  # Skip other edge types

                        # Add US element to the list
                        item = scene.selected_epoch_us_list.add()
                        item.name = other_node.name
                        item.description = other_node.description
                        item.status = status
                        item.y_pos = str(other_node.attributes.get('y_pos', 0))
        else:
            self.report({'WARNING'}, f"Epoch node '{selected_epoch.name}' not found in the graph.")

        return {'FINISHED'}

class EPOCH_OT_reset_visibility_ui(Operator):
    """Reset all epoch visibility toggles to ON"""
    bl_idname = "epoch_manager.reset_visibility_ui"
    bl_label = "Reset Visibility UI"
    bl_description = "Reset all epoch visibility toggles to their initial state (ON)"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        
        # Imposta tutti gli use_toggle a True
        for epoch in scene.epoch_list:
            epoch.use_toggle = True
        
        self.report({'INFO'}, f"Reset {len(scene.epoch_list)} epoch visibility toggles")
        return {'FINISHED'}

def register_operators():
    """Register all operator classes."""
    operators = [
        EPOCH_OT_reset_index,
        EM_toggle_select,
        EM_toggle_visibility,
        EM_toggle_selectable,
        EM_select_epoch_rm,
        EM_add_remove_epoch_models,
        EM_change_selected_objects,
        EM_UpdateUSListOperator,
        EPOCH_OT_reset_visibility_ui
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
        EPOCH_OT_reset_visibility_ui,
        EM_UpdateUSListOperator,
        EM_change_selected_objects,
        EM_add_remove_epoch_models,
        EM_select_epoch_rm,
        EM_toggle_selectable,
        EM_toggle_visibility,
        EM_toggle_select,
        EPOCH_OT_reset_index,
    ]
    
    for cls in reversed(operators):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            # Class might already be unregistered
            pass
