# export_manager/providers/rdf/properties.py
"""RDF Export — Scene properties.

Attached to bpy.types.Scene with the rdf_* prefix so they live alongside the
existing heriverse_* / em_* scene properties. The export operator reads them.
"""

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty


def _scene_props():
    """Return (attr_name, Blender property) pairs to attach to Scene."""
    path_opts = {'PATH_SUPPORTS_BLEND_RELATIVE'} if bpy.app.version >= (4, 5, 0) else set()

    return [
        ("rdf_export_path", StringProperty(
            name="RDF Export Path",
            description="File path where to save the RDF output. Extension is adjusted automatically to match the chosen format.",
            subtype='FILE_PATH',
            default="",
            options=path_opts,
        )),
        ("rdf_format", EnumProperty(
            name="Format",
            description="RDF serialization format",
            items=[
                ('turtle',   'Turtle (.ttl)',
                 'Turtle — human-readable, recommended for inspection and small/medium datasets'),
                ('nt',       'N-Triples (.nt)',
                 'N-Triples — one triple per line, no prefixes; best for streaming and large datasets'),
                ('jsonld',   'JSON-LD (.jsonld)',
                 'JSON-LD — JSON with semantic context; best for web/JS consumers'),
                ('trig',     'TriG (.trig)',
                 'TriG — like Turtle but with named graph support; recommended for multi-graph export'),
                ('xml',      'RDF/XML (.rdf)',
                 'RDF/XML — legacy XML serialization (interoperability with older tools)'),
            ],
            default='turtle',
        )),
        ("rdf_base_uri", StringProperty(
            name="Base URI",
            description=(
                "URI prefix used to mint identifiers for graphs and nodes. "
                "Node IRIs are of the form <base>/graph/<graph_id>/node/<node_id>. "
                "For local tests any value works (e.g. https://localhost/em/). "
                "For LOD publishing, use your own resolvable domain (e.g. https://stratigraph.cnr.it/em/)."
            ),
            default="https://heriverse.example/em/",
        )),
        ("rdf_export_all_graphs", BoolProperty(
            name="Export all publishable graphs",
            description=(
                "If enabled, exports all graphs marked as 'publishable' into a single multi-named-graph file. "
                "If disabled, exports only the currently active graph."
            ),
            default=False,
        )),
        ("rdf_parent_hdt_iri", StringProperty(
            name="Parent HDT IRI (optional)",
            description=(
                "If set, every exported EMGraph (HC16) is attached to this HC2 Heritage Digital Twin via "
                "hdto:HP33i_is_proposition_set_of. Use when all the graphs you are exporting are proposition sets "
                "of the same parent HDT (e.g. the site/landscape HDT). Leave empty to skip this binding — "
                "HDT linkage can also be expressed via explicit HDTNode instances inside the graph."
            ),
            default="",
        )),
        ("rdf_export_advanced", BoolProperty(
            name="Advanced RDF options",
            description="Show advanced RDF export options",
            default=False,
        )),
    ]


def register():
    for attr, prop in _scene_props():
        setattr(bpy.types.Scene, attr, prop)


def unregister():
    for attr, _prop in _scene_props():
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)
