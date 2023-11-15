import bpy
import bmesh
import math
from bpy.types import Operator
from bpy.types import Menu, Panel, UIList, PropertyGroup
import os

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
        print(f"Volume: {volume} metri cubi")
    except ValueError:
        print("Impossibile calcolare il volume. Assicurati che la mesh sia chiusa.")
    finally:
        bm.free()

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

class EM_calculate_stats(bpy.types.Operator):
    bl_idname = "calculate.emstats"
    bl_label = "Calculate EM stats"
    bl_options = {"REGISTER", "UNDO"}

    #node_type: StringProperty()

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

class EM_statistics:
    bl_label = "EM statistics"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_settings = scene.em_settings
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

'''        
        if scene.EM_file:
            col = split.column(align=True)
            if is_em_list:
                button_load_text = 'Reload'
                button_load_icon = 'FILE_REFRESH'
            else:
                button_load_text = 'Load'
                button_load_icon = 'IMPORT'
            col.operator("import.em_graphml", icon= button_load_icon, text=button_load_text)
        else:
            col.label(text="Select a GraphML file below", icon='SORT_ASC')
        #row = layout.row()
        if is_em_list:
            col = split.column(align=True)
            op = col.operator("list_icon.update", icon="PRESET", text='Refresh')
            op.list_type = "all"

        row = layout.row(align=True)
        row.prop(context.scene, 'EM_file', toggle = True, text ="")
        
        ############# box con le statistiche del file ##################
        box = layout.box()
        row = box.row(align=True)
        #row = layout.row(align=True)
        split = row.split()
        col = split.column()
        col.label(text="US/USV")
        #col = split.column()
        col.prop(scene, "em_list", text='')
        col = split.column()
        col.label(text="Periods")
        #col = split.column()
        col.prop(scene, "epoch_list", text='')

        col = split.column()
        col.label(text="Properties")
        #col = split.column()
        col.prop(scene, "em_properties_list", text='')

        col = split.column()
        col.label(text="Sources")
        #col = split.column()
        col.prop(scene, "em_sources_list", text='')

        ################ da qui setto la cartella DosCo ##################

        row = layout.row(align=True)
        box = layout.box()
        row = box.row()
        row.prop(context.scene, 'EMDosCo_dir', toggle = True, text ="DosCo")  

        ################ da qui setto la lista delle sources ##################

        row = layout.row()
        box = layout.box()
        row = box.row()
        row.label(text="Load external xlsx source file")
        row.operator("load.emdb_xlsx", icon="STICKY_UVS_DISABLE", text='')
        row.operator("open_prefs_panel.em_tools", icon="SETTINGS", text="")
        row = box.row()

        
        row.prop(scene, "EMdb_xlsx_filepath", text="")      
'''
class VIEW3D_PT_Statistics(Panel, EM_statistics):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_Statistics"
    bl_context = "objectmode"

#SETUP MENU
#####################################################################

classes = [
    VIEW3D_PT_Statistics,
    EM_calculate_stats]

def register():
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
    for cls in classes:
        bpy.utils.unregister_class(cls)
    #del bpy.types.Scene.EMdb_file
    #del bpy.types.Scene.EMDosCo_dir