'''
G1 · Più grafi in una scena, ognuno col suo georiferimento.

Il sistema di riferimento della scena è quello del **primo grafo caricato**
(si può cambiare): il suo GeoPositionNode dice in quale CRS stanno le
coordinate locali della scena e quale punto vale (0, 0, 0). Ogni altro grafo
ha il suo GeoPositionNode (epsg, shift_x/y/z, rotation) e le sue geometrie
sono locali al SUO ancoraggio. Qui si calcola dove va quel sistema locale
dentro la scena:

* **stesso EPSG** → la differenza degli shift (e delle rotazioni);
* **EPSG diverso** → l'origine del grafo si riproietta nel CRS della scena, e
  la rotazione attorno a Z è la **convergenza** fra i due reticoli in quel
  punto (il nord del reticolo dell'altro CRS visto nel reticolo della scena).
  La riproiezione la fa chi c'è: ``/v1/reproject`` del server se raggiungibile,
  altrimenti pyproj locale, altrimenti si dice che serve e non si inventa.

**Cosa vuol dire ``rotation`` qui.** È l'azimut dell'asse +Y locale, in gradi,
in senso orario, misurato sul **nord del reticolo** del CRS del grafo. Con
``rotation = 0`` gli assi locali SONO gli assi del CRS meno lo shift — che è
come si costruisce un modello shiftato (3DSC, BlenderGIS). Il docstring di
Da D2 (E.D., 4 ottobre 2026) lo dice anche s3Dgraphy, docstring e dato
(``rotation_reference = "grid"``): prima diceva «nord geografico». La differenza
fra i due è la convergenza del CRS in quel punto, che per un grafo da solo
nessuno applica; fra due grafi conta la convergenza RELATIVA, ed è quella
calcolata.

**Cosa NON si applica, e si dice.** Il fattore di scala fra i due reticoli
(``scale``, tipicamente 1 ± 1e-3 fra zone UTM vicine) è misurato e riportato ma
non applicato: si sposta e si ruota, non si deforma un rilievo. Le quote non si
convertono fra datum verticali: si applica la differenza degli shift_z.

Niente ``bpy``: si misura con pytest.
'''

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Sequence, Tuple

Point2 = Tuple[float, float]
#: ``reproject(points, epsg_source, epsg_target) -> points``
Reprojector = Callable[[Sequence[Point2], int, int], List[Point2]]

#: Passo, in unità del CRS (metri), con cui si misura il nord del reticolo.
NORTH_STEP = 100.0


@dataclass(frozen=True)
class Anchor:
    '''Il georiferimento di un grafo, letto dal suo GeoPositionNode.'''

    epsg: Optional[int]
    shift_x: float = 0.0
    shift_y: float = 0.0
    shift_z: float = 0.0
    rotation: float = 0.0

    @property
    def georeferenced(self) -> bool:
        return self.epsg is not None


def anchor_from_data(data: Any) -> Anchor:
    '''Da ``node.data`` (o da un dict) a :class:`Anchor`. Senza epsg → non
    georiferito (mai 4326 per difetto, s3Dgraphy dev29 A6).'''
    data = data if isinstance(data, dict) else {}
    raw = data.get('epsg')
    epsg = None
    if raw is not None and str(raw).strip().isdigit():
        epsg = int(str(raw).strip())

    def f(key):
        try:
            return float(data.get(key) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return Anchor(epsg, f('shift_x'), f('shift_y'), f('shift_z'), f('rotation'))


@dataclass
class Placement:
    '''Dove va il sistema locale di un grafo nella scena, e perché.

    ``dx, dy, dz`` è la traslazione (in metri di scena) e ``rot_z_deg`` la
    rotazione attorno a Z, antioraria come in Blender: un punto locale ``p``
    del grafo va in ``Rz(rot_z) · p + (dx, dy, dz)``.
    '''

    ok: bool
    dx: float = 0.0
    dy: float = 0.0
    dz: float = 0.0
    rot_z_deg: float = 0.0
    method: str = ''            # 'reference' | 'same-epsg' | 'reprojected' | 'refused'
    convergence_deg: float = 0.0
    scale: float = 1.0
    via: str = ''               # chi ha riproiettato: 'server' | 'pyproj' | ''
    notes: List[str] = field(default_factory=list)

    def sentence(self) -> str:
        '''La dichiarazione, in una riga: cosa si è applicato.'''
        if not self.ok:
            return '; '.join(self.notes) or 'not placed'
        if self.method == 'reference':
            return 'reference graph: the scene is in its CRS, nothing applied'
        head = (f"moved by ({self.dx:.3f}, {self.dy:.3f}, {self.dz:.3f}) m, "
                f"rotated {self.rot_z_deg:+.4f}° about Z")
        if self.method == 'same-epsg':
            head += ' — same EPSG: difference of the shifts'
        else:
            head += (f" — EPSG reprojected via {self.via}: grid convergence "
                     f"{self.convergence_deg:+.4f}°, scale {self.scale:.6f} "
                     f"(measured, not applied)")
        return '; '.join([head] + self.notes)


#: Q7 · CRSs whose coordinates are DEGREES: a metric Blender scene cannot sit
#: in one (a metre of the scene would be a degree, ~111 km). The common ones;
#: an EPSG not listed here is taken as projected, which is what a scene needs.
GEOGRAPHIC = {4326: "WGS 84", 4258: "ETRS89", 4230: "ED50", 4269: "NAD83",
              4267: "NAD27", 4283: "GDA94", 4612: "JGD2000", 4019: "GRS 1980",
              4979: "WGS 84 3D", 4937: "ETRS89 3D"}


def projected_for(epsg: Optional[int], x: float = 0.0, y: float = 0.0
                  ) -> Optional[Tuple[int, str]]:
    """For a geographic EPSG: (the UTM EPSG to propose, the sentence); None
    for a projected one. ``x``/``y`` are the origin in that CRS — longitude
    and latitude — and choose the zone; with no origin, nothing is guessed."""
    if epsg not in GEOGRAPHIC:
        return None
    name = GEOGRAPHIC[epsg]
    head = (f"EPSG {epsg} ({name}) is in degrees: a metric scene cannot sit in it — "
            f"one unit of the scene would be a degree.")
    if not (-180.0 <= x <= 180.0 and -90.0 <= y <= 90.0) or (x == 0.0 and y == 0.0):
        return (0, head + " Choose a projected CRS (UTM or the national grid).")
    zone = int((x + 180.0) // 6.0) + 1
    zone = min(max(zone, 1), 60)
    base = 25800 if epsg in (4258, 4937) and y >= 0 else (32600 if y >= 0 else 32700)
    if base == 25800 and not 28 <= zone <= 38:      # ETRS89 / UTM covers 28–38
        base = 32600
    proposed = base + zone
    label = ("ETRS89 / UTM" if base == 25800 else "WGS 84 / UTM") + \
        f" zone {zone}{'N' if y >= 0 else 'S'}"
    return (proposed, head + f" Proposed: EPSG {proposed} ({label}), the zone of "
                             f"the origin ({x:.4f}, {y:.4f}).")


def _rot(x: float, y: float, deg: float) -> Point2:
    '''Rotazione antioraria di ``deg`` gradi.'''
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (c * x - s * y, s * x + c * y)


def convergence(reproject: Reprojector, x: float, y: float,
                epsg_source: int, epsg_target: int,
                step: float = NORTH_STEP) -> Tuple[Point2, float, float]:
    '''Il punto ``(x, y)`` del CRS sorgente nel CRS di destinazione, con la
    convergenza (gradi, antioraria) e la scala del reticolo sorgente visto da lì.

    Si riproiettano DUE punti in una chiamata: l'origine e un punto ``step``
    metri a nord sul reticolo sorgente. L'angolo del segmento d'arrivo dal
    nord del reticolo di destinazione è la convergenza relativa; la sua
    lunghezza diviso ``step`` è la scala.
    '''
    out = reproject([(x, y), (x, y + step)], epsg_source, epsg_target)
    (x0, y0), (x1, y1) = out[0], out[1]
    vx, vy = x1 - x0, y1 - y0
    delta = math.degrees(math.atan2(-vx, vy))
    return (x0, y0), delta, math.hypot(vx, vy) / step


def place(reference: Anchor, other: Anchor,
          reproject: Optional[Reprojector] = None, *,
          via: str = '', missing: str = '') -> Placement:
    '''Dove va ``other`` nella scena il cui CRS è quello di ``reference``.

    ``reproject`` serve solo se gli EPSG differiscono; se manca, il risultato
    è un rifiuto che dice cosa serve (``missing``), non una posizione inventata.
    '''
    if other is reference or other == reference:
        return Placement(True, method='reference')
    if not reference.georeferenced or not other.georeferenced:
        who = 'the reference graph' if not reference.georeferenced else 'this graph'
        return Placement(False, method='refused', notes=[
            f"{who} declares no EPSG: not georeferenced, nothing to align "
            f"(set its georeferencing first)"])

    dz = other.shift_z - reference.shift_z
    if reference.epsg == other.epsg:
        ex, ey = other.shift_x - reference.shift_x, other.shift_y - reference.shift_y
        dx, dy = _rot(ex, ey, reference.rotation)
        return Placement(True, dx, dy, dz,
                         rot_z_deg=reference.rotation - other.rotation,
                         method='same-epsg')

    if reproject is None:
        return Placement(False, method='refused', notes=[
            f"EPSG {other.epsg} ≠ scene EPSG {reference.epsg}: a reprojection "
            f"is needed — {missing or 'no server reachable and no pyproj installed'}"])
    try:
        (px, py), delta, scale = convergence(
            reproject, other.shift_x, other.shift_y, other.epsg, reference.epsg)
    except Exception as exc:  # noqa: BLE001 — the reason goes to the person
        return Placement(False, method='refused', notes=[
            f"reprojection EPSG {other.epsg} → {reference.epsg} failed: {exc}"])
    dx, dy = _rot(px - reference.shift_x, py - reference.shift_y,
                  reference.rotation)
    notes = ['heights: difference of shift_z, no vertical datum conversion']
    return Placement(True, dx, dy, dz,
                     rot_z_deg=reference.rotation + delta - other.rotation,
                     method='reprojected', convergence_deg=delta, scale=scale,
                     via=via, notes=notes)


def apply_point(placement: Placement, p: Sequence[float]) -> Tuple[float, float, float]:
    '''Un punto locale del grafo nella scena (per le prove e per chi non ha
    matrici): ``Rz · p + d``.'''
    x, y = _rot(float(p[0]), float(p[1]), placement.rot_z_deg)
    z = float(p[2]) if len(p) > 2 else 0.0
    return (x + placement.dx, y + placement.dy, z + placement.dz)


# ── chi riproietta ───────────────────────────────────────────────────────────

def server_reprojector(base_url: str, token: Optional[str] = None,
                       timeout: float = 5.0) -> Reprojector:
    '''``POST /v1/reproject`` (forma a lotti: un transformer solo).'''
    url = base_url.rstrip('/') + '/v1/reproject'

    def run(points, epsg_source, epsg_target):
        body = json.dumps({'points': [[float(x), float(y)] for x, y in points],
                           'epsg_source': int(epsg_source),
                           'epsg_target': int(epsg_target)}).encode('utf-8')
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        req = urllib.request.Request(url, data=body, headers=headers,
                                     method='POST')
        try:        # the node behind Caddy too (sync_manager/trust.py)
            from ..sync_manager.access import urlopen as _open
        except ImportError:  # loaded by path, outside the package (the suite)
            _open = urllib.request.urlopen
        with _open(req, timeout=timeout) as resp:
            doc = json.loads(resp.read().decode('utf-8'))
        return [(float(x), float(y)) for x, y in doc['points']]
    return run


def pyproj_reprojector() -> Optional[Reprojector]:
    '''pyproj locale, se installato nel Python di Blender; altrimenti None.'''
    try:
        from pyproj import Transformer  # type: ignore
    except Exception:  # noqa: BLE001
        return None

    def run(points, epsg_source, epsg_target):
        tr = Transformer.from_crs(int(epsg_source), int(epsg_target),
                                  always_xy=True)
        return [tuple(map(float, tr.transform(x, y))) for x, y in points]
    return run


def choose_reprojector(base_url: Optional[str] = None,
                       token: Optional[str] = None,
                       probe: Optional[Tuple[int, int]] = None
                       ) -> Tuple[Optional[Reprojector], str, str]:
    '''``(reprojector, via, perché_no)``: il server se risponde, poi pyproj.

    Il server si prova davvero (una riproiezione dell'origine se ``probe`` è
    dato): un indirizzo nel campo non è un server raggiungibile.
    '''
    why = []
    if base_url:
        cand = server_reprojector(base_url, token)
        try:
            if probe:
                cand([(0.0, 0.0)], probe[0], probe[0])
            return cand, 'server', ''
        except urllib.error.HTTPError as exc:
            why.append(f"server {base_url} answered {exc.code}")
        except Exception as exc:  # noqa: BLE001
            why.append(f"server {base_url} not reachable ({exc})")
    else:
        why.append('no server address')
    local = pyproj_reprojector()
    if local is not None:
        return local, 'pyproj', ''
    why.append("pyproj is not installed in Blender's Python")
    return None, '', '; '.join(why)
