"""Community packages in EM Tools (MICRO-PL12, row W9 of the extensions plan).

The packages of this computer (``~/.s3dgraphy``, the same EMStudio reads) in
the Preferences; their colour schemes and vocabularies in the Visual Manager;
the AnnotationRegion chain READ by Proxy Box and Areale (G14 — writing it is
1.7); the measures the packages declare computed from the placed points. See
``core.py``.
"""

from . import i18n, operators


def register():
    i18n.register()
    operators.register()


def unregister():
    operators.unregister()
    i18n.unregister()
