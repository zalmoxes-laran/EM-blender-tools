"""
Enrich GraphML Operators for EM-blender-tools

Bakes EM Tables (paradata, stratigraphy) into an already-loaded GraphML file.
Creates rotating backups before overwriting.

Phase 1: Bake EM Paradata Table (em_paradata.xlsx) into loaded GraphML.
Phase 2 (future): Bake EM Stratigraphy Table into loaded GraphML.
"""

import bpy  # type: ignore
import os
import shutil


def rotate_backups(filepath, max_backups):
    """
    Create a rotating backup of a file before overwriting it.

    Backup naming: file.graphml.bak1 (newest) ... file.graphml.bakN (oldest)

    Args:
        filepath: Path to the file to back up
        max_backups: Maximum number of backups to keep (0 = no backup)

    Returns:
        str or None: Path to the newest backup (.bak1), or None if no backup was created
    """
    if max_backups <= 0:
        return None

    if not os.path.exists(filepath):
        return None

    # Rotate existing backups: bakN → delete, bak(N-1) → bakN, ..., bak1 → bak2
    for i in range(max_backups, 0, -1):
        bak_path = f"{filepath}.bak{i}"
        if i == max_backups:
            # Delete the oldest backup
            if os.path.exists(bak_path):
                try:
                    os.remove(bak_path)
                except OSError as e:
                    print(f"  Warning: Could not remove old backup {bak_path}: {e}")
        else:
            # Rename bak(i) → bak(i+1)
            next_bak = f"{filepath}.bak{i + 1}"
            if os.path.exists(bak_path):
                try:
                    os.rename(bak_path, next_bak)
                except OSError as e:
                    print(f"  Warning: Could not rotate backup {bak_path}: {e}")

    # Copy current file → .bak1
    bak1_path = f"{filepath}.bak1"
    try:
        shutil.copy2(filepath, bak1_path)
        print(f"  Backup created: {os.path.basename(bak1_path)}")
        return bak1_path
    except OSError as e:
        print(f"  Warning: Could not create backup: {e}")
        return None


class ENRICH_OT_bake_paradata(bpy.types.Operator):
    """Bake EM Paradata Table into the loaded GraphML file"""
    bl_idname = "enrich.bake_paradata"
    bl_label = "Bake Paradata into GraphML"
    bl_description = (
        "Enrich the loaded GraphML with deep provenance chains from an "
        "EM Paradata Table (em_paradata.xlsx). A backup is created automatically"
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        em_tools = context.scene.em_tools

        # ── Validate: active GraphML selected ──
        if em_tools.active_file_index < 0 or not em_tools.graphml_files:
            self.report({'ERROR'}, "No GraphML file selected")
            return {'CANCELLED'}

        graphml = em_tools.graphml_files[em_tools.active_file_index]

        # ── Validate: paradata file specified ──
        paradata_file = bpy.path.abspath(graphml.enrich_paradata_file)
        if not paradata_file or not paradata_file.strip():
            self.report({'ERROR'}, "No EM Paradata Table file specified")
            return {'CANCELLED'}

        if not os.path.exists(paradata_file):
            self.report({'ERROR'}, f"Paradata file not found: {paradata_file}")
            return {'CANCELLED'}

        # ── Validate: GraphML path exists ──
        graphml_path = bpy.path.abspath(graphml.graphml_path)
        if not graphml_path or not os.path.exists(graphml_path):
            self.report({'ERROR'}, f"GraphML file not found: {graphml_path}")
            return {'CANCELLED'}

        # ── Validate: graph is loaded in memory ──
        try:
            from s3dgraphy import get_graph
            graph = get_graph(graphml.name)
        except ImportError:
            self.report({'ERROR'}, "s3dgraphy library not available")
            return {'CANCELLED'}

        if graph is None:
            self.report({'ERROR'},
                f"Graph '{graphml.name}' not loaded in memory. "
                "Please reload the GraphML first (click the reload icon)."
            )
            return {'CANCELLED'}

        # Check graph has stratigraphic nodes (US, USVs, USVn, USD, SF, VSF, etc.)
        strat_types = {"US", "USVs", "USVn", "USD", "SF", "VSF", "TSU",
                       "serSU", "serUSVn", "serUSVs", "serUSD", "stratigraphic"}
        strat_nodes = [n for n in graph.nodes if n.node_type in strat_types]
        if not strat_nodes:
            self.report({'ERROR'},
                "Graph has no stratigraphic nodes. "
                "Load a GraphML with US/USV nodes before baking paradata."
            )
            return {'CANCELLED'}

        # ── Step 1: Backup ──
        print(f"\n{'='*60}")
        print(f"Bake EM Paradata Table into GraphML")
        print(f"{'='*60}")
        print(f"  GraphML: {os.path.basename(graphml_path)}")
        print(f"  Paradata: {os.path.basename(paradata_file)}")
        print(f"  Overwrite: {graphml.enrich_paradata_overwrite}")

        # Get backup count from addon preferences
        max_backups = 2  # default
        try:
            prefs = context.preferences.addons[__package__.rsplit('.', 1)[0]].preferences
            max_backups = prefs.graphml_backup_count
        except Exception:
            # If preferences not accessible, use default
            pass

        if max_backups > 0:
            print(f"\n  Creating backup (max {max_backups})...")
            backup_path = rotate_backups(graphml_path, max_backups)
            if backup_path:
                self.report({'INFO'}, f"Backup created: {os.path.basename(backup_path)}")
            else:
                self.report({'WARNING'}, "Could not create backup, proceeding anyway")
        else:
            print(f"\n  Backups disabled (graphml_backup_count=0)")

        # ── Step 2: Enrich with QualiaImporter ──
        nodes_before = len(graph.nodes)
        edges_before = len(graph.edges)

        try:
            from s3dgraphy.importer.qualia_importer import QualiaImporter
            qualia = QualiaImporter(
                filepath=paradata_file,
                existing_graph=graph,
                overwrite=graphml.enrich_paradata_overwrite
            )
            graph = qualia.parse()
        except Exception as e:
            self.report({'ERROR'}, f"Failed to import paradata: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        nodes_added = len(graph.nodes) - nodes_before
        edges_added = len(graph.edges) - edges_before

        print(f"\n  Paradata enrichment: +{nodes_added} nodes, +{edges_added} edges")

        # ── Step 3: Re-export GraphML ──
        try:
            from s3dgraphy.exporter.graphml import GraphMLExporter
            exporter = GraphMLExporter(graph)
            exporter.export(graphml_path)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export GraphML: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        print(f"  GraphML saved: {graphml_path}")

        # ── Step 4: Auto-reload Blender lists ──
        try:
            from ..populate_lists import (
                populate_blender_lists_from_graph,
                update_graph_statistics
            )
            populate_blender_lists_from_graph(context, graph)
            update_graph_statistics(context, graph, graphml)
            print(f"  Blender lists refreshed")
        except Exception as e:
            print(f"  Warning: Could not refresh Blender lists: {e}")
            self.report({'WARNING'},
                f"Paradata baked successfully but UI lists could not be refreshed. "
                f"Click the reload icon to refresh manually."
            )

        # ── Success ──
        print(f"\n{'='*60}")
        print(f"Bake complete: +{nodes_added} nodes, +{edges_added} edges")
        print(f"{'='*60}\n")

        self.report({'INFO'},
            f"Paradata baked: +{nodes_added} nodes, +{edges_added} edges "
            f"into {os.path.basename(graphml_path)}"
        )

        # Force UI redraw
        for area in context.screen.areas:
            area.tag_redraw()

        return {'FINISHED'}


def register():
    bpy.utils.register_class(ENRICH_OT_bake_paradata)


def unregister():
    bpy.utils.unregister_class(ENRICH_OT_bake_paradata)


if __name__ == "__main__":
    register()
