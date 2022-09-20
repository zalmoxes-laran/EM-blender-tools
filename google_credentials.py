import bpy
from bpy.types import Operator, AddonPreferences, Panel
from bpy.props import StringProperty, IntProperty, BoolProperty
import os

import logging
log = logging.getLogger(__name__)

def get_creds_folder_path():
    script_file = os.path.realpath(__file__)
    directory = os.path.dirname(script_file)
    credential_folder = os.path.join(directory, "creds")

    if not os.path.exists(credential_folder):
        os.mkdir(credential_folder)
        print('There is no creds folder. Creating one...')
    else:
        print('Found previously created creds folder. I will use it')
        print(credential_folder)

    return credential_folder

def check_google_modules():
    addon_prefs = bpy.context.preferences.addons.get(__package__, None)
    #addon_prefs = bpy.context.preferences.addons[__name__].preferences
    #for addon in bpy.context.preferences.addons:
    #    if addon.module.startswith('nUveil'):
    #        addon_prefs = addon.preferences
    try:
        import googleapiclient
        import google_auth_oauthlib
        import google_auth_httplib2
        addon_prefs.preferences.is_google_module = True
        print("ci sono")
    except ImportError:
        addon_prefs.preferences.is_google_module = False
        print("Non ci sono")
        
class uNveil_GoogleCredentialsPreferences(AddonPreferences):
    # this must match the add-on name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __package__

    filepath: StringProperty(
        name="Google credentials folder path",
        subtype='FILE_PATH',
        default = get_creds_folder_path(),
    )
    '''
    number: IntProperty(
        name="Example Number",
        default=4,
    )
    '''
    is_google_module: BoolProperty(
        name="Google modules are present",
        default=False,
    )
   
    def draw(self, context):
        layout = self.layout
        layout.label(text="Google credentials setup")
        layout.prop(self, "filepath", text="Credentials path:")
        if self.is_google_module:
            layout.label(text="Google modules are correctly installed")
        else:
            layout.label(text="Google modules are missing: install with the button below")
        row = layout.row()
        #row.label(text="")
        op = row.operator("install_missing.modules", icon="STICKY_UVS_DISABLE", text='Install google modules (waiting some minutes is normal)')
        op.is_install = True
        row = layout.row()
        op = row.operator("install_missing.modules", icon="STICKY_UVS_DISABLE", text='Uninstall google modules (waiting some minutes is normal)')
        op.is_install = False
        #layout.prop(self, "number")
        #layout.prop(self, "is_google_module")

class OBJECT_OT_uNveil_prefs_googlecreds(Operator):
    """Display Google Credentials preferences"""
    bl_idname = "object_.unveil_prefs_googlecreds"
    bl_label = "uNveil Preferences Google Credentials"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        preferences = context.preferences
        addon_prefs = preferences.addons.get(__package__, None)
        #addon_prefs = preferences.addons[__name__].preferences

        info = ("Path: %s" % (addon_prefs.preferences.filepath))
        #info = ("Path: %s, Number: %d, Boolean %r" %
        #        (addon_prefs.filepath, addon_prefs.number, addon_prefs.boolean))

        self.report({'INFO'}, info)
        print(info)

        return {'FINISHED'}

class OBJECT_OT_uNveil_open_prefs(Operator):
    """Open Google Credentials preferences panel"""
    bl_idname = "open_prefs_panel.unveil_googlecreds"
    bl_label = "open panel uNveil preferences Google Credentials"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        
        bpy.ops.preferences.addon_show(module=__package__)
        return {'FINISHED'}

class OBJECT_OT_uNveil_try_credentials(Operator):
    """If the button is grey, fille the fields above AND open preference panel (button with the gears here on the right) and launch installation of necessary dependances"""
    bl_idname = "try_google.unveil_googlecreds"
    bl_label = "Check uNveil Google Credentials"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        is_active_button = False
        prefs = context.preferences.addons.get(__package__, None)
        if len(context.scene.g_spreadsheet_id) == 44 and len(context.scene.g_spreadsheet_sheet) > 0 and prefs.preferences.is_google_module:
            is_active_button = True
        return is_active_button
	
    def execute(self, context):
        from .spreadsheet import init_spreadsheet_service
        if init_spreadsheet_service(context):
            self.report({'INFO'}, "Connection works")
        else:
            self.report({'ERROR'}, "Connection failed, check parameters")
        return {'FINISHED'}

class ToolsPanelMetadata:
    bl_label = "Google Spreadsheet setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.active_object
        #resolution_pano = scene.RES_pano

        #row = layout.row()
        #row.label(text="Google Spreadsheet setup")
        row = layout.row()
        layout.prop(scene, "g_spreadsheet_id", text="id")
        # qui serve un operatore per isolare il codice id in automatico
        # tra le seguenti stringhe
        # https://docs.google.com/spreadsheets/d/
        # e l'ultimo  "/"

        row = layout.row()
        layout.prop(scene, "g_spreadsheet_sheet", text="sheet")
        
        #row.operator("activate.spreadsheetservice", icon="STICKY_UVS_DISABLE", text='')
        row = layout.row()
        row.label(text="Try connection")
        row.operator("try_google.unveil_googlecreds", icon="STICKY_UVS_DISABLE", text='')
        row.operator("open_prefs_panel.unveil_googlecreds", icon="SETTINGS", text="")

class VIEW3D_PT_metadata(Panel, ToolsPanelMetadata):
    bl_category = "uNveil"
    bl_idname = "VIEW3D_PT_metadata"
    #bl_context = "objectmode"

classes = [
    uNveil_GoogleCredentialsPreferences,
    VIEW3D_PT_metadata,
    OBJECT_OT_uNveil_prefs_googlecreds,
    OBJECT_OT_uNveil_open_prefs,
    OBJECT_OT_uNveil_try_credentials,
    ]

# Registration
def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError as e:
            log.warning('{} is already registered, now unregister and retry... '.format(cls))
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)
    
    bpy.types.Scene.g_spreadsheet_id = StringProperty(
        name = "Define the id of the Google spreadsheet",
        default = "",
        description = "look at the link to the spreadsheed: id is a 44 token between https://docs.google.com/spreadsheets/d/ and /edit#gid=0. EXAMPLE: https://docs.google.com/spreadsheets/d/154hagqP1iQ0pkoQ5FB9mqTbkOzzXk0R_knWSPudfgAs/edit#gid=0 TOKEN here is 154hagqP1iQ0pkoQ5FB9mqTbkOzzXk0R_knWSPudfgAs")

    bpy.types.Scene.g_spreadsheet_sheet = StringProperty(
        name = "Google spreadsheet sheet name",
        default = "",
        description = "Define the name of the Google spreadsheet sheet")

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.g_spreadsheet_id
    del bpy.types.Scene.g_spreadsheet_sheet