import bpy
import sqlite3
import bpy.props as prop
from .functions import EM_list_clear
from bpy.props import StringProperty
#from bpy.types import Panel


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


class OP_dbtypeset(bpy.types.Operator):
       bl_idname = "dbtype.set"
       bl_label = "Set db type"
       bl_description = "This operator set the type of the db to be connected"
       bl_options = {"REGISTER", "UNDO"}
       
       db_type : StringProperty()

       def execute(self, context):
              scene = context.scene
              scene.current_db_type = self.db_type
              return {'FINISHED'}   

class EMdb_import_sqlite(bpy.types.Operator):
    bl_idname = "import.emdb_sqlite"
    bl_label = "Import the EMdb sqlite"
    bl_description = "Import the EMdb sqlite"
    bl_options = {"REGISTER", "UNDO"}
    
    db_type : StringProperty()

    def execute(self, context):

       scene = context.scene
       nome_db = scene.EMdb_file
       emdb_list_index = 0
       EM_list_clear(context, "emdb_list")
       #nome_db = 'Schede_US.db'
          
       conn = sqlite3.connect(nome_db)
       documento = conn.cursor()

       if self.db_type == "EMdb":
              nome_tabella = 'USM_sheet'
              
              for row in documento.execute('SELECT * FROM '+nome_tabella):
                     nome_scheda = row[0]
                     scene.emdb_list.add()
                     scene.emdb_list[emdb_list_index].name = nome_scheda
                     scene.emdb_list[emdb_list_index].description = str(row[19])
                     scene.emdb_list[emdb_list_index].technics = row[20]
                     #print("l'unità "+nome_scheda+ " ha descrizione: "+str(row[3]))

                     for us_item in scene.em_list:
                            if us_item.name == nome_scheda:
                                   us_item.icon_db = "DECORATE_KEYFRAME"
                     emdb_list_index += 1

       elif self.db_type == "Pyarchinit":
              nome_tabella = 'us_table'
              for row in documento.execute('SELECT * FROM '+nome_tabella):
                     tipo_scheda = row[29]
                     numero_scheda = str(row[3])
                     nome_scheda = tipo_scheda+numero_scheda
                     
                     scene.emdb_list.add()
                     scene.emdb_list[emdb_list_index].name = nome_scheda
                     scene.emdb_list[emdb_list_index].description = str(row[4])
                     scene.emdb_list[emdb_list_index].technics = row[5]
                     #print("l'unità "+nome_scheda+ " ha descrizione: "+str(row[3]))

                     for us_item in scene.em_list:
                            if us_item.name == nome_scheda:
                                   us_item.icon_db = "DECORATE_KEYFRAME"
                     emdb_list_index += 1    
       conn.close()
       return {'FINISHED'}    

class EMdb_type_menu(bpy.types.Menu):
    bl_label = "Custom Menu"
    bl_idname = "OBJECT_MT_EMdb_type_menu"

    def draw(self, context):
        layout = self.layout
        op = layout.operator("dbtype.set", text="EMdb")
        op.db_type = "EMdb"
        op = layout.operator("dbtype.set", text="Pyarchinit")
        op.db_type = "Pyarchinit"
       

classes = [
        EMdbListItem,
        EMdb_import_sqlite,
        EMdb_type_menu,
        OP_dbtypeset]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


    bpy.types.Scene.emdb_list = prop.CollectionProperty(type = EMdbListItem)
    bpy.types.Scene.emdb_list_index = prop.IntProperty(name = "Index for EMdb list", default = 0)
    bpy.types.Scene.current_db_type = prop.StringProperty(name = "Type of db connection", default = "EMdb")

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.emdb_list
    del bpy.types.Scene.emdb_list_index
    del bpy.types.Scene.current_db_type