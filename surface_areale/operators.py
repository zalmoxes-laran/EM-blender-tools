"""
Operators for the Surface Areale system.
Main modal operator for drawing contours on RM surfaces via Grease Pencil.

Blender version compatibility:
- Blender 4.3-4.4: GP v3 API via bpy.data.grease_pencils_v3, mode PAINT_GREASE_PENCIL
- Blender 5.0+: GP v3 API via bpy.data.grease_pencils (renamed), mode PAINT_GREASE_PENCIL
"""

import bpy
from bpy.types import Operator


def _get_gp_collection():
    """Get the correct grease pencils data collection for the current Blender version."""
    # Blender 5.0+ renamed grease_pencils_v3 back to grease_pencils
    if hasattr(bpy.data, 'grease_pencils'):
        return bpy.data.grease_pencils
    elif hasattr(bpy.data, 'grease_pencils_v3'):
        return bpy.data.grease_pencils_v3
    else:
        raise RuntimeError("Grease Pencil API not found. Requires Blender 4.3+")


def _get_gp_paint_mode():
    """Get the correct GP paint mode name for the current Blender version."""
    # Blender 4.3+ uses PAINT_GREASE_PENCIL for the new GP v3 objects
    return 'PAINT_GREASE_PENCIL'


class EMTOOLS_OT_draw_surface_areale(Operator):
    """Draw a surface areale on a Representation Model"""
    bl_idname = "emtools.draw_surface_areale"
    bl_label = "Draw Surface Areale"
    bl_description = "Enter drawing mode to create a surface areale proxy on the selected RM"
    bl_options = {'REGISTER', 'UNDO'}

    _gp_obj = None

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        settings = em_tools.surface_areale
        has_graph = em_tools.active_file_index >= 0
        return (
            has_graph and
            settings.target_rm is not None and
            settings.target_rm.type == 'MESH' and
            not settings.is_drawing
        )

    def invoke(self, context, event):
        settings = context.scene.em_tools.surface_areale

        # Validate target RM
        rm_obj = settings.target_rm
        if not rm_obj or rm_obj.type != 'MESH':
            self.report({'ERROR'}, "Select a valid mesh as Target RM")
            return {'CANCELLED'}

        # Create temporary Grease Pencil object
        try:
            self._gp_obj = self._create_temp_gp(context, rm_obj)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create Grease Pencil: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        # Configure surface snap
        self._setup_surface_drawing(context, rm_obj)

        # Update state
        settings.is_drawing = True
        settings.drawing_phase = 'CONTOUR'

        # Select the GP object and enter draw mode
        bpy.ops.object.select_all(action='DESELECT')
        self._gp_obj.select_set(True)
        context.view_layer.objects.active = self._gp_obj

        try:
            bpy.ops.object.mode_set(mode=_get_gp_paint_mode())
        except Exception:
            # Fallback: try legacy mode name
            try:
                bpy.ops.object.mode_set(mode='PAINT_GPENCIL')
            except Exception as e:
                self.report({'ERROR'}, f"Cannot enter GP paint mode: {e}")
                self._remove_temp_gp(context)
                settings.is_drawing = False
                return {'CANCELLED'}

        # Set up modal
        context.window_manager.modal_handler_add(self)

        # Header info
        context.area.header_text_set(
            "Surface Areale: Draw CONTOUR strokes. "
            "[B] Switch to Whisker | [Enter] Confirm | [Esc] Cancel"
        )

        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        settings = context.scene.em_tools.surface_areale

        if event.type == 'B' and event.value == 'PRESS':
            if settings.drawing_phase == 'CONTOUR':
                settings.drawing_phase = 'WHISKER'
                context.area.header_text_set(
                    "Surface Areale: Draw WHISKER (short stroke inside the area). "
                    "[Enter] Confirm | [Esc] Cancel"
                )
                return {'RUNNING_MODAL'}

        elif event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            return self._finalize(context)

        elif event.type == 'ESC' and event.value == 'PRESS':
            return self._cancel(context)

        return {'PASS_THROUGH'}

    def _finalize(self, context):
        """Process the GP strokes and create the areale mesh."""
        settings = context.scene.em_tools.surface_areale

        # Exit paint mode
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        try:
            from .contour_builder import (
                extract_gp_strokes, identify_whisker,
                concatenate_strokes, close_contour,
                resample_contour, reproject_on_surface,
                create_bvh_from_object
            )
            from .strategies import strategy_projective
            from .postprocess import (
                apply_normal_offset, decimate_preserving_boundary,
                assign_em_material, link_areale_to_graph
            )

            rm_obj = settings.target_rm

            # ── Extract GP strokes ────────────────────────────────────
            strokes = extract_gp_strokes(self._gp_obj)
            if len(strokes) < 2:
                self.report({'ERROR'},
                            "Need at least 2 strokes: contour stroke(s) + whisker")
                return self._cancel(context)

            # ── Separate contour and whisker ──────────────────────────
            contour_strokes, whisker_point = identify_whisker(strokes)

            # ── Build contour ─────────────────────────────────────────
            contour = concatenate_strokes(contour_strokes)
            contour = close_contour(contour)

            # ── Resample ──────────────────────────────────────────────
            contour = resample_contour(contour, settings.resample_distance)

            if len(contour) < 3:
                self.report({'ERROR'}, "Contour too small after resampling")
                return self._cancel(context)

            # ── Build BVH and reproject ───────────────────────────────
            bvh_tree = create_bvh_from_object(rm_obj)

            projected = reproject_on_surface(contour, bvh_tree)
            contour_points = [p[0] for p in projected]
            contour_normals = [p[1] for p in projected]

            # Reproject whisker point
            wh_loc, wh_normal, _, _ = bvh_tree.find_nearest(whisker_point)
            if wh_loc:
                whisker_point = wh_loc

            # ── Generate areale mesh ──────────────────────────────────
            self.report({'INFO'}, "Generating surface areale...")

            areale_obj = strategy_projective(
                contour_points, contour_normals, whisker_point,
                rm_obj, bvh_tree, settings
            )

            # ── Post-processing ───────────────────────────────────────
            context.collection.objects.link(areale_obj)

            decimate_preserving_boundary(
                areale_obj, settings.max_triangles,
                settings.conformity_threshold, bvh_tree
            )

            apply_normal_offset(areale_obj, bvh_tree, settings.offset_distance)

            alpha = getattr(context.scene.em_tools, 'proxy_display_alpha', 0.5)
            assign_em_material(areale_obj, settings.us_type, alpha)

            # Graph linking
            if settings.us_type != 'GENERIC':
                try:
                    us_node, msg = link_areale_to_graph(
                        context, areale_obj, rm_obj, settings
                    )
                    self.report({'INFO'}, msg)
                except Exception as e:
                    self.report({'WARNING'}, f"Graph linking failed: {e}")

            # ── Cleanup ───────────────────────────────────────────────
            self._remove_temp_gp(context)

            bpy.ops.object.select_all(action='DESELECT')
            areale_obj.select_set(True)
            context.view_layer.objects.active = areale_obj

            settings.is_drawing = False
            settings.drawing_phase = 'IDLE'
            context.area.header_text_set(None)

            self.report({'INFO'}, f"Surface areale created: {areale_obj.name}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to create areale: {e}")
            import traceback
            traceback.print_exc()
            return self._cancel(context)

    def _cancel(self, context):
        """Cancel the drawing and clean up."""
        settings = context.scene.em_tools.surface_areale

        if context.mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass

        self._remove_temp_gp(context)

        settings.is_drawing = False
        settings.drawing_phase = 'IDLE'
        context.area.header_text_set(None)

        self.report({'INFO'}, "Surface areale drawing cancelled")
        return {'CANCELLED'}

    def _create_temp_gp(self, context, rm_obj):
        """Create a temporary Grease Pencil object for drawing with visible stroke."""
        settings = context.scene.em_tools.surface_areale

        gp_collection = _get_gp_collection()
        gp_data = gp_collection.new("_EM_TempArealeGP")
        gp_obj = bpy.data.objects.new("_EM_TempArealeGP", gp_data)

        context.collection.objects.link(gp_obj)

        # Create a layer and initial frame
        layer = gp_data.layers.new("Areale")
        layer.frames.new(context.scene.frame_current)

        # Apply bright color and thickness from preferences
        color = settings.gp_stroke_color
        thickness = settings.gp_stroke_thickness

        # Set layer color (GP v3 uses layer.color)
        try:
            layer.color = (*color, 1.0)
        except (AttributeError, TypeError):
            try:
                layer.color = color[:3]
            except Exception:
                pass

        # Create a material with the bright color for the GP strokes
        mat_name = "_EM_ArealeStroke"
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = False
        # GP material settings
        try:
            mat.grease_pencil.color = (*color, 1.0)
            mat.grease_pencil.show_stroke = True
            mat.grease_pencil.mode = 'LINE'
        except AttributeError:
            # GP v3 material handling differs
            pass

        # Assign material to GP object
        if gp_data.materials:
            gp_data.materials[0] = mat
        else:
            gp_data.materials.append(mat)

        # Set line thickness on the GP object
        try:
            gp_data.pixel_factor = 1.0
            layer.line_change = thickness
        except AttributeError:
            pass

        return gp_obj

    def _setup_surface_drawing(self, context, rm_obj):
        """Configure GP surface drawing mode snapping to the RM."""
        ts = context.scene.tool_settings

        # Set stroke placement to surface — property name varies by version
        try:
            ts.gpencil_stroke_placement_view3d = 'SURFACE'
        except AttributeError:
            pass

        try:
            ts.use_gpencil_draw_onback = False
        except AttributeError:
            pass

    def _remove_temp_gp(self, context):
        """Remove the temporary GP object and data."""
        if self._gp_obj:
            gp_data = self._gp_obj.data

            for collection in self._gp_obj.users_collection:
                collection.objects.unlink(self._gp_obj)
            bpy.data.objects.remove(self._gp_obj, do_unlink=True)

            if gp_data and gp_data.users == 0:
                gp_collection = _get_gp_collection()
                gp_collection.remove(gp_data)

            self._gp_obj = None


class EMTOOLS_OT_confirm_areale(Operator):
    """Confirm and process the drawn surface areale"""
    bl_idname = "emtools.confirm_areale"
    bl_label = "Confirm Areale"
    bl_description = "Process the drawn contour and create the surface areale mesh"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = context.scene.em_tools.surface_areale
        return settings.is_drawing

    def execute(self, context):
        self.report({'WARNING'}, "Use Enter key to confirm in drawing mode")
        return {'CANCELLED'}


def _get_next_numbered_name(graph, prefix, node_type_filter=None):
    """
    Find the next available numbered name in the graph.
    Scans nodes for names like '{prefix}.1', '{prefix}.2', etc.
    and returns the next free number.

    Args:
        graph: s3dgraphy graph
        prefix: Name prefix (e.g. 'D', 'US', 'UL')
        node_type_filter: Optional node_type to filter by

    Returns:
        String like '{prefix}.{next_number}'
    """
    max_num = 0
    for node in graph.nodes:
        if not hasattr(node, 'name') or not isinstance(node.name, str):
            continue
        if node_type_filter and hasattr(node, 'node_type'):
            if node.node_type != node_type_filter:
                continue
        name = node.name
        if name.startswith(f'{prefix}.'):
            try:
                num = int(name.split('.', 1)[1])
                max_num = max(max_num, num)
            except (ValueError, IndexError):
                continue
    return f"{prefix}.{max_num + 1}"


class EMTOOLS_OT_suggest_next_doc(Operator):
    """Suggest the next available document number"""
    bl_idname = "emtools.suggest_next_doc"
    bl_label = "Next Doc Number"
    bl_description = "Fill in the next available document number (e.g. D.15)"

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        return em_tools.active_file_index >= 0

    def execute(self, context):
        from s3dgraphy import get_graph

        em_tools = context.scene.em_tools
        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)

        if not graph:
            self.report({'ERROR'}, "Graph not loaded")
            return {'CANCELLED'}

        next_name = _get_next_numbered_name(graph, 'D', node_type_filter='document')
        em_tools.surface_areale.new_doc_name = next_name
        self.report({'INFO'}, f"Next document: {next_name}")
        return {'FINISHED'}


class EMTOOLS_OT_suggest_next_us(Operator):
    """Suggest the next available US number based on the selected type"""
    bl_idname = "emtools.suggest_next_us"
    bl_label = "Next US Number"
    bl_description = "Fill in the next available US number for the selected type"

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        return em_tools.active_file_index >= 0

    def execute(self, context):
        from s3dgraphy import get_graph

        em_tools = context.scene.em_tools
        settings = em_tools.surface_areale
        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)

        if not graph:
            self.report({'ERROR'}, "Graph not loaded")
            return {'CANCELLED'}

        # Map US type to prefix and node_type filter
        type_to_prefix = {
            'UL': 'UL',
            'TSU': 'TSU',
            'US_NEG': 'USN',
            'US': 'US',
        }

        type_to_node_type = {
            'UL': 'UL',
            'TSU': 'TSU',
            'US_NEG': 'US',
            'US': 'US',
        }

        prefix = type_to_prefix.get(settings.us_type, 'US')
        node_filter = type_to_node_type.get(settings.us_type)

        next_name = _get_next_numbered_name(graph, prefix, node_type_filter=node_filter)
        settings.new_us_name = next_name
        self.report({'INFO'}, f"Next US: {next_name}")
        return {'FINISHED'}


class EMTOOLS_OT_detect_rm_document(Operator):
    """Detect if the selected RM has a linked document in the graph"""
    bl_idname = "emtools.detect_rm_document"
    bl_label = "Detect Document"
    bl_description = "Check if the Target RM has a document linked in the graph"

    @classmethod
    def poll(cls, context):
        settings = context.scene.em_tools.surface_areale
        em_tools = context.scene.em_tools
        return (
            settings.target_rm is not None and
            em_tools.active_file_index >= 0
        )

    def execute(self, context):
        from s3dgraphy import get_graph
        from .postprocess import _find_rm_document

        em_tools = context.scene.em_tools
        settings = em_tools.surface_areale
        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)

        if not graph:
            self.report({'ERROR'}, "Graph not loaded")
            return {'CANCELLED'}

        doc_node = _find_rm_document(graph, settings.target_rm)
        if doc_node:
            settings.linked_document = doc_node.name
            self.report({'INFO'}, f"Found document: {doc_node.name}")
        else:
            settings.linked_document = ""
            self.report({'INFO'}, "No document linked to this RM")

        return {'FINISHED'}


classes = [
    EMTOOLS_OT_draw_surface_areale,
    EMTOOLS_OT_confirm_areale,
    EMTOOLS_OT_suggest_next_doc,
    EMTOOLS_OT_suggest_next_us,
    EMTOOLS_OT_detect_rm_document,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
