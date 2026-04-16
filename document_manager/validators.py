# document_manager/validators.py
"""Health check puri per RMDocItem — nessun side effect.

Usati sia dall'UI (per scegliere cosa disegnare) sia dagli operatori
(per decidere se procedere o cancellare).
"""
from dataclasses import dataclass

import bpy


@dataclass
class RMDocItemHealth:
    quad_ok: bool
    materials_ok: bool
    image_ok: bool
    camera_declared: bool
    camera_ok: bool
    orphan: bool

    @property
    def is_healthy(self):
        return self.quad_ok and self.materials_ok and (not self.camera_declared or self.camera_ok)

    @property
    def needs_camera_repair(self):
        return self.camera_declared and not self.camera_ok


def check_rmdoc_item(item) -> RMDocItemHealth:
    """Ispeziona un RMDocItem e ritorna il suo stato di salute.

    Non modifica nulla: decisioni e side effect spettano al caller.
    """
    quad_obj = bpy.data.objects.get(item.name)
    quad_ok = bool(quad_obj and quad_obj.type == 'MESH' and quad_obj.data)

    materials_ok = False
    image_ok = False
    if quad_ok and quad_obj.data.materials:
        mat = quad_obj.data.materials[0]
        if mat and mat.use_nodes and mat.node_tree:
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf and 'Alpha' in bsdf.inputs:
                materials_ok = True
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    image_ok = True
                    break

    camera_declared = bool(item.has_camera)
    cam_obj = bpy.data.objects.get(item.camera_object_name) if camera_declared else None
    camera_ok = bool(cam_obj and cam_obj.type == 'CAMERA')

    orphan = not quad_ok

    return RMDocItemHealth(
        quad_ok=quad_ok,
        materials_ok=materials_ok,
        image_ok=image_ok,
        camera_declared=camera_declared,
        camera_ok=camera_ok,
        orphan=orphan,
    )


def disable_pilot(context):
    """Spegni lo stato di piloting: flag + lock_camera su tutte le aree 3D.

    Idempotente — chiamabile in qualsiasi momento senza effetti indesiderati.
    """
    doc_settings = getattr(context.scene, 'doc_settings', None)
    if doc_settings and doc_settings.is_piloting_camera:
        doc_settings.is_piloting_camera = False

    screen = getattr(context, 'screen', None)
    if not screen:
        return
    for area in screen.areas:
        if area.type != 'VIEW_3D':
            continue
        for space in area.spaces:
            if space.type != 'VIEW_3D':
                continue
            if space.lock_camera:
                space.lock_camera = False
            if space.region_3d and space.region_3d.view_perspective == 'CAMERA':
                space.region_3d.view_perspective = 'PERSP'
