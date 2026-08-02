"""C1 — typing the icon nodes of a pre-1.4 EM GraphML.

Pure XML logic, deliberately free of ``bpy`` so it can be unit-tested outside
Blender. The Blender operator (`graphml_converter.py`) is a thin shell over it.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

_GRAPHML_NS = "http://graphml.graphdrawing.org/xmlns"
_YWORKS_NS = "http://www.yworks.com/xml/graphml"

_G = "{%s}" % _GRAPHML_NS
_Y = "{%s}" % _YWORKS_NS

# ── C1: typing the icon nodes of a pre-1.4 graph ────────────────────────────
#
# Old EM graphs draw extractors, combiners and continuity nodes as `y:SVGNode`
# — an icon, no shape, all of them filled with yEd's default `#CCCCFF`. The
# importer recognises them ONLY by the label convention (`D.` = extractor,
# `C.` = combiner). An author who named an extractor after the unit it reads
# from — `SF04.2`, `USR2170.1` — drew a perfectly unambiguous extractor icon
# and still got an untyped node, along with every edge touching it.
#
# The type IS in the file: it is the SVG resource the node points at. What that
# resource MEANS is learned from the file's own usage — in a graph where 102
# nodes sharing one icon are all called `D.something`, that icon is the
# extractor icon, and the 18 stragglers sharing it are extractors too. This is
# reading the drawing, not guessing from names: the individual label is exactly
# what we refuse to trust.
#
# yEd numbers `y:Resource` by serialisation order, so a refid means nothing
# across files and the mapping is rebuilt for every conversion.
#
# The verdict is written as the explicit `_s3d_node_type:<Class>` marker in the
# node's description — the channel s3Dgraphy already uses for round-tripping,
# which takes precedence over every shape/label heuristic and is stripped from
# the description before it reaches any UI.

_S3D_NODE_TYPE_MARKER = "_s3d_node_type:"

#: Label prefix → node class, mirroring the importer's own convention
#: (`EM_extract_extractor_node` / `EM_extract_combiner_node` in
#: s3Dgraphy/importer/import_graphml.py). Longest prefix first when matching.
_LABEL_PREFIX_TO_CLASS = {
    "D.": "ExtractorNode",
    "C.": "CombinerNode",
}

#: A resource whose `sodipodi:docname` names it outright needs no vote.
_DOCNAME_TO_CLASS = {
    "continuity.svg": "ContinuityNode",
}

#: A refid is only assigned a meaning when its labelled users agree
#: overwhelmingly AND there are enough of them to be a convention rather than a
#: coincidence. Below either bar the resource stays unknown and its nodes are
#: left untyped — which is the correct outcome: the author is told, nothing is
#: invented.
_MIN_VOTES = 3
_MIN_AGREEMENT = 0.9


def _svg_nodes(root):
    """Yield ``(node_element, svg_element, refid, label)`` for every SVGNode."""
    for node in root.iter(f"{_G}node"):
        svg = node.find(f".//{_Y}SVGNode")
        if svg is None:
            continue
        content = svg.find(f".//{_Y}SVGContent")
        refid = content.attrib.get("refid") if content is not None else None
        if not refid:
            continue
        label_elem = svg.find(f".//{_Y}NodeLabel")
        label = (label_elem.text or "").strip() if label_elem is not None else ""
        yield node, svg, refid, label


def _class_for_label(label):
    """The node class the label convention claims, or None. Longest prefix
    first so a future ``D.x``/``Dx.`` pair cannot shadow each other."""
    for prefix in sorted(_LABEL_PREFIX_TO_CLASS, key=len, reverse=True):
        if label.startswith(prefix):
            return _LABEL_PREFIX_TO_CLASS[prefix]
    return None


def learn_svg_resource_classes(root):
    """Build ``{refid: (node class, how)}`` for this document.

    Two independent routes:

    * ``"docname"`` — the resource names itself
      (``sodipodi:docname="continuity.svg"``). The importer reads this signal
      too, so these nodes already resolve and need no help;
    * ``"vote"`` — the labelled nodes using the resource agree on a convention,
      by a wide margin and in sufficient number. This is the route the importer
      cannot take, and the only one worth writing a marker for.

    A refid that satisfies neither is simply absent from the result.
    """
    resources = {}
    for res in root.iter(f"{_Y}Resource"):
        rid = res.attrib.get("id")
        if rid:
            resources[rid] = res.text or ""

    learned = {}
    for rid, body in resources.items():
        for docname, cls in _DOCNAME_TO_CLASS.items():
            if f'docname="{docname}"' in body:
                learned[rid] = (cls, "docname")
                break

    votes = {}
    for _node, _svg, refid, label in _svg_nodes(root):
        cls = _class_for_label(label)
        if cls:
            votes.setdefault(refid, []).append(cls)

    for refid, cast in votes.items():
        if refid in learned:
            continue  # the resource named itself; a vote cannot override that
        if len(cast) < _MIN_VOTES:
            continue
        winner = max(set(cast), key=cast.count)
        if cast.count(winner) / len(cast) >= _MIN_AGREEMENT:
            learned[refid] = (winner, "vote")
    return learned


def _description_element(root, node):
    """The node's ``description`` data element, created if absent.

    The key id is read from the document's own ``<key>`` declarations — yEd
    files number them differently (``d5`` here, ``d4`` there) and hardcoding
    one would silently write into the wrong field.
    """
    key_id = None
    for key in root.findall(f"{_G}key"):
        if key.attrib.get("for") == "node" and \
                key.attrib.get("attr.name") == "description":
            key_id = key.attrib.get("id")
            break
    if key_id is None:
        return None
    for data in node.findall(f"{_G}data"):
        if data.attrib.get("key") == key_id:
            return data
    data = ET.SubElement(node, f"{_G}data", {"key": key_id})
    return data


def annotate_icon_node_types(root):
    """Write ``_s3d_node_type:<Class>`` on every SVGNode the label convention
    misses but the icon identifies.

    Returns ``(annotated, skipped_unknown_resource)``. Idempotent: a node that
    already carries a marker is left alone, so converting twice is a no-op.

    The edit is kept as small as the problem. A node is left alone when it
    already imports correctly — because its label follows the convention, or
    because its resource names itself and the importer reads that too. Only the
    genuine gap is written to; restating in 150 descriptions what the labels
    already say would just make the file noisier in yEd.

    Group nodes are never annotated: a box drawn with an icon realizer is still
    a container, and the importer types it from its palette colour. Declaring
    it a Combiner because its icon is the combiner icon would be a new error,
    not a fix.
    """
    learned = learn_svg_resource_classes(root)
    annotated = 0
    skipped = 0
    for node, _svg, refid, label in _svg_nodes(root):
        if _class_for_label(label):
            continue  # already recognisable — leave the description alone
        if node.find(f".//{_Y}ProxyAutoBoundsNode") is not None or \
                node.find(f"{_G}graph") is not None:
            continue  # a group, not a leaf node
        entry = learned.get(refid)
        if entry is None:
            skipped += 1
            continue
        cls, how = entry
        if how == "docname":
            continue  # the importer already recognises this resource itself
        data = _description_element(root, node)
        if data is None:
            skipped += 1
            continue
        existing = data.text or ""
        if _S3D_NODE_TYPE_MARKER in existing:
            continue  # already annotated
        marker = f"{_S3D_NODE_TYPE_MARKER}{cls}"
        data.text = f"{existing.strip()} {marker}".strip() if existing.strip() else marker
        annotated += 1
    return annotated, skipped
