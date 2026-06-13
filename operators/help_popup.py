# operators/help_popup.py
import bpy
import os
import json
from bpy.props import StringProperty, EnumProperty
from bpy.types import Operator


DOCS_CONFIG_DEFAULT = {
    'em_tools': {
        'url_base': 'https://docs.extendedmatrix.org/projects/EM-tools/en/',
        # None → release-line derivata da version.json (major.minor), poi "latest"
        'version': None,
    },
    'em': {
        'url_base': 'https://docs.extendedmatrix.org/en/',
        'version': None,  # None → release-line da version.json (major.minor), poi "latest"
    },
}

_PROJECT_ITEMS = [
    ('em_tools', "EM-tools", "EM-tools addon manual (panels, operators, workflows)"),
    ('em', "Extended Matrix", "Extended Matrix formal language manual (nodes, canvas, connectors)"),
]


def _read_version_json():
    """Legge e parsa version.json (accanto all'addon), o None se assente/illeggibile.

    version.json è la single source of truth della versione: da qui viene
    generato anche blender_manifest.toml.
    """
    try:
        addon_dir = os.path.dirname(os.path.dirname(__file__))
        version_file = os.path.join(addon_dir, "version.json")
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _version_line_from_json():
    """Release-line "M.m" derivata da major/minor in version.json, o None.

    Derivare la release-line dai campi major/minor evita il drift del vecchio
    campo docs.<project>.version, che andava aggiornato a mano a ogni bump.
    """
    data = _read_version_json()
    if data:
        major = data.get('major')
        minor = data.get('minor')
        if major is not None and minor is not None:
            return f"{major}.{minor}"
    return None


def _load_docs_config():
    """Carica docs.* da version.json fondendoli con DOCS_CONFIG_DEFAULT."""
    config = {k: dict(v) for k, v in DOCS_CONFIG_DEFAULT.items()}
    data = _read_version_json()
    if data:
        docs = data.get('docs') or {}
        for project_key, entry in docs.items():
            if project_key not in config:
                config[project_key] = {}
            config[project_key].update(entry)
    return config


def get_docs_version(project='em_tools'):
    """Ritorna la release-line del manuale scelto (es. "1.6").

    Granularità release-line: tutti gli utenti M.m.x vedono lo stesso manuale
    (ReadTheDocs serve /en/1.6/, non /en/1.6.0/, /en/1.6.1/, etc.).

    Ordine di risoluzione (uguale per entrambi i progetti):
      1. override esplicito docs.<project>.version in version.json — escape hatch
         se l'addon e il manuale del linguaggio EM divergono di release-line;
      2. M.m derivato da major/minor in version.json (single source of truth);
      3. "latest".

    Nota: blender_manifest.toml NON viene consultato. È un artefatto generato da
    version.json al momento del publish dello zip: non è mai più autorevole di
    version.json (che viaggia dentro ogni zip) e in dev può essere stale/orfano.
    """
    config = _load_docs_config()
    entry = config.get(project, config['em_tools'])
    version = entry.get('version')
    if version:
        return version
    version_line = _version_line_from_json()
    if version_line:
        return version_line
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
