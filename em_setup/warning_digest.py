"""S6 — turn a flat list of importer warnings into something an author can act on.

``graph.warnings`` is emitted one line per node, per group, per edge. On a real
dataset that is not a list, it is a wall: SarmiForum produces ~96 lines, Aiano
102, and the same three problems repeat down the whole column. Nobody reads
that, so nobody fixes the graph — which defeats the point of having made the
warnings meaningful in the first place (the connection-resolution arc).

The aggregation belongs **here, in the UI layer**, not in the core: the core's
job is to say exactly what went wrong with each element, once per element. What
changes between a console dump and a panel is only the presentation.

This module is deliberately free of ``bpy`` so it can be unit-tested outside
Blender.
"""

from __future__ import annotations

#: Warning families, in the order they are shown. Each entry is
#: ``(key, label, icon, matchers)``; a warning joins the FIRST family whose
#: matcher substring occurs in it, so the order below is also the priority.
#:
#: The matchers are substrings of the messages s3Dgraphy actually emits. They
#: are intentionally short and stable fragments ("has no recognised EM type"),
#: not whole sentences: the wording around them may be reworded without
#: silently emptying a family. A family that stops matching shows up as a
#: growing "Other" bucket rather than as lost information — nothing is ever
#: dropped.
WARNING_FAMILIES = (
    (
        "untyped_node",
        "Nodes with no recognised EM type",
        "OUTLINER_OB_POINTCLOUD",
        ("has no recognised EM type",),
    ),
    (
        "unclassified_group",
        "Groups with no EM role",
        "OUTLINER_COLLECTION",
        ("has no EM role",),
    ),
    (
        "degraded_edge",
        "Connections degraded to generic_connection",
        "DRIVER",
        ("Using 'generic_connection' instead", "not allowed between"),
    ),
    (
        "unknown_node_type",
        "Node types this version does not know",
        "QUESTION",
        ("unknown node type", "Unknown node type"),
    ),
    (
        "schema",
        "Document version",
        "FILE_TEXT",
        ("schema_version", "format version"),
    ),
    (
        "header",
        "Graph header",
        "INFO",
        ("site ID", "placeholder dates"),
    ),
)

#: Where everything that matched no family goes. Never silently discarded.
OTHER_FAMILY = ("other", "Other", "DOT")


class WarningGroup:
    """One family plus the messages that fell into it."""

    __slots__ = ("key", "label", "icon", "messages")

    def __init__(self, key, label, icon, messages):
        self.key = key
        self.label = label
        self.icon = icon
        self.messages = messages

    @property
    def count(self):
        return len(self.messages)

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<WarningGroup {self.key} n={self.count}>"


def digest_warnings(warnings):
    """Group ``warnings`` into :class:`WarningGroup`s, largest family first.

    Empty and whitespace-only lines are dropped; everything else is kept
    exactly once, in its original order within its family. The total across the
    returned groups always equals the number of non-empty input lines — the
    digest summarises, it never filters.
    """
    buckets = {}
    order = []
    for raw in warnings or []:
        message = (raw or "").strip()
        if not message:
            continue
        key, label, icon = OTHER_FAMILY[0], OTHER_FAMILY[1], OTHER_FAMILY[2]
        for fam_key, fam_label, fam_icon, matchers in WARNING_FAMILIES:
            if any(m in message for m in matchers):
                key, label, icon = fam_key, fam_label, fam_icon
                break
        if key not in buckets:
            buckets[key] = WarningGroup(key, label, icon, [])
            order.append(key)
        buckets[key].messages.append(message)

    groups = [buckets[k] for k in order]
    # Biggest problem first; ties keep the order the families were declared in,
    # so the panel does not reshuffle between two imports of the same file.
    groups.sort(key=lambda g: -g.count)
    return groups


def summarise(groups):
    """One-line summary for the panel header, e.g.
    ``"18 untyped nodes · 57 degraded connections"``. Empty string when there
    is nothing to say."""
    if not groups:
        return ""
    return " · ".join(f"{g.count} {g.label.lower()}" for g in groups[:2])
