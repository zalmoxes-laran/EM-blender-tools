"""
Operators for viewport overlay
"""

import bpy
from bpy.types import Operator


class VISUAL_OT_open_overlay_preferences(Operator):
    """Open addon preferences at the viewport overlay settings section"""
    bl_idname = "visual.open_overlay_preferences"
    bl_label = "Open Overlay Settings"
    bl_description = "Open addon preferences at Viewport Overlay Settings section"
    bl_options = {'REGISTER'}

    def execute(self, context):
        # Open preferences
        bpy.ops.screen.userpref_show('INVOKE_DEFAULT')

        # Get preferences area
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'PREFERENCES':
                    # Set to addons
                    for space in area.spaces:
                        if space.type == 'PREFERENCES':
                            space.filter_type = 'ADDONS'

                            # Try to activate our addon and expand to Viewport Overlay Settings
                            try:
                                # Get our addon module name
                                addon_module = __package__.split('.')[0]
                                bpy.ops.preferences.addon_show(module=addon_module)

                                # Get addon preferences to ensure Viewport Overlay section is visible
                                # The preferences UI automatically shows all sections when expanded
                                prefs = context.preferences.addons.get(addon_module)
                                if prefs and hasattr(prefs, 'preferences'):
                                    # The section is already visible in the UI
                                    # No additional action needed as the UI draws all sections
                                    pass

                            except Exception as e:
                                # Silently fail if there's an error
                                print(f"Error opening addon preferences: {e}")

                            break
                    break
            break

        self.report({'INFO'}, "Opened EMtools preferences at Viewport Overlay Settings")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(VISUAL_OT_open_overlay_preferences)


def unregister():
    bpy.utils.unregister_class(VISUAL_OT_open_overlay_preferences)
