"""
Visual Manager - Solo UI e Operatori Base
Questo modulo contiene SOLO l'interfaccia utente e gli operatori base per la gestione delle proprietà.
I visualization_modules avanzati sono registrati separatamente dall'__init__.py principale.
"""

import bpy

# Import solo i moduli base necessari per l'UI
from .data import register_data, unregister_data
from .ui import register_ui, unregister_ui

from .operators import register_operators, unregister_operators

# NON importare visualization_modules - sarà registrato dall'__init__.py principale
# NON importare label_tools - causa conflitti

# Module info
__all__ = ['register', 'unregister']

def register():
    """Register Visual Manager - solo UI e operatori base."""
    print("=== REGISTERING VISUAL MANAGER (UI ONLY) ===")
    
    try:
        # 1. Register data first (properties, UI lists, etc.)
        print("Registering visual manager data...")
        register_data()
        
        # 2. Register operators (property management, color schemes, etc.)
        print("Registering visual manager operators...")
        register_operators()
        
        # 3. Register UI last (panels, lists, menus)
        print("Registering visual manager UI...")
        register_ui()
        
        print("=== VISUAL MANAGER (UI ONLY) REGISTRATION COMPLETE ===")
        
        # Verifica se il pannello è stato registrato
        if hasattr(bpy.types, 'VIEW3D_PT_visual_panel'):
            print("✅ Visual Manager panel successfully registered!")
        else:
            print("❌ Visual Manager panel not found after registration")
        
    except Exception as e:
        print(f"❌ ERROR in Visual Manager UI registration: {e}")
        import traceback
        traceback.print_exc()

def unregister():
    """Unregister Visual Manager - solo UI e operatori base."""
    print("=== UNREGISTERING VISUAL MANAGER (UI ONLY) ===")
    
    try:
        # Unregister in reverse order
        unregister_ui()
        unregister_operators()
        unregister_data()
        
        print("=== VISUAL MANAGER (UI ONLY) UNREGISTRATION COMPLETE ===")
        
    except Exception as e:
        print(f"❌ ERROR in Visual Manager UI unregistration: {e}")
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
    status = check_visual_manager_status()
    
    print("\n=== VISUAL MANAGER STATUS ===")
    print(f"Panel Registered: {'✅' if status['panel_registered'] else '❌'}")
    print(f"Operators Available ({len(status['operators_available'])}): {', '.join(status['operators_available'])}")
    print(f"Properties Available ({len(status['properties_available'])}): {', '.join(status['properties_available'])}")
    print("============================\n")