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
  GeoPositionNode del grafo attivo (chiamato automaticamente al save
  del blend / Heriverse export, disponibile anche manualmente).
'''

from __future__ import annotations

import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper, ExportHelper

from . import bgis_adapter, dsc_adapter, graph_sync, shift_io


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
        g.epsg = rec.epsg
        g.shift_x = rec.x
        g.shift_y = rec.y
        g.shift_z = rec.z

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
                    epsg=g.epsg, x=g.shift_x, y=g.shift_y, z=g.shift_z,
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
        epsg = g.epsg or '4326'
        pushed = []

        if bgis_adapter.is_available():
            ok, msg = bgis_adapter.write_state(
                scene, epsg, g.shift_x, g.shift_y,
                move_objects=bool(g.move_objects_on_change),
                sync_lat_lon=bool(g.sync_lat_lon),
            )
            pushed.append(f"BGIS:{'ok' if ok else 'fail'}")
            _em_log(f"[georef] sync BGIS: {msg}")

        if dsc_adapter.is_available():
            ok, msg = dsc_adapter.write_state(
                scene, epsg, g.shift_x, g.shift_y, g.shift_z,
            )
            pushed.append(f"3DSC:{'ok' if ok else 'fail'}")
            _em_log(f"[georef] sync 3DSC: {msg}")

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
        if state.get('shift_x') is not None:
            g.shift_x = float(state['shift_x'])
        if state.get('shift_y') is not None:
            g.shift_y = float(state['shift_y'])
        if state.get('shift_z') is not None:
            g.shift_z = float(state['shift_z'])

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
        ok = graph_sync.push_to_geonode(
            graph, g.epsg or None, g.shift_x, g.shift_y, g.shift_z,
        )
        if not ok:
            self.report({'WARNING'}, "Could not write GeoPositionNode on active graph")
            return {'CANCELLED'}
        self.report({'INFO'}, f"GeoPositionNode updated on graph {graph.graph_id}")
        return {'FINISHED'}


CLASSES = (
    EM_OT_georef_import_shift_txt,
    EM_OT_georef_export_shift_txt,
    EM_OT_georef_sync_all,
    EM_OT_georef_pull,
    EM_OT_georef_push_geonode,
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
