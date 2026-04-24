# export_operators/heriverse/gltf.py
"""Thin wrapper around bpy.ops.export_scene.gltf with Heriverse export_vars applied."""

import bpy


def export_gltf_with_animation_support(filepath, export_vars, scene, use_selection=True,
                                       export_extras=False, export_gpu_instances=False,
                                       format_file="GLTF_SEPARATE"):
    """Template function per l'export glTF con supporto animazioni.

    Usato per sostituire tutte le chiamate dirette a bpy.ops.export_scene.gltf().
    """
    export_params = {
        'filepath': str(filepath),
        'export_format': format_file.upper(),
        'export_copyright': scene.em_tools.EMviq_model_author_name if hasattr(scene.em_tools, 'EMviq_model_author_name') else "",
        'export_texcoords': True,
        'export_normals': True,
        'export_draco_mesh_compression_enable': export_vars.heriverse_use_draco,
        'export_draco_mesh_compression_level': export_vars.heriverse_draco_level,
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

    if export_vars.heriverse_export_animations:
        export_params.update({
            'export_animations': True,
            'export_frame_range': export_vars.heriverse_animation_frame_range,
            'export_frame_step': 1,
            'export_force_sampling': True,
            'export_nla_strips': export_vars.heriverse_export_all_animations,
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
