"""resources_tab — the EM Scene tab (EMTools).

The face of the shared Resource layer: a panel in the "EM Scene" N-panel tab
with Documents · Representation Models · DTC · Shelf sections, wired to the
s3dgraphy R1 FS-index backend. Generalises the DosCo auxiliary-files prototype;
hatting a Shelf orphan → a Document ADOPTS the FS stable ID as node_id.

Pure logic in resource_backend.py (bpy-free, unit-testable), mirroring
graph_info/ and dtc_authoring/. In-process s3dgraphy; em.json = source of truth.
"""

from __future__ import annotations

from . import properties, operators, ui


def register():
    properties.register()
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    properties.unregister()
