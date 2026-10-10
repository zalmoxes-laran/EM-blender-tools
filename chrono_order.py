"""The order of the units, from the chronology — never from the drawing.

``y_pos`` is a fossil of the GraphML (E.D., 10 Oct 2026): the vertical
coordinate of a node in yEd, which the GraphML importer reads only to rebuild
the chronology from the drawing. An em.json does not carry it, so an order
that read it would put every unit at 0.0 the moment the graph came from an
em.json instead of a GraphML.

The order here reads only what both formats carry:

1. the chronology s3dgraphy computes (``Graph.chronology()``: the written
   dates, the epochs, the propagation along the stratigraphic relations) —
   most recent first, undated units last;
2. at equal dates, the stratigraphic order — what lies above comes first
   (the longest chain of more recent units over it, along ``is_after`` /
   ``cuts`` / ``overlies`` / ``fills`` and their inverses, as s3dgraphy's
   cycle check reads them);
3. at equal position too, the name, so the order is stable.

No ``bpy``: the module is measured by ``tests/test_chrono_order.py``.
"""

from typing import Dict, Iterable, List


def _depth_from_top(graph) -> Dict[str, int]:
    """``{node_id: n}`` — the length of the longest chain of more recent
    units above the node; 0 for a unit nothing lies over.

    Iterative and tolerant of the cycles a real graph sometimes has: a node
    met again while still on the walk is not followed.
    """
    from s3dgraphy.diagnostics import _build_more_recent_graph

    above = _build_more_recent_graph(graph)
    depth: Dict[str, int] = {}
    for root in above:
        if root in depth:
            continue
        on_walk = {root}
        stack = [(root, iter(above.get(root, ())))]
        best = {root: 0}
        while stack:
            nid, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                stack.pop()
                on_walk.discard(nid)
                depth[nid] = best[nid]
                if stack:
                    parent = stack[-1][0]
                    best[parent] = max(best[parent], depth[nid] + 1)
                continue
            if nxt in depth:
                best[nid] = max(best[nid], depth[nxt] + 1)
            elif nxt not in on_walk:
                on_walk.add(nxt)
                best[nxt] = 0
                stack.append((nxt, iter(above.get(nxt, ()))))
    return depth


def chronological_order(graph, nodes: Iterable) -> List:
    """``nodes`` sorted most recent first, by the rules in the module doc."""
    chron = graph.chronology()
    depth = _depth_from_top(graph)

    def key(node):
        entry = chron.get(node.node_id) or {}
        start, end = entry.get("start"), entry.get("end")
        return (start is None, -(start or 0.0),
                end is None, -(end or 0.0),
                depth.get(node.node_id, 0),
                node.name or "", node.node_id)

    return sorted(nodes, key=key)
