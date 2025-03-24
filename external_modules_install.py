import os
import bpy # type: ignore
from bpy.types import Operator # type: ignore
from bpy.props import BoolProperty, StringProperty # type: ignore
import subprocess
import sys
import importlib

from .blender_pip import Pip

def check_external_modules():
    """Verifica e mostra lo stato dei moduli esterni richiesti"""
    try:
        # Controlla pandas
        has_pandas = Pip.is_module_installed("pandas")
        pandas_version = Pip.get_module_version("pandas") if has_pandas else None
        
        # Controlla networkx
        has_networkx = Pip.is_module_installed("networkx")
        networkx_version = Pip.get_module_version("networkx") if has_networkx else None

        # Controlla networkx
        has_pillow = Pip.is_module_installed("PIL")
        pillow_version = Pip.get_module_version("PIL") if has_pillow else None

        # Aggiorna le preferenze dell'addon
        user_preferences = bpy.context.preferences
        addon_prefs = user_preferences.addons.get(__package__, None)
        if addon_prefs and hasattr(addon_prefs, 'preferences'):
            addon_prefs.preferences.is_external_module = has_pandas and has_networkx
        
        # Stampa lo stato di debug
        print("\n=== External Modules Status ===")
        print(f"pandas: {'Installato (v' + pandas_version + ')' if has_pandas else 'Non installato'}")
        print(f"networkx: {'Installato (v' + networkx_version + ')' if has_networkx else 'Non installato'}")
        print(f"pillow: {'Installato (v' + pillow_version + ')' if has_pillow else 'Non installato'}")
        print("===============================\n")

        # Restituisce True se entrambi i moduli sono disponibili
        return has_pandas and has_networkx and has_pillow
        
    except Exception as e:
        print(f"Errore durante la verifica dei moduli esterni: {e}")
        return False

class OBJECT_OT_install_external_modules(Operator):
    """Installa/disinstalla moduli esterni per EM Tools"""
    bl_idname = "emtools.install_external_modules"
    bl_label = "Install/Uninstall External Modules"
    bl_description = "Install or uninstall required external Python modules"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    is_install: BoolProperty(name="Install", default=True) # type: ignore
    module_name: StringProperty(name="Module Name", default="pandas") # type: ignore
    
    def execute(self, context):
        try:
            if self.is_install:
                # Installa il modulo specificato
                success, message, install_path = Pip.install(self.module_name)
                if success:
                    self.report({'INFO'}, f"Successfully installed {self.module_name} in {install_path}")
                else:
                    self.report({'ERROR'}, f"Failed to install {self.module_name}: {message}")
            else:
                # Disinstalla il modulo specificato
                success, message = Pip.uninstall(self.module_name)
                if success:
                    self.report({'INFO'}, f"Successfully uninstalled {self.module_name}")
                else:
                    self.report({'ERROR'}, f"Failed to uninstall {self.module_name}: {message}")
            
            # Aggiorna lo stato dei moduli
            #check_external_modules()
            
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)}")
            return {'CANCELLED'}

def register():
    bpy.utils.register_class(OBJECT_OT_install_external_modules)
    check_external_modules()
    
def unregister():
    bpy.utils.unregister_class(OBJECT_OT_install_external_modules)