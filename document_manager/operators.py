"""Operators for the Document Manager."""

import bpy


class DOCMANAGER_OT_open_url(bpy.types.Operator):
    """Open the URL associated with the selected document"""
    bl_idname = "em.docmanager_open_url"
    bl_label = "Open Document URL"

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        idx = em_tools.em_sources_list_index
        return 0 <= idx < len(em_tools.em_sources_list) and em_tools.em_sources_list[idx].url

    def execute(self, context):
        import webbrowser
        em_tools = context.scene.em_tools
        item = em_tools.em_sources_list[em_tools.em_sources_list_index]
        if item.url:
            webbrowser.open(item.url)
            self.report({'INFO'}, f"Opened URL for {item.name}")
        return {'FINISHED'}


class DOCMANAGER_OT_select_scene_object(bpy.types.Operator):
    """Select the scene object that corresponds to this document"""
    bl_idname = "em.docmanager_select_object"
    bl_label = "Select Scene Object"

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        idx = em_tools.em_sources_list_index
        if 0 <= idx < len(em_tools.em_sources_list):
            name = em_tools.em_sources_list[idx].name
            return name in bpy.data.objects
        return False

    def execute(self, context):
        em_tools = context.scene.em_tools
        item = em_tools.em_sources_list[em_tools.em_sources_list_index]
        obj = bpy.data.objects.get(item.name)
        if obj:
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj
            self.report({'INFO'}, f"Selected {item.name}")
        return {'FINISHED'}


class DOCMANAGER_OT_filter_masters(bpy.types.Operator):
    """Toggle filter to show only master documents"""
    bl_idname = "em.docmanager_filter_masters"
    bl_label = "Filter Masters"

    def execute(self, context):
        context.scene.em_tools.docmanager_filter_masters = not context.scene.em_tools.docmanager_filter_masters
        return {'FINISHED'}


classes = (
    DOCMANAGER_OT_open_url,
    DOCMANAGER_OT_select_scene_object,
    DOCMANAGER_OT_filter_masters,
)


def register_operators():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister_operators():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
