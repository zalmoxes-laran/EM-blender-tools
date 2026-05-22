"""Filter value cache for EM-tools mapped importers.

The cache is keyed by (filepath, mtime, column) so distinct values are
re-queried from disk only when the source file actually changes.

Used by the dynamic EnumProperty callbacks that populate the
``pyarchinit_filter_N`` dropdowns in the import panels. Storing the
returned ``list`` here also keeps a strong reference alive across
draw passes, avoiding the well-known Blender enum garbage-collection
crash where item strings get freed before Blender finishes painting.
"""

from __future__ import annotations


_CACHE: dict = {}


def get(filepath: str, mtime: float, column: str):
    """Return cached distinct values for ``column`` or ``None``."""
    return _CACHE.get((filepath, mtime, column))


def put(filepath: str, mtime: float, column: str, values: list):
    """Store distinct ``values`` for ``column`` in the cache."""
    _CACHE[(filepath, mtime, column)] = values


def clear():
    """Empty the cache (e.g. on add-on reload or explicit refresh)."""
    _CACHE.clear()
