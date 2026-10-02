'''
Propagazione di scene.em_georef verso BlenderGIS e 3DSC — senza bpy.

Un campo EPSG vuoto vuol dire «non georiferito», mai EPSG 4326: è la stessa
regola di s3Dgraphy dev29 (A6) e di graph_sync per il GeoPositionNode.
Senza EPSG:
- a BlenderGIS non si dà nessun CRS (non lo si chiama: il suo stato resta
  com'era);
- a 3DSC arriva lo shift con EPSG assente (il suo adapter scrive 'NotSet',
  la sentinella di 3DSC per «nessun CRS»).
Con un EPSG impostato il comportamento è quello di prima.

Usato dal callback di update (props) e da "Propagate coordinates"
(operators), così le due vie non possono divergere.
'''

from __future__ import annotations

from typing import List, Optional, Tuple

#: Riga di stato del pannello quando l'EPSG manca.
NOT_GEOREFERENCED = "Not georeferenced (no EPSG)"

#: Messaggio quando BlenderGIS viene lasciato com'era per mancanza di EPSG.
BGIS_SKIPPED = "no EPSG: not georeferenced, BlenderGIS CRS left untouched"


def epsg_or_none(raw) -> Optional[str]:
    '''L'EPSG come stringa ripulita, o None se assente.

    Vuoto, solo spazi e 'NotSet' (la sentinella di 3DSC) sono "assente".
    '''
    if raw is None:
        return None
    value = str(raw).strip()
    if not value or value.lower() == 'notset':
        return None
    return value


def push_to_addons(scene, g, bgis_adapter, dsc_adapter, *, log) -> List[Tuple[str, str, str]]:
    '''Spinge epsg/shift di ``g`` verso gli addon installati.

    Ritorna una lista di (addon, esito, messaggio) con esito in
    'ok' / 'fail' / 'skipped'.
    '''
    epsg = epsg_or_none(g.epsg)
    results = []

    if bgis_adapter.is_available():
        if epsg is None:
            results.append(('BGIS', 'skipped', BGIS_SKIPPED))
            log(f"[georef] BGIS push: {BGIS_SKIPPED}", "DEBUG")
        else:
            ok, msg = bgis_adapter.write_state(
                scene, epsg, g.shift_x, g.shift_y,
                move_objects=bool(g.move_objects_on_change),
                sync_lat_lon=bool(g.sync_lat_lon),
            )
            results.append(('BGIS', 'ok' if ok else 'fail', msg))
            log(f"[georef] BGIS push: {msg}", "DEBUG" if ok else "WARNING")

    if dsc_adapter.is_available():
        ok, msg = dsc_adapter.write_state(
            scene, epsg, g.shift_x, g.shift_y, g.shift_z,
        )
        results.append(('3DSC', 'ok' if ok else 'fail', msg))
        log(f"[georef] 3DSC push: {msg}", "DEBUG" if ok else "WARNING")

    return results
