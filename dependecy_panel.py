import bpy # type: ignore
from bpy.types import Panel # type: ignore
from bpy.props import BoolProperty, StringProperty, EnumProperty # type: ignore
from .blender_pip import Pip

# Dictionary of required modules with minimum versions
REQUIRED_MODULES = {
    "pandas": "1.3.0",  # Minima versione richiesta
    "numpy": "1.20.0",
    "networkx": "2.5.0",
    "openpyxl": "3.0.0",
    "pytz": "2020.1",
    "python-dateutil": "2.8.1",
    "six": "1.15.0",
    "tzdata": "2021.1"
}

# Group modules into categories
MODULE_GROUPS = {
    "ALL": list(REQUIRED_MODULES.keys()),
    "EMdb_xlsx": ["pandas", "pytz", "python-dateutil", "numpy", "six", "openpyxl", "tzdata"],
    "NetworkX": ["networkx"]
}

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
            # Controlla tutti i moduli richiesti
            missing_modules = []
            for module_name, min_version in REQUIRED_MODULES.items():
                try:
                    module_version = Pip.get_module_version(module_name)
                    
                    if not module_version:
                        missing_modules.append(module_name)
                        continue
                        
                    # Controlla versione minima
                    import pkg_resources
                    if pkg_resources.parse_version(module_version) < pkg_resources.parse_version(min_version):
                        missing_modules.append(module_name)
                        
                except (ImportError, AttributeError):
                    missing_modules.append(module_name)
            
            # Mostra il pannello se mancano moduli
            return len(missing_modules) > 0
            
        except ImportError:
            # Se c'è un problema nell'importazione, mostra il pannello
            return True
    
    def draw(self, context):
        layout = self.layout
        
        # Controllo moduli
        missing_modules = []
        installed_modules = []
        
        for module_name, min_version in REQUIRED_MODULES.items():
            try:
                module_version = Pip.get_module_version(module_name)
                
                if not module_version:
                    missing_modules.append(module_name)
                    continue
                    
                # Controlla versione minima
                import pkg_resources
                if pkg_resources.parse_version(module_version) < pkg_resources.parse_version(min_version):
                    missing_modules.append(f"{module_name} (attuale: {module_version}, richiesta: {min_version})")
                else:
                    installed_modules.append(f"{module_name} {module_version}")
                    
            except (ImportError, AttributeError):
                missing_modules.append(module_name)
        
        # Intestazione
        box = layout.box()
        if missing_modules:
            box.label(text="Moduli mancanti o obsoleti", icon='ERROR')
            
            for module in missing_modules:
                box.label(text=f"• {module}")
                
            row = box.row()
            row.scale_y = 1.5  # Bottone più grande
            
            # Bottone per installare tutto
            if len(missing_modules) > 1:
                op = row.operator("install_em_missing.modules", icon="PACKAGE", text="Installa tutti i moduli")
                op.is_install = True
                op.module_group = "ALL"
            else:
                module_name = missing_modules[0].split(" ")[0]  # Estrai solo il nome del modulo
                op = row.operator("install_em_missing.modules", icon="PACKAGE", text=f"Installa {module_name}")
                op.is_install = True
                op.module_group = "SINGLE"
                op.single_module = module_name
        else:
            box.label(text="Tutti i moduli richiesti sono installati", icon='CHECKMARK')
        
        # Moduli installati (espandibile)
        if installed_modules:
            box = layout.box()
            row = box.row()
            row.prop(context.scene, "em_deps_show_installed", 
                    text="Moduli installati",
                    icon='TRIA_DOWN' if context.scene.em_deps_show_installed else 'TRIA_RIGHT',
                    emboss=False)
            
            if context.scene.em_deps_show_installed:
                for module in installed_modules:
                    box.label(text=f"• {module}")
        
        # Opzioni avanzate (espandibile)
        box = layout.box()
        row = box.row()
        row.prop(context.scene, "em_deps_advanced", 
                text="Opzioni avanzate",
                icon='TRIA_DOWN' if context.scene.em_deps_advanced else 'TRIA_RIGHT',
                emboss=False)
        
        if context.scene.em_deps_advanced:
            # Gruppi di moduli
            row = box.row()
            row.label(text="Gruppi di moduli:")
            
            for group_name, module_list in MODULE_GROUPS.items():
                if group_name != "ALL":  # "ALL" è gestito sopra
                    row = box.row()
                    op = row.operator("install_em_missing.modules", text=f"Installa gruppo {group_name}")
                    op.is_install = True
                    op.module_group = group_name
            
            # Disinstallazione
            row = box.row()
            row.label(text="Disinstallazione:")
            
            row = box.row()
            row.prop(context.scene, "em_deps_module_to_remove", text="Modulo")
            
            row = box.row()
            op = row.operator("install_em_missing.modules", text="Disinstalla modulo", icon="TRASH")
            op.is_install = False
            op.module_group = "SINGLE"
            op.single_module = context.scene.em_deps_module_to_remove
            
            # Debug info
            row = box.row()
            row.operator("install_em_missing.debug_info", text="Mostra info di debug", icon="CONSOLE")
        
        # Avviso di riavvio
        box = layout.box()
        box.label(text="⚠️ Riavvia Blender dopo l'installazione", icon='INFO')

# Operatore per installare/disinstallare moduli
class OBJECT_OT_install_em_missing_modules(bpy.types.Operator):
    bl_idname = "install_em_missing.modules"
    bl_label = "Installa/Disinstalla Moduli"
    bl_options = {"REGISTER"}

    is_install: BoolProperty(
        name="Installa",
        description="True per installare, False per disinstallare",
        default=True
    ) # type: ignore
    
    module_group: EnumProperty(
        name="Gruppo di moduli",
        items=[
            ("ALL", "Tutti i moduli", "Installa tutti i moduli necessari"),
            ("EMdb_xlsx", "EMdb_xlsx", "Moduli per importazione Excel"),
            ("NetworkX", "NetworkX", "Moduli per grafica e rete"),
            ("SINGLE", "Singolo modulo", "Installa un singolo modulo specifico")
        ],
        default="ALL"
    ) # type: ignore
    
    single_module: StringProperty(
        name="Nome modulo",
        description="Nome del modulo singolo da installare/disinstallare",
        default=""
    ) # type: ignore

    def execute(self, context):
        # Prepara la lista dei moduli da installare
        modules_to_process = []
        
        if self.module_group == "SINGLE":
            if self.single_module:
                modules_to_process = [self.single_module]
            else:
                self.report({'ERROR'}, "Nessun modulo specificato")
                return {'CANCELLED'}
        else:
            modules_to_process = MODULE_GROUPS.get(self.module_group, [])
        
        if not modules_to_process:
            self.report({'ERROR'}, f"Nessun modulo trovato per il gruppo {self.module_group}")
            return {'CANCELLED'}
        
        successful = 0
        failed = 0
        skipped = 0
        
        # Aggiorna pip all'inizio se stiamo installando
        if self.is_install:
            self.report({'INFO'}, "Aggiornamento di pip...")
            pip_updated = Pip.upgrade_pip()
            if not pip_updated:
                self.report({'WARNING'}, "Aggiornamento di pip fallito, si tenta l'installazione comunque")
        
        # Processo ogni modulo
        for module in modules_to_process:
            try:
                if self.is_install:
                    min_version = REQUIRED_MODULES.get(module, None)
                    result, message, install_path = Pip.install(module, upgrade=True, min_version=min_version)
                    
                    if result:
                        if "Already installed" in message:
                            self.report({'INFO'}, f"{module} già installato in {install_path}")
                            skipped += 1
                        else:
                            self.report({'INFO'}, f"Installato {module} in {install_path}")
                            successful += 1
                    else:
                        self.report({'ERROR'}, f"Errore installando {module}: {message}")
                        failed += 1
                else:
                    result, message = Pip.uninstall(module)
                    
                    if result:
                        self.report({'INFO'}, f"Disinstallato {module}")
                        successful += 1
                    else:
                        self.report({'ERROR'}, f"Errore disinstallando {module}: {message}")
                        failed += 1
            
            except Exception as e:
                self.report({'ERROR'}, f"Errore processando {module}: {str(e)}")
                failed += 1
        
        # Riepilogo delle operazioni
        action = "installazione" if self.is_install else "disinstallazione"
        if failed == 0:
            if skipped > 0:
                self.report({'INFO'}, f"{action.capitalize()} completata: {successful} moduli elaborati, {skipped} già installati")
            else:
                self.report({'INFO'}, f"{action.capitalize()} completata: {successful} moduli elaborati")
        else:
            self.report({'WARNING'}, f"{action.capitalize()} completata con errori: {successful} successi, {failed} fallimenti")
        
        return {'FINISHED'}

# Operatore per mostrare info di debug
class OBJECT_OT_debug_em_modules(bpy.types.Operator):
    bl_idname = "install_em_missing.debug_info"
    bl_label = "Informazioni di Debug"
    bl_options = {"REGISTER"}
    
    def execute(self, context):
        Pip.debug_python_environment()
        self.report({'INFO'}, "Informazioni di debug stampate nella console")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="Le informazioni di debug sono state stampate nella console.")
        layout.label(text="Apri la console per visualizzarle (Window > Toggle System Console).")

def register():
    bpy.utils.register_class(VIEW3D_PT_EM_MissingModules)
    bpy.utils.register_class(OBJECT_OT_install_em_missing_modules)
    bpy.utils.register_class(OBJECT_OT_debug_em_modules)
    
    # Registra le proprietà in modo appropriato
    bpy.types.Scene.em_deps_module_to_remove = StringProperty(
        name="Modulo da disinstallare",
        default="pandas"
    )
    
    # Usa BoolProperty (già decorata con type: ignore)
    bpy.types.Scene.em_deps_show_installed = BoolProperty(
        name="Mostra moduli installati",
        default=False
    )
    
    bpy.types.Scene.em_deps_advanced = BoolProperty(
        name="Opzioni avanzate",
        default=False
    )

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_debug_em_modules)
    bpy.utils.unregister_class(OBJECT_OT_install_em_missing_modules)
    bpy.utils.unregister_class(VIEW3D_PT_EM_MissingModules)
    
    # Rimuovi le proprietà
    del bpy.types.Scene.em_deps_module_to_remove
    del bpy.types.Scene.em_deps_show_installed
    del bpy.types.Scene.em_deps_advanced