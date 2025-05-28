import bpy
import sqlite3
import bpy.props as prop
from .functions import EM_list_clear
from bpy.props import StringProperty, BoolProperty
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
           name="Building Technique",
           description="A description for this item",
           default="Empty")

    chronology: prop.StringProperty(
           name="Chronology",
           description="A chronology for this item",
           default="Empty")

    period: prop.StringProperty(
           name="period ",
           description="A period for this item",
           default="Empty")

    level_knowledge: prop.StringProperty(
           name="level_knowledge ",
           description="A level of knowledge for this item",
           default="Empty")

    icon: prop.StringProperty(
           name="code for icon",
           description="",
           default="RESTRICT_INSTANCED_ON")


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
       
       # Ottieni le impostazioni di concatenazione
       em_settings = bpy.context.window_manager.em_addon_settings
       concatena_tipo_us = getattr(em_settings, 'concatena_tipo_us', True)  # Default True per retrocompatibilità
       
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

                     for us_item in scene.em_list:
                            if us_item.name == nome_scheda:
                                   us_item.icon_db = "DECORATE_KEYFRAME"
                     emdb_list_index += 1

       elif self.db_type == "EMdb-usv":
              nome_tabella = 'USV_sheet'
              
              for row in documento.execute('SELECT * FROM '+nome_tabella):
                     nome_scheda = row[1]+str(row[0])
                     scene.emdb_list.add()
                     scene.emdb_list[emdb_list_index].name = nome_scheda
                     scene.emdb_list[emdb_list_index].description = str(row[8])
                     scene.emdb_list[emdb_list_index].chronology = str(row[9])+" - "+str(row[10])
                     scene.emdb_list[emdb_list_index].period = str(row[11])+" - "+str(row[12])
                     scene.emdb_list[emdb_list_index].level_knowledge = str(row[34])

                     for us_item in scene.em_list:
                            if us_item.name == nome_scheda:
                                   us_item.icon_db = "DECORATE_KEYFRAME"
                     emdb_list_index += 1

       elif self.db_type == "Pyarchinit":
              nome_tabella = 'us_table'
              for row in documento.execute('SELECT * FROM '+nome_tabella):
                     tipo_scheda = row[29] if row[29] else ""  # unita_tipo (colonna 29)
                     numero_scheda = str(row[3]) if row[3] is not None else ""  # us (colonna 3)
                     
                     # Scegli il nome della scheda in base alle impostazioni
                     if concatena_tipo_us and tipo_scheda:
                         nome_scheda = tipo_scheda + numero_scheda
                     else:
                         nome_scheda = numero_scheda
                     
                     # Debug: stampa per verificare
                     print(f"Pyarchinit: tipo='{tipo_scheda}', numero='{numero_scheda}', nome_finale='{nome_scheda}', concatena={concatena_tipo_us}")
                     
                     scene.emdb_list.add()
                     scene.emdb_list[emdb_list_index].name = nome_scheda
                     scene.emdb_list[emdb_list_index].description = str(row[4]) if row[4] else ""  # d_stratigrafica
                     scene.emdb_list[emdb_list_index].technics = str(row[5]) if row[5] else ""  # d_interpretativa

                     # Cerca corrispondenza nella lista EM sia con nome finale che con numero puro
                     for us_item in scene.em_list:
                         # Prova prima con il nome finale
                         if us_item.name == nome_scheda:
                             us_item.icon_db = "DECORATE_KEYFRAME"
                             print(f"Trovata corrispondenza esatta: {us_item.name} = {nome_scheda}")
                         # Se non trova corrispondenza e stiamo concatenando, prova anche con il numero puro
                         elif concatena_tipo_us and us_item.name == numero_scheda:
                             us_item.icon_db = "DECORATE_KEYFRAME"
                             print(f"Trovata corrispondenza con numero: {us_item.name} = {numero_scheda}")
                         # Se non stiamo concatenando, prova anche con tipo+numero
                         elif not concatena_tipo_us and tipo_scheda and us_item.name == (tipo_scheda + numero_scheda):
                             us_item.icon_db = "DECORATE_KEYFRAME"
                             print(f"Trovata corrispondenza con tipo+numero: {us_item.name} = {tipo_scheda + numero_scheda}")
                     
                     emdb_list_index += 1    
       
       conn.close()
       print(f"Importate {emdb_list_index} schede dal database {self.db_type}")
       return {'FINISHED'}    

class EMdb_type_menu(bpy.types.Menu):
    bl_label = "Custom Menu"
    bl_idname = "OBJECT_MT_EMdb_type_menu"

    def draw(self, context):
        layout = self.layout
        op = layout.operator("dbtype.set", text="EMdb")
        op.db_type = "EMdb"
        op = layout.operator("dbtype.set", text="EMdb-usv")
        op.db_type = "EMdb-usv"
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