import bpy  # type: ignore

__all__ = ["update_rm_list_on_graph_load"]


@bpy.app.handlers.persistent
def update_rm_list_on_graph_load(dummy):
    """Update RM list when a graph is loaded"""

    # Ensure we're in a context where we can access scene
    if not bpy.context or not hasattr(bpy.context, 'scene'):
        return

    scene = bpy.context.scene

    # Check if auto update is enabled
    if not hasattr(scene, 'rm_settings') or not scene.rm_settings.auto_update_on_load:
        return

    # Only call the operator if we have an active file
    if (hasattr(scene, 'em_tools') and
        hasattr(scene.em_tools, 'graphml_files') and
        len(scene.em_tools.graphml_files) > 0 and
        scene.em_tools.active_file_index >= 0):

        try:
            # ✅ BLENDER 4.5 COMPATIBLE: Timer callback must return None or float
            def timer_callback():
                bpy.ops.rm.update_list(from_graph=True)
                return None  # Required for Blender 4.5+

            bpy.app.timers.register(timer_callback, first_interval=0.5)
        except Exception as e:
            print(f"Error updating RM list on graph load: {e}")
