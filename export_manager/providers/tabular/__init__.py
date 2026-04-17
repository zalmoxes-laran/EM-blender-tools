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
)


def register():
    operators.register()
    register_provider(PROVIDER)


def unregister():
    unregister_provider(PROVIDER.id)
    operators.unregister()
