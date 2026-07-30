"""shelf_tool — the EM Shelf tool (EMTools, Shelf v2 Session C1).

A SEPARATE N-panel tab ("EM Shelf"), distinct from "EM Scene": an un-hatted
resource library populated by a 3D-first project-folder search that drives the
s3dgraphy acquisition pipeline in-process (fs mapping → AcquisitionDescriptor →
acquire_from_descriptor). Cards reflect the mapping fields (name/media_type/size)
+ a tier badge; the shelf persists as a standalone reusable em.json (ShelfGraph).

Pure logic in shelf_backend.py (bpy-free, unit-testable). In-process s3dgraphy;
em.json = source of truth. NO hatting (that is C2), NO network connectors.
"""

from __future__ import annotations

from . import properties, operators, ui, handlers


def register():
    properties.register()
    operators.register()
    ui.register()
    handlers.register()


def unregister():
    handlers.unregister()
    ui.unregister()
    operators.unregister()
    properties.unregister()
