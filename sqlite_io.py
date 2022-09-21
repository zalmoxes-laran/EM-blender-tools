import bpy
import sqlite3
import bpy.props as prop
from .functions import EM_list_clear


class EMdbListItem(bpy.types.PropertyGroup):
    """ Group of properties representing an item in the list """

    name: prop.StringProperty(
           name="Name",
           description="A name for this item",
           default="Untitled")

    description: prop.StringProperty(
           name="Description",
           description="A description for this item",
           default="Empty")

    technics: prop.StringProperty(
           name="Tecnica_Muraria",
           description="A description for this item",
           default="Empty")


    icon: prop.StringProperty(
           name="code for icon",
           description="",
           default="RESTRICT_INSTANCED_ON")

'''
    url: prop.StringProperty(
           name="url",
           description="An url behind this item",
           default="Empty")

    shape: prop.StringProperty(
           name="shape",
           description="The shape of this item",
           default="Empty")

    y_pos: prop.FloatProperty(
           name="y_pos",
           description="The y_pos of this item",
           default=0.0)

    epoch: prop.StringProperty(
           name="code for epoch",
           description="",
           default="Empty")

    id_node: prop.StringProperty(
           name="id node",
           description="",
           default="Empty")
'''

class EMdb_import_sqlite(bpy.types.Operator):
    bl_idname = "import.emdb_sqlite"
    bl_label = "Import the EMdb sqlite"
    bl_description = "Import the EMdb sqlite"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):

        scene = context.scene
        nome_db = scene.EMdb_file
        emdb_list_index = 0
        EM_list_clear(context, "emdb_list")
        #nome_db = 'Schede_US.db'
        nome_tabella = 'USM_sheet'   

        conn = sqlite3.connect(nome_db)
        documento = conn.cursor()

        for row in documento.execute('SELECT * FROM '+nome_tabella):
                nome_scheda = row[0]
                
                
                scene.emdb_list.add()
                scene.emdb_list[emdb_list_index].name = nome_scheda
                scene.emdb_list[emdb_list_index].description = str(row[19])
                scene.emdb_list[emdb_list_index].technics = row[20]
                print("l'unità "+nome_scheda+ " ha descrizione: "+str(row[3]))

                for us_item in scene.em_list:
                        if us_item.name == nome_scheda:
                                us_item.icon_db = "DECORATE_KEYFRAME"

                emdb_list_index += 1



        conn.close()
        return {'FINISHED'}    

classes = [
        EMdbListItem,
        EMdb_import_sqlite]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
        
    bpy.types.Scene.emdb_list = prop.CollectionProperty(type = EMdbListItem)
    bpy.types.Scene.emdb_list_index = prop.IntProperty(name = "Index for EMdb list", default = 0)

def unregister():

    del bpy.types.Scene.emdb_list
    del bpy.types.Scene.emdb_list_index
    
    for cls in classes:
        bpy.utils.unregister_class(cls)


