"""The panel's lists FOLLOW the room · an incoming field lands on its row.

The EM lists (units, epochs, documents, properties, extractors, combiners) are a
projection of the graph. A STRUCTURAL op rebuilds them (`_repopulate`); a FIELD
that arrives (`update_field`: someone renamed US3 in EMStudio) is written on the
node and then here, on the row that shows that node — without a rebuild, so the
selection and the scroll stay where the person left them.

Measured on 12 Oct 2026 (prova 5 del tavolo): the rename reached the graph and
NOT the panel. The row was searched by `node.name` — already the NEW one after
`set_field` — or by `node_id`, a field the populated rows leave empty (the list
of units keeps the id in `id_node`, the epochs in `id`). So the row was never
found, and when it was, only `description` was copied.

Here the row is found by its node id FIRST (each list with its own key), and by
the name it had BEFORE the write only on rows that carry no id; every field the
populate functions put on a row (`populate_lists.py`) is set again from the
node. A rename also travels to the rows that show the old name of ANOTHER node:
a unit's epoch, a unit's container, the reused table.

Plain Python, no `bpy`: the rows are anything with attributes, so the rule is
tested without Blender. A field is written only when it differs — a row's
`description` has an update callback that emits to the room, and a value that
is already there must not travel back (it also guards itself, twice is fine).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


def _clean(value) -> str:
    """`functions.clean_value_for_ui`, without the import of `bpy` it drags."""
    if value is None:
        return ""
    return " ".join(str(value).replace("\n", " ").replace("\r", " ").split())


def _rgb(hex_color: str) -> Tuple[float, float, float]:
    """`functions.hex_to_rgb` (gamma 2.2), for the same reason."""
    value = (hex_color or "#FFFFFF").lstrip("#")
    if len(value) != 6:
        value = "FFFFFF"
    return tuple(pow(int(value[i:i + 2], 16) / 255, 2.2) for i in (0, 2, 4))


def _url_fields(raw) -> Dict[str, Any]:
    url = _clean(raw or "")
    return {"url": url, "icon_url": "CHECKBOX_HLT" if url else "CHECKBOX_DEHLT"}


def _unit(node) -> Dict[str, Any]:
    return {"name": node.name, "description": node.description}


def _document(node) -> Dict[str, Any]:
    return {"name": node.name, "description": node.description,
            **_url_fields(getattr(node, "url", ""))}


def _property(node) -> Dict[str, Any]:
    attrs = getattr(node, "attributes", None) or {}
    return {"name": attrs.get("original_name") or node.name,
            "description": node.description,
            **_url_fields(getattr(node, "value", ""))}


def _extractor(node) -> Dict[str, Any]:
    return {"name": node.name, "description": node.description,
            **_url_fields(getattr(node, "source", ""))}


def _combiner(node) -> Dict[str, Any]:
    sources = getattr(node, "sources", None) or []
    return {"name": node.name, "description": node.description,
            **_url_fields(sources[0] if sources else "")}


def _epoch(node) -> Dict[str, Any]:
    start = getattr(node, "start_time", None)
    end = getattr(node, "end_time", None)
    color = getattr(node, "color", None) or "#FFFFFF"
    return {"name": node.name, "description": node.description or "",
            "start_time": start if start is not None else 0.0,
            "end_time": end if end is not None else 0.0,
            "epoch_color": color, "epoch_RGB_color": _rgb(color)}


#: the lists that show nodes: (label, how to reach it from `scene.em_tools`,
#: the row's attribute holding the node id, the fields the row shows). The
#: virtual paradata lists (`em_v_*`) are not here: they are rebuilt from the
#: graph each time a unit is selected, so they never hold a stale name.
LISTS: Tuple[Tuple[str, Callable[[Any], Any], str, Callable[[Any], Dict[str, Any]]], ...] = (
    ("units", lambda t: t.stratigraphy.units, "id_node", _unit),
    ("epochs", lambda t: t.epochs.list, "id", _epoch),
    ("documents", lambda t: t.em_sources_list, "id_node", _document),
    ("properties", lambda t: t.em_properties_list, "id_node", _property),
    ("extractors", lambda t: t.em_extractors_list, "id_node", _extractor),
    ("combiners", lambda t: t.em_combiners_list, "id_node", _combiner),
)


def find_row(rows: Iterable, key: str, node_id: Optional[str],
             old_name: Optional[str]):
    """The row of a node: by its id first; by the name it had BEFORE the
    write only among rows that carry no id (a row with another node's id is
    another node, whatever its name)."""
    rows = list(rows)
    if node_id:
        for row in rows:
            if getattr(row, key, "") == node_id:
                return row
    if old_name:
        for row in rows:
            if not getattr(row, key, "") and getattr(row, "name", None) == old_name:
                return row
    return None


def _same(a, b) -> bool:
    if not isinstance(a, str) and hasattr(a, "__len__"):  # a colour: a bpy array
        try:
            return len(a) == len(b) and all(abs(x - y) < 1e-6 for x, y in zip(a, b))
        except TypeError:
            return False
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-9
        except (TypeError, ValueError):
            return False
    return a == b


def _write(row, fields: Dict[str, Any], label: str, changed: List[str]) -> None:
    # `name` first: the description callback finds its node BY NAME, and with
    # the new name in place it sees the value already there and stays silent
    for field in sorted(fields, key=lambda f: f != "name"):
        value = fields[field]
        if value is None or not hasattr(row, field):
            continue
        if _same(getattr(row, field), value):
            continue
        try:
            setattr(row, field, value)
        except (AttributeError, TypeError, ValueError):
            continue
        changed.append(f"{label}.{field}")


def _rename_references(em_tools, node, old_name: str, changed: List[str]) -> None:
    """The rows that show this node's name while being about ANOTHER node."""
    new = node.name
    nid = getattr(node, "node_id", None)
    kind = getattr(node, "node_type", "")
    try:
        units = list(em_tools.stratigraphy.units)
    except AttributeError:
        units = []
    for row in units:
        if kind == "EpochNode" and getattr(row, "epoch", None) == old_name:
            row.epoch = new
            changed.append("units.epoch")
        if nid and getattr(row, "parent_node_id", "") == nid \
                and getattr(row, "contained_in_name", None) != new:
            row.contained_in_name = new
            changed.append("units.contained_in_name")
    try:
        reused = list(em_tools.stratigraphy.reused)
    except AttributeError:
        reused = []
    for row in reused:
        attr = "epoch" if kind == "EpochNode" else "em_element"
        if getattr(row, attr, None) == old_name:
            setattr(row, attr, new)
            changed.append(f"reused.{attr}")
    if kind == "EpochNode":
        try:
            docs = list(em_tools.em_sources_list)
        except AttributeError:
            docs = []
        for row in docs:
            if getattr(row, "epoch_name", None) == old_name:
                row.epoch_name = new
                changed.append("documents.epoch_name")


def mirror(em_tools, node, old_name: Optional[str] = None) -> List[str]:
    """Write `node`'s fields on the row(s) that show it. → what changed, as
    `list.field` (empty: no row shows this node, or it already said it)."""
    if em_tools is None or node is None:
        return []
    nid = getattr(node, "node_id", None)
    before = old_name if old_name is not None else node.name
    changed: List[str] = []
    for label, reach, key, fields in LISTS:
        try:
            rows = reach(em_tools)
        except AttributeError:
            continue
        row = find_row(rows, key, nid, before)
        if row is None:
            continue
        try:
            values = fields(node)
        except Exception:  # noqa: BLE001 — a node of an unexpected shape: no row is worth a crash
            continue
        _write(row, values, label, changed)
    if before and before != node.name:
        _rename_references(em_tools, node, before, changed)
    return changed
