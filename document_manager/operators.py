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
from bpy.props import StringProperty, FloatProperty, EnumProperty  # type: ignore

from .data import sync_doc_list


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
        mat.blend_method = 'BLEND'

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

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj

        # Zoom if setting enabled
        if context.scene.doc_settings.zoom_to_selected:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            with context.temp_override(area=area, region=region):
                                bpy.ops.view3d.view_selected()
                            break
                    break

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
        focal = context.scene.doc_settings.default_focal_length

        cam_data = bpy.data.cameras.new(name=f"Cam_{self.object_name}")
        cam_data.lens = focal
        cam_obj = bpy.data.objects.new(name=f"Cam_{self.object_name}", object_data=cam_data)
        context.collection.objects.link(cam_obj)
        cam_obj.matrix_world = view_matrix
        cam_obj.parent = quad_obj
        quad_obj['em_camera_name'] = cam_obj.name

        # Re-sync rmdoc_list to pick up the camera
        sync_doc_list(context.scene)

        self.report({'INFO'}, f"Created camera for {self.object_name} (f={focal:.0f}mm)")
        return {'FINISHED'}


class RMDOC_OT_look_through(bpy.types.Operator):
    """Switch viewport to look through this RMDoc's camera"""
    bl_idname = "em.rmdoc_look_through"
    bl_label = "Look Through Camera"

    object_name: StringProperty()  # type: ignore

    def execute(self, context):
        quad_obj = bpy.data.objects.get(self.object_name)
        if not quad_obj:
            return {'CANCELLED'}

        cam_name = quad_obj.get('em_camera_name', '')
        cam_obj = bpy.data.objects.get(cam_name) if cam_name else None

        # Fallback: check children
        if not cam_obj or cam_obj.type != 'CAMERA':
            for child in quad_obj.children:
                if child.type == 'CAMERA':
                    cam_obj = child
                    break

        if not cam_obj or cam_obj.type != 'CAMERA':
            self.report({'ERROR'}, "No camera found for this object")
            return {'CANCELLED'}

        context.scene.camera = cam_obj
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces[0].region_3d.view_perspective = 'CAMERA'
                break

        return {'FINISHED'}


class RMDOC_OT_open_document(bpy.types.Operator):
    """Open the document file linked to this RMDoc object"""
    bl_idname = "em.rmdoc_open_document"
    bl_label = "Open Document"

    doc_node_id: StringProperty()  # type: ignore

    def execute(self, context):
        # Find the doc_list item by node_id to get the URL
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
    DOCMANAGER_OT_create_document,
    RMDOC_OT_select_object,
    RMDOC_OT_create_camera,
    RMDOC_OT_look_through,
    RMDOC_OT_open_document,
)


def register_operators():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister_operators():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
