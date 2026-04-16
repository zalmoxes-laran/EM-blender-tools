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


class RMDOC_OT_create_from_document(bpy.types.Operator):
    """Create a quad+camera from a document, positioned at current viewport"""
    bl_idname = "em.rmdoc_create_from_document"
    bl_label = "Create from Document"
    bl_description = "Create an image quad with camera from the active document"
    bl_options = {'REGISTER', 'UNDO'}

    doc_node_id: StringProperty(default="")  # type: ignore

    @classmethod
    def poll(cls, context):
        # Either doc_node_id will be passed, or use active doc_list item
        if context.scene.em_tools.active_file_index < 0:
            return False
        idx = context.scene.doc_list_index
        return 0 <= idx < len(context.scene.doc_list)

    def execute(self, context):
        scene = context.scene

        # Resolve which document to use
        doc_node_id = self.doc_node_id
        doc_item = None
        if doc_node_id:
            for d in scene.doc_list:
                if d.node_id == doc_node_id:
                    doc_item = d
                    break
        else:
            idx = scene.doc_list_index
            if 0 <= idx < len(scene.doc_list):
                doc_item = scene.doc_list[idx]
                doc_node_id = doc_item.node_id

        if not doc_item:
            self.report({'ERROR'}, "No document selected")
            return {'CANCELLED'}

        # Guard: check document doesn't already have an RMDoc
        for item in scene.rmdoc_list:
            if item.doc_node_id == doc_node_id:
                self.report({'ERROR'},
                            f"Document '{doc_item.name}' already has RMDoc '{item.name}'")
                return {'CANCELLED'}

        # Resolve image path
        image_path = _resolve_doc_image_path(context, doc_item)
        if not image_path:
            self.report({'ERROR'},
                        f"Cannot resolve image for '{doc_item.name}'. Check DosCo directory.")
            return {'CANCELLED'}

        # Load image
        try:
            img = bpy.data.images.load(image_path, check_existing=True)
        except Exception as e:
            self.report({'ERROR'}, f"Cannot load image: {e}")
            return {'CANCELLED'}

        # Get current viewport position
        region_3d = None
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                region_3d = area.spaces[0].region_3d
                break
        if not region_3d:
            self.report({'ERROR'}, "No 3D Viewport found")
            return {'CANCELLED'}

        view_matrix = region_3d.view_matrix.inverted()
        focal = scene.doc_settings.default_focal_length
        alpha = scene.doc_settings.default_alpha
        depth = 2.0

        # Get or create DosCo collection
        dosco_col = _get_or_create_dosco_collection()

        # --- Create camera ---
        cam_data = bpy.data.cameras.new(name=f"Cam_Doc_{doc_item.name}")
        cam_data.lens = focal
        cam_obj = bpy.data.objects.new(name=f"Cam_Doc_{doc_item.name}",
                                       object_data=cam_data)
        dosco_col.objects.link(cam_obj)
        cam_obj.matrix_world = view_matrix

        # --- Create quad (plane) ---
        # Use the graph prefix for naming
        try:
            from ..operators.addon_prefix_helpers import node_name_to_proxy_name
            from ..functions import is_graph_available
            graph_ok, graph = is_graph_available(context)
            quad_name = node_name_to_proxy_name(
                doc_item.name, context=context, graph=graph if graph_ok else None)
        except Exception:
            quad_name = f"DocQuad_{doc_item.name}"

        # --- Create quad using PhotogrTool pattern ---
        # Use bpy.ops to create the plane exactly as PhotogrTool does
        bpy.ops.mesh.primitive_plane_add()
        quad_obj = bpy.context.active_object
        quad_obj.name = quad_name

        # Edit mode: resize to unit (0.5 scale), UV project, rotate 90° Z
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.transform.resize(value=(0.5, 0.5, 0.5))
        bpy.ops.uv.smart_project(angle_limit=66, island_margin=0, area_weight=0)
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.transform.rotate(value=1.5708, orient_axis='Z')
        bpy.ops.object.editmode_toggle()

        # Position at -depth from camera in local space, THEN parent
        quad_obj.location = (0, 0, -depth)
        quad_obj.parent = cam_obj

        # Move to DosCo collection (remove from active collection)
        for col in quad_obj.users_collection:
            col.objects.unlink(quad_obj)
        dosco_col.objects.link(quad_obj)

        # --- Set up scale drivers (PhotogrTool pattern) ---
        # Scale Y first (with aspect ratio), then Scale X (plain)
        # — same order as PhotogrTool.SetupDriversForImagePlane
        if img.size[0] > 0 and img.size[1] > 0:
            aspect = img.size[1] / img.size[0]
        else:
            aspect = 1.0

        def _setup_driver_vars(driver, quad, cam):
            """Set up camAngle and depth variables on a driver."""
            v_angle = driver.variables.new()
            v_angle.name = 'camAngle'
            v_angle.type = 'SINGLE_PROP'
            v_angle.targets[0].id = cam
            v_angle.targets[0].data_path = "data.angle"
            v_depth = driver.variables.new()
            v_depth.name = 'depth'
            v_depth.type = 'TRANSFORMS'
            v_depth.targets[0].id = quad
            v_depth.targets[0].transform_type = 'LOC_Z'
            v_depth.targets[0].transform_space = 'LOCAL_SPACE'

        # Scale drivers: quad must FILL the camera frustum exactly.
        # primitive_plane_add() → 2×2, resize(0.5) → 1×1 (vertices ±0.5).
        # Camera frustum full width at distance d: 2 * d * tan(angle/2).
        # Plane world width = 1 * scale_x → need scale_x = 2*d*tan(angle/2).
        # depth variable = local Z = -d → d = -depth → scale = -2*depth*tan(angle/2).

        # Scale Y (index 1) — includes image aspect ratio
        drv_y = quad_obj.driver_add('scale', 1).driver
        drv_y.type = 'SCRIPTED'
        _setup_driver_vars(drv_y, quad_obj, cam_obj)
        drv_y.expression = f"-2*depth*tan(camAngle/2)*{aspect}"

        # Scale X (index 0) — fills horizontal FOV
        drv_x = quad_obj.driver_add('scale', 0).driver
        drv_x.type = 'SCRIPTED'
        _setup_driver_vars(drv_x, quad_obj, cam_obj)
        drv_x.expression = "-2*depth*tan(camAngle/2)"

        bpy.context.view_layer.update()

        # Autocrop: set camera clip to tightly frame the quad
        cam_data.clip_start = max(0.01, depth - 0.1)
        cam_data.clip_end = depth + 0.5

        # --- Create material with image texture ---
        mat = bpy.data.materials.new(name=f"M_Doc_{doc_item.name}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex_node.image = img
        tex_node.location = (-460, 90)
        mat.node_tree.links.new(bsdf.inputs['Base Color'], tex_node.outputs['Color'])
        mat.node_tree.links.new(bsdf.outputs['BSDF'],
                                mat.node_tree.nodes.get("Material Output").inputs[0])
        bsdf.inputs['Alpha'].default_value = alpha
        try:
            mat.blend_method = 'BLEND'
        except AttributeError:
            pass  # Blender 4.2+ auto-detects alpha
        if quad_obj.data.materials:
            quad_obj.data.materials[0] = mat
        else:
            quad_obj.data.materials.append(mat)

        # Set render resolution to match image (perfect camera overlay)
        scene.render.resolution_x = img.size[0]
        scene.render.resolution_y = img.size[1]
        scene.render.resolution_percentage = 100
        scene.render.pixel_aspect_x = 1.0
        scene.render.pixel_aspect_y = 1.0
        cam_data.sensor_fit = 'HORIZONTAL'

        # --- Tag the quad ---
        quad_obj['em_doc_node_id'] = doc_node_id
        quad_obj['em_dimensions_type'] = 'SYMBOLIC'
        quad_obj['em_camera_name'] = cam_obj.name

        # Re-sync to pick up the new quad
        sync_doc_list(context.scene)

        # Invalidate UI cache
        from .ui import invalidate_doc_connection_cache
        invalidate_doc_connection_cache()

        self.report({'INFO'},
                    f"Created RMDoc for {doc_item.name} (f={focal:.0f}mm, depth={depth}m)")
        return {'FINISHED'}


class RMDOC_OT_remove(bpy.types.Operator):
    """Delete RMDoc: removes quad and camera objects from the scene"""
    bl_idname = "em.rmdoc_remove"
    bl_label = "Delete RMDoc"
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
    """Create a camera at the current viewport position for this RMDoc quad"""
    bl_idname = "em.rmdoc_create_camera"
    bl_label = "Create Camera"
    bl_options = {'REGISTER', 'UNDO'}

    object_name: StringProperty()  # type: ignore

    def execute(self, context):
        quad_obj = bpy.data.objects.get(self.object_name)
        if not quad_obj:
            self.report({'ERROR'}, f"Object '{self.object_name}' not found")
            return {'CANCELLED'}

        region_3d = None
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                region_3d = area.spaces[0].region_3d
                break
        if not region_3d:
            self.report({'ERROR'}, "No 3D Viewport found")
            return {'CANCELLED'}

        view_matrix = region_3d.view_matrix.inverted()
        focal = context.scene.doc_settings.default_focal_length

        cam_data = bpy.data.cameras.new(name=f"Cam_{self.object_name}")
        cam_data.lens = focal
        cam_obj = bpy.data.objects.new(name=f"Cam_{self.object_name}",
                                       object_data=cam_data)

        # Link to same collection as the quad
        for col in quad_obj.users_collection:
            col.objects.link(cam_obj)
            break
        else:
            context.collection.objects.link(cam_obj)

        cam_obj.matrix_world = view_matrix
        cam_obj.parent = quad_obj
        quad_obj['em_camera_name'] = cam_obj.name

        sync_doc_list(context.scene)
        self.report({'INFO'}, f"Created camera for {self.object_name} (f={focal:.0f}mm)")
        return {'FINISHED'}


class RMDOC_OT_look_through(bpy.types.Operator):
    """Look through camera and fit render resolution to image dimensions"""
    bl_idname = "em.rmdoc_look_through"
    bl_label = "Look Through Camera"

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
    bl_description = "Fix inconsistent RMDoc state: reset stale flags, remove orphan items, force exit pilot"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        items=[
            ('RESET_CAMERA_FLAG', "Reset Camera Flag", "Clear has_camera flag for items whose camera object is missing"),
            ('REMOVE_ORPHAN', "Remove Orphan Item", "Remove an RMDoc item whose quad object has been deleted"),
            ('UNSTUCK_PILOT', "Force Exit Pilot", "Exit piloting mode even if camera/viewport state is inconsistent"),
            ('FULL_SWEEP', "Full Sweep", "Run all repair operations on the whole RMDoc list"),
        ],
        default='FULL_SWEEP',
    )  # type: ignore
    rmdoc_index: IntProperty(default=-1)  # type: ignore

    def execute(self, context):
        scene = context.scene
        fixed = 0

        if self.mode in {'UNSTUCK_PILOT', 'FULL_SWEEP'}:
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
    RMDOC_OT_select_object,
    RMDOC_OT_add_selected,
    RMDOC_OT_search_document,
    RMDOC_OT_assign_document,
    RMDOC_OT_create_from_document,
    RMDOC_OT_remove,
    RMDOC_OT_create_camera,
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
