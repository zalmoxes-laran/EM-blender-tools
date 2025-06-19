# viewport_graph_indicator.py
"""
Sistema per mostrare informazioni sui grafi nella viewport 3D
"""

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader

# Handler globale per il disegno
_draw_handler = None

def draw_graph_info_callback():
    """
    Callback che disegna le informazioni del grafo nella viewport 3D
    """
    context = bpy.context
    if not context or not context.scene:
        return
    
    scene = context.scene
    
    # Verifica se siamo in una vista 3D
    if not hasattr(context, 'region') or not context.region:
        return
    
    # Verifica se l'indicatore è abilitato
    if not getattr(scene, 'show_viewport_graph_info', True):
        return
    
    # Importa le utility di conversione nomi
    from .name_conversion_utils import get_active_graph_code, should_show_multigraph
    
    try:
        # Ottieni informazioni sui grafi
        is_multigraph = should_show_multigraph(context)
        active_graph_code = get_active_graph_code(context)
        
        # Se non ci sono grafi caricati, non mostrare nulla
        if not active_graph_code or active_graph_code == "UNKNOWN":
            graphs_count = get_loaded_graphs_count(context)
            if graphs_count == 0:
                return  # Nessun grafo = nessuna scritta
            # Se ci sono grafi ma nessuno attivo, mostra un messaggio
            active_graph_code = f"NESSUNO ATTIVO ({graphs_count} caricati)"
        
        # Imposta il font
        font_id = 0
        blf.size(font_id, 16, 72)
        
        # Calcola posizione (angolo superiore sinistro)
        region = context.region
        x_pos = 20
        y_pos = region.height - 30
        
        # Testo da mostrare
        if is_multigraph:
            main_text = "MODALITÀ MULTIGRAPH"
            sub_text = f"Grafi attivi: {get_loaded_graphs_count(context)}"
            color_main = (1.0, 0.8, 0.2, 1.0)  # Arancione
            color_sub = (0.8, 0.8, 0.8, 1.0)   # Grigio chiaro
        else:
            main_text = f"GRAFO ATTIVO: {active_graph_code}"
            sub_text = "Modalità singolo grafo"
            color_main = (0.2, 1.0, 0.3, 1.0)  # Verde
            color_sub = (0.6, 0.6, 0.6, 1.0)   # Grigio
        
        # Disegna testo principale
        blf.position(font_id, x_pos, y_pos, 0)
        blf.color(font_id, *color_main)
        blf.draw(font_id, main_text)
        
        # Disegna testo secondario
        blf.size(font_id, 12, 72)
        blf.position(font_id, x_pos, y_pos - 20, 0)
        blf.color(font_id, *color_sub)
        blf.draw(font_id, sub_text)
        
        # Aggiungi indicatori aggiuntivi in modalità multigraph
        if is_multigraph:
            draw_multigraph_indicators(context, x_pos, y_pos - 45)
    
    except Exception as e:
        print(f"Errore nel disegno delle informazioni grafo: {e}")

def draw_multigraph_indicators(context, start_x, start_y):
    """
    Disegna indicatori aggiuntivi per la modalità multigraph
    """
    font_id = 0
    blf.size(font_id, 10, 72)
    
    # Lista dei grafi caricati
    loaded_graphs = get_loaded_graphs_info(context)
    
    for i, (code, status) in enumerate(loaded_graphs):
        y_offset = start_y - (i * 15)
        
        # Colore basato sullo status
        if status == "active":
            color = (0.2, 1.0, 0.3, 1.0)  # Verde
            indicator = "●"
        elif status == "loaded":
            color = (1.0, 1.0, 0.2, 1.0)  # Giallo
            indicator = "○"
        else:
            color = (0.5, 0.5, 0.5, 1.0)  # Grigio
            indicator = "○"
        
        blf.position(font_id, start_x, y_offset, 0)
        blf.color(font_id, *color)
        blf.draw(font_id, f"{indicator} {code}")

def get_loaded_graphs_count(context):
    """
    Conta i grafi caricati
    """
    try:
        scene = context.scene
        count = 0
        
        # Metodo 1: Controlla em_tools.graphml_files se esiste
        if hasattr(scene, 'em_tools') and hasattr(scene.em_tools, 'graphml_files'):
            for graphml in scene.em_tools.graphml_files:
                if graphml.graphml_path:  # Ha un file associato
                    count += 1
        
        # Metodo 2: Controlla direttamente nel sistema s3Dgraphy se disponibile
        if count == 0:
            try:
                from ..s3Dgraphy import get_all_graphs
                all_graphs = get_all_graphs()
                count = len([g for g in all_graphs.values() if g is not None])
            except (ImportError, AttributeError):
                pass
        
        return count
    
    except Exception as e:
        print(f"Error counting loaded graphs: {e}")
        return 0

def get_loaded_graphs_info(context):
    """
    Ottiene informazioni sui grafi caricati
    Returns:
        list: Lista di tuple (codice_grafo, status)
    """
    scene = context.scene
    graphs_info = []
    
    if hasattr(scene, 'em_tools') and scene.em_tools.graphml_files:
        for graphml in scene.em_tools.graphml_files:
            if graphml.graphml_path:
                # Estrai il codice dal nome o path
                from .name_conversion_utils import extract_code_from_path
                code = extract_code_from_path(graphml.graphml_path)
                
                # Determina lo status (potresti aver bisogno di aggiustare questa logica)
                status = "active" if getattr(graphml, 'is_active', False) else "loaded"
                graphs_info.append((code, status))
    
    return graphs_info

def register_viewport_indicator():
    """
    Registra l'handler per il disegno nella viewport
    """
    global _draw_handler
    
    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_graph_info_callback, 
            (), 
            'WINDOW', 
            'POST_PIXEL'
        )
        print("Viewport graph indicator registered")

def unregister_viewport_indicator():
    """
    Rimuove l'handler per il disegno nella viewport
    """
    global _draw_handler
    
    if _draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None
        print("Viewport graph indicator unregistered")

# Operatore per toggle dell'indicatore
class EM_OT_ToggleViewportIndicator(bpy.types.Operator):
    """Toggle viewport graph indicator"""
    bl_idname = "em.toggle_viewport_indicator"
    bl_label = "Toggle Viewport Graph Info"
    bl_description = "Show/hide graph information in the 3D viewport"

    def execute(self, context):
        global _draw_handler
        
        if _draw_handler is None:
            register_viewport_indicator()
            self.report({'INFO'}, "Viewport indicator enabled")
        else:
            unregister_viewport_indicator()
            self.report({'INFO'}, "Viewport indicator disabled")
        
        # Forza il refresh della viewport
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        
        return {'FINISHED'}

# Proprietà per abilitare/disabilitare l'indicatore
def register_properties():
    """Registra le proprietà per l'indicatore viewport"""
    bpy.types.Scene.show_viewport_graph_info = bpy.props.BoolProperty(
        name="Show Graph Info in Viewport",
        description="Display active graph information in the 3D viewport",
        default=True,
        update=lambda self, context: toggle_indicator_on_property_change(self, context)
    )

def toggle_indicator_on_property_change(scene, context):
    """Callback per quando cambia la proprietà"""
    if scene.show_viewport_graph_info:
        register_viewport_indicator()
    else:
        unregister_viewport_indicator()

def register():
    """Registra tutto il sistema dell'indicatore viewport"""
    try:
        bpy.utils.register_class(EM_OT_ToggleViewportIndicator)
        register_properties()
        
        # Registra automaticamente se la proprietà è True
        # Ma solo se ci sono grafi caricati
        if getattr(bpy.context.scene, 'show_viewport_graph_info', True):
            register_viewport_indicator()
        
        print("Viewport indicator system registered")
        
    except Exception as e:
        print(f"Error registering viewport indicator: {e}")

def unregister():
    """Disregistra tutto il sistema dell'indicatore viewport"""
    try:
        unregister_viewport_indicator()
        
        if hasattr(bpy.types.Scene, 'show_viewport_graph_info'):
            del bpy.types.Scene.show_viewport_graph_info
        
        bpy.utils.unregister_class(EM_OT_ToggleViewportIndicator)
        
        print("Viewport indicator system unregistered")
        
    except Exception as e:
        print(f"Error unregistering viewport indicator: {e}")