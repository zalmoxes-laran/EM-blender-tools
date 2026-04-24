'''
Adapter lazy verso 3D Survey Collection (3DSC).

3DSC espone il suo stato di shift come proprietà di scena:
    scene.BL_epsg   (StringProperty)
    scene.BL_x_shift, BL_y_shift, BL_z_shift (FloatProperty)

L'adapter legge/scrive queste proprietà se presenti. Non importa
direttamente il modulo 3DSC: ispeziona la presenza degli attributi
sul tipo `Scene`, così funziona senza dipendenze dure.
'''

from __future__ import annotations

from typing import Optional


_DSC_ATTRS = ('BL_epsg', 'BL_x_shift', 'BL_y_shift', 'BL_z_shift')


def is_available() -> bool:
    import bpy
    return all(hasattr(bpy.types.Scene, attr) for attr in _DSC_ATTRS)


def read_state(scene) -> Optional[dict]:
    if not is_available():
        return None
    try:
        epsg = getattr(scene, 'BL_epsg', 'NotSet')
        if not epsg or epsg == 'NotSet':
            epsg = None
        return {
            'epsg': epsg,
            'shift_x': float(getattr(scene, 'BL_x_shift', 0.0)),
            'shift_y': float(getattr(scene, 'BL_y_shift', 0.0)),
            'shift_z': float(getattr(scene, 'BL_z_shift', 0.0)),
        }
    except Exception:
        return None


def write_state(scene, epsg: str, shift_x: float, shift_y: float, shift_z: float):
    if not is_available():
        return False, "3DSC not available"
    try:
        scene.BL_epsg = str(epsg) if epsg else 'NotSet'
        scene.BL_x_shift = float(shift_x)
        scene.BL_y_shift = float(shift_y)
        scene.BL_z_shift = float(shift_z)
        return True, "3DSC scene props updated"
    except Exception as e:
        return False, f"3DSC write failed: {e}"
