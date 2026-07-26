"""dtc_authoring — DTC (Digital Twin Chain) authoring panel (EMTools, ECHOES).

Author a DTC genesis — a Process (DTCProcessNode) with input/output Resources
(LinkNodes carrying dtc_kind + resource_type), wired by dtc_had_input /
dtc_had_output / dtc_derived_from — on the active s3dgraphy graph. Mirrors
graph_info/: pure logic (dtc_graph.py) + properties + operators + an inline UI
section drawn by the EM Data Tree panel. In-process s3dgraphy (no bridge);
DTC nodes are graph metadata, NEVER Blender 3D scene objects.
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
