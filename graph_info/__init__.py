"""graph_info — Dataset / HDT-O info panel (fetta 3).

Graph-level HDT-O (ECHOES D7.1) metadata editor: the reference HDT (HC2), the
Heritage Entity it is about (HC1 + authority), the Study (HC9) and the Project
(HC13). Mirrors EMStudio's store.applyHdto/readHdto on the active s3dgraphy graph
— idempotent singletons keyed by data.hdto_role, NEVER Blender scene objects.
Authority autocomplete is in-process via s3dgraphy.authorities (no em-bridge).
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
