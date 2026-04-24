"""Facade over :mod:`s3dgraphy.classification` — the canonical source
of truth for stratigraphic type metadata is the JSON datamodel in
s3Dgraphy. This module exposes what the Blender side needs in the
shape that Blender expects:

- :func:`get_us_type_items` — ready-made ``EnumProperty`` items (with
  a module-level cache, as required on macOS to avoid GC'd strings).
- :func:`get_us_class` — resolves ``node_type`` → Python class via
  ``STRATIGRAPHIC_CLASS_MAP``.
- :func:`get_us_color` — ``(r, g, b, a)`` from ``em_visual_rules.json``.
- :func:`get_us_label` — human label from the JSON datamodel.

The full family/series classification is accessible through the
re-exported helpers (``is_real``, ``is_virtual``, ``is_series``,
``REAL_US_TYPES``, …) so callers can ``from .us_types import …``
without reaching into s3dgraphy directly.

Design intent: a single changepoint. If a new US type appears, you
add it to the datamodel JSON + the Python class in s3dgraphy, and the
Blender UI updates automatically.
"""

from __future__ import annotations

from typing import List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────
# Re-export the classification primitives so callers have one import.
# ──────────────────────────────────────────────────────────────────
try:
    from s3dgraphy import (  # noqa: F401
        get_family, is_real, is_virtual, is_series,
        get_subtype_info, iter_subtypes,
        REAL_US_TYPES, VIRTUAL_US_TYPES,
        SERIES_US_TYPES, ALL_US_TYPES,
    )
    from s3dgraphy.utils.utils import (  # noqa: F401
        STRATIGRAPHIC_CLASS_MAP, get_stratigraphic_node_class,
        get_material_color,
    )
except Exception as e:  # pragma: no cover — registration-time safety
    print(f"[us_types] Warning: s3dgraphy classification API not "
          f"available: {e}")
    get_family = lambda _n: None  # noqa: E731
    is_real = is_virtual = is_series = lambda _n: False  # noqa: E731
    get_subtype_info = lambda _n: None  # noqa: E731
    iter_subtypes = lambda: iter(())  # noqa: E731
    REAL_US_TYPES = VIRTUAL_US_TYPES = frozenset()
    SERIES_US_TYPES = ALL_US_TYPES = frozenset()
    STRATIGRAPHIC_CLASS_MAP = {}
    def get_stratigraphic_node_class(_n):
        return None
    def get_material_color(_n, rules_path=None):
        return None


# ──────────────────────────────────────────────────────────────────
# EnumProperty items — Blender needs a stable list of tuples, and on
# macOS the string objects MUST be kept alive in a module-level cache
# (otherwise labels render as garbage). We keep one cache per variant
# of the items function.
# ──────────────────────────────────────────────────────────────────

_US_TYPE_ITEMS_CACHE: dict = {}


def _build_items(include_series: bool,
                 include_special: bool) -> List[Tuple[str, str, str]]:
    """Build the items list from the JSON datamodel, ordered so that
    the most common choices appear first (non-series real → series
    real → non-series virtual → series virtual → special).
    """
    # Bucket by (family, is_series) to get a stable, pedagogically
    # useful ordering.
    real_single, real_series = [], []
    virtual_single, virtual_series = [], []
    specials = []
    for abbr, info in iter_subtypes():
        fam = info.get("family")
        series = bool(info.get("is_series"))
        label = (info.get("label") or abbr)
        display = f"{abbr} — {label}"
        description = (info.get("description") or "").strip()
        # Blender truncates long descriptions in the tooltip; keep it
        # under ~200 chars so the UI stays readable.
        if len(description) > 200:
            description = description[:197] + "..."
        entry = (abbr, display, description)
        if fam == "real":
            (real_series if series else real_single).append(entry)
        elif fam == "virtual":
            (virtual_series if series else virtual_single).append(entry)
        else:
            specials.append(entry)

    items = real_single + virtual_single
    if include_series:
        items += real_series + virtual_series
    if include_special:
        items += specials
    return items


def get_us_type_items(include_series: bool = True,
                      include_special: bool = False
                      ) -> List[Tuple[str, str, str]]:
    """Return ``EnumProperty`` items for a Stratigraphic Unit picker.

    - ``include_series`` (default True): include aggregates like
      ``serSU``, ``serUSVs``, ``serUSVn``, ``serUSD``.
    - ``include_special`` (default False): include helper/special
      types that are not proper US (``BR``, ``SE``) — normally left
      out of creation pickers.

    The result is cached per (include_series, include_special) pair;
    the cached list MUST NOT be mutated by callers (Blender keeps a
    pointer into it).
    """
    key = (include_series, include_special)
    cached = _US_TYPE_ITEMS_CACHE.get(key)
    if cached is not None:
        return cached
    items = _build_items(
        include_series=include_series,
        include_special=include_special)
    _US_TYPE_ITEMS_CACHE[key] = items
    return items


def get_us_type_items_callback_all(self, context):
    """EnumProperty ``items`` callback — full picker (series
    included, specials excluded). Convenience for callers that want
    a drop-in callback without constructing the list manually.
    """
    return get_us_type_items(include_series=True,
                             include_special=False)


def get_us_type_items_callback_no_series(self, context):
    """EnumProperty ``items`` callback — picker without series.
    Useful when the operation semantics don't fit aggregates (e.g.
    drawing a single Surface Areale).
    """
    return get_us_type_items(include_series=False,
                             include_special=False)


# ──────────────────────────────────────────────────────────────────
# Class + material helpers
# ──────────────────────────────────────────────────────────────────

def get_us_class(node_type: str):
    """Return the Python class for ``node_type`` (e.g. ``"USN"`` →
    :class:`NegativeStratigraphicUnit`). Falls back to
    :class:`StratigraphicNode` for unknown types, matching s3Dgraphy.
    """
    return get_stratigraphic_node_class(node_type)


def get_us_label(node_type: str) -> str:
    """Return the human label for ``node_type`` (e.g. ``"Negative SU"``),
    or the abbreviation itself when the type is unknown.
    """
    info = get_subtype_info(node_type)
    if info is None:
        return node_type
    return info.get("label") or node_type


_US_COLOR_CACHE: dict = {}


def get_us_color(node_type: str) -> Optional[Tuple[float, float, float, float]]:
    """Return ``(R, G, B, A)`` in ``[0, 1]`` for ``node_type`` from
    ``em_visual_rules.json``, or ``None`` when the type has no
    material entry. Cached per type.
    """
    if node_type in _US_COLOR_CACHE:
        return _US_COLOR_CACHE[node_type]
    color = get_material_color(node_type)
    _US_COLOR_CACHE[node_type] = color
    return color


# ──────────────────────────────────────────────────────────────────
# Convenience sets for filter-chain consumers — drop-in replacement
# for the hardcoded ``['US', 'USVs', ...]`` lists previously scattered
# across ``functions.py``, ``stratigraphy_manager``, ``landscape_system``,
# ``visual_manager``, ``debug_graph_connections``, etc. Derived from
# the JSON datamodel so adding a new US type (e.g. a future variant
# of USN) is a one-line change in the datamodel.
# ──────────────────────────────────────────────────────────────────

#: Every US type that is "proper" — i.e. has a ``family`` assigned and
#: therefore participates in materials, filters, node_type validation,
#: and the Stratigraphy Manager list. Excludes :data:`BR` / :data:`SE`
#: (helper nodes without a family). Use this wherever you previously
#: wrote ``node.node_type in ['US', 'USVs', ...]``.
US_PROPER_TYPES: frozenset = frozenset(
    abbr for abbr in ALL_US_TYPES if get_family(abbr) is not None)


def us_material_names() -> List[str]:
    """Sorted list variant of :data:`US_PROPER_TYPES` — handy when a
    stable iteration order matters (e.g. material consolidation
    loops). Derived from ``ALL_US_TYPES`` minus BR/SE; the JSON
    datamodel stays the single source of truth.
    """
    return sorted(US_PROPER_TYPES)
