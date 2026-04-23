'''
Adapter lazy verso BlenderGIS.

Non importa BGIS a livello di modulo: ogni funzione fa import on-demand,
così il modulo EMTools resta usabile anche quando BGIS non è installato.

Regola d'oro: usiamo l'API `GeoScene` di BGIS senza MAI passare dai
`window_manager.geoscnProps`, per evitare i callback che spostano gli
oggetti in scena. Scriviamo con `setOriginPrj(synch=False)` per non
innescare reprojection verso WGS84 (che richiede GDAL/PyProj) e con
`updObjLoc=False` per non traslare le geometrie già importate.
'''

from __future__ import annotations

from typing import Optional, Tuple


def is_available() -> bool:
    '''True se BGIS risulta importabile come modulo Python.'''
    try:
        import BlenderGIS  # noqa: F401
        return True
    except Exception:
        try:
            from BlenderGIS import geoscene  # noqa: F401
            return True
        except Exception:
            return False


def _get_geoscene(scene):
    from BlenderGIS.geoscene import GeoScene
    return GeoScene(scene)


def read_state(scene) -> Optional[dict]:
    '''Ritorna {epsg, shift_x, shift_y} letti da BGIS, o None se non disponibile.

    BGIS non gestisce shift_z: lo shift verticale è un'estensione nativa
    di 3DSC / EMTools. Il caller unisce le due fonti.
    '''
    if not is_available():
        return None
    try:
        gs = _get_geoscene(scene)
        state = {'epsg': None, 'shift_x': None, 'shift_y': None}
        if gs.hasValidCRS:
            crs = gs.crs or ''
            state['epsg'] = crs.replace('EPSG:', '').strip() or None
        if gs.hasOriginPrj:
            x, y = gs.getOriginPrj()
            state['shift_x'] = float(x)
            state['shift_y'] = float(y)
        return state
    except Exception:
        return None


def write_state(
    scene,
    epsg: str,
    shift_x: float,
    shift_y: float,
    *,
    move_objects: bool = False,
    sync_lat_lon: bool = False,
) -> Tuple[bool, str]:
    '''Scrive CRS + origin su BGIS senza side effect sulle geometrie.

    Strategia: reset di origin-geo e origin-prj, poi set del CRS, poi
    set dell'origin proiettato. Con `move_objects=False` (default) e
    `sync_lat_lon=False` (default) la chiamata è no-op per le mesh.

    Ritorna (success, message).
    '''
    if not is_available():
        return False, "BlenderGIS not available"
    try:
        gs = _get_geoscene(scene)

        if gs.hasOriginGeo:
            gs.delOriginGeo()

        if move_objects and gs.hasOriginPrj and gs.hasValidCRS:
            # Traslazione esplicita richiesta: usiamo updOriginPrj per
            # spostare le geometrie di conseguenza.
            try:
                gs.crs = f'EPSG:{epsg}'
            except Exception:
                gs.delOriginPrj()
                gs.crs = f'EPSG:{epsg}'
                gs.setOriginPrj(shift_x, shift_y, synch=sync_lat_lon)
                return True, "BGIS origin set (no prior origin to translate from)"
            gs.updOriginPrj(
                shift_x,
                shift_y,
                updObjLoc=True,
                synch=sync_lat_lon,
            )
            return True, "BGIS origin updated, objects translated"

        # Via sicura: reset e set senza side effect.
        if gs.hasOriginPrj:
            gs.delOriginPrj()
        gs.crs = f'EPSG:{epsg}'
        gs.setOriginPrj(shift_x, shift_y, synch=sync_lat_lon)
        return True, "BGIS origin set (no object movement)"
    except Exception as e:
        return False, f"BGIS write failed: {e}"
