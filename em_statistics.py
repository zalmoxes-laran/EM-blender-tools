import bpy
import bmesh
import math
from bpy.types import Operator
from bpy.types import Menu, Panel, UIList, PropertyGroup
import os

import csv
from bpy_extras.io_utils import ExportHelper
from bpy.props import BoolProperty, PointerProperty
from bpy.types import Operator
from .functions import *

# Operatore per esportare in CSV
class EMExportCSV(Operator, ExportHelper):
    bl_idname = "export_mesh.csv"
    bl_label = "Esporta dati Mesh in CSV"

    # Specifica dell'estensione del file
    filename_ext = ".csv"

    filter_glob: bpy.props.StringProperty(
            default='*.csv',
            options={'HIDDEN'},
            maxlen=255,
            ) # type: ignore

    def execute(self, context):
        # Accedi alle impostazioni della scena per vedere se esportare il CSV
        #em_csv_settings = context.scene.em_csv_settings
        #if em_csv_settings.export_csv:
        self.esporta_in_csv(context.selected_objects, self.filepath)
        self.report({'INFO'}, f"Dati esportati in {self.filepath}")
        return {'FINISHED'}

    def esporta_in_csv(self, objs, file_path):
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Name', 'EM node', 'Epoch', 'Description', 'Volume (m^3)', 'Measurement type', 'Total Surface (m^2)', 'Vertical surface (m^2)']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')

            writer.writeheader()
            for obj in objs:
                # Calcola le metriche per l'oggetto
                misurazione = None
                volume, misurazione = self.calcola_volume(obj)
                superficie_totale = self.arrotonda_a_tre_decimali(self.calcola_superficie_totale(obj))
                superficie_verticale =self.arrotonda_a_tre_decimali(self.calcola_superficie_verticale(obj))
                epoca = None
                description = None
                emnode = ["none","none"]

                for i in bpy.context.scene.em_list:
                    if obj.name == i.name:
                        epoca = i.epoch
                        description = i.description
                        emnode = convert_shape2type(i.shape)
                        pass 
                print(obj.name)
                if emnode:
                    # Scrivi le metriche nel CSV
                    
                    writer.writerow({
                        'Name': obj.name,
                        'EM node': emnode[0],
                        'Epoch': epoca,
                        'Description': description,
                        'Volume (m^3)': self.arrotonda_a_tre_decimali(volume),
                        'Measurement type': misurazione,
                        'Total Surface (m^2)': superficie_totale,
                        'Vertical surface (m^2)': superficie_verticale
                    })

    def calcola_volume(self, obj):
        #obj = bpy.context.active_object
        misurazione = None
        if obj == None or obj.type != 'MESH':
            print("Nessun oggetto mesh selezionato.")
            return

        # Verifica se il conteggio dei poligoni è zero
        if len(obj.data.polygons) == 0:
            return        

        bpy.context.view_layer.update()

        # Crea una copia dell'oggetto con i modificatori applicati
        depsgraph = bpy.context.evaluated_depsgraph_get()
        obj_evaluated = obj.evaluated_get(depsgraph)
        mesh_copy = obj_evaluated.to_mesh()

        bm = bmesh.new()
        bm.from_mesh(mesh_copy)
        bm.faces.ensure_lookup_table()

        for edge in bm.edges:
            # Se un bordo è condiviso da meno di 2 facce, la mesh è aperta
            if len(edge.link_faces) < 2:
                dimensions = obj.dimensions
                volume = dimensions.x * dimensions.y * dimensions.z
                misurazione = "Bounding box (open mesh)"
                bm.free()
                return volume, misurazione
        try:
            # Calcola il volume
            volume = bm.calc_volume(signed=False)
            misurazione = "Closed Mesh"
        except ValueError:
            volume = -10
            misurazione = "Not possible to calculate"
            #print("Impossibile calcolare il volume. Assicurati che la mesh sia chiusa.")
        finally:
            # Rilascia il BMesh e rimuovi la copia della mesh
            bm.free()
            obj_evaluated.to_mesh_clear()
        return volume, misurazione

    def calcola_superficie_totale(self, obj):
        #obj = bpy.context.active_object
        
        if obj == None or obj.type != 'MESH':
            print("Nessun oggetto mesh selezionato.")
            return

        # Verifica se il conteggio dei poligoni è zero
        if len(obj.data.polygons) == 0:
            return        

        bpy.context.view_layer.update()
        
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()

        superficie = sum(f.calc_area() for f in bm.faces)
        bm.free()

        print(f"Superficie totale: {superficie} metri quadri")
        return superficie

    def calcola_superficie_verticale(self, obj, soglia_angolo=5):
        #obj = bpy.context.active_object
        print(obj.name)
        if obj == None or obj.type != 'MESH':
            print("Nessun oggetto mesh selezionato.")
            return

        # Verifica se il conteggio dei poligoni è zero
        if len(obj.data.polygons) == 0:
            return        

        bpy.context.view_layer.update()
        
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()

        superficie_verticale = 0
        for f in bm.faces:
            # Controlla che la normale non sia un vettore di lunghezza zero
            if f.normal.length > 0:  
                # Calcolare l'angolo tra il vettore normale del poligono e l'asse Z
                angolo = f.normal.angle([0,0,1])
                
                # Convertire l'angolo in gradi
                angolo_gradi = math.degrees(angolo)

                # Verificare se l'angolo è inferiore alla soglia_angolo
                if 90 - soglia_angolo <= angolo_gradi <= 90 + soglia_angolo:
                    superficie_verticale += f.calc_area()

        print(f"Superficie verticale: {superficie_verticale} metri quadri")
        return superficie_verticale

    def arrotonda_a_tre_decimali(self, valore):
        return round(valore, 2)

class EM_statistics:
    bl_label = "EM statistics"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_csv_settings = scene.em_csv_settings
        obj = context.object
        
        if len(scene.em_list) > 0:
            is_em_list = True
        else:
            is_em_list = False
            
        layout = self.layout
        scene = context.scene
        em_csv_settings = scene.em_csv_settings
        
        # Pulsante per esportare il CSV
        #row = layout.row()
        #row.prop(em_csv_settings, "export_csv", text="Esporta CSV")

        # Pulsante che attiva l'operatore del file browser se il booleano è vero
        #if em_csv_settings.export_csv:
        row = layout.row()
        row.label(text="Select proxies and export statistical data")
        row = layout.row()
        row.operator("export_mesh.csv", text="Export CSV")

class VIEW3D_PT_Statistics(Panel, EM_statistics):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_Statistics"
    bl_context = "objectmode"

#SETUP MENU
#####################################################################

# Gruppo di proprietà
class EMProperties(PropertyGroup):
    export_csv: BoolProperty(
        name="Esporta CSV",
        description="Se attivato, esporterà i dati mesh selezionati in CSV",
        default=False
    ) # type: ignore

classes = [
    VIEW3D_PT_Statistics
    ]

def register():
    bpy.utils.register_class(EMExportCSV)
    #bpy.utils.register_class(EMPanel)
    bpy.utils.register_class(EMProperties)

    bpy.types.Scene.em_csv_settings = PointerProperty(type=EMProperties)

    for cls in classes:
        bpy.utils.register_class(cls)
'''
    bpy.types.Scene.EMdb_file = StringProperty(
        name = "EM db file",
        default = "",
        description = "Define the path to the EM db (sqlite) file",
        subtype = 'FILE_PATH'
    )   

    bpy.types.Scene.EMDosCo_dir = StringProperty(
        name = "EM DosCo folder",
        default = "",
        description = "Define the path to the EM DosCo folder",
        subtype = 'DIR_PATH'
    )   
'''
def unregister():
    bpy.utils.unregister_class(EMExportCSV)
    #bpy.utils.unregister_class(EMPanel)
    bpy.utils.unregister_class(EMProperties)
    del bpy.types.Scene.em_csv_settings

    for cls in classes:
        bpy.utils.unregister_class(cls)
    #del bpy.types.Scene.EMdb_file
    #del bpy.types.Scene.EMDosCo_dir