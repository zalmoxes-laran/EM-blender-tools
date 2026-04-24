# operators/help_popup.py
import bpy
import os
import re
import json
from bpy.props import StringProperty, EnumProperty
from bpy.types import Operator


DOCS_CONFIG_DEFAULT = {
    'em_tools': {
        'url_base': 'https://docs.extendedmatrix.org/projects/EM-tools/en/',
        'version': None,  # None → fallback a manifest (em_tools) o a "latest"
    },
    'em': {
        'url_base': 'https://docs.extendedmatrix.org/en/',
        'version': None,  # None → fallback a "latest"
    },
}

_PROJECT_ITEMS = [
    ('em_tools', "EM-tools", "EM-tools addon manual (panels, operators, workflows)"),
    ('em', "Extended Matrix", "Extended Matrix formal language manual (nodes, canvas, connectors)"),
]


def _read_version_from_manifest():
    """Legge la versione base (major.minor.patch) dal blender_manifest.toml, o None."""
    try:
        addon_dir = os.path.dirname(os.path.dirname(__file__))
        manifest_file = os.path.join(addon_dir, "blender_manifest.toml")
        if os.path.exists(manifest_file):
            with open(manifest_file, 'r') as f:
                content = f.read()
            m = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
            if m:
                base = re.match(r'(\d+\.\d+\.\d+)', m.group(1))
                return base.group(1) if base else m.group(1)
    except Exception:
        pass
    return None


def _load_docs_config():
    """Carica docs.* da version.json fondendoli con DOCS_CONFIG_DEFAULT."""
    config = {k: dict(v) for k, v in DOCS_CONFIG_DEFAULT.items()}
    try:
        addon_dir = os.path.dirname(os.path.dirname(__file__))
        version_file = os.path.join(addon_dir, "version.json")
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                data = json.load(f)
            docs = data.get('docs') or {}
            for project_key, entry in docs.items():
                if project_key not in config:
                    config[project_key] = {}
                config[project_key].update(entry)
    except Exception:
        pass
    return config


def get_docs_version(project='em_tools'):
    """Ritorna la versione del manuale scelto.

    - em_tools: prima version.json docs.em_tools.version, poi manifest, poi "latest"
    - em: prima version.json docs.em.version, poi "latest"
    """
    config = _load_docs_config()
    entry = config.get(project, config['em_tools'])
    version = entry.get('version')
    if version:
        return version
    if project == 'em_tools':
        manifest_version = _read_version_from_manifest()
        if manifest_version:
            return manifest_version
    return 'latest'


def build_docs_url(path='', project='em_tools'):
    """Costruisce l'URL completo della documentazione per il manuale scelto.

    Args:
        path: path relativo (es. 'panels/em_setup.html#emsetup')
        project: 'em_tools' (addon) o 'em' (linguaggio formale)
    """
    config = _load_docs_config()
    entry = config.get(project, config['em_tools'])
    base_url = entry.get('url_base', DOCS_CONFIG_DEFAULT['em_tools']['url_base'])
    version = get_docs_version(project)
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

    title: StringProperty(default="Help")  # type: ignore
    text: StringProperty(default="")  # type: ignore
    url: StringProperty(default="")  # type: ignore
    project: EnumProperty(
        items=_PROJECT_ITEMS,
        default='em_tools',
        description="Which manual to link to",
    )  # type: ignore

    def execute(self, context):
        title = self.title
        help_text = self.text
        url = build_docs_url(self.url, project=self.project) if self.url else "https://docs.extendedmatrix.org"

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


class EM_open_docs(Operator):
    """Open a documentation URL directly in the browser (no popup)"""
    bl_idname = "em.open_docs"
    bl_label = "Open Documentation"
    bl_description = "Open the relevant documentation page in the browser"

    url: StringProperty(default="")  # type: ignore
    project: EnumProperty(
        items=_PROJECT_ITEMS,
        default='em_tools',
        description="Which manual to link to",
    )  # type: ignore

    def execute(self, context):
        full_url = build_docs_url(self.url, project=self.project) if self.url else "https://docs.extendedmatrix.org"
        bpy.ops.wm.url_open(url=full_url)
        return {'FINISHED'}


_classes = (EM_help_popup, EM_open_docs)


def register():
    for cls in _classes:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
