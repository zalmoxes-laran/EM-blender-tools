"""UI components for the Paradata Manager."""

import bpy
from bpy.types import Panel, UIList

from ..functions import check_if_current_obj_has_brother_inlist
from .. import icons_manager


def draw_multiline_text(layout, text, max_chars=70, icon="NONE"):
    """
    Disegna testo su più righe se supera max_chars.
    Versione migliorata che gestisce meglio il wrapping.
    """
    if not text:
        layout.label(text="(empty)", icon="ERROR")
        return

    text_str = str(text).strip()
    if len(text_str) <= max_chars:
        row = layout.row()
        row.scale_y = 0.9
        row.label(text=text_str, icon=icon)
        return

    box = layout.box()
    box.scale_y = 0.8
    col = box.column(align=True)

    words = text_str.split()
    current_line = ""
    line_count = 0

    for word in words:
        test_line = (current_line + " " + word) if current_line else word
        if len(test_line) <= max_chars:
            current_line = test_line
        else:
            if current_line:
                row = col.row()
                row.scale_y = 0.9
                if line_count == 0:
                    row.label(text=current_line, icon=icon)
                else:
                    row.label(text=current_line)
                line_count += 1
            current_line = word

    if current_line:
        row = col.row()
        row.scale_y = 0.9
        if line_count == 0:
            row.label(text=current_line, icon=icon)
        else:
            row.label(text=current_line)


class EM_ParadataPanel:
    bl_label = "Paradata Manager"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        return em_tools.mode_em_advanced

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.object

        control_box = layout.box()
        row = control_box.row(align=True)
        row.prop(scene.em_tools, "paradata_auto_update", text="Auto Update")
        row.operator("em.update_paradata_lists", text="Refresh", icon="FILE_REFRESH")
        row = layout.row()

        if scene.em_tools.paradata_streaming_mode:
            property_list_var = "em_v_properties_list"
            property_list_index_var = "em_v_properties_list_index"
            property_list_cmd = "scene.em_tools.em_v_properties_list"
            property_list_index_cmd = "scene.em_tools.em_v_properties_list_index"

            combiner_list_var = "em_v_combiners_list"
            combiner_list_index_var = "em_v_combiners_list_index"
            combiner_list_cmd = "scene.em_tools.em_v_combiners_list"
            combiner_list_index_cmd = "scene.em_tools.em_v_combiners_list_index"

            extractor_list_var = "em_v_extractors_list"
            extractor_list_index_var = "em_v_extractors_list_index"
            extractor_list_cmd = "scene.em_tools.em_v_extractors_list"
            extractor_list_index_cmd = "scene.em_tools.em_v_extractors_list_index"

            source_list_var = "em_v_sources_list"
            source_list_index_var = "em_v_sources_list_index"
            source_list_cmd = "scene.em_tools.em_v_sources_list"
            source_list_index_cmd = "scene.em_tools.em_v_sources_list_index"

        else:
            property_list_var = "em_properties_list"
            property_list_index_var = "em_properties_list_index"
            property_list_cmd = "scene.em_tools.em_properties_list"
            property_list_index_cmd = "scene.em_tools.em_properties_list_index"

            combiner_list_var = "em_combiners_list"
            combiner_list_index_var = "em_combiners_list_index"
            combiner_list_cmd = "scene.em_tools.em_combiners_list"
            combiner_list_index_cmd = "scene.em_tools.em_combiners_list_index"

            extractor_list_var = "em_extractors_list"
            extractor_list_index_var = "em_extractors_list_index"
            extractor_list_cmd = "scene.em_tools.em_extractors_list"
            extractor_list_index_cmd = "scene.em_tools.em_extractors_list_index"

            source_list_var = "em_sources_list"
            source_list_index_var = "em_sources_list_index"
            source_list_cmd = "scene.em_tools.em_sources_list"
            source_list_index_cmd = "scene.em_tools.em_sources_list_index"

        property_list_length = len(eval(property_list_cmd))
        property_list_index = eval(property_list_index_cmd)
        property_index_valid = property_list_length > 0 and 0 <= property_list_index < property_list_length

        paradata_text = "Full list of paradata"
        strat = scene.em_tools.stratigraphy
        if scene.em_tools.paradata_streaming_mode and strat.units_index >= 0 and len(strat.units) > 0:
            paradata_text = str("Paradata related to: " + str(strat.units[strat.units_index].name))
        else:
            try:
                if hasattr(scene, "em_tools") and hasattr(scene.em_tools, "active_file_index"):
                    if scene.em_tools.active_file_index >= 0 and hasattr(scene.em_tools, "graphml_files"):
                        if scene.em_tools.active_file_index < len(scene.em_tools.graphml_files):
                            graphml_file = scene.em_tools.graphml_files[scene.em_tools.active_file_index]
                            if hasattr(graphml_file, "graph_code") and graphml_file.graph_code:
                                paradata_text = f"Full list of paradata in: {graphml_file.graph_code}"
                            else:
                                paradata_text = "Full list of paradata (no graph code available)"
                        else:
                            paradata_text = "Full list of paradata (invalid file index)"
                    else:
                        paradata_text = "No GraphML file selected"
                else:
                    paradata_text = "EM Tools not properly initialized"
            except Exception as exc:
                print(f"Error getting graph code: {exc}")
                paradata_text = "Error accessing GraphML information"

        split = layout.split(factor=0.70)
        col1 = split.column()
        col1.label(text=paradata_text)
        col2 = split.column()
        col2.prop(scene.em_tools, "paradata_streaming_mode", text="Filter Paradata", icon="SHORTDISPLAY")

        row = layout.row()
        row.label(icon_value=icons_manager.get_icon_value("property"), text="Properties: (" + str(property_list_length) + ")")

        if property_list_length > 0:
            row = layout.row()
            row.template_list(
                "EM_UL_properties_managers",
                "",
                scene.em_tools,
                property_list_var,
                scene.em_tools,
                property_list_index_var,
                rows=2,
            )

            box = layout.box()
            if property_index_valid:
                item_property = eval(property_list_cmd)[property_list_index]
                row = box.row()
                row.label(text="Name:", icon="FILE_TEXT")
                row = box.row()
                draw_multiline_text(row, item_property.name, max_chars=70)

                row = box.row()
                row.label(text="Description:", icon="TEXT")
                row = box.row()
                draw_multiline_text(row, item_property.description, max_chars=70)
            else:
                row = box.row()
                row.label(text="No properties available")

        combiner_list_length = len(eval(combiner_list_cmd))
        combiner_list_index = eval(combiner_list_index_cmd)
        combiner_index_valid = combiner_list_length > 0 and 0 <= combiner_list_index < combiner_list_length

        row = layout.row()
        row.label(icon_value=icons_manager.get_icon_value("combiner"), text="Combiners: (" + str(combiner_list_length) + ")")

        if combiner_list_length > 0:
            row = layout.row()
            row.template_list(
                "EM_UL_combiners_managers",
                "",
                scene.em_tools,
                combiner_list_var,
                scene.em_tools,
                combiner_list_index_var,
                rows=1,
            )

            box = layout.box()
            if combiner_index_valid:
                item_property = eval(combiner_list_cmd)[combiner_list_index]
                row = box.row()
                row.label(text="Name:", icon="FILE_TEXT")
                row = box.row()
                draw_multiline_text(row, item_property.name, max_chars=70)

                row = box.row()
                row.label(text="Description:", icon="TEXT")
                row = box.row()
                draw_multiline_text(row, item_property.description, max_chars=70)

                row = box.row()
                row.label(text="URL:", icon="URL")
                split = row.split(factor=0.85)
                col_url = split.column()
                draw_multiline_text(col_url, item_property.url, max_chars=70)
                col_btn = split.column()
                op = col_btn.operator("open.file", icon="EMPTY_SINGLE_ARROW", text="")
                if op:
                    op.node_type = combiner_list_var

        extractor_list_length = len(eval(extractor_list_cmd))
        extractor_list_index = eval(extractor_list_index_cmd)
        extractor_index_valid = extractor_list_length > 0 and 0 <= extractor_list_index < extractor_list_length

        row = layout.row()
        row.label(icon_value=icons_manager.get_icon_value("extractor"), text="Extractors: (" + str(extractor_list_length) + ")")

        if extractor_list_length > 0:
            row = layout.row()
            row.template_list(
                "EM_UL_extractors_managers",
                "",
                scene.em_tools,
                extractor_list_var,
                scene.em_tools,
                extractor_list_index_var,
                rows=2,
            )

            box = layout.box()
            if extractor_index_valid:
                item_source = eval(extractor_list_cmd)[extractor_list_index]

                row = box.row()
                split = row.split(factor=0.15)
                split.label(text="Name:", icon="FILE_TEXT")

                main_split = split.split(factor=0.82)
                col_name = main_split.column()
                draw_multiline_text(col_name, item_source.name, max_chars=70)

                col_btns = main_split.column(align=True)
                btn_row = col_btns.row(align=True)
                op = btn_row.operator("listitem.toobj", icon="LINK_BLEND", text="")
                if op:
                    op.list_type = extractor_list_var

                strat = scene.em_tools.stratigraphy
                if strat.units_index >= 0 and len(strat.units) > 0 and strat.units[strat.units_index].icon == "LINKED":
                    _ps_icon = icons_manager.get_icon_value("proxies_select")
                    if _ps_icon:
                        op = btn_row.operator("select.fromlistitem", text="", icon_value=_ps_icon)
                    else:
                        op = btn_row.operator("select.fromlistitem", text="", icon="MESH_CUBE")
                    if op:
                        op.list_type = extractor_list_var
                else:
                    _po_icon = icons_manager.get_icon_value("proxies_off")
                    if _po_icon:
                        btn_row.label(text="", icon_value=_po_icon)
                    else:
                        btn_row.label(text="", icon="MESH_CUBE")

                if obj and check_if_current_obj_has_brother_inlist(obj.name, extractor_list_var):
                    op = btn_row.operator("select.listitem", text="", icon="LONGDISPLAY")
                    if op:
                        op.list_type = extractor_list_var
                else:
                    btn_row.label(text="", icon="LONGDISPLAY")

                row = box.row()
                row.label(text="Description:", icon="TEXT")
                row = box.row()
                draw_multiline_text(row, item_source.description, max_chars=70)

                row = box.row()
                row.label(text="URL:", icon="URL")
                split = row.split(factor=0.85)
                col_url = split.column()
                draw_multiline_text(col_url, item_source.url, max_chars=70)
                col_btn = split.column()
                op = col_btn.operator("open.file", icon="EMPTY_SINGLE_ARROW", text="")
                if op:
                    op.node_type = extractor_list_var
            else:
                row = box.row()
                row.label(text="No extractor available")

        source_list_length = len(eval(source_list_cmd))
        source_list_index = eval(source_list_index_cmd)
        source_index_valid = source_list_length > 0 and 0 <= source_list_index < source_list_length

        row = layout.row()
        row.label(icon_value=icons_manager.get_icon_value("document"), text="Docs: (" + str(source_list_length) + ")")

        if source_list_length > 0:
            row = layout.row()
            row.template_list(
                "EM_UL_sources_managers",
                "",
                scene.em_tools,
                source_list_var,
                scene.em_tools,
                source_list_index_var,
                rows=2,
            )

            box = layout.box()
            if source_index_valid:
                item_source = eval(source_list_cmd)[source_list_index]

                row = box.row()
                split = row.split(factor=0.15)
                split.label(text="Name:", icon="FILE_TEXT")

                main_split = split.split(factor=0.82)
                col_name = main_split.column()
                draw_multiline_text(col_name, item_source.name, max_chars=70)

                col_btns = main_split.column(align=True)
                btn_row = col_btns.row(align=True)
                op = btn_row.operator("listitem.toobj", icon="LINK_BLEND", text="")
                if op:
                    op.list_type = source_list_var

                strat = scene.em_tools.stratigraphy
                if strat.units_index >= 0 and len(strat.units) > 0 and strat.units[strat.units_index].icon == "LINKED":
                    _ps_icon = icons_manager.get_icon_value("proxies_select")
                    if _ps_icon:
                        op = btn_row.operator("select.fromlistitem", text="", icon_value=_ps_icon)
                    else:
                        op = btn_row.operator("select.fromlistitem", text="", icon="MESH_CUBE")
                    if op:
                        op.list_type = source_list_var
                else:
                    _po_icon = icons_manager.get_icon_value("proxies_off")
                    if _po_icon:
                        btn_row.label(text="", icon_value=_po_icon)
                    else:
                        btn_row.label(text="", icon="MESH_CUBE")

                if obj and check_if_current_obj_has_brother_inlist(obj.name, source_list_var):
                    op = btn_row.operator("select.listitem", text="", icon="LONGDISPLAY")
                    if op:
                        op.list_type = source_list_var
                else:
                    btn_row.label(text="", icon="LONGDISPLAY")

                row = box.row()
                row.label(text="Description:", icon="TEXT")
                row = box.row()
                draw_multiline_text(row, item_source.description, max_chars=70)

                row = box.row()
                row.label(text="URL:", icon="URL")
                split = row.split(factor=0.85)
                col_url = split.column()
                draw_multiline_text(col_url, item_source.url, max_chars=70)
                col_btn = split.column()
                op = col_btn.operator("open.file", icon="EMPTY_SINGLE_ARROW", text="")
                if op:
                    op.node_type = source_list_var
            else:
                row = box.row()
                row.label(text="No documents available")

        if scene.paradata_image.image_collection:
            box = layout.box()
            row = box.row()
            images = scene.paradata_image.image_collection
            active_index = scene.paradata_image.active_image_index

            if len(images) > 1:
                row = box.row()
                row.operator("em.previous_image", text="", icon="TRIA_LEFT")
                row.label(text=f"Image {active_index + 1} of {len(images)}")
                row.operator("em.next_image", text="", icon="TRIA_RIGHT")

            if 0 <= active_index < len(images):
                active_image = images[active_index].image
                row = box.row()
                row.template_preview(active_image, show_buttons=False)


class VIEW3D_PT_ParadataPanel(Panel, EM_ParadataPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ParadataPanel"
    bl_context = "objectmode"


class EM_UL_sources_managers(UIList):
    # Map certainty classes to Blender layer color icons
    CERTAINTY_ICONS = {
        "direct": "COLLECTION_COLOR_01",          # red
        "reconstructed": "COLLECTION_COLOR_02",   # orange
        "hypothetical": "COLLECTION_COLOR_03",    # yellow
        "unknown": "COLLECTION_COLOR_08",         # gray
    }

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if item.is_master:
            # Master document: show certainty icon + name + date info
            certainty_icon = self.CERTAINTY_ICONS.get(item.certainty_class, "KEYTYPE_MOVING_HOLD_VEC")
            row = layout.row(align=True)
            row.label(text="", icon=certainty_icon)
            split = row.split(factor=0.25, align=True)
            name_label = item.name
            if item.absolute_start_date:
                name_label = f"{item.name} ({item.absolute_start_date})"
            split.label(text=name_label, icon=item.icon)
            split.label(text=item.description, icon=item.icon_url)
        else:
            # Standard document instance display (unchanged)
            layout = layout.split(factor=0.22, align=True)
            layout.label(text=item.name, icon=item.icon)
            layout.label(text=item.description, icon=item.icon_url)


class EM_UL_properties_managers(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout = layout.split(factor=0.4, align=True)
        layout.label(text=item.name)
        layout.label(text=item.description)


class EM_UL_combiners_managers(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout = layout.split(factor=0.25, align=True)
        layout.label(text=item.name)
        layout.label(text=item.description)


class EM_UL_extractors_managers(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout = layout.split(factor=0.25, align=True)
        layout.label(text=item.name, icon=item.icon)
        layout.label(text=item.description, icon=item.icon_url)


classes = (
    VIEW3D_PT_ParadataPanel,
    EM_UL_properties_managers,
    EM_UL_sources_managers,
    EM_UL_extractors_managers,
    EM_UL_combiners_managers,
)


def register_ui():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister_ui():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
