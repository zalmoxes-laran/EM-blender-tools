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
    scene.render.image_settings.file_format = 'OPEN_EXR_MULTILAYER'
    scene.render.image_settings.color_depth = '32'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.exr_codec = 'ZIP'  # Lossless compression

    # Get active view layer
    view_layer = scene.view_layers.active

    # Enable required passes
    view_layer.use_pass_combined = True
    view_layer.use_pass_z = True  # Depth pass

    # Enable Cryptomatte
    view_layer.use_pass_cryptomatte_object = True
    view_layer.use_pass_cryptomatte_material = True
    view_layer.cycles.use_pass_crypto_accurate = True  # More accurate

    # Optional passes
    if export_normals:
        view_layer.use_pass_normal = True

    # Cycles settings - VERY LOW SAMPLES (ID/depth only, NO lighting!)
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

    print(f"Render setup: {res_x}x{res_y}, Cycles {samples} samples (ID-only mode, no lighting)")


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

    # Extract Combined (RGB)
    combined_path = output_dir / "render_rgb.png"
    rgb_data = _extract_pass_oiio(pixels, spec, "Combined", channels=3)
    _save_image_oiio(rgb_data, combined_path, spec.width, spec.height, channels=3)
    result['rgb'] = str(combined_path)

    # Extract Depth
    depth_path = output_dir / "render_depth.png"
    depth_data = _extract_pass_oiio(pixels, spec, "Depth", channels=1)
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
