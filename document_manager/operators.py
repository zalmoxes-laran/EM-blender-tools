"""Operators for the 3D Document Manager.

Provides:
- Sync doc list from paradata sources
- Import image and create textured quad
- Create camera at current viewport position
- Look through document camera
- Open URL / Select scene object
- Filter toggles
"""

import os
import math

import bpy
from bpy.props import StringProperty, FloatProperty, EnumProperty, IntProperty, BoolProperty  # type: ignore

from .data import sync_doc_list
from .validators import check_rmdoc_item, disable_pilot


def _find_rmdoc_item_by_name(scene, object_name):
    """Trova un RMDocItem per nome del quad. Ritorna (item, index) o (None, -1)."""
    if not hasattr(scene, 'rmdoc_list'):
        return None, -1
    for i, item in enumerate(scene.rmdoc_list):
        if item.name == object_name:
            return item, i
    return None, -1


def _get_active_doc_item(context):
    """Return the active DocItem from scene.doc_list, or None."""
    scene = context.scene
    idx = scene.doc_list_index
    if 0 <= idx < len(scene.doc_list):
        return scene.doc_list[idx]
    return None


def _resolve_doc_image_path(context, item):
    """Resolve the image file path for a document item using DOSCO logic.

    Returns absolute path string, or None if not resolvable.
    """
    from ..em_setup.resource_utils import resolve_dosco_dir

    if not item.url:
        return None

    em_tools = context.scene.em_tools
    if em_tools.active_file_index < 0 or not em_tools.graphml_files:
        return None

    graphml = em_tools.graphml_files[em_tools.active_file_index]
    dosco_dir = resolve_dosco_dir(graphml)
    if not dosco_dir:
        return None

    # Try several path variants (same logic as build_file_path)
    path = item.url
    path_variants = [
        path,
        path.split("/")[-1],
        os.path.basename(path),
    ]
    graph_code = getattr(graphml, 'graph_code', None)
    if graph_code:
        path_variants.append(f"{graph_code}.{path}")
        path_variants.append(path.replace(f"{graph_code}.", ""))

    for variant in path_variants:
        variant_path = variant.lstrip(os.path.sep)
        full_path = os.path.join(dosco_dir, variant_path)
        if os.path.exists(full_path):
            return os.path.normpath(full_path)

    return None


# ============================================================================
# SYNC
# ============================================================================

class DOCMANAGER_OT_sync(bpy.types.Operator):
    """Synchronize document list from graph data"""
    bl_idname = "em.docmanager_sync"
    bl_label = "Sync Documents"
    bl_description = "Rebuild the document catalog from the active GraphML and scan the scene for linked quads"
    bl_options = {'REGISTER'}

    def execute(self, context):
        # Invalidate UI caches before sync so counts are rebuilt fresh
        from .ui import invalidate_doc_connection_cache
        invalidate_doc_connection_cache()

        sync_doc_list(context.scene)

        # Diagnostic: print edge type distribution for document connections
        try:
            from s3dgraphy import get_graph
            em_tools = context.scene.em_tools
            if em_tools.active_file_index >= 0:
                graph_info = em_tools.graphml_files[em_tools.active_file_index]
                graph = get_graph(graph_info.name)
                if graph:
                    # Collect all document node IDs
                    doc_ids = {item.node_id for item in context.scene.doc_list if item.node_id}
                    # Count edge types involving documents
                    edge_stats = {}
                    doc_counts = {}
                    for edge in graph.edges:
                        if edge.edge_target in doc_ids or edge.edge_source in doc_ids:
                            edge_stats[edge.edge_type] = edge_stats.get(edge.edge_type, 0) + 1
                        # Count per-doc (same logic as _get_doc_instance_counts)
                        if edge.edge_type in ("extracted_from", "has_documentation", "has_visual_reference"):
                            if edge.edge_target in doc_ids:
                                doc_counts[edge.edge_target] = doc_counts.get(edge.edge_target, 0) + 1
                        elif edge.edge_type == "is_documentation_of":
                            if edge.edge_source in doc_ids:
                                doc_counts[edge.edge_source] = doc_counts.get(edge.edge_source, 0) + 1
                    print(f"[DocManager] Graph has {len(graph.edges)} edges total")
                    print(f"[DocManager] Edges involving documents: {edge_stats}")
                    print(f"[DocManager] Per-doc reference counts: {doc_counts}")
                    print(f"[DocManager] Document node IDs sample: {list(doc_ids)[:3]}")
        except Exception as e:
            print(f"[DocManager] Diagnostic error: {e}")

        self.report({'INFO'}, f"Synced {len(context.scene.doc_list)} documents")
        return {'FINISHED'}


# ============================================================================
# IMPORT IMAGE & CREATE QUAD
# ============================================================================

class DOCMANAGER_OT_import_image(bpy.types.Operator):
    """Import document image into the scene as a textured quad"""
    bl_idname = "em.docmanager_import_image"
    bl_label = "Import Image"
    bl_description = "Create a textured image quad in the scene at the 3D cursor, sized from the image aspect ratio"
    bl_options = {'REGISTER', 'UNDO'}

    quad_width: FloatProperty(
        name="Width (m)",
        description="Quad width in meters",
        default=1.0, min=0.01, max=50.0, unit='LENGTH',
    )  # type: ignore
    quad_height: FloatProperty(
        name="Height (m)",
        description="Quad height in meters. Set to 0 to auto-compute from image aspect ratio",
        default=0.0, min=0.0, max=50.0, unit='LENGTH',
    )  # type: ignore
    dimensions_type: EnumProperty(
        name="Dimensions",
        items=[
            ('SYMBOLIC', "Symbolic", "Approximate/default dimensions"),
            ('METRIC', "Metric", "Real measured dimensions"),
        ],
        default='SYMBOLIC',
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        item = _get_active_doc_item(context)
        return item is not None and item.url and not item.has_quad

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "dimensions_type")
        layout.prop(self, "quad_width")
        row = layout.row()
        row.prop(self, "quad_height")
        if self.quad_height == 0.0:
            row.label(text="(auto from aspect ratio)")

    def execute(self, context):
        item = _get_active_doc_item(context)
        if not item:
            self.report({'ERROR'}, "No document selected")
            return {'CANCELLED'}

        # Resolve image path
        image_path = _resolve_doc_image_path(context, item)
        if not image_path:
            self.report({'ERROR'}, f"Cannot resolve image for '{item.name}'. Check DosCo directory.")
            return {'CANCELLED'}

        # Load image
        try:
            img = bpy.data.images.load(image_path, check_existing=True)
        except Exception as e:
            self.report({'ERROR'}, f"Cannot load image: {e}")
            return {'CANCELLED'}

        # Compute dimensions
        width = self.quad_width
        if self.quad_height > 0:
            height = self.quad_height
        else:
            # Auto from aspect ratio
            if img.size[0] > 0 and img.size[1] > 0:
                aspect = img.size[1] / img.size[0]
                height = width * aspect
            else:
                height = width

        # Create plane at 3D cursor position
        bpy.ops.mesh.primitive_plane_add(size=1.0, location=context.scene.cursor.location)
        obj = context.active_object
        obj.name = f"DocQuad_{item.name}"

        # Scale to metric dimensions (plane default is 2x2, size=1.0 → 1x1)
        obj.scale = (width, height, 1.0)
        bpy.ops.object.transform_apply(scale=True)

        # Create material with image texture
        # Pattern adapted from 3D Survey Collection PhotogrTool.py mat_from_image()
        mat = bpy.data.materials.new(name=f"M_Doc_{item.name}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex_node.image = img
        tex_node.location = (-460, 90)
        mat.node_tree.links.new(bsdf.inputs['Base Color'], tex_node.outputs['Color'])
        alpha = context.scene.doc_settings.default_alpha
        bsdf.inputs['Alpha'].default_value = alpha
        try:
            mat.blend_method = 'BLEND'
        except AttributeError:
            pass  # Blender 4.2+

        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

        # Tag the object for graph_updaters integration
        obj['em_doc_node_id'] = item.node_id
        obj['em_dimensions_type'] = self.dimensions_type

        # Update DocItem
        item.has_quad = True
        item.quad_object_name = obj.name
        item.image_path = image_path
        item.quad_width = width
        item.quad_height = height
        item.dimensions_type = self.dimensions_type

        self.report({'INFO'}, f"Created quad for {item.name} ({width:.2f} x {height:.2f} m)")
        return {'FINISHED'}


# ============================================================================
# CREATE CAMERA
# ============================================================================

class DOCMANAGER_OT_create_camera(bpy.types.Operator):
    """Create a camera at the current viewport position looking at the document quad"""
    bl_idname = "em.docmanager_create_camera"
    bl_label = "Create Camera"
    bl_description = "Create a camera at the current viewport pose, aligned to this document's quad"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        item = _get_active_doc_item(context)
        return item is not None and item.has_quad and not item.has_camera

    def execute(self, context):
        item = _get_active_doc_item(context)
        if not item:
            return {'CANCELLED'}

        quad_obj = bpy.data.objects.get(item.quad_object_name)
        if not quad_obj:
            self.report({'ERROR'}, f"Quad object '{item.quad_object_name}' not found")
            return {'CANCELLED'}

        # Capture current 3D viewport position
        region_3d = None
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                region_3d = area.spaces[0].region_3d
                break

        if not region_3d:
            self.report({'ERROR'}, "No 3D Viewport found")
            return {'CANCELLED'}

        view_matrix = region_3d.view_matrix.inverted()

        # Create camera
        focal = context.scene.doc_settings.default_focal_length
        cam_data = bpy.data.cameras.new(name=f"Cam_Doc_{item.name}")
        cam_data.lens = focal

        cam_obj = bpy.data.objects.new(name=f"Cam_Doc_{item.name}", object_data=cam_data)
        context.collection.objects.link(cam_obj)

        # Position at current view
        cam_obj.matrix_world = view_matrix

        # Parent camera to quad (grouped transform)
        cam_obj.parent = quad_obj

        # Tag the quad with camera reference
        quad_obj['em_camera_name'] = cam_obj.name

        # Update DocItem
        item.has_camera = True
        item.camera_object_name = cam_obj.name

        self.report({'INFO'}, f"Created camera for {item.name} (f={focal:.0f}mm)")
        return {'FINISHED'}


# ============================================================================
# LOOK THROUGH CAMERA
# ============================================================================

class DOCMANAGER_OT_look_through(bpy.types.Operator):
    """Switch viewport to look through this document's camera"""
    bl_idname = "em.docmanager_look_through"
    bl_label = "Look Through Camera"
    bl_description = "Switch the viewport to this document's camera and fit render resolution to the image"

    @classmethod
    def poll(cls, context):
        item = _get_active_doc_item(context)
        return item is not None and item.has_camera

    def execute(self, context):
        item = _get_active_doc_item(context)
        if not item:
            return {'CANCELLED'}

        cam_obj = bpy.data.objects.get(item.camera_object_name)
        if not cam_obj or cam_obj.type != 'CAMERA':
            self.report({'ERROR'}, f"Camera '{item.camera_object_name}' not found")
            return {'CANCELLED'}

        context.scene.camera = cam_obj

        # Switch active 3D viewport to camera view
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces[0].region_3d.view_perspective = 'CAMERA'
                break

        return {'FINISHED'}


# ============================================================================
# UTILITY OPERATORS
# ============================================================================

class DOCMANAGER_OT_open_url(bpy.types.Operator):
    """Open the URL or file associated with the selected document"""
    bl_idname = "em.docmanager_open_url"
    bl_label = "Open Document"
    bl_description = "Open the document's URL in the browser, or its file via the system default application"

    @classmethod
    def poll(cls, context):
        item = _get_active_doc_item(context)
        return item is not None and item.url

    def execute(self, context):
        import subprocess
        import sys
        from ..functions import is_valid_url

        item = _get_active_doc_item(context)
        if not item:
            return {'CANCELLED'}

        if is_valid_url(item.url):
            bpy.ops.wm.url_open(url=item.url)
            return {'FINISHED'}

        # Try to resolve via DOSCO and open
        image_path = _resolve_doc_image_path(context, item)
        if image_path and os.path.exists(image_path):
            try:
                if os.name == "nt":
                    os.startfile(image_path)
                elif os.name == "posix":
                    opener = "open" if sys.platform == "darwin" else "xdg-open"
                    subprocess.run([opener, image_path])
                return {'FINISHED'}
            except Exception as e:
                self.report({'WARNING'}, f"Cannot open file: {e}")
                return {'CANCELLED'}

        self.report({'WARNING'}, f"Cannot resolve path for {item.name}")
        return {'CANCELLED'}


class DOCMANAGER_OT_select_scene_object(bpy.types.Operator):
    """Select the quad object for this document in the viewport"""
    bl_idname = "em.docmanager_select_object"
    bl_label = "Select Quad"
    bl_description = "Select this document's quad object in the 3D viewport"

    @classmethod
    def poll(cls, context):
        item = _get_active_doc_item(context)
        return item is not None and item.has_quad

    def execute(self, context):
        item = _get_active_doc_item(context)
        if not item:
            return {'CANCELLED'}

        obj = bpy.data.objects.get(item.quad_object_name)
        if obj:
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj
            self.report({'INFO'}, f"Selected {obj.name}")
        return {'FINISHED'}


# ============================================================================
# RENAME OBJECT FROM DOCUMENT
# ============================================================================

class DOCMANAGER_OT_rename_object(bpy.types.Operator):
    """Rename the selected 3D object using the document name (with graph prefix)"""
    bl_idname = "em.docmanager_rename_object"
    bl_label = "Rename Object from Document"
    bl_description = "Rename the active 3D object to match this document's name (with the graph prefix applied)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        item = _get_active_doc_item(context)
        return item is not None and context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        from ..functions import is_graph_available as check_graph
        from ..operators.addon_prefix_helpers import node_name_to_proxy_name

        item = _get_active_doc_item(context)
        if not item:
            return {'CANCELLED'}

        graph_exists, graph = check_graph(context)
        active_graph = graph if graph_exists else None

        proxy_name = node_name_to_proxy_name(item.name, context=context, graph=active_graph)
        context.active_object.name = proxy_name

        # Tag the object as document quad for graph_updaters integration
        context.active_object['em_doc_node_id'] = item.node_id

        # Invalidate object cache after renaming
        from ..object_cache import invalidate_object_cache
        invalidate_object_cache()

        # Re-sync to detect the renamed object
        sync_doc_list(context.scene)

        self.report({'INFO'}, f"Renamed object to '{proxy_name}'")
        return {'FINISHED'}


class DOCMANAGER_OT_select_linked(bpy.types.Operator):
    """Select objects linked to this document via graph edges (RM or RMDoc)"""
    bl_idname = "em.docmanager_select_linked"
    bl_label = "Select Linked"
    bl_description = "Select the linked RM or RMDoc object in the 3D viewport"

    doc_node_id: StringProperty()  # type: ignore
    link_type: StringProperty(default='RM')  # 'RM' or 'RMDoc'  # type: ignore

    def execute(self, context):
        if not self.doc_node_id:
            return {'CANCELLED'}

        try:
            from s3dgraphy import get_graph
            em_tools = context.scene.em_tools
            if em_tools.active_file_index < 0:
                return {'CANCELLED'}

            graph_info = em_tools.graphml_files[em_tools.active_file_index]
            graph = get_graph(graph_info.name)
            if not graph:
                return {'CANCELLED'}

            # Find linked node via edges
            target_node_id = None
            if self.link_type == 'RM':
                edge_type = "has_representation_model"
            else:
                edge_type = "has_representation_model_doc"

            for edge in graph.edges:
                if (edge.edge_source == self.doc_node_id and
                        edge.edge_type == edge_type):
                    target_node_id = edge.edge_target
                    break

            if not target_node_id:
                self.report({'INFO'}, f"No {self.link_type} linked to this document")
                return {'CANCELLED'}

            # Find the target node to get its name
            target_node = graph.find_node_by_id(target_node_id)
            if not target_node:
                return {'CANCELLED'}

            # For RMDoc: find the Blender object via em_doc_node_id custom property
            if self.link_type == 'RMDoc':
                for obj in bpy.data.objects:
                    if obj.get('em_doc_node_id') == self.doc_node_id:
                        bpy.ops.object.select_all(action='DESELECT')
                        obj.select_set(True)
                        context.view_layer.objects.active = obj
                        self.report({'INFO'}, f"Selected RMDoc: {obj.name}")
                        return {'FINISHED'}

            # For RM: find by name in scene
            if self.link_type == 'RM' and hasattr(target_node, 'name'):
                obj = bpy.data.objects.get(target_node.name)
                if obj:
                    bpy.ops.object.select_all(action='DESELECT')
                    obj.select_set(True)
                    context.view_layer.objects.active = obj
                    self.report({'INFO'}, f"Selected RM: {obj.name}")
                    return {'FINISHED'}

                # Try with graph prefix
                from ..operators.addon_prefix_helpers import node_name_to_proxy_name
                prefixed_name = node_name_to_proxy_name(target_node.name, context, graph)
                obj = bpy.data.objects.get(prefixed_name)
                if obj:
                    bpy.ops.object.select_all(action='DESELECT')
                    obj.select_set(True)
                    context.view_layer.objects.active = obj
                    self.report({'INFO'}, f"Selected RM: {obj.name}")
                    return {'FINISHED'}

            self.report({'INFO'}, f"Object not found in scene")
            return {'CANCELLED'}

        except Exception as e:
            self.report({'WARNING'}, f"Error selecting linked: {e}")
            return {'CANCELLED'}


class DOCMANAGER_OT_select_linked_entity(bpy.types.Operator):
    """Select linked entity (US proxy, RMSF object, or RMDoc quad) and jump to its panel row"""
    bl_idname = "em.docmanager_select_linked_entity"
    bl_label = "Select Linked Entity"
    bl_description = "Select the linked object in the viewport and highlight its row in the target panel"

    node_id: StringProperty()  # type: ignore
    entity_type: StringProperty()  # 'US', 'RMSF', 'RMDoc'  # type: ignore

    def _select_object(self, context, obj):
        """Deselect all, ensure object is accessible, select and activate, optionally zoom."""
        from ..epoch_manager.operators import _ensure_object_accessible_for_viewlayer

        # Make sure the object is visible and selectable (unhide collections, etc.)
        prep = _ensure_object_accessible_for_viewlayer(
            context, obj, make_visible=True, make_selectable=True
        )
        if prep["activated_collections"]:
            self.report({'INFO'}, f"Enabled collections: {', '.join(prep['activated_collections'])}")
        if prep["errors"]:
            self.report({'WARNING'}, "; ".join(prep["errors"]))
            return False

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj

        if context.scene.doc_settings.zoom_to_selected:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            with context.temp_override(area=area, region=region):
                                bpy.ops.view3d.view_selected()
                            break
                    break
        return True

    def _find_object_by_name(self, name, context):
        """Try to find a scene object by exact name, then with graph prefix."""
        obj = bpy.data.objects.get(name)
        if obj:
            return obj

        # Try with graph prefix
        try:
            from ..operators.addon_prefix_helpers import node_name_to_proxy_name
            from ..functions import is_graph_available
            graph_exists, graph = is_graph_available(context)
            if graph_exists and graph:
                prefixed = node_name_to_proxy_name(name, context=context, graph=graph)
                obj = bpy.data.objects.get(prefixed)
                if obj:
                    return obj
        except Exception:
            pass
        return None

    def _handle_us(self, context):
        """Select US proxy object and set Stratigraphy Manager row."""
        from s3dgraphy import get_graph

        em_tools = context.scene.em_tools
        if em_tools.active_file_index < 0 or not em_tools.graphml_files:
            self.report({'WARNING'}, "No graph loaded")
            return {'CANCELLED'}

        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)
        if not graph:
            self.report({'WARNING'}, "Graph not available")
            return {'CANCELLED'}

        node = graph.find_node_by_id(self.node_id)
        if not node or not hasattr(node, 'name'):
            self.report({'WARNING'}, f"Node {self.node_id} not found in graph")
            return {'CANCELLED'}

        # Find the proxy object in the scene
        obj = self._find_object_by_name(node.name, context)
        if not obj:
            self.report({'INFO'}, f"No proxy object found for US '{node.name}'")
            return {'CANCELLED'}

        if not self._select_object(context, obj):
            return {'CANCELLED'}

        # Set Stratigraphy Manager list index
        units = em_tools.stratigraphy.units
        for i, unit in enumerate(units):
            if unit.id_node == self.node_id:
                em_tools.stratigraphy.units_index = i
                break

        self.report({'INFO'}, f"Selected US: {obj.name}")
        return {'FINISHED'}

    def _handle_rmsf(self, context):
        """Select RMSF object and set Anastylosis panel row."""
        em_tools = context.scene.em_tools
        anastylosis = em_tools.anastylosis

        # Find the RMSF item by sf_node_id (the SF/VSF stratigraphic node)
        found_idx = -1
        found_item = None
        for i, item in enumerate(anastylosis.list):
            if item.sf_node_id == self.node_id:
                found_idx = i
                found_item = item
                break

        if found_item is None:
            self.report({'INFO'}, f"No RMSF entry found for SF node {self.node_id}")
            return {'CANCELLED'}

        obj = bpy.data.objects.get(found_item.name)
        if not obj:
            self.report({'INFO'}, f"RMSF object '{found_item.name}' not found in scene")
            return {'CANCELLED'}

        if not self._select_object(context, obj):
            return {'CANCELLED'}
        anastylosis.list_index = found_idx

        self.report({'INFO'}, f"Selected RMSF: {obj.name}")
        return {'FINISHED'}

    def _handle_rmdoc(self, context):
        """Select RMDoc quad object and set RMDoc panel row."""
        scene = context.scene

        # Find scene object by em_doc_node_id custom property
        target_obj = None
        for obj in bpy.data.objects:
            if obj.get('em_doc_node_id') == self.node_id:
                target_obj = obj
                break

        if not target_obj:
            self.report({'INFO'}, f"No RMDoc quad found for document {self.node_id}")
            return {'CANCELLED'}

        if not self._select_object(context, target_obj):
            return {'CANCELLED'}

        # Set rmdoc_list index
        for i, item in enumerate(scene.rmdoc_list):
            if item.name == target_obj.name:
                scene.rmdoc_list_index = i
                break

        self.report({'INFO'}, f"Selected RMDoc: {target_obj.name}")
        return {'FINISHED'}

    def execute(self, context):
        if not self.node_id or not self.entity_type:
            return {'CANCELLED'}

        if self.entity_type == 'US':
            return self._handle_us(context)
        elif self.entity_type == 'RMSF':
            return self._handle_rmsf(context)
        elif self.entity_type == 'RMDoc':
            return self._handle_rmdoc(context)
        else:
            self.report({'WARNING'}, f"Unknown entity type: {self.entity_type}")
            return {'CANCELLED'}


class DOCMANAGER_OT_select_all_linked_us(bpy.types.Operator):
    """Select all US proxy objects linked to a document"""
    bl_idname = "em.docmanager_select_all_linked_us"
    bl_label = "Select All Linked US"
    bl_description = "Select all US proxy objects linked to this document in the viewport"

    doc_node_id: StringProperty()  # type: ignore

    def _find_object_by_name(self, name, context):
        """Try to find a scene object by exact name, then with graph prefix."""
        obj = bpy.data.objects.get(name)
        if obj:
            return obj
        try:
            from ..operators.addon_prefix_helpers import node_name_to_proxy_name
            from ..functions import is_graph_available
            graph_exists, graph = is_graph_available(context)
            if graph_exists and graph:
                prefixed = node_name_to_proxy_name(name, context=context, graph=graph)
                obj = bpy.data.objects.get(prefixed)
                if obj:
                    return obj
        except Exception:
            pass
        return None

    def execute(self, context):
        from ..epoch_manager.operators import _ensure_object_accessible_for_viewlayer

        if not self.doc_node_id:
            return {'CANCELLED'}

        # Build the doc cache to get linked US nodes
        from .ui import _build_doc_cache
        doc_cache = _build_doc_cache(context)
        doc_info = doc_cache.get(self.doc_node_id, {})
        us_nodes = doc_info.get('us_nodes', [])

        # Filter out SF/VSF (same logic as the UI)
        sf_types = {"SF", "VSF"}
        regular_us = [u for u in us_nodes if u[2] not in sf_types]

        if not regular_us:
            self.report({'INFO'}, "No linked US found for this document")
            return {'CANCELLED'}

        # Get the graph to resolve node IDs to names
        from s3dgraphy import get_graph
        em_tools = context.scene.em_tools
        if em_tools.active_file_index < 0 or not em_tools.graphml_files:
            self.report({'WARNING'}, "No graph loaded")
            return {'CANCELLED'}

        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)
        if not graph:
            self.report({'WARNING'}, "Graph not available")
            return {'CANCELLED'}

        # Collect all proxy objects
        proxy_objects = []
        for us_name, us_node_id, us_type in regular_us:
            node = graph.find_node_by_id(us_node_id)
            if node and hasattr(node, 'name'):
                obj = self._find_object_by_name(node.name, context)
                if obj:
                    proxy_objects.append(obj)

        if not proxy_objects:
            self.report({'INFO'}, "No proxy objects found in scene for linked US")
            return {'CANCELLED'}

        # Ensure all objects are accessible and select them
        bpy.ops.object.select_all(action='DESELECT')
        selected_count = 0
        for obj in proxy_objects:
            prep = _ensure_object_accessible_for_viewlayer(
                context, obj, make_visible=True, make_selectable=True
            )
            if not prep["errors"]:
                try:
                    obj.select_set(True)
                    selected_count += 1
                except RuntimeError:
                    pass

        # Set first selected as active
        if selected_count > 0:
            for obj in context.selected_objects:
                context.view_layer.objects.active = obj
                break

            # Zoom to selection if enabled
            if context.scene.doc_settings.zoom_to_selected:
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                with context.temp_override(area=area, region=region):
                                    bpy.ops.view3d.view_selected()
                                break
                        break

        self.report({'INFO'}, f"Selected {selected_count} US prox{'y' if selected_count == 1 else 'ies'}")
        return {'FINISHED'}


class DOCMANAGER_OT_create_document(bpy.types.Operator):
    """Create a new document node in the graph"""
    bl_idname = "docmanager.create_document"
    bl_label = "Create Document"
    bl_description = "Create a new document node and add it to the graph"
    bl_options = {'REGISTER', 'UNDO'}

    doc_name: bpy.props.StringProperty(
        name="Name", description="Document name (e.g. D.15)", default=""
    )  # type: ignore
    doc_description: bpy.props.StringProperty(
        name="Description", description="Brief description", default=""
    )  # type: ignore
    doc_date: bpy.props.StringProperty(
        name="Date", description="Date of the document (e.g. 2016)", default=""
    )  # type: ignore
    doc_type: bpy.props.EnumProperty(
        name="Type", description="Document type",
        items=[
            ('IMAGE', 'Image', 'Photograph, drawing, scan'),
            ('MODEL_3D', '3D Model', 'Photogrammetric or laser scan model'),
            ('TEXT', 'Textual', 'Written document'),
            ('PDF', 'PDF', 'PDF document'),
            ('CAD', 'CAD', 'CAD drawing (DWG, DXF)'),
            ('SHAPEFILE', 'Shapefile', 'GIS shapefile'),
            ('OTHER', 'Other', 'Other document type'),
        ],
        default='IMAGE'
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.scene.em_tools.active_file_index >= 0

    def invoke(self, context, event):
        # Auto-suggest next document number
        from s3dgraphy import get_graph
        em_tools = context.scene.em_tools
        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)
        if graph:
            max_num = 0
            for node in graph.nodes:
                if (hasattr(node, 'node_type') and node.node_type == 'document'
                        and hasattr(node, 'name') and isinstance(node.name, str)):
                    if node.name.startswith('D.'):
                        try:
                            num = int(node.name.split('.', 1)[1])
                            max_num = max(max_num, num)
                        except (ValueError, IndexError):
                            pass
            self.doc_name = f"D.{max_num + 1}"
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "doc_name")
        layout.prop(self, "doc_description")
        layout.prop(self, "doc_date")
        layout.prop(self, "doc_type")

    def execute(self, context):
        if not self.doc_name:
            self.report({'ERROR'}, "Document name is required")
            return {'CANCELLED'}

        import uuid
        from s3dgraphy import get_graph
        from s3dgraphy.nodes import DocumentNode

        em_tools = context.scene.em_tools
        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)
        if not graph:
            self.report({'ERROR'}, "Graph not loaded")
            return {'CANCELLED'}

        # Check if document with this name already exists
        for node in graph.nodes:
            if (hasattr(node, 'node_type') and node.node_type == 'document'
                    and hasattr(node, 'name') and node.name == self.doc_name):
                self.report({'ERROR'}, f"Document '{self.doc_name}' already exists in the graph")
                return {'CANCELLED'}

        # Create document node
        doc_node = DocumentNode(
            node_id=str(uuid.uuid4()),
            name=self.doc_name,
            description=self.doc_description or self.doc_name
        )
        if self.doc_date:
            doc_node.attributes['date'] = self.doc_date
        doc_node.attributes['doc_type'] = self.doc_type
        graph.add_node(doc_node)

        # Refresh lists
        from ..populate_lists import populate_document_node
        idx = len(em_tools.em_sources_list)
        populate_document_node(context.scene, doc_node, idx, graph=graph)

        sync_doc_list(context.scene)

        self.report({'INFO'}, f"Created document: {self.doc_name}")
        return {'FINISHED'}


# Module-level cache for the epoch-items EnumProperty callback — Blender
# requires Python to retain references to the strings returned by a
# dynamic items callback, otherwise the UI renders garbled labels.
_MASTER_DOC_EPOCH_ITEMS_CACHE: list = []


def _master_doc_epoch_items(self, context):
    """EnumProperty items callback: epochs present in the active graph,
    plus a ``__derive__`` sentinel that lets the operator resolve the
    anchor from a provided year. Mirrors the DosCo Create Host flow so
    the dialog feels identical to users coming from that entry point.
    """
    global _MASTER_DOC_EPOCH_ITEMS_CACHE
    items = [("__derive__", "-- derive from year --",
              "Derive the has_first_epoch anchor by looking up which "
              "EpochNode range contains the year below")]
    em_tools = context.scene.em_tools
    if (em_tools.active_file_index >= 0
            and em_tools.active_file_index < len(em_tools.graphml_files)):
        try:
            from s3dgraphy import get_graph
            gi = em_tools.graphml_files[em_tools.active_file_index]
            graph = get_graph(gi.name)
        except Exception:
            graph = None
        if graph is not None:
            for n in graph.nodes:
                if type(n).__name__ == "EpochNode":
                    start = getattr(n, "start_time", None)
                    end = getattr(n, "end_time", None)
                    range_hint = ""
                    if start is not None and end is not None:
                        range_hint = f" [{int(start)}..{int(end)}]"
                    items.append((n.node_id,
                                  (n.name or n.node_id) + range_hint,
                                  f"Anchor has_first_epoch to {n.name}"))
    _MASTER_DOC_EPOCH_ITEMS_CACHE = items
    return items


class DOCMANAGER_OT_suggest_next_doc_name_for_dialog(bpy.types.Operator):
    """Fill the Name field of the open Create Master Document dialog
    with the next available ``D.NNN``.

    Implementation: the dialog's Name field is backed by the scene
    property ``scene.em_pending_master_doc_name`` (a shared transient
    buffer). This operator writes the next suggested value into that
    property; on the next UI tick Blender redraws the dialog with the
    fresh value. This avoids the fragile ``wm.operators`` stack walk
    that was not reliable for dialogs still in their modal lifetime.
    """
    bl_idname = "docmanager.suggest_next_doc_name_for_dialog"
    bl_label = "Suggest next D.NNN"
    bl_description = (
        "Fill Name with the next available D.NNN — uses the gap-aware "
        "numbering (first free number in range, else max+1)"
    )
    bl_options = {'INTERNAL'}

    def execute(self, context):
        em_tools = context.scene.em_tools
        graph = None
        try:
            if em_tools.active_file_index >= 0:
                from s3dgraphy import get_graph
                gi = em_tools.graphml_files[em_tools.active_file_index]
                graph = get_graph(gi.name)
        except Exception:
            graph = None
        from ..master_document_helpers import suggest_next_document_name
        proposed = suggest_next_document_name(graph)
        # Write into the shared scene buffer — the open dialog's Name
        # field reads from this property, so it updates on next tick.
        context.scene.em_pending_master_doc_name = proposed
        self.report({'INFO'}, f"Suggested next: {proposed}")
        return {'FINISHED'}


class DOCMANAGER_OT_create_master_document(bpy.types.Operator):
    """Create a Master Document with the full three-axis classification
    (EM 1.6 — role / content_nature / geometry) and a temporal anchor.

    Shared entry point for any EMtools flow that needs a new DP-07
    Master Document: DosCo Create Host (for orphan promotion), the RM
    Manager container creation (DP-47 extension), and any standalone
    use case from the Document Manager panel. Thin operator wrapper
    around :func:`master_document_helpers.create_master_document_node`.
    """
    bl_idname = "docmanager.create_master_document"
    bl_label = "Create Master Document"
    bl_description = (
        "Create a new Master Document with three-axis classification "
        "(role / content nature / geometry) and a temporal anchor. "
        "Mirrors the DosCo Create Host dialog."
    )
    bl_options = {'REGISTER', 'UNDO'}

    # Inputs shared with the DosCo Create Host dialog pattern.
    # Note: the Name field is backed by the scene-level
    # ``em_pending_master_doc_name`` (see data.py) instead of an
    # operator property, so the "+" suggest-next button can write
    # into the open dialog without the fragile wm.operators dance.
    new_description: bpy.props.StringProperty(
        name="Description",
        description="Free-text description (optional)",
        default=""
    )  # type: ignore
    persist_after_create: bpy.props.BoolProperty(
        name="Persist to GraphML after creation",
        description=(
            "Also save the GraphML right after creating the document, "
            "so the new master survives a Blender close or graph "
            "reload. Requires the .graphml file to be CLOSED in yEd "
            "(yEd does not hold a filesystem lock on macOS/Linux, so "
            "the user is responsible for closing it before saving)."
        ),
        default=True,
    )  # type: ignore
    epoch_id: bpy.props.EnumProperty(
        name="Anchor epoch",
        description=(
            "Epoch this document first appears in. Creates a "
            "has_first_epoch edge. Leave on 'derive from year' to let "
            "the operator pick the epoch whose range contains the "
            "provided year."
        ),
        items=_master_doc_epoch_items,
    )  # type: ignore
    has_creation_year: bpy.props.BoolProperty(
        name="Provide creation year",
        default=False,
    )  # type: ignore
    creation_year: bpy.props.IntProperty(
        name="Creation year",
        description="Year of this document (negative = BCE)",
        default=0,
    )  # type: ignore
    doc_role: bpy.props.EnumProperty(
        name="Role",
        items=[
            ("analytical", "Analytical",
             "Primary source about this context"),
            ("comparative", "Comparative",
             "External reference / analogy"),
        ],
        default="analytical",
    )  # type: ignore
    doc_content_nature: bpy.props.EnumProperty(
        name="Content nature",
        items=[
            ("2d_object", "2D Object",
             "Image, drawing, photograph, text"),
            ("3d_object", "3D Object",
             "Mesh, laser scan, photogrammetric model"),
        ],
        default="2d_object",
    )  # type: ignore
    doc_geometry: bpy.props.EnumProperty(
        name="Geometry",
        items=[
            ("none", "No 3D spatialization",
             "Document has no Representation Model"),
            ("reality_based", "Reality-based (red)",
             "Sensor / algorithmic positioning"),
            ("observable", "Observable (orange)",
             "Reconstructed from rigorous documentation"),
            ("asserted", "Asserted (yellow)",
             "Compositional positioning asserted by the operator"),
            ("em_based", "EM-based reconstruction (blue)",
             "3D reconstruction produced via the Extended Matrix "
             "methodology — typically a hypothesis model built from "
             "another EM graph"),
        ],
        default="none",
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        return em_tools.active_file_index >= 0

    def invoke(self, context, event):
        # Reset to defaults on every invocation. Name is stored in a
        # scene-level transient property so the "+" button can write
        # to the open dialog (operator StringProperty can't be
        # mutated from a sub-operator while the dialog is alive).
        scene = context.scene
        em_tools = scene.em_tools
        graph = None
        try:
            if em_tools.active_file_index >= 0:
                from s3dgraphy import get_graph
                gi = em_tools.graphml_files[em_tools.active_file_index]
                graph = get_graph(gi.name)
        except Exception:
            graph = None
        from ..master_document_helpers import suggest_next_document_name
        scene.em_pending_master_doc_name = suggest_next_document_name(graph)
        self.new_description = ""
        self.has_creation_year = False
        self.creation_year = 0
        self.doc_role = "analytical"
        self.doc_content_nature = "2d_object"
        self.doc_geometry = "none"
        self.persist_after_create = True
        return context.window_manager.invoke_props_dialog(self, width=440)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.label(text="New Master Document", icon='FILE_TEXT')
        layout.separator()
        # Name field with an inline "+" button that suggests the next
        # available D.NNN. Bound to a scene property so the button can
        # write into the open dialog.
        name_row = layout.row(align=True)
        name_row.prop(scene, "em_pending_master_doc_name", text="Name")
        name_row.operator(
            "docmanager.suggest_next_doc_name_for_dialog",
            text="", icon='ADD')
        layout.prop(self, "new_description")

        # Temporal anchor
        anchor_box = layout.box()
        anchor_box.label(text="Temporal anchor (required):", icon='TIME')
        anchor_box.prop(self, "epoch_id", text="Epoch")
        row = anchor_box.row(align=True)
        row.prop(self, "has_creation_year", text="Year")
        sub = row.row(align=True)
        sub.enabled = self.has_creation_year
        sub.prop(self, "creation_year", text="")

        if self.epoch_id == "__derive__" and not self.has_creation_year:
            warn = anchor_box.row()
            warn.alert = True
            warn.label(text="Choose an epoch OR tick Year with a date",
                       icon='ERROR')
        elif self.epoch_id == "__derive__" and self.has_creation_year:
            em_tools = context.scene.em_tools
            graph = None
            if em_tools.active_file_index >= 0:
                try:
                    from s3dgraphy import get_graph
                    gi = em_tools.graphml_files[em_tools.active_file_index]
                    graph = get_graph(gi.name)
                except Exception:
                    graph = None
            from ..master_document_helpers import resolve_epoch_from_year
            resolved = resolve_epoch_from_year(graph, self.creation_year)
            hint = anchor_box.row()
            if resolved is None:
                hint.alert = True
                hint.label(
                    text=f"No epoch covers year {self.creation_year}",
                    icon='ERROR')
            else:
                hint.label(text=f"Will anchor to {resolved.name}",
                           icon='CHECKMARK')

        # Classification
        cls_box = layout.box()
        cls_box.label(text="Master Document classification:",
                      icon='OUTLINER_DATA_LATTICE')
        cls_box.prop(self, "doc_role", text="Role")
        cls_box.prop(self, "doc_content_nature", text="Content")
        cls_box.prop(self, "doc_geometry", text="Geometry")
        hint = cls_box.row()
        color_hint = {
            "none":          "no RM -> no geometry node",
            "reality_based": "border red",
            "observable":    "border orange",
            "asserted":      "border yellow",
            "em_based":      "border blue",
        }.get(self.doc_geometry, "--")
        hint.label(text=color_hint, icon='CHECKMARK')

        # Persistence — default ON so the master document reaches disk
        # right away. The disclaimer makes the yEd-must-be-closed
        # constraint visible to the user (yEd does not hold an OS
        # file-lock on macOS/Linux, so the system cannot detect it
        # automatically).
        persist_box = layout.box()
        persist_box.prop(self, "persist_after_create")
        disclaimer = persist_box.row()
        if self.persist_after_create:
            disclaimer.alert = True
            disclaimer.label(
                text="Close the .graphml in yEd before saving "
                     "— yEd doesn't hold a file lock.",
                icon='ERROR')
        else:
            disclaimer.label(
                text="In-memory only — lost on reload or Blender close.",
                icon='MEMORY')

    def execute(self, context):
        scene = context.scene
        em_tools = scene.em_tools
        if em_tools.active_file_index < 0:
            self.report({'ERROR'}, "No active graph")
            return {'CANCELLED'}
        name = (scene.em_pending_master_doc_name or "").strip()
        if not name:
            self.report({'ERROR'}, "Name is required")
            return {'CANCELLED'}

        from s3dgraphy import get_graph
        gi = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(gi.name)
        if graph is None:
            self.report({'ERROR'}, "Graph not loaded")
            return {'CANCELLED'}

        # Resolve epoch: explicit pick wins; otherwise derive from year.
        from ..master_document_helpers import (
            create_master_document_node, refresh_document_lists,
            resolve_epoch_from_year,
        )
        resolved_epoch = None
        if self.epoch_id and self.epoch_id != "__derive__":
            resolved_epoch = next(
                (n for n in graph.nodes if n.node_id == self.epoch_id),
                None)
        elif self.has_creation_year:
            resolved_epoch = resolve_epoch_from_year(
                graph, self.creation_year)
            if resolved_epoch is None:
                self.report({'ERROR'},
                            f"No epoch range contains year "
                            f"{self.creation_year}. Pick an epoch "
                            f"explicitly or adjust the year.")
                return {'CANCELLED'}

        if resolved_epoch is None:
            self.report({'ERROR'},
                        "Temporal anchor required: pick an epoch "
                        "or tick Year with a valid date.")
            return {'CANCELLED'}

        _role = self.doc_role
        _nature = self.doc_content_nature
        _geom = (self.doc_geometry
                 if self.doc_geometry != "none" else None)
        desc = (self.new_description or "").strip()
        node = create_master_document_node(
            graph,
            name=name,
            description=desc or f"Master Document '{name}'",
            resolved_epoch=resolved_epoch,
            creation_year=(self.creation_year
                           if self.has_creation_year else None),
            role=_role,
            content_nature=_nature,
            geometry=_geom,
            mark_as_master=True,
        )
        refresh_document_lists(context, node, graph)

        # Expose the created doc_node_id in a volatile scene field so
        # callers chaining this operator (e.g. RM Manager container
        # creation) can consume it after the dialog closes.
        em_tools["last_created_master_doc_id"] = node.node_id

        # Optional persistence — run Save GraphML so the new master
        # document reaches disk. The write-lock guard (see
        # graphml_lock.py) will fail fast with a clear message when
        # yEd holds the file on Windows; on macOS/Linux yEd doesn't
        # lock, so the disclaimer shown in the dialog makes the
        # responsibility explicit.
        persisted = False
        if self.persist_after_create:
            try:
                result = bpy.ops.export.graphml_update()
                persisted = 'FINISHED' in result
            except Exception as e:
                self.report({'WARNING'},
                            f"Document created but Save GraphML failed: {e}")

        msg_tail = f" @ {resolved_epoch.name}"
        if self.has_creation_year:
            msg_tail += f" ({self.creation_year})"
        if persisted:
            msg_tail += " [persisted]"
        self.report({'INFO'},
                    f"Created Master Document {name!r}{msg_tail}")
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class DOCMANAGER_OT_edit_classification(bpy.types.Operator):
    """Edit the three-axis classification (EM 1.6) of an existing
    Master Document: role, content nature, geometry.
    """
    bl_idname = "docmanager.edit_classification"
    bl_label = "Edit classification"
    bl_description = (
        "Edit the three-axis Master-Document classification "
        "(role / content nature / geometry) of the selected document"
    )
    bl_options = {'REGISTER', 'UNDO'}

    doc_node_id: bpy.props.StringProperty()  # type: ignore

    doc_role: bpy.props.EnumProperty(
        name="Role",
        description="Axis 1 — how this document participates in the "
                    "reconstructive reasoning",
        items=[
            ("analytical", "Analytical",
             "Primary source about THIS context"),
            ("comparative", "Comparative",
             "External reference / analogy from other contexts"),
        ],
    )  # type: ignore

    doc_content_nature: bpy.props.EnumProperty(
        name="Content nature",
        description="Axis 2 — what this document is",
        items=[
            ("2d_object", "2D Object",
             "Image, drawing, photograph, text"),
            ("3d_object", "3D Object",
             "Mesh, laser scan, photogrammetric model"),
        ],
    )  # type: ignore

    doc_geometry: bpy.props.EnumProperty(
        name="Geometry",
        description="Axis 3 — how the RM is spatialized in 3D. "
                    "Choose 'No 3D spatialization' for documents "
                    "without an RM (PDF article, bibliography)",
        items=[
            ("none", "No 3D spatialization",
             "The document has no RM — no geometry value recorded"),
            ("reality_based", "Reality-based (red)",
             "Sensor / algorithmic positioning"),
            ("observable", "Observable (orange)",
             "Reconstructed from rigorous documentation"),
            ("asserted", "Asserted (yellow)",
             "Compositional positioning asserted by the operator"),
            ("em_based", "EM-based reconstruction (blue)",
             "3D reconstruction produced via the Extended Matrix "
             "methodology — typically a hypothesis model from "
             "another EM graph"),
        ],
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.scene.em_tools.active_file_index >= 0

    def _resolve_node(self, context):
        from s3dgraphy import get_graph
        em_tools = context.scene.em_tools
        if em_tools.active_file_index < 0:
            return None
        gi = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(gi.name)
        if graph is None or not self.doc_node_id:
            return None
        return graph.find_node_by_id(self.doc_node_id)

    def invoke(self, context, event):
        node = self._resolve_node(context)
        if node is None:
            self.report({'ERROR'}, "DocumentNode not found")
            return {'CANCELLED'}
        data = getattr(node, "data", None) or {}
        self.doc_role = data.get("role") or "analytical"
        self.doc_content_nature = data.get("content_nature") or "2d_object"
        self.doc_geometry = data.get("geometry") or "none"
        return context.window_manager.invoke_props_dialog(self, width=440)

    def draw(self, context):
        layout = self.layout
        node = self._resolve_node(context)
        name = node.name if node is not None else self.doc_node_id
        layout.label(text=f"Editing: {name}", icon='FILE_TEXT')
        layout.separator()
        layout.prop(self, "doc_role")
        layout.prop(self, "doc_content_nature")
        layout.prop(self, "doc_geometry")
        hint = layout.row()
        color_hint = {
            "none":          "no RM -> no geometry node",
            "reality_based": "border red",
            "observable":    "border orange",
            "asserted":      "border yellow",
            "em_based":      "border blue",
        }.get(self.doc_geometry, "--")
        hint.label(text=color_hint, icon='CHECKMARK')

    def execute(self, context):
        node = self._resolve_node(context)
        if node is None:
            self.report({'ERROR'}, "DocumentNode not found")
            return {'CANCELLED'}
        if not hasattr(node, "data") or node.data is None:
            node.data = {}
        node.data["role"] = self.doc_role
        node.data["content_nature"] = self.doc_content_nature
        if self.doc_geometry == "none":
            node.data.pop("geometry", None)
        else:
            node.data["geometry"] = self.doc_geometry

        # Refresh the Document Manager cache + UIList so the icon
        # colour updates without requiring a graphml reload.
        try:
            from .ui import invalidate_doc_connection_cache
            invalidate_doc_connection_cache()
        except Exception:
            pass
        for area in context.screen.areas:
            area.tag_redraw()
        self.report(
            {'INFO'},
            f"Classification updated for {node.name}: "
            f"role={self.doc_role}, content={self.doc_content_nature}, "
            f"geometry={self.doc_geometry}")
        return {'FINISHED'}


# ============================================================================
# RMDOC OPERATORS (object-centric — operate on scene quads, not doc_list)
# ============================================================================

def _get_active_rmdoc_item(context):
    """Return the active RMDocItem from scene.rmdoc_list, or None."""
    scene = context.scene
    idx = scene.rmdoc_list_index
    if 0 <= idx < len(scene.rmdoc_list):
        return scene.rmdoc_list[idx]
    return None


def _get_or_create_dosco_collection():
    """Get or create the DosCo collection for document quads."""
    col = bpy.data.collections.get("DosCo")
    if col is None:
        col = bpy.data.collections.new(name="DosCo")
        bpy.context.scene.collection.children.link(col)
    return col


def _find_rmdoc_camera(obj):
    """Find camera for an RMDoc quad object. Returns camera object or None."""
    cam_name = obj.get('em_camera_name', '')
    if cam_name:
        cam_obj = bpy.data.objects.get(cam_name)
        if cam_obj and cam_obj.type == 'CAMERA':
            return cam_obj
    # Fallback: check children
    for child in obj.children:
        if child.type == 'CAMERA':
            return child
    return None


def _camera_quad_distance(cam_obj, quad_obj):
    """Calculate distance from camera to quad."""
    if quad_obj.parent == cam_obj:
        dist = abs(quad_obj.location.z)
    else:
        dist = (cam_obj.matrix_world.translation - quad_obj.matrix_world.translation).length
    return max(dist, 0.2)


def _ensure_accessible_and_select(operator, context, obj):
    """Ensure object is accessible (unhide collections) then select it.
    Returns True on success, False on failure."""
    from ..epoch_manager.operators import _ensure_object_accessible_for_viewlayer

    prep = _ensure_object_accessible_for_viewlayer(
        context, obj, make_visible=True, make_selectable=True
    )
    if prep["activated_collections"]:
        operator.report({'INFO'}, f"Enabled collections: {', '.join(prep['activated_collections'])}")
    if prep["errors"]:
        operator.report({'WARNING'}, "; ".join(prep["errors"]))
        return False

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    context.view_layer.objects.active = obj

    if context.scene.doc_settings.zoom_to_selected:
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        with context.temp_override(area=area, region=region):
                            bpy.ops.view3d.view_selected()
                        break
                break
    return True


class RMDOC_OT_select_object(bpy.types.Operator):
    """Select this RMDoc quad object in the viewport"""
    bl_idname = "em.rmdoc_select_object"
    bl_label = "Select RMDoc Object"
    bl_description = "Select this RMDoc's quad in the 3D viewport (unhides its collection if needed)"

    object_name: StringProperty()  # type: ignore

    def execute(self, context):
        obj = bpy.data.objects.get(self.object_name)
        if not obj:
            self.report({'WARNING'}, f"Object '{self.object_name}' not found")
            return {'CANCELLED'}

        if not _ensure_accessible_and_select(self, context, obj):
            return {'CANCELLED'}

        self.report({'INFO'}, f"Selected: {obj.name}")
        return {'FINISHED'}


class RMDOC_OT_add_selected(bpy.types.Operator):
    """Add selected mesh objects to the RMDoc list"""
    bl_idname = "em.rmdoc_add_selected"
    bl_label = "Add Selected"
    bl_description = "Add the selected mesh objects to the RMDoc list (they become document quads after linking)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' and obj.select_get() for obj in context.view_layer.objects)

    def execute(self, context):
        scene = context.scene
        rmdoc_list = scene.rmdoc_list
        existing_names = {item.name for item in rmdoc_list}

        added = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            if obj.name in existing_names:
                continue
            item = rmdoc_list.add()
            item.name = obj.name
            item.object_exists = True
            added += 1

        if added > 0:
            scene.rmdoc_list_index = len(rmdoc_list) - 1
            self.report({'INFO'}, f"Added {added} object{'s' if added > 1 else ''} to RMDoc list")
        else:
            self.report({'INFO'}, "No new objects to add (already in list or not mesh)")
        return {'FINISHED'}


class RMDOC_OT_search_document(bpy.types.Operator):
    """Search and select a document to link to this RMDoc object"""
    bl_idname = "em.rmdoc_search_document"
    bl_label = "Link to Document"
    bl_description = "Search for a document to associate with this RMDoc object"
    bl_options = {'REGISTER', 'INTERNAL'}

    rmdoc_index: IntProperty(default=-1)  # type: ignore
    search_query: StringProperty(name="Search", default="")  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.scene.em_tools.active_file_index >= 0

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "search_query", text="", icon='VIEWZOOM')
        layout.separator()

        em_tools = context.scene.em_tools
        if em_tools.active_file_index < 0:
            layout.label(text="No active graph", icon='ERROR')
            return

        try:
            from s3dgraphy import get_graph
            graph_info = em_tools.graphml_files[em_tools.active_file_index]
            graph = get_graph(graph_info.name)
        except Exception:
            graph = None

        if not graph:
            layout.label(text="Graph not loaded", icon='ERROR')
            return

        # Build set of already-used doc_node_ids
        used_doc_ids = {item.doc_node_id for item in context.scene.rmdoc_list if item.doc_node_id}

        # Filter document nodes by search query
        doc_nodes = []
        for node in graph.nodes:
            if not (hasattr(node, 'node_type') and node.node_type == 'document'):
                continue
            node_name = getattr(node, 'name', '')
            node_desc = getattr(node, 'description', '')
            search_lower = self.search_query.lower()
            if (not self.search_query or
                    search_lower in node_name.lower() or
                    search_lower in node_desc.lower()):
                doc_nodes.append(node)

        doc_nodes.sort(key=lambda n: n.name)

        if doc_nodes:
            from .. import icons_manager
            box = layout.box()
            doc_icon = icons_manager.get_icon_value("document")
            box.label(text=f"Found {len(doc_nodes)} documents:", icon_value=doc_icon if doc_icon else 0)

            for node in doc_nodes[:20]:
                row = box.row(align=True)
                is_used = node.node_id in used_doc_ids
                label = f"{node.name} — {node.description}" if node.description else node.name
                if is_used:
                    label = f"⚠ {label} (already linked)"

                if doc_icon and not is_used:
                    op = row.operator("em.rmdoc_assign_document",
                                      text=label, icon_value=doc_icon)
                elif is_used:
                    op = row.operator("em.rmdoc_assign_document",
                                      text=label, icon='ERROR')
                else:
                    op = row.operator("em.rmdoc_assign_document",
                                      text=label, icon='FILE')
                op.rmdoc_index = self.rmdoc_index
                op.doc_node_id = node.node_id
                op.doc_name = node.name

            if len(doc_nodes) > 20:
                box.label(text=f"...and {len(doc_nodes) - 20} more. Refine your search.",
                          icon='INFO')
        else:
            layout.label(text="No documents found", icon='INFO')

    def execute(self, context):
        return {'FINISHED'}


class RMDOC_OT_assign_document(bpy.types.Operator):
    """Assign a document to an RMDoc object"""
    bl_idname = "em.rmdoc_assign_document"
    bl_label = "Assign Document"
    bl_description = "Link this RMDoc quad to an existing document from the catalog"
    bl_options = {'REGISTER', 'UNDO'}

    rmdoc_index: IntProperty(default=-1)  # type: ignore
    doc_node_id: StringProperty()  # type: ignore
    doc_name: StringProperty()  # type: ignore

    def execute(self, context):
        scene = context.scene
        rmdoc_list = scene.rmdoc_list

        if self.rmdoc_index < 0 or self.rmdoc_index >= len(rmdoc_list):
            self.report({'ERROR'}, "Invalid RMDoc index")
            return {'CANCELLED'}

        # Guard: check if document is already linked to another RMDoc
        for i, item in enumerate(rmdoc_list):
            if item.doc_node_id == self.doc_node_id and i != self.rmdoc_index:
                self.report({'ERROR'},
                            f"Document '{self.doc_name}' is already linked to '{item.name}'")
                return {'CANCELLED'}

        item = rmdoc_list[self.rmdoc_index]
        item.doc_node_id = self.doc_node_id
        item.doc_name = self.doc_name

        # Set custom property on the scene object
        obj = bpy.data.objects.get(item.name)
        if obj:
            obj['em_doc_node_id'] = self.doc_node_id

        # Update description from doc_list
        for doc_item in scene.doc_list:
            if doc_item.node_id == self.doc_node_id:
                item.doc_description = doc_item.description
                item.certainty_class = doc_item.certainty_class
                break

        self.report({'INFO'}, f"Linked '{item.name}' → {self.doc_name}")
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# Shared helpers for quad / camera construction (Phase 1 refactor)
# ----------------------------------------------------------------------------

def _resolve_doc_from_context_or_id(scene, doc_node_id):
    """Return (doc_item, node_id) given an explicit node id or the active
    doc_list selection. Returns (None, "") on failure.
    """
    if doc_node_id:
        for d in scene.doc_list:
            if d.node_id == doc_node_id:
                return d, doc_node_id
        return None, ""
    idx = scene.doc_list_index
    if 0 <= idx < len(scene.doc_list):
        d = scene.doc_list[idx]
        return d, d.node_id
    return None, ""


def _apply_render_settings_from_image(scene, image, cam_data):
    """Match render resolution + pixel aspect + sensor_fit to the image.
    Shared helper — also called from look_through / pilot in Step 6 to
    preserve the 1:1 overlay invariant regardless of who created the
    camera.
    """
    if image and image.size[0] > 0 and image.size[1] > 0:
        scene.render.resolution_x = image.size[0]
        scene.render.resolution_y = image.size[1]
        scene.render.resolution_percentage = 100
        scene.render.pixel_aspect_x = 1.0
        scene.render.pixel_aspect_y = 1.0
    if cam_data is not None:
        cam_data.sensor_fit = 'HORIZONTAL'


def _resolve_quad_name(context, doc_name):
    """Return the quad object name using the graph prefix when available."""
    try:
        from ..operators.addon_prefix_helpers import node_name_to_proxy_name
        from ..functions import is_graph_available
        graph_ok, graph = is_graph_available(context)
        return node_name_to_proxy_name(
            doc_name, context=context,
            graph=graph if graph_ok else None)
    except Exception:
        return f"DocQuad_{doc_name}"


def _build_doc_material(doc_name, image, alpha):
    """Create a Principled BSDF material with the given image texture."""
    mat = bpy.data.materials.new(name=f"M_Doc_{doc_name}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex_node.image = image
    tex_node.location = (-460, 90)
    mat.node_tree.links.new(
        bsdf.inputs['Base Color'], tex_node.outputs['Color'])
    mat.node_tree.links.new(
        bsdf.outputs['BSDF'],
        mat.node_tree.nodes.get("Material Output").inputs[0])
    bsdf.inputs['Alpha'].default_value = alpha
    try:
        mat.blend_method = 'BLEND'
    except AttributeError:
        pass  # Blender 4.2+ auto-detects alpha
    return mat


def _viewport_placement_matrix(context, quad_width, quad_height):
    """Return a 4×4 world matrix placing a quad in front of the active
    3D Viewport, facing the viewer. Falls back to the 3D cursor when no
    viewport is available.

    The quad is placed at the viewport's focal point (view rotation
    center) so the user sees it immediately; its +Z axis points toward
    the viewer, its +X matches the view's right.
    """
    import mathutils
    scene = context.scene
    for area in context.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        r3d = area.spaces[0].region_3d
        # view_matrix.inverted() places us at the viewer looking down
        # its -Z; the view focal point is at local (0, 0, -view_distance).
        view_inv = r3d.view_matrix.inverted()
        focal = view_inv @ mathutils.Vector(
            (0.0, 0.0, -max(r3d.view_distance, 0.001)))
        # Orientation: keep view's axes so the quad faces the viewer.
        rot = view_inv.to_3x3().to_4x4()
        trans = mathutils.Matrix.Translation(focal)
        return trans @ rot
    # No viewport → cursor fallback with identity rotation.
    return mathutils.Matrix.Translation(scene.cursor.location)


def _build_quad_for_document(context, doc_item, image, placement_matrix=None,
                             width=1.0):
    """Create a textured quad for a document — no camera, no drivers.

    Args:
        context:           Blender context.
        doc_item:          DocItem from scene.doc_list.
        image:             loaded bpy.types.Image.
        placement_matrix:  4x4 world matrix for the quad; when None the
                           quad is placed at the current viewport's
                           focal point, facing the viewer.
        width:             quad width in meters; height is derived from
                           image aspect (h/w).

    Returns the new quad object (a MESH). Caller is responsible for
    installing a camera and/or resyncing lists afterwards.
    """
    scene = context.scene
    alpha = scene.doc_settings.default_alpha

    dosco_col = _get_or_create_dosco_collection()
    quad_name = _resolve_quad_name(context, doc_item.name)

    if image.size[0] > 0 and image.size[1] > 0:
        aspect = image.size[1] / image.size[0]
    else:
        aspect = 1.0
    height = width * aspect

    if placement_matrix is None:
        placement_matrix = _viewport_placement_matrix(context, width, height)

    # Unit plane (1×1 after the 0.5 resize), UV mapped.
    bpy.ops.mesh.primitive_plane_add()
    quad_obj = bpy.context.active_object
    quad_obj.name = quad_name
    bpy.ops.object.editmode_toggle()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.transform.resize(value=(0.5, 0.5, 0.5))
    bpy.ops.uv.smart_project(angle_limit=66, island_margin=0, area_weight=0)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.transform.rotate(value=1.5708, orient_axis='Z')
    bpy.ops.object.editmode_toggle()

    # Apply world placement, then scale freely from image aspect.
    quad_obj.matrix_world = placement_matrix
    quad_obj.scale = (width, height, 1.0)

    # Move into DosCo collection.
    for col in list(quad_obj.users_collection):
        col.objects.unlink(quad_obj)
    dosco_col.objects.link(quad_obj)

    # Material.
    mat = _build_doc_material(doc_item.name, image, alpha)
    if quad_obj.data.materials:
        quad_obj.data.materials[0] = mat
    else:
        quad_obj.data.materials.append(mat)

    # Tags.
    quad_obj['em_doc_node_id'] = doc_item.node_id
    quad_obj['em_dimensions_type'] = 'SYMBOLIC'

    return quad_obj


def _build_camera_quad_driven(context, quad_obj, image, focal=None):
    """Create a camera that frames ``quad_obj`` and is parented to it.

    No scale drivers are installed — the quad keeps its authored
    dimensions and the camera follows the quad through parenting. Uses
    the default focal length from DocManagerSettings unless overridden.

    Returns the new camera object.
    """
    scene = context.scene
    if focal is None:
        focal = scene.doc_settings.default_focal_length

    dosco_col = _get_or_create_dosco_collection()

    cam_data = bpy.data.cameras.new(name=f"Cam_Doc_{quad_obj.name}")
    cam_data.lens = focal
    cam_obj = bpy.data.objects.new(
        name=f"Cam_Doc_{quad_obj.name}", object_data=cam_data)
    dosco_col.objects.link(cam_obj)

    # Distance chosen so the camera horizontal FOV exactly matches the
    # quad width. scale.x is the quad's world width (plane is unit at
    # scale=1). angle = 2 * atan((sensor_w/2) / focal); sensor_fit is
    # set to HORIZONTAL below via _apply_render_settings_from_image.
    quad_w = abs(quad_obj.scale.x)
    cam_data.sensor_fit = 'HORIZONTAL'
    sensor_w = cam_data.sensor_width
    fov = 2.0 * math.atan((sensor_w / 2.0) / focal)
    d = quad_w / (2.0 * math.tan(fov / 2.0))

    cam_obj.parent = quad_obj
    cam_obj.matrix_parent_inverse.identity()
    cam_obj.location = (0.0, 0.0, d)
    cam_obj.rotation_euler = (0.0, 0.0, 0.0)

    cam_data.clip_start = max(0.01, d - 0.1)
    cam_data.clip_end = d + 0.5

    _apply_render_settings_from_image(scene, image, cam_data)

    # Bidirectional pointers.
    quad_obj['em_camera_name'] = cam_obj.name
    cam_obj['em_quad_name'] = quad_obj.name

    return cam_obj


def _get_image_from_quad(quad_obj):
    """Return the ``bpy.types.Image`` referenced by the quad's material,
    or ``None`` when the quad has no textured material.
    """
    if not quad_obj or not quad_obj.data or not quad_obj.data.materials:
        return None
    mat = quad_obj.data.materials[0]
    if not mat or not mat.node_tree:
        return None
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image is not None:
            return node.image
    return None


def _image_aspect(image):
    """Return h/w of ``image``, or 1.0 when invalid."""
    if image and image.size[0] > 0 and image.size[1] > 0:
        return image.size[1] / image.size[0]
    return 1.0


def _reparent_keep_world(child, new_parent):
    """Reparent ``child`` to ``new_parent`` (or None) preserving its
    current world transform.

    Leaves ``matrix_parent_inverse`` at identity so the child's
    ``matrix_basis`` (i.e. its ``location``/``rotation``/``scale``
    attributes) ends up expressed relative to the new parent, which
    is what the scale drivers and the rest of the UI expect — in
    particular the ``LOC_Z`` driver variable reads from the local
    (basis) frame.
    """
    world = child.matrix_world.copy()
    child.parent = new_parent
    child.matrix_parent_inverse.identity()
    child.matrix_world = world


def _align_camera_to_quad(context, quad_obj, cam_obj, parent_to_quad=True):
    """Position ``cam_obj`` so it frames ``quad_obj`` exactly.

    When ``parent_to_quad`` is True the camera ends up as a child of
    the quad with a tidy local transform; otherwise the camera keeps
    its existing parent and is placed in world space.

    Works for both PERSP and ORTHO cameras: distance is computed from
    horizontal FOV in PERSP, and ``ortho_scale`` is set to the quad's
    world width in ORTHO.
    """
    scene = context.scene
    cam_data = cam_obj.data

    # Quad world width = scale.x (unit plane, ±0.5 verts).
    quad_w = abs(quad_obj.scale.x)
    if quad_w <= 0:
        quad_w = 1.0

    cam_data.sensor_fit = 'HORIZONTAL'

    if cam_data.type == 'ORTHO':
        cam_data.ortho_scale = quad_w
        d = max(2.0, quad_w)  # keep camera clear of quad for clip
    else:
        sensor_w = cam_data.sensor_width
        focal = cam_data.lens
        fov = 2.0 * math.atan((sensor_w / 2.0) / focal)
        d = quad_w / (2.0 * math.tan(fov / 2.0))

    cam_data.clip_start = max(0.01, d - 0.1)
    cam_data.clip_end = d + 0.5

    if parent_to_quad:
        cam_obj.parent = quad_obj
        cam_obj.matrix_parent_inverse.identity()
        cam_obj.location = (0.0, 0.0, d)
        cam_obj.rotation_euler = (0.0, 0.0, 0.0)
        cam_obj.scale = (1.0, 1.0, 1.0)
    else:
        # World-space placement along quad's local +Z axis, rotation
        # matched to the quad's so the camera's own -Z looks back at
        # the quad. We deliberately strip the quad's scale from the
        # composition — camera objects must stay unit-scale, otherwise
        # reparenting the quad under the camera later bakes wrong
        # values into the driver's ``depth`` variable.
        import mathutils  # local import to keep module header compact
        quad_world = quad_obj.matrix_world
        loc = quad_world.translation.copy()
        rot = quad_world.to_quaternion()
        rot_mat = rot.to_matrix().to_4x4()
        offset_world = rot @ mathutils.Vector((0.0, 0.0, d))
        cam_obj.matrix_world = (
            mathutils.Matrix.Translation(loc + offset_world) @ rot_mat
        )

    # Sync bidirectional pointers.
    quad_obj['em_camera_name'] = cam_obj.name
    cam_obj['em_quad_name'] = quad_obj.name

    # Render invariant.
    image = _get_image_from_quad(quad_obj)
    _apply_render_settings_from_image(scene, image, cam_data)


def _set_rmdoc_drive_mode(scene, quad_name, mode):
    """Set ``drive_mode`` on the RMDocItem matching ``quad_name``.

    Called after creation helpers finish so the UI and validators see
    the correct state. Silently no-ops when the item isn't in the list
    yet (the next sync_doc_list will classify it via migration).
    """
    for item in getattr(scene, 'rmdoc_list', []):
        if item.name == quad_name:
            item.drive_mode = mode
            return


# ----------------------------------------------------------------------------
# Creation operators
# ----------------------------------------------------------------------------

class RMDOC_OT_create_from_document(bpy.types.Operator):
    """Create a free-standing quad from the active document — no camera.

    Quad-first workflow: the quad is placed at the current 3D Viewport's
    focal point and oriented to face the viewer. A camera can be added
    afterwards via Create Camera or Set Drive Mode.
    """
    bl_idname = "em.rmdoc_create_from_document"
    bl_label = "Create from Document"
    bl_description = (
        "Create an image quad from the active document at the current "
        "viewport focal point, facing the viewer. No camera is created; "
        "add one later with Create Camera"
    )
    bl_options = {'REGISTER', 'UNDO'}

    doc_node_id: StringProperty(default="")  # type: ignore
    width: FloatProperty(
        name="Width",
        description="Quad width in meters (height follows image aspect)",
        default=1.0, min=0.001, soft_max=50.0, unit='LENGTH',
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        if context.scene.em_tools.active_file_index < 0:
            return False
        idx = context.scene.doc_list_index
        return 0 <= idx < len(context.scene.doc_list)

    def execute(self, context):
        scene = context.scene
        doc_item, doc_node_id = _resolve_doc_from_context_or_id(
            scene, self.doc_node_id)
        if not doc_item:
            self.report({'ERROR'}, "No document selected")
            return {'CANCELLED'}

        # Guard: 1:1 doc↔quad.
        for item in scene.rmdoc_list:
            if item.doc_node_id == doc_node_id:
                self.report(
                    {'ERROR'},
                    f"Document '{doc_item.name}' already has RMDoc '{item.name}'")
                return {'CANCELLED'}

        image_path = _resolve_doc_image_path(context, doc_item)
        if not image_path:
            self.report(
                {'ERROR'},
                f"Cannot resolve image for '{doc_item.name}'. Check DosCo directory.")
            return {'CANCELLED'}
        try:
            img = bpy.data.images.load(image_path, check_existing=True)
        except Exception as e:
            self.report({'ERROR'}, f"Cannot load image: {e}")
            return {'CANCELLED'}

        quad_obj = _build_quad_for_document(
            context, doc_item, img, placement_matrix=None, width=self.width)

        sync_doc_list(scene)
        _set_rmdoc_drive_mode(scene, quad_obj.name, 'NO_CAMERA')

        # Select the newly created record in the RMDoc UIList so the
        # user can immediately act on it (add camera, re-align, etc.).
        for i, rm_item in enumerate(scene.rmdoc_list):
            if rm_item.name == quad_obj.name:
                scene.rmdoc_list_index = i
                break

        from .ui import invalidate_doc_connection_cache
        invalidate_doc_connection_cache()

        self.report(
            {'INFO'},
            f"Created quad for {doc_item.name} (width={self.width:.2f}m, no camera)")
        return {'FINISHED'}


class RMDOC_OT_remove(bpy.types.Operator):
    """Delete RMDoc: removes quad and camera objects from the scene"""
    bl_idname = "em.rmdoc_remove"
    bl_label = "Delete RMDoc"
    bl_description = "Delete this RMDoc — removes both the quad and its camera from the scene"
    bl_options = {'REGISTER', 'UNDO'}

    rmdoc_index: IntProperty(default=-1)  # type: ignore

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        scene = context.scene
        rmdoc_list = scene.rmdoc_list
        idx = self.rmdoc_index

        if idx < 0 or idx >= len(rmdoc_list):
            self.report({'ERROR'}, "Invalid RMDoc index")
            return {'CANCELLED'}

        item = rmdoc_list[idx]
        obj_name = item.name
        deleted = []

        obj = bpy.data.objects.get(obj_name)
        if obj:
            # Delete camera first (child or referenced)
            cam_obj = _find_rmdoc_camera(obj)
            if cam_obj:
                cam_data = cam_obj.data
                bpy.data.objects.remove(cam_obj, do_unlink=True)
                # Clean up orphan camera data
                if cam_data and cam_data.users == 0:
                    bpy.data.cameras.remove(cam_data)
                deleted.append("camera")

            # Remove drivers before deleting (avoids Blender warnings)
            try:
                obj.driver_remove('scale', 0)
                obj.driver_remove('scale', 1)
            except Exception:
                pass

            # Delete the quad object
            mesh_data = obj.data if obj.type == 'MESH' else None
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh_data and mesh_data.users == 0:
                bpy.data.meshes.remove(mesh_data)
            deleted.append("quad")

        # Remove from list
        rmdoc_list.remove(idx)

        # Adjust index
        if scene.rmdoc_list_index >= len(rmdoc_list):
            scene.rmdoc_list_index = max(0, len(rmdoc_list) - 1)

        parts = " + ".join(deleted) if deleted else "entry"
        self.report({'INFO'}, f"Deleted {parts} for '{obj_name}'")
        return {'FINISHED'}


class RMDOC_OT_create_camera(bpy.types.Operator):
    """Create a camera that frames this RMDoc quad (camera-driven).

    The camera is placed in world space along the quad's normal at the
    distance needed to fit the quad into its horizontal FOV (or
    ortho_scale for ORTHO cameras). The quad is then reparented to the
    camera and scale drivers are installed — moving the camera carries
    the quad along.
    """
    bl_idname = "em.rmdoc_create_camera"
    bl_label = "Create Camera"
    bl_description = (
        "Create a camera aligned to this quad (camera-driven). The quad "
        "becomes child of the camera and fills its frustum via drivers"
    )
    bl_options = {'REGISTER', 'UNDO'}

    object_name: StringProperty()  # type: ignore

    def execute(self, context):
        from .drivers import install_scale_drivers

        quad_obj = bpy.data.objects.get(self.object_name)
        if not quad_obj:
            self.report({'ERROR'}, f"Object '{self.object_name}' not found")
            return {'CANCELLED'}

        scene = context.scene
        focal = scene.doc_settings.default_focal_length

        dosco_col = _get_or_create_dosco_collection()
        cam_data = bpy.data.cameras.new(name=f"Cam_{self.object_name}")
        cam_data.lens = focal
        cam_obj = bpy.data.objects.new(
            name=f"Cam_{self.object_name}", object_data=cam_data)
        dosco_col.objects.link(cam_obj)

        # Align camera in world space to frame the quad exactly.
        _align_camera_to_quad(context, quad_obj, cam_obj,
                              parent_to_quad=False)

        # Reparent quad to camera (keep world transform) — the camera
        # now leads the quad through the parent chain.
        _reparent_keep_world(quad_obj, cam_obj)

        # Install scale drivers so the quad fills the frustum.
        image = _get_image_from_quad(quad_obj)
        install_scale_drivers(quad_obj, cam_obj, _image_aspect(image))
        bpy.context.view_layer.update()

        quad_obj['em_camera_name'] = cam_obj.name
        cam_obj['em_quad_name'] = quad_obj.name

        sync_doc_list(scene)
        _set_rmdoc_drive_mode(scene, quad_obj.name, 'CAMERA_DRIVEN')
        self.report(
            {'INFO'},
            f"Created camera for {self.object_name} "
            f"(camera-driven, f={focal:.0f}mm)")
        return {'FINISHED'}


class RMDOC_OT_remove_camera(bpy.types.Operator):
    """Remove the camera linked to this quad — keeps the quad in place.

    Use this as the "start" button for a free-move workflow: remove
    the camera, reposition the quad freely in 3D, then press Create
    Camera to rebuild a camera aligned to the quad's new pose.
    """
    bl_idname = "em.rmdoc_remove_camera"
    bl_label = "Remove Camera"
    bl_description = (
        "Delete the linked camera and detach the quad. The quad stays "
        "where it is; use Create Camera afterwards to rebuild a camera "
        "aligned to the quad's new position"
    )
    bl_options = {'REGISTER', 'UNDO'}

    object_name: StringProperty()  # type: ignore

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        from .drivers import freeze_scale_from_drivers

        quad_obj = bpy.data.objects.get(self.object_name)
        if not quad_obj:
            self.report({'ERROR'}, f"Object '{self.object_name}' not found")
            return {'CANCELLED'}

        cam_obj = _find_rmdoc_camera(quad_obj)
        if cam_obj is None:
            self.report({'WARNING'}, "No camera linked to this quad")
            return {'CANCELLED'}

        # Freeze any scale drivers first so the quad keeps its current
        # visible size after the camera is gone.
        freeze_scale_from_drivers(quad_obj)

        # Detach parent links (keep world transform) before deleting so
        # the quad does not jump.
        if quad_obj.parent == cam_obj:
            _reparent_keep_world(quad_obj, None)
        if cam_obj.parent == quad_obj:
            _reparent_keep_world(cam_obj, None)

        cam_data = cam_obj.data
        bpy.data.objects.remove(cam_obj, do_unlink=True)
        if cam_data and cam_data.users == 0:
            bpy.data.cameras.remove(cam_data)

        quad_obj['em_camera_name'] = ''

        sync_doc_list(context.scene)
        _set_rmdoc_drive_mode(context.scene, quad_obj.name, 'NO_CAMERA')

        self.report({'INFO'}, f"Removed camera for {self.object_name}")
        return {'FINISHED'}


class RMDOC_OT_look_through(bpy.types.Operator):
    """Look through camera and fit render resolution to image dimensions"""
    bl_idname = "em.rmdoc_look_through"
    bl_label = "Look Through Camera"
    bl_description = "Switch the viewport to this RMDoc's camera and fit render resolution to the image"

    object_name: StringProperty()  # type: ignore

    def execute(self, context):
        item, _ = _find_rmdoc_item_by_name(context.scene, self.object_name)
        if item:
            health = check_rmdoc_item(item)
            if health.orphan:
                self.report({'ERROR'}, f"Quad '{self.object_name}' is missing — use Repair")
                return {'CANCELLED'}
            if health.needs_camera_repair:
                item.has_camera = False
                item.camera_object_name = ""
                disable_pilot(context)
                self.report({'WARNING'}, "Camera missing — flag reset. Please create camera again.")
                return {'CANCELLED'}

        quad_obj = bpy.data.objects.get(self.object_name)
        if not quad_obj:
            return {'CANCELLED'}

        cam_obj = _find_rmdoc_camera(quad_obj)
        if not cam_obj:
            self.report({'ERROR'}, "No camera found for this object")
            return {'CANCELLED'}

        # Set render resolution from image pixels so camera frame matches exactly
        img = self._get_quad_image(quad_obj)
        if img and img.size[0] > 0 and img.size[1] > 0:
            context.scene.render.resolution_x = img.size[0]
            context.scene.render.resolution_y = img.size[1]
            context.scene.render.resolution_percentage = 100
            context.scene.render.pixel_aspect_x = 1.0
            context.scene.render.pixel_aspect_y = 1.0
            # Match camera sensor to image aspect for perfect overlay
            cam_data = cam_obj.data
            cam_data.sensor_fit = 'HORIZONTAL'

        context.scene.camera = cam_obj
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces[0].region_3d.view_perspective = 'CAMERA'
                break

        return {'FINISHED'}

    @staticmethod
    def _get_quad_image(quad_obj):
        """Extract the image from the quad's material, if any."""
        if not quad_obj.data or not quad_obj.data.materials:
            return None
        mat = quad_obj.data.materials[0]
        if not mat or not mat.use_nodes:
            return None
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                return node.image
        return None


class RMDOC_OT_pilot_camera(bpy.types.Operator):
    """Toggle camera piloting — navigate inside camera view, moving camera and quad"""
    bl_idname = "em.rmdoc_pilot_camera"
    bl_label = "Pilot Camera"
    bl_description = "Toggle camera pilot mode — viewport navigation drives the camera (and the quad if parented)"

    object_name: StringProperty()  # type: ignore

    def execute(self, context):
        item, _ = _find_rmdoc_item_by_name(context.scene, self.object_name)
        if item:
            health = check_rmdoc_item(item)
            if health.orphan:
                self.report({'ERROR'}, f"Quad '{self.object_name}' is missing — use Repair")
                disable_pilot(context)
                return {'CANCELLED'}
            if health.needs_camera_repair:
                item.has_camera = False
                item.camera_object_name = ""
                disable_pilot(context)
                self.report({'WARNING'}, "Camera missing — flag reset. Please create camera again.")
                return {'CANCELLED'}

        quad_obj = bpy.data.objects.get(self.object_name)
        if not quad_obj:
            return {'CANCELLED'}

        cam_obj = _find_rmdoc_camera(quad_obj)
        if not cam_obj:
            self.report({'ERROR'}, "No camera found for this object")
            return {'CANCELLED'}

        doc_settings = context.scene.doc_settings
        is_piloting = doc_settings.is_piloting_camera

        # Find the 3D viewport
        space = None
        region_3d = None
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces[0]
                region_3d = space.region_3d
                break

        if not space or not region_3d:
            self.report({'ERROR'}, "No 3D Viewport found")
            return {'CANCELLED'}

        if is_piloting:
            disable_pilot(context)
            self.report({'INFO'}, "Camera unlocked")
        else:
            # Turn ON: enter camera view, lock
            context.scene.camera = cam_obj
            region_3d.view_perspective = 'CAMERA'
            space.lock_camera = True
            doc_settings.is_piloting_camera = True
            self.report({'INFO'}, "Piloting camera — navigate to reposition")

        return {'FINISHED'}


class RMDOC_OT_set_alpha(bpy.types.Operator):
    """Set the transparency of the document quad image"""
    bl_idname = "em.rmdoc_set_alpha"
    bl_label = "Set Alpha"
    bl_description = "Set the transparency of this quad's material (0 = transparent, 1 = opaque)"
    bl_options = {'REGISTER', 'UNDO'}

    object_name: StringProperty()  # type: ignore
    alpha: FloatProperty(
        name="Alpha", default=0.5, min=0.0, max=1.0,
        description="Image transparency (0 = fully transparent, 1 = opaque)"
    )  # type: ignore

    def execute(self, context):
        obj = bpy.data.objects.get(self.object_name)
        if not obj or not obj.data or not obj.data.materials:
            self.report({'WARNING'}, "No material found on quad")
            return {'CANCELLED'}

        mat = obj.data.materials[0]
        if mat and mat.use_nodes:
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bsdf.inputs['Alpha'].default_value = self.alpha
                try:
                    mat.blend_method = 'BLEND' if self.alpha < 1.0 else 'OPAQUE'
                except AttributeError:
                    pass  # Blender 4.2+
        return {'FINISHED'}


class RMDOC_OT_toggle_ortho(bpy.types.Operator):
    """Toggle camera between perspective and orthographic mode"""
    bl_idname = "em.rmdoc_toggle_ortho"
    bl_label = "Toggle Ortho"
    bl_description = "Switch this camera between perspective and orthographic projection (preserves framing)"
    bl_options = {'REGISTER', 'UNDO'}

    object_name: StringProperty()  # type: ignore

    def execute(self, context):
        quad_obj = bpy.data.objects.get(self.object_name)
        if not quad_obj:
            return {'CANCELLED'}

        cam_obj = _find_rmdoc_camera(quad_obj)
        if not cam_obj:
            self.report({'ERROR'}, "No camera found")
            return {'CANCELLED'}

        cam_data = cam_obj.data
        if cam_data.type == 'PERSP':
            # Switch to orthographic
            cam_data.type = 'ORTHO'
            # Compute ortho_scale from quad's apparent size at its depth
            # The quad sits at local Z = -depth from camera
            depth = abs(quad_obj.location.z) if quad_obj.parent == cam_obj else 2.0
            # In perspective: apparent half-width = depth * tan(fov/2)
            # ortho_scale = 2 * apparent half-width
            fov = cam_data.angle  # radians
            cam_data.ortho_scale = 2.0 * depth * math.tan(fov / 2.0)
            # Set tight clip for isolating the quad view
            cam_data.clip_start = max(0.001, depth - 0.5)
            cam_data.clip_end = depth + 0.5
            self.report({'INFO'}, f"Ortho mode (scale={cam_data.ortho_scale:.2f}m, clip={cam_data.clip_start:.2f}-{cam_data.clip_end:.2f})")
        else:
            # Switch back to perspective
            cam_data.type = 'PERSP'
            cam_data.clip_start = 0.1
            cam_data.clip_end = 1000.0
            self.report({'INFO'}, "Perspective mode")

        return {'FINISHED'}


class RMDOC_OT_autocrop_near(bpy.types.Operator):
    """Set near clip just before the document quad"""
    bl_idname = "em.rmdoc_autocrop_near"
    bl_label = "Auto Near"
    bl_description = "Set near clip just before the quad plane"
    bl_options = {'REGISTER', 'UNDO'}

    object_name: StringProperty()  # type: ignore

    def execute(self, context):
        quad_obj = bpy.data.objects.get(self.object_name)
        if not quad_obj:
            return {'CANCELLED'}

        cam_obj = _find_rmdoc_camera(quad_obj)
        if not cam_obj:
            self.report({'ERROR'}, "No camera found")
            return {'CANCELLED'}

        dist = _camera_quad_distance(cam_obj, quad_obj)
        cam_data = cam_obj.data
        cam_data.clip_start = max(0.01, dist - 0.1)

        self.report({'INFO'}, f"Near clip: {cam_data.clip_start:.2f} (quad at {dist:.2f}m)")
        return {'FINISHED'}


class RMDOC_OT_autocrop_far(bpy.types.Operator):
    """Set far clip just behind the document quad"""
    bl_idname = "em.rmdoc_autocrop_far"
    bl_label = "Auto Far"
    bl_description = "Set far clip just behind the quad plane"
    bl_options = {'REGISTER', 'UNDO'}

    object_name: StringProperty()  # type: ignore

    def execute(self, context):
        quad_obj = bpy.data.objects.get(self.object_name)
        if not quad_obj:
            return {'CANCELLED'}

        cam_obj = _find_rmdoc_camera(quad_obj)
        if not cam_obj:
            self.report({'ERROR'}, "No camera found")
            return {'CANCELLED'}

        dist = _camera_quad_distance(cam_obj, quad_obj)
        cam_data = cam_obj.data
        cam_data.clip_end = dist + 0.5

        self.report({'INFO'}, f"Far clip: {cam_data.clip_end:.2f} (quad at {dist:.2f}m)")
        return {'FINISHED'}


class RMDOC_OT_fly(bpy.types.Operator):
    """Enter fly navigation mode in the 3D viewport"""
    bl_idname = "em.rmdoc_fly"
    bl_label = "Fly"
    bl_description = "Enter fly navigation mode to move camera interactively"

    def execute(self, context):
        # Ensure we are in a 3D viewport context
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                with context.temp_override(area=area, region=area.regions[-1]):
                    bpy.ops.view3d.fly('INVOKE_DEFAULT')
                return {'FINISHED'}
        self.report({'WARNING'}, "No 3D viewport found")
        return {'CANCELLED'}


class RMDOC_OT_open_document(bpy.types.Operator):
    """Open the document file linked to this RMDoc object"""
    bl_idname = "em.rmdoc_open_document"
    bl_label = "Open Document"
    bl_description = "Open the source file of the document linked to this RMDoc"

    doc_node_id: StringProperty()  # type: ignore

    def execute(self, context):
        for doc_item in context.scene.doc_list:
            if doc_item.node_id == self.doc_node_id:
                if doc_item.url:
                    import subprocess
                    import sys
                    from ..functions import is_valid_url

                    if is_valid_url(doc_item.url):
                        bpy.ops.wm.url_open(url=doc_item.url)
                        return {'FINISHED'}

                    image_path = _resolve_doc_image_path(context, doc_item)
                    if image_path and os.path.exists(image_path):
                        try:
                            if os.name == "nt":
                                os.startfile(image_path)
                            elif os.name == "posix":
                                opener = "open" if sys.platform == "darwin" else "xdg-open"
                                subprocess.run([opener, image_path])
                            return {'FINISHED'}
                        except Exception as e:
                            self.report({'WARNING'}, f"Cannot open file: {e}")
                            return {'CANCELLED'}

                self.report({'WARNING'}, "No URL set for this document")
                return {'CANCELLED'}

        self.report({'WARNING'}, "Document not found in catalog")
        return {'CANCELLED'}


class RMDOC_OT_repair(bpy.types.Operator):
    """Repair inconsistent RMDoc state (missing cameras, orphan items, stuck pilot)"""
    bl_idname = "em.rmdoc_repair"
    bl_label = "Repair RMDoc"
    bl_description = "Fix inconsistent RMDoc state: reset stale flags, remove orphan items"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        items=[
            ('RESET_CAMERA_FLAG', "Reset Camera Flag", "Clear has_camera flag for items whose camera object is missing"),
            ('REMOVE_ORPHAN', "Remove Orphan Item", "Remove an RMDoc item whose quad object has been deleted"),
            ('FULL_SWEEP', "Full Sweep", "Run all repair operations on the whole RMDoc list"),
        ],
        default='FULL_SWEEP',
    )  # type: ignore
    rmdoc_index: IntProperty(default=-1)  # type: ignore

    def execute(self, context):
        scene = context.scene
        fixed = 0

        if self.mode == 'FULL_SWEEP':
            ds = getattr(scene, 'doc_settings', None)
            if ds and ds.is_piloting_camera:
                active_cam = scene.camera
                if not active_cam or active_cam.type != 'CAMERA':
                    disable_pilot(context)
                    fixed += 1

        if not hasattr(scene, 'rmdoc_list'):
            self.report({'INFO'}, f"RMDoc repair: fixed {fixed} issue(s)")
            return {'FINISHED'}

        if self.mode in {'RESET_CAMERA_FLAG', 'FULL_SWEEP'}:
            if 0 <= self.rmdoc_index < len(scene.rmdoc_list):
                items = [scene.rmdoc_list[self.rmdoc_index]]
            else:
                items = list(scene.rmdoc_list)
            for item in items:
                h = check_rmdoc_item(item)
                if h.needs_camera_repair:
                    item.has_camera = False
                    item.camera_object_name = ""
                    fixed += 1

        if self.mode in {'REMOVE_ORPHAN', 'FULL_SWEEP'}:
            if 0 <= self.rmdoc_index < len(scene.rmdoc_list):
                # Singolo item — rimuovi solo se orfano
                item = scene.rmdoc_list[self.rmdoc_index]
                if check_rmdoc_item(item).orphan:
                    scene.rmdoc_list.remove(self.rmdoc_index)
                    if scene.rmdoc_list_index >= len(scene.rmdoc_list):
                        scene.rmdoc_list_index = max(0, len(scene.rmdoc_list) - 1)
                    fixed += 1
            else:
                # Sweep totale
                to_remove = [i for i, item in enumerate(scene.rmdoc_list)
                             if check_rmdoc_item(item).orphan]
                for i in reversed(to_remove):
                    scene.rmdoc_list.remove(i)
                    fixed += 1
                if scene.rmdoc_list_index >= len(scene.rmdoc_list):
                    scene.rmdoc_list_index = max(0, len(scene.rmdoc_list) - 1)

        self.report({'INFO'}, f"RMDoc repair: fixed {fixed} issue(s)")
        return {'FINISHED'}


# ============================================================================
# DRIVE MODE / RE-ALIGN (Phase 1 refactor)
# ============================================================================


def _find_rmdoc_item_for_quad(scene, quad_name):
    for item in getattr(scene, 'rmdoc_list', []):
        if item.name == quad_name:
            return item
    return None


class RMDOC_OT_set_drive_mode(bpy.types.Operator):
    """Switch the Quad↔Camera relationship for an RMDoc.

    Handles reparenting (preserving world transform), driver install /
    freeze, and camera creation/removal per the target mode.
    """
    bl_idname = "em.rmdoc_set_drive_mode"
    bl_label = "Set Drive Mode"
    bl_description = (
        "Switch the quad↔camera relationship: Quad-driven (camera follows "
        "quad), Camera-driven (quad fills frustum), Unlinked (independent), "
        "No Camera (quad only)"
    )
    bl_options = {'REGISTER', 'UNDO'}

    object_name: StringProperty()  # type: ignore
    mode: EnumProperty(
        items=[
            ('NO_CAMERA',     "No Camera",     "Remove the camera; keep only the quad"),
            ('QUAD_DRIVEN',   "Quad-driven",   "Camera is child of quad; moving quad moves camera"),
            ('CAMERA_DRIVEN', "Camera-driven", "Quad is child of camera; quad fills frustum via drivers"),
            ('UNLINKED',      "Unlinked",      "Quad and camera coexist but are independent"),
        ],
    )  # type: ignore

    def invoke(self, context, event):
        # Confirm before destructive transitions (camera removal).
        if self.mode == 'NO_CAMERA':
            quad_obj = bpy.data.objects.get(self.object_name)
            if quad_obj and _find_rmdoc_camera(quad_obj):
                return context.window_manager.invoke_confirm(self, event)
        return self.execute(context)

    def execute(self, context):
        from .drivers import (
            install_scale_drivers,
            freeze_scale_from_drivers,
            remove_scale_drivers,
        )

        scene = context.scene
        quad_obj = bpy.data.objects.get(self.object_name)
        if not quad_obj:
            self.report({'ERROR'}, f"Quad '{self.object_name}' not found")
            return {'CANCELLED'}

        item = _find_rmdoc_item_for_quad(scene, self.object_name)
        cam_obj = _find_rmdoc_camera(quad_obj)
        image = _get_image_from_quad(quad_obj)
        aspect = _image_aspect(image)

        # --- Ensure we have a camera when the target mode needs one ---
        if self.mode in {'QUAD_DRIVEN', 'CAMERA_DRIVEN', 'UNLINKED'} and cam_obj is None:
            cam_obj = _build_camera_quad_driven(context, quad_obj, image)
            # _build_camera_quad_driven already parents cam to quad;
            # further reparenting below will adjust if the mode needs it.

        # --- Leaving CAMERA_DRIVEN: freeze drivers before anything else ---
        if self.mode != 'CAMERA_DRIVEN':
            # Freeze (or remove) whatever driver state is currently
            # present. freeze_scale_from_drivers is a no-op when there
            # are no drivers.
            freeze_scale_from_drivers(quad_obj)

        # --- Apply target mode ---
        if self.mode == 'NO_CAMERA':
            remove_scale_drivers(quad_obj)
            if cam_obj is not None:
                # Detach parent relations first to keep world transforms.
                if quad_obj.parent == cam_obj:
                    _reparent_keep_world(quad_obj, None)
                cam_data = cam_obj.data
                bpy.data.objects.remove(cam_obj, do_unlink=True)
                if cam_data and cam_data.users == 0:
                    bpy.data.cameras.remove(cam_data)
                quad_obj['em_camera_name'] = ''

        elif self.mode == 'QUAD_DRIVEN':
            # Camera must be child of quad.
            if quad_obj.parent == cam_obj:
                # Legacy layout: quad is child of camera. Swap direction.
                _reparent_keep_world(quad_obj, None)
            if cam_obj.parent != quad_obj:
                _reparent_keep_world(cam_obj, quad_obj)
            # Refresh clip/ortho for the new parenting.
            _align_camera_to_quad(context, quad_obj, cam_obj,
                                  parent_to_quad=True)

        elif self.mode == 'CAMERA_DRIVEN':
            # Legacy PhotogrTool layout: quad is child of camera.
            if cam_obj.parent == quad_obj:
                _reparent_keep_world(cam_obj, None)
            if quad_obj.parent != cam_obj:
                _reparent_keep_world(quad_obj, cam_obj)
            install_scale_drivers(quad_obj, cam_obj, aspect)
            bpy.context.view_layer.update()

        elif self.mode == 'UNLINKED':
            # Neither object is the parent of the other.
            if quad_obj.parent == cam_obj:
                _reparent_keep_world(quad_obj, None)
            if cam_obj.parent == quad_obj:
                _reparent_keep_world(cam_obj, None)

        # Pointers + item state.
        if cam_obj is not None and self.mode != 'NO_CAMERA':
            quad_obj['em_camera_name'] = cam_obj.name
            cam_obj['em_quad_name'] = quad_obj.name

        sync_doc_list(scene)
        _set_rmdoc_drive_mode(scene, quad_obj.name, self.mode)

        self.report({'INFO'}, f"Drive mode: {self.mode}")
        return {'FINISHED'}


class RMDOC_OT_realign(bpy.types.Operator):
    """Re-align the quad↔camera pair after one side was moved.

    Mode-aware: in QUAD_DRIVEN mode this moves the camera to frame the
    quad; in CAMERA_DRIVEN mode it refreshes the drivers so the quad
    fills the camera frustum again. Disabled in UNLINKED / NO_CAMERA.
    """
    bl_idname = "em.rmdoc_realign"
    bl_label = "Re-align"
    bl_description = (
        "Restore alignment between quad and camera. In Quad-driven mode "
        "the camera is moved to frame the quad; in Camera-driven mode "
        "the quad is re-fitted to the camera frustum"
    )
    bl_options = {'REGISTER', 'UNDO'}

    object_name: StringProperty()  # type: ignore

    def execute(self, context):
        from .drivers import install_scale_drivers

        scene = context.scene
        quad_obj = bpy.data.objects.get(self.object_name)
        if not quad_obj:
            self.report({'ERROR'}, f"Quad '{self.object_name}' not found")
            return {'CANCELLED'}

        item = _find_rmdoc_item_for_quad(scene, self.object_name)
        mode = item.drive_mode if item else ''
        cam_obj = _find_rmdoc_camera(quad_obj)
        if cam_obj is None:
            self.report({'ERROR'}, "No camera associated with this quad")
            return {'CANCELLED'}

        if mode == 'QUAD_DRIVEN':
            _align_camera_to_quad(
                context, quad_obj, cam_obj,
                parent_to_quad=(cam_obj.parent == quad_obj))
            self.report({'INFO'}, "Camera re-aligned to quad")
            return {'FINISHED'}

        if mode == 'CAMERA_DRIVEN':
            image = _get_image_from_quad(quad_obj)
            install_scale_drivers(quad_obj, cam_obj, _image_aspect(image))
            bpy.context.view_layer.update()
            self.report({'INFO'}, "Drivers refreshed; quad re-fits frustum")
            return {'FINISHED'}

        self.report({'WARNING'},
                    f"Re-align is not applicable in mode '{mode or 'UNKNOWN'}'")
        return {'CANCELLED'}


# ============================================================================
# REGISTRATION
# ============================================================================

classes = (
    DOCMANAGER_OT_sync,
    DOCMANAGER_OT_import_image,
    DOCMANAGER_OT_create_camera,
    DOCMANAGER_OT_look_through,
    DOCMANAGER_OT_open_url,
    DOCMANAGER_OT_select_scene_object,
    DOCMANAGER_OT_rename_object,
    DOCMANAGER_OT_select_linked,
    DOCMANAGER_OT_select_linked_entity,
    DOCMANAGER_OT_select_all_linked_us,
    DOCMANAGER_OT_create_document,
    DOCMANAGER_OT_suggest_next_doc_name_for_dialog,
    DOCMANAGER_OT_create_master_document,
    DOCMANAGER_OT_edit_classification,
    RMDOC_OT_select_object,
    RMDOC_OT_add_selected,
    RMDOC_OT_search_document,
    RMDOC_OT_assign_document,
    RMDOC_OT_create_from_document,
    RMDOC_OT_set_drive_mode,
    RMDOC_OT_realign,
    RMDOC_OT_remove,
    RMDOC_OT_create_camera,
    RMDOC_OT_remove_camera,
    RMDOC_OT_look_through,
    RMDOC_OT_pilot_camera,
    RMDOC_OT_set_alpha,
    RMDOC_OT_toggle_ortho,
    RMDOC_OT_autocrop_near,
    RMDOC_OT_autocrop_far,
    RMDOC_OT_fly,
    RMDOC_OT_open_document,
    RMDOC_OT_repair,
)


def register_operators():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister_operators():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
