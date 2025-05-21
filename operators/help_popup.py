# operators/help_popup.py
import bpy
import os
import re
import json
from bpy.props import StringProperty
from bpy.types import Operator

def get_docs_version():
    """Estrae la versione base dal manifest o version.json"""
    try:
        # Prima prova a leggere dal manifest
        addon_dir = os.path.dirname(os.path.dirname(__file__))  # Sale di un livello dalla cartella operators
        manifest_file = os.path.join(addon_dir, "blender_manifest.toml")
        
        if os.path.exists(manifest_file):
            with open(manifest_file, 'r') as f:
                manifest_content = f.read()
                
            # Cerca la versione nel manifest - essere specifici per la riga "version"
            # Usando ^version assicuriamo che la riga inizi con "version" (no "schema_version")
            version_match = re.search(r'^version\s*=\s*"([^"]+)"', manifest_content, re.MULTILINE)
            if version_match:
                full_version = version_match.group(1)
                # Estrai solo la parte base della versione (es. 1.5.0 da 1.5.0-dev.73)
                base_version_match = re.match(r'(\d+\.\d+\.\d+)', full_version)
                if base_version_match:
                    return base_version_match.group(1)
                return full_version  # Fallback alla versione completa se il regex non funziona
        
        # Fallback su version.json
        version_file = os.path.join(addon_dir, "version.json")
        
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                config = json.load(f)
            
            # Genera la stringa di versione base
            major = config.get('major', 1)
            minor = config.get('minor', 5) 
            patch = config.get('patch', 0)
            
            return f"{major}.{minor}.{patch}"
                
    except Exception as e:
        print(f"Error reading version information: {e}")
    
    # Fallback statico se non riesce a leggere
    return "latest"

def build_docs_url(path=""):
    """Costruisce l'URL completo della documentazione"""
    base_url = "https://docs.extendedmatrix.org/projects/EM-tools/en/"
    version = get_docs_version()
    print(f"Estratta versione: {version}")  # Debug
    
    # Costruisci l'URL completo
    url = f"{base_url}{version}/"
    
    # Aggiungi il percorso specifico se fornito
    if path:
        if path.startswith('/'):
            path = path[1:]
        url += path
    
    print(f"URL completo: {url}")  # Debug
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
        
        bpy.context.window_manager.popup_menu(draw, title=title)
        return {'FINISHED'}

def register():
    bpy.utils.register_class(EM_help_popup)

def unregister():
    bpy.utils.unregister_class(EM_help_popup)