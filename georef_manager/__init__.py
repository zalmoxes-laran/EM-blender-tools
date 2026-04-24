'''
Georef Manager — DP-56.

Pannello unico in EMTools per gestire shift + EPSG della scena,
orchestrando (quando installati) BlenderGIS e 3D Survey Collection.

Design 1.6:
- Fonte canonica di scena: scene.em_georef (PropertyGroup)
- Spie semaforiche per stato sync con BGIS/3DSC
- Edit in EMTools propaga agli addon presenti via API sicure
  (GeoScene.setOriginPrj synch=False, updObjLoc=False)
- GeoPositionNode del grafo = specchio passivo, aggiornato al save/export
- NO reprojection CRS in questo scope (pianificata in Phase 2)

Moduli:
- shift_io      : parser autonomo per shift.txt (formato 3DSC)
- bgis_adapter  : lazy import, read/write GeoScene senza side effect
- dsc_adapter   : lazy read/write di scene.BL_* props di 3DSC
- graph_sync    : accesso grafo attivo + push/pull GeoPositionNode
- props         : EMGeorefProperties su Scene (+ update callbacks)
- operators     : Import/Export/Sync/Pull/PushGeoNode
- panel         : EM_PT_georef (tab "EM", default closed)
'''

from __future__ import annotations

from . import props, operators, panel


def register():
    props.register()
    operators.register()
    panel.register()


def unregister():
    panel.unregister()
    operators.unregister()
    props.unregister()
