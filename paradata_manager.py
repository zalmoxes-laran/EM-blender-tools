import bpy
import xml.etree.ElementTree as ET
import os
import bpy.props as prop

from bpy.props import (BoolProperty,
                       FloatProperty,
                       StringProperty,
                       EnumProperty,
                       CollectionProperty,
                       IntProperty,
                       PointerProperty,
                       FloatVectorProperty,
                       )

from bpy.types import (
        AddonPreferences,
        PropertyGroup,
        )

from .functions import *

#### da qui si definiscono le funzioni e gli operatori

class EM_files_opener(bpy.types.Operator):
    bl_idname = "open.file"
    bl_label = "Open file using external software"
    bl_options = {"REGISTER", "UNDO"}

    node_type: StringProperty()

    def execute(self, context):
        scene = context.scene
        
        #basedir = os.path.dirname(scene.EM_file)
        #basedir = os.path.dirname(scene.EM_file)
        basedir = bpy.path.abspath(scene.EMDosCo_dir)
        #doc_file_path = bpy.path.abspath(os.path.join(dir_path, entry))

        #print(basedir)

        file_res_path = eval("scene."+self.node_type+"[scene."+self.node_type+"_index].url")
        path_to_file = os.path.join(basedir,file_res_path)
        if os.path.exists(path_to_file):
            #print(path_to_file)
            bpy.ops.wm.url_open(url=path_to_file)
            #os.open(path_to_file)
            #print(path_to_file)
            #from urllib.request import urlopen
            #urlopen(path_to_file)
            #import subprocess
            #subprocess.run(path_to_file, shell=True)
        return {'FINISHED'}

# aggiungere icona con presenza autori: 'COMMUNITY' oppure assenza 'QUESTION'
