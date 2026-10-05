"""P3 (6 Oct 2026) · the tab EM Scene in the two spaces of EMStudio.

EMStudio's workspaces (`frontend/src/workspace.ts`) give the 3D side of a study
two places: **Contents** — «which files do I have, and what has become a
document?»: the Storage window (the files), the EMtree, the Shelf, the DTC
chain — and **Space** — «where is it, and what shape has it in each epoch?»:
the Scene and the table of the Models. The tab EM Scene had ten panels side by
side in the order they were written; here they sit under those two names, as
Blender sub-panels, and the Publication Deck comes last, the last step.

* **Contents**: Storage (the panel that was «Files», named after EMStudio's
  window: the space is Contents, the window in it is Storage; the card «Where
  it comes from» is in it), Shelf, Document Manager (a file becomes a document
  there).
* **Space**: Representation Model (RM), Asset versions (the versions are the
  Models table), RMDoc, Anastylosis, Proxy & surface tools, Georeferencing.
* **Publication Deck**, at the bottom.

The two heads draw nothing of their own: they are the names, and each child
keeps its panel, its idname and its commands (nothing lost: the inventory
before and after is in the report of the MICRO). They are registered before
every child (`_core_independent_modules`): a parent must exist first.
"""

import bpy  # type: ignore

CONTENTS = "EM_PT_scene_contents"
SPACE = "EM_PT_scene_space"


class EM_PT_scene_contents(bpy.types.Panel):
    """The files of the study, the shelf and the documents — EMStudio's
    Contents"""
    bl_label = "Contents"
    bl_idname = CONTENTS
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM Scene"
    bl_order = 1

    def draw_header(self, context):
        self.layout.label(text="", icon="FILE_FOLDER")

    def draw(self, context):
        pass


class EM_PT_scene_space(bpy.types.Panel):
    """The models in the scene, their versions and where they stand —
    EMStudio's Space"""
    bl_label = "Space"
    bl_idname = SPACE
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM Scene"
    bl_order = 2

    def draw_header(self, context):
        self.layout.label(text="", icon="SCENE_DATA")

    def draw(self, context):
        pass


CLASSES = (EM_PT_scene_contents, EM_PT_scene_space)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
