'''
Il CRS del georiferimento come lo conosce il database di PROJ — senza bpy.

Gemello di ``EMStudio/tools/em_geotiles.py`` (``crs_info`` / ``same_grid`` /
``convert_point``, bridge livello 38): le stesse domande, le stesse risposte,
fatte qui con il pyproj del Python di Blender (Blender 5.2 lo porta con sé:
pyproj 3.7.2). Niente rete: tutto viene da ``proj.db``.

- **Deprecato**: la colonna ``deprecated`` della tabella del CRS; i sostituti
  vengono dalle tabelle ``deprecation`` e ``supersession`` dello stesso
  database — mai da una tabella scritta a mano (31700 → 3844 è il caso di
  prova, non una regola di questo file).
- **Ballpark**: la trasformazione che PROJ sceglie per andare a WGS 84 nel
  punto dello shift non cambia datum (è la parola di PROJ, «Ballpark
  geographic offset»): accuratezza sconosciuta, al GT16 ~127 m.
- **Stessa griglia**: stessa proiezione, stessi parametri, stesso ellissoide,
  stesse unità; cambia solo il datum dichiarato. Le coordinate sono gli
  stessi numeri: convertire è cambiare il codice, lo shift resta.
- **Griglia diversa**: lo shift si riproietta con l'operazione migliore per
  quel punto, e l'accuratezza si dice.

Senza pyproj nessuna risposta inventata: ``available()`` è falso e il
pannello dice che il controllo non si può fare.
'''

from __future__ import annotations

import functools
import math
import os
from typing import Optional


def available() -> bool:
    try:
        import pyproj  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _proj_db():
    import sqlite3
    import pyproj
    path = os.path.join(pyproj.datadir.get_data_dir(), 'proj.db')
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _op_at(src, dst, x, y):
    '''L'operazione che PROJ usa per un punto di ``src`` (la prima, nel suo
    ordine di preferenza, la cui area d'uso contiene il punto) e il punto
    trasformato. None se nessuna risponde.'''
    from pyproj import Transformer
    from pyproj.transformer import TransformerGroup
    tg = TransformerGroup(src, dst, always_xy=True)
    try:
        lon, lat = Transformer.from_crs(src, 4326, always_xy=True).transform(x, y)
    except Exception:  # noqa: BLE001
        lon = lat = None
    first = None
    for t in tg.transformers:
        try:
            a, b = t.transform(x, y)
        except Exception:  # noqa: BLE001 — un candidato che qui non gira
            continue
        if not (math.isfinite(a) and math.isfinite(b)):
            continue
        aou = t.area_of_use
        inside = (aou is None or lon is None
                  or (aou.west <= lon <= aou.east and aou.south <= lat <= aou.north)
                  or (aou.west > aou.east and (lon >= aou.west or lon <= aou.east)
                      and aou.south <= lat <= aou.north))
        hit = (t, a, b)
        if inside:
            return hit
        first = first or hit
    return first


def _op_words(t):
    '''Un'operazione come la dice il pannello: nome, accuratezza (metri, None
    = sconosciuta) e se è un «ballpark».'''
    acc = t.accuracy if t.accuracy is not None and t.accuracy >= 0 else None
    steps = [st for st in t.description.split(" + ")
             if not st.startswith("axis order change") and not st.startswith("Inverse of ")]
    name = " + ".join(steps) or t.description
    return {"name": name, "accuracy": acc, "ballpark": "ballpark" in t.description.lower()}


def same_grid(a: int, b: int) -> bool:
    '''Due CRS proiettati sulla stessa griglia: le loro coordinate sono gli
    stessi numeri, e convertire è cambiare solo il codice.'''
    from pyproj import CRS
    A, B = CRS.from_epsg(int(a)), CRS.from_epsg(int(b))
    if not (A.is_projected and B.is_projected):
        return False
    oa, ob = A.coordinate_operation, B.coordinate_operation
    if oa is None or ob is None or oa.method_name != ob.method_name:
        return False
    pa = sorted((p.name, round(float(p.value), 9), p.unit_name) for p in oa.params)
    pb = sorted((p.name, round(float(p.value), 9), p.unit_name) for p in ob.params)
    ea, eb = A.ellipsoid, B.ellipsoid
    units = [ax.unit_name for ax in A.axis_info] == [ax.unit_name for ax in B.axis_info]
    return pa == pb and units and abs(ea.semi_major_metre - eb.semi_major_metre) < 1e-6 \
        and abs((ea.inverse_flattening or 0) - (eb.inverse_flattening or 0)) < 1e-6


def convert_point(src: int, dst: int, x: float, y: float) -> dict:
    '''Uno shift da un CRS a un altro con l'operazione migliore per quel punto,
    e la sua accuratezza. Stessa griglia: gli stessi numeri (nessuna operazione).'''
    if same_grid(src, dst):
        return {"ok": True, "x": float(x), "y": float(y), "same_grid": True, "op": None}
    hit = _op_at(int(src), int(dst), float(x), float(y))
    if not hit:
        return {"ok": False,
                "error": f"PROJ has no operation from EPSG:{src} to EPSG:{dst} for this point"}
    t, a, b = hit
    return {"ok": True, "x": a, "y": b, "same_grid": False, "op": _op_words(t)}


def crs_info(epsg: int, x=None, y=None) -> dict:
    '''Cosa serve sapere del CRS di un georiferimento, dal database di PROJ:
    nome e tipo; se EPSG l'ha deprecato e i codici che il database dà come
    sostituti (ognuno con «stessa griglia» sì/no); l'operazione verso WGS 84
    che PROJ usa nel punto (x, y) — lo shift — con l'accuratezza e se è un
    ballpark. Stessa forma di ``/geo/crs-info`` del bridge di EMStudio.'''
    from pyproj import CRS
    epsg = int(epsg)
    try:
        crs = CRS.from_epsg(epsg)
    except Exception as exc:  # noqa: BLE001 — un codice sconosciuto
        return {"ok": False, "epsg": epsg,
                "error": f"EPSG:{epsg} is not in PROJ's database ({exc})"}
    kind = "projected" if crs.is_projected else "geographic" if crs.is_geographic else crs.type_name
    table = "projected_crs" if crs.is_projected else "geodetic_crs"
    repl = []
    with _proj_db() as db:
        row = db.execute(f"SELECT deprecated FROM {table} WHERE auth_name='EPSG' AND code=?",
                         (str(epsg),)).fetchone()
        deprecated = bool(row and row[0])
        seen = set()
        rows = db.execute(
            "SELECT replacement_code, source FROM deprecation WHERE table_name=? "
            "AND deprecated_auth_name='EPSG' AND deprecated_code=? "
            "AND replacement_auth_name='EPSG'", (table, str(epsg))).fetchall()
        rows += db.execute(
            "SELECT replacement_code, source FROM supersession WHERE superseded_table_name=? "
            "AND superseded_auth_name='EPSG' AND superseded_code=? "
            "AND replacement_auth_name='EPSG'", (table, str(epsg))).fetchall()
        for code, source in rows:
            c = int(code)
            if c in seen:
                continue
            seen.add(c)
            try:
                name = CRS.from_epsg(c).name
            except Exception:  # noqa: BLE001
                name = ""
            repl.append({"epsg": c, "name": name,
                         "same_grid": same_grid(epsg, c) if crs.is_projected else False,
                         "source": source or "EPSG"})
    to = None
    if epsg != 4326:
        if x is None or y is None:
            aou = crs.area_of_use
            if aou is not None:
                from pyproj import Transformer
                x, y = Transformer.from_crs(4326, epsg, always_xy=True).transform(
                    (aou.west + aou.east) / 2, (aou.south + aou.north) / 2)
        hit = _op_at(epsg, 4326, float(x), float(y)) if x is not None else None
        to = _op_words(hit[0]) if hit else None
    for r in repl:
        # l'operazione del sostituto verso WGS 84, nello stesso punto (portato
        # sulla sua griglia quando è un'altra)
        r["to_wgs84"] = None
        r["shift"] = None
        if x is None:
            continue
        rx, ry = float(x), float(y)
        if not r["same_grid"]:
            c = convert_point(epsg, r["epsg"], rx, ry)
            if not c.get("ok"):
                continue
            rx, ry = c["x"], c["y"]
            r["convert_op"] = c.get("op")
        r["shift"] = (rx, ry)
        hit = _op_at(r["epsg"], 4326, rx, ry)
        r["to_wgs84"] = _op_words(hit[0]) if hit else None
    return {"ok": True, "epsg": epsg, "name": crs.name, "kind": kind,
            "deprecated": deprecated, "replacements": repl, "to_wgs84": to}


@functools.lru_cache(maxsize=32)
def _cached_info(epsg: int, x: float, y: float) -> dict:
    return crs_info(epsg, x, y)


def accuracy_words(op: Optional[dict]) -> str:
    '''«±3 m», «unknown (ballpark)», «unknown».'''
    if not op:
        return "unknown"
    if op.get("accuracy") is not None:
        acc = float(op["accuracy"])
        return "exact (±0 m)" if acc == 0 else f"±{acc:g} m"
    return "unknown (ballpark)" if op.get("ballpark") else "unknown"


def proposal(epsg, x: float = 0.0, y: float = 0.0) -> Optional[dict]:
    '''La proposta da mostrare per un EPSG, o None se non c'è niente da dire.

    ``{"info", "warn", "reason", "accuracy", "replacement", "unavailable"}``:
    ``warn`` è vero se il codice è deprecato o la trasformazione usata è un
    ballpark; ``replacement`` è il sostituto scelto (il primo sulla stessa
    griglia, altrimenti il primo dato dal database) con ``same_grid``, il nuovo
    shift e l'accuratezza dopo. Senza pyproj: ``{"unavailable": True}``.
    Il risultato è in cache per (epsg, shift arrotondato al metro): il
    pannello lo chiede a ogni ridisegno. Per questo lo ``shift`` del sostituto
    qui è indicativo (al metro): la conversione vera lo ricalcola dallo shift
    esatto (``convert_point``).
    '''
    raw = str(epsg).strip() if epsg is not None else ''
    if not raw.isdigit():
        return None
    if not available():
        return {"unavailable": True}
    try:
        info = _cached_info(int(raw), round(float(x)), round(float(y)))
    except Exception as exc:  # noqa: BLE001 — un PROJ rotto si dice, non si tace
        return {"unavailable": True, "error": str(exc)}
    if not info.get("ok"):
        return {"info": info, "warn": True, "reason": info.get("error", ""),
                "accuracy": "unknown", "replacement": None}
    op = info.get("to_wgs84")
    ballpark = bool(op and op.get("ballpark"))
    reasons = []
    if info["deprecated"]:
        reasons.append(f"EPSG:{info['epsg']} ({info['name']}) is deprecated in the EPSG database")
    if ballpark:
        reasons.append("PROJ reaches WGS 84 from it only with a «ballpark» "
                       "(no datum shift): accuracy unknown, can be ~100 m")
    repl = None
    cands = info.get("replacements") or []
    if cands:
        repl = next((r for r in cands if r["same_grid"]), cands[0])
    return {"info": info, "warn": bool(info["deprecated"] or ballpark),
            "reason": "; ".join(reasons), "accuracy": accuracy_words(op),
            "operation": (op or {}).get("name", ""), "replacement": repl}
