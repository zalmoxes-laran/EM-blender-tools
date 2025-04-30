import bpy
from bpy.types import Panel
from bpy.props import BoolProperty, StringProperty, EnumProperty
from .blender_pip import Pip

# Dictionary of required modules with minimum versions
REQUIRED_MODULES = {
    "pandas": "1.3.0",  # Minimum required version
    "numpy": "1.20.0",
    "networkx": "2.5.0",
    "openpyxl": "3.0.0",
    "pytz": "2020.1",
    "six": "1.15.0",
    "tzdata": "2022.7",
    "Pillow": "8.2.0",
    "matplotlib": "3.10.1",
    "contourpy": "1.0.1",
    "cycler": "0.10",
    "kiwisolver": "1.3.1",
    "pyparsing": "2.4.7",
    "python-dateutil": "2.8.1"
}

# Group modules into categories
MODULE_GROUPS = {
    "ALL": list(REQUIRED_MODULES.keys()),
    "EMdb_xlsx": ["pandas", "pytz", "numpy", "six", "openpyxl", "tzdata"],
    "NetworkX": ["networkx"],
    "Pillow": ["Pillow", "matplotlib", "numpy", "contourpy", "cycler", "kiwisolver", "pyparsing", "python-dateutil", "six"]
}

class VIEW3D_PT_EM_MissingModules(Panel):
    bl_label = "EM Tools Dependencies"
    bl_idname = "VIEW3D_PT_EM_MissingModules"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM"
    bl_order = 0
    
    @classmethod
    def poll(cls, context):
        # Verifica se le dipendenze sono mancanti
        try:
            # Controlla tutti i moduli richiesti
            missing_modules = []
            for module_name, min_version in REQUIRED_MODULES.items():
                try:
                    # Prima controlla nell'ambiente principale di Blender
                    main_version = cls.check_module_in_main_python(module_name)
                    
                    # Se esiste nell'ambiente principale, è sufficiente
                    if main_version:
                        if cls.is_version_sufficient(main_version, min_version):
                            continue
                    
                    # Controlla nell'ambiente dell'addon
                    addon_version = Pip.get_module_version(module_name)
                    
                    if not addon_version:
                        missing_modules.append(module_name)
                        continue
                        
                    # Controlla versione minima
                    if not cls.is_version_sufficient(addon_version, min_version):
                        missing_modules.append(module_name)
                        
                except (ImportError, AttributeError):
                    missing_modules.append(module_name)
            
            # Mostra il pannello se mancano moduli
            return len(missing_modules) > 0
            
        except ImportError:
            # Se c'è un problema nell'importazione, mostra il pannello
            return True
    
    @staticmethod
    def check_module_in_main_python(module_name):
        """Verifica se il modulo è già disponibile nell'ambiente Python principale di Blender"""
        try:
            import importlib
            import importlib.metadata
            try:
                # Per Python 3.8+
                return importlib.metadata.version(module_name)
            except (ImportError, AttributeError):
                # Fallback per versioni precedenti
                module = importlib.import_module(module_name)
                return getattr(module, "__version__", None)
        except (ImportError, ModuleNotFoundError):
            return None
    
    @staticmethod
    def is_version_sufficient(current_version, required_version):
        """Verifica se la versione corrente è sufficiente"""
        try:
            import pkg_resources
            return pkg_resources.parse_version(current_version) >= pkg_resources.parse_version(required_version)
        except (ImportError, AttributeError):
            # Semplice confronto se pkg_resources non è disponibile
            return current_version >= required_version
    
    def draw(self, context):
        layout = self.layout
        
        # Analisi dei moduli richiesti
        missing_modules = []
        outdated_modules = []
        installed_modules = []
        main_python_modules = []  # Moduli già disponibili in Blender
        
        for module_name, min_version in REQUIRED_MODULES.items():
            # Controlla prima se esiste nell'ambiente principale di Blender
            main_version = self.check_module_in_main_python(module_name)
            if main_version:
                if self.is_version_sufficient(main_version, min_version):
                    main_python_modules.append(f"{module_name} {main_version} (Blender)")
                    continue
            
            # Controlla nell'ambiente dell'addon
            try:
                module_version = Pip.get_module_version(module_name)
                
                if not module_version:
                    missing_modules.append(module_name)
                    continue
                    
                # Controlla versione minima
                if not self.is_version_sufficient(module_version, min_version):
                    outdated_modules.append(f"{module_name} (present: {module_version}, required: {min_version})")
                else:
                    installed_modules.append(f"{module_name} {module_version}")
                    
            except (ImportError, AttributeError):
                missing_modules.append(module_name)
        
        # Intestazione
        box = layout.box()
        
        # Moduli nell'ambiente principale di Blender
        if main_python_modules:
            box.label(text="Modules available in Blender", icon='CHECKMARK')
            for module in main_python_modules:
                box.label(text=f"• {module}")
        
        # Moduli mancanti o obsoleti
        if missing_modules or outdated_modules:
            if missing_modules:
                box = layout.box()
                box.label(text="Missing modules", icon='ERROR')
                for module in missing_modules:
                    box.label(text=f"• {module}")
            
            if outdated_modules:
                box = layout.box()
                box.label(text="Outdated modules", icon='ERROR')
                for module in outdated_modules:
                    box.label(text=f"• {module}")
                    
            # Opzioni di installazione
            box = layout.box()
            row = box.row()
            row.scale_y = 1.5  # Bottone più grande
            
            # Bottone per installare solo i moduli mancanti
            if missing_modules:
                op = row.operator("install_em_missing.modules", icon="PACKAGE", 
                                  text="Install missing modules")
                op.is_install = True
                op.install_only_missing = True
                op.module_group = "ALL"
                
            # Bottone per aggiornare i moduli obsoleti
            if outdated_modules:
                op = row.operator("install_em_missing.modules", icon="FILE_REFRESH", 
                                  text="Update outdated modules")
                op.is_install = True
                op.update_outdated = True
                op.module_group = "ALL"
        else:
            box.label(text="All required modules are installed", icon='CHECKMARK')
        
        # Moduli installati (espandibile)
        if installed_modules:
            box = layout.box()
            row = box.row()
            row.prop(context.scene, "em_deps_show_installed", 
                    text="Installed modules",
                    icon='TRIA_DOWN' if context.scene.em_deps_show_installed else 'TRIA_RIGHT',
                    emboss=False)
            
            if context.scene.em_deps_show_installed:
                for module in installed_modules:
                    box.label(text=f"• {module}")
        
        # Opzioni avanzate (espandibile)
        box = layout.box()
        row = box.row()
        row.prop(context.scene, "em_deps_advanced", 
                text="Advanced Options",
                icon='TRIA_DOWN' if context.scene.em_deps_advanced else 'TRIA_RIGHT',
                emboss=False)
        
        if context.scene.em_deps_advanced:
            # Opzione per scegliere dove installare i moduli
            box.prop(context.scene, "em_deps_install_location", text="Install Location")
            
            # Gruppi di moduli
            row = box.row()
            row.label(text="Module groups:")
            
            for group_name, module_list in MODULE_GROUPS.items():
                if group_name != "ALL":  # "ALL" è gestito sopra
                    row = box.row()
                    op = row.operator("install_em_missing.modules", text=f"Install {group_name}")
                    op.is_install = True
                    op.module_group = group_name
                    op.install_location = context.scene.em_deps_install_location
            
            # Disinstallazione
            row = box.row()
            row.label(text="Uninstalling:")
            
            row = box.row()
            row.prop(context.scene, "em_deps_module_to_remove", text="Module to remove")
            
            row = box.row()
            op = row.operator("install_em_missing.modules", text="Uninstall module", icon="TRASH")
            op.is_install = False
            op.module_group = "SINGLE"
            op.single_module = context.scene.em_deps_module_to_remove
            
            # Debug info
            row = box.row()
            row.operator("install_em_missing.debug_info", text="Show debug info", icon="CONSOLE")
            
            # Opzione per ignorare i moduli esistenti
            row = box.row()
            row.prop(context.scene, "em_deps_ignore_existing_modules", 
                    text="Skip modules available in Blender")
        
        # Avviso di riavvio
        box = layout.box()
        box.label(text="⚠️ Restart Blender after installation", icon='INFO')


# Operatore per installare/disinstallare moduli
class OBJECT_OT_install_em_missing_modules(bpy.types.Operator):
    bl_idname = "install_em_missing.modules"
    bl_label = "Install/Uninstall Modules"
    bl_options = {"REGISTER"}

    is_install: BoolProperty(
        name="Install",
        description="True to install, False to uninstall",
        default=True
    )
    
    module_group: EnumProperty(
        name="Module Group",
        items=[
            ("ALL", "All modules", "Install all required modules"),
            ("EMdb_xlsx", "EMdb_xlsx", "Modules for Excel import"),
            ("NetworkX", "NetworkX", "Modules for graph and network"),
            ("Pillow", "Pillow", "Modules for images"),
            ("SINGLE", "Single module", "Install a specific single module")
        ],
        default="ALL"
    )
    
    single_module: StringProperty(
        name="Module Name",
        description="Name of the single module to install/uninstall",
        default=""
    )
    
    install_location: EnumProperty(
        name="Install Location",
        items=[
            ("ADDON", "Addon lib folder", "Install in the addon's lib folder (isolated)"),
            ("BLENDER", "Blender Python", "Install in Blender's Python environment (shared)")
        ],
        default="ADDON"
    )
    
    install_only_missing: BoolProperty(
        name="Install Only Missing",
        description="Install only modules that are missing",
        default=False
    )
    
    update_outdated: BoolProperty(
        name="Update Outdated",
        description="Update only modules that are outdated",
        default=False
    )

    def execute(self, context):
        # Prepara la lista dei moduli da installare
        modules_to_process = []
        
        if self.module_group == "SINGLE":
            if self.single_module:
                modules_to_process = [self.single_module]
            else:
                self.report({'ERROR'}, "No module specified")
                return {'CANCELLED'}
        else:
            modules_to_process = MODULE_GROUPS.get(self.module_group, [])
        
        if not modules_to_process:
            self.report({'ERROR'}, f"No modules found for group {self.module_group}")
            return {'CANCELLED'}
        
        successful = 0
        failed = 0
        skipped = 0
        
        # Se stiamo installando solo moduli mancanti o aggiornando quelli obsoleti
        if self.is_install and (self.install_only_missing or self.update_outdated):
            filtered_modules = []
            
            for module in modules_to_process:
                min_version = REQUIRED_MODULES.get(module, None)
                
                # Controlla se esiste nell'ambiente principale di Blender
                main_version = VIEW3D_PT_EM_MissingModules.check_module_in_main_python(module)
                if main_version and VIEW3D_PT_EM_MissingModules.is_version_sufficient(main_version, min_version):
                    # Se è disponibile in Blender e dobbiamo ignorarlo, salta
                    if context.scene.em_deps_ignore_existing_modules:
                        continue
                
                # Controlla nell'ambiente dell'addon
                addon_version = Pip.get_module_version(module)
                
                if self.install_only_missing and not addon_version:
                    # Aggiungi solo se manca
                    filtered_modules.append(module)
                elif self.update_outdated and addon_version:
                    # Aggiungi solo se esiste ed è obsoleto
                    if min_version and not VIEW3D_PT_EM_MissingModules.is_version_sufficient(addon_version, min_version):
                        filtered_modules.append(module)
            
            modules_to_process = filtered_modules
            
            if not modules_to_process:
                self.report({'INFO'}, "No modules to process with current criteria")
                return {'FINISHED'}
        
        # Aggiorna pip all'inizio se stiamo installando
        if self.is_install:
            self.report({'INFO'}, "Updating pip...")
            pip_updated = Pip.upgrade_pip()
            if not pip_updated:
                self.report({'WARNING'}, "Pip update failed, attempting installation anyway")
        
        # Processo ogni modulo
        for module in modules_to_process:
            try:
                if self.is_install:
                    # Se dobbiamo ignorare i moduli esistenti in Blender
                    if context.scene.em_deps_ignore_existing_modules:
                        min_version = REQUIRED_MODULES.get(module, None)
                        main_version = VIEW3D_PT_EM_MissingModules.check_module_in_main_python(module)
                        
                        if main_version and VIEW3D_PT_EM_MissingModules.is_version_sufficient(main_version, min_version):
                            self.report({'INFO'}, f"Skipping {module} (available in Blender: {main_version})")
                            skipped += 1
                            continue
                    
                    min_version = REQUIRED_MODULES.get(module, None)
                    
                    # Scelta della location di installazione
                    use_user = self.install_location == "BLENDER"
                    
                    result, message, install_path = Pip.install(
                        module, 
                        upgrade=True, 
                        min_version=min_version,
                        use_user=use_user
                    )
                    
                    if result:
                        if "Already installed" in message:
                            self.report({'INFO'}, f"{module} already installed in {install_path}")
                            skipped += 1
                        else:
                            self.report({'INFO'}, f"Installed {module} in {install_path}")
                            successful += 1
                    else:
                        self.report({'ERROR'}, f"Error installing {module}: {message}")
                        failed += 1
                else:
                    # Per disinstallazione, scegli se disinstallare dall'ambiente utente
                    use_user = self.install_location == "BLENDER"
                    result, message = Pip.uninstall(module, use_user=use_user)
                    
                    if result:
                        self.report({'INFO'}, f"Uninstalled {module}")
                        successful += 1
                    else:
                        self.report({'ERROR'}, f"Error uninstalling {module}: {message}")
                        failed += 1
            
            except Exception as e:
                self.report({'ERROR'}, f"Error processing {module}: {str(e)}")
                failed += 1
        
        # Riepilogo delle operazioni
        action = "installation" if self.is_install else "uninstallation"
        location = "Blender Python" if self.install_location == "BLENDER" else "addon lib folder"
        
        if failed == 0:
            if skipped > 0:
                self.report({'INFO'}, f"{action.capitalize()} completed: {successful} modules processed, {skipped} skipped")
            else:
                self.report({'INFO'}, f"{action.capitalize()} completed: {successful} modules processed in {location}")
        else:
            self.report({'WARNING'}, f"{action.capitalize()} completed with errors: {successful} successes, {failed} failures")
        
        return {'FINISHED'}

# Operatore per mostrare info di debug
class OBJECT_OT_debug_em_modules(bpy.types.Operator):
    bl_idname = "install_em_missing.debug_info"
    bl_label = "Debug Information"
    bl_options = {"REGISTER"}
    
    def execute(self, context):
        Pip.debug_python_environment()
        self.report({'INFO'}, "Debug information printed to console")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="Debug information has been printed to the console.")
        layout.label(text="Open the console to view it (Window > Toggle System Console).")

def register():
    bpy.utils.register_class(VIEW3D_PT_EM_MissingModules)
    bpy.utils.register_class(OBJECT_OT_install_em_missing_modules)
    bpy.utils.register_class(OBJECT_OT_debug_em_modules)
    
    # Registra le proprietà
    bpy.types.Scene.em_deps_module_to_remove = StringProperty(
        name="Module to uninstall",
        default="pandas"
    )
    
    bpy.types.Scene.em_deps_show_installed = BoolProperty(
        name="Show installed modules",
        default=False
    )
    
    bpy.types.Scene.em_deps_advanced = BoolProperty(
        name="Advanced options",
        default=False
    )
    
    bpy.types.Scene.em_deps_install_location = EnumProperty(
        name="Install Location",
        items=[
            ("ADDON", "Addon lib folder", "Install in the addon's lib folder (isolated)"),
            ("BLENDER", "Blender Python", "Install in Blender's Python environment (shared)")
        ],
        default="ADDON"
    )
    
    bpy.types.Scene.em_deps_ignore_existing_modules = BoolProperty(
        name="Skip modules available in Blender",
        description="Don't install modules that are already available in Blender's Python",
        default=True
    )

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_debug_em_modules)
    bpy.utils.unregister_class(OBJECT_OT_install_em_missing_modules)
    bpy.utils.unregister_class(VIEW3D_PT_EM_MissingModules)
    
    # Rimuovi le proprietà
    del bpy.types.Scene.em_deps_ignore_existing_modules
    del bpy.types.Scene.em_deps_install_location
    del bpy.types.Scene.em_deps_module_to_remove
    del bpy.types.Scene.em_deps_show_installed
    del bpy.types.Scene.em_deps_advanced