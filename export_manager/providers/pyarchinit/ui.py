# export_manager/providers/pyarchinit/ui.py
"""Draw function for the 'PyArchInit DB' section of the Export panel (#27)."""


def poll(context):
    return True


def draw(box, context):
    em_tools = context.scene.em_tools
    export_vars = context.window_manager.export_vars

    # The export reuses the connection configured in the 3D GIS import
    # panel (Sub-2) — show which target it will write to.
    conn_mode = getattr(em_tools, "pyarchinit_connection_mode", "sqlite")
    info = box.row()
    if conn_mode == "postgres":
        host = (getattr(em_tools, "pyarchinit_pg_host", "") or "").strip()
        dbname = (getattr(em_tools, "pyarchinit_pg_dbname", "") or "").strip()
        target = f"PostgreSQL: {host}/{dbname}" if (host and dbname) else "PostgreSQL (not configured)"
    else:
        path = getattr(em_tools, "pyarchinit_db_path", "")
        target = f"SQLite: {path}" if path else "SQLite (no file selected)"
    info.label(text=target, icon='EXPORT')

    box.label(text="Connection is set in the 3D GIS Import panel.", icon='INFO')

    box.prop(export_vars, "pyarchinit_export_sito", text="Site")
    box.prop(export_vars, "pyarchinit_export_create_epochs")

    col = box.column(align=True)
    preview = col.row()
    op = preview.operator("export.pyarchinit_db",
                          text="Preview (dry run)", icon='VIEWZOOM')
    op.dry_run = True

    write = col.row()
    write.scale_y = 1.3
    op = write.operator("export.pyarchinit_db",
                        text="Export to PyArchInit DB", icon='EXPORT')
    op.dry_run = False
