'''
Georef Manager — DP-56.

Pannello unico in EMTools per gestire shift + EPSG della scena,
orchestrando (quando installati) BlenderGIS e 3D Survey Collection.

Design 1.6:
- Fonte canonica di scena: scene.em_georef (PropertyGroup)
- Spie semaforiche per stato sync con BGIS/3DSC
- Edit in EMTools propaga agli addon presenti via API sicure
  (GeoScene.setOriginPrj synch=False, updObjLoc=False)
- GeoPositionNode del grafo: letto all'apertura se la scena non è georiferita,
  altrimenti confrontato (discrepanza + «Pull from graph»); scritto con «Push
  to GeoNode» e a ogni salvataggio (on_save), collegato al gruppo «Graph paradata»
- EPSG deprecato o «ballpark»: avviso e «Convert to EPSG:NNNN» (crs_check)

Moduli:
- shift_io      : parser autonomo per shift.txt (formato 3DSC)
- bgis_adapter  : lazy import, read/write GeoScene senza side effect
- dsc_adapter   : lazy read/write di scene.BL_* props di 3DSC
- graph_sync    : accesso grafo attivo + push/pull GeoPositionNode, lettura
                  all'apertura, discrepanze, shift esatto (i campi sono float32)
- crs_check     : il CRS come lo sa il database di PROJ (deprecato, sostituto,
                  stessa griglia, accuratezza), senza bpy
- propagation   : push verso BGIS/3DSC; EPSG vuoto = non georiferito, mai 4326
- props         : EMGeorefProperties su Scene (+ update callbacks)
- operators     : Import/Export/Sync/Pull/PushGeoNode/PullGraph/ConvertEPSG
- panel         : EM_PT_georef (tab "EM", default closed)
- graph_align   : G1, più grafi in una scena (bpy-free: shift, convergenza)
- graph_align_ops : «Align graphs to the scene» (sposta e dichiara)
- on_save       : il georiferimento della scena nel grafo a ogni salvataggio
- i18n          : le frasi del pannello in it/de (fr/es da validare), con
                  bpy.app.translations
'''

from __future__ import annotations

from . import props, operators, panel, graph_align_ops, i18n


def register():
    i18n.register()
    props.register()
    operators.register()
    graph_align_ops.register()
    panel.register()


def unregister():
    panel.unregister()
    graph_align_ops.unregister()
    operators.unregister()
    props.unregister()
    i18n.unregister()
