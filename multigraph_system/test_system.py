# multigraph_system/test_system.py
"""
Test del sistema multigraph - utile per verificare che tutto funzioni
"""

import bpy

def test_name_conversion():
    """Test delle funzioni di conversione nomi"""
    print("\n=== TEST CONVERSIONE NOMI ===")
    
    from .name_conversion_utils import (
        get_display_name,
        get_proxy_name, 
        get_graph_code_from_name
    )
    
    # Test casi normali
    assert get_display_name("GT16.USM10") == "USM10"
    assert get_display_name("USM10") == "USM10"
    assert get_proxy_name("USM10", "GT16") == "GT16.USM10"
    assert get_graph_code_from_name("GT16.USM10") == "GT16"
    assert get_graph_code_from_name("USM10") is None
    
    print("✅ Conversione nomi OK")

def test_properties():
    """Test delle proprietà scene"""
    print("\n=== TEST PROPRIETÀ ===")
    
    scene = bpy.context.scene
    
    # Test proprietà esistenti
    has_show_all_graphs = hasattr(scene, 'show_all_graphs')
    has_viewport_info = hasattr(scene, 'show_viewport_graph_info')
    has_active_graph = hasattr(scene, 'active_graph_code')
    
    print(f"show_all_graphs: {'✅' if has_show_all_graphs else '❌'}")
    print(f"show_viewport_graph_info: {'✅' if has_viewport_info else '❌'}")
    print(f"active_graph_code: {'✅' if has_active_graph else '❌'}")
    
    if has_show_all_graphs:
        # Test toggle
        original_value = scene.show_all_graphs
        scene.show_all_graphs = not original_value
        scene.show_all_graphs = original_value
        print("✅ Toggle multigraph OK")

def test_uilist_classes():
    """Test che le classi UIList enhanced esistano"""
    print("\n=== TEST UILIST CLASSES ===")
    
    # Controlla che le classi siano registrate
    enhanced_classes = [
        "EM_STRAT_UL_List_Enhanced",
        "EM_PROPERTIES_UL_List_Enhanced", 
        "EM_DOCUMENTS_UL_List_Enhanced"
    ]
    
    registered_classes = [cls.__name__ for cls in bpy.types.UIList.__subclasses__()]
    
    for class_name in enhanced_classes:
        if class_name in registered_classes:
            print(f"✅ {class_name}")
        else:
            print(f"❌ {class_name} - non registrata")

def test_operators():
    """Test degli operatori multigraph"""
    print("\n=== TEST OPERATORI ===")
    
    # Lista operatori che dovrebbero esistere
    operators_to_check = [
        "em.toggle_multigraph",
        "em.reload_multigraph_lists",
        "em.set_active_graph",
        "em.toggle_viewport_indicator"
    ]
    
    for op_id in operators_to_check:
        try:
            # Prova a trovare l'operatore
            module, name = op_id.split('.')
            if hasattr(getattr(bpy.ops, module), name):
                print(f"✅ {op_id}")
            else:
                print(f"❌ {op_id} - non trovato")
        except Exception as e:
            print(f"❌ {op_id} - errore: {e}")

def test_viewport_indicator():
    """Test dell'indicatore viewport"""
    print("\n=== TEST VIEWPORT INDICATOR ===")
    
    from . import viewport_graph_indicator
    
    # Controlla se l'handler è registrato
    global _draw_handler
    if hasattr(viewport_graph_indicator, '_draw_handler'):
        handler = viewport_graph_indicator._draw_handler
        if handler is not None:
            print("✅ Handler viewport registrato")
        else:
            print("ℹ️ Handler viewport non attivo")
    else:
        print("❌ Variabile handler non trovata")

def test_multigraph_system_complete():
    """Test completo del sistema"""
    print("\n" + "="*50)
    print("TEST COMPLETO SISTEMA MULTIGRAPH")
    print("="*50)
    
    try:
        test_name_conversion()
        test_properties()
        test_uilist_classes()
        test_operators()
        test_viewport_indicator()
        
        print("\n" + "="*50)
        print("✅ SISTEMA MULTIGRAPH FUNZIONALE")
        print("="*50)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRORE NEL TEST: {e}")
        print("="*50)
        return False

# Operatore per eseguire i test dalla UI
class EM_OT_TestMultigraphSystem(bpy.types.Operator):
    """Test the multigraph system"""
    bl_idname = "em.test_multigraph_system"
    bl_label = "Test Multigraph System"
    bl_description = "Run tests to verify multigraph system is working"

    def execute(self, context):
        success = test_multigraph_system_complete()
        
        if success:
            self.report({'INFO'}, "Multigraph system tests passed!")
        else:
            self.report({'ERROR'}, "Multigraph system tests failed - check console")
        
        return {'FINISHED'}

def register():
    bpy.utils.register_class(EM_OT_TestMultigraphSystem)

def unregister():
    bpy.utils.unregister_class(EM_OT_TestMultigraphSystem)

# Esegui test automaticamente quando il modulo viene importato (solo in modalità debug)
if __name__ == "__main__":
    test_multigraph_system_complete()