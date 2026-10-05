"""
Export Manager Module
Plugin-style Export panel: each exporter section is a provider under providers/.

Organization:
    registry.py        -> ExportProvider + register/get providers
    dialogs.py         -> EM ▸ Export: each provider as a dialog (T1, 5 Oct 2026;
                          the panel went to _dead_code/export_manager/panel.py)
    providers/         -> one subpackage per exporter UI section
        tabular/       -> CSV export (US/USV, Sources, Extractors)
        heriverse/     -> only the scene.heriverse_* properties: the Heriverse
                          exporter left (H4, 5 Oct 2026, _dead_code/); the
                          package is a version on disk (Publication Deck)

Dead EMviq/ATON operators (EM_runaton, EM_export, EM_openemviq, the legacy
export.emjson) were removed: they were only reached through a commented-out UI
block and had no other callers.
"""

from . import registry
from . import dialogs
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
    dialogs.register()


def unregister():
    dialogs.unregister()
    providers.unregister()
