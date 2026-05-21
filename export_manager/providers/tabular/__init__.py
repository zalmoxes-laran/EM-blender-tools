"""Tabular export provider: CSV dump of US/USV, Sources, Extractors."""

from ...registry import ExportProvider, register_provider, unregister_provider
from . import operators, ui


PROVIDER = ExportProvider(
    id="tabular",
    label="Tabular Export",
    order=10,
    icon='LONGDISPLAY',
    poll=ui.poll,
    draw=ui.draw,
    help_title="Tabular Export",
    help_text="Export to em_data.xlsx (5-sheet canonical) or CSV for downstream analysis.",
    help_url="panels/export_manager.html#tabular-export",
)


def register():
    operators.register()
    register_provider(PROVIDER)


def unregister():
    unregister_provider(PROVIDER.id)
    operators.unregister()
