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
import re

from . import render_utils
from . import graph_bridge
from . import network_client


def generate_job_name(context, tapestry):
    """
    Generate job name: {timestamp}_{filename_7chars}_{epoch}_{camera}

    Args:
        context: Blender context
        tapestry: TapestryManagerProps instance

    Returns:
        str: Generated job name (e.g., "20251228_EMdatas_Phase1_Cam01")
    """
    parts = []

    # 1. Timestamp (YYYYMMDD format)
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d")
    parts.append(timestamp)

    # 2. Filename (first 7 characters, without .blend extension)
    blend_file = bpy.path.basename(bpy.data.filepath)
    if blend_file:
        # Remove .blend extension and sanitize
        filename = blend_file.replace('.blend', '')
        filename = re.sub(r'[^\w\-]', '_', filename)  # Replace non-alphanumeric with _
        # Take first 7 characters
        filename_short = filename[:7]
        parts.append(filename_short)
    else:
        parts.append("untitle")

    # 3. Epoch (if EM mode and epoch filtering active)
    scene = context.scene
    if hasattr(scene, 'em_tools') and scene.em_tools.mode_em_advanced:
        if scene.filter_by_epoch:
            epochs = scene.em_tools.epochs
            if epochs.list and epochs.list_index >= 0:
                epoch = epochs.list[epochs.list_index]
                epoch_name = re.sub(r'[^\w\-]', '_', epoch.name)
                parts.append(epoch_name)

    # 4. Camera name
    if tapestry.render_camera:
        camera_name = re.sub(r'[^\w\-]', '_', tapestry.render_camera.name)
        parts.append(camera_name)
    else:
        parts.append("nocam")

    # Join with underscores
    job_name = "_".join(parts)

    return job_name


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
                epoch_filter = epochs.list[epochs.list_index].name

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


class TAPESTRY_OT_generate_job_name(Operator):
    """Generate job name from filename_epoch_camera_###"""
    bl_idname = "tapestry.generate_job_name"
    bl_label = "Generate Job Name"
    bl_description = "Auto-generate job name from current settings"

    def execute(self, context):
        tapestry = context.scene.em_tools.tapestry

        # Generate job name
        job_name = generate_job_name(context, tapestry)

        # Set in property
        tapestry.job_name = job_name

        self.report({'INFO'}, f"Job name: {job_name}")

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
                camera=tapestry.render_camera,
                export_normals=tapestry.export_normals
            )

            self.report({'INFO'}, "Render setup complete")

        except Exception as e:
            self.report({'ERROR'}, f"Setup failed: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class TAPESTRY_OT_setup_epoch_filter(Operator):
    """Setup epoch filtering for Tapestry render"""
    bl_idname = "tapestry.setup_epoch_filter"
    bl_label = "Setup Epoch Filter"
    bl_description = "Configure epoch filtering by hiding RMs and enabling stratigraphy filter"

    def execute(self, context):
        scene = context.scene
        em_tools = scene.em_tools

        # Verify we're in EM mode
        if not em_tools.mode_em_advanced:
            self.report({'WARNING'}, "Epoch filtering only available in EM Advanced mode")
            return {'CANCELLED'}

        # Verify epoch is selected
        epochs = em_tools.epochs
        if not epochs.list or epochs.list_index < 0:
            self.report({'ERROR'}, "No epoch selected. Select an epoch from the Epoch Manager first")
            return {'CANCELLED'}

        try:
            # Step 1: Hide all RMs
            bpy.ops.em.strat_hide_all_rms()
            self.report({'INFO'}, "Hidden all RMs")

            # Step 2: Disable RM visibility sync
            scene.sync_rm_visibility = False
            self.report({'INFO'}, "Disabled RM visibility sync")

            # Step 3: Enable epoch filtering
            scene.filter_by_epoch = True

            active_epoch = epochs.list[epochs.list_index].name
            self.report({'INFO'}, f"Epoch filter enabled: {active_epoch}")

        except Exception as e:
            self.report({'ERROR'}, f"Epoch filter setup failed: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}


class TAPESTRY_OT_disable_epoch_filter(Operator):
    """Disable epoch filtering and restore normal visibility"""
    bl_idname = "tapestry.disable_epoch_filter"
    bl_label = "Disable Epoch Filter"
    bl_description = "Disable epoch filtering and restore RM visibility sync"

    def execute(self, context):
        scene = context.scene

        try:
            # Disable epoch filtering
            scene.filter_by_epoch = False

            # Re-enable RM visibility sync
            scene.sync_rm_visibility = True

            self.report({'INFO'}, "Epoch filter disabled, RM sync restored")

        except Exception as e:
            self.report({'ERROR'}, f"Failed to disable epoch filter: {str(e)}")
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

        # SAVE render settings before modifying
        saved_settings = render_utils.save_render_settings(scene)
        self.report({'INFO'}, "Saved render settings (will restore after export)")

        try:
            # Generate job name if not set
            if not tapestry.job_name:
                job_name = generate_job_name(context, tapestry)
                tapestry.job_name = job_name
                self.report({'INFO'}, f"Auto-generated job name: {job_name}")
            else:
                job_name = tapestry.job_name

            # Setup render (includes camera configuration)
            bpy.ops.tapestry.setup_render()

            # Determine output path
            output_dir = Path(bpy.path.abspath("//")) / "tapestry_export"
            output_dir.mkdir(exist_ok=True, parents=True)

            # Use job name as directory name (job_id)
            job_id = job_name

            job_dir = output_dir / job_id
            job_dir.mkdir(exist_ok=True)

            # Store export path in property for UI display
            tapestry.last_export_path = str(job_dir)

            # Render EXR
            self.report({'INFO'}, f"Rendering to: {job_dir}")

            exr_path = job_dir / "render.exr"
            scene.render.filepath = str(exr_path)

            # Render
            bpy.ops.render.render(write_still=True)

            self.report({'INFO'}, f"Render complete: {exr_path}")

            # Prepare EXR for Tapestry (new EXR-only pipeline)
            self.report({'INFO'}, "Preparing EXR for Tapestry...")

            render_data = render_utils.prepare_exr_for_tapestry(
                exr_path,
                job_dir
            )

            # Generate Tapestry JSON (legacy format, will be deprecated)
            self.report({'INFO'}, "Generating Tapestry JSON...")

            json_data = graph_bridge.generate_tapestry_json(
                context,
                job_id,
                render_data,
                tapestry
            )

            # Save Tapestry JSON
            json_path = job_dir / "tapestry_input.json"
            with open(json_path, 'w') as f:
                json.dump(json_data, f, indent=2)

            # Generate semantic JSON from graph
            self.report({'INFO'}, "Generating semantic JSON from EM graph...")

            semantic_json = graph_bridge.extract_semantic_json_from_graph(
                context,
                tapestry.visible_proxies,
                tapestry.render_camera
            )

            # Set job_id in semantic JSON
            semantic_json["scene"]["job_id"] = job_id

            # Save semantic JSON
            semantic_path = job_dir / "semantic.json"
            with open(semantic_path, 'w') as f:
                json.dump(semantic_json, f, indent=2)

            self.report({'INFO'}, f"Export complete: {json_path}, {semantic_path}")
            print(f"\nTAPESTRY EXPORT PATH: {job_dir}")
            print(f"  - EXR: {exr_path}")
            print(f"  - JSON: {json_path}")
            print(f"  - Semantic JSON: {semantic_path}\n")

            # Auto-submit if enabled
            if tapestry.auto_submit:
                self.report({'INFO'}, "Submitting to Tapestry server...")

                # Prepare upload data with EXR + semantic JSON
                upload_data = {
                    'job_id': job_id,
                    'input': {
                        'exr': str(exr_path),
                        'semantic_json': str(semantic_path),
                        'rgb_preview': render_data.get('rgb_preview')
                    },
                    'generation_params': json_data.get('generation_params', {}),
                    'metadata': semantic_json.get('metadata', {})
                }

                success, message = network_client.submit_job(
                    tapestry.server_address,
                    tapestry.server_port,
                    upload_data
                )

                if success:
                    self.report({'INFO'}, f"Job submitted: {message}")
                else:
                    self.report({'WARNING'}, f"Submission failed: {message}")

            # Cleanup if needed
            if not tapestry.keep_intermediate:
                os.remove(exr_path)
                self.report({'INFO'}, "Removed intermediate EXR file")

        except Exception as e:
            self.report({'ERROR'}, f"Render failed: {str(e)}")
            import traceback
            traceback.print_exc()
            # RESTORE settings even on error
            render_utils.restore_render_settings(scene, saved_settings)
            return {'CANCELLED'}

        finally:
            # ALWAYS restore render settings
            render_utils.restore_render_settings(scene, saved_settings)

        return {'FINISHED'}


# Registration
class TAPESTRY_OT_open_web_ui(Operator):
    """Open Tapestry Web UI in browser"""
    bl_idname = "tapestry.open_web_ui"
    bl_label = "Open Tapestry Web UI"
    bl_description = "Open Tapestry Web UI in your default browser to monitor jobs and download results"

    def execute(self, context):
        import webbrowser

        tapestry = context.scene.em_tools.tapestry

        # Build URL from server settings
        url = f"http://{tapestry.server_address}:{tapestry.server_port}"

        # Open in browser
        try:
            webbrowser.open(url)
            self.report({'INFO'}, f"Opening {url} in browser")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Cannot open browser: {e}")
            return {'CANCELLED'}


classes = (
    TAPESTRY_OT_test_connection,
    TAPESTRY_OT_analyze_camera_view,
    TAPESTRY_OT_generate_job_name,
    TAPESTRY_OT_setup_render,
    TAPESTRY_OT_setup_epoch_filter,
    TAPESTRY_OT_disable_epoch_filter,
    TAPESTRY_OT_render_for_tapestry,
    TAPESTRY_OT_open_web_ui,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
