import bpy
from bpy.types import Operator, AddonPreferences, Panel
from bpy.props import StringProperty, IntProperty, BoolProperty
import os

import logging
log = logging.getLogger(__name__)

def check_google_modules():
    addon_prefs = bpy.context.preferences.addons.get(__package__, None)

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

    is_google_module: BoolProperty(
        name="Google modules are present",
        default=False,
    )
   
    def draw(self, context):
        layout = self.layout
        layout.label(text="Google credentials setup")

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


classes = [
    uNveil_GoogleCredentialsPreferences,
    OBJECT_OT_uNveil_prefs_googlecreds,
    OBJECT_OT_uNveil_open_prefs,
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
    

def unregister():
    for cls in classes:
        print(cls)
        bpy.utils.unregister_class(cls)
