import bpy
import xml.etree.ElementTree as ET
import os
import sys
import bpy.props as prop
import subprocess
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
    """If the button is grey, set the path to a DosCo folder in the EM setup panel above"""
    bl_idname = "open.file"
    bl_label = "Open a file using external software or a url using the default system browser"
    bl_options = {"REGISTER", "UNDO"}

    node_type: StringProperty()

    #@classmethod
    #def poll(cls, context):
        # The button works if DosCo and the url field are valorised
    #    return context.scene.EMDosCo_dir 

    def execute(self, context):
        scene = context.scene        
        file_res_path = eval("scene."+self.node_type+"[scene."+self.node_type+"_index].url")
        if is_valid_url(file_res_path): # nel caso nel nodo fonte ci sia una risorsa online
            print(file_res_path)
            bpy.ops.wm.url_open(url=file_res_path)

        else: # nel caso nel nodo fonte ci sia una risorsa locale
            basedir = bpy.path.abspath(scene.EMDosCo_dir)
            path_to_file = os.path.join(basedir, file_res_path)
            if os.path.exists(path_to_file):
                try:
                    if os.name == 'nt':  # Windows
                        os.startfile(path_to_file)
                    elif os.name == 'posix':  # macOS, Linux
                        opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
                        subprocess.run([opener, path_to_file])
                except Exception as e:
                    print("Error when opening the file:", e)
                    self.report({'WARNING'}, "Cannot open file: " + str(e))
                    return {'CANCELLED'}
            
        return {'FINISHED'}

# aggiungere icona con presenza autori: 'COMMUNITY' oppure assenza 'QUESTION'
