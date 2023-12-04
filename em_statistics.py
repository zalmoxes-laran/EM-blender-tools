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

def esporta_in_csv(objs, file_path):
    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Nome Oggetto', 'Volume (m^3)', 'Superficie Totale (m^2)', 'Superficie Verticale (m^2)']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for obj in objs:
            # Calcola le metriche per l'oggetto
            volume = calcola_volume(obj)
            superficie_totale = calcola_superficie_totale(obj)
            superficie_verticale = calcola_superficie_verticale(obj)
            
            # Scrivi le metriche nell'CSV
            writer.writerow({
                'Nome Oggetto': obj.name,
                'Volume (m^3)': volume,
                'Superficie Totale (m^2)': superficie_totale,
                'Superficie Verticale (m^2)': superficie_verticale
            })

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
    )

    def execute(self, context):
        # Accedi alle impostazioni della scena per vedere se esportare il CSV
        em_csv_settings = context.scene.em_csv_settings
        if em_csv_settings.export_csv:
            esporta_in_csv(context.selected_objects, self.filepath)
            self.report({'INFO'}, f"Dati esportati in {self.filepath}")
        return {'FINISHED'}

def calcola_volume(obj):
    #obj = bpy.context.active_object
    
    if obj == None or obj.type != 'MESH':
        print("Nessun oggetto mesh selezionato.")
        return

    bpy.context.view_layer.update()

    # Creazione di un nuovo oggetto BMesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    try:
        volume = abs(bm.calc_volume())
        #print(f"Volume: {volume} metri cubi")
    except ValueError:
        volume = -10
        #print("Impossibile calcolare il volume. Assicurati che la mesh sia chiusa.")
    finally:
        bm.free()
    return volume

def calcola_superficie_totale(obj):
    #obj = bpy.context.active_object
    
    if obj == None or obj.type != 'MESH':
        print("Nessun oggetto mesh selezionato.")
        return

    bpy.context.view_layer.update()
    
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    superficie = sum(f.calc_area() for f in bm.faces)
    bm.free()

    print(f"Superficie totale: {superficie} metri quadri")
    return superficie

def calcola_superficie_verticale(obj, soglia_angolo=5):
    #obj = bpy.context.active_object
    
    if obj == None or obj.type != 'MESH':
        print("Nessun oggetto mesh selezionato.")
        return

    bpy.context.view_layer.update()
    
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    superficie_verticale = 0
    for f in bm.faces:
        # Calcolare l'angolo tra il vettore normale del poligono e l'asse Z
        angolo = f.normal.angle([0,0,1])
        
        # Convertire l'angolo in gradi
        angolo_gradi = math.degrees(angolo)

        # Verificare se l'angolo è inferiore alla soglia_angolo
        if 90 - soglia_angolo <= angolo_gradi <= 90 + soglia_angolo:
            superficie_verticale += f.calc_area()

    print(f"Superficie verticale: {superficie_verticale} metri quadri")
    return superficie_verticale

def arrotonda_a_tre_decimali(valore):
    return round(valore, 3)


class EM_calculate_stats(bpy.types.Operator):
    bl_idname = "calculate.emstats"
    bl_label = "Calculate EM stats"
    bl_options = {"REGISTER", "UNDO"}

    #node_type: StringProperty()
    '''
    def execute(self, context):
        scene = context.scene
        
        obj = bpy.context.active_object

        if obj == None or obj.type != 'MESH':
            print("Nessun oggetto mesh selezionato.")

        else: 
            bpy.context.view_layer.update()
            calcola_superficie_totale(obj)
            #calcola_superficie_volume(obj)
            calcola_superficie_verticale(obj)
            calcola_volume(obj)
        return {'FINISHED'}
        '''
    def execute(self, context):
        # Ottieni tutti gli oggetti selezionati di tipo 'MESH'
        objs = [obj for obj in context.selected_objects if obj.type == 'MESH']

        # Apri il file CSV per la scrittura
        with open(self.filepath, 'w', newline='') as csvfile:
            fieldnames = ['Nome Oggetto', 'Volume (m^3)', 'Superficie Totale (m^2)', 'Superficie Verticale (m^2)']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            # Per ogni oggetto calcola i dati e scrivi nel CSV
            for obj in objs:
                volume = arrotonda_a_tre_decimali(calcola_volume(obj))
                superficie_totale = arrotonda_a_tre_decimali(calcola_superficie_totale(obj))
                superficie_verticale = arrotonda_a_tre_decimali(calcola_superficie_verticale(obj))
                writer.writerow({
                    'Nome Oggetto': obj.name,
                    'Volume (m^3)': volume,
                    'Superficie Totale (m^2)': superficie_totale,
                    'Superficie Verticale (m^2)': superficie_verticale
                })

        return {'FINISHED'}

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
        #box = layout.box()

        row = layout.row(align=True)
        split = row.split()
        col = split.column()
        col.label(text="Calculate area and volume")
        col.operator("calculate.emstats", icon= 'IMPORT', text="calculate")

        layout = self.layout
        scene = context.scene
        em_csv_settings = scene.em_csv_settings
        
        # Pulsante per esportare il CSV
        row = layout.row()
        row.prop(em_csv_settings, "export_csv", text="Esporta CSV")

        # Pulsante che attiva l'operatore del file browser se il booleano è vero
        if em_csv_settings.export_csv:
            row = layout.row()
            row.operator("export_mesh.csv", text="Salva CSV")

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
    )

classes = [
    VIEW3D_PT_Statistics,
    EM_calculate_stats]

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