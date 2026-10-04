"""U2 · «Offset proxy» (it. «Scosta il proxy»): the proxy a little outside the
surface it annotates, so that it does not z-fight with the RM.

MICRO-EMTOOLS-MENO-E-MEGLIO, decided by E.D. on 4 October 2026: the inflation
(Solidify, `proxy_inflate_manager/`, now in `_dead_code/`) did not work well,
and its real purpose was this one. Measured on Templu Mare the same day: 34
proxies of the reconstruction (GT16.USV1xx, GT16.T2x–T4x, GT16.VSF141) lie on
the RM surfaces they annotate, more than half of their vertices within 5 mm
and the median within 0.02 mm — coplanar, and so z-fighting in the viewport.

ONE gesture, NOT destructive: a Displace modifier named «EM offset» that moves
each vertex along its normal by a small distance (the mesh is untouched, the
modifier can be removed), for the active proxy, the selection or every proxy
of the stratigraphy list. The distance is one value of the scene; changing it
moves every proxy already offset.
"""

from typing import Iterable, List

MODIFIER = "EM offset"
#: the Solidify modifiers of the old inflation, recognised to be removed
OLD_INFLATE_SUFFIX = "_inflate"
#: measured on Templu Mare, 4 Oct 2026, GT16.USV140 on the podium's RM
#: (tests/blender_shots_proxy_offset.py, the report has the shots), with the
#: viewport's clip range 0.01–1000 m: from 15 m, 2 mm and 5 mm are already clean;
#: from 40 m — the whole temple in view — 2 mm still speckles, 5 mm a little,
#: 10 mm is clean. 1 cm on a building is below what a proxy annotates
DEFAULT_DISTANCE = 0.01


def offset_names(modifier_names: Iterable[str]) -> List[str]:
    """Pure: which of these modifiers are the offset."""
    return [n for n in modifier_names if n == MODIFIER]


def old_inflate_names(modifier_names: Iterable[str]) -> List[str]:
    """Pure: which of these modifiers are the old inflation's."""
    return [n for n in modifier_names if str(n).endswith(OLD_INFLATE_SUFFIX)]


def said(verb: str, count: int, distance: float) -> str:
    """The sentence of the gesture, the same from every button."""
    mm = f"{distance * 1000:g} mm"
    if count == 0:
        return "no proxy to " + ("offset" if verb == "offset" else "bring back") + " here"
    if verb == "offset":
        return f"{count} prox{'y' if count == 1 else 'ies'} offset by {mm} from the surface"
    return f"{count} prox{'y' if count == 1 else 'ies'} back on the surface"


def register():  # pragma: no cover — bpy
    from . import operators, ui
    operators.register()
    ui.register()


def unregister():  # pragma: no cover — bpy
    from . import operators, ui
    ui.unregister()
    operators.unregister()
