"""
Render utilities for Tapestry integration

Handles:
- EXR multilayer render setup
- Cryptomatte configuration
- Pass extraction from EXR
- Mask generation per proxy
"""

import bpy
import os
import numpy as np
from pathlib import Path


def save_render_settings(scene):
    """
    Save current render settings to restore later

    Returns:
        dict: Saved settings
    """
    view_layer = scene.view_layers[0] if hasattr(scene.view_layers, '__getitem__') else scene.view_layers.active

    saved = {
        'engine': scene.render.engine,
        'resolution_x': scene.render.resolution_x,
        'resolution_y': scene.render.resolution_y,
        'resolution_percentage': scene.render.resolution_percentage,
        'file_format': scene.render.image_settings.file_format,
        'color_depth': scene.render.image_settings.color_depth,
        'color_mode': scene.render.image_settings.color_mode,
        'camera': scene.camera,
        'samples': scene.cycles.samples if hasattr(scene, 'cycles') else None,
        'use_denoising': scene.cycles.use_denoising if hasattr(scene, 'cycles') else None,
        'max_bounces': scene.cycles.max_bounces if hasattr(scene, 'cycles') else None,
        'diffuse_bounces': scene.cycles.diffuse_bounces if hasattr(scene, 'cycles') else None,
        'glossy_bounces': scene.cycles.glossy_bounces if hasattr(scene, 'cycles') else None,
        'transmission_bounces': scene.cycles.transmission_bounces if hasattr(scene, 'cycles') else None,
        'volume_bounces': scene.cycles.volume_bounces if hasattr(scene, 'cycles') else None,
        # View layer passes
        'use_pass_combined': view_layer.use_pass_combined,
        'use_pass_z': view_layer.use_pass_z,
        'use_pass_normal': view_layer.use_pass_normal,
        'use_pass_cryptomatte_object': view_layer.use_pass_cryptomatte_object,
        'use_pass_cryptomatte_material': view_layer.use_pass_cryptomatte_material,
    }

    return saved


def restore_render_settings(scene, saved):
    """
    Restore render settings from saved state

    Args:
        scene: Blender scene
        saved: Dict with saved settings
    """
    if not saved:
        return

    view_layer = scene.view_layers[0] if hasattr(scene.view_layers, '__getitem__') else scene.view_layers.active

    # Restore render settings
    scene.render.engine = saved['engine']
    scene.render.resolution_x = saved['resolution_x']
    scene.render.resolution_y = saved['resolution_y']
    scene.render.resolution_percentage = saved['resolution_percentage']
    scene.render.image_settings.file_format = saved['file_format']
    scene.render.image_settings.color_depth = saved['color_depth']
    scene.render.image_settings.color_mode = saved['color_mode']
    scene.camera = saved['camera']

    # Restore Cycles settings
    if saved['samples'] is not None:
        scene.cycles.samples = saved['samples']
    if saved['use_denoising'] is not None:
        scene.cycles.use_denoising = saved['use_denoising']
    if saved['max_bounces'] is not None:
        scene.cycles.max_bounces = saved['max_bounces']
    if saved['diffuse_bounces'] is not None:
        scene.cycles.diffuse_bounces = saved['diffuse_bounces']
    if saved['glossy_bounces'] is not None:
        scene.cycles.glossy_bounces = saved['glossy_bounces']
    if saved['transmission_bounces'] is not None:
        scene.cycles.transmission_bounces = saved['transmission_bounces']
    if saved['volume_bounces'] is not None:
        scene.cycles.volume_bounces = saved['volume_bounces']

    # Restore view layer passes
    view_layer.use_pass_combined = saved['use_pass_combined']
    view_layer.use_pass_z = saved['use_pass_z']
    view_layer.use_pass_normal = saved['use_pass_normal']
    view_layer.use_pass_cryptomatte_object = saved['use_pass_cryptomatte_object']
    view_layer.use_pass_cryptomatte_material = saved['use_pass_cryptomatte_material']

    print("Render settings restored")


def setup_exr_render(scene, res_x, res_y, samples, camera=None, export_normals=True):
    """
    Configure scene for EXR multilayer rendering with Cryptomatte

    Uses CYCLES with very low samples - just for ID/depth/normals, no lighting calculation

    Args:
        scene: Blender scene
        res_x: Resolution width
        res_y: Resolution height
        samples: Number of render samples (low, typically 8)
        camera: Camera object to use for rendering (optional)
        export_normals: Include normal pass
    """
    # Set active camera if provided
    if camera:
        scene.camera = camera

    # Force Cycles (no user choice - optimized for ID/depth only)
    scene.render.engine = 'CYCLES'

    # Set resolution
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.resolution_percentage = 100

    # Set EXR multilayer format
    # Blender 5.0 changed EXR: use media_type instead of OPEN_EXR_MULTILAYER
    # Try Blender 5.0 method first, then fallback to older versions

    scene.render.image_settings.color_depth = '32'
    scene.render.image_settings.exr_codec = 'ZIP'  # Lossless compression

    # CRITICAL: Try Blender 5.0 approach first (media_type)
    try:
        # Blender 5.0: OPEN_EXR + media_type
        scene.render.image_settings.file_format = 'OPEN_EXR'
        scene.render.image_settings.media_type = 'MULTI_LAYER_IMAGE'
        print("Using Blender 5.0 EXR multilayer (OPEN_EXR + MULTI_LAYER_IMAGE)")
    except (AttributeError, TypeError):
        # Blender 4.x and older: OPEN_EXR_MULTILAYER
        scene.render.image_settings.file_format = 'OPEN_EXR_MULTILAYER'
        print("Using Blender 4.x EXR multilayer (OPEN_EXR_MULTILAYER)")

    # Get active view layer
    # Blender 5.0 changed view_layers.active to view_layers[0] or active_layer
    try:
        view_layer = scene.view_layers.active
    except AttributeError:
        # Blender 5.0+ doesn't have .active, use first view layer
        view_layer = scene.view_layers[0]

    # DISABLE all passes first (for speed)
    view_layer.use_pass_combined = False
    view_layer.use_pass_z = False
    view_layer.use_pass_normal = False
    view_layer.use_pass_diffuse_color = False
    view_layer.use_pass_emit = False
    view_layer.use_pass_environment = False
    view_layer.use_pass_ambient_occlusion = False
    view_layer.use_pass_shadow = False
    view_layer.use_pass_mist = False

    # Enable ONLY required passes (minimal for speed)
    view_layer.use_pass_combined = True  # RGB render
    view_layer.use_pass_z = True  # Depth pass

    # Enable Cryptomatte (for object masks)
    view_layer.use_pass_cryptomatte_object = True
    view_layer.use_pass_cryptomatte_material = True

    # Blender 5.0 removed use_pass_crypto_accurate (always accurate now)
    if hasattr(view_layer.cycles, 'use_pass_crypto_accurate'):
        view_layer.cycles.use_pass_crypto_accurate = True  # More accurate (Blender <5.0)

    # Optional: Normal pass (only if requested)
    if export_normals:
        view_layer.use_pass_normal = True

    # Debug: Print enabled passes
    print(f"  - Enabled passes:")
    print(f"    - Combined: {view_layer.use_pass_combined}")
    print(f"    - Depth (Z): {view_layer.use_pass_z}")
    print(f"    - Cryptomatte Object: {view_layer.use_pass_cryptomatte_object}")
    print(f"    - Cryptomatte Material: {view_layer.use_pass_cryptomatte_material}")
    if export_normals:
        print(f"    - Normal: {view_layer.use_pass_normal}")

    # Blender 5.0 NOTE: EXR multilayer works differently
    # We'll extract passes from render result in memory instead of EXR file
    scene.use_nodes = False  # Disable compositor for now (extract from bpy.data.images['Render Result'])
    scene.render.use_compositing = False

    # Cycles settings - FORCE 1 SAMPLE (ID/depth/cryptomatte only, NO lighting calculation!)
    # More than 1 sample is USELESS for ID passes and wastes time
    if samples > 1:
        print(f"WARNING: Forcing samples from {samples} to 1 (ID/depth only, no lighting needed)")
        samples = 1

    scene.cycles.samples = samples
    scene.cycles.use_denoising = False  # No denoising needed for ID passes

    # CRITICAL: Disable ALL light bouncing (we only need geometry/ID)
    scene.cycles.max_bounces = 0
    scene.cycles.diffuse_bounces = 0
    scene.cycles.glossy_bounces = 0
    scene.cycles.transmission_bounces = 0
    scene.cycles.volume_bounces = 0

    # Disable caustics (faster)
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False

    # Use fastest integrator settings
    scene.cycles.sample_clamp_indirect = 0  # No clamping needed (no lighting)

    print(f"Tapestry Render Setup: {res_x}x{res_y}, {samples} sample (ID-only: Combined+Depth+Cryptomatte, NO lighting)")
    print(f"  - Max bounces: 0 (geometry only)")
    print(f"  - Denoising: OFF")
    print(f"  - Passes: Combined, Depth, Cryptomatte{' + Normal' if export_normals else ''}")


def prepare_exr_for_tapestry(exr_path, output_dir):
    """
    Prepare EXR for Tapestry upload (EXR-only pipeline)

    In the new pipeline:
    - EXR contains all passes (Combined, Depth, Normal, Cryptomatte)
    - Cryptomatte IDs are in the EXR itself (no separate mask PNGs)
    - Semantic JSON provides object names for Cryptomatte matching

    Args:
        exr_path: Path to rendered EXR file
        output_dir: Directory for any extracted preview images (optional)

    Returns:
        dict: Paths to files for upload
            {
                'exr': path to multilayer EXR,
                'rgb_preview': optional RGB preview PNG (for UI)
            }
    """
    output_dir = Path(output_dir)
    result = {
        'exr': str(exr_path),
        'rgb_preview': None
    }

    # Optional: Extract RGB preview for UI display
    # This is just for visual feedback, not required for generation
    try:
        render_result = bpy.data.images.get('Render Result')
        if render_result:
            scene = bpy.context.scene
            old_format = scene.render.image_settings.file_format

            scene.render.image_settings.file_format = 'PNG'
            scene.render.image_settings.color_mode = 'RGB'

            preview_path = output_dir / "preview_rgb.png"
            render_result.save_render(str(preview_path))
            result['rgb_preview'] = str(preview_path)

            scene.render.image_settings.file_format = old_format
            print(f"  - Saved RGB preview: {preview_path}")
    except Exception as e:
        print(f"Warning: Could not extract RGB preview: {e}")

    print(f"EXR prepared for Tapestry: {exr_path}")
    print(f"  - All passes embedded in EXR (Combined, Depth, Cryptomatte, Normal)")
    print(f"  - Object masks via Cryptomatte IDs (no separate PNGs)")

    return result


def extract_passes_from_render_result(output_dir, visible_proxies):
    """
    Extract passes directly from Blender's Render Result (in-memory)
    This works better with Blender 5.0 which changed EXR multilayer handling

    Args:
        output_dir: Directory to save extracted images
        visible_proxies: List of proxy data with US IDs

    Returns:
        dict: Paths to extracted files
    """
    output_dir = Path(output_dir)
    result = {
        'rgb': None,
        'depth': None,
        'masks': {}
    }

    # Get render result from memory
    render_result = bpy.data.images.get('Render Result')
    if not render_result:
        raise RuntimeError("No render result found. Did rendering complete?")

    # Extract Combined (RGB) - Always available
    # CRITICAL: Set format to PNG before saving (was OPEN_EXR from render setup)
    scene = bpy.context.scene
    old_format = scene.render.image_settings.file_format
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'

    combined_path = output_dir / "render_rgb.png"
    render_result.save_render(str(combined_path))

    # Restore format
    scene.render.image_settings.file_format = old_format

    result['rgb'] = str(combined_path)
    print(f"Saved RGB: {combined_path}")

    # CRITICAL: In Blender 5.0, render_result.size returns (0, 0) even when render is valid!
    # We must get resolution from scene.render instead
    scene = bpy.context.scene
    width = scene.render.resolution_x
    height = scene.render.resolution_y
    print(f"Using resolution from scene.render: {width}x{height}")

    # Try to access render passes from ViewLayer
    import PIL.Image
    view_layer = scene.view_layers[0]

    # Extract Depth pass if available
    depth_path = output_dir / "render_depth.png"

    # IMPORTANT: render_result.size returns (width, height)
    # But numpy/PIL need (height, width, channels)
    # So we create array as (height, width, 3) where height=height, width=width

    print("WARNING: Depth pass extraction from Render Result requires compositor")
    print("  Creating black placeholder for now")

    # Create placeholder depth (black = no depth data)
    # Array shape: (height, width, channels)
    placeholder_depth = np.zeros((height, width, 3), dtype=np.uint8)
    print(f"DEBUG: Placeholder depth shape: {placeholder_depth.shape}")

    # Save using PIL
    depth_img = PIL.Image.fromarray(placeholder_depth, mode='RGB')
    print(f"DEBUG: PIL Image size: {depth_img.size}")
    depth_img.save(str(depth_path))
    result['depth'] = str(depth_path)
    print(f"Saved depth placeholder: {depth_path}")

    # Create placeholder masks (white = all visible)
    print("WARNING: Cryptomatte mask extraction from Render Result not yet implemented")
    print("  Creating white placeholder masks (all proxies fully visible)")

    for proxy in visible_proxies:
        us_id = proxy.us_id
        mask_path = output_dir / f"mask_{us_id}.png"

        # Array shape: (height, width, channels)
        placeholder_mask = np.ones((height, width, 3), dtype=np.uint8) * 255  # White = fully visible
        mask_img = PIL.Image.fromarray(placeholder_mask, mode='RGB')
        mask_img.save(str(mask_path))
        result['masks'][us_id] = str(mask_path)

    print(f"  Created {len(result['masks'])} placeholder masks")

    return result


def extract_exr_passes(exr_path, output_dir, visible_proxies):
    """
    Extract passes from EXR multilayer and generate masks per proxy

    Args:
        exr_path: Path to rendered EXR file
        output_dir: Directory to save extracted images
        visible_proxies: List of proxy data with US IDs

    Returns:
        dict: Paths to extracted files
            {
                'rgb': 'path/to/render_rgb.png',
                'depth': 'path/to/render_depth.png',
                'masks': {'USM100': 'path/to/mask_USM100.png', ...}
            }
    """
    try:
        import OpenImageIO as oiio
    except ImportError:
        # Fallback: Use Blender's image API (less efficient but works)
        return _extract_exr_passes_blender(exr_path, output_dir, visible_proxies)

    output_dir = Path(output_dir)
    result = {
        'rgb': None,
        'depth': None,
        'masks': {}
    }

    # Open EXR file
    img_input = oiio.ImageInput.open(str(exr_path))
    if not img_input:
        raise RuntimeError(f"Cannot open EXR: {exr_path}")

    spec = img_input.spec()

    # Read all pixels
    pixels = img_input.read_image()
    img_input.close()

    # Debug: Print available channel names
    channel_names = [spec.channelnames[i] for i in range(spec.nchannels)]
    print(f"EXR Channels: {channel_names}")

    # Extract Combined (RGB) - Blender 5.0 may use different names
    combined_path = output_dir / "render_rgb.png"
    # Try different pass names (Blender 4.x vs 5.0)
    try:
        rgb_data = _extract_pass_oiio(pixels, spec, "Combined", channels=3)
    except ValueError:
        try:
            # Blender 5.0 might use "ViewLayer.Combined" or just RGB channels
            rgb_data = _extract_pass_oiio(pixels, spec, "ViewLayer.Combined", channels=3)
        except ValueError:
            # Fallback: Use first 3 channels (R, G, B)
            print("WARNING: Using fallback RGB extraction (first 3 channels)")
            rgb_data = pixels[:, :, :3]

    _save_image_oiio(rgb_data, combined_path, spec.width, spec.height, channels=3)
    result['rgb'] = str(combined_path)

    # Extract Depth - Try different names
    depth_path = output_dir / "render_depth.png"
    try:
        depth_data = _extract_pass_oiio(pixels, spec, "Depth", channels=1)
    except ValueError:
        try:
            depth_data = _extract_pass_oiio(pixels, spec, "ViewLayer.Depth", channels=1)
        except ValueError:
            # Find depth channel by searching for "Depth" or "Z"
            depth_channel = None
            for i, name in enumerate(channel_names):
                if "Depth" in name or name.endswith(".Z"):
                    depth_channel = i
                    break
            if depth_channel is not None:
                depth_data = pixels[:, :, depth_channel]
            else:
                raise ValueError("Depth pass not found in EXR")

    # Normalize depth to 0-1 range for visualization
    depth_normalized = _normalize_depth(depth_data)
    _save_image_oiio(depth_normalized, depth_path, spec.width, spec.height, channels=1)
    result['depth'] = str(depth_path)

    # Extract Cryptomatte and generate masks
    cryptomatte_data = _extract_cryptomatte(pixels, spec)

    for proxy in visible_proxies:
        us_id = proxy.us_id
        obj_name = proxy.object_name

        # Generate mask for this object
        mask = _generate_cryptomatte_mask(cryptomatte_data, obj_name, spec.width, spec.height)

        # Save mask
        mask_path = output_dir / f"mask_{us_id}.png"
        _save_image_oiio(mask, mask_path, spec.width, spec.height, channels=1)
        result['masks'][us_id] = str(mask_path)

    print(f"Extracted {len(result['masks'])} masks from EXR")

    return result


def _extract_exr_passes_blender(exr_path, output_dir, visible_proxies):
    """
    Fallback extraction using Blender's image API
    Less efficient but doesn't require OpenImageIO
    """
    output_dir = Path(output_dir)
    result = {
        'rgb': None,
        'depth': None,
        'masks': {}
    }

    # Load EXR into Blender
    img = bpy.data.images.load(str(exr_path))

    try:
        # Extract Combined RGB
        combined_path = output_dir / "render_rgb.png"
        img.save_render(str(combined_path))
        result['rgb'] = str(combined_path)

        # For depth and masks, we need to use compositor
        # This is more complex - create a simple version for now
        print("Warning: Using simplified extraction. Install OpenImageIO for full support.")

        # Create placeholder depth (will be improved)
        depth_path = output_dir / "render_depth.png"
        result['depth'] = str(depth_path)

        # Create placeholder masks (will be improved)
        for proxy in visible_proxies:
            us_id = proxy.us_id
            mask_path = output_dir / f"mask_{us_id}.png"
            result['masks'][us_id] = str(mask_path)

    finally:
        # Cleanup
        bpy.data.images.remove(img)

    return result


def _extract_pass_oiio(pixels, spec, pass_name, channels=3):
    """Extract a specific pass from EXR pixels"""
    # Find pass in spec
    channel_names = [spec.channelnames[i] for i in range(spec.nchannels)]

    # Look for pass channels (e.g., "Combined.R", "Combined.G", "Combined.B")
    pass_channels = [i for i, name in enumerate(channel_names)
                     if name.startswith(pass_name)]

    if not pass_channels:
        raise ValueError(f"Pass '{pass_name}' not found in EXR")

    # Extract channels
    if channels == 1:
        return pixels[:, :, pass_channels[0]]
    else:
        return pixels[:, :, pass_channels[:channels]]


def _extract_cryptomatte(pixels, spec):
    """Extract Cryptomatte data from EXR"""
    # Cryptomatte uses multiple channels to encode object IDs
    # Format: CryptoObject00.R, CryptoObject00.G, CryptoObject00.B, CryptoObject00.A
    # Each pixel contains hash of object name + coverage

    channel_names = [spec.channelnames[i] for i in range(spec.nchannels)]
    crypto_channels = [i for i, name in enumerate(channel_names)
                       if "CryptoObject" in name]

    if not crypto_channels:
        raise ValueError("Cryptomatte pass not found in EXR")

    return pixels[:, :, crypto_channels]


def _generate_cryptomatte_mask(cryptomatte_data, object_name, width, height):
    """
    Generate binary mask for specific object from Cryptomatte data

    Cryptomatte encoding:
    - Each RGBA set contains 2 ID/coverage pairs
    - ID = hash of object name
    - Coverage = fractional coverage (for antialiasing)
    """
    # Compute hash of object name (Cryptomatte uses MurmurHash3)
    obj_hash = _cryptomatte_hash(object_name)

    # Create mask
    mask = np.zeros((height, width), dtype=np.float32)

    # Check each pixel
    for y in range(height):
        for x in range(width):
            # Cryptomatte stores ID/coverage pairs
            # First pair: R (ID), G (coverage)
            # Second pair: B (ID), A (coverage)

            id1 = cryptomatte_data[y, x, 0]  # R
            coverage1 = cryptomatte_data[y, x, 1]  # G

            id2 = cryptomatte_data[y, x, 2]  # B
            coverage2 = cryptomatte_data[y, x, 3]  # A

            # Compare with object hash
            if abs(id1 - obj_hash) < 0.0001:
                mask[y, x] = coverage1
            elif abs(id2 - obj_hash) < 0.0001:
                mask[y, x] = coverage2

    return mask


def _cryptomatte_hash(name):
    """
    Compute Cryptomatte hash for object name
    Uses MurmurHash3 algorithm
    """
    try:
        import mmh3
    except ImportError:
        raise ImportError(
            "mmh3 module not found. Cryptomatte requires mmh3 for object ID hashing.\n"
            "Install it by running: em.bat setup force\n"
            "Or manually: pip install mmh3>=4.1.0"
        )

    # Cryptomatte normalizes hash to 0-1 range
    hash_val = mmh3.hash(name, signed=False)
    return (hash_val & 0xffffffff) / float(0xffffffff)


def _normalize_depth(depth_data):
    """Normalize depth values to 0-1 range for PNG export"""
    min_depth = np.min(depth_data[depth_data > 0])  # Ignore background
    max_depth = np.max(depth_data)

    normalized = (depth_data - min_depth) / (max_depth - min_depth)
    normalized = np.clip(normalized, 0, 1)

    return normalized


def _save_image_oiio(data, path, width, height, channels):
    """Save image data to file using OpenImageIO"""
    import OpenImageIO as oiio

    # Ensure data is in correct format
    if channels == 1:
        # Grayscale - expand to RGB for PNG compatibility
        data_rgb = np.stack([data, data, data], axis=-1)
    else:
        data_rgb = data

    # Create spec
    spec = oiio.ImageSpec(width, height, 3, oiio.FLOAT)

    # Open output
    img_output = oiio.ImageOutput.create(str(path))
    if not img_output:
        raise RuntimeError(f"Cannot create output: {path}")

    img_output.open(str(path), spec)
    img_output.write_image(data_rgb)
    img_output.close()

    print(f"Saved: {path}")
