"""'Export to PyArchInit DB' operator (issue #27, Sub-3).

Writes the active s3dgraphy graph back into a PyArchInit database
(SQLite or PostgreSQL) via ``s3dgraphy.sync.GraphIngestor``. A dry-run
mode previews the planned inserts / updates / conflicts without
touching the database.

Connection settings are shared with the 3D GIS import panel (Sub-2):
the same ``em_tools.pyarchinit_*`` fields and keychain are reused, so a
round-trip reads and writes the same database with one configuration.
"""

import os

import bpy  # type: ignore
from bpy.props import BoolProperty  # type: ignore
from bpy.types import Operator  # type: ignore


class EXPORT_OT_pyarchinit_db(Operator):
    """Write the active EM graph back into a PyArchInit database.

    Toggle ``dry_run`` to preview the plan (no writes) versus applying
    it. Uses the connection configured in the 3D GIS import panel.
    """
    bl_idname = "export.pyarchinit_db"
    bl_label = "Export to PyArchInit DB"
    bl_options = {"REGISTER"}

    dry_run: BoolProperty(
        name="Dry run",
        description="Preview the planned changes without writing to the database",
        default=True,
        options={'SKIP_SAVE'},
    )  # type: ignore

    def execute(self, context):
        em_tools = context.scene.em_tools
        export_vars = context.window_manager.export_vars

        # 1. Active graph -------------------------------------------------
        if not (em_tools.active_file_index >= 0 and len(em_tools.graphml_files) > 0):
            self.report({'ERROR'}, "No active graph to export.")
            return {'CANCELLED'}
        from s3dgraphy import get_graph
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graphml.name)
        if graph is None:
            self.report({'ERROR'},
                        f"Active graph '{graphml.name}' is not loaded.")
            return {'CANCELLED'}

        # 2. Site name (required by GraphIngestor) ------------------------
        sito = (getattr(export_vars, "pyarchinit_export_sito", "") or "").strip()
        if not sito:
            self.report({'ERROR'}, "Set the 'Site' name before exporting.")
            return {'CANCELLED'}

        # 3. Connection spec ---------------------------------------------
        from ....import_operators.pyarchinit_connection import resolve_db_spec
        from ....import_operators.pyarchinit_db_reader import (
            is_postgres_spec, redact_url_from_message, redacted_db_spec,
        )
        db_spec, err = resolve_db_spec(em_tools)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        # GraphIngestor resolves str specs through SQLAlchemy, so a SQLite
        # *path* must become a sqlite:/// URL; a PG URL passes through.
        if is_postgres_spec(db_spec):
            sa_spec = db_spec
        else:
            sa_spec = "sqlite:///" + os.path.abspath(bpy.path.abspath(db_spec))

        # 4. Ingestor -----------------------------------------------------
        try:
            from s3dgraphy.sync import GraphIngestor
        except Exception as e:
            self.report(
                {'ERROR'},
                f"s3dgraphy.sync is unavailable ({e}). The reverse-export "
                "needs SQLAlchemy bundled — re-run './em.sh setup'.",
            )
            return {'CANCELLED'}

        create_epochs = bool(
            getattr(export_vars, "pyarchinit_export_create_epochs", False))

        from .result_format import (
            format_ingest_result, is_node_uuid_error, node_uuid_help,
        )
        from ....functions import show_popup_message

        def _ingest():
            return GraphIngestor().populate_list(
                graph, sa_spec, sito,
                dry_run=self.dry_run,
                create_missing_epochs=create_epochs,
            )

        migration_note = None
        try:
            result = _ingest()
        except Exception as e:
            if not is_node_uuid_error(str(e)):
                # Defensive: an upstream exception message may (today or
                # in a future SQLAlchemy/psycopg2/s3dgraphy.sync change)
                # embed the connection URL with creds. Strip
                # ``user:password@`` from any postgres URL substring
                # before surfacing the message to the user popup.
                self.report({'ERROR'},
                            f"Export failed: {redact_url_from_message(e)}")
                return {'CANCELLED'}

            # node_uuid columns missing. NEVER mutate the schema during a
            # dry-run preview — just explain. On a real export, try to add
            # them (PyArchInit's job, attempted best-effort) and retry;
            # fall back to the message if it can't.
            if self.dry_run:
                show_popup_message(
                    context, title="PyArchInit DB needs updating",
                    message=node_uuid_help(), icon='ERROR')
                self.report(
                    {'ERROR'},
                    "PyArchInit DB missing node_uuid — update it from PyArchInit.")
                return {'CANCELLED'}

            from ....import_operators.pyarchinit_migrate import (
                apply_node_uuid_migration,
            )
            try:
                counts = apply_node_uuid_migration(sa_spec)
            except Exception as me:
                show_popup_message(
                    context, title="PyArchInit DB needs updating",
                    message=node_uuid_help(str(me)), icon='ERROR')
                self.report(
                    {'ERROR'},
                    "Could not add node_uuid columns — update the DB from PyArchInit.")
                return {'CANCELLED'}

            migration_note = ("Added node_uuid columns: " +
                              ", ".join(f"{t} (+{n})" for t, n in counts.items()))
            try:
                result = _ingest()
            except Exception as e2:
                self.report(
                    {'ERROR'},
                    f"Export failed after migration: "
                    f"{redact_url_from_message(e2)}")
                return {'CANCELLED'}

        # 5. Summary ------------------------------------------------------
        lines = format_ingest_result(result, redacted_db_spec(db_spec), self.dry_run)
        if migration_note:
            lines.insert(1, migration_note)
        show_popup_message(
            context,
            title=("PyArchInit DB — Dry run" if self.dry_run
                   else "PyArchInit DB — Export"),
            message="\n".join(lines),
            icon='INFO',
        )
        self.report({'INFO'}, lines[0])
        return {'FINISHED'}


classes = (
    EXPORT_OT_pyarchinit_db,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
