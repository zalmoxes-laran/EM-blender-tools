# operators/help_popup.py
import bpy
import os
import re
import json
from bpy.props import StringProperty
from bpy.types import Operator

def get_docs_version():
    """Estrae la versione base dal manifest o version.json come fallback."""
    try:
        addon_dir = os.path.dirname(os.path.dirname(__file__))
        manifest_file = os.path.join(addon_dir, "blender_manifest.toml")

        if os.path.exists(manifest_file):
            with open(manifest_file, 'r') as f:
                manifest_content = f.read()

            version_match = re.search(r'^version\s*=\s*"([^"]+)"', manifest_content, re.MULTILINE)
            if version_match:
                full_version = version_match.group(1)
                base_version = re.match(r'(\d+\.\d+\.\d+)', full_version)
                if base_version:
                    return base_version.group(1)
                return full_version

        # Fallback su version.json (solo durante lo sviluppo)
        version_file = os.path.join(addon_dir, "version.json")
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                config = json.load(f)
            major = config.get('major', 1)
            minor = config.get('minor', 5)
            patch = config.get('patch', 0)
            return f"{major}.{minor}.{patch}"

    except Exception:
        pass

    return "latest"

def build_docs_url(path=""):
    """
    Costruisce l'URL completo della documentazione combinando
    la base URL, la versione e il percorso specifico.
    """
    base_url = "https://docs.extendedmatrix.org/projects/EM-tools/en/"
    version = get_docs_version()
    url = f"{base_url}{version}/"

    if path:
        if path.startswith('/'):
            path = path[1:]
        url += path

    return url

class EM_help_popup(Operator):
    """Show a help popup with text and documentation link"""
    bl_idname = "em.help_popup"
    bl_label = "Help Information"
    bl_description = "Show help information"

    title: StringProperty(default="Help")
    text: StringProperty(default="")
    url: StringProperty(default="")

    def execute(self, context):
        title = self.title
        help_text = self.text
        url = build_docs_url(self.url) if self.url else "https://docs.extendedmatrix.org"

        def draw(popup_self, context):
            layout = popup_self.layout
            if help_text:
                for line in help_text.split('\n'):
                    layout.label(text=line)
            else:
                layout.label(text="Lorem ipsum:")
                layout.label(text="- When enabled: Lorem Ipsum")
                layout.label(text="- When disabled: Lorem Ipsum")
            layout.separator()
            op = layout.operator("wm.url_open", text="Open Documentation")
            op.url = url

        bpy.context.window_manager.popup_menu(draw, title=title)
        return {'FINISHED'}

def register():
    try:
        bpy.utils.unregister_class(EM_help_popup)
    except RuntimeError:
        pass
    bpy.utils.register_class(EM_help_popup)

def unregister():
    try:
        bpy.utils.unregister_class(EM_help_popup)
    except RuntimeError:
        pass
