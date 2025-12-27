"""
Operators for Tapestry Integration

Implements:
- Test connection to Tapestry server
- Analyze camera view for visible proxies
- Setup render for EXR multilayer
- Render and export to Tapestry
"""

import bpy
from bpy.types import Operator
import json
import os
from pathlib import Path

from . import render_utils
from . import graph_bridge
from . import network_client


class TAPESTRY_OT_test_connection(Operator):
    """Test connection to Tapestry server"""
    bl_idname = "tapestry.test_connection"
    bl_label = "Test Connection"
    bl_description = "Test connection to Tapestry server"

    def execute(self, context):
        tapestry = context.scene.em_tools.tapestry

        # Test connection
        success, message = network_client.test_connection(
            tapestry.server_address,
            tapestry.server_port
        )

        tapestry.connection_status = success

        if success:
            self.report({'INFO'}, f"Connected to Tapestry: {message}")
        else:
            self.report({'ERROR'}, f"Connection failed: {message}")

        return {'FINISHED'}


class TAPESTRY_OT_analyze_camera_view(Operator):
    """Analyze camera view to identify visible proxies"""
    bl_idname = "tapestry.analyze_camera_view"
    bl_label = "Analyze Camera View"
    bl_description = "Identify proxies visible in selected camera"

    def execute(self, context):
        tapestry = context.scene.em_tools.tapestry
        scene = context.scene

        # Check camera is set
        if not tapestry.render_camera:
            self.report({'ERROR'}, "No camera selected")
            return {'CANCELLED'}

        # Clear previous results
        tapestry.visible_proxies.clear()

        # Get camera
        camera = tapestry.render_camera

        # Get epoch filter (if EM mode)
        epoch_filter = None
        if scene.em_tools.mode_em_advanced:
            # Use active epoch from epoch manager
            epochs = scene.em_tools.epochs
            if epochs.list and epochs.list_index >= 0:
                epoch_filter = epochs.list[epochs.list_index].epoch

        # Analyze visible proxies
        try:
            visible_proxies = graph_bridge.get_visible_proxies(
                context,
                camera,
                use_frustum_culling=tapestry.use_visible_only,
                epoch_filter=epoch_filter
            )

            # Add to property collection
            for proxy_data in visible_proxies:
                proxy_item = tapestry.visible_proxies.add()
                proxy_item.us_id = proxy_data['us_id']
                proxy_item.object_name = proxy_data['object_name']
                proxy_item.visibility_percent = proxy_data['visibility_percent']
                proxy_item.in_queue = True

            tapestry.visible_proxies_count = len(visible_proxies)

            self.report({'INFO'}, f"Found {len(visible_proxies)} visible proxies")

        except Exception as e:
            self.report({'ERROR'}, f"Analysis failed: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class TAPESTRY_OT_setup_render(Operator):
    """Setup render settings for Tapestry export"""
    bl_idname = "tapestry.setup_render"
    bl_label = "Setup Render"
    bl_description = "Configure scene for EXR multilayer rendering"

    def execute(self, context):
        tapestry = context.scene.em_tools.tapestry
        scene = context.scene

        try:
            render_utils.setup_exr_render(
                scene,
                tapestry.render_resolution_x,
                tapestry.render_resolution_y,
                tapestry.render_samples,
                export_normals=tapestry.export_normals
            )

            self.report({'INFO'}, "Render setup complete")

        except Exception as e:
            self.report({'ERROR'}, f"Setup failed: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class TAPESTRY_OT_render_for_tapestry(Operator):
    """Render scene and export for Tapestry"""
    bl_idname = "tapestry.render_for_tapestry"
    bl_label = "Render for Tapestry"
    bl_description = "Render EXR multilayer and prepare Tapestry export"

    def execute(self, context):
        tapestry = context.scene.em_tools.tapestry
        scene = context.scene

        # Validate
        if not tapestry.render_camera:
            self.report({'ERROR'}, "No camera selected")
            return {'CANCELLED'}

        if tapestry.visible_proxies_count == 0:
            self.report({'ERROR'}, "No visible proxies. Run 'Analyze Camera View' first")
            return {'CANCELLED'}

        # Setup render
        bpy.ops.tapestry.setup_render()

        # Set camera
        scene.camera = tapestry.render_camera

        # Determine output path
        output_dir = Path(bpy.path.abspath("//")) / "tapestry_export"
        output_dir.mkdir(exist_ok=True, parents=True)

        # Generate unique job ID
        import time
        job_id = f"blender_{int(time.time())}"

        job_dir = output_dir / job_id
        job_dir.mkdir(exist_ok=True)

        # Render EXR
        self.report({'INFO'}, "Rendering EXR multilayer...")

        exr_path = job_dir / "render.exr"
        scene.render.filepath = str(exr_path)

        try:
            # Render
            bpy.ops.render.render(write_still=True)

            self.report({'INFO'}, f"Render complete: {exr_path}")

            # Extract passes
            self.report({'INFO'}, "Extracting passes and masks...")

            render_data = render_utils.extract_exr_passes(
                exr_path,
                job_dir,
                tapestry.visible_proxies
            )

            # Generate JSON
            self.report({'INFO'}, "Generating Tapestry JSON...")

            json_data = graph_bridge.generate_tapestry_json(
                context,
                job_id,
                render_data,
                tapestry
            )

            # Save JSON
            json_path = job_dir / "tapestry_input.json"
            with open(json_path, 'w') as f:
                json.dump(json_data, f, indent=2)

            self.report({'INFO'}, f"Export complete: {json_path}")

            # Auto-submit if enabled
            if tapestry.auto_submit:
                self.report({'INFO'}, "Submitting to Tapestry server...")

                success, message = network_client.submit_job(
                    tapestry.server_address,
                    tapestry.server_port,
                    json_data
                )

                if success:
                    self.report({'INFO'}, f"Job submitted: {message}")
                else:
                    self.report({'WARNING'}, f"Submission failed: {message}")

            # Cleanup if needed
            if not tapestry.keep_intermediate:
                os.remove(exr_path)

        except Exception as e:
            self.report({'ERROR'}, f"Render failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        return {'FINISHED'}


# Registration
classes = (
    TAPESTRY_OT_test_connection,
    TAPESTRY_OT_analyze_camera_view,
    TAPESTRY_OT_setup_render,
    TAPESTRY_OT_render_for_tapestry,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
