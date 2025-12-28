"""
Tapestry Integration Properties

Property groups for Tapestry, to be integrated in scene.em_tools
"""

import bpy
from bpy.props import (
    StringProperty, IntProperty, BoolProperty, EnumProperty,
    FloatProperty, CollectionProperty, PointerProperty
)
from bpy.types import PropertyGroup


class TapestryVisibleProxy(PropertyGroup):
    """Represents a proxy visible in camera view"""
    us_id: StringProperty(name="US ID")  # type: ignore
    object_name: StringProperty(name="Object Name")  # type: ignore
    visibility_percent: FloatProperty(
        name="Visibility %",
        min=0.0,
        max=100.0
    )  # type: ignore
    in_queue: BoolProperty(name="In Queue", default=False)  # type: ignore


def _update_render_resolution(self, context):
    """Update scene render resolution when Tapestry resolution changes"""
    scene = context.scene
    scene.render.resolution_x = self.render_resolution_x
    scene.render.resolution_y = self.render_resolution_y


class TapestryManagerProps(PropertyGroup):
    """
    Tapestry integration properties

    Accessed via: scene.em_tools.tapestry
    """

    # ============================================
    # NETWORK SETTINGS
    # ============================================

    server_address: StringProperty(
        name="Server Address",
        description="Tapestry server IP or hostname",
        default="localhost"
    )  # type: ignore

    server_port: IntProperty(
        name="Port",
        description="Tapestry server port",
        default=9000,
        min=1,
        max=65535
    )  # type: ignore

    connection_status: BoolProperty(
        name="Connected",
        description="Connection status to Tapestry server",
        default=False
    )  # type: ignore

    # ============================================
    # RENDER SETTINGS
    # ============================================

    render_camera: PointerProperty(
        name="Camera",
        description="Camera to use for rendering",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'CAMERA'
    )  # type: ignore

    render_resolution_x: IntProperty(
        name="Resolution X",
        description="Render resolution width",
        default=1024,
        min=256,
        max=4096,
        update=_update_render_resolution
    )  # type: ignore

    render_resolution_y: IntProperty(
        name="Resolution Y",
        description="Render resolution height",
        default=1024,
        min=256,
        max=4096,
        update=_update_render_resolution
    )  # type: ignore

    use_visible_only: BoolProperty(
        name="Use Only Visible Proxies",
        description="Filter proxies outside camera frustum or fully occluded",
        default=True
    )  # type: ignore

    # ============================================
    # VISIBLE PROXIES LIST
    # ============================================

    visible_proxies: CollectionProperty(
        type=TapestryVisibleProxy
    )  # type: ignore

    visible_proxies_count: IntProperty(
        name="Visible Proxies Count",
        default=0
    )  # type: ignore

    # ============================================
    # EPOCH SELECTION
    # ============================================

    def _get_epoch_items(self, context):
        """Dynamic epoch list from EM Epoch Manager"""
        items = [('NONE', 'No Epoch Filter', 'Use all objects regardless of epoch')]

        scene = context.scene
        if hasattr(scene, 'em_tools') and scene.em_tools.mode_em_advanced:
            epochs = scene.em_tools.epochs
            if hasattr(epochs, 'list') and epochs.list:
                for i, epoch in enumerate(epochs.list):
                    items.append((epoch.name, epoch.name, f"Filter by epoch: {epoch.name}"))

        return items

    selected_epoch: EnumProperty(
        name="Epoch",
        description="Select epoch to filter objects (EM Advanced mode only)",
        items=_get_epoch_items
    )  # type: ignore

    # ============================================
    # GENERATION PARAMETERS
    # ============================================

    model_name: EnumProperty(
        name="Model",
        description="AI model to use for generation",
        items=[
            ('v1-5-pruned-emaonly.safetensors', 'SD 1.5',
             'Stable Diffusion 1.5 (works with ControlNet)'),
            ('sd_xl_base_1.0.safetensors', 'SDXL',
             'Stable Diffusion XL (higher quality, no ControlNet)')
        ],
        default='v1-5-pruned-emaonly.safetensors'
    )  # type: ignore

    generation_steps: IntProperty(
        name="Steps",
        description="Number of diffusion steps",
        default=20,
        min=1,
        max=150
    )  # type: ignore

    cfg_scale: FloatProperty(
        name="CFG Scale",
        description="Classifier-free guidance scale",
        default=7.5,
        min=1.0,
        max=20.0
    )  # type: ignore

    denoise_strength: FloatProperty(
        name="Denoise Strength",
        description="How much to denoise (0=keep original, 1=full generation)",
        default=0.75,
        min=0.0,
        max=1.0
    )  # type: ignore

    # ============================================
    # ADVANCED SETTINGS
    # ============================================

    render_samples: IntProperty(
        name="Samples",
        description="Number of render samples (Cycles) - 1 is enough for ID/depth/cryptomatte",
        default=1,  # 1 sample is sufficient for ID/depth (no lighting calculation)
        min=1,
        max=64
    )  # type: ignore

    export_normals: BoolProperty(
        name="Export Normals",
        description="Include normal pass for lighting hints",
        default=True
    )  # type: ignore

    keep_intermediate: BoolProperty(
        name="Keep Intermediate Files",
        description="Keep EXR multilayer file after extraction",
        default=False
    )  # type: ignore

    auto_submit: BoolProperty(
        name="Auto Submit",
        description="Automatically submit job to Tapestry after render",
        default=False
    )  # type: ignore

    last_export_path: StringProperty(
        name="Last Export Path",
        description="Path to last Tapestry export directory",
        default=""
    )  # type: ignore

    # ============================================
    # UI STATE
    # ============================================

    network_expanded: BoolProperty(
        name="Network Expanded",
        default=False
    )  # type: ignore

    advanced_expanded: BoolProperty(
        name="Advanced Expanded",
        default=False
    )  # type: ignore


# Registration list for this module
classes = (
    TapestryVisibleProxy,
    TapestryManagerProps,
)


def register():
    # NOTE: PropertyGroups are registered by em_props.py
    # TapestryVisibleProxy and TapestryManagerProps are in the em_props.classes tuple
    # No need to register them here to avoid "already registered" errors
    pass


def unregister():
    # NOTE: PropertyGroups are unregistered by em_props.py
    # No need to unregister them here
    pass
