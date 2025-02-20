import bpy
import csv
import os
import bmesh
import math
from bpy_extras.io_utils import ExportHelper
from .s3Dgraphy import convert_shape2type

# Percorso del file CSV con materiali e densità
CSV_FILE = os.path.join(os.path.dirname(__file__), "resources/materials", "ch_materials.csv")

def load_materials():
    """Carica le densità dei materiali dal file CSV."""
    materials = {}
    try:
        with open(CSV_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                materials[row['material'].strip().lower()] = float(row['density_kg_m3'])
    except FileNotFoundError:
        print(f"File {CSV_FILE} non trovato.")
    return materials

def get_material_items(self, context):
    """Restituisce l'elenco dei materiali come items per EnumProperty."""
    materials = load_materials()
    return [(mat, mat.title(), "") for mat in sorted(materials.keys())] if materials else [("none", "No material available", "")]

def is_mesh_closed(bm):
    """Verifica se una mesh è chiusa controllando i bordi non manifold."""
    return all(len(edge.link_faces) == 2 for edge in bm.edges)

def calculate_object_metrics(obj, selected_material, materials):
    """Calcola volume, peso e superfici di un oggetto."""
    if not obj or obj.type != 'MESH':
        return None, None, None, None, None
    
    # Calcolo del volume con BMesh
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    
    if is_mesh_closed(bm):
        measurement_type = "Closed Mesh"
        try:
            volume = bm.calc_volume()
        except RuntimeError:
            volume = None
            measurement_type = "Errore nel calcolo del volume"
    else:
        measurement_type = "Open Mesh - Bounding Box"
        dimensions = obj.dimensions
        volume = dimensions.x * dimensions.y * dimensions.z
    
    total_surface = sum(f.calc_area() for f in bm.faces)
    vertical_surface = sum(f.calc_area() for f in bm.faces if 85 <= math.degrees(f.normal.angle((0, 0, 1))) <= 95)
    
    bm.free()
    
    # Calcolo del peso
    material_name = selected_material.strip().lower()
    if material_name in materials:
        density = materials[material_name]
        weight = volume * density if volume else "Errore nel volume"
    else:
        weight = "Materiale non valido"
    
    return volume, weight, measurement_type, total_surface, vertical_surface

# Proprietà per la selezione delle opzioni di esportazione
class EMSceneProperties(bpy.types.PropertyGroup):
    export_volume: bpy.props.BoolProperty(name="Calculate Volume", default=True)
    export_weight: bpy.props.BoolProperty(name="Calculate weight", default=False)
    material_list: bpy.props.EnumProperty(name="Material", items=get_material_items)

class EMExportCSV(bpy.types.Operator, ExportHelper):
    """Esporta i dati degli oggetti selezionati in CSV."""
    bl_idname = "export_mesh.csv"
    bl_label = "Esporta dati Mesh in CSV"
    filename_ext = ".csv"
    filter_glob: bpy.props.StringProperty(default="*.csv", options={'HIDDEN'})

    def execute(self, context):
        scene_props = context.scene.em_properties
        materials = load_materials()

        data = []
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            
            selected_material = scene_props.material_list
            volume, weight, measurement_type, total_surface, vertical_surface = calculate_object_metrics(obj, selected_material, materials)
            
            epoca = description = emnode = "none"
            for i in bpy.context.scene.em_list:
                if obj.name == i.name:
                    epoca = i.epoch
                    description = i.description
                    emnode = convert_shape2type(i.shape, i.border_style)[0]
                    break
            
            row = {
                "Name": obj.name,
                "EM node": emnode,
                "Epoch": epoca,
                "Description": description,
                "Volume (m³)": volume if scene_props.export_volume else "",
                "Measurement type": measurement_type,
                "Weight (kg)": weight if scene_props.export_weight else "",
                "Total Surface (m²)": total_surface,
                "Vertical Surface (m²)": vertical_surface
            }
            data.append(row)

        # Esportazione CSV
        with open(self.filepath, 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=["Name", "EM node", "Epoch", "Description", "Volume (m³)", "Measurement type", "Weight (kg)", "Total Surface (m²)", "Vertical Surface (m²)"])
            writer.writeheader()
            writer.writerows(data)

        self.report({'INFO'}, f"Esportato CSV in {self.filepath}")
        return {'FINISHED'}

# Pannello per l'interfaccia utente
class EM_PT_ExportPanel(bpy.types.Panel):
    bl_label = "Export statistics"
    bl_idname = "EM_PT_ExportPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM'

    def draw(self, context):
        layout = self.layout
        scene_props = context.scene.em_properties
        layout.prop(scene_props, "export_volume")
        layout.prop(scene_props, "export_weight")
        if scene_props.export_weight:
            layout.prop(scene_props, "material_list")
        layout.operator("export_mesh.csv")

# Registrazione delle classi
def register():
    bpy.utils.register_class(EMSceneProperties)
    bpy.types.Scene.em_properties = bpy.props.PointerProperty(type=EMSceneProperties)
    bpy.utils.register_class(EMExportCSV)
    bpy.utils.register_class(EM_PT_ExportPanel)

def unregister():
    bpy.utils.unregister_class(EM_PT_ExportPanel)
    bpy.utils.unregister_class(EMExportCSV)
    bpy.utils.unregister_class(EMSceneProperties)
    del bpy.types.Scene.em_properties

if __name__ == "__main__":
    register()
