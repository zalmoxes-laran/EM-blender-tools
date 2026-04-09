import bpy
import blf

# Global variable to store the draw handler
_draw_handler = None


def draw_callback_px():
    """Draw callback executed for each 3D View region."""
    # Check if overlay is enabled in scene settings
    context = bpy.context
    scene = getattr(context, "scene", None)
    if not scene or not hasattr(scene, "em_tools"):
        return

    em_tools = scene.em_tools
    visual = getattr(em_tools, "visual", None)
    if not visual or not getattr(visual, "overlay_epoch_us", False):
        return

    # Get region - IMPORTANT: must be a VIEW_3D region
    region = context.region
    if not region:
        return

    # Get overlay settings from addon preferences
    prefs = context.preferences.addons.get(__package__)
    if prefs and hasattr(prefs, 'preferences'):
        overlay_prefs = prefs.preferences
        font_size = overlay_prefs.overlay_font_size
        position_mode = overlay_prefs.overlay_position_mode
        offset_x = overlay_prefs.overlay_offset_x
        offset_y = overlay_prefs.overlay_offset_y
        custom_x = overlay_prefs.overlay_custom_x
        custom_y_offset = overlay_prefs.overlay_custom_y_offset
        epoch_color = overlay_prefs.overlay_epoch_color
        us_color = overlay_prefs.overlay_us_color
    else:
        # Fallback defaults
        font_size = 22
        position_mode = 'TOP_LEFT'
        offset_x = 300
        offset_y = -144
        custom_x = 130
        custom_y_offset = -220
        epoch_color = (0.3, 0.5, 1.0)
        us_color = (1.0, 0.7, 0.2)

    # Get epoch and US names separately for colored display
    epoch_name, us_name = _get_epoch_us_names()

    # Font settings
    font_id = 0

    # Calculate position based on mode
    if position_mode == 'TOP_CENTER':
        x = (region.width // 2) + offset_x
        y = region.height + offset_y
    elif position_mode == 'TOP_LEFT':
        x = 16 + offset_x
        y = region.height + offset_y
    else:  # CUSTOM
        x = custom_x
        y = region.height + custom_y_offset

    # Set font size
    blf.size(font_id, font_size)

    # Draw epoch name in blue (or custom color)
    blf.position(font_id, x, y, 0)
    blf.color(font_id, *epoch_color, 1.0)
    epoch_text = f"[{epoch_name}]"
    blf.draw(font_id, epoch_text)

    # Calculate width of epoch text to position US text next to it
    epoch_width = blf.dimensions(font_id, epoch_text)[0]

    # Draw separator and US name in ochre/yellow (or custom color)
    separator_x = x + epoch_width + 5
    blf.position(font_id, separator_x, y, 0)
    blf.color(font_id, 1.0, 1.0, 1.0, 1.0)  # White for separator
    blf.draw(font_id, " | ")

    # Calculate separator width
    separator_width = blf.dimensions(font_id, " | ")[0]

    # Draw US name
    us_x = separator_x + separator_width
    blf.position(font_id, us_x, y, 0)
    blf.color(font_id, *us_color, 1.0)
    blf.draw(font_id, f"[{us_name}]")


def _get_epoch_us_names():
    """Get epoch and US names separately for colored display."""
    scene = getattr(bpy.context, "scene", None)
    if not scene or not hasattr(scene, "em_tools"):
        return "—", "—"

    em_tools = scene.em_tools
    epoch = getattr(em_tools, "epochs", None)
    strat = getattr(em_tools, "stratigraphy", None)

    epoch_name = ""
    if epoch and epoch.list and 0 <= epoch.list_index < len(epoch.list):
        epoch_name = epoch.list[epoch.list_index].name

    us_name = ""
    if strat and strat.units and 0 <= strat.units_index < len(strat.units):
        us_name = strat.units[strat.units_index].name

    epoch_label = epoch_name if epoch_name else "—"
    us_label = us_name if us_name else "—"

    return epoch_label, us_label


def _compute_epoch_us_text():
    """Compute current epoch/US label (for backward compatibility)."""
    epoch_label, us_label = _get_epoch_us_names()
    return f"[{epoch_label}] | [{us_label}]"


def refresh_text():
    """Recompute text based on current epoch/US selection and force redraw."""
    # Force redraw of all 3D viewports
    wm = bpy.context.window_manager if bpy.context else None
    if not wm:
        return
    for window in wm.windows:
        screen = window.screen
        if not screen:
            continue
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def register():
    """Register the viewport overlay handler."""
    global _draw_handler
    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_px, (), 'WINDOW', 'POST_PIXEL'
        )
        # Force initial redraw
        refresh_text()


def unregister():
    """Unregister the viewport overlay handler."""
    global _draw_handler
    if _draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None
