'''
Operatori del pannello Georeferencing.

- EM_OT_georef_import_shift_txt: legge un file shift.txt (formato 3DSC)
  e popola scene.em_georef — che a sua volta propaga a BGIS/3DSC.
- EM_OT_georef_export_shift_txt: scrive un file shift.txt dai valori
  correnti di scene.em_georef.
- EM_OT_georef_sync_all: propaga forzatamente scene.em_georef agli
  addon presenti (utile se qualcuno ha toccato BGIS/3DSC a mano).
- EM_OT_georef_pull: legge dallo stato di BGIS o 3DSC e aggiorna
  scene.em_georef. Dialog con scelta della fonte quando divergono.
- EM_OT_georef_push_geonode: scrive i valori correnti sul
  GeoPositionNode del grafo attivo e lo collega al gruppo «Graph paradata».
- EM_OT_georef_pull_graph: l'inverso — i valori del GeoPositionNode del
  grafo attivo in scene.em_georef (e da lì a BGIS/3DSC). Esplicito, con
  conferma: si usa quando scena e grafo differiscono.
'''

from __future__ import annotations

import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper, ExportHelper

from . import bgis_adapter, dsc_adapter, graph_sync, propagation, shift_io


def _em_log(msg, level="INFO"):
    try:
        from ..functions import em_log
        em_log(msg, level)
    except Exception:
        if level in ("WARNING", "ERROR"):
            print(f"[EM {level}] {msg}")


class EM_OT_georef_import_shift_txt(Operator, ImportHelper):
    bl_idname = "em.georef_import_shift_txt"
    bl_label = "Import shift.txt"
    bl_description = "Read a shift.txt file (3DSC format) and populate scene georef values"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".txt"
    filter_glob: StringProperty(default="*.txt", options={'HIDDEN'})  # type: ignore

    def execute(self, context):
        try:
            rec = shift_io.parse_shift_file(self.filepath)
        except Exception as e:
            self.report({'ERROR'}, f"Cannot parse shift file: {e}")
            return {'CANCELLED'}

        g = context.scene.em_georef
        # L'assegnazione dei 4 campi triggera 4 volte il callback update;
        # è accettabile (ogni propagazione è idempotente). In futuro si
        # può aggiungere un batch-mode con notify disabilitato.
        graph_sync.set_shift(g, rec.x, rec.y, rec.z)
        g.epsg = rec.epsg

        self.report({'INFO'}, f"Loaded shift: EPSG:{rec.epsg} ({rec.x}, {rec.y}, {rec.z})")
        return {'FINISHED'}


class EM_OT_georef_export_shift_txt(Operator, ExportHelper):
    bl_idname = "em.georef_export_shift_txt"
    bl_label = "Export shift.txt"
    bl_description = "Write the current georef values to a shift.txt file (3DSC format)"

    filename_ext = ".txt"
    filter_glob: StringProperty(default="*.txt", options={'HIDDEN'})  # type: ignore

    def execute(self, context):
        g = context.scene.em_georef
        if not g.epsg:
            self.report({'ERROR'}, "EPSG is empty — fill it before exporting")
            return {'CANCELLED'}
        try:
            shift_io.write_shift_file(
                self.filepath,
                shift_io.ShiftRecord(
                    g.epsg, *graph_sync.exact_shift(g),
                ),
            )
        except Exception as e:
            self.report({'ERROR'}, f"Cannot write shift file: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Wrote {self.filepath}")
        return {'FINISHED'}


class EM_OT_georef_sync_all(Operator):
    bl_idname = "em.georef_sync_all"
    bl_label = "Propagate coordinates"
    bl_description = "Propagate current EMTools georef values to BlenderGIS and 3D Survey Collection (when installed). EMTools is the source; installed addons receive the update"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        g = scene.em_georef
        # Senza EPSG nessun EPSG viaggia (mai 4326 per difetto): vedi propagation.
        results = propagation.push_to_addons(
            scene, g, bgis_adapter, dsc_adapter, log=_em_log,
        )
        pushed = [f"{name}:{outcome}" for name, outcome, _msg in results]
        if propagation.epsg_or_none(g.epsg) is None and results:
            pushed.append("no EPSG, not georeferenced")

        if not pushed:
            self.report({'INFO'}, "No external georef addon installed — nothing to sync")
        else:
            self.report({'INFO'}, f"Synced: {', '.join(pushed)}")
        return {'FINISHED'}


class EM_OT_georef_pull(Operator):
    bl_idname = "em.georef_pull"
    bl_label = "Pull from addon"
    bl_description = "Read georef state from BGIS or 3DSC and overwrite EMTools values (with confirmation)"
    bl_options = {'REGISTER', 'UNDO'}

    source: StringProperty(default="auto")  # type: ignore

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        scene = context.scene
        state = None
        src = None

        if self.source in ('auto', 'bgis'):
            state = bgis_adapter.read_state(scene)
            src = 'BlenderGIS' if state else src
        if state is None and self.source in ('auto', 'dsc'):
            state = dsc_adapter.read_state(scene)
            src = '3DSC' if state else src

        if not state:
            self.report({'WARNING'}, "No georef state to pull (no addon or state empty)")
            return {'CANCELLED'}

        g = scene.em_georef
        if state.get('epsg'):
            g.epsg = str(state['epsg'])
        cur = graph_sync.exact_shift(g)
        graph_sync.set_shift(
            g,
            *(float(state[k]) if state.get(k) is not None else c
              for k, c in zip(('shift_x', 'shift_y', 'shift_z'), cur)))

        self.report({'INFO'}, f"Pulled georef from {src}")
        return {'FINISHED'}


class EM_OT_georef_push_geonode(Operator):
    bl_idname = "em.georef_push_geonode"
    bl_label = "Push to GeoNode"
    bl_description = "Write current georef values onto the active graph's GeoPositionNode"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        graph = graph_sync.get_active_graph()
        if graph is None:
            self.report({'WARNING'}, "No active graph — load a GraphML first")
            return {'CANCELLED'}

        g = context.scene.em_georef
        # G1 · the scene's georeferencing is the REFERENCE graph's: writing it
        # into another graph would overwrite that graph's own anchor.
        rows = list(getattr(context.scene.em_tools, 'graphml_files', ()) or ())
        ref = getattr(g, 'reference_graph', '') or ''
        if len(rows) > 1 and ref and graph.graph_id != ref:
            self.report({'WARNING'},
                        f"{graph.graph_id} is not the scene's reference graph "
                        f"({ref}): its own georeferencing is kept — use «Align "
                        f"graphs to the scene» to place it")
            return {'CANCELLED'}
        ok = graph_sync.push_to_geonode(
            graph, g.epsg or None, *graph_sync.exact_shift(g), g.rotation,
        )
        if not ok:
            self.report({'WARNING'}, "Could not write GeoPositionNode on active graph")
            return {'CANCELLED'}
        self.report({'INFO'}, f"GeoPositionNode updated on graph {graph.graph_id}")
        return {'FINISHED'}


class EM_OT_georef_pull_graph(Operator):
    bl_idname = "em.georef_pull_graph"
    bl_label = "Pull from graph"
    bl_description = (
        "Read EPSG, shift and azimuth from the active graph's GeoPositionNode "
        "and overwrite the scene's values (then BlenderGIS and 3DSC through the "
        "usual propagation). Objects are not moved")
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        graph = graph_sync.get_active_graph()
        if graph is None:
            self.report({'WARNING'}, "No active graph — load a graph first")
            return {'CANCELLED'}
        g = context.scene.em_georef
        # G1 · the scene's georeferencing is the REFERENCE graph's (as for Push)
        rows = list(getattr(context.scene.em_tools, 'graphml_files', ()) or ())
        ref = getattr(g, 'reference_graph', '') or ''
        if len(rows) > 1 and ref and graph.graph_id != ref:
            self.report({'WARNING'},
                        f"{graph.graph_id} is not the scene's reference graph "
                        f"({ref}): the scene keeps the reference graph's "
                        f"georeferencing")
            return {'CANCELLED'}
        values = graph_sync.pull_from_geonode(graph)
        if not graph_sync.is_georeferenced(values):
            self.report({'WARNING'},
                        f"Graph {graph.graph_id} declares no georeferencing")
            return {'CANCELLED'}
        graph_sync.write_scene(g, values)
        g.graph_note = (f"Georeferencing pulled from graph {graph.graph_id}: "
                        f"EPSG:{values['epsg'] or '—'} · {values['shift_x']:.3f}, "
                        f"{values['shift_y']:.3f}, {values['shift_z']:.3f}")
        self.report({'INFO'}, g.graph_note)
        return {'FINISHED'}


CLASSES = (
    EM_OT_georef_import_shift_txt,
    EM_OT_georef_export_shift_txt,
    EM_OT_georef_sync_all,
    EM_OT_georef_pull,
    EM_OT_georef_push_geonode,
    EM_OT_georef_pull_graph,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
