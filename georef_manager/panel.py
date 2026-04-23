'''
Micro-pannello Georeferencing in EMTools.

Mostra:
- campi editabili EPSG + shift_x/y/z
- spie semaforiche per BGIS e 3DSC (verde/giallo/grigio/rosso)
- pulsanti Import/Export shift.txt, Sync all, Pull, Push to GeoNode
- sezione Advanced con toggle move_objects / sync_lat_lon

Regola spie (senza reprojection in scope 1.6):
- grigio  : addon non installato
- giallo  : addon installato ma valori divergenti da scene.em_georef
- verde   : addon installato e valori coincidenti
- rosso   : addon presente ma stato incoerente (es. EPSG impostato a
            'NotSet' con shift non-zero)
'''

from __future__ import annotations

import bpy
from bpy.types import Panel

from . import bgis_adapter, dsc_adapter, graph_sync


# Tolleranza numerica per considerare "uguali" due valori di shift.
# 1 mm (1e-3) è abbondantemente sotto ogni significato archeologico
# quando gli shift tipici sono dell'ordine di 1e5-1e6.
_SHIFT_TOLERANCE = 1e-3


def _compare_state(ref: dict, state: dict | None) -> str:
    '''Ritorna lo stato semaforico confrontando EMTools vs addon.'''
    if state is None:
        return 'grey'

    epsg_ref = (ref.get('epsg') or '').strip()
    epsg_state = (state.get('epsg') or '').strip() if state.get('epsg') else ''

    if epsg_ref and not epsg_state:
        return 'red'
    if epsg_state and epsg_ref and epsg_state != epsg_ref:
        return 'yellow'

    for key in ('shift_x', 'shift_y', 'shift_z'):
        r = ref.get(key)
        s = state.get(key)
        if r is None or s is None:
            continue
        if abs(float(r) - float(s)) > _SHIFT_TOLERANCE:
            return 'yellow'

    if not epsg_ref and not epsg_state:
        # Entrambi vuoti / default: ok ma nothing-to-sync.
        return 'grey'
    return 'green'


_DOT_ICON = {
    'green': 'RADIOBUT_ON',
    'yellow': 'DOT',
    'red': 'ERROR',
    'grey': 'RADIOBUT_OFF',
}

_TOOLTIP_BGIS_MISSING = (
    "BlenderGIS not installed. When present, provides: scene CRS "
    "management, projected origin handling, CRS transforms (needs "
    "PyProj for non-UTM CRS)."
)
_TOOLTIP_DSC_MISSING = (
    "3D Survey Collection not installed. When present, provides: "
    "georeferenced DXF/point import, Cesium 3D Tiles export, "
    "shift.txt bidirectional sync."
)


class EM_PT_georef(Panel):
    bl_label = "Georeferencing"
    bl_idname = "EM_PT_georef"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        g = scene.em_georef

        ref = {
            'epsg': g.epsg,
            'shift_x': g.shift_x,
            'shift_y': g.shift_y,
            'shift_z': g.shift_z,
        }

        bgis_state = bgis_adapter.read_state(scene) if bgis_adapter.is_available() else None
        dsc_state = dsc_adapter.read_state(scene) if dsc_adapter.is_available() else None

        bgis_status = _compare_state(ref, bgis_state)
        dsc_status = _compare_state(ref, dsc_state)

        # --- Editable fields ---
        col = layout.column(align=True)
        col.prop(g, "epsg", text="EPSG")
        col.prop(g, "shift_x", text="Shift X")
        col.prop(g, "shift_y", text="Shift Y")
        col.prop(g, "shift_z", text="Shift Z")

        # --- Active graph indicator ---
        graph = graph_sync.get_active_graph()
        row = layout.row()
        if graph is not None:
            row.label(text=f"Active graph: {graph.graph_id}", icon='NODETREE')
        else:
            row.label(text="No active graph", icon='DOT')

        # --- Sync status (lights) ---
        box = layout.box()
        box.label(text="Sync status:")

        row = box.row(align=True)
        row.label(text="", icon=_DOT_ICON[bgis_status])
        if bgis_state is None:
            sub = row.row()
            sub.enabled = False
            sub.label(text="BlenderGIS (not installed)")
            row.label(text="", icon='INFO')
            # Tooltip via a disabled operator would be ideal; Blender 4.x
            # does not support native tooltips on labels — we expose the
            # hint via an inline help label toggle.
        else:
            row.label(text=f"BlenderGIS ({bgis_status})")

        row = box.row(align=True)
        row.label(text="", icon=_DOT_ICON[dsc_status])
        if dsc_state is None:
            sub = row.row()
            sub.enabled = False
            sub.label(text="3D Survey Collection (not installed)")
            row.label(text="", icon='INFO')
        else:
            row.label(text=f"3DSC ({dsc_status})")

        # Integration hints (collapsible via operator would be nicer;
        # for now shown inline only when at least one is missing).
        if bgis_state is None or dsc_state is None:
            hint_box = box.box()
            hint_box.scale_y = 0.7
            hint_box.label(text="Integrations available when installed:", icon='PLUGIN')
            if bgis_state is None:
                for line in _TOOLTIP_BGIS_MISSING.split('. '):
                    if line.strip():
                        hint_box.label(text=f"BGIS: {line.strip()}")
            if dsc_state is None:
                for line in _TOOLTIP_DSC_MISSING.split('. '):
                    if line.strip():
                        hint_box.label(text=f"3DSC: {line.strip()}")

        # --- Actions ---
        row = layout.row(align=True)
        row.operator("em.georef_import_shift_txt", text="Import shift.txt", icon='IMPORT')
        row.operator("em.georef_export_shift_txt", text="Export shift.txt", icon='EXPORT')

        row = layout.row(align=True)
        row.operator("em.georef_sync_all", text="Sync all", icon='FILE_REFRESH')
        row.operator("em.georef_pull", text="Pull", icon='TRIA_DOWN_BAR')

        row = layout.row()
        row.enabled = graph is not None
        row.operator("em.georef_push_geonode", text="Push to GeoNode", icon='WORLD')

        # --- Advanced ---
        header, body = layout.panel("em_georef_advanced", default_closed=True) \
            if hasattr(layout, 'panel') else (None, None)
        if body is not None:
            header.label(text="Advanced")
            body.prop(g, "move_objects_on_change")
            body.prop(g, "sync_lat_lon")
        else:
            # Fallback for older Blender versions without layout.panel()
            box = layout.box()
            box.label(text="Advanced:")
            box.prop(g, "move_objects_on_change")
            box.prop(g, "sync_lat_lon")


CLASSES = (EM_PT_georef,)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
