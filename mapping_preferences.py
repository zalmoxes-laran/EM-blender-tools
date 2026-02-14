"""
Mapping Preferences Module
Gestisce i percorsi personalizzati dei file di mapping.
Default: usa user_mappings dentro l'addon (portabile)
Avanzato: permette di puntare altrove (non portabile)
"""

import bpy
from bpy.types import AddonPreferences, Operator
from bpy.props import StringProperty, BoolProperty, EnumProperty, FloatVectorProperty, IntProperty
import os

import logging
log = logging.getLogger(__name__)


def get_addon_dir():
    """Ottiene la directory root dell'addon"""
    return os.path.dirname(os.path.realpath(__file__))


def get_default_user_mappings_path(mapping_type=''):
    """
    Ottiene il percorso di default per user_mappings.
    
    Args:
        mapping_type: 'emdb', 'pyarchinit', o '' per la root
        
    Returns:
        Path alla cartella user_mappings (o sottocartella)
    """
    addon_dir = get_addon_dir()
    user_mappings_dir = os.path.join(addon_dir, "user_mappings")
    
    if mapping_type:
        return os.path.join(user_mappings_dir, mapping_type)
    return user_mappings_dir


def ensure_user_mappings_exist():
    """Crea la struttura user_mappings se non esiste"""
    user_path = get_default_user_mappings_path()
    
    if not os.path.exists(user_path):
        try:
            os.makedirs(user_path)
            
            # Crea sottocartelle
            for subdir in ['emdb', 'pyarchinit']:
                subdir_path = os.path.join(user_path, subdir)
                os.makedirs(subdir_path, exist_ok=True)
                
                # Crea README
                readme_path = os.path.join(subdir_path, 'README.txt')
                with open(readme_path, 'w', encoding='utf-8') as f:
                    f.write(f"Place your custom {subdir} mapping JSON files here.\n")
                    f.write(f"They will be loaded automatically and have priority over built-in mappings.\n")
            
            # README principale
            readme_main = os.path.join(user_path, 'README.txt')
            with open(readme_main, 'w', encoding='utf-8') as f:
                f.write("EM Tools - User Custom Mappings\n")
                f.write("=" * 50 + "\n\n")
                f.write("This folder contains your custom mapping files.\n")
                f.write("These mappings are stored with your Blender installation\n")
                f.write("and will be available across all .blend files.\n\n")
                f.write("Subfolders:\n")
                f.write("  📁 emdb/        - EMdb Excel format mappings\n")
                f.write("  📁 pyarchinit/  - pyArchInit database mappings\n\n")
                f.write("Simply copy your .json mapping files to the appropriate folder.\n")
            
            log.info(f"✓ Created user_mappings structure: {user_path}")
        except Exception as e:
            log.error(f"Error creating user_mappings: {e}")
    
    return user_path


def resolve_path(path_string):
    """Risolve percorsi relativi Blender (//)"""
    if not path_string:
        return ""
    
    try:
        resolved = bpy.path.abspath(path_string)
        resolved = os.path.normpath(resolved)
        return resolved
    except Exception as e:
        log.warning(f"Error resolving path '{path_string}': {e}")
        return ""


def get_mapping_path(prefs, mapping_type):
    """
    Ottiene il percorso effettivo per un tipo di mapping.
    Se custom è vuoto o non valido, usa il default.
    
    Args:
        prefs: Addon preferences
        mapping_type: 'emdb' o 'pyarchinit'
        
    Returns:
        Percorso valido o None
    """
    custom_attr = f"custom_{mapping_type}_path"
    custom_path = getattr(prefs, custom_attr, "")
    
    if custom_path:
        # L'utente ha impostato un percorso custom
        resolved = resolve_path(custom_path)
        if resolved and os.path.exists(resolved):
            return resolved
        else:
            log.warning(f"Custom {mapping_type} path not valid: {custom_path}")
    
    # Fallback al default (user_mappings dentro addon)
    default_path = get_default_user_mappings_path(mapping_type)
    if os.path.exists(default_path):
        return default_path
    
    return None


class EMToolsMappingPreferences(AddonPreferences):
    """Preferenze per i percorsi di mapping personalizzati"""
    bl_idname = __package__
    
    # Modalità semplice/avanzata
    show_advanced: BoolProperty(
        name="Show Advanced Settings",
        description="Show advanced path configuration (for non-portable setups)",
        default=False
    )
    
    # Percorsi custom (opzionali - default è user_mappings interno)
    custom_emdb_path: StringProperty(
        name="EMdb Mappings Path",
        description="Leave empty to use default user_mappings folder (recommended for portability)",
        subtype='DIR_PATH',
        default="",
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set(),
        update=lambda self, context: update_mapping_path(self, context, 'emdb')
    )

    custom_pyarchinit_path: StringProperty(
        name="pyArchInit Mappings Path",
        description="Leave empty to use default user_mappings folder (recommended for portability)",
        subtype='DIR_PATH',
        default="",
        options={'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set(),
        update=lambda self, context: update_mapping_path(self, context, 'pyarchinit')
    )
    
    # Flag inizializzazione
    mappings_initialized: BoolProperty(
        name="Mappings Initialized",
        default=False
    )

    # ===== VIEWPORT OVERLAY SETTINGS =====
    overlay_epoch_color: FloatVectorProperty(
        name="Epoch Color",
        description="Color for the epoch name in the viewport overlay",
        subtype='COLOR',
        default=(0.3, 0.5, 1.0),  # Blue
        min=0.0, max=1.0,
        size=3
    )

    overlay_us_color: FloatVectorProperty(
        name="US Color",
        description="Color for the US name in the viewport overlay",
        subtype='COLOR',
        default=(1.0, 0.7, 0.2),  # Ochre/Yellow
        min=0.0, max=1.0,
        size=3
    )

    overlay_font_size: IntProperty(
        name="Font Size",
        description="Size of the overlay text",
        default=22,  # Changed from 16
        min=10,
        max=48
    )

    overlay_position_mode: EnumProperty(
        name="Position Mode",
        description="How to position the overlay text",
        items=[
            ('TOP_CENTER', "Top Center", "Center at the top of the viewport"),
            ('TOP_LEFT', "Top Left", "Top left corner of the viewport"),
            ('CUSTOM', "Custom", "Use custom X/Y offset values"),
        ],
        default='TOP_LEFT'  # Changed from TOP_CENTER
    )

    overlay_offset_x: IntProperty(
        name="X Offset",
        description="Horizontal offset from the base position (pixels)",
        default=300,  # Changed from 0
        min=-1000,
        max=1000
    )

    overlay_offset_y: IntProperty(
        name="Y Offset",
        description="Vertical offset from the top (negative moves down)",
        default=-144,  # Changed from -80
        min=-500,
        max=0
    )

    overlay_custom_x: IntProperty(
        name="Custom X",
        description="Custom X position (only used in Custom mode)",
        default=130,
        min=0,
        max=4000
    )

    overlay_custom_y_offset: IntProperty(
        name="Custom Y Offset",
        description="Custom Y offset from top (only used in Custom mode)",
        default=-220,
        min=-2000,
        max=0
    )

    # ===== GRAPHML BACKUP SETTINGS =====
    graphml_backup_count: IntProperty(
        name="GraphML Backup Count",
        description="Number of rotating backups to keep when baking data into a GraphML file (0 = no backup)",
        default=2,
        min=0,
        max=10
    )

    # ✅ Verbose Logging
    verbose_logging: BoolProperty(
        name="Verbose Logging",
        description="Enable detailed console logging for debugging operations (warnings and errors are always shown)",
        default=False
    )

    def draw(self, context):
        layout = self.layout
        
        # ===== SEZIONE PRINCIPALE: USER MAPPINGS =====
        box = layout.box()
        box.label(text="📦 User Custom Mappings", icon='PACKAGE')
        
        default_path = get_default_user_mappings_path()
        
        # Info sulla location
        info_box = box.box()
        info_box.label(text="Default Location (Portable):", icon='INFO')
        
        # Split per mostrare il path e il bottone
        split = info_box.split(factor=0.85)
        col1 = split.column()
        col1.label(text=default_path)
        col2 = split.column()
        col2.operator("emtools.open_folder", 
                     text="", 
                     icon='FILEBROWSER').folder_path = default_path
        
        # Statistiche
        stats_row = box.row(align=True)
        
        emdb_path = get_default_user_mappings_path('emdb')
        emdb_count = len([f for f in os.listdir(emdb_path) if f.endswith('.json')]) if os.path.exists(emdb_path) else 0
        
        pyarch_path = get_default_user_mappings_path('pyarchinit')
        pyarch_count = len([f for f in os.listdir(pyarch_path) if f.endswith('.json')]) if os.path.exists(pyarch_path) else 0
        
        col = stats_row.column()
        col.label(text=f"EMdb: {emdb_count} mappings", icon='CHECKMARK' if emdb_count > 0 else 'DOT')
        
        col = stats_row.column()
        col.label(text=f"pyArchInit: {pyarch_count} mappings", icon='CHECKMARK' if pyarch_count > 0 else 'DOT')
        
        # Info su come usare
        help_box = box.box()
        help_box.label(text="💡 How to add mappings:", icon='QUESTION')
        help_box.label(text="1. Click the folder icon above to open user_mappings")
        help_box.label(text="2. Copy your .json mapping files to emdb/ or pyarchinit/")
        help_box.label(text="3. Click 'Reload Mappings' or restart Blender")
        
        layout.separator()
        
        # ===== SEZIONE AVANZATA (COLLAPSIBLE) =====
        box = layout.box()
        row = box.row()
        row.prop(self, "show_advanced", 
                icon='TRIA_DOWN' if self.show_advanced else 'TRIA_RIGHT',
                emboss=False)
        
        if self.show_advanced:
            warning_box = box.box()
            warning_box.alert = True
            warning_box.label(text="⚠ Warning: Custom paths are NOT portable!", icon='ERROR')
            warning_box.label(text="Files with custom paths won't work on other computers.")
            warning_box.label(text="Leave empty for portable setup.")
            
            box.separator()
            
            # EMdb custom path
            row = box.row()
            row.label(text="Custom EMdb Path:")
            row = box.row()
            split = row.split(factor=0.7)
            split.prop(self, "custom_emdb_path", text="")
            
            op = split.operator("emtools.reset_to_default", text="Reset to Default")
            op.mapping_type = 'emdb'
            
            # Mostra percorso effettivo
            effective_path = get_mapping_path(self, 'emdb')
            if effective_path:
                is_default = (effective_path == get_default_user_mappings_path('emdb'))
                info_row = box.row()
                info_row.label(
                    text=f"{'✓ Using default' if is_default else '⚠ Using custom'}: {effective_path}",
                    icon='CHECKMARK' if is_default else 'ERROR'
                )
            
            box.separator()
            
            # pyArchInit custom path
            row = box.row()
            row.label(text="Custom pyArchInit Path:")
            row = box.row()
            split = row.split(factor=0.7)
            split.prop(self, "custom_pyarchinit_path", text="")
            
            op = split.operator("emtools.reset_to_default", text="Reset to Default")
            op.mapping_type = 'pyarchinit'
            
            # Mostra percorso effettivo
            effective_path = get_mapping_path(self, 'pyarchinit')
            if effective_path:
                is_default = (effective_path == get_default_user_mappings_path('pyarchinit'))
                info_row = box.row()
                info_row.label(
                    text=f"{'✓ Using default' if is_default else '⚠ Using custom'}: {effective_path}",
                    icon='CHECKMARK' if is_default else 'ERROR'
                )
        
        layout.separator()

        # ===== VIEWPORT OVERLAY SETTINGS =====
        box = layout.box()
        box.label(text="📺 Viewport Overlay Settings", icon='VIEW3D')

        # Position mode
        row = box.row()
        row.prop(self, "overlay_position_mode", text="Position")

        # Show appropriate offset controls based on mode
        if self.overlay_position_mode in ['TOP_CENTER', 'TOP_LEFT']:
            row = box.row(align=True)
            row.prop(self, "overlay_offset_x", text="X Offset")
            row.prop(self, "overlay_offset_y", text="Y Offset")
        else:  # CUSTOM
            row = box.row(align=True)
            row.prop(self, "overlay_custom_x", text="X Position")
            row.prop(self, "overlay_custom_y_offset", text="Y Offset")

        # Font size
        row = box.row()
        row.prop(self, "overlay_font_size", text="Font Size")

        # Colors
        split = box.split(factor=0.5)
        col = split.column()
        col.prop(self, "overlay_epoch_color", text="Epoch Color")
        col = split.column()
        col.prop(self, "overlay_us_color", text="US Color")

        layout.separator()

        # ===== GRAPHML BACKUP SETTINGS =====
        box = layout.box()
        box.label(text="GraphML Backup Settings", icon='FILE_BACKUP')
        row = box.row()
        row.prop(self, "graphml_backup_count", text="Max Backups")
        info_box = box.box()
        if self.graphml_backup_count == 0:
            info_box.label(text="Backups disabled: bake operations will overwrite without backup", icon='ERROR')
        else:
            info_box.label(
                text=f"Keeps {self.graphml_backup_count} rotating backup(s) (.bak1, .bak2, ...) when baking into GraphML",
                icon='INFO'
            )

        layout.separator()

        # ===== DEVELOPER SETTINGS =====
        box = layout.box()
        box.label(text="Developer Settings", icon='PREFERENCES')
        row = box.row()
        row.prop(self, "verbose_logging", text="Enable Verbose Console Logging")
        if self.verbose_logging:
            info_box = box.box()
            info_box.label(text="Verbose logging active: detailed operations will be printed to console", icon='INFO')
        else:
            info_box = box.box()
            info_box.label(text="Quiet mode: only warnings, errors, and essential messages", icon='INFO')

        layout.separator()

        # ===== AZIONI =====
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator("emtools.reload_custom_mappings",
                     text="Reload All Mappings",
                     icon='FILE_REFRESH')


def update_mapping_path(prefs, context, mapping_type):
    """Callback quando si modifica un percorso custom"""
    custom_attr = f"custom_{mapping_type}_path"
    custom_path = getattr(prefs, custom_attr, "")
    
    if not custom_path:
        log.info(f"{mapping_type} path cleared - will use default")
        return
    
    resolved = resolve_path(custom_path)
    if resolved and os.path.exists(resolved):
        log.info(f"Custom {mapping_type} path set: {resolved}")
        # Ricarica i mapping
        try:
            from s3dgraphy import add_custom_mapping_directory
            add_custom_mapping_directory(mapping_type, resolved, priority='high')
        except Exception as e:
            log.error(f"Error loading custom {mapping_type} mappings: {e}")
    else:
        log.warning(f"Invalid {mapping_type} path: {custom_path}")


class EMTOOLS_OT_open_folder(Operator):
    """Apri una cartella nel file manager"""
    bl_idname = "emtools.open_folder"
    bl_label = "Open Folder"
    bl_description = "Open folder in system file manager"
    bl_options = {'REGISTER'}
    
    folder_path: StringProperty()
    
    def execute(self, context):
        import subprocess
        import platform
        
        if not os.path.exists(self.folder_path):
            self.report({'ERROR'}, f"Folder not found: {self.folder_path}")
            return {'CANCELLED'}
        
        try:
            if platform.system() == "Windows":
                os.startfile(self.folder_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", self.folder_path])
            else:  # Linux
                subprocess.Popen(["xdg-open", self.folder_path])
            
            self.report({'INFO'}, f"Opened: {self.folder_path}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Cannot open folder: {str(e)}")
            return {'CANCELLED'}


class EMTOOLS_OT_reset_to_default(Operator):
    """Reset custom path to default"""
    bl_idname = "emtools.reset_to_default"
    bl_label = "Reset to Default"
    bl_description = "Clear custom path and use default user_mappings folder"
    bl_options = {'REGISTER'}
    
    mapping_type: StringProperty()
    
    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        
        custom_attr = f"custom_{self.mapping_type}_path"
        setattr(prefs, custom_attr, "")
        
        self.report({'INFO'}, f"Reset {self.mapping_type} path to default")
        
        # Ricarica i mapping
        bpy.ops.emtools.reload_custom_mappings()
        
        return {'FINISHED'}

class EMTOOLS_OT_reload_custom_mappings(Operator):
    """Ricarica tutti i mapping"""
    bl_idname = "emtools.reload_custom_mappings"
    bl_label = "Reload Custom Mappings"
    bl_description = "Reload all mapping files from configured directories"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        
        try:
            from s3dgraphy.mappings import mapping_registry
            from s3dgraphy import add_custom_mapping_directory
            
            print("\n" + "="*60)
            print("RELOAD CUSTOM MAPPINGS")
            print("="*60)
            
            # ✅ STEP 1: Svuota COMPLETAMENTE il registry
            print("\n1. Resetting mapping registry...")
            mapping_registry._mapping_directories = {
                'pyarchinit': [],
                'emdb': [],
                'generic': []
            }
            
            # Re-inizializza i percorsi built-in (rilegge il filesystem)
            mapping_registry._initialize_builtin_paths()
            print("   ✓ Registry reset complete")
            
            loaded = []
            
            # ✅ STEP 2: Ricarica le directory custom
            print("\n2. Loading custom directories...")
            
            # Carica EMdb
            emdb_path = get_mapping_path(prefs, 'emdb')
            if emdb_path and os.path.exists(emdb_path):
                add_custom_mapping_directory('emdb', emdb_path, priority='high')
                count = len([f for f in os.listdir(emdb_path) if f.endswith('.json')])
                is_default = (emdb_path == get_default_user_mappings_path('emdb'))
                loaded.append(f"EMdb: {count} {'(default)' if is_default else '(custom)'}")
                print(f"   ✓ EMdb: {count} files from {emdb_path}")
            
            # Carica pyArchInit
            pyarch_path = get_mapping_path(prefs, 'pyarchinit')
            if pyarch_path and os.path.exists(pyarch_path):
                add_custom_mapping_directory('pyarchinit', pyarch_path, priority='high')
                count = len([f for f in os.listdir(pyarch_path) if f.endswith('.json')])
                is_default = (pyarch_path == get_default_user_mappings_path('pyarchinit'))
                loaded.append(f"pyArchInit: {count} {'(default)' if is_default else '(custom)'}")
                print(f"   ✓ pyArchInit: {count} files from {pyarch_path}")
            
            # ✅ STEP 3: Ottieni lista valida DOPO il reset
            print("\n3. Getting valid mapping IDs...")
            valid_emdb = [m[0] for m in mapping_registry.list_available_mappings('emdb')]
            valid_pyarch = [m[0] for m in mapping_registry.list_available_mappings('pyarchinit')]
            print(f"   ✓ Valid EMdb IDs: {valid_emdb}")
            print(f"   ✓ Valid pyArchInit IDs: {valid_pyarch}")
            
            # ✅ STEP 4: FORZA il reset dei valori negli auxiliary files
            print("\n4. Forcing reset of invalid values in auxiliary files...")
            from . import em_setup
            
            cleaned_count = 0
            em_tools = context.scene.em_tools
            
            if hasattr(em_tools, 'graphml_files'):
                for i, graphml in enumerate(em_tools.graphml_files):
                    if hasattr(graphml, 'auxiliary_files'):
                        for j, aux_file in enumerate(graphml.auxiliary_files):
                            
                            if aux_file.file_type == "emdb_xlsx":
                                current = aux_file.emdb_mapping
                                if current and current != 'none' and current not in valid_emdb:
                                    print(f"   ! Resetting GraphML[{i}].Aux[{j}]: '{current}' → 'none'")
                                    aux_file.emdb_mapping = 'none'
                                    cleaned_count += 1
                            
                            elif aux_file.file_type == "pyarchinit":
                                current = aux_file.pyarchinit_mapping
                                if current and current != 'none' and current not in valid_pyarch:
                                    print(f"   ! Resetting GraphML[{i}].Aux[{j}]: '{current}' → 'none'")
                                    aux_file.pyarchinit_mapping = 'none'
                                    cleaned_count += 1
            
            print(f"   ✓ Cleaned {cleaned_count} obsolete references")
            
            # ✅ STEP 5: Forza il refresh dell'UI
            print("\n5. Forcing UI refresh...")
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    area.tag_redraw()
            
            # Costruisci messaggio
            msg_parts = []
            if loaded:
                msg_parts.append(f"Reloaded: {' | '.join(loaded)}")
            else:
                msg_parts.append("No mappings found")
            
            if cleaned_count > 0:
                msg_parts.append(f"Cleaned {cleaned_count} obsolete references")
            
            print("\n" + "="*60)
            print("RELOAD COMPLETE")
            print("="*60 + "\n")
            
            self.report({'INFO'}, ' | '.join(msg_parts))
            
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


class EMTOOLS_OT_open_mapping_preferences(Operator):
    """Apri preferenze mapping"""
    bl_idname = "emtools.open_mapping_preferences"
    bl_label = "Open Mapping Preferences"
    bl_description = "Open addon preferences panel"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        bpy.ops.preferences.addon_show(module=__package__)
        return {'FINISHED'}


# Classi da registrare
classes = [
    EMToolsMappingPreferences,
    EMTOOLS_OT_open_folder,
    EMTOOLS_OT_reset_to_default,
    EMTOOLS_OT_reload_custom_mappings,
    EMTOOLS_OT_open_mapping_preferences,
]


def register():
    """Registra le classi"""
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)
    
    # Assicura che user_mappings esista
    ensure_user_mappings_exist()
    
    # Handler per reset flag
    if reset_initialization_flag not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(reset_initialization_flag)


def unregister():
    """Deregistra le classi"""
    if reset_initialization_flag in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(reset_initialization_flag)
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


@bpy.app.handlers.persistent
def reset_initialization_flag(dummy):
    """Reset flag on file load"""
    try:
        addon_prefs = bpy.context.preferences.addons.get(__package__, None)
        if addon_prefs:
            addon_prefs.preferences.mappings_initialized = False
    except:
        pass


def initialize_custom_mappings():
    """Inizializza i mapping all'avvio"""
    def load_mappings():
        try:
            addon_prefs = bpy.context.preferences.addons.get(__package__, None)
            if not addon_prefs:
                return None
            
            prefs = addon_prefs.preferences
            
            if prefs.mappings_initialized:
                return None
            
            from s3dgraphy import add_custom_mapping_directory
            
            loaded = []
            
            # Carica EMdb
            emdb_path = get_mapping_path(prefs, 'emdb')
            if emdb_path:
                add_custom_mapping_directory('emdb', emdb_path, priority='high')
                count = len([f for f in os.listdir(emdb_path) if f.endswith('.json')])
                if count > 0:
                    loaded.append(f"EMdb ({count})")
            
            # Carica pyArchInit
            pyarch_path = get_mapping_path(prefs, 'pyarchinit')
            if pyarch_path:
                add_custom_mapping_directory('pyarchinit', pyarch_path, priority='high')
                count = len([f for f in os.listdir(pyarch_path) if f.endswith('.json')])
                if count > 0:
                    loaded.append(f"pyArchInit ({count})")
            
            prefs.mappings_initialized = True
            
            if loaded:
                log.info(f"✓ Loaded user mappings: {', '.join(loaded)}")
            
        except Exception as e:
            log.error(f"Error loading mappings: {e}")
        
        return None
    
    bpy.app.timers.register(load_mappings, first_interval=0.1)