# Aggiungi questo codice al file UI.py o crea un nuovo file chiamato dependency_panel.py

import bpy
from bpy.types import Panel
from .blender_pip import Pip

class VIEW3D_PT_EM_MissingModules(Panel):
    bl_label = "EM Tools Dependencies"
    bl_idname = "VIEW3D_PT_EM_MissingModules"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM"
    bl_order = 0  # Questo lo porrà in cima alla lista dei pannelli
    
    @classmethod
    def poll(cls, context):
        # Verifica se le dipendenze sono mancanti
        try:
            import pandas
            import networkx
            return False  # Non mostrare il pannello se i moduli sono già presenti
        except ImportError:
            return True  # Mostra il pannello solo se mancano i moduli
    
    def draw(self, context):
        layout = self.layout
        
        box = layout.box()
        box.label(text="Missing Dependencies", icon='ERROR')
        box.label(text="Some features are disabled")
        
        row = box.row()
        row.scale_y = 1.5  # Bottone più grande
        op = row.operator("install_em_missing.modules", icon="PACKAGE", text="Install All Dependencies")
        op.is_install = True
        op.list_modules_to_install = "ALL"
        
        box.label(text="This will install:")
        box.label(text="- pandas (for Excel import)")
        box.label(text="- networkx (for graph visualization)")
        
        box.separator()
        box.label(text="Restart Blender after installation")

# Aggiungi questa classe e modifica l'operatore esistente

class OBJECT_OT_install_em_missing_modules(bpy.types.Operator):
    bl_idname = "install_em_missing.modules"
    bl_label = "Install Missing Modules"
    bl_options = {"REGISTER", "UNDO"}

    is_install: bpy.props.BoolProperty()
    list_modules_to_install: bpy.props.StringProperty()

    def execute(self, context):
        if self.list_modules_to_install == "ALL":
            # Installa tutti i moduli necessari
            modules = ["pandas", "pytz", "python-dateutil", "numpy", "six", 
                      "openpyxl", "webdavclient3", "lxml", "networkx"]
        elif self.list_modules_to_install == "EMdb_xlsx":
            modules = ["pandas", "pytz", "python-dateutil", "numpy", "six", 
                      "openpyxl", "webdavclient3", "lxml"]
        elif self.list_modules_to_install == "NetworkX":
            modules = ["networkx"]
        else:
            self.report({'ERROR'}, "Unknown module group")
            return {'CANCELLED'}
            
        if self.is_install:
            try:
                Pip.upgrade_pip()
                for module in modules:
                    result = Pip.install(module)
                    self.report({'INFO'}, f"Installing {module}: {'Success' if result[0] else 'Failed'}")
                
                self.report({'INFO'}, "Installation complete. Please restart Blender.")
                return {'FINISHED'}
            except Exception as e:
                self.report({'ERROR'}, f"Installation error: {str(e)}")
                return {'CANCELLED'}
        
        return {'FINISHED'}

# Aggiungi la classe al registro nell'__init__.py

def register():
    bpy.utils.register_class(VIEW3D_PT_EM_MissingModules)
    bpy.utils.register_class(OBJECT_OT_install_em_missing_modules)
    # resto del codice di registrazione

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_install_em_missing_modules)
    bpy.utils.unregister_class(VIEW3D_PT_EM_MissingModules)
    # resto del codice di deregistrazione