"""
Visual Manager - Solo UI e Operatori Base
Questo modulo contiene SOLO l'interfaccia utente e gli operatori base per la gestione delle proprietà.
"""

import bpy # type: ignore

# Import solo i moduli base necessari per l'UI
from .data import register_data, unregister_data
from .ui import register_ui, unregister_ui
from .operators import register_operators, unregister_operators
from .operators_overlay import register as register_overlay_operators, unregister as unregister_overlay_operators
from .label_tools import register_label_tools, unregister_label_tools


# Module info
__all__ = ['register', 'unregister']

from bpy.app.handlers import persistent  # type: ignore


@persistent
def _display_mode_on_load(_dummy=None):
    """P4 · a file saved with the mode «select» (the old default, a value no
    menu writes) gets the mode its proxies' materials show, silently."""
    try:
        from ..functions import PROXY_DISPLAY_MODES, infer_display_mode
        em_tools = bpy.context.scene.em_tools
        if em_tools.proxy_display_mode not in PROXY_DISPLAY_MODES:
            em_tools.proxy_display_mode = infer_display_mode(bpy.context)
    except Exception as exc:  # noqa: BLE001 — a migration never stops a load
        print(f"[VisualManager] display mode not read: {exc}")


def register():
    """Register Visual Manager - solo UI e operatori base."""
    if _display_mode_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_display_mode_on_load)
    try:
        register_data()
        register_operators()
        register_overlay_operators()
        register_label_tools()
        register_ui()

        # Verifica se il pannello è stato registrato
        if not hasattr(bpy.types, 'VIEW3D_PT_visual_panel'):
            print("[VisualManager] Error: panel not found after registration")

    except Exception as e:
        print(f"[VisualManager] Error: registration failed: {e}")
        import traceback
        traceback.print_exc()

def unregister():
    """Unregister Visual Manager - solo UI e operatori base."""
    if _display_mode_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_display_mode_on_load)
    try:
        unregister_ui()
        unregister_label_tools()
        unregister_overlay_operators()
        unregister_operators()
        unregister_data()

    except Exception as e:
        print(f"[VisualManager] Error: unregistration failed: {e}")
        import traceback
        traceback.print_exc()

# Funzioni di utilità per verificare lo stato
def is_panel_registered():
    """Verifica se il pannello Visual Manager è registrato."""
    return hasattr(bpy.types, 'VIEW3D_PT_visual_panel')

def check_visual_manager_status():
    """Controlla lo stato del Visual Manager."""
    status = {
        'panel_registered': is_panel_registered(),
        'operators_available': [],
        'properties_available': []
    }
    
    # Controlla operatori visual.*
    if hasattr(bpy.ops, 'visual'):
        visual_ops = [attr for attr in dir(bpy.ops.visual) if not attr.startswith('_')]
        status['operators_available'] = visual_ops
    
    # Controlla proprietà scene
    scene = bpy.context.scene
    visual_props = [
        'property_values', 'selected_property', 'property_enum',
        'color_ramp_props', 'camera_em_list', 'label_settings'
    ]
    
    for prop in visual_props:
        if hasattr(scene, prop):
            status['properties_available'].append(prop)
    
    return status

def print_visual_manager_status():
    """Stampa lo status del Visual Manager per debug."""
    return check_visual_manager_status()