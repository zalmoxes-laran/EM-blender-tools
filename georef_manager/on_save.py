'''MICRO georef al salvataggio (decisione E.D. del 24 ott 2026) · il
georiferimento della scena va nel GeoPositionNode del grafo a ogni scrittura
del grafo, non solo con «Push to GeoNode».

Le regole stanno in :mod:`graph_sync` (``save_plan``, ``write_on_save``, senza
bpy); qui c'è il collante con Blender, chiamato da:

- ``em_setup.graph_tree.save_origin`` — «Save em.json», «Save this file»,
  «Save all files», il salvataggio dopo una creazione (``persist_active``);
- ``export_operators.exporter_emjson._save_as_origin`` — «Save em.json As…»;
- la stanza: il nodo cambiato parte come operazioni (``scene_sync.to_the_room``);
- il pacchetto Heriverse («Write the package on disk»).

GraphML: nessuno lo scrive più (G1, decisione E.D. del 4 ott 2026), quindi non
c'è un salvataggio GraphML da agganciare.
'''

from __future__ import annotations

from typing import Iterable, Optional

from . import graph_sync

#: what the person chooses when scene and graph differ and the scene was never
#: aligned to the graph (the operators' ``georef`` property)
GEOREF_ITEMS = [
    ('ASK', "Ask", "Do not save while scene and graph differ: say it and wait "
                   "for a choice"),
    ('PUSH', "Push the scene into the graph",
     "Write the scene's EPSG, shift and azimuth into the graph's "
     "GeoPositionNode, then save"),
    ('PULL', "Pull the graph into the scene",
     "Take the graph's EPSG, shift and azimuth into the scene (BlenderGIS and "
     "3DSC follow, objects are not moved), then save"),
    ('KEEP', "Keep both as they are",
     "Save with the graph's georeferencing untouched; the scene keeps its own "
     "and the difference stays visible"),
]


def _log(msg, level="INFO"):
    try:
        from ..functions import em_log
        em_log(f"[georef] {msg}", level)
    except Exception:  # noqa: BLE001
        print(f"[georef] {msg}")


def _live(graph_id):
    from s3dgraphy import get_graph
    return get_graph(graph_id)


def conflict(context, graph_ids: Iterable[str]) -> Optional[dict]:
    '''The unresolved discrepancy a save of ``graph_ids`` would meet, or None.'''
    try:
        return graph_sync.save_conflict(context.scene, list(graph_ids), _live)
    except Exception as exc:  # noqa: BLE001 — never block a save on a bug here
        print(f"[georef] save check skipped: {exc}")
        return None


def _in_room(context, graph_id) -> bool:
    try:
        import bpy  # type: ignore
        from .. import graph_origins
        rows = list(context.scene.em_tools.graphml_files)
        row = next((r for r in rows if r.name == graph_id), None)
        return bool(row is not None and graph_origins.origin_of(
            row, abspath=bpy.path.abspath).is_room)
    except Exception:  # noqa: BLE001
        return False


def before_write(context, graph_ids: Iterable[str], choice: str = 'ASK',
                 room: Optional[bool] = None) -> Optional[dict]:
    '''The scene's georeferencing into the scene's graph, if it is among
    ``graph_ids``, before they are written. ``room``: the graph lives in a
    room — what changes on the node goes to the room as operations (None:
    read from the graph's origin).
    → ``graph_sync.write_on_save``'s plan (``outcome == 'conflict'``: do not
    save), or None.'''
    ids = list(graph_ids)
    scene = context.scene

    def run(_graph=None):
        return graph_sync.write_on_save(scene, ids, _live, choice, log=_log)

    try:
        if room is None:
            room = _in_room(context, graph_sync.scene_graph_id(scene))
        if not room:
            return run()
        pending = graph_sync.save_conflict(scene, ids, _live)
        if pending is not None and (choice or 'ASK').upper() == 'ASK':
            return run()          # says the conflict, writes nothing
        gid = graph_sync.scene_graph_id(scene)
        graph = _live(gid) if gid in ids else None
        if graph is None:
            return None
        try:
            from ..sync_manager import scene_sync
            return scene_sync.to_the_room(graph, run)
        except ImportError:
            return run()
    except Exception as exc:  # noqa: BLE001 — the file is still written
        print(f"[georef] georeferencing not written at save: {exc}")
        return None


def tail(plan: Optional[dict]) -> str:
    '''What a save report adds: the georeferencing written, pulled or kept.'''
    if not plan or plan.get('outcome') in (None, 'same', 'scene-empty'):
        return ''
    return plan.get('sentence') or ''


def draw_choice(layout, op, plan: dict) -> None:
    '''The question of a save in front of an unresolved discrepancy: the
    differences field by field and the three choices.'''
    from .panel import _FIELD_LABEL, _fmt, _wrap
    box = layout.box()
    box.alert = True
    box.label(text="The scene's georeferencing and the graph's differ",
              icon='ERROR')
    col = box.column(align=True)
    for key, sv, gv in plan.get('differences') or []:
        col.label(text=f"{_FIELD_LABEL[key]}: scene {_fmt(key, sv)} · "
                       f"graph {_fmt(key, gv)}")
    for line in _wrap("The scene was never aligned to these values of the "
                      "graph. Choose before saving:", 60):
        box.label(text=line)
    col = layout.column(align=True)
    for key in ('PUSH', 'PULL', 'KEEP'):
        col.prop_enum(op, "georef", key)
