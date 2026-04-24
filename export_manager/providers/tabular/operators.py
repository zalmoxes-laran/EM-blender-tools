# export_manager/providers/tabular/operators.py
"""Tabular (CSV) export operators: UUSS data dump driven by the UI toggles."""

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper

from s3dgraphy.utils.utils import convert_shape2type


class OBJECT_OT_ExportUUSS(Operator):
    bl_idname = "export.uuss_export"
    bl_label = "Export UUSS"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.export.uuss_data('INVOKE_DEFAULT')
        return {'FINISHED'}


class ExportuussData(Operator, ExportHelper):
    """Export UUSS data into a csv file"""
    bl_idname = "export.uuss_data"
    bl_label = "Export UUSS Data"
    filename_ext = ".csv"

    filter_glob: StringProperty(
        default="*.csv",
        options={'HIDDEN'},
        maxlen=255,
    ) # type: ignore

    only_UUSS_with_proxies: BoolProperty(
        name="Only elements with proxies",
        description="Only elements with proxies",
        default=False,
    ) # type: ignore

    header_line: BoolProperty(
        name="Header line",
        description="Header line with description of the columns",
        default=True,
    ) # type: ignore

    def execute(self, context):
        return self._write(context, self.filepath, self.only_UUSS_with_proxies, self.header_line)

    def _write(self, context, filepath, only_UUSS, header):
        with open(filepath, 'w', encoding='utf-8') as f:
            table_type = context.window_manager.export_tables_vars.table_type

            if table_type == 'US/USV':
                if header:
                    f.write("Name; Description; Epoch; Type \n")
                strat = context.scene.em_tools.stratigraphy
                for US in strat.units:
                    if only_UUSS:
                        if US.icon == "RESTRICT_INSTANCED_ON":
                            f.write("%s\t %s\t %s\t %s\n" % (
                                US.name, US.description, US.epoch,
                                convert_shape2type(US.shape, US.border_style)[1]
                            ))
                    else:
                        f.write("%s\t %s\t %s\t %s\n" % (
                            US.name, US.description, US.epoch, US.shape
                        ))

            elif table_type == 'Sources':
                if header:
                    f.write("Name; Description \n")
                for source in context.scene.em_tools.em_sources_list:
                    if only_UUSS:
                        if source.icon == "RESTRICT_INSTANCED_ON":
                            f.write("%s\t %s\n" % (source.name, source.description))
                    else:
                        f.write("%s\t %s\n" % (source.name, source.description))

            elif table_type == 'Extractors':
                if header:
                    f.write("Name\t Description \n")
                for extractor in context.scene.em_tools.em_extractors_list:
                    if only_UUSS:
                        if extractor.icon == "RESTRICT_INSTANCED_ON":
                            f.write("%s\t %s\n" % (extractor.name, extractor.description))
                    else:
                        f.write("%s\t %s\n" % (extractor.name, extractor.description))

        return {'FINISHED'}


classes = (
    OBJECT_OT_ExportUUSS,
    ExportuussData,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
