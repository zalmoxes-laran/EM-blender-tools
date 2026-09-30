"""Mostrare le letture 3D in Blender, e accorgersi se qualcuno le sposta.

**Sola lettura, per ora.** La modifica da Blender (`gltf_to_geometry` al
ritorno) è il sync dell'authoring, il passo successivo della roadmap: qui un
oggetto di `EM_readings` spostato NON scrive niente nel grafo, e lo si dice.

Cosa diventa una lettura in Blender è quello che produce l'importer glTF, e non
una scelta di EMtools (misurato su Blender 5.2, referto 2026-10-12):

* un punto → una mesh con UN vertice (POINTS); una linea o una polilinea → una
  mesh di soli spigoli (LINE_STRIP). Un empty si vedrebbe meglio, ma non
  viaggia in glTF: l'exporter lo scrive come nodo senza primitivo, e
  `gltf_to_geometry` non avrebbe niente da leggere al ritorno. La mesh invece
  torna com'è con ``use_mesh_vertices`` / ``use_mesh_edges``;
* ``show_in_front``: una lettura sta SULLA superficie del modello, e senza
  verrebbe nascosta dalla mesh su cui è stata presa.
"""

from __future__ import annotations

import os
import tempfile

import bpy  # type: ignore
from bpy.types import Operator  # type: ignore

from ..functions import em_log
from . import core


def _active_graph(context):
    from s3dgraphy import get_graph
    em_tools = getattr(context.scene, "em_tools", None)
    if em_tools is None or em_tools.active_file_index < 0 \
            or len(em_tools.graphml_files) == 0:
        return None
    try:
        return get_graph(em_tools.graphml_files[em_tools.active_file_index].name)
    except Exception:                            # noqa: BLE001 — nessun grafo
        return None


def readings_collection(context, create=True):
    coll = bpy.data.collections.get(core.COLLECTION)
    if coll is None and create:
        coll = bpy.data.collections.new(core.COLLECTION)
        context.scene.collection.children.link(coll)
    return coll


def world_points(obj):
    if obj.type != 'MESH':
        return [tuple(obj.matrix_world.translation)]
    mw = obj.matrix_world
    return [tuple(mw @ v.co) for v in obj.data.vertices]


def _import_glb(glb: bytes, name: str):
    """Il glb con l'importer di Blender → gli oggetti nuovi."""
    fd, path = tempfile.mkstemp(suffix=".glb", prefix="em_reading_")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(glb)
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=path)
        return [o for o in bpy.data.objects if o not in before]
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def show_readings(context, graph):
    """Rifà la collezione `EM_readings` dal grafo. → ``(shown, skipped)``.

    Idempotente: gli oggetti di prima vengono tolti e rifatti, così la
    collezione dice sempre quello che il grafo dice adesso.
    """
    plan = core.plan_readings(graph)
    coll = readings_collection(context)
    for obj in list(coll.objects):
        if obj.get(core.PROP_ID):
            mesh = obj.data if obj.type == 'MESH' else None
            bpy.data.objects.remove(obj)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)

    shown = []
    for reading in plan.shown:
        objects = _import_glb(reading.glb, reading.name)
        for obj in objects:
            for c in list(obj.users_collection):
                c.objects.unlink(obj)
            coll.objects.link(obj)
            obj.name = reading.name
            if obj.type == 'MESH':
                obj.data.name = reading.name
            obj[core.PROP_ID] = reading.region_id
            obj[core.PROP_KIND] = reading.kind
            obj.show_in_front = True
            obj.hide_render = True
            obj.select_set(False)
        # il depsgraph del mondo è quello dopo l'import
        context.view_layer.update()
        for obj in objects:
            obj[core.PROP_SIGNATURE] = core.signature(world_points(obj))
            obj[core.PROP_MOVED] = False
        shown.append((reading, [o.name for o in objects]))
    return shown, plan.skipped


class EM_OT_show_readings(Operator):
    """Show the 3D readings of the active graph (point, line, polyline) as objects
    in the EM_readings collection. Read-only: moving them does not change the graph"""
    bl_idname = "em.show_readings"
    bl_label = "Show 3D readings"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active_graph(context) is not None

    def execute(self, context):
        graph = _active_graph(context)
        if graph is None:
            self.report({'WARNING'}, "No active graph")
            return {'CANCELLED'}
        shown, skipped = show_readings(context, graph)
        for s in skipped:
            em_log(f"[readings] {s['name']} ({s['region_id']}) not shown: {s['reason']}",
                   "WARNING")
        msg = f"{len(shown)} readings in {core.COLLECTION}"
        if skipped:
            msg += f", {len(skipped)} not shown (see the log)"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


# ── l'avviso quando una lettura viene spostata ──────────────────────────────

def _warn_popup(names):
    def draw(menu, _context):
        menu.layout.label(text="Readings are read-only in Blender for now:")
        for n in names[:6]:
            menu.layout.label(text=f"  {n}", icon='ERROR')
        menu.layout.label(text="The graph is NOT changed. Re-show them to reset.")
    try:
        bpy.context.window_manager.popup_menu(draw, title="Reading moved",
                                              icon='ERROR')
    except Exception:                            # noqa: BLE001 — headless
        pass
    return None


def moved_readings(scene):
    """Gli oggetti di `EM_readings` che non stanno più dove il grafo li mette.
    Aggiorna il flag `em_reading_moved`; → i nomi di quelli appena spostati."""
    coll = bpy.data.collections.get(core.COLLECTION)
    if coll is None:
        return []
    newly = []
    for obj in coll.objects:
        sig = obj.get(core.PROP_SIGNATURE)
        if not sig:
            continue
        moved = core.signature(world_points(obj)) != sig
        if moved and not obj.get(core.PROP_MOVED):
            newly.append(obj.name)
        if bool(obj.get(core.PROP_MOVED)) != moved:
            obj[core.PROP_MOVED] = moved
    return newly


@bpy.app.handlers.persistent
def _on_depsgraph_update(scene, depsgraph):
    coll = bpy.data.collections.get(core.COLLECTION)
    if coll is None:
        return
    touched = False
    for update in depsgraph.updates:
        obj = update.id
        if isinstance(obj, bpy.types.Object) and obj.get(core.PROP_ID) \
                and (update.is_updated_transform or update.is_updated_geometry):
            touched = True
            break
    if not touched:
        return
    newly = moved_readings(scene)
    if newly:
        em_log(f"[readings] moved in Blender, NOT written to the graph "
               f"(read-only until the authoring sync): {', '.join(newly)}",
               "WARNING")
        bpy.app.timers.register(lambda: _warn_popup(newly), first_interval=0.0)


classes = (EM_OT_show_readings,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    if _on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph_update)


def unregister():
    if _on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph_update)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
