# export_operators/heriverse/gltf.py
"""Thin wrapper around bpy.ops.export_scene.gltf with Heriverse export_vars applied."""

import bpy


def export_gltf_with_animation_support(filepath, export_vars, scene, use_selection=True,
                                       export_extras=False, export_gpu_instances=False,
                                       format_file="GLTF_SEPARATE", animations=None,
                                       frame_range=None, image_quality=None):
    """Template function per l'export glTF con supporto animazioni.

    Usato per sostituire tutte le chiamate dirette a bpy.ops.export_scene.gltf().

    ``animations`` (``none`` / ``active`` / ``all``), ``frame_range`` and
    ``image_quality`` come from the RECIPE of a version (``version_recipe``,
    E.D. 6 Oct 2026); left None, the scene's ``export_vars`` decide, as the old
    exporter's panel did.
    """
    export_params = {
        'filepath': str(filepath),
        'export_format': format_file.upper(),
        'export_copyright': scene.em_tools.EMviq_model_author_name if hasattr(scene.em_tools, 'EMviq_model_author_name') else "",
        'export_texcoords': True,
        'export_normals': True,
        # Q5 (E.D., 5 Oct 2026) · no Draco of its own: a model that must be
        # light for the web is a distribution version made by «Prepare for a
        # use…» (Draco there, measured and written in the DTC)
        'export_draco_mesh_compression_enable': False,
        'export_materials': 'EXPORT',
        'use_selection': use_selection,
        'export_apply': True,
        'export_image_format': 'AUTO',
        'export_texture_dir': "",
        'export_keep_originals': False,
        'check_existing': False,
    }

    if export_extras:
        export_params['export_extras'] = True
    if export_gpu_instances:
        export_params['export_gpu_instances'] = True

    if image_quality:
        export_params['export_image_quality'] = int(image_quality)
    if animations is None:
        animate = bool(export_vars.heriverse_export_animations)
        all_of_them = bool(export_vars.heriverse_export_all_animations)
        in_range = bool(export_vars.heriverse_animation_frame_range)
    else:
        animate = animations != "none"
        all_of_them = animations == "all"
        in_range = True if frame_range is None else bool(frame_range)
    if animate:
        export_params.update({
            'export_animations': True,
            'export_frame_range': in_range,
            'export_frame_step': 1,
            'export_force_sampling': True,
            'export_nla_strips': all_of_them,
            'export_def_bones': True,
            'export_current_frame': False,
            'export_skins': True,
            'export_all_influences': True,
            'export_morph': True,
        })
    else:
        export_params.update({
            'export_animations': False,
            'export_frame_range': False,
            'export_frame_step': 1,
            'export_force_sampling': False,
            'export_nla_strips': False,
            'export_def_bones': False,
            'export_current_frame': False,
            'export_skins': False,
            'export_all_influences': False,
            'export_morph': False,
        })

    bpy.ops.export_scene.gltf(**export_params)
