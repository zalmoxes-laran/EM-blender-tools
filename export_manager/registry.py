# export_manager/registry.py
"""Plugin-style registry of export providers rendered by VIEW3D_PT_ExportPanel.

A provider describes one collapsible section in the Export panel. It owns its
own draw/poll logic, so the panel itself never needs to change when a new
exporter is added.

To add a new exporter UI:
    1. Create export_manager/providers/<name>/ (as a subpackage)
    2. Build an ExportProvider (see providers/tabular or providers/heriverse)
    3. Call register_provider(PROVIDER) from the subpackage register()
    4. Import the subpackage from providers/__init__.py
"""

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class ExportProvider:
    id: str                               # must match the expand-toggle attr on ExportVars (e.g. "heriverse" -> heriverse_expanded)
    label: str                            # section header text
    order: int = 100                      # lower = drawn earlier
    icon: str = 'EXPORT'                  # Blender icon for the section header
    poll: Callable[[object], bool] = field(default=lambda ctx: True)
    draw: Callable[[object, object], None] = field(default=lambda box, ctx: None)


_providers: dict[str, ExportProvider] = {}


def register_provider(provider: ExportProvider) -> None:
    _providers[provider.id] = provider


def unregister_provider(provider_id: str) -> None:
    _providers.pop(provider_id, None)


def get_providers() -> list[ExportProvider]:
    return sorted(_providers.values(), key=lambda p: p.order)
