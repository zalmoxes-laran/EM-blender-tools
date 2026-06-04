"""PyArchInit DB export provider: reverse-export the active EM graph
back into a PyArchInit database via s3dgraphy.sync.GraphIngestor.

Issue #27, Sub-3. Connection settings are shared with the 3D GIS import
panel (Sub-2).
"""

from ...registry import ExportProvider, register_provider, unregister_provider
from . import operators, ui


PROVIDER = ExportProvider(
    id="pyarchinit",
    label="PyArchInit DB Export",
    order=40,
    icon='EXPORT',
    poll=ui.poll,
    draw=ui.draw,
    help_title="PyArchInit DB Export",
    help_text=("Write the active EM graph back into a PyArchInit database "
               "(SQLite or PostgreSQL). Use 'Preview (dry run)' first to "
               "see planned inserts/updates/conflicts."),
    help_url="panels/export_manager.html#pyarchinit-db-export",
)


def register():
    operators.register()
    register_provider(PROVIDER)


def unregister():
    unregister_provider(PROVIDER.id)
    operators.unregister()
