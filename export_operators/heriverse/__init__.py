"""What is left of the Heriverse exporter: the pieces a VERSION ON DISK uses.

H4 (E.D., 5 Oct 2026, the correction of the evening): the mesh re-exporter
dedicated to Heriverse does not come back as it was. A package for Heriverse /
ATON is a VERSION ON DISK — use ``heriverse``/``aton``, made by «Prepare for a
use…» (``sync_manager/asset_versions.py``) and registered with its sha256 —
and the Publication Deck writes the folder with the em.json and those versions
(``publication_heriverse.py``, ``publication_deck_ui/heriverse.py``).

What the old engine had and the version uses stays here:

    utils.py           -> clean_filename, find_layer_collection, get_collection_for_object
    gltf.py            -> export_gltf_with_animation_support: the glTF writing
                          (its settings, no Draco of its own — Q5)
    dissemination.py   -> who is published and who is not (bpy-free)

The rest — the operator ``export.heriverse`` and its project tree, the JSON
writer ``export.heriversejson``, the collections helper, the threaded export —
is in ``_dead_code/`` with a note (``_dead_code/README.md``, H4). No operator
is registered from here.
"""

from .utils import clean_filename, find_layer_collection, get_collection_for_object
from .gltf import export_gltf_with_animation_support

__all__ = [
    'clean_filename',
    'find_layer_collection',
    'get_collection_for_object',
    'export_gltf_with_animation_support',
]
