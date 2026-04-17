# em_statistics/operators.py

import csv

import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper

from s3dgraphy import convert_shape2type

from .materials import format_decimal, load_materials
from .metrics import calculate_object_metrics


class EMExportCSV(Operator, ExportHelper):
    """Esporta i dati degli oggetti selezionati in CSV"""
    bl_idname = "export_mesh.csv"
    bl_label = "Esporta dati Mesh in CSV"
    filename_ext = ".csv"
    filter_glob: StringProperty(default="*.csv", options={'HIDDEN'})

    def execute(self, context):
        scene_props = context.scene.em_properties
        materials = load_materials()

        fieldnames = [
            "Nome",
            "Tipo_Nodo_EM",
            "Epoca",
            "Descrizione",
            "Volume_(m³)",
            "Tipo_Misurazione",
            "Peso_(kg)",
            "Superficie_Totale_(m²)",
            "Superficie_Verticale_(m²)"
        ]

        data = []
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue

            selected_material = scene_props.material_list
            volume, weight, measurement_type, total_surface, vertical_surface = calculate_object_metrics(
                obj, selected_material, materials
            )

            epoca = description = emnode = "none"
            strat = bpy.context.scene.em_tools.stratigraphy
            for i in strat.units:
                if obj.name == i.name:
                    epoca = i.epoch
                    description = i.description
                    emnode = convert_shape2type(i.shape, i.border_style)[0]
                    break

            row = {
                "Nome": obj.name,
                "Tipo_Nodo_EM": emnode,
                "Epoca": epoca,
                "Descrizione": description,
                "Volume_(m³)": format_decimal(volume) if scene_props.export_volume else "",
                "Tipo_Misurazione": measurement_type,
                "Peso_(kg)": format_decimal(weight) if scene_props.export_weight else "",
                "Superficie_Totale_(m²)": format_decimal(total_surface),
                "Superficie_Verticale_(m²)": format_decimal(vertical_surface)
            }
            data.append(row)

        # Esportazione CSV con punto e virgola come separatore
        with open(self.filepath, 'w', newline='', encoding='utf-8-sig') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(data)

        self.report({'INFO'}, f"Esportato CSV in {self.filepath}")
        return {'FINISHED'}


classes = (
    EMExportCSV,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
