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
- EM_OT_georef_convert_epsg: «Convert to EPSG:NNNN» per un EPSG deprecato
  o con trasformazione «ballpark» (il sostituto dal database di PROJ, mai da
  una tabella scritta a mano); EM_OT_georef_undo_conversion la disfa.
- EM_OT_georef_pull_graph: l'inverso — i valori del GeoPositionNode del
  grafo attivo in scene.em_georef (e da lì a BGIS/3DSC). Esplicito, con
  conferma: si usa quando scena e grafo differiscono.
'''

from __future__ import annotations

import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper, ExportHelper

from . import bgis_adapter, crs_check, dsc_adapter, graph_sync, propagation, shift_io


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
        g.shift_txt_path = self.filepath

        self.report({'INFO'}, f"Loaded shift: EPSG:{rec.epsg} ({rec.x}, {rec.y}, {rec.z})")
        # a deprecated EPSG or a «ballpark» transformation: said now, with the
        # proposal (the conversion is a click in the panel, never silent)
        prop = crs_check.proposal(rec.epsg, rec.x, rec.y)
        if prop and prop.get('warn'):
            repl = prop.get('replacement')
            tail = (f" — proposed: convert to EPSG:{repl['epsg']} in the "
                    f"Georeferencing panel" if repl else "")
            self.report({'WARNING'}, f"{prop['reason']}{tail}")
            _em_log(f"[georef] shift.txt {self.filepath}: {prop['reason']}{tail}",
                    "WARNING")
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


def _backup_name(path: str) -> str:
    """shift.txt → shift.old.txt beside it; an existing one is never
    overwritten (shift.old.1.txt, shift.old.2.txt …)."""
    import os
    folder, name = os.path.split(path)
    stem, ext = os.path.splitext(name)
    cand = os.path.join(folder, f"{stem}.old{ext}")
    n = 1
    while os.path.exists(cand):
        cand = os.path.join(folder, f"{stem}.old.{n}{ext}")
        n += 1
    return cand


class EM_OT_georef_convert_epsg(Operator):
    bl_idname = "em.georef_convert_epsg"
    bl_label = "Convert EPSG"
    bl_description = (
        "Convert the scene's georeferencing to the EPSG code PROJ's database "
        "gives as the replacement of a deprecated code (or of one reachable "
        "only with a «ballpark» transformation). Same grid: only the code "
        "changes, the shift stays. Another grid: the shift is reprojected. "
        "BlenderGIS and 3DSC follow; the graph's node too when it agreed with "
        "the scene. Undoable")
    bl_options = {'REGISTER', 'UNDO'}

    epsg_to: StringProperty(default="")  # type: ignore
    rewrite_shift_txt: bpy.props.BoolProperty(
        name="Rewrite shift.txt (keep shift.old.txt beside it)",
        default=False)  # type: ignore

    def _plan(self, context):
        g = context.scene.em_georef
        src, dst = int(str(g.epsg).strip()), int(self.epsg_to)
        x, y, z = graph_sync.exact_shift(g)
        conv = crs_check.convert_point(src, dst, x, y)
        before = crs_check.proposal(src, x, y) or {}
        return g, src, dst, (x, y, z), conv, before

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        layout = self.layout
        try:
            g, src, dst, (x, y, z), conv, before = self._plan(context)
        except Exception as exc:  # noqa: BLE001
            layout.label(text=f"Cannot plan the conversion: {exc}", icon='ERROR')
            return
        repl = (before.get('replacement') or {})
        for line in _wrap(before.get('reason', ''), 70):
            layout.label(text=line)
        after = crs_check.accuracy_words(repl.get('to_wgs84')) \
            if repl.get('epsg') == dst else '?'
        layout.label(text=f"Accuracy to WGS 84: {before.get('accuracy', '?')} → {after}")
        if conv.get('ok') and conv.get('same_grid'):
            layout.label(text=f"Same grid: only the code changes, shift stays "
                              f"({x:.3f}, {y:.3f})", icon='CHECKMARK')
        elif conv.get('ok'):
            layout.label(text=f"Another grid: shift reprojected to "
                              f"({conv['x']:.3f}, {conv['y']:.3f}), "
                              f"{crs_check.accuracy_words(conv.get('op'))}", icon='ERROR')
            layout.label(text="Models with absolute plan coordinates must be treated too")
        else:
            layout.label(text=conv.get('error', 'no operation'), icon='ERROR')
        if g.shift_txt_path:
            layout.prop(self, "rewrite_shift_txt")

    def execute(self, context):
        import json
        import os
        if not crs_check.available():
            self.report({'ERROR'}, "PROJ (pyproj) is not available in this Blender")
            return {'CANCELLED'}
        try:
            g, src, dst, (x, y, z), conv, before = self._plan(context)
        except Exception as exc:  # noqa: BLE001
            self.report({'ERROR'}, f"Cannot convert: {exc}")
            return {'CANCELLED'}
        if not conv.get('ok'):
            self.report({'ERROR'}, conv.get('error', 'no operation'))
            return {'CANCELLED'}
        nx, ny = float(conv['x']), float(conv['y'])
        undo = {'epsg': str(src), 'shift': [x, y, z], 'graph': None,
                'shift_txt': None}

        # the graph's node follows when it said what the scene said (else the
        # discrepancy stays visible, and Push/Pull are the person's choice)
        graph = graph_sync.get_active_graph()
        before_graph = graph_sync.pull_from_geonode(graph) if graph is not None else None
        scene_before = graph_sync.scene_values(g)
        write_graph = (before_graph is not None
                       and graph_sync.is_georeferenced(before_graph)
                       and not graph_sync.differences(scene_before, before_graph))
        rows = list(getattr(context.scene.em_tools, 'graphml_files', ()) or ())
        ref = getattr(g, 'reference_graph', '') or ''
        if len(rows) > 1 and ref and graph is not None and graph.graph_id != ref:
            write_graph = False

        graph_sync.set_shift(g, nx, ny, z)
        g.epsg = str(dst)                     # last: the propagation carries both
        if write_graph:
            graph_sync.push_to_geonode(graph, str(dst), nx, ny, z, g.rotation)
            undo['graph'] = {'graph_id': graph.graph_id, **before_graph}

        said = []
        if self.rewrite_shift_txt and g.shift_txt_path:
            path = bpy.path.abspath(g.shift_txt_path)
            try:
                backup = _backup_name(path)
                if os.path.exists(path):
                    import shutil
                    shutil.copy2(path, backup)
                shift_io.write_shift_file(path, shift_io.ShiftRecord(str(dst), nx, ny, z))
                undo['shift_txt'] = {'path': path, 'backup': backup}
                said.append(f"shift.txt rewritten, the old one in {os.path.basename(backup)}")
            except Exception as exc:  # noqa: BLE001
                said.append(f"shift.txt NOT rewritten: {exc}")
        g.last_conversion = json.dumps(undo)

        acc_after = crs_check.accuracy_words(
            (before.get('replacement') or {}).get('to_wgs84')) \
            if (before.get('replacement') or {}).get('epsg') == dst else '?'
        head = (f"EPSG:{src} → EPSG:{dst}: "
                + ("same grid, only the code changed"
                   if conv.get('same_grid') else
                   f"shift reprojected to ({nx:.3f}, {ny:.3f}), "
                   f"{crs_check.accuracy_words(conv.get('op'))}; models with "
                   f"absolute plan coordinates must be treated too")
                + f"; accuracy to WGS 84 {before.get('accuracy', '?')} → {acc_after}")
        if write_graph:
            said.append(f"graph {graph.graph_id} updated")
        msg = '; '.join([head] + said)
        _em_log(f"[georef] {msg}", "INFO")
        self.report({'INFO'} if conv.get('same_grid') else {'WARNING'}, msg)
        return {'FINISHED'}


class EM_OT_georef_undo_conversion(Operator):
    bl_idname = "em.georef_undo_conversion"
    bl_label = "Undo the conversion"
    bl_description = (
        "Back to the EPSG and shift before the last «Convert to EPSG»: the "
        "scene, BlenderGIS/3DSC, the graph's node (if the conversion wrote it) "
        "and shift.txt (if it was rewritten; shift.old.txt stays)")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import json
        g = context.scene.em_georef
        try:
            undo = json.loads(g.last_conversion or 'null')
        except ValueError:
            undo = None
        if not undo:
            self.report({'WARNING'}, "No conversion to undo")
            return {'CANCELLED'}
        x, y, z = undo['shift']
        graph_sync.set_shift(g, x, y, z)
        g.epsg = undo['epsg']
        said = [f"back to EPSG:{undo['epsg']}"]
        gb = undo.get('graph')
        if gb:
            from s3dgraphy import get_graph
            graph = get_graph(gb['graph_id'])
            if graph is not None:
                graph_sync.push_to_geonode(graph, gb['epsg'], gb['shift_x'],
                                           gb['shift_y'], gb['shift_z'],
                                           gb.get('rotation', 0.0))
                said.append(f"graph {gb['graph_id']} restored")
        st = undo.get('shift_txt')
        if st:
            try:
                shift_io.write_shift_file(
                    st['path'], shift_io.ShiftRecord(undo['epsg'], x, y, z))
                said.append("shift.txt restored")
            except Exception as exc:  # noqa: BLE001
                said.append(f"shift.txt NOT restored: {exc}")
        g.last_conversion = ""
        self.report({'INFO'}, '; '.join(said))
        return {'FINISHED'}


def _wrap(text, width):
    import textwrap
    return textwrap.wrap(text or '', width) or [""]


CLASSES = (
    EM_OT_georef_import_shift_txt,
    EM_OT_georef_export_shift_txt,
    EM_OT_georef_sync_all,
    EM_OT_georef_pull,
    EM_OT_georef_push_geonode,
    EM_OT_georef_pull_graph,
    EM_OT_georef_convert_epsg,
    EM_OT_georef_undo_conversion,
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
