"""Resolve a pyunitastratigrafiche row to its s3dgraphy US node (issue #34).

Pure-Python (same pattern as ``reimport_planner``) so it is unit-testable
without Blender. Resolution order: the ``node_uuid`` the mapping turns
into ``node_id`` → the label composed with the mapping's own rule
(``table_settings.node_name_template``) → the bare ``us`` number — the
reader's historical behaviour, kept so a graph whose names are the
numbers still hooks up.
"""

import re

from .geom_constants import GRAPH_ATTR_AUX_US_NO_GEOM

#: the template of s3dgraphy's pyArchInit mapping, used when the caller
#: does not pass the one it read from the mapping file
DEFAULT_NAME_TEMPLATE = "{area}.{settore}.{unita_tipo}{us}"

#: node types that can carry an imported geometry
STRATIGRAPHIC_NODE_TYPES = frozenset({
    "US", "USN", "USV", "USVS", "USVA", "USM", "USR",
    "SF", "TSU", "VSF", "USD",
})


def _text(value):
    return "" if value is None else str(value).strip()


def compose_label(row, template):
    """The label of a US as the mapping composes it.

    Faithful copy of ``PyArchInitImporter._resolve_node_name``: the
    ``{column}`` placeholders come from the row, empties are omitted,
    runs of dots collapse, leading and trailing dots go; all empty →
    the bare value of ``us``.
    """
    if not template:
        return _text(row.get("us"))
    composed = re.sub(r"\{(\w+)\}", lambda m: _text(row.get(m.group(1))), template)
    composed = re.sub(r"\.{2,}", ".", composed).strip(".")
    return composed or _text(row.get("us"))


def parse_us_key(us_key):
    """``sito=…,area=…,us=…`` (the reader's row key) → dict."""
    out = {}
    for part in (us_key or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def pick_stratigraphic(candidates):
    """Prefer a node whose type can carry a geometry; else the first."""
    candidates = list(candidates)
    for n in candidates:
        if getattr(n, "node_type", "") in STRATIGRAPHIC_NODE_TYPES:
            return n
    return candidates[0] if candidates else None


def resolve_bare(graph, us_key):
    """The reader's historical resolution: match by the bare ``us`` value."""
    if graph is None:
        return None
    us_value = parse_us_key(us_key).get("us")
    if not us_value:
        return None
    return pick_stratigraphic(
        n for n in getattr(graph, "nodes", [])
        if getattr(n, "name", None) == us_value
    )


class RowIdentityResolver:
    """From a polygon's key to its graph node, using the row's identity.

    ``polygons`` are the dicts yielded by ``fetch_polygons`` /
    ``fetch_polygons_pg``, which carry ``node_uuid`` / ``settore`` /
    ``unita_tipo`` next to the key (issue #34). ``how`` records, per
    key, which step resolved it: uuid / label / bare / orphan.
    """

    def __init__(self, polygons, name_template=None):
        self.template = name_template or DEFAULT_NAME_TEMPLATE
        self._rows = {}
        for p in polygons:
            self._rows.setdefault(p["us_key"], p)
        self.how = {}

    def __call__(self, graph, us_key):
        if graph is None:
            return None
        nodes = list(getattr(graph, "nodes", []) or [])
        row = self._rows.get(us_key)
        if row is not None:
            uid = _text(row.get("node_uuid"))
            if uid:
                node = next((n for n in nodes
                             if _text(getattr(n, "node_id", None)) == uid), None)
                if node is not None:
                    self.how[us_key] = "uuid"
                    return node
            label = compose_label(row, self.template)
            node = pick_stratigraphic(n for n in nodes
                                      if getattr(n, "name", None) == label)
            if node is not None:
                self.how[us_key] = "label"
                return node
        node = resolve_bare(graph, us_key)
        self.how[us_key] = "bare" if node is not None else "orphan"
        return node

    def matched_by(self):
        """{'uuid': n, 'label': n, 'bare': n, 'orphan': n} over the keys seen."""
        counts = {"uuid": 0, "label": 0, "bare": 0, "orphan": 0}
        for how in self.how.values():
            counts[how] += 1
        return counts


def record_us_without_geometry(polygons, graph, report, resolve_us_node):
    """List the stratigraphic nodes no polygon resolved on.

    «Has a geometry» means «a polygon resolved on this node» — not
    «its name is one of the table's numbers» (issue #34).
    """
    if graph is None:
        return
    with_geom = set()
    for p in polygons:
        node = resolve_us_node(graph, p["us_key"])
        if node is not None:
            with_geom.add(id(node))
    for node in getattr(graph, "nodes", []):
        if getattr(node, "node_type", "") not in STRATIGRAPHIC_NODE_TYPES:
            continue
        name = getattr(node, "name", "")
        if not name or id(node) in with_geom:
            continue
        report["us_without_geometry"].append(name)
        attrs = getattr(graph, "attributes", None)
        if isinstance(attrs, dict):
            node_id = getattr(node, "node_id", None) or getattr(node, "id", None)
            if node_id is not None:
                attrs.setdefault(GRAPH_ATTR_AUX_US_NO_GEOM, []).append(node_id)
