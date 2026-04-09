"""
Epoch Lighting — Per-epoch HDR world lighting management.

Provides:
- apply_epoch_world_lighting(context, epoch): pure function to set up
  or update the Blender World with an HDR environment from an epoch.
- EPOCH_OT_apply_lighting: operator to manually apply epoch lighting.

The managed world is always named "EM_Epoch_World".  No other world
datablocks are touched.
"""

import os

import bpy  # type: ignore
from bpy.types import Operator  # type: ignore


# =====================================================
# CONSTANTS
# =====================================================

EM_WORLD_NAME = "EM_Epoch_World"

# Deterministic node names inside the managed world
_NODE_NAMES = {
    "output":   "EM_WorldOutput",
    "bg":       "EM_Background",
    "env":      "EM_EnvTexture",
    "mapping":  "EM_Mapping",
    "texcoord": "EM_TexCoord",
}


# =====================================================
# HELPERS
# =====================================================

def _ensure_node(nodes, bl_idname, name):
    """Return an existing node (matched by *name* and *type*) or create one."""
    existing = nodes.get(name)
    if existing is not None and existing.bl_idname == bl_idname:
        return existing
    # Remove stale node with same name but wrong type
    if existing is not None:
        nodes.remove(existing)
    node = nodes.new(type=bl_idname)
    node.name = name
    return node


def _find_or_load_image(filepath):
    """Return an existing image datablock whose resolved path matches
    *filepath*, or load a new one.  Returns None on failure."""
    abs_path = os.path.normpath(os.path.abspath(filepath))
    for img in bpy.data.images:
        try:
            existing = os.path.normpath(os.path.abspath(bpy.path.abspath(img.filepath)))
            if existing == abs_path:
                img.reload()
                return img
        except Exception:
            continue
    # Load new
    try:
        img = bpy.data.images.load(filepath, check_existing=True)
        return img
    except Exception as e:
        print(f"EM Epoch Lighting: could not load image '{filepath}': {e}")
        return None


# =====================================================
# CORE FUNCTION
# =====================================================

def apply_epoch_world_lighting(context, epoch):
    """Create / update the EM-managed world with the epoch's HDR settings.

    Parameters
    ----------
    context : bpy.types.Context
    epoch : EPOCHListItem  (the Blender PropertyGroup instance)

    Returns
    -------
    bool – True on success, False on failure (missing file, etc.)
    """
    # --- resolve HDR path ---------------------------------------------------
    raw_path = epoch.epoch_hdr_path
    if not raw_path:
        print("EM Epoch Lighting: no HDR path set on epoch.")
        return False

    abs_path = bpy.path.abspath(raw_path)
    if not os.path.isfile(abs_path):
        print(f"EM Epoch Lighting: HDR file not found: {abs_path}")
        return False

    # --- get or create the managed world ------------------------------------
    world = bpy.data.worlds.get(EM_WORLD_NAME)
    if world is None:
        world = bpy.data.worlds.new(EM_WORLD_NAME)
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links

    # --- ensure nodes -------------------------------------------------------
    node_output  = _ensure_node(nodes, 'ShaderNodeOutputWorld',      _NODE_NAMES["output"])
    node_bg      = _ensure_node(nodes, 'ShaderNodeBackground',       _NODE_NAMES["bg"])
    node_env     = _ensure_node(nodes, 'ShaderNodeTexEnvironment',   _NODE_NAMES["env"])
    node_mapping = _ensure_node(nodes, 'ShaderNodeMapping',          _NODE_NAMES["mapping"])
    node_tc      = _ensure_node(nodes, 'ShaderNodeTexCoord',         _NODE_NAMES["texcoord"])

    # --- load / assign image ------------------------------------------------
    img = _find_or_load_image(abs_path)
    if img is None:
        return False
    node_env.image = img

    # --- set parameters -----------------------------------------------------
    node_bg.inputs['Strength'].default_value = epoch.epoch_hdr_intensity

    # Mapping node: rotation is a Vector(3); we only touch Z
    node_mapping.inputs['Rotation'].default_value[0] = 0.0
    node_mapping.inputs['Rotation'].default_value[1] = 0.0
    node_mapping.inputs['Rotation'].default_value[2] = epoch.epoch_hdr_rotation

    # --- rewire (clear + reconnect) -----------------------------------------
    links.clear()
    links.new(node_tc.outputs['Generated'],   node_mapping.inputs['Vector'])
    links.new(node_mapping.outputs['Vector'],  node_env.inputs['Vector'])
    links.new(node_env.outputs['Color'],       node_bg.inputs['Color'])
    links.new(node_bg.outputs['Background'],   node_output.inputs['Surface'])

    # --- layout nodes for readability (optional) ----------------------------
    node_tc.location      = (-800, 300)
    node_mapping.location = (-600, 300)
    node_env.location     = (-300, 300)
    node_bg.location      = (0, 300)
    node_output.location  = (200, 300)

    # --- assign world to scene ----------------------------------------------
    context.scene.world = world
    return True


# =====================================================
# OPERATOR
# =====================================================

class EPOCH_OT_apply_lighting(Operator):
    """Apply the selected epoch's HDR lighting to the scene World"""
    bl_idname = "epoch_manager.apply_epoch_lighting"
    bl_label = "Apply Epoch Lighting"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        epochs = em_tools.epochs
        if epochs.list_index < 0 or epochs.list_index >= len(epochs.list):
            return False
        epoch = epochs.list[epochs.list_index]
        return epoch.epoch_lighting_enabled and bool(epoch.epoch_hdr_path)

    def execute(self, context):
        epoch = context.scene.em_tools.epochs.list[
            context.scene.em_tools.epochs.list_index
        ]
        ok = apply_epoch_world_lighting(context, epoch)
        if ok:
            self.report({'INFO'}, f"Applied lighting from epoch '{epoch.name}'")
        else:
            self.report({'WARNING'},
                        f"Could not apply lighting for epoch '{epoch.name}' "
                        f"— check HDR path")
        return {'FINISHED'}


# =====================================================
# REGISTRATION
# =====================================================

def register_lighting():
    bpy.utils.register_class(EPOCH_OT_apply_lighting)


def unregister_lighting():
    try:
        bpy.utils.unregister_class(EPOCH_OT_apply_lighting)
    except RuntimeError:
        pass
