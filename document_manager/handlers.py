"""Handlers for the Document Manager.

Note on sync_doc_list: Unlike RM Manager and Anastylosis Manager, the Document
Manager does NOT use a load_post handler. The s3dgraphy graph lives in memory
only — it is not saved in the .blend file. So at load_post time there is no
graph to sync from. Instead, sync_doc_list() is called directly at the end of
GraphML import (in import_operators/importer_graphml.py) when em_sources_list
is freshly populated.

RMDoc self-heal: a depsgraph_update_post handler keeps RMDoc state consistent
when users delete quads or cameras outside the RMDoc system. Idempotent — only
writes when the stored value differs from the observed one.
"""
import bpy
from bpy.app.handlers import persistent


_last_object_count = {'n': -1}

# Minimum usable ortho_scale for an RMDoc camera. Dragging below this
# collapses the driven quad to near-zero dimensions and sends the
# viewport into an unresponsive state. Applied in camera-driven mode
# only (where drivers are active).
_ORTHO_SCALE_MIN = 1e-3


@persistent
def rmdoc_self_heal(scene, depsgraph=None):
    """Pulizia difensiva dello stato RMDoc quando cambiano gli oggetti."""

    # Safety clamp: keep ortho_scale of RMDoc cameras above the minimum
    # so accidental ortho-zoom gestures cannot freeze the viewport. Runs
    # every tick because ortho_scale changes via mousewheel/drag don't
    # alter bpy.data.objects count.
    rmdoc_list = getattr(scene, 'rmdoc_list', None)
    if rmdoc_list:
        for item in rmdoc_list:
            if not item.has_camera or not item.camera_object_name:
                continue
            cam_obj = bpy.data.objects.get(item.camera_object_name)
            if cam_obj is None or cam_obj.type != 'CAMERA':
                continue
            cd = cam_obj.data
            if cd.type == 'ORTHO' and cd.ortho_scale < _ORTHO_SCALE_MIN:
                cd.ortho_scale = _ORTHO_SCALE_MIN

    try:
        current_count = len(bpy.data.objects)
    except Exception:
        return

    # Guard: agisci solo quando il numero di oggetti cambia.
    if current_count == _last_object_count['n']:
        return
    _last_object_count['n'] = current_count

    # 1. Unstuck is_piloting_camera se la camera attiva non esiste più.
    doc_settings = getattr(scene, 'doc_settings', None)
    if doc_settings and doc_settings.is_piloting_camera:
        active_cam = scene.camera
        if not active_cam or active_cam.type != 'CAMERA':
            doc_settings.is_piloting_camera = False

    # 2. Sincronizza object_exists e has_camera su tutti gli item.
    rmdoc_list = getattr(scene, 'rmdoc_list', None)
    if rmdoc_list is None:
        return

    for item in rmdoc_list:
        quad_obj = bpy.data.objects.get(item.name)
        should_exist = bool(quad_obj)
        if item.object_exists != should_exist:
            item.object_exists = should_exist

        if item.has_camera and item.camera_object_name:
            cam_obj = bpy.data.objects.get(item.camera_object_name)
            if not cam_obj or cam_obj.type != 'CAMERA':
                item.has_camera = False
                item.camera_object_name = ""


def register_handlers():
    """Registra il handler di self-heal su depsgraph_update_post."""
    handlers = bpy.app.handlers.depsgraph_update_post
    if rmdoc_self_heal not in handlers:
        handlers.append(rmdoc_self_heal)
    # Reset del contatore: il primo tick forza un sweep completo.
    _last_object_count['n'] = -1


def unregister_handlers():
    """Rimuove il handler di self-heal."""
    handlers = bpy.app.handlers.depsgraph_update_post
    if rmdoc_self_heal in handlers:
        handlers.remove(rmdoc_self_heal)
