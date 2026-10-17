"""The placement of a Blender object as a representation node carries it.

s3Dgraphy's node datamodel 1.6.31 (E.D. 16-17 Oct 2026) declares
``data.transform`` for the representation models (RM, RMDoc, RMSF) and the
semantic shapes: numbers, the rotation in DEGREES with its ``rotation_order``,
``up_axis`` Z, the ``pivot`` the object turns and scales about (the centre of
its box in its own frame) and the computed quaternion. Until 17 Oct EM Tools
wrote strings and radians, from ``obj.location`` — which is relative to the
parent — and a non-XYZ Euler went out as if it were XYZ (report «lo spazio 3D,
seconda passata», 16 Oct). One function now, for the three writers
(``graph_updaters`` for the RMDoc, ``sync_manager.asset_versions`` for a
version placed «On the node», the anastylosis for the RMSF):

* the pose is the WORLD matrix (``matrix_world``), parent and delta included;
* the angles are given in the object's own Euler order when it has one (the
  ones a person typed, kept close by ``compat``), XYZ for a quaternion or an
  axis-angle;
* the pivot is the centre of ``obj.bound_box`` (the mesh's box in its own
  frame), and the position is rebased on it so the matrix is Blender's.

The proxies are not written here: their pose is in the nodes of the glb the
Heriverse export writes (measured on 16 Oct, 57 of 65 nodes with a TRS) and a
second copy on the shape would be applied twice by EMStudio and Heriverse.
Reading needs nothing here: an em.json is read through s3Dgraphy, which
converts the old form (``geometry.transform.migrate_graph_transforms``).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

try:                                   # inside the add-on, a package
    from .version_recipe import placement
except ImportError:                    # in the tests, a top-level module
    from version_recipe import placement  # type: ignore

#: Blender's six Euler orders (``Object.rotation_mode``).
EULER_ORDERS = ("XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX")


def box_centre(corners: Optional[Sequence[Sequence[float]]]) -> Optional[list]:
    """The centre of a box given by its corners (``obj.bound_box``: eight
    points in the object's own frame); None without corners."""
    pts = [tuple(float(c) for c in p) for p in (corners or ())]
    if not pts:
        return None
    return [(min(p[i] for p in pts) + max(p[i] for p in pts)) / 2 for i in range(3)]


def object_transform(obj) -> Dict[str, Any]:  # pragma: no cover — bpy
    """``data.transform`` of a Blender object, in the new form (see above)."""
    loc, quat, scale = obj.matrix_world.decompose()
    mode = getattr(obj, "rotation_mode", "XYZ")
    if mode in EULER_ORDERS:
        euler = quat.to_euler(mode, obj.rotation_euler)
        order = mode
    else:
        euler = quat.to_euler("XYZ")
        order = "XYZ"
    corners = [tuple(v) for v in obj.bound_box] if getattr(obj, "bound_box", None) else None
    return placement(tuple(loc), tuple(euler), tuple(scale), rotation_order=order,
                     pivot=box_centre(corners))
