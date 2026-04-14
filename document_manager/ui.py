"""UI components for the Document Manager and RMDoc panels.

Document Manager: catalog of all documents from the graph (metadata, connections).
The row shows: master/instance icon, name [ref count], description, linked object icons.

RMDoc panel: scene objects (quads) linked to documents — object-centric like RM Manager.
"""

import re

import bpy
from bpy.types import Panel, UIList
from .. import icons_manager


def _natural_sort_key(name):
    """Natural sort key: 'D.2' < 'D.10' (numeric aware)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name)]


# Certainty of spatial positioning (used in RMDoc, NOT in Document Manager)
CERTAINTY_ICONS = {
    "direct": "COLLECTION_COLOR_01",          # red — photogrammetric placement
    "reconstructed": "COLLECTION_COLOR_02",   # orange — manual repositioning
    "hypothetical": "COLLECTION_COLOR_03",    # yellow/green — attributed context
    "unknown": "COLLECTION_COLOR_08",         # gray
}

CERTAINTY_LABELS = {
    "direct": "Direct positioning",
    "reconstructed": "Reconstructed positioning",
    "hypothetical": "Hypothetical positioning",
    "unknown": "Unknown",
}


# ══════════════════════════════════════════════════════════════════════
# HELPERS — graph connection + instance count caches
# ══════════════════════════════════════════════════════════════════════

_doc_cache = None
_doc_cache_graph_id = None


def _natural_sort_order(items):
    """Return Blender-format sort order: order[original_idx] = new_position."""
    sorted_indices = sorted(range(len(items)), key=lambda idx: _natural_sort_key(items[idx].name))
    order = [0] * len(items)
    for new_pos, orig_idx in enumerate(sorted_indices):
        order[orig_idx] = new_pos
    return order


def _build_doc_cache(context):
    """Build comprehensive per-document cache: ref counts, linked US, linked objects.

    Returns dict: doc_node_id -> {
        'ref_count': int,              # how many times referenced
        'us_nodes': [(name, node_id, node_type)],  # US nodes that use this doc
        'has_rmdoc': bool,             # has a quad in scene
        'rmdoc_obj': str,              # quad object name (if any)
    }
    Cached per graph instance.
    """
    global _doc_cache, _doc_cache_graph_id

    em_tools = context.scene.em_tools
    if em_tools.active_file_index < 0:
        return {}

    try:
        from s3dgraphy import get_graph
        graph_info = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graph_info.name)
        if not graph:
            return {}
    except Exception:
        return {}

    cache_key = id(graph)
    if _doc_cache_graph_id == cache_key and _doc_cache is not None:
        return _doc_cache

    # --- Build reverse edge index for chain traversal ---
    # target_id -> [(source_id, edge_type)]
    edges_by_target = {}
    for edge in graph.edges:
        edges_by_target.setdefault(edge.edge_target, []).append(
            (edge.edge_source, edge.edge_type)
        )
    edges_by_source = {}
    for edge in graph.edges:
        edges_by_source.setdefault(edge.edge_source, []).append(
            (edge.edge_target, edge.edge_type)
        )

    # --- Identify all document node IDs ---
    doc_ids = set()
    for item in context.scene.doc_list:
        if item.node_id:
            doc_ids.add(item.node_id)

    # --- Count references per document ---
    doc_as_target_types = {"extracted_from", "has_documentation", "has_visual_reference"}
    doc_as_source_types = {"is_documentation_of"}

    ref_counts = {}
    for edge in graph.edges:
        if edge.edge_type in doc_as_target_types and edge.edge_target in doc_ids:
            ref_counts[edge.edge_target] = ref_counts.get(edge.edge_target, 0) + 1
        elif edge.edge_type in doc_as_source_types and edge.edge_source in doc_ids:
            ref_counts[edge.edge_source] = ref_counts.get(edge.edge_source, 0) + 1

    # --- Trace paradata chain: Doc ← extracted_from ← Extractor ← has_data_provenance ← Property ← has_property ← US ---
    # Also direct: US → has_documentation → Doc
    doc_to_us = {}  # doc_node_id -> set of (us_name, us_node_id, us_node_type)

    for doc_id in doc_ids:
        us_set = set()

        # Path 1: Direct has_documentation (US → Doc)
        for (src_id, etype) in edges_by_target.get(doc_id, []):
            if etype == "has_documentation":
                src_node = graph.find_node_by_id(src_id)
                if src_node and hasattr(src_node, 'node_type'):
                    us_set.add((src_node.name, src_id, src_node.node_type))

        # Path 2: Reverse paradata chain
        # Step 1: Find extractors that extracted_from this doc
        extractors = set()
        for (src_id, etype) in edges_by_target.get(doc_id, []):
            if etype == "extracted_from":
                extractors.add(src_id)

        # Step 2: Find properties that has_data_provenance to each extractor
        properties = set()
        for ext_id in extractors:
            for (src_id, etype) in edges_by_target.get(ext_id, []):
                if etype == "has_data_provenance":
                    properties.add(src_id)

        # Step 3: Find US that has_property to each property
        for prop_id in properties:
            for (src_id, etype) in edges_by_target.get(prop_id, []):
                if etype == "has_property":
                    src_node = graph.find_node_by_id(src_id)
                    if src_node and hasattr(src_node, 'node_type'):
                        us_set.add((src_node.name, src_id, src_node.node_type))

        if us_set:
            doc_to_us[doc_id] = us_set

    # --- Build RMDoc lookup from scene ---
    rmdoc_by_doc_id = {}
    if hasattr(context.scene, 'rmdoc_list'):
        for item in context.scene.rmdoc_list:
            if item.doc_node_id:
                rmdoc_by_doc_id[item.doc_node_id] = item.name

    # --- Assemble per-doc cache ---
    cache = {}
    for doc_id in doc_ids:
        us_list = list(doc_to_us.get(doc_id, []))
        cache[doc_id] = {
            'ref_count': ref_counts.get(doc_id, 0),
            'us_nodes': us_list,
            'has_rmdoc': doc_id in rmdoc_by_doc_id,
            'rmdoc_obj': rmdoc_by_doc_id.get(doc_id, ""),
        }

    _doc_cache = cache
    _doc_cache_graph_id = cache_key
    return cache


def invalidate_doc_connection_cache():
    """Call after graph changes to force cache rebuild."""
    global _doc_cache, _doc_cache_graph_id
    _doc_cache = None
    _doc_cache_graph_id = None


# ══════════════════════════════════════════════════════════════════════
# DOCUMENT MANAGER — catalog of all documents
# ══════════════════════════════════════════════════════════════════════

class DOCMANAGER_UL_documents(UIList):
    """UIList for document items.

    Row: master/instance icon | name [ref_count] | description | linked object icons
    """

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        doc_cache = _build_doc_cache(context)
        doc_info = doc_cache.get(item.node_id, {})

        row = layout.row(align=True)

        # 1. Master/instance icon
        if item.is_master:
            row.label(text="", icon="KEYTYPE_KEYFRAME_VEC")
        else:
            row.label(text="", icon="DOT")

        # 2. Name + reference count
        count = doc_info.get('ref_count', 0)
        count_str = f" [{count}]" if count > 0 else ""
        row.label(text=f"{item.name}{count_str}")

        # 3. Description (flexible space)
        row.label(text=item.description if item.description else "")

        # 4. Linked entity icons at the end of the row
        us_nodes = doc_info.get('us_nodes', [])
        sf_types = {"SF", "VSF"}
        regular_us = [u for u in us_nodes if u[2] not in sf_types]
        sf_us = [u for u in us_nodes if u[2] in sf_types]

        # US proxy icon
        if regular_us:
            us_name, us_node_id, us_type = regular_us[0]
            op = row.operator(
                "em.docmanager_select_linked_entity", text="",
                icon='MESH_CUBE', emboss=False
            )
            op.node_id = us_node_id
            op.entity_type = 'US'

        # RMSF icon (show_all_special_finds)
        if sf_us:
            sf_name, sf_node_id, sf_type = sf_us[0]
            sf_icon = icons_manager.get_icon_value("show_all_special_finds")
            if sf_icon:
                op = row.operator(
                    "em.docmanager_select_linked_entity", text="",
                    icon_value=sf_icon, emboss=False
                )
            else:
                op = row.operator(
                    "em.docmanager_select_linked_entity", text="",
                    icon='OUTLINER_OB_ARMATURE', emboss=False
                )
            op.node_id = sf_node_id
            op.entity_type = 'RMSF'

        # RMDoc icon (spatialized document quad)
        if doc_info.get('has_rmdoc'):
            rmdoc_icon = icons_manager.get_icon_value("show_all_RMDoc")
            if rmdoc_icon:
                op = row.operator(
                    "em.docmanager_select_linked_entity", text="",
                    icon_value=rmdoc_icon, emboss=False
                )
            else:
                op = row.operator(
                    "em.docmanager_select_linked_entity", text="",
                    icon='FILE_IMAGE', emboss=False
                )
            op.node_id = item.node_id
            op.entity_type = 'RMDoc'

    def filter_items(self, context, data, propname):
        """Custom filtering and sorting — sort by name (natural numeric)."""
        items = getattr(data, propname)
        filter_flags = [self.bitflag_filter_item] * len(items)

        settings = context.scene.doc_settings

        for i, item in enumerate(items):
            if settings.filter_masters and not item.is_master:
                filter_flags[i] = 0
            if settings.filter_with_3d and not item.has_quad:
                filter_flags[i] = 0

        # Sort: order[original_idx] = new_position (Blender convention)
        order = _natural_sort_order(items)
        return filter_flags, order


class VIEW3D_PT_3DDocumentManager(Panel):
    """Document Manager — catalog of all documents from the graph."""
    bl_label = "Document Manager"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EM Annotator"
    bl_idname = "VIEW3D_PT_3DDocumentManager"
    bl_context = "objectmode"
    bl_order = 4
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, 'em_tools') and context.scene.em_tools.mode_em_advanced

    def draw_header(self, context):
        layout = self.layout
        icon_id = icons_manager.get_icon_value("document")
        if icon_id:
            layout.label(text="", icon_value=icon_id)
        else:
            layout.label(text="", icon='FILE')

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        doc_list = scene.doc_list
        doc_settings = scene.doc_settings
        idx = scene.doc_list_index

        total = len(doc_list)

        # --- Summary line 1: total documents + masters ---
        row1 = layout.row(align=True)
        doc_icon = icons_manager.get_icon_value("document")
        if doc_icon:
            row1.label(text=f"{total} Documents", icon_value=doc_icon)
        else:
            row1.label(text=f"{total} Documents", icon="FILE")
        masters = sum(1 for item in doc_list if item.is_master)
        row1.label(text=f"Masters: {masters}", icon="KEYTYPE_KEYFRAME_VEC")
        # Create Document — experimental only (requires GraphML write-back for persistence)
        if context.scene.em_tools.experimental_features:
            row1.operator("docmanager.create_document", text="", icon="ADD")

        # --- Summary line 2: RM, RMDoc, RMSF, direct US→Doc ---
        if total > 0:
            rm_count = len(scene.rm_list) if hasattr(scene, 'rm_list') else 0
            rmdoc_count = len(scene.rmdoc_list) if hasattr(scene, 'rmdoc_list') else 0
            rmsf_count = 0
            if hasattr(scene.em_tools, 'anastylosis'):
                rmsf_count = len(scene.em_tools.anastylosis.list)

            # Count documents directly linked to US (has_documentation edges)
            doc_cache = _build_doc_cache(context)
            docs_with_us = sum(1 for d in doc_cache.values() if d.get('us_nodes'))

            row2 = layout.row(align=True)

            rm_icon = icons_manager.get_icon_value("show_all_RMs")
            if rm_icon:
                row2.label(text=f"RM: {rm_count}", icon_value=rm_icon)
            else:
                row2.label(text=f"RM: {rm_count}", icon="OBJECT_DATA")

            rmdoc_icon = icons_manager.get_icon_value("show_all_RMDoc")
            if rmdoc_icon:
                row2.label(text=f"RMDoc: {rmdoc_count}", icon_value=rmdoc_icon)
            else:
                row2.label(text=f"RMDoc: {rmdoc_count}", icon="FILE_IMAGE")

            sf_icon = icons_manager.get_icon_value("show_all_special_finds")
            if sf_icon:
                row2.label(text=f"RMSF: {rmsf_count}", icon_value=sf_icon)
            else:
                row2.label(text=f"RMSF: {rmsf_count}", icon="OUTLINER_OB_ARMATURE")

            row2.label(text=f"US: {docs_with_us}", icon="MESH_CUBE")

        # --- Filter row ---
        filter_row = layout.row(align=True)
        filter_row.prop(doc_settings, "filter_masters", toggle=True)
        filter_row.prop(doc_settings, "filter_with_3d", toggle=True)

        # --- Document list ---
        row = layout.row()
        row.template_list(
            "DOCMANAGER_UL_documents", "",
            scene, "doc_list",
            scene, "doc_list_index",
            rows=8,
        )

        # --- Detail panel for selected document ---
        if 0 <= idx < total:
            item = doc_list[idx]
            doc_cache = _build_doc_cache(context)
            doc_info = doc_cache.get(item.node_id, {})

            detail_box = layout.box()
            col = detail_box.column(align=True)

            # Header: name + master/instance badge
            header = col.row()
            header.label(text=item.name, icon="FILE_TEXT")
            if item.is_master:
                header.label(text="Master", icon="KEYTYPE_KEYFRAME_VEC")
            else:
                header.label(text="Instance", icon="DOT")

            # Description
            if item.description:
                col.separator()
                col.label(text=item.description, icon="TEXT")

            # Reference count
            ref_count = doc_info.get('ref_count', 0)
            col.separator()
            col.label(text=f"Referenced {ref_count} time{'s' if ref_count != 1 else ''}", icon="LINKED")

            # Linked US nodes
            us_nodes = doc_info.get('us_nodes', [])
            if us_nodes:
                col.separator()
                sf_types = {"SF", "VSF"}
                for us_name, us_node_id, us_type in us_nodes:
                    us_row = col.row(align=True)
                    if us_type in sf_types:
                        sf_icon_val = icons_manager.get_icon_value("show_all_special_finds")
                        if sf_icon_val:
                            us_row.label(text=f"→ {us_name} ({us_type})", icon_value=sf_icon_val)
                        else:
                            us_row.label(text=f"→ {us_name} ({us_type})", icon='OUTLINER_OB_ARMATURE')
                    else:
                        us_row.label(text=f"→ {us_name} ({us_type})", icon='MESH_CUBE')
                    op = us_row.operator(
                        "em.docmanager_select_linked_entity", text="",
                        icon='RESTRICT_SELECT_OFF', emboss=False
                    )
                    op.node_id = us_node_id
                    op.entity_type = 'RMSF' if us_type in sf_types else 'US'

            # Document type (commented out for 1.5 — read-only, no editing)
            # col.separator()
            # col.prop(item, "doc_type", text="Type")

            # Chronology (masters only)
            if item.is_master:
                col.separator()
                chrono_row = col.row()
                chrono_row.label(text="Chronology:", icon="TIME")
                if item.absolute_start_date:
                    chrono_row.label(text=item.absolute_start_date)
                else:
                    chrono_row.label(text="not set", icon="ERROR")
                if item.epoch_name:
                    col.label(text=f"Epoch: {item.epoch_name}")

            # Source type
            if item.source_type:
                col.separator()
                if item.source_type == "analytical":
                    col.label(text="Analytical (from context)", icon="DOCUMENTS")
                else:
                    col.label(text="Comparative (from analogues)", icon="WORLD")

            # URL
            if item.url:
                col.separator()
                col.operator("em.docmanager_open_url", text="Open File", icon="URL")

        # --- Settings (collapsible) ---
        settings_header = layout.row()
        settings_header.prop(
            doc_settings, "show_settings",
            icon="TRIA_DOWN" if doc_settings.show_settings else "TRIA_RIGHT",
            emboss=False, text="Settings"
        )
        if doc_settings.show_settings:
            settings_box = layout.box()
            settings_box.prop(doc_settings, "zoom_to_selected")


# ══════════════════════════════════════════════════════════════════════
# RMDOC PANEL — scene objects linked to documents (object-centric)
# ══════════════════════════════════════════════════════════════════════
#
# Pattern: scene objects (quads with em_doc_node_id) → rmdoc_list → UIList
# Same as RM Manager (scene objects → rm_list → epochs)
# and Anastylosis (scene objects → rmsf_list → Special Finds)

class RMDOC_UL_documents(UIList):
    """UIList for RMDoc: lists scene objects (quads) linked to documents.

    Row layout: certainty color | object name | linked doc name | camera icon
    """

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)

        # 1. Certainty of positioning color
        cert_icon = CERTAINTY_ICONS.get(item.certainty_class, "COLLECTION_COLOR_08")
        row.label(text="", icon=cert_icon)

        # 2. Object name (this is the scene object)
        name_col = row.row(align=True)
        name_col.scale_x = 0.3
        obj_icon = 'MESH_PLANE' if item.object_exists else 'ERROR'
        name_col.label(text=item.name, icon=obj_icon)

        # 3. Linked document name
        doc_col = row.row(align=True)
        doc_col.scale_x = 0.3
        doc_col.label(text=item.doc_name if item.doc_name else "[no doc]")

        # 4. Description (truncated)
        desc_col = row.row(align=True)
        desc_col.scale_x = 0.25
        desc_col.label(text=item.doc_description if item.doc_description else "")

        # 5. Camera icon (or blank placeholder)
        cam_col = row.row(align=True)
        cam_col.scale_x = 0.08
        if item.has_camera:
            cam_col.label(text="", icon="CAMERA_DATA")
        else:
            cam_col.label(text="", icon="BLANK1")

        # 6. Select object in viewport
        op_col = row.row(align=True)
        op_col.scale_x = 0.08
        op = op_col.operator("em.rmdoc_select_object", text="", icon='RESTRICT_SELECT_OFF', emboss=False)
        op.object_name = item.name

    def filter_items(self, context, data, propname):
        """Sort by object name (natural numeric)."""
        items = getattr(data, propname)
        filter_flags = [self.bitflag_filter_item] * len(items)
        order = _natural_sort_order(items)
        return filter_flags, order


class VIEW3D_PT_RMDoc_Manager(Panel):
    """Representation Model Document — scene objects linked to documents."""
    bl_label = "Representation Model Document (RMDoc)"
    bl_idname = "VIEW3D_PT_RMDoc_Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EM Annotator'
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        return em_tools.mode_em_advanced

    def draw_header(self, context):
        layout = self.layout
        icon_id = icons_manager.get_icon_value("show_all_RMDoc")
        if icon_id:
            layout.label(text="", icon_value=icon_id)
        else:
            layout.label(text="", icon='FILE_IMAGE')

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        rmdoc_list = scene.rmdoc_list
        total = len(rmdoc_list)

        # --- Sync controls ---
        sync_row = layout.row(align=True)
        sync_row.operator("em.docmanager_sync", text="Sync", icon="FILE_REFRESH")
        sync_row.label(text=f"{total} object{'s' if total != 1 else ''} in scene")

        if total == 0:
            layout.label(text="No spatialized documents in scene", icon='INFO')
            layout.label(text="Use Document Manager to import images", icon='FORWARD')
            return

        # --- Summary ---
        with_camera = sum(1 for item in rmdoc_list if item.has_camera)
        summary_row = layout.row(align=True)
        summary_row.label(text=f"Quads: {total}", icon="MESH_PLANE")
        summary_row.label(text=f"Cameras: {with_camera}", icon="CAMERA_DATA")

        # --- UIList (object-centric: rmdoc_list) ---
        row = layout.row()
        row.template_list(
            "RMDOC_UL_documents", "",
            scene, "rmdoc_list",
            scene, "rmdoc_list_index",
            rows=5,
        )

        # --- Detail panel for selected item ---
        idx = scene.rmdoc_list_index
        if 0 <= idx < total:
            item = rmdoc_list[idx]

            detail_box = layout.box()
            col = detail_box.column(align=True)

            # Object + linked document
            header_row = col.row()
            header_row.label(text=item.name, icon="MESH_PLANE")
            if item.doc_name:
                header_row.label(text=f"→ {item.doc_name}", icon="FILE_TEXT")
            else:
                header_row.label(text="→ [unlinked]", icon="UNLINKED")

            # Description
            if item.doc_description:
                col.label(text=item.doc_description, icon="TEXT")

            # Certainty of positioning
            col.separator()
            cert_icon = CERTAINTY_ICONS.get(item.certainty_class, "COLLECTION_COLOR_08")
            cert_label = CERTAINTY_LABELS.get(item.certainty_class, "Unknown")
            col.label(text=f"Positioning: {cert_label}", icon=cert_icon)

            # Quad dimensions
            col.separator()
            dim_row = col.row(align=True)
            dim_row.label(text=f"{item.quad_width:.2f} × {item.quad_height:.2f} m", icon="MESH_PLANE")
            dim_row.label(text=f"({item.dimensions_type})")

            # Camera info
            col.separator()
            if item.has_camera:
                col.label(text=f"Camera: {item.camera_object_name}", icon="CAMERA_DATA")
                cam_obj = bpy.data.objects.get(item.camera_object_name)
                if cam_obj and cam_obj.type == 'CAMERA':
                    col.prop(cam_obj.data, "lens", text="Focal Length")
                op = col.operator("em.rmdoc_look_through", text="Look Through", icon="HIDE_OFF")
                op.object_name = item.name
            else:
                op = col.operator("em.rmdoc_create_camera", text="Create Camera", icon="CAMERA_DATA")
                op.object_name = item.name

            # Actions
            col.separator()
            action_row = col.row(align=True)
            op = action_row.operator("em.rmdoc_select_object", text="Select Quad", icon="RESTRICT_SELECT_OFF")
            op.object_name = item.name
            if item.doc_node_id:
                op = action_row.operator("em.rmdoc_open_document", text="Open File", icon="URL")
                op.doc_node_id = item.doc_node_id


classes = (
    DOCMANAGER_UL_documents,
    RMDOC_UL_documents,
    VIEW3D_PT_3DDocumentManager,
    VIEW3D_PT_RMDoc_Manager,
)


def register_ui():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister_ui():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
