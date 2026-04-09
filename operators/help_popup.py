# operators/help_popup.py
import bpy
import os
import re
import json
from bpy.props import StringProperty
from bpy.types import Operator

def get_docs_version():
    """Estrae la versione base dal manifest o version.json come fallback"""
    try:
        # Prima prova a leggere dal manifest (che sarà sempre presente nel .blext)
        addon_dir = os.path.dirname(os.path.dirname(__file__))
        manifest_file = os.path.join(addon_dir, "blender_manifest.toml")
        
        print(f"DEBUG get_docs_version: Cerco manifest in: {manifest_file}")
        
        if os.path.exists(manifest_file):
            with open(manifest_file, 'r') as f:
                manifest_content = f.read()
                
            # Cerca la versione principale nel manifest (non blender_version_min o altre versioni)
            # Pattern migliorato per catturare solo la versione principale
            import re
            version_match = re.search(r'^version\s*=\s*"([^"]+)"', manifest_content, re.MULTILINE)
            if version_match:
                full_version = version_match.group(1)
                print(f"DEBUG get_docs_version: Versione trovata nel manifest: {full_version}")
                
                # Estrai solo la parte base (1.5.0 da 1.5.0-dev.73)
                base_version = re.match(r'(\d+\.\d+\.\d+)', full_version)
                if base_version:
                    base_version_str = base_version.group(1)
                    print(f"DEBUG get_docs_version: Versione base estratta: {base_version_str}")
                    return base_version_str
                return full_version
        
        # Fallback su version.json (solo durante lo sviluppo)
        version_file = os.path.join(addon_dir, "version.json")
        
        print(f"DEBUG get_docs_version: Cerco version.json in: {version_file}")
        
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                config = json.load(f)
            
            # Genera la stringa di versione basata sul mode
            major = config.get('major', 1)
            minor = config.get('minor', 5) 
            patch = config.get('patch', 0)
            base_version = f"{major}.{minor}.{patch}"
            
            print(f"DEBUG get_docs_version: Versione da version.json: {base_version}")
            return base_version
                
    except Exception as e:
        print(f"DEBUG get_docs_version: Errore durante la lettura della versione: {e}")
    
    # Fallback statico se non riesce a leggere
    print("DEBUG get_docs_version: Usando fallback statico 'latest'")
    return "latest"

def build_docs_url(path=""):
    """
    Costruisce l'URL completo della documentazione combinando
    la base URL, la versione e il percorso specifico.
    
    Args:
        path (str): Percorso della documentazione (es. "EMstructure.html#us-usv-manager")
        
    Returns:
        str: URL completo della documentazione
    """
    base_url = "https://docs.extendedmatrix.org/projects/EM-tools/en/"
    version = get_docs_version()
    
    print(f"DEBUG build_docs_url: Parametro path: '{path}'")
    print(f"DEBUG build_docs_url: Versione estratta: '{version}'")
    
    # Costruisci l'URL completo
    url = f"{base_url}{version}/"
    
    # Aggiungi il percorso specifico se fornito
    if path:
        # Rimuove eventuali slash iniziali
        if path.startswith('/'):
            path = path[1:]
        url += path
    
    print(f"DEBUG build_docs_url: URL finale: '{url}'")
    return url

class EM_help_popup(Operator):
    """Show a help popup with text and documentation link"""
    bl_idname = "em.help_popup"
    bl_label = "Help Information"
    bl_description = "Show help information"
    
    title: StringProperty(default="Help")
    text: StringProperty(default="")
    url: StringProperty(default="")  # Ora può essere il percorso relativo
    
    def execute(self, context):
        print(f"DEBUG execute: Operator EM_help_popup execute chiamato")
        print(f"DEBUG execute: title: '{self.title}'")
        print(f"DEBUG execute: text: '{self.text[:30]}...' (troncato)")
        print(f"DEBUG execute: url: '{self.url}'")
        
        # Capture properties in local variables for closure
        title = self.title
        help_text = self.text
        
        # Costruisci l'URL completo della documentazione
        url = build_docs_url(self.url) if self.url else "https://docs.extendedmatrix.org"
        
        def draw(popup_self, context):
            layout = popup_self.layout
            
            # Split the text into lines and display it
            if help_text:
                for line in help_text.split('\n'):
                    layout.label(text=line)
            else:
                # Default text if not specified
                layout.label(text="Lorem ipsum:")
                layout.label(text="- When enabled: Lorem Ipsum")
                layout.label(text="- When disabled: Lorem Ipsum")
            
            layout.separator()
            
            # Button to open documentation
            op = layout.operator("wm.url_open", text="Open Documentation")
            op.url = url
            print(f"DEBUG draw: Settato URL '{url}' per wm.url_open")
        
        print(f"DEBUG execute: Prima di window_manager.popup_menu")
        bpy.context.window_manager.popup_menu(draw, title=title)
        print(f"DEBUG execute: Dopo window_manager.popup_menu")
        return {'FINISHED'}

def register():
    print("DEBUG register: Tentativo di registrare EM_help_popup")
    try:
        # Prova a de-registrare prima, in caso fosse già registrato
        bpy.utils.unregister_class(EM_help_popup)
        print("DEBUG register: EM_help_popup de-registrato con successo")
    except RuntimeError as e:
        print(f"DEBUG register: EM_help_popup non era registrato: {e}")
    
    # Ora registra
    try:
        bpy.utils.register_class(EM_help_popup)
        print("DEBUG register: EM_help_popup registrato con successo")
    except Exception as e:
        print(f"DEBUG register: Errore durante la registrazione di EM_help_popup: {e}")

def unregister():
    print("DEBUG unregister: Tentativo di de-registrare EM_help_popup")
    try:
        bpy.utils.unregister_class(EM_help_popup)
        print("DEBUG unregister: EM_help_popup de-registrato con successo")
    except Exception as e:
        print(f"DEBUG unregister: Errore durante la de-registrazione di EM_help_popup: {e}")