"""
Export Manager Module
Plugin-style Export panel: each exporter section is a provider under providers/.

Organization:
    registry.py        -> ExportProvider + register/get providers
    panel.py           -> VIEW3D_PT_ExportPanel (generic, iterates providers)
    providers/         -> one subpackage per exporter UI section
        tabular/       -> CSV export (US/USV, Sources, Extractors)
        heriverse/     -> Heriverse Export UI (delegates to export.heriverse op
                          defined in export_operators.heriverse)

Dead EMviq/ATON operators (EM_runaton, EM_export, EM_openemviq, the legacy
export.emjson) were removed: they were only reached through a commented-out UI
block and had no other callers.
"""

from . import registry
from . import panel
from . import providers

# Re-export the registry API so third-party/plugin code can add providers.
from .registry import (
    ExportProvider,
    register_provider,
    unregister_provider,
    get_providers,
)

__all__ = [
    'register',
    'unregister',
    'ExportProvider',
    'register_provider',
    'unregister_provider',
    'get_providers',
]


def register():
    providers.register()
    panel.register()


def unregister():
    panel.unregister()
    providers.unregister()
