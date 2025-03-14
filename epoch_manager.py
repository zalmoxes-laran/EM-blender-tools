import bpy # type: ignore
import string

from bpy.props import EnumProperty, StringProperty, BoolProperty, IntProperty, CollectionProperty, BoolVectorProperty, PointerProperty # type: ignore
import bpy.props as prop # type: ignore

from bpy.types import Panel, UIList # type: ignore

from .functions import *

from .s3Dgraphy.nodes.stratigraphic_node import StratigraphicNode  # Import diretto

from .s3Dgraphy import get_graph


class EM_UL_named_epoch_managers(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        epoch_list = item
        icons_style = 'OUTLINER'
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Mostra solo il nome dell'epoca e il colore, rimuovendo le date
            layout.prop(epoch_list, "name", text="", emboss=False)
            
            # select operator
            icon = 'RESTRICT_SELECT_ON' if epoch_list.is_selected else 'RESTRICT_SELECT_OFF'
            if icons_style == 'OUTLINER':
                icon = 'VIEWZOOM' if epoch_list.use_toggle else 'VIEWZOOM'
            layout = layout.split(factor=0.1, align=True)
            layout.prop(epoch_list, "epoch_RGB_color", text="", emboss=True, icon_value=0)
            op = layout.operator(
                "epoch_manager.toggle_select", text="", emboss=False, icon=icon)

            op.group_em_idx = index

            # lock operator
            icon = 'LOCKED' if epoch_list.is_locked else 'UNLOCKED'
            if icons_style == 'OUTLINER':
                icon = 'RESTRICT_SELECT_OFF' if epoch_list.is_locked else 'RESTRICT_SELECT_ON'
            op = layout.operator("epoch_manager.toggle_selectable", text="", emboss=False, icon=icon)
            op.group_em_idx = index

            # view operator
            icon = 'RESTRICT_VIEW_OFF' if epoch_list.use_toggle else 'RESTRICT_VIEW_ON'
            op = layout.operator(
                "epoch_manager.toggle_visibility", text="", emboss=False, icon=icon)
            op.group_em_vis_idx = index

            # view reconstruction
            icon = 'MESH_CUBE' if not epoch_list.reconstruction_on else 'SNAP_VOLUME'
            op = layout.operator(
                "epoch_manager.toggle_reconstruction", text="", emboss=False, icon=icon)
            op.group_em_vis_idx = index

            # soloing operator
            icon = 'RADIOBUT_ON' if epoch_list.epoch_soloing else 'RADIOBUT_OFF'
            op = layout.operator(
                "epoch_manager.toggle_soloing", text="", emboss=False, icon=icon)
            op.group_em_idx = index

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'

#Periods Manager
class EM_BasePanel:
    bl_label = "Epochs Manager"
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
        row = layout.row()
        ob = context.object

        if len(scene.em_list) > 0:
            row.template_list(
                "EM_UL_named_epoch_managers", "", scene, "epoch_list", scene, "epoch_list_index")
            
            # Aggiungiamo il sottopannello con i dettagli dell'epoca selezionata
            if scene.epoch_list_index >= 0 and len(scene.epoch_list) > 0:
                epoch = scene.epoch_list[scene.epoch_list_index]
                
                # Box collassabile per i dettagli dell'epoca
                box = layout.box()
                row = box.row()
                row.prop(scene, "show_epoch_details", 
                        icon='TRIA_DOWN' if scene.show_epoch_details else 'TRIA_RIGHT',
                        emboss=False, text="Epoch details")
                
                # Mostra i dettagli solo se il pannello è espanso
                if scene.show_epoch_details:
                    col = box.column(align=True)
                    # Date di inizio e fine
                    row = col.row()
                    row.label(text="Years time-span:")
                    row = col.row(align=True)
                    row.prop(epoch, "start_time", text="Start")
                    row.prop(epoch, "end_time", text="End")
                    
                    # Description - to be implemented in the future
                    #if epoch.description:
                    #    row = col.row()
                    #    row.label(text="Descrizione:")
                    #    row = col.row()
                    #    row.label(text=epoch.description)
        
        else:
            row.label(text="No epochs here :-(")
            
        # Aggiungiamo sezione RM (Representation Models) se necessario
        '''
        if scene.epoch_list_index >= 0 and len(scene.epoch_list) > 0:
            box = layout.box()
            row = box.row()
            row.label(text="Representation Models (RM):")
            op = row.operator("epoch_models.add_remove", text="", emboss=False, icon='ADD')
            op.rm_epoch = scene.epoch_list[scene.epoch_list_index].name
            op.rm_add = True
            op = row.operator("epoch_models.add_remove", text="", emboss=False, icon='REMOVE')
            op.rm_epoch = scene.epoch_list[scene.epoch_list_index].name
            op.rm_add = False
            op = row.operator("select_rm.given_epoch", text="", emboss=False, icon='SELECT_SET')
            op.rm_epoch = scene.epoch_list[scene.epoch_list_index].name
        '''

class VIEW3D_PT_BasePanel(Panel, EM_BasePanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_BasePanel"
    bl_context = "objectmode"

########################

class EM_UL_List(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.03, align = True)
        layout.label(text = "", icon = item.icon_db)
        layout = layout.split(factor =0.30, align = True)
        layout.label(text = item.name, icon = item.icon)
        layout.label(text = item.description, icon='NONE', icon_value=0)
        #layout.label(text = str(item.y_pos), icon='NONE', icon_value=0)

########################

class EM_toggle_select(bpy.types.Operator):
    """Toggle select proxies in epoch"""
    bl_idname = "epoch_manager.toggle_select"
    bl_label = "Toggle Select"
    bl_description = "Toggle Select"
    bl_options = {'REGISTER', 'UNDO'}

    group_em_idx : IntProperty() # type: ignore

    def execute(self, context):
        scene = context.scene
        missing_objects = []
        if self.group_em_idx < len(scene.epoch_list):
            # check_same_ids()  # check scene ids
            current_e_manager = scene.epoch_list[self.group_em_idx]
            for us in scene.em_list:
                if us.icon == "RESTRICT_INSTANCED_OFF":
                    #print(f"La US {us.name} appartiene all'epoca {us.epoch}")
                    if current_e_manager.name == us.epoch:
                        object_to_select = bpy.data.objects[us.name]
                        try:
                            object_to_select.select_set(True)
                        except RuntimeError as e:
                            if "can't be selected because it is not in View Layer" in str(e):
                                missing_objects.append(object_to_select.name)
                            else:
                                self.report({'ERROR'}, f"Error selecting object '{object_to_select.name}': {e}")
                                return {'CANCELLED'}

        if missing_objects:
            self.report({'WARNING'}, f"The following objects cannot be selected because they are in inactive layers: {', '.join(missing_objects)}")
            self.show_message(", ".join(missing_objects))

        return {'FINISHED'}
    
    def show_message(self, missing_objects_str):
        def draw(self, context):
            self.layout.label(text="Some objects cannot be selected because they are in inactive layers:")
            self.layout.label(text=missing_objects_str)
        bpy.context.window_manager.popup_menu(draw, title="Warning", icon='INFO')

class EM_toggle_reconstruction(bpy.types.Operator):
    """Draw a line with the mouse"""
    bl_idname = "epoch_manager.toggle_reconstruction"
    bl_label = "Toggle Reconstruction"
    bl_description = "Toggle Reconstruction"
    bl_options = {'REGISTER', 'UNDO'}

    group_em_vis_idx : IntProperty() # type: ignore
    soloing_epoch: StringProperty() # type: ignore


    def execute(self, context):
        scene = context.scene
        if self.group_em_vis_idx < len(scene.epoch_list):
            # check_same_ids()  # check scene ids
            current_e_manager = scene.epoch_list[self.group_em_vis_idx]
            #parsing the em list
            for us in scene.em_list:
                #selecting only in-scene em elements
                if us.icon == "RESTRICT_INSTANCED_OFF":
                    # check if the us is in epoch
                    if current_e_manager.name == us.epoch:
                        if is_reconstruction_us(us):

                            # identify object to be turned on/off
                            object_to_set_visibility = bpy.data.objects[us.name]
                            # before to turn on/off elements in scene, check if we are in soloing mode
                            if scene.em_settings.soloing_mode == True:
                                found_reused = False
                                # parsing the re_used element list
                                for em_reused in scene.em_reused:
                                    if found_reused is False:
                                        if em_reused.em_element == us.name and em_reused.epoch == self.soloing_epoch:
                                            object_to_set_visibility.hide_viewport = False
                                            found_reused = True
                                        else:
                                            object_to_set_visibility.hide_viewport = current_e_manager.reconstruction_on
                            else:
                                object_to_set_visibility.hide_viewport = current_e_manager.reconstruction_on
        current_e_manager.reconstruction_on = not current_e_manager.reconstruction_on
        return {'FINISHED'}

class EM_toggle_visibility(bpy.types.Operator):
    """Toggle visibility"""
    bl_idname = "epoch_manager.toggle_visibility"
    bl_label = "Toggle Visibility"
    bl_description = "Toggle Visibility"
    bl_options = {'REGISTER', 'UNDO'}

    group_em_vis_idx : IntProperty() # type: ignore
    soloing_epoch: StringProperty() # type: ignore
    
    def execute(self, context):
        scene = context.scene
        if self.group_em_vis_idx < len(scene.epoch_list):
            # check_same_ids()  # check scene ids
            current_e_manager = scene.epoch_list[self.group_em_vis_idx]
            #parsing the em list
            for us in scene.em_list:
                #selecting only in-scene em elements
                if us.icon == "RESTRICT_INSTANCED_OFF":
                    # check if the us is in epoch
                    if current_e_manager.name == us.epoch:
                        # identify object to be turned on/off
                        object_to_set_visibility = bpy.data.objects[us.name]
                        # before to turn on/off elements in scene, check if we are in soloing mode
                        if scene.em_settings.soloing_mode == True:
                            found_reused = False
                            # parsing the re_used element list
                            for em_reused in scene.em_reused:
                                if found_reused is False:
                                    if em_reused.em_element == us.name and em_reused.epoch == self.soloing_epoch:
                                        object_to_set_visibility.hide_viewport = False
                                        found_reused = True
                                    else:
                                        object_to_set_visibility.hide_viewport = current_e_manager.use_toggle
                        else:
                            object_to_set_visibility.hide_viewport = current_e_manager.use_toggle
        current_e_manager.use_toggle = not current_e_manager.use_toggle
        return {'FINISHED'}

class EM_toggle_selectable(bpy.types.Operator):
    """Toggle select"""
    bl_idname = "epoch_manager.toggle_selectable"
    bl_label = "Toggle Selectable"
    bl_description = "Toggle Selectable"
    bl_options = {'REGISTER', 'UNDO'}

    group_em_idx : IntProperty() # type: ignore

    def execute(self, context):
        scene = context.scene
        if self.group_em_idx < len(scene.epoch_list):
            # check_same_ids()  # check scene ids
            current_e_manager = scene.epoch_list[self.group_em_idx]
            for us in scene.em_list:
                if us.icon == "RESTRICT_INSTANCED_OFF":
                    if current_e_manager.name == us.epoch:
                        object_to_set_visibility = bpy.data.objects[us.name]
                        object_to_set_visibility.hide_select = current_e_manager.is_locked
        current_e_manager.is_locked = not current_e_manager.is_locked
        return {'FINISHED'}

class EM_toggle_soloing(bpy.types.Operator):
    """Toggle soloing"""
    bl_idname = "epoch_manager.toggle_soloing"
    bl_label = "Toggle Soloing"
    bl_description = "Toggle epoch Soloing"
    bl_options = {'REGISTER', 'UNDO'}

    group_em_idx : IntProperty() # type: ignore

    def execute(self, context):
        scene = context.scene
        ep_idx = 0
        # check if selected row is consistent
        if self.group_em_idx < len(scene.epoch_list):
            #get current row in epoch list
            current_e_manager = scene.epoch_list[self.group_em_idx]
            # invert soloing icon for clicked row
            current_e_manager.epoch_soloing = not current_e_manager.epoch_soloing
            # set general soloing mode from current row
            scene.em_settings.soloing_mode = current_e_manager.epoch_soloing
            # parsing epoch list to update icons and run routines
            for ep_idx in range(len(scene.epoch_list)):
                # in case of the row to be "soloed"
                if ep_idx == self.group_em_idx:
                    # force toggle visibility to soloing row
                    scene.epoch_list[ep_idx].use_toggle = False
                    bpy.ops.epoch_manager.toggle_visibility("INVOKE_DEFAULT", group_em_vis_idx = ep_idx, soloing_epoch = current_e_manager.name)
                # in case of other rows..
                else:
                    # .. force turn off soloing
                    scene.epoch_list[ep_idx].epoch_soloing = False
                    # .. check if they are turned off
                    if scene.epoch_list[ep_idx].use_toggle == False:
                        # .. and in that case check if we are no more in soloing mode..
                        if scene.em_settings.soloing_mode is False:
                            # .. and turn them all back visible
                            bpy.ops.epoch_manager.toggle_visibility("INVOKE_DEFAULT", group_em_vis_idx = ep_idx, soloing_epoch = current_e_manager.name)
                    else:
                        bpy.ops.epoch_manager.toggle_visibility("INVOKE_DEFAULT", group_em_vis_idx = ep_idx, soloing_epoch = current_e_manager.name)
                            
        return {'FINISHED'}

class EM_select_epoch_rm(bpy.types.Operator):
    """Select RM for a given epoch"""
    bl_idname = "select_rm.given_epoch"
    bl_label = "Select RM for a given epoch"
    bl_description = "Select RM for a given epoch"
    bl_options = {'REGISTER', 'UNDO'}

    rm_epoch : StringProperty() # type: ignore

    def execute(self, context):
        #scene = context.scene
        for ob in bpy.data.objects:
            if len(ob.EM_ep_belong_ob) >= 0:
                for ob_tagged in ob.EM_ep_belong_ob:
                    if ob_tagged.epoch == self.rm_epoch:
                        ob.select_set(True)
        return {'FINISHED'}

class EM_add_remove_epoch_models(bpy.types.Operator):
    """Add and remove models from epochs"""
    bl_idname = "epoch_models.add_remove"
    bl_label = "Add and remove models from epochs"
    bl_description = "Add and remove models from epochs"
    bl_options = {'REGISTER', 'UNDO'}

    rm_epoch : StringProperty() # type: ignore
    rm_add : BoolProperty() # type: ignore

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

class EM_set_EM_materials(bpy.types.Operator):
    bl_idname = "emset.emmaterial"
    bl_label = "Change proxy materials EM"
    bl_description = "Change proxy materials using EM standard palette"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        context.scene.proxy_display_mode = "EM"
        update_icons(context,"em_list")
        set_materials_using_EM_list(context)
        return {'FINISHED'}

class EM_set_epoch_materials(bpy.types.Operator):
    bl_idname = "emset.epochmaterial"
    bl_label = "Change proxy periods"
    bl_description = "Change proxy materials using periods"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        context.scene.proxy_display_mode = "Periods"
        update_icons(context,"em_list")
        set_materials_using_epoch_list(context)
        return {'FINISHED'}

class EM_change_selected_objects(bpy.types.Operator):
    bl_idname = "epoch_manager.change_selected_objects"
    bl_label = "Change Selected"
    bl_description = "Change Selected"
    bl_options = {'REGISTER', 'UNDO'}

    sg_objects_changer : EnumProperty(
        items=(('BOUND_SHADE', 'BOUND_SHADE', ''),
               ('WIRE_SHADE', 'WIRE_SHADE', ''),
               ('MATERIAL_SHADE', 'MATERIAL_SHADE', ''),
               ('SHOW_WIRE', 'SHOW_WIRE', ''),
               ('EM_COLOURS', 'EM_COLOURS', ''),
               ('ONESIDE_SHADE', 'ONESIDE_SHADE', ''),
               ('TWOSIDE_SHADE', 'TWOSIDE_SHADE', '')
               ),
        default = 'MATERIAL_SHADE'
    ) # type: ignore
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
    
class EM_UpdateUSListOperator(bpy.types.Operator):
    bl_idname = "epoch_manager.update_us_list"
    bl_label = "Update US List"

    def execute(self, context):
        scene = context.scene

        # Clear existing US list
        scene.selected_epoch_us_list.clear()

        # Accedi al grafo
        graph_instance = get_graph()

        if not graph_instance:
            self.report({'ERROR'}, "Grafo non caricato.")
            return {'CANCELLED'}

        # Get the selected epoch
        if scene.epoch_list_index >= 0 and scene.epoch_list_index < len(scene.epoch_list):
            selected_epoch = scene.epoch_list[scene.epoch_list_index]

            # Access the graph (ensure it's stored in scene.em_graph)
            #graph = scene.em_graph

            if graph_instance:
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
                                item.y_pos = str(other_node.attributes['y_pos'])
                else:
                    self.report({'WARNING'}, f"Epoch node '{selected_epoch.name}' not found in the graph.")
            else:
                self.report({'ERROR'}, "Graph not loaded. Please ensure the graph is available as 'scene.em_graph'.")
        else:
            self.report({'WARNING'}, "No epoch selected.")

        return {'FINISHED'}

def update_filtered_lists_if_needed(self, context):
    # Aggiorna la lista US per la visualizzazione nell'altro pannello
    bpy.ops.epoch_manager.update_us_list()
    
    # Se il filtro per epoca è attivo, aggiorna anche la lista principale
    if context.scene.filter_by_epoch:
        bpy.ops.em.filter_lists()


classes = [
    EM_UL_named_epoch_managers,
    EM_UL_List,
    EM_toggle_reconstruction,
    EM_toggle_select,
    EM_toggle_visibility,
    EM_set_EM_materials,
    EM_set_epoch_materials,
    EM_change_selected_objects,
    EM_toggle_selectable,
    EM_toggle_soloing,
    EM_add_remove_epoch_models,
    EM_select_epoch_rm,
    EM_UpdateUSListOperator,
    VIEW3D_PT_BasePanel
    ]

# Registration
def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.show_epoch_details = BoolProperty(
        name="Show Epoch Details",
        description="Show/hide details of the selected epoch.",
        default=False
    )

    # Aggiungi questo per aggiornare la lista quando cambia l'epoca selezionata
    bpy.types.Scene.epoch_list_index = IntProperty(
        name="Index for epoch_list",
        default=0,
        update=lambda self, context: update_filtered_lists_if_needed(self, context)
    )

def unregister():
        
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    # Rimuovi la proprietà quando si disattiva l'addon
    del bpy.types.Scene.show_epoch_details


