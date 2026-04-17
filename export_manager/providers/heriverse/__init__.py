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
)


def register():
    properties.register()
    register_provider(PROVIDER)


def unregister():
    unregister_provider(PROVIDER.id)
    properties.unregister()
