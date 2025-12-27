"""
UI Panel for Tapestry Integration

Provides user interface in EM Bridge tab for:
- Network configuration
- Render settings
- Camera and proxy selection
- Preview and queue management
"""

import bpy
from bpy.types import Panel


class TAPESTRY_PT_main_panel(Panel):
    """Main Tapestry panel in EM Bridge tab"""
    bl_label = "Tapestry"
    bl_idname = "TAPESTRY_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM Bridge'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        """Show only when experimental features enabled"""
        return context.scene.em_tools.experimental_features

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        tapestry = scene.em_tools.tapestry

        # Header with logo/icon
        box = layout.box()
        row = box.row()
        row.label(text="AI-Powered Photorealistic Reconstruction", icon='IMAGE_DATA')

        # Network Settings (collapsible)
        self.draw_network_section(layout, tapestry)

        # Render Settings
        self.draw_render_settings(layout, tapestry, scene)

        # Preview & Analysis
        self.draw_preview_section(layout, tapestry, context)

        # Advanced Settings (collapsible)
        self.draw_advanced_section(layout, tapestry)

    def draw_network_section(self, layout, tapestry):
        """Draw network configuration section"""
        box = layout.box()
        row = box.row()
        row.prop(
            tapestry,
            "network_expanded",
            text="Tapestry Connection",
            icon='TRIA_DOWN' if tapestry.network_expanded else 'TRIA_RIGHT',
            emboss=False
        )

        if tapestry.network_expanded:
            # Server address and port
            row = box.row()
            col = row.column()
            col.prop(tapestry, "server_address", text="Server")
            col = row.column()
            col.prop(tapestry, "server_port", text="Port")

            # Connection status
            row = box.row()
            if tapestry.connection_status:
                row.label(text="Status: Connected", icon='LINKED')
            else:
                row.label(text="Status: Disconnected", icon='UNLINKED')

            row.operator("tapestry.test_connection", text="Test Connection", icon='PLUGIN')

            # Future: Authentication
            row = box.row()
            row.label(text="Future: Keycloak Authentication", icon='INFO')

    def draw_render_settings(self, layout, tapestry, scene):
        """Draw render configuration section"""
        box = layout.box()
        box.label(text="Render Settings", icon='CAMERA_DATA')

        # Camera selection
        row = box.row()
        row.prop(tapestry, "render_camera", text="Camera")

        # Resolution
        row = box.row()
        col = row.column()
        col.prop(tapestry, "render_resolution_x", text="Width")
        col = row.column()
        col.prop(tapestry, "render_resolution_y", text="Height")

        # Visibility filter
        row = box.row()
        row.prop(tapestry, "use_visible_only", text="Use Only Visible Proxies")

        # Epoch filter (only in EM mode)
        if scene.em_tools.mode_em_advanced:
            row = box.row()
            row.prop(tapestry, "epoch_filter", text="Epoch")
            row.label(text="", icon='TIME')

    def draw_preview_section(self, layout, tapestry, context):
        """Draw preview and queue management section"""
        box = layout.box()

        # Header with proxy count
        row = box.row()
        row.label(text=f"Visible Proxies: {tapestry.visible_proxies_count} objects", icon='OUTLINER_OB_GROUP_INSTANCE')

        # Analysis button
        row = box.row()
        row.scale_y = 1.3
        row.operator("tapestry.analyze_camera_view", text="Analyze Camera View", icon='VIEWZOOM')

        # Proxies list (if analyzed)
        if tapestry.visible_proxies_count > 0:
            box.separator()

            # List header
            row = box.row()
            row.label(text="Object")
            row.label(text="Visibility")

            # Show first 5 proxies
            for i, proxy in enumerate(tapestry.visible_proxies[:5]):
                row = box.row()
                row.label(text=f"  {proxy.us_id} ({proxy.object_name})")
                row.label(text=f"{proxy.visibility_percent:.1f}%")

            # Show "and N more" if > 5
            if tapestry.visible_proxies_count > 5:
                row = box.row()
                row.label(text=f"  ... and {tapestry.visible_proxies_count - 5} more", icon='THREE_DOTS')

            box.separator()

            # Render and submit buttons
            row = box.row(align=True)
            row.scale_y = 1.5

            # Render button
            render_op = row.operator("tapestry.render_for_tapestry", text="Render for Tapestry", icon='RENDER_STILL')

            # Submit toggle
            row = box.row()
            row.prop(tapestry, "auto_submit", text="Auto-submit to Server")

    def draw_advanced_section(self, layout, tapestry):
        """Draw advanced settings section"""
        box = layout.box()
        row = box.row()
        row.prop(
            tapestry,
            "advanced_expanded",
            text="Advanced Settings",
            icon='TRIA_DOWN' if tapestry.advanced_expanded else 'TRIA_RIGHT',
            emboss=False
        )

        if tapestry.advanced_expanded:
            # Render engine
            row = box.row()
            row.prop(tapestry, "render_engine", text="Engine")

            row = box.row()
            row.prop(tapestry, "render_samples", text="Samples")

            # Pass options
            row = box.row()
            row.prop(tapestry, "export_normals", text="Export Normals")

            row = box.row()
            row.prop(tapestry, "export_ao", text="Export AO")

            # File management
            row = box.row()
            row.prop(tapestry, "keep_intermediate", text="Keep Intermediate Files")

            box.separator()

            # Generation parameters
            box.label(text="AI Generation Parameters", icon='SHADERFX')

            row = box.row()
            row.prop(tapestry, "model_name", text="Model")

            row = box.row()
            row.prop(tapestry, "generation_steps", text="Steps")

            row = box.row()
            row.prop(tapestry, "cfg_scale", text="CFG Scale")

            row = box.row()
            row.prop(tapestry, "denoise_strength", text="Denoise Strength")


def register():
    bpy.utils.register_class(TAPESTRY_PT_main_panel)


def unregister():
    bpy.utils.unregister_class(TAPESTRY_PT_main_panel)
