"""RDF Export provider: UI section + Scene properties.

Renders the 'RDF Export' section in the Export Manager panel (EM Bridge
sidebar). Calls into the `export.rdf` operator (export_operators/rdf/) which
in turn delegates to s3dgraphy.exporter.RDFExporter.

This provider exposes:
  * Format selection (Turtle / N-Triples / JSON-LD / RDF-XML / TriG)
  * Output path
  * Base URI (the prefix used to mint node IRIs)
  * "Export all publishable graphs" toggle (vs only active)
  * Optional parent HDT IRI (links all exported EMGraphs to an HC2 via HP33)
"""

from ...registry import ExportProvider, register_provider, unregister_provider
from . import properties, ui


PROVIDER = ExportProvider(
    id="rdf",
    label="RDF Export (Turtle / N-Triples / JSON-LD)",
    order=15,  # rendered before Heriverse (order=20)
    icon='RNA',
    poll=ui.poll,
    draw=ui.draw,
    help_title="RDF Export",
    help_text=(
        "Export the current EM graph(s) to RDF using the CIDOC-CRM + HDT-O + "
        "Extended Matrix ontology declared in s3dgraphy v1.6.0. Output formats: "
        "Turtle (.ttl), N-Triples (.nt), JSON-LD (.jsonld), RDF/XML (.rdf), "
        "TriG (.trig). Requires rdflib (pip install rdflib in Blender's Python). "
        "After export, the .ttl can be loaded into Oxigraph, GraphDB, Virtuoso "
        "or any SPARQL-1.1 triplestore for querying."
    ),
    help_url="panels/rdf_export.html#rdf-export",
)


def register():
    properties.register()
    register_provider(PROVIDER)


def unregister():
    unregister_provider(PROVIDER.id)
    properties.unregister()
