"""Mostrare le letture 3D in Blender, accorgersi se qualcuno le sposta, e
riportarle nel grafo quando lo si chiede.

Una lettura spostata NON scrive da sola: l'handler la segna e lo dice.
**«Bring back to graph»** (`em.readings_to_graph`) è il primo pezzo del sync
dell'authoring: per le letture selezionate, export glTF → `gltf_to_geometry`
(senza kind: lo legge dagli extras del nodo, ``em_reading_kind``) →
``data.coords`` della regione, con la lunghezza ricalcolata. Un passo solo.

**Il frame.** Il grafo tiene le coordinate LOCALI della scena (Y-up, metri,
``crs: "local"``), quelle del glb del modello. L'exporter glTF converte Z-up →
Y-up; ma la trasformazione dell'OGGETTO (una lettura spostata con G) la scrive
come ``translation`` del nodo, e `gltf_to_geometry` legge solo le POSITION
(misurato: un punto spostato tornava a ``[0, 0, 0]``). Per questo si esporta
una copia con ``matrix_world`` cotta nei vertici: quello che si vede nella
viewport, nello stesso frame locale del modello. Nessuno shift geografico
entra qui: le coordinate assolute si ricostruiscono dal file di shift, quando
servono o quando le si chiede.

Cosa diventa una lettura in Blender è quello che produce l'importer glTF, e non
una scelta di EMtools (misurato su Blender 5.2, referto 2026-10-12):

* un punto → una mesh con UN vertice (POINTS); una linea o una polilinea → una
  mesh di soli spigoli (LINE_STRIP). Un empty si vedrebbe meglio, ma non
  viaggia in glTF: l'exporter lo scrive come nodo senza primitivo, e
  `gltf_to_geometry` non avrebbe niente da leggere al ritorno. La mesh invece
  torna com'è con ``use_mesh_vertices`` / ``use_mesh_edges``;
* ``show_in_front``: una lettura sta SULLA superficie del modello, e senza
  verrebbe nascosta dalla mesh su cui è stata presa;
* il punto ha in più una CROCE di tre spigoli (`core.cross_arms`) che non
  tocca il suo vertice: il vertice resta sciolto e l'exporter lo scrive come
  primitivo POINTS a parte, l'unico che `gltf_to_geometry` legge per un punto.
  Misurato contro un ottaedro con lo stesso vertice sciolto (tornano uguali):
  la croce ha solo spigoli, e davanti al modello non ne copre la superficie.
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


def _add_cross(obj):
    """La croce attorno al vertice del punto (coordinate della mesh)."""
    import bmesh  # type: ignore
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    center = tuple(bm.verts[0].co)
    for a, b in core.cross_arms(center):
        bm.edges.new((bm.verts.new(a), bm.verts.new(b)))
    bm.to_mesh(obj.data)
    bm.free()


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
            if reading.kind == "point" and obj.type == 'MESH' \
                    and len(obj.data.vertices) == 1:
                _add_cross(obj)
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


# ── il ritorno: da Blender al grafo ─────────────────────────────────────────

def export_reading_glb(context, obj) -> bytes:
    """Il glb di UNA lettura come la vede la viewport.

    Una copia con ``matrix_world`` cotta nei vertici e trasformazione identità
    (vedi il docstring del modulo: la ``translation`` di un nodo non la legge
    nessuno), esportata con ``use_mesh_vertices`` / ``use_mesh_edges`` /
    ``export_extras``. Selezione e oggetto attivo si rimettono com'erano.
    """
    view_layer = context.view_layer
    selected = [o for o in context.selected_objects]
    active = view_layer.objects.active
    tmp = obj.copy()                                  # custom property comprese
    tmp.data = obj.data.copy()
    tmp.data.transform(obj.matrix_world)
    tmp.matrix_world.identity()
    tmp.parent = None
    context.scene.collection.objects.link(tmp)
    fd, path = tempfile.mkstemp(suffix=".glb", prefix="em_reading_back_")
    os.close(fd)
    try:
        for o in selected:
            o.select_set(False)
        tmp.select_set(True)
        view_layer.objects.active = tmp
        bpy.ops.export_scene.gltf(filepath=path, use_selection=True,
                                  export_format='GLB', use_mesh_vertices=True,
                                  use_mesh_edges=True, export_extras=True)
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        mesh = tmp.data
        bpy.data.objects.remove(tmp)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        for o in selected:
            try:
                o.select_set(True)
            except ReferenceError:
                pass
        view_layer.objects.active = active
        try:
            os.unlink(path)
        except OSError:
            pass


def readings_to_graph(context, graph, objects):
    """Le letture `objects` → le loro regioni nel grafo. → i risultati di
    `core.apply_back`, uno per oggetto. Una lettura scritta si ri-firma (non è
    più «spostata»); una non scritta resta segnata."""
    from s3dgraphy.api import gltf_to_geometry
    results = []
    for obj in objects:
        rid = obj.get(core.PROP_ID)
        try:
            back = gltf_to_geometry(export_reading_glb(context, obj))
        except Exception as exc:                  # ReadingGlbError: niente da leggere
            results.append({"region_id": rid, "written": False,
                            "reason": f"glTF not readable: {exc}", "warnings": []})
            continue
        result = core.apply_back(graph, rid, back)
        results.append(result)
        if result["written"] or result["reason"] == "unchanged":
            context.view_layer.update()
            obj[core.PROP_SIGNATURE] = core.signature(world_points(obj))
            obj[core.PROP_MOVED] = False
    return results


class EM_OT_readings_to_graph(Operator):
    """Write the selected 3D readings back into the active graph: their vertices
    (as seen in the viewport, in the scene's local frame) become the region's
    coords, and a line's length is recomputed"""
    bl_idname = "em.readings_to_graph"
    bl_label = "Bring back to graph"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active_graph(context) is not None and any(
            o.get(core.PROP_ID) for o in context.selected_objects)

    def execute(self, context):
        graph = _active_graph(context)
        objects = [o for o in context.selected_objects if o.get(core.PROP_ID)]
        if graph is None or not objects:
            self.report({'WARNING'}, "Select readings of EM_readings in the active graph")
            return {'CANCELLED'}
        results = readings_to_graph(context, graph, objects)
        written = [r for r in results if r["written"]]
        refused = [r for r in results if not r["written"] and r["reason"] != "unchanged"]
        for r in results:
            em_log(f"[readings] {core.describe(r)}",
                   "WARNING" if r in refused else "INFO")
        msg = f"{len(written)} of {len(results)} readings written to the graph"
        if refused:
            msg += f"; {len(refused)} NOT written: " + "; ".join(
                core.describe(r) for r in refused[:3])
            self.report({'WARNING'}, msg)
        else:
            self.report({'INFO'}, msg)
        return {'FINISHED'}


# ── l'avviso quando una lettura viene spostata ──────────────────────────────

def _warn_popup(names):
    def draw(menu, _context):
        menu.layout.label(text="Moved in Blender, not yet in the graph:")
        for n in names[:6]:
            menu.layout.label(text=f"  {n}", icon='ERROR')
        menu.layout.label(text="Bring back to graph to write them, Show to reset.")
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
        em_log(f"[readings] moved in Blender, NOT yet written to the graph "
               f"(Bring back to graph writes them): {', '.join(newly)}",
               "WARNING")
        bpy.app.timers.register(lambda: _warn_popup(newly), first_interval=0.0)


classes = (EM_OT_show_readings, EM_OT_readings_to_graph)


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
