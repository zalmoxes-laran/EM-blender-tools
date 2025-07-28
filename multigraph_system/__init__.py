# multigraph_system/__init__.py
"""
Sistema multigraph per la gestione di più grafi simultanei
"""

import bpy

# Importa tutti i moduli del sistema
from . import name_conversion_utils
from . import viewport_graph_indicator  
from . import enhanced_uilist
from . import panel_integration
from . import multigraph_system_init
from . import test_system

def register():
    """Registra tutto il sistema multigraph"""
    print("Registering multigraph system...")
    
    # Registra nell'ordine di dipendenza - UNA VOLTA SOLA
    try:
        # 1. Sistema base di conversione nomi (nessuna registrazione necessaria)
        print("  ✓ Name conversion utilities loaded")
        
        # 2. Proprietà e sistema di inizializzazione
        multigraph_system_init.register()
        print("  ✓ Multigraph system properties registered")
        
        # 3. Indicatore viewport
        viewport_graph_indicator.register()
        print("  ✓ Viewport indicator registered")
        
        # 4. UIList potenziate
        enhanced_uilist.register()
        print("  ✓ Enhanced UILists registered")
        
        # 5. Integrazione pannelli
        panel_integration.register()
        print("  ✓ Panel integration registered")
        
        # 6. Sistema di test
        test_system.register()
        print("  ✓ Test system registered")
        
        print("Multigraph system registration complete!")
        
    except Exception as e:
        print(f"Error registering multigraph system: {e}")
        raise e

def unregister():
    """Disregistra tutto il sistema multigraph"""
    print("Unregistering multigraph system...")
    
    # Disregistra in ordine inverso
    try:
        test_system.unregister()
        panel_integration.unregister()
        enhanced_uilist.unregister()
        viewport_graph_indicator.unregister()
        multigraph_system_init.unregister()
        
        print("Multigraph system unregistration complete!")
        
    except Exception as e:
        print(f"Error unregistering multigraph system: {e}")

# Esporta le funzioni principali per uso esterno
__all__ = [
    'register',
    'unregister',
    'name_conversion_utils',
    'viewport_graph_indicator',
    'enhanced_uilist',
]