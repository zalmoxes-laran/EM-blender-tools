import bpy
import bpy.props as prop

from bpy.props import (BoolProperty,
                       FloatProperty,
                       StringProperty,
                       EnumProperty,
                       CollectionProperty,
                       IntProperty,
                       PointerProperty,
                       FloatVectorProperty,
                       )

from bpy.types import (
        AddonPreferences,
        PropertyGroup,
        )

from .functions import *


#### da qui si definiscono le funzioni e gli operatori

# class EM_usname_OT_toproxy(bpy.types.Operator):
#     bl_idname = "usname.toproxy"
#     bl_label = "Use US name for selected proxy"
#     bl_options = {"REGISTER", "UNDO"}

#     @classmethod
#     def poll(cls, context):
#         obj = context.object
#         if obj is None:
#             pass
#         else:
#             return (obj.type in ['MESH'])

#     def execute(self, context):
#         scene = context.scene
#         item = scene.em_list[scene.em_list_index]
#         context.active_object.name = item.name
#         update_icons(context)
#         if context.scene.proxy_display_mode == "EM":
#             bpy.ops.emset.emmaterial
#         else:
#             bpy.ops.emset.epochmaterial
#         return {'FINISHED'}

# class Source_update_icon_list(bpy.types.Operator):
#     bl_idname = "sourcelist_icon.update"
#     bl_label = "Update only the icons of the sources"
#     bl_options = {"REGISTER", "UNDO"}

#     def execute(self, context):
#         #update_icons(context)
#         pass        
#         return {'FINISHED'}


# class EM_select_source_list_item(bpy.types.Operator):
#     bl_idname = "select.source_listitem"
#     bl_label = "Select element in the list above from a 3D proxy"
#     bl_options = {"REGISTER", "UNDO"}

#     @classmethod
#     def poll(cls, context):
#         obj = context.object
#         if obj is None:
#             pass
#         else:
#             return (check_if_current_obj_has_brother_inlist(obj.name))

#     def execute(self, context):
#         scene = context.scene
#         obj = context.object
#         select_list_element_from_obj_proxy(obj)
#         return {'FINISHED'}

# class EM_select_from_source_list_item(bpy.types.Operator):
#     bl_idname = "select.fromsourcelistitem"
#     bl_label = "Select 3D proxy from the list above"
#     bl_options = {"REGISTER", "UNDO"}

#     @classmethod
#     def poll(cls, context):
#         scene = context.scene
#         list_exists = scene.em_list[0]
#         if list_exists is None:
#             pass
#         else:
#             return (scene.em_list[scene.em_list_index].icon == 'RESTRICT_INSTANCED_OFF')

#     def execute(self, context):
#         scene = context.scene
#         list_item = scene.em_list[scene.em_list_index]
#         select_3D_obj(list_item.name)
#         return {'FINISHED'}