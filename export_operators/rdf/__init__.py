"""RDF exporter subpackage.

Organization:
    operator.py  -> EXPORT_OT_rdf (bl_idname 'export.rdf')

The operator delegates to s3dgraphy.exporter.RDFExporter for the actual
RDF serialization. rdflib is required (graceful failure with a user-visible
message if not installed).
"""

from . import operator
from .operator import EXPORT_OT_rdf

__all__ = [
    'register',
    'unregister',
    'EXPORT_OT_rdf',
]


def register():
    operator.register()


def unregister():
    operator.unregister()
