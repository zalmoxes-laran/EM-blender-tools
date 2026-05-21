"""Heriverse export provider: UI section + Scene properties.

The actual exporter operator (bl_idname `export.heriverse`) lives in
export_operators/heriverse/ — this provider only binds the UI.
"""

from ...registry import ExportProvider, register_provider, unregister_provider
from . import properties, ui


PROVIDER = ExportProvider(
    id="heriverse",
    label="Heriverse Export",
    order=20,
    icon='WORLD_DATA',
    poll=ui.poll,
    draw=ui.draw,
    help_title="Heriverse Export",
    help_text="Multi-component export for Heriverse publishing platform (proxies, RM, RB, animations, paradata).",
    help_url="panels/heriverse_export.html#heriverse-export",
)


def register():
    properties.register()
    register_provider(PROVIDER)


def unregister():
    unregister_provider(PROVIDER.id)
    properties.unregister()
