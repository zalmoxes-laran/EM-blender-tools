"""Le letture 3D del grafo (punto, linea, polilinea) mostrate in Blender.

La geometria sta in ``data.coords`` della regione e arriva in Blender attraverso
il glTF di s3Dgraphy (`geometry_to_gltf`); torna nel grafo, quando lo si chiede,
con `gltf_to_geometry` («Bring back to graph», primo pezzo del sync
dell'authoring).
"""

from . import operators
from . import ui


def register():
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
