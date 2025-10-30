"""
Keymap management for Graph Editor
Handles keyboard shortcuts for synchronization between 3D, UI, and Graph Editor.
"""

import bpy

# Lista globale per tenere traccia delle keymap registrate
addon_keymaps = []

def register_keymaps():
    """Registra le keymap per Graph Editor"""
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    
    if not kc:
        print("⚠️  Keyconfig addon non disponibile")
        return
    
    # ========================================================================
    # KEYMAP 1: Shift+Alt+F nella 3D View (per evitare collisione con Stratigraphy Manager)
    # ========================================================================
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
    
    kmi = km.keymap_items.new(
        'graphedit.sync_selection',
        type='F',
        value='PRESS',
        shift=True,  # ✅ Aggiunto Shift per evitare collisione
        alt=True
    )
    
    addon_keymaps.append((km, kmi))
    print("✓ Registrata keymap: Shift+Alt+F in 3D View → Graph Editor Sync")
    
    # ========================================================================
    # KEYMAP 2: Shift+Alt+F nel Node Editor
    # ========================================================================
    km = kc.keymaps.new(name='Node Editor', space_type='NODE_EDITOR')
    
    kmi = km.keymap_items.new(
        'graphedit.sync_selection',
        type='F',
        value='PRESS',
        shift=True,  # ✅ Aggiunto Shift
        alt=True
    )
    
    addon_keymaps.append((km, kmi))
    print("✓ Registrata keymap: Shift+Alt+F in Node Editor → Sync to 3D")
    
    # ========================================================================
    # KEYMAP 3: Shift+Alt+N per Neighborhood nel Node Editor
    # ========================================================================
    km = kc.keymaps.new(name='Node Editor', space_type='NODE_EDITOR')
    
    kmi = km.keymap_items.new(
        'graphedit.draw_neighborhood',
        type='N',
        value='PRESS',
        shift=True,
        alt=True
    )
    kmi.properties.depth = 1
    
    addon_keymaps.append((km, kmi))
    print("✓ Registrata keymap: Shift+Alt+N in Node Editor → Draw Neighborhood")


def unregister_keymaps():
    """Unregistra le keymap"""
    for km, kmi in addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except:
            pass
    
    addon_keymaps.clear()
    print("✓ Tutte le keymap di Graph Editor rimosse")