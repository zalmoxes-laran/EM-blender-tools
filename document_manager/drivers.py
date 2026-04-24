"""Scale-driver helpers for the Quad ↔ Camera relationship.

In CAMERA_DRIVEN mode the quad must fill the camera frustum exactly —
this is achieved via scripted drivers on the quad's scale X/Y channels
that depend on the camera lens angle, the quad's local Z offset, and
the image aspect ratio (PhotogrTool pattern).

In every other drive_mode (QUAD_DRIVEN, UNLINKED, NO_CAMERA) the quad
scale is authored freely and drivers must not be present.

This module exposes three operations used by mode-switch operators:

    install_scale_drivers(quad, cam, image_aspect)
    remove_scale_drivers(quad)
    freeze_scale_from_drivers(quad)        # bake current driver output
                                           # into obj.scale, then remove

All three are idempotent and safe to call on quads without
animation_data.
"""
import bpy


# --- Scale driver expressions (covers PERSP and ORTHO cameras) ---
#
# Plane created via primitive_plane_add() and resized to 0.5 has
# vertices at ±0.5 → world width at scale=1 is 1.0. With
# ``sensor_fit = 'HORIZONTAL'`` and render resolution matching the
# image, the aspect variable is h/w = resY/resX.
#
# PERSP: at local depth d (local-Z, negative looking down -Z) the
# full horizontal frustum width is 2 * d * tan(angle/2). Since the
# driver variable ``depth`` is signed local-Z, d = -depth, so:
#     scale_x = -2 * depth * tan(camAngle/2)
#     scale_y = -2 * depth * tan(camAngle/2) * aspect
#
# ORTHO: the visible horizontal extent is simply ``ortho_scale`` at
# any depth (no perspective):
#     scale_x = orthoScale
#     scale_y = orthoScale * aspect
#
# ``type`` is an enum exposed as an integer to drivers:
#     PERSP = 0, ORTHO = 1, PANO = 2.
# PANO is treated like PERSP (rare for document overlays).

# ``max(..., 1e-3)`` on the ortho branch is a safety clamp: if the
# user accidentally drags ``ortho_scale`` toward zero, the driven
# quad would otherwise collapse to zero scale, producing singular
# transforms that make the viewport extremely sluggish (the
# "Blender freeze" observed during ortho scaling gestures).
_EXPR_X = "(max(orthoScale,1e-3) if camType==1 else -2*depth*tan(camAngle/2))"
_EXPR_Y = "(max(orthoScale,1e-3)*{aspect} if camType==1 else -2*depth*tan(camAngle/2)*{aspect})"


def _add_driver_vars(driver, quad_obj, cam_obj):
    """Attach the ``camAngle``, ``depth``, ``orthoScale`` and ``camType``
    variables used by the scale expressions above. Safe to call on a
    freshly-created driver.
    """
    v_angle = driver.variables.new()
    v_angle.name = 'camAngle'
    v_angle.type = 'SINGLE_PROP'
    v_angle.targets[0].id = cam_obj
    v_angle.targets[0].data_path = "data.angle"

    v_depth = driver.variables.new()
    v_depth.name = 'depth'
    v_depth.type = 'TRANSFORMS'
    v_depth.targets[0].id = quad_obj
    v_depth.targets[0].transform_type = 'LOC_Z'
    v_depth.targets[0].transform_space = 'LOCAL_SPACE'

    v_ortho = driver.variables.new()
    v_ortho.name = 'orthoScale'
    v_ortho.type = 'SINGLE_PROP'
    v_ortho.targets[0].id = cam_obj
    v_ortho.targets[0].data_path = "data.ortho_scale"

    v_type = driver.variables.new()
    v_type.name = 'camType'
    v_type.type = 'SINGLE_PROP'
    v_type.targets[0].id = cam_obj
    v_type.targets[0].data_path = "data.type"


def has_scale_drivers(quad_obj):
    """Return True if any driver exists on the quad's scale channels."""
    ad = getattr(quad_obj, "animation_data", None)
    if ad is None or ad.drivers is None:
        return False
    for fcu in ad.drivers:
        if fcu.data_path == "scale":
            return True
    return False


def install_scale_drivers(quad_obj, cam_obj, image_aspect):
    """Install PhotogrTool-style scale drivers on ``quad_obj``.

    Drivers constrain the quad to fill the camera frustum at whatever
    local-Z depth the quad currently has. Any existing scale drivers
    are removed first so the operation is idempotent.

    Args:
        quad_obj:       the mesh object whose scale is to be driven.
        cam_obj:        the camera object supplying ``data.angle``.
        image_aspect:   height / width of the reference image; clamped
                        to 1.0 when the image size is invalid.
    """
    remove_scale_drivers(quad_obj)

    aspect = float(image_aspect) if image_aspect and image_aspect > 0 else 1.0

    drv_y = quad_obj.driver_add('scale', 1).driver
    drv_y.type = 'SCRIPTED'
    _add_driver_vars(drv_y, quad_obj, cam_obj)
    drv_y.expression = _EXPR_Y.format(aspect=aspect)

    drv_x = quad_obj.driver_add('scale', 0).driver
    drv_x.type = 'SCRIPTED'
    _add_driver_vars(drv_x, quad_obj, cam_obj)
    drv_x.expression = _EXPR_X


def remove_scale_drivers(quad_obj):
    """Remove every driver on ``quad_obj``'s scale X/Y/Z channels.

    Idempotent — silently does nothing if no drivers are present.
    """
    ad = getattr(quad_obj, "animation_data", None)
    if ad is None or ad.drivers is None:
        return
    for i in (0, 1, 2):
        try:
            quad_obj.driver_remove('scale', i)
        except (RuntimeError, TypeError):
            # No driver on that channel — ignore.
            pass


def freeze_scale_from_drivers(quad_obj):
    """Evaluate the current driver output and bake it into ``obj.scale``,
    then remove the drivers.

    Called when leaving CAMERA_DRIVEN mode: the quad keeps the exact
    size it has right now, but becomes free to edit. Produces no
    visible jump if called after a depsgraph update.

    Returns the frozen scale as a tuple ``(x, y, z)``.
    """
    # Ensure the depsgraph is up to date so ``obj.scale`` holds the
    # latest driver output before we detach.
    bpy.context.view_layer.update()

    frozen = (quad_obj.scale[0], quad_obj.scale[1], quad_obj.scale[2])
    remove_scale_drivers(quad_obj)
    # Re-assign explicitly: without drivers, the scale values we just
    # read become the authoritative ones.
    quad_obj.scale = frozen
    return frozen
