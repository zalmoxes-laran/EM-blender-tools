import bpy
import csv
import os
import bmesh
from bpy_extras.io_utils import ExportHelper

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
    return [(mat, mat.title(), "") for mat in sorted(materials.keys())] if materials else [("none", "Nessun materiale disponibile", "")]

def calculate_object_weight(obj, selected_material, materials):
    """Calcola il volume e il peso di un oggetto selezionato."""
    if not obj or obj.type != 'MESH':
        return None, None
    
    # Calcolo del volume con BMesh
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    
    try:
        volume = bm.calc_volume()
    except RuntimeError:
        print(f"Mesh aperta per '{obj.name}', impossibile calcolare il volume.")
        return None, "Errore: Mesh aperta"
    
    bm.free()
    
    # Verifica del materiale selezionato
    material_name = selected_material.strip().lower()
    print(f"DEBUG: Oggetto {obj.name} - Materiale selezionato: '{material_name}'")
    
    if material_name in materials:
        density = materials[material_name]
        weight = volume * density
        print(f"DEBUG: Materiale trovato! Densità: {density} - Volume: {volume} - Peso: {weight}")
        return volume, weight
    else:
        print(f"ERRORE: Materiale '{material_name}' non trovato nel CSV. Disponibili: {list(materials.keys())}")
        return volume, "Materiale non valido"

# Proprietà per la selezione delle opzioni di esportazione
class EMSceneProperties(bpy.types.PropertyGroup):
    export_volume: bpy.props.BoolProperty(name="Esporta Volume", default=True)
    export_weight: bpy.props.BoolProperty(name="Esporta Peso", default=False)
    material_list: bpy.props.EnumProperty(name="Materiale", items=get_material_items)

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
            volume, weight = calculate_object_weight(obj, selected_material, materials)
            
            row = {
                "name": obj.name,
                "volume": volume if scene_props.export_volume else "",
                "weight": weight if scene_props.export_weight else ""
            }
            data.append(row)

        # Esportazione CSV
        with open(self.filepath, 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=["name", "volume", "weight"])
            writer.writeheader()
            writer.writerows(data)

        self.report({'INFO'}, f"Esportato CSV in {self.filepath}")
        return {'FINISHED'}

# Pannello per l'interfaccia utente
class EM_PT_ExportPanel(bpy.types.Panel):
    bl_label = "Esporta Dati Mesh"
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
