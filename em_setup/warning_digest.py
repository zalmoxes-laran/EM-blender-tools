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
#: ``(key, label, icon, matchers)``.
#:
#: ``key`` is the s3Dgraphy warning KIND
#: (``edges.connection_resolver.WARNING_KINDS``) wherever one exists, because a
#: warning that arrives as a record is filed by its kind — exactly, no guessing.
#:
#: ``matchers`` are the fallback for warnings that arrive as plain strings: the
#: free-form ones s3Dgraphy has always emitted (a deserialisation note, a header
#: complaint) and any older graph handed over without records. They are short,
#: stable fragments of the English message rather than whole sentences, so a
#: rewording upstream does not silently empty a family — it grows the "Other"
#: bucket instead, which is visible. Nothing is ever dropped either way.
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
        ("Using 'generic_connection' instead", "not allowed between",
         "is 'generic_connection'"),
    ),
    (
        "dangling_edge",
        "Connections with a missing endpoint",
        "UNLINKED",
        ("has a missing endpoint",),
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
    """One family plus the warnings that fell into it.

    ``messages`` is the list of sentences (what the panel draws). ``records``
    holds the ``{kind, node_id, message}`` record behind each one, aligned by
    index, or ``None`` where the warning arrived as a bare string. That is what
    a future "select the offending node" button reads — and the ``None`` says
    truthfully that for this line there is nothing to select.
    """

    __slots__ = ("key", "label", "icon", "messages", "records")

    def __init__(self, key, label, icon, messages, records=None):
        self.key = key
        self.label = label
        self.icon = icon
        self.messages = messages
        self.records = records if records is not None else []

    @property
    def count(self):
        return len(self.messages)

    def node_ids(self):
        """The graph elements this family points at, in order, skipping the
        warnings that point at nothing."""
        return [r["node_id"] for r in self.records
                if isinstance(r, dict) and r.get("node_id")]

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<WarningGroup {self.key} n={self.count}>"


def _classify(message, kind):
    """(key, label, icon) for a warning. An explicit ``kind`` wins outright."""
    for fam_key, fam_label, fam_icon, matchers in WARNING_FAMILIES:
        if kind is not None:
            if kind == fam_key:
                return fam_key, fam_label, fam_icon
            continue
        if any(m in message for m in matchers):
            return fam_key, fam_label, fam_icon
    return OTHER_FAMILY


def digest_warnings(warnings):
    """Group ``warnings`` into :class:`WarningGroup`s, largest family first.

    Accepts both shapes, mixed freely:

    * a ``{kind, node_id, message}`` record — filed by its **kind**, exactly;
    * a plain string — filed by matching the message, the fallback for the
      free-form warnings and for a graph that predates the records.

    Empty and whitespace-only entries are dropped; everything else is kept
    exactly once, in its original order within its family. The total across the
    returned groups always equals the number of non-empty inputs — the digest
    summarises, it never filters.
    """
    buckets = {}
    order = []
    for raw in warnings or []:
        if isinstance(raw, dict):
            record = raw
            message = (record.get("message") or "").strip()
            kind = record.get("kind") or None
        else:
            record = None
            message = (raw or "").strip()
            kind = None
        if not message:
            continue
        key, label, icon = _classify(message, kind)
        if key not in buckets:
            buckets[key] = WarningGroup(key, label, icon, [], [])
            order.append(key)
        buckets[key].messages.append(message)
        buckets[key].records.append(record)

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
