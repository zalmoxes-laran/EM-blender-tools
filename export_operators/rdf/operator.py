# export_operators/rdf/operator.py
"""EXPORT_OT_rdf — Export EM graph(s) to RDF formats.

Reads scene.rdf_* properties (from export_manager.providers.rdf.properties)
and delegates to s3dgraphy.exporter.RDFExporter (which itself uses rdflib).

Behavior:
  * If scene.rdf_export_all_graphs is True: exports every graph marked as
    'is_publishable' in em_tools.graphml_files into a single multi-named-graph
    file (use TriG or N-Quads formats for full multi-graph fidelity).
  * Otherwise: exports only the currently active graph.

  * If scene.rdf_parent_hdt_iri is set, every exported EMGraph gets a
    hdto:HP33i_is_proposition_set_of triple pointing to that HDT IRI.

  * If rdflib is not installed in Blender's Python environment, the operator
    fails gracefully and instructs the user to install it.
"""

import os

import bpy
from bpy.types import Operator


def _try_import_exporter():
    """Import s3dgraphy.exporter.RDFExporter or return (None, error_message)."""
    try:
        from s3dgraphy.exporter import RDFExporter
        return RDFExporter, None
    except ImportError as e:
        msg = (
            "RDF export requires rdflib. Install in Blender's Python env:\n"
            "  cd <Blender_install>/<version>/python/bin/\n"
            "  ./python3 -m pip install rdflib\n"
            f"Original error: {e}"
        )
        return None, msg


class EXPORT_OT_rdf(Operator):
    """Export the current EM graph (or all publishable graphs) to RDF (Turtle / N-Triples / JSON-LD / TriG / RDF-XML)."""

    bl_idname = "export.rdf"
    bl_label = "Export EM Graph to RDF"
    bl_description = (
        "Export the current EM graph(s) to RDF using the CIDOC-CRM + HDT-O + "
        "Extended Matrix ontology. Output can be loaded into any SPARQL-1.1 "
        "triplestore (Oxigraph, GraphDB, Virtuoso)."
    )
    bl_options = {'REGISTER'}

    # ── Validation ──────────────────────────────────────────────────────────

    @classmethod
    def poll(cls, context):
        return (
            hasattr(context.scene, 'em_tools')
            and hasattr(context.scene, 'rdf_export_path')
        )

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _resolve_graph_ids(self, context):
        """Return the list of graph IDs to export."""
        scene = context.scene
        em_tools = scene.em_tools

        if scene.rdf_export_all_graphs:
            ids = []
            for graphml_item in em_tools.graphml_files:
                if getattr(graphml_item, 'is_publishable', True):
                    ids.append(graphml_item.name)
            return ids

        # Single active graph
        if em_tools.active_file_index < 0 or em_tools.active_file_index >= len(em_tools.graphml_files):
            return []
        return [em_tools.graphml_files[em_tools.active_file_index].name]

    def _resolve_output_path(self, scene):
        """Apply the format's expected extension to the user's path if needed."""
        raw = scene.rdf_export_path
        if not raw:
            return None
        path = bpy.path.abspath(raw)

        ext_map = {
            'turtle': '.ttl',
            'nt':     '.nt',
            'jsonld': '.jsonld',
            'trig':   '.trig',
            'xml':    '.rdf',
        }
        wanted = ext_map.get(scene.rdf_format, '.ttl')

        root, ext = os.path.splitext(path)
        if ext.lower() != wanted:
            path = root + wanted
        return path

    # ── Execute ─────────────────────────────────────────────────────────────

    def execute(self, context):
        scene = context.scene

        # 1) Validate path
        output_path = self._resolve_output_path(scene)
        if not output_path:
            self.report({'ERROR'}, "No output path set. Choose a file in RDF Export Path.")
            return {'CANCELLED'}

        # 2) Validate format
        format_key = scene.rdf_format

        # 3) Validate base URI
        base_uri = (scene.rdf_base_uri or "").strip()
        if not base_uri:
            self.report({'ERROR'}, "Base URI is empty. Use a valid URI prefix (e.g. https://heriverse.example/em/).")
            return {'CANCELLED'}

        # 4) Optional parent HDT IRI (HP33i binding)
        parent_hdt = (scene.rdf_parent_hdt_iri or "").strip() or None

        # 5) Try import s3dgraphy exporter
        RDFExporter, err = _try_import_exporter()
        if RDFExporter is None:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}

        # 6) Resolve graph IDs
        graph_ids = self._resolve_graph_ids(context)
        if not graph_ids:
            self.report(
                {'ERROR'},
                "No graphs available. Load a GraphML file in EM Setup and (if 'all graphs' "
                "is enabled) mark at least one as Publishable."
            )
            return {'CANCELLED'}

        # 7) Run export — parent_hdt_iri is wired through to the exporter
        #    which emits the hdto:HP33i_is_proposition_set_of triple per graph.
        try:
            exporter = RDFExporter(
                output_path=output_path,
                format=format_key,
                base_uri=base_uri,
                parent_hdt_iri=parent_hdt,
            )
            written_path = exporter.export_graphs(graph_ids)
        except ValueError as e:
            # Typical case: malformed parent_hdt_iri
            self.report({'ERROR'}, f"Invalid parameter: {e}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"RDF export failed: {e}")
            return {'CANCELLED'}

        # 8) Report
        stats = exporter.stats
        summary = (
            f"RDF export OK: {written_path} "
            f"({stats['graphs']} graphs, {stats['nodes']} nodes, "
            f"{stats['edges_emitted']} edges emitted, "
            f"{stats['edges_skipped_deprecated']} deprecated skipped, "
            f"{stats['nodes_unmapped']} nodes unmapped, "
            f"{stats['edges_unmapped']} edges unmapped"
        )
        if parent_hdt:
            summary += f", {stats.get('parent_hdt_bindings', 0)} HDT bindings to {parent_hdt}"
        summary += ")"
        self.report({'INFO'}, summary)
        print(f"[RDF export] {summary}")
        return {'FINISHED'}


# ──────────────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────────────

_classes = (EXPORT_OT_rdf,)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
