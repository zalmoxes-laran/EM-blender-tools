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
    """
    Verifies if a bmesh is closed, with additional safety checks.
    
    Args:
        bm (bmesh.types.BMesh): Bmesh to check
    
    Returns:
        bool: True if mesh is closed, False otherwise
    """
    try:
        # Check if all edges have exactly 2 faces
        return all(len(edge.link_faces) == 2 for edge in bm.edges if edge.is_valid)
    except Exception as e:
        print(f"Mesh closure check error: {e}")
        return False

def calculate_object_metrics(obj, selected_material, materials):
    """
    Calculate volume, weight, and surface metrics for an object with improved error handling.
    
    Args:
        obj (bpy.types.Object): Blender object to measure
        selected_material (str): Selected material for weight calculation
        materials (dict): Dictionary of material densities
    
    Returns:
        tuple: (volume, weight, measurement_type, total_surface, vertical_surface)
    """
    if not obj or obj.type != 'MESH':
        return None, None, None, None, None
    
    print(f"Processing object: {obj.name}")
    
    # Create a copy of the mesh to avoid modifying the original
    mesh = obj.data.copy()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    
    # Reset bmesh to handle potential degenerate geometries
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    
    # Check if mesh is valid
    if not bm.faces or len(bm.faces) == 0:
        bm.free()
        return 0, 0, "Empty Mesh", 0, 0
    
    # Improved volume calculation with fallback
    try:
        if is_mesh_closed(bm):
            measurement_type = "Closed Mesh"
            volume = bm.calc_volume()
        else:
            measurement_type = "Open Mesh - Bounding Box"
            dimensions = obj.dimensions
            volume = max(0, dimensions.x * dimensions.y * dimensions.z)
    except Exception as e:
        print(f"Volume calculation error: {e}")
        measurement_type = "Volume Calculation Failed"
        volume = 0
    
    # Safe surface area calculation
    try:
        total_surface = sum(f.calc_area() for f in bm.faces if f.calc_area() > 0)
    except Exception as e:
        print(f"Total surface calculation error: {e}")
        total_surface = 0
    
    # Improved vertical surface calculation with robust normal checking
    def is_vertical_face(face):
        try:
            # Normalize the normal vector to handle potential zero-length vectors
            normal = face.normal.normalized()
            # Check if normal is close to vertical (between 85 and 95 degrees from Z-axis)
            return 85 <= math.degrees(normal.angle((0, 0, 1))) <= 95
        except Exception as e:
            print(f"Vertical face calculation error: {e}")
            return False
    
    try:
        vertical_surface = sum(f.calc_area() for f in bm.faces if is_vertical_face(f))
    except Exception as e:
        print(f"Vertical surface calculation error: {e}")
        vertical_surface = 0
    
    # Clean up
    bm.free()
    
    # Weight calculation
    try:
        material_name = selected_material.strip().lower()
        weight = volume * materials.get(material_name, 0) if volume and material_name in materials else 0
    except Exception as e:
        print(f"Weight calculation error: {e}")
        weight = 0
    
    return volume, weight, measurement_type, total_surface, vertical_surface

# Proprietà per la selezione delle opzioni di esportazione
class EMSceneProperties(bpy.types.PropertyGroup):
    export_volume: bpy.props.BoolProperty(name="Calculate Volume", default=True)
    export_weight: bpy.props.BoolProperty(name="Calculate weight", default=False)
    material_list: bpy.props.EnumProperty(name="Material", items=get_material_items)

class EMExportCSV(bpy.types.Operator, ExportHelper):
    """Esporta i dati degli oggetti selezionati in CSV"""
    bl_idname = "export_mesh.csv"
    bl_label = "Esporta dati Mesh in CSV"
    filename_ext = ".csv"
    filter_glob: bpy.props.StringProperty(default="*.csv", options={'HIDDEN'})

    def execute(self, context):
        scene_props = context.scene.em_properties
        materials = load_materials()

        # Definisci esattamente i fieldnames come nel writer
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
            volume, weight, measurement_type, total_surface, vertical_surface = calculate_object_metrics(obj, selected_material, materials)
            
            epoca = description = emnode = "none"
            for i in bpy.context.scene.em_list:
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

def format_decimal(value):
    """Converte un valore numerico con virgola come separatore decimale."""
    try:
        if isinstance(value, (int, float)):
            return f"{value:.3f}".replace('.', ',')
        return str(value)
    except Exception:
        return str(value)


# Pannello per l'interfaccia utente
class EM_PT_ExportPanel(bpy.types.Panel):
    bl_label = "Export statistics"
    bl_idname = "EM_PT_ExportPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM'
    bl_options = {'DEFAULT_CLOSED'}

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
