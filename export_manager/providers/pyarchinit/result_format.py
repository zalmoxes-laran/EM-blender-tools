"""Format a s3dgraphy.sync ``IngestResult`` into display lines.

Blender-free so the formatter can be unit-tested with a duck-typed
result object (issue #27, Sub-3).
"""


def is_node_uuid_error(message):
    """True if ``message`` is GraphIngestor's missing-node_uuid error."""
    return bool(message) and "node_uuid" in message


def node_uuid_help(migration_failed=None):
    """User-facing guidance for the missing-node_uuid case.

    ``migration_failed`` (optional str) appends the reason EMTools could
    not apply the migration automatically.
    """
    msg = (
        "This PyArchInit database isn't ready for reverse-export yet.\n"
        "\n"
        "The 'node_uuid' columns are missing. They are normally added by "
        "PyArchInit (it owns the database schema), on us_table, "
        "inventario_materiali_table and periodizzazione_table.\n"
        "\n"
        "Update the database from PyArchInit and try again."
    )
    if migration_failed:
        msg += (
            "\n\nEMTools tried to add them automatically but could not: "
            f"{migration_failed}"
        )
    return msg


def format_ingest_result(result, target_label, dry_run):
    """Return a list of human-readable summary lines for ``result``.

    ``result`` is a s3dgraphy.sync.IngestResult (or anything exposing the
    same attributes). ``target_label`` is the credential-stripped DB
    spec. ``dry_run`` toggles the heading between a preview and a real
    write.
    """
    head = ("DRY-RUN — nothing was written"
            if dry_run else "Export complete — changes written")
    lines = [
        head,
        f"Target:    {target_label}",
        f"Applied:   {getattr(result, 'applied', 0)}",
        f"Inserted:  {getattr(result, 'inserted', 0)}",
        f"Updated:   {getattr(result, 'updated', 0)}",
        f"Skipped:   {getattr(result, 'skipped', 0)}",
        f"Epochs +:  {getattr(result, 'epochs_created', 0)}",
    ]

    conflicts = tuple(getattr(result, "conflicts", ()) or ())
    if conflicts:
        lines.append(f"Conflicts: {len(conflicts)}")
        for c in conflicts[:5]:
            lines.append(
                f"  - {getattr(c, 'field', '?')} "
                f"@ {getattr(c, 'node_uuid', '?')}: "
                f"{getattr(c, 'db_value', '?')} -> {getattr(c, 'graph_value', '?')}"
            )
        if len(conflicts) > 5:
            lines.append(f"  … and {len(conflicts) - 5} more")

    errors = tuple(getattr(result, "errors", ()) or ())
    if errors:
        lines.append(f"Errors:    {len(errors)}")
        for e in errors[:5]:
            lines.append(f"  - {e}")
        if len(errors) > 5:
            lines.append(f"  … and {len(errors) - 5} more")

    return lines
