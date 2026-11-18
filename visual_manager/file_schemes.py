"""The colour schemes INSIDE an em.json — MICRO-T-COLORI-NEL-FILE (E.D., 18 Nov 2026).

An em.json may carry its colour schemes in a section of its own, apart from the
graphs (em.json 1.2 ED §2.8, ``s3dgraphy.presentation``)::

    "presentation": {
      "colour_schemes": {"<name>": <a .emc document>},
      "active_colour_scheme": {"<graph id>": "<name>"}
    }

A scheme IS a .emc (``utils.save_color_scheme`` / ``load_color_scheme``):
``metadata.property_name`` and ``color_mapping`` (value → linear floats, as
``item.color`` takes them), with the two special values EM Tools already
writes. ``metadata.value_codes`` maps a label to the code (URI) of its term: a
value carrying that code takes the entry's colour whatever its label says.

Opening an em.json, EM Tools lists the file's schemes and applies the one the
active graph uses (``import_operators/importer_emjson.py``); the .emc files keep
working as before. This module reads the section without Blender — the
operator and the panel are in ``operators.py`` / ``ui.py``. It does not lean on
the bundled s3dgraphy: a section written by any tool is read the same.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Tuple

PRESENTATION_KEY = "presentation"
SCHEMES_KEY = "colour_schemes"
ACTIVE_KEY = "active_colour_scheme"
VALUE_CODES_KEY = "value_codes"
#: EM Tools' grey (``utils.DEFAULT_COLOR``): a value the scheme does not colour
DEFAULT_COLOR = (0.5, 0.5, 0.5, 1.0)


def _scheme_problem(doc: Any) -> Optional[str]:
    if not isinstance(doc, dict):
        return "not an object"
    meta, mapping = doc.get("metadata"), doc.get("color_mapping")
    if not isinstance(meta, dict) or not isinstance(meta.get("property_name"), str) \
            or not isinstance(mapping, dict):
        return "metadata.property_name and color_mapping are needed"
    for v, c in mapping.items():
        if not isinstance(c, (list, tuple)) or len(c) < 3 or not all(
                isinstance(x, (int, float)) and not isinstance(x, bool) for x in c):
            return f"not a colour for {v!r}"
    codes = meta.get(VALUE_CODES_KEY)
    if codes is not None and not (isinstance(codes, dict)
                                  and all(isinstance(x, str) for x in codes.values())):
        return f"metadata.{VALUE_CODES_KEY} is not a map of texts"
    return None


def read_section(doc: Any) -> Tuple[Dict[str, Any], List[str]]:
    """``({"schemes": {name: .emc}, "active": {graph id: name}}, warnings)``.
    A file without the section: no scheme, no warning."""
    out: Dict[str, Any] = {"schemes": {}, "active": {}}
    warnings: List[str] = []
    raw = doc.get(PRESENTATION_KEY) if isinstance(doc, dict) else None
    if raw is None:
        return out, warnings
    if not isinstance(raw, dict):
        return out, [f"{PRESENTATION_KEY}: not an object; ignored"]
    schemes = raw.get(SCHEMES_KEY) or {}
    for name, sch in (schemes.items() if isinstance(schemes, dict) else []):
        why = _scheme_problem(sch)
        if why:
            warnings.append(f"colour scheme {name!r} not readable ({why}); left out")
            continue
        out["schemes"][str(name)] = sch
    active = raw.get(ACTIVE_KEY) or {}
    for gid, name in (active.items() if isinstance(active, dict) else []):
        if name in out["schemes"]:
            out["active"][str(gid)] = name
        else:
            warnings.append(f"graph {gid!r}: active colour scheme {name!r} is not in the file; ignored")
    return out, warnings


def read_file(path: str) -> Tuple[Dict[str, Any], List[str]]:
    """The section of the em.json at ``path`` (an unreadable file: none, said)."""
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        return {"schemes": {}, "active": {}}, [f"colour schemes of the file not read: {exc}"]
    return read_section(doc)


def scheme_list(section: Mapping[str, Any], graph_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """The schemes as the panel lists them: name, property, number of
    colours, and whether ``graph_id`` uses it."""
    used = (section.get("active") or {}).get(graph_id) if graph_id else None
    return [{"name": n, "property": s["metadata"]["property_name"],
             "values": len(s["color_mapping"]), "active": n == used}
            for n, s in sorted((section.get("schemes") or {}).items())]


def active_for(section: Mapping[str, Any], graph_id: Optional[str]) -> Optional[str]:
    if not graph_id:
        return None
    name = (section.get("active") or {}).get(graph_id)
    return name if name in (section.get("schemes") or {}) else None


def _rgba(c) -> Tuple[float, float, float, float]:
    c = [float(x) for x in c]
    return (c[0], c[1], c[2], c[3] if len(c) > 3 else 1.0)


def rows_for(scheme: Mapping[str, Any], values: Mapping[str, Optional[str]]
             ) -> List[Tuple[str, Tuple[float, float, float, float]]]:
    """The rows of ``scene.property_values`` for a scheme on a graph:
    ``values`` are the labels found (``{label: code of its term or None}``,
    the special values among them). Each found label gets the colour of the
    scheme's entry with its CODE when it has one the scheme knows, else of the
    entry with its text, else EM Tools' grey; then the scheme's other entries,
    as «Load Schema» lists them."""
    mapping = scheme["color_mapping"]
    codes = (scheme.get("metadata") or {}).get(VALUE_CODES_KEY) or {}
    by_code = {code: mapping[label] for label, code in sorted(codes.items()) if label in mapping}
    out: List[Tuple[str, Tuple[float, float, float, float]]] = []
    seen = set()
    for label in sorted(values):
        code = values[label]
        if code and code in by_code:
            out.append((label, _rgba(by_code[code])))
        elif label in mapping:
            out.append((label, _rgba(mapping[label])))
        else:
            out.append((label, DEFAULT_COLOR))
        seen.add(label)
    for label in mapping:
        if label not in seen:
            out.append((label, _rgba(mapping[label])))
    return out


def value_code_of(_node) -> Optional[str]:
    """The code of a property node's value. WHERE a node keeps it is MICRO-U's
    (vocabularies): until then a value has none and the schemes colour by
    text — this is the one seam."""
    return None
