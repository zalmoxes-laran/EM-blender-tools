'''
Property registration per il pannello Georeferencing.

Le proprietà vivono su Scene (non Window Manager) così persistono
nel file .blend. Sono la "fonte canonica di scena" per EMTools:
quando gli addon BGIS/3DSC non sono installati, questi campi sono
l'unica registrazione dello shift nel blend.

Quando BGIS o 3DSC sono presenti, l'update callback propaga i valori
verso i loro rispettivi state store, usando le API sicure
(GeoScene.setOriginPrj con synch=False e updObjLoc=False implicito).
'''

from __future__ import annotations

import bpy
from bpy.props import StringProperty, FloatProperty, BoolProperty
from bpy.types import PropertyGroup


def _on_georef_changed(self, context):
    '''Callback update: propaga i valori verso BGIS e 3DSC se installati.

    NON sposta oggetti di default (move_objects=False). L'utente può
    attivare la traslazione via toggle "move_objects_on_change".
    '''
    from . import bgis_adapter, dsc_adapter

    scene = context.scene
    g = scene.em_georef
    epsg = g.epsg or '4326'

    move_objects = bool(g.move_objects_on_change)
    sync_latlon = bool(g.sync_lat_lon)

    try:
        from ..functions import em_log
    except Exception:
        def em_log(msg, level="INFO"):
            pass

    if bgis_adapter.is_available():
        ok, msg = bgis_adapter.write_state(
            scene, epsg, g.shift_x, g.shift_y,
            move_objects=move_objects, sync_lat_lon=sync_latlon,
        )
        em_log(f"[georef] BGIS push: {msg}", "DEBUG" if ok else "WARNING")

    if dsc_adapter.is_available():
        ok, msg = dsc_adapter.write_state(
            scene, epsg, g.shift_x, g.shift_y, g.shift_z,
        )
        em_log(f"[georef] 3DSC push: {msg}", "DEBUG" if ok else "WARNING")


class EMGeorefProperties(PropertyGroup):
    '''Stato georef di scena — canonico quando gli addon esterni non
    sono installati, altrimenti mirror dell'addon primario.'''

    epsg: StringProperty(
        name="EPSG",
        description="EPSG code of the projected CRS (e.g. 32633 for UTM 33N)",
        default="",
        update=_on_georef_changed,
    )  # type: ignore

    shift_x: FloatProperty(
        name="Shift X",
        description="Easting offset from scene origin, in CRS units (typically meters)",
        default=0.0,
        precision=3,
        update=_on_georef_changed,
    )  # type: ignore

    shift_y: FloatProperty(
        name="Shift Y",
        description="Northing offset from scene origin, in CRS units",
        default=0.0,
        precision=3,
        update=_on_georef_changed,
    )  # type: ignore

    shift_z: FloatProperty(
        name="Shift Z",
        description="Elevation offset from scene origin, in CRS units",
        default=0.0,
        precision=3,
        update=_on_georef_changed,
    )  # type: ignore

    # Toggle avanzati (default conservativi)

    move_objects_on_change: BoolProperty(
        name="Move objects on origin change",
        description=(
            "When editing the shift, translate existing top-level objects "
            "accordingly. OFF by default: safe for scenes with already-"
            "imported shifted geometry (typical archaeological workflow)."
        ),
        default=False,
    )  # type: ignore

    sync_lat_lon: BoolProperty(
        name="Compute lat/lon (needs PyProj)",
        description=(
            "Also derive scene lat/lon from the projected origin via "
            "BlenderGIS reprojection. Requires GDAL or PyProj installed "
            "in Blender's Python. OFF by default."
        ),
        default=False,
    )  # type: ignore


CLASSES = (EMGeorefProperties,)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.em_georef = bpy.props.PointerProperty(type=EMGeorefProperties)


def unregister():
    if hasattr(bpy.types.Scene, 'em_georef'):
        del bpy.types.Scene.em_georef
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
