import bpy
from bpy.types import Panel, Operator
from bpy.props import BoolProperty, StringProperty, EnumProperty, FloatProperty
from .blender_pip import Pip
import threading
import time
import queue

# Dictionary of required modules with minimum versions
REQUIRED_MODULES = {
    "pandas": "1.3.0",
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

# Code delle comunicazioni tra thread e UI
installation_queue = queue.Queue()
result_queue = queue.Queue()

def worker_thread(modules_to_process, is_install=True, ignore_existing=True, min_versions=None):
    """Thread di lavoro che gestisce l'installazione/disinstallazione dei moduli"""
    successful = 0
    failed = 0
    skipped = 0
    total = len(modules_to_process)
    
    # Aggiorna pip all'inizio se stiamo installando
    if is_install:
        installation_queue.put(("STATUS", f"Updating pip...", 0, total))
        pip_updated = Pip.upgrade_pip()
        if not pip_updated:
            installation_queue.put(("WARNING", "Pip update failed, attempting installation anyway", 0, total))
    
    # Processo ogni modulo
    for idx, module in enumerate(modules_to_process, 1):
        try:
            if is_install:
                # Se dobbiamo ignorare i moduli esistenti in Blender
                if ignore_existing:
                    min_version = min_versions.get(module, None) if min_versions else None
                    main_version = check_module_in_main_python(module)
                    
                    if main_version and is_version_sufficient(main_version, min_version):
                        installation_queue.put(("INFO", f"Skipping {module} (available in Blender: {main_version})", idx, total))
                        skipped += 1
                        continue
                
                min_version = min_versions.get(module, None) if min_versions else None
                
                # Aggiorna stato
                installation_queue.put(("STATUS", f"Installing {module}...", idx, total))
                
                # Installa modulo
                result, message, install_path = Pip.install(
                    module, 
                    upgrade=True, 
                    min_version=min_version
                )
                
                if result:
                    if "Already installed" in message:
                        installation_queue.put(("INFO", f"{module} already installed in {install_path}", idx, total))
                        skipped += 1
                    else:
                        installation_queue.put(("INFO", f"Installed {module} in {install_path}", idx, total))
                        successful += 1
                else:
                    installation_queue.put(("ERROR", f"Error installing {module}: {message}", idx, total))
                    failed += 1
            else:
                # Aggiorna stato
                installation_queue.put(("STATUS", f"Uninstalling {module}...", idx, total))
                
                # Disinstalla modulo
                result, message = Pip.uninstall(module)
                
                if result:
                    installation_queue.put(("INFO", f"Uninstalled {module}", idx, total))
                    successful += 1
                else:
                    installation_queue.put(("ERROR", f"Error uninstalling {module}: {message}", idx, total))
                    failed += 1
            
        except Exception as e:
            installation_queue.put(("ERROR", f"Error processing {module}: {str(e)}", idx, total))
            failed += 1
    
    # Riepilogo delle operazioni
    action = "installation" if is_install else "uninstallation"
    
    if failed == 0:
        if skipped > 0:
            installation_queue.put(("SUMMARY", f"{action.capitalize()} completed: {successful} modules processed, {skipped} skipped", total, total))
        else:
            installation_queue.put(("SUMMARY", f"{action.capitalize()} completed: {successful} modules processed", total, total))
    else:
        installation_queue.put(("WARNING", f"{action.capitalize()} completed with errors: {successful} successes, {failed} failures", total, total))
    
    # Segnala completamento
    installation_queue.put(("DONE", "", total, total))

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

def is_version_sufficient(current_version, required_version):
    """Verifica se la versione corrente è sufficiente"""
    if not current_version or not required_version:
        return False
        
    try:
        import pkg_resources
        return pkg_resources.parse_version(current_version) >= pkg_resources.parse_version(required_version)
    except (ImportError, AttributeError):
        # Semplice confronto se pkg_resources non è disponibile
        return current_version >= required_version

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
                    main_version = check_module_in_main_python(module_name)
                    
                    # Se esiste nell'ambiente principale, è sufficiente
                    if main_version:
                        if is_version_sufficient(main_version, min_version):
                            continue
                    
                    # Controlla nell'ambiente dell'addon
                    addon_version = Pip.get_module_version(module_name)
                    
                    if not addon_version:
                        missing_modules.append(module_name)
                        continue
                        
                    # Controlla versione minima
                    if not is_version_sufficient(addon_version, min_version):
                        missing_modules.append(module_name)
                        
                except (ImportError, AttributeError):
                    missing_modules.append(module_name)
            
            # Mostra il pannello se mancano moduli o se c'è un processo in corso
            return len(missing_modules) > 0 or hasattr(context.window_manager, "em_installation_in_progress")
            
        except ImportError:
            # Se c'è un problema nell'importazione, mostra il pannello
            return True
    
    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        
        # Verifica se un'installazione è in corso
        if hasattr(wm, "em_installation_in_progress") and wm.em_installation_in_progress:
            # Mostra la barra di progresso e lo stato
            box = layout.box()
            
            # Informazioni sull'installazione in corso
            box.label(text=f"Installing: {wm.em_current_operation}", icon='INFO')
            
            # Barra di progresso
            row = box.row()
            row.prop(wm, "em_installation_progress", text="")
            
            # Pulsante per annullare
            row = box.row()
            row.operator("em.cancel_installation", text="Cancel", icon='X')
            
            # Se ci sono messaggi recenti, mostrali
            if hasattr(wm, "em_installation_message") and wm.em_installation_message:
                box.label(text=wm.em_installation_message)
            
            return
        
        # Analisi dei moduli richiesti (quando non c'è un'installazione in corso)
        missing_modules = []
        outdated_modules = []
        installed_modules = []
        main_python_modules = []  # Moduli già disponibili in Blender
        
        for module_name, min_version in REQUIRED_MODULES.items():
            # Controlla prima se esiste nell'ambiente principale di Blender
            main_version = check_module_in_main_python(module_name)
            if main_version:
                if is_version_sufficient(main_version, min_version):
                    main_python_modules.append(f"{module_name} {main_version} (Blender)")
                    continue
            
            # Controlla nell'ambiente dell'addon
            try:
                module_version = Pip.get_module_version(module_name)
                
                if not module_version:
                    missing_modules.append(module_name)
                    continue
                    
                # Controlla versione minima
                if not is_version_sufficient(module_version, min_version):
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
                op = row.operator("em.install_modules_background", icon="PACKAGE", 
                                 text="Install missing modules")
                op.is_install = True
                op.install_only_missing = True
                op.module_group = "ALL"
                
            # Bottone per aggiornare i moduli obsoleti
            if outdated_modules:
                op = row.operator("em.install_modules_background", icon="FILE_REFRESH", 
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
            # Gruppi di moduli
            row = box.row()
            row.label(text="Module groups:")
            
            for group_name, module_list in MODULE_GROUPS.items():
                if group_name != "ALL":  # "ALL" è gestito sopra
                    row = box.row()
                    op = row.operator("em.install_modules_background", text=f"Install {group_name}")
                    op.is_install = True
                    op.module_group = group_name
            
            # Disinstallazione
            row = box.row()
            row.label(text="Uninstalling:")
            
            row = box.row()
            row.prop(context.scene, "em_deps_module_to_remove", text="Module to remove")
            
            row = box.row()
            op = row.operator("em.install_modules_background", text="Uninstall module", icon="TRASH")
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

# Operatore per installare/disinstallare moduli in background
class OBJECT_OT_install_modules_background(Operator):
    bl_idname = "em.install_modules_background"
    bl_label = "Install/Uninstall Modules (Background)"
    bl_description = "Install or uninstall Python modules in the background"
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
    
    list_modules_to_install: StringProperty(
        name="List of modules",
        description="For backward compatibility",
        default=""
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
        wm = context.window_manager
        
        # Verifica che non ci sia già un processo in corso
        if hasattr(wm, "em_installation_in_progress") and wm.em_installation_in_progress:
            self.report({'WARNING'}, "An installation is already in progress")
            return {'CANCELLED'}
        
        # Prepara la lista dei moduli da installare
        modules_to_process = []
        
        if self.module_group == "SINGLE":
            if self.single_module:
                modules_to_process = [self.single_module]
            else:
                self.report({'ERROR'}, "No module specified")
                return {'CANCELLED'}
        else:
            # Compatibilità con versioni precedenti
            if self.list_modules_to_install:
                if self.list_modules_to_install == "EMdb_xlsx":
                    modules_to_process = MODULE_GROUPS["EMdb_xlsx"]
                elif self.list_modules_to_install == "NetworkX":
                    modules_to_process = MODULE_GROUPS["NetworkX"]
                elif self.list_modules_to_install == "Pillow":
                    modules_to_process = MODULE_GROUPS["Pillow"]
                else:
                    modules_to_process = MODULE_GROUPS["ALL"]
            else:
                modules_to_process = MODULE_GROUPS.get(self.module_group, [])
        
        if not modules_to_process:
            self.report({'ERROR'}, f"No modules found for group {self.module_group}")
            return {'CANCELLED'}
        
        # Se stiamo installando solo moduli mancanti o aggiornando quelli obsoleti
        if self.is_install and (self.install_only_missing or self.update_outdated):
            filtered_modules = []
            
            for module in modules_to_process:
                min_version = REQUIRED_MODULES.get(module, None)
                
                # Controlla se esiste nell'ambiente principale di Blender
                main_version = check_module_in_main_python(module)
                if main_version and is_version_sufficient(main_version, min_version):
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
                    if min_version and not is_version_sufficient(addon_version, min_version):
                        filtered_modules.append(module)
            
            modules_to_process = filtered_modules
            
            if not modules_to_process:
                self.report({'INFO'}, "No modules to process with current criteria")
                return {'FINISHED'}
        
        # Svuota le code dei messaggi
        while not installation_queue.empty():
            installation_queue.get()
            
        while not result_queue.empty():
            result_queue.get()
        
        # Inizializza le proprietà dell'installazione in corso
        action = "Installing" if self.is_install else "Uninstalling"
        module_desc = self.module_group if self.module_group != "SINGLE" else self.single_module
        
        # Registra le proprietà per il monitoraggio dell'installazione
        wm.em_installation_in_progress = True
        wm.em_current_operation = f"{action} {module_desc}"
        wm.em_installation_progress = 0.0
        wm.em_installation_message = f"Starting {action.lower()} {module_desc}"
        
        # Avvia il thread di installazione
        install_thread = threading.Thread(
            target=worker_thread,
            args=(modules_to_process, self.is_install, context.scene.em_deps_ignore_existing_modules, REQUIRED_MODULES)
        )
        install_thread.daemon = True
        install_thread.start()
        
        # Avvia il timer per le verifiche di stato
        bpy.app.timers.register(self.check_installation_status)
        
        return {'FINISHED'}
    
    def check_installation_status(self):
        """Timer per verificare lo stato dell'installazione"""
        wm = bpy.context.window_manager
        
        # Verifica se ci sono messaggi dalla queue
        try:
            # Processa tutti i messaggi disponibili
            messages_processed = 0
            max_messages_per_tick = 5  # Limita il numero di messaggi processati per tick
            
            while not installation_queue.empty() and messages_processed < max_messages_per_tick:
                msg_type, message, current, total = installation_queue.get_nowait()
                messages_processed += 1
                
                # Aggiorna la barra di progresso
                if total > 0:
                    wm.em_installation_progress = current / total
                
                # Gestisci i messaggi
                if msg_type == "STATUS":
                    wm.em_installation_message = message
                elif msg_type in ["INFO", "WARNING", "ERROR"]:
                    print(f"{msg_type}: {message}")
                    wm.em_installation_message = message
                elif msg_type == "SUMMARY":
                    wm.em_installation_message = message
                elif msg_type == "DONE":
                    # L'installazione è completata
                    wm.em_installation_in_progress = False
                    
                    # Aggiorna l'interfaccia un'ultima volta
                    for area in bpy.context.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
                    
                    # Termina il timer
                    return None
            
            # Forza l'aggiornamento dell'interfaccia solo se sono stati processati messaggi
            if messages_processed > 0:
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
                
        except queue.Empty:
            pass
        
        # Continua a controllare ogni 0.5 secondi (valore ottimizzato)
        return 0.5  # Aumentato da 0.1 a 0.5 secondi

# Operatore per annullare l'installazione
class OBJECT_OT_cancel_installation(Operator):
    bl_idname = "em.cancel_installation"
    bl_label = "Cancel Installation"
    bl_description = "Cancel the current module installation"
    bl_options = {"REGISTER"}
    
    def execute(self, context):
        wm = context.window_manager
        
        if hasattr(wm, "em_installation_in_progress"):
            wm.em_installation_in_progress = False
            wm.em_installation_message = "Installation cancelled by user"
            
            # Rimuovi il timer se presente
            if bpy.app.timers.is_registered(OBJECT_OT_install_modules_background.check_installation_status):
                bpy.app.timers.unregister(OBJECT_OT_install_modules_background.check_installation_status)
        
        self.report({'INFO'}, "Installation cancelled")
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
    # Registra le proprietà della finestra per monitorare l'installazione
    bpy.types.WindowManager.em_installation_in_progress = bpy.props.BoolProperty(default=False)
    bpy.types.WindowManager.em_current_operation = bpy.props.StringProperty(default="")
    bpy.types.WindowManager.em_installation_progress = bpy.props.FloatProperty(
        default=0.0, min=0.0, max=1.0, subtype='PERCENTAGE')
    bpy.types.WindowManager.em_installation_message = bpy.props.StringProperty(default="")
    
    # Registra le classi degli operatori e del pannello
    bpy.utils.register_class(VIEW3D_PT_EM_MissingModules)
    bpy.utils.register_class(OBJECT_OT_install_modules_background)
    bpy.utils.register_class(OBJECT_OT_cancel_installation)
    bpy.utils.register_class(OBJECT_OT_debug_em_modules)
    
    # Registra le proprietà della scena
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
    
    bpy.types.Scene.em_deps_ignore_existing_modules = BoolProperty(
        name="Skip modules available in Blender",
        description="Don't install modules that are already available in Blender's Python",
        default=True
    )

def unregister():
    # Rimuovi le proprietà della finestra
    del bpy.types.WindowManager.em_installation_message
    del bpy.types.WindowManager.em_installation_progress
    del bpy.types.WindowManager.em_current_operation
    del bpy.types.WindowManager.em_installation_in_progress
    
    # Rimuovi le proprietà della scena
    del bpy.types.Scene.em_deps_ignore_existing_modules
    del bpy.types.Scene.em_deps_module_to_remove
    del bpy.types.Scene.em_deps_show_installed
    del bpy.types.Scene.em_deps_advanced
    
    # Rimuovi il timer se ancora attivo
    if bpy.app.timers.is_registered(OBJECT_OT_install_modules_background.check_installation_status):
        bpy.app.timers.unregister(OBJECT_OT_install_modules_background.check_installation_status)
    
    # Rimuovi le classi
    bpy.utils.unregister_class(OBJECT_OT_debug_em_modules)
    bpy.utils.unregister_class(OBJECT_OT_cancel_installation)
    bpy.utils.unregister_class(OBJECT_OT_install_modules_background)
    bpy.utils.unregister_class(VIEW3D_PT_EM_MissingModules)