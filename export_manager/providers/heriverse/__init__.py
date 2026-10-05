"""Heriverse: no exporter any more, only the Scene properties it left.

H4 (E.D., 5 Oct 2026): nothing is re-exported from Blender for Heriverse.
Heriverse reads the study (em.json) and picks, for each representation model,
the version to load with the one rule of s3dgraphy
(`api.version_for(graph, rm, ["heriverse", "aton", "web", "realtime"])`). The
Publication Deck leads there by two roads (`publication_deck_ui/heriverse.py`):
on the node, and on disk — a folder with the em.json and the versions, a
version for Heriverse being made by «Prepare for a use…» (use heriverse/aton).
The engine and its settings section are in
`_dead_code/export_operators/heriverse/` and
`_dead_code/export_manager/providers/heriverse/ui.py`.

No provider is registered, so nothing draws an export for Heriverse. The
`scene.heriverse_*` properties stay registered, as Q5 kept them: they are
saved in .blend files, `rm_manager/containers.py` still reads the old export
folder as one more place where a model's file may be, the package on disk
goes into `heriverse_export_path` / `heriverse_project_name`, and the glTF of a
version for Heriverse reads the animation settings.
"""

from . import properties


def register():
    properties.register()


def unregister():
    properties.unregister()
