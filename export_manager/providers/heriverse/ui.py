# export_manager/providers/heriverse/ui.py
"""Draw function for the 'Heriverse Export' section of the Export panel.

This module renders the UI and dispatches to the `export.heriverse` operator
defined in export_operators.heriverse. No exporter logic lives here.
"""

# icons_manager lives at the addon root; this file is three levels deep
# (heriverse/providers/export_manager/<addon_root>).
from .... import icons_manager


def poll(context):
    return context.scene.em_tools.mode_em_advanced


def draw(box, context):
    scene = context.scene
    export_vars = context.window_manager.export_vars

    row = box.row()
    row.prop(scene, "heriverse_export_path", text="Export Path")

    row = box.row()
    row.prop(scene, "heriverse_project_name", text="Project Name")

    row = box.row()
    row.label(text="Only graphs marked as 'Publishable' will be exported", icon='INFO')

    row = box.row()
    col = row.column()
    col.prop(export_vars, "heriverse_overwrite_json", text="Export JSON")
    col = row.column()
    col.prop(export_vars, "heriverse_export_dosco", text="Export DosCo")

    if export_vars.heriverse_overwrite_json and not export_vars.heriverse_export_rm:
        warning_box = box.box()
        warning_box.alert = True
        warning_box.row().label(text="Warning: JSON export without RM export!", icon='ERROR')
        warning_box.row().label(text="Links between RM nodes and models will be missing")
        warning_box.row().label(text="in the JSON if RM Export is not enabled.")

    row = box.row()
    col = row.column()
    col.prop(export_vars, "heriverse_export_proxies", text="Export Proxies")
    col = row.column()
    col.prop(export_vars, "heriverse_export_rm", text="Export RM")
    row = box.row()
    col = row.column()
    col.prop(export_vars, "heriverse_export_rmdoc", text="Export RM Doc")
    col = row.column()
    col.prop(export_vars, "heriverse_export_rmsf", text="Export RM SF")

    row = box.row()
    col = row.column()
    col.prop(export_vars, "heriverse_create_zip", text="Create ZIP")
    col = row.column()
    col.prop(scene, "heriverse_export_panorama", text="Add Panorama")

    # Advanced options
    row = box.row()
    row.prop(
        export_vars, "heriverse_advanced_options",
        text="Advanced Options",
        icon='TRIA_DOWN' if export_vars.heriverse_advanced_options else 'TRIA_RIGHT',
        emboss=False,
    )

    if export_vars.heriverse_advanced_options:
        box_pd = box.box()
        box_pd.row().prop(export_vars, "heriverse_use_draco", text="Use Draco Compression")
        if export_vars.heriverse_use_draco:
            box_pd.row().prop(export_vars, "heriverse_draco_level", text="Compression Level")
        box_pd.row().prop(export_vars, "heriverse_separate_textures", text="Separate Textures")
        box_pd.row().prop(export_vars, "heriverse_use_gpu_instancing", text="Use GPU Instancing")
        box_pd.row().prop(export_vars, "heriverse_export_animations", text="Export Animations")

        if export_vars.heriverse_export_animations:
            box_pd.row().prop(export_vars, "heriverse_export_all_animations", text="All Animations")
            box_pd.row().prop(export_vars, "heriverse_animation_frame_range", text="Frame Range Only")
            box_pd.row().label(text="Note: Exports armatures, bones, and keyframe data", icon='INFO')

        if export_vars.heriverse_separate_textures:
            box_comp = box.box()
            box_comp.row().label(text="Texture Compression:")
            box_comp.row().prop(scene, "heriverse_enable_compression", text="Enable Compression")
            if scene.heriverse_enable_compression:
                row_comp = box_comp.row()
                row_comp.prop(scene, "heriverse_texture_max_res", text="Max Size")
                row_comp.prop(scene, "heriverse_texture_quality", text="Quality")
                box_comp.row().label(text="Quality: 100=lossless, 80=good, 60=compressed, 40=heavily compressed")

        if export_vars.heriverse_export_rmdoc:
            box_pd = box.box()
            box_pd.row().label(text="ParaData Export Options:")
            box_pd.row().prop(scene, "heriverse_preserve_rmdoc_transform", text="Preserve Transforms for each RMDoc")
            box_pd.row().prop(scene, "heriverse_paradata_texture_compression", text="Compress Textures")
            if scene.heriverse_paradata_texture_compression:
                row_pd = box_pd.row()
                row_pd.prop(scene, "heriverse_rmdoc_texture_max_res", text="Max Size")
                row_pd.prop(scene, "heriverse_rmdoc_texture_quality", text="Quality")

        # Cesium tilesets
        box_tileset = box.box()
        box_tileset.row().label(text="Cesium Tileset Options:")
        box_tileset.row().prop(export_vars, "heriverse_skip_extracted_tilesets")

    row = box.row()
    icon_id = icons_manager.get_icon_value("heriverse_logo_tight")
    if icon_id:
        row.operator("export.heriverse", text="Export Heriverse Project", icon_value=icon_id)
    else:
        row.operator("export.heriverse", text="Export Heriverse Project", icon='WORLD_DATA')
