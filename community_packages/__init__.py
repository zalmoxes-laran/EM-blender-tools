"""Community packages in EM Tools (MICRO-PL12, row W9 of the extensions plan).

The packages of this computer (``~/.s3dgraphy``, the same EMStudio reads) in
the Preferences; their colour schemes and vocabularies in the Visual Manager;
the AnnotationRegion chain READ by Proxy Box and Areale (G14 — writing it is
1.7); the measures the packages declare computed from the placed points. See
``core.py``. The repositories of this computer (X6, MICRO-PL26): ``repositories.py``.
"""

from . import i18n, operators, repo_operators


def register():
    i18n.register()
    operators.register()
    repo_operators.register()       # MICRO-PL26 (X6): the repositories, as EMStudio reads them


def unregister():
    repo_operators.unregister()
    operators.unregister()
    i18n.unregister()
