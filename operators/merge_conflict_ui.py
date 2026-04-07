"""
Merge conflict resolution UI for EM-blender-tools.

Provides operators and panel for comparing an existing graph with
incoming XLSX stratigraphy data, showing conflicts, and letting the
user accept or reject each change.

UI elements:
- Conflict counter (e.g., "3/15 conflicts")
- Previous / Next conflict navigation
- Accept Change / Reject Change per conflict
- Accept All Changes / Keep All Original bulk actions
"""

import bpy  # type: ignore
from bpy.props import (  # type: ignore
    StringProperty, IntProperty, EnumProperty, BoolProperty,
    CollectionProperty
)

from s3dgraphy import get_graph
from s3dgraphy.merge import GraphMerger, Conflict


# ---------------------------------------------------------------------------
# Module-level state for active merge session
# ---------------------------------------------------------------------------

_active_conflicts = []      # List[Conflict]
_incoming_graph = None       # The graph imported from XLSX for comparison
_merger = None               # GraphMerger instance


def get_active_conflicts():
    return _active_conflicts


def is_merge_active():
    return len(_active_conflicts) > 0


# NOTE: MergeConflictItem PropertyGroup is defined in em_props.py and
# registered there. It provides: node_name, field_name, current_value,
# incoming_value, conflict_type, resolved, accepted.
# Accessed via context.scene.em_tools.merge_conflicts


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class EM_OT_merge_xlsx_start(bpy.types.Operator):
    """Start merge of XLSX stratigraphy data with active graph"""
    bl_idname = "em.merge_xlsx_start"
    bl_label = "Merge XLSX Stratigraphy"
    bl_description = (
        "Import stratigraphy data from XLSX and compare with "
        "the active graph. Shows conflicts for user resolution"
    )
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(
        name="XLSX File",
        description="Path to the stratigraphy XLSX file",
        subtype='FILE_PATH'
    )

    filter_glob: StringProperty(default="*.xlsx;*.xls", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        if em_tools.active_file_index < 0:
            return False
        if em_tools.active_file_index >= len(em_tools.graphml_files):
            return False
        return bool(get_graph(em_tools.graphml_files[em_tools.active_file_index].name))

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        global _active_conflicts, _incoming_graph, _merger

        em_tools = context.scene.em_tools
        graphml_file = em_tools.graphml_files[em_tools.active_file_index]
        existing_graph = get_graph(graphml_file.name)

        if existing_graph is None:
            self.report({'ERROR'}, "No active graph loaded")
            return {'CANCELLED'}

        # Import XLSX into a temporary graph
        try:
            from s3dgraphy.importer.mapped_xlsx_importer import MappedXLSXImporter
            from s3dgraphy.graph import Graph
            import uuid

            temp_graph = Graph(graph_id=str(uuid.uuid4()))
            importer = MappedXLSXImporter(
                filepath=self.filepath,
                graph=temp_graph,
                mapping_name='excel_to_graphml_mapping'
            )
            temp_graph = importer.parse()
            _incoming_graph = temp_graph

        except Exception as e:
            self.report({'ERROR'}, f"Error importing XLSX: {str(e)}")
            return {'CANCELLED'}

        # Compare graphs
        _merger = GraphMerger()
        _active_conflicts = _merger.compare(existing_graph, _incoming_graph)

        # Filter to only user-resolvable conflicts (exclude auto-accepted node_added)
        user_conflicts = _merger.get_unresolved_conflicts(_active_conflicts)

        if not user_conflicts:
            # No conflicts - apply all changes directly
            _merger.apply_resolutions(existing_graph, _active_conflicts, _incoming_graph)
            _active_conflicts = []
            _incoming_graph = None

            self.report({'INFO'},
                        "XLSX merged successfully - no conflicts detected")
            return {'FINISHED'}

        # Populate Blender property for UI display
        em_tools.merge_conflicts.clear()
        for conflict in _active_conflicts:
            if conflict.resolved:
                continue  # Skip auto-resolved
            item = em_tools.merge_conflicts.add()
            item.node_name = conflict.node_name
            item.field_name = conflict.display_field
            item.current_value = conflict.current_value[:200]
            item.incoming_value = conflict.incoming_value[:200]
            item.conflict_type = conflict.conflict_type
            item.resolved = False
            item.accepted = False

        em_tools.merge_conflict_index = 0
        em_tools.merge_active = True

        stats = _merger.get_statistics(_active_conflicts)
        self.report({'WARNING'},
                    f"Found {stats['unresolved']} conflicts to resolve "
                    f"({stats.get('by_type', {}).get('value_changed', 0)} value changes, "
                    f"{stats.get('by_type', {}).get('edge_added', 0)} new edges, "
                    f"{stats.get('by_type', {}).get('edge_removed', 0)} removed edges)")

        return {'FINISHED'}


class EM_OT_resolve_conflict(bpy.types.Operator):
    """Resolve a single merge conflict"""
    bl_idname = "em.resolve_conflict"
    bl_label = "Resolve Conflict"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        name="Action",
        items=[
            ('ACCEPT', "Accept Change", "Use the incoming value"),
            ('REJECT', "Reject Change", "Keep the current value"),
        ]
    )

    @classmethod
    def poll(cls, context):
        return context.scene.em_tools.merge_active

    def execute(self, context):
        em_tools = context.scene.em_tools
        idx = em_tools.merge_conflict_index

        if idx < 0 or idx >= len(em_tools.merge_conflicts):
            return {'CANCELLED'}

        # Update the Blender property
        item = em_tools.merge_conflicts[idx]
        item.resolved = True
        item.accepted = (self.action == 'ACCEPT')

        # Update the internal conflict object
        unresolved = [c for c in _active_conflicts if not c.resolved]
        if idx < len(unresolved):
            unresolved[idx].resolved = True
            unresolved[idx].accepted = (self.action == 'ACCEPT')

        # Auto-advance to next unresolved
        self._advance_to_next_unresolved(context)

        return {'FINISHED'}

    def _advance_to_next_unresolved(self, context):
        em_tools = context.scene.em_tools
        for i, item in enumerate(em_tools.merge_conflicts):
            if not item.resolved:
                em_tools.merge_conflict_index = i
                return
        # All resolved
        em_tools.merge_conflict_index = max(0, len(em_tools.merge_conflicts) - 1)


class EM_OT_resolve_all_conflicts(bpy.types.Operator):
    """Resolve all remaining conflicts at once"""
    bl_idname = "em.resolve_all_conflicts"
    bl_label = "Resolve All"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        name="Action",
        items=[
            ('ACCEPT_ALL', "Accept All Changes",
             "Use incoming values for all remaining conflicts"),
            ('KEEP_ALL', "Keep All Original",
             "Keep current values for all remaining conflicts"),
        ]
    )

    @classmethod
    def poll(cls, context):
        return context.scene.em_tools.merge_active

    def execute(self, context):
        em_tools = context.scene.em_tools
        accept = (self.action == 'ACCEPT_ALL')

        for item in em_tools.merge_conflicts:
            if not item.resolved:
                item.resolved = True
                item.accepted = accept

        for conflict in _active_conflicts:
            if not conflict.resolved:
                conflict.resolved = True
                conflict.accepted = accept

        self.report({'INFO'},
                    f"{'Accepted' if accept else 'Rejected'} all remaining changes")

        return {'FINISHED'}


class EM_OT_navigate_conflict(bpy.types.Operator):
    """Navigate between conflicts"""
    bl_idname = "em.navigate_conflict"
    bl_label = "Navigate Conflict"

    direction: EnumProperty(
        name="Direction",
        items=[
            ('NEXT', "Next", "Go to next conflict"),
            ('PREV', "Previous", "Go to previous conflict"),
        ]
    )

    @classmethod
    def poll(cls, context):
        return context.scene.em_tools.merge_active

    def execute(self, context):
        em_tools = context.scene.em_tools
        total = len(em_tools.merge_conflicts)
        if total == 0:
            return {'CANCELLED'}

        if self.direction == 'NEXT':
            em_tools.merge_conflict_index = min(
                em_tools.merge_conflict_index + 1, total - 1)
        else:
            em_tools.merge_conflict_index = max(
                em_tools.merge_conflict_index - 1, 0)

        return {'FINISHED'}


class EM_OT_apply_merge(bpy.types.Operator):
    """Apply all resolved conflicts and save to GraphML"""
    bl_idname = "em.apply_merge"
    bl_label = "Apply Merge"
    bl_description = "Apply resolved conflicts to the graph and save to GraphML"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        if not em_tools.merge_active:
            return False
        # All conflicts must be resolved
        return all(item.resolved for item in em_tools.merge_conflicts)

    def execute(self, context):
        global _active_conflicts, _incoming_graph, _merger
        from ..functions import normalize_path
        from s3dgraphy.exporter.graphml import GraphMLPatcher

        em_tools = context.scene.em_tools
        graphml_file = em_tools.graphml_files[em_tools.active_file_index]
        existing_graph = get_graph(graphml_file.name)

        if existing_graph is None or _merger is None:
            self.report({'ERROR'}, "No active merge session")
            return {'CANCELLED'}

        # Apply resolved conflicts to the in-memory graph
        _merger.apply_resolutions(existing_graph, _active_conflicts, _incoming_graph)

        # Save to GraphML using the patcher
        filepath = normalize_path(graphml_file.graphml_path)
        try:
            patcher = GraphMLPatcher(filepath, existing_graph)
            nodes_updated, nodes_added, edges_added, problems = patcher.patch()

            for p in problems:
                self.report({'WARNING'}, p)

            stats = _merger.get_statistics(_active_conflicts)
            self.report({'INFO'},
                        f"Merge applied: {stats['accepted']} changes accepted, "
                        f"{stats['rejected']} rejected. "
                        f"GraphML: {nodes_updated} updated, "
                        f"{nodes_added} added, {edges_added} edges added")

        except Exception as e:
            self.report({'ERROR'}, f"Error saving GraphML: {str(e)}")
            return {'CANCELLED'}

        # Clean up merge session
        _active_conflicts = []
        _incoming_graph = None
        _merger = None
        em_tools.merge_active = False
        em_tools.merge_conflicts.clear()

        return {'FINISHED'}


class EM_OT_cancel_merge(bpy.types.Operator):
    """Cancel the current merge operation"""
    bl_idname = "em.cancel_merge"
    bl_label = "Cancel Merge"
    bl_options = {'REGISTER'}

    def execute(self, context):
        global _active_conflicts, _incoming_graph, _merger

        _active_conflicts = []
        _incoming_graph = None
        _merger = None

        em_tools = context.scene.em_tools
        em_tools.merge_active = False
        em_tools.merge_conflicts.clear()

        self.report({'INFO'}, "Merge cancelled")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class EMTOOLS_PT_conflict_resolution(bpy.types.Panel):
    """Conflict resolution panel for XLSX merge"""
    bl_label = "Conflict Resolution"
    bl_idname = "EMTOOLS_PT_conflict_resolution"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.em_tools.merge_active

    def draw(self, context):
        layout = self.layout
        em_tools = context.scene.em_tools

        conflicts = em_tools.merge_conflicts
        total = len(conflicts)
        resolved_count = sum(1 for c in conflicts if c.resolved)
        idx = em_tools.merge_conflict_index

        # Header with counter
        box = layout.box()
        row = box.row()
        row.label(text=f"Conflicts: {resolved_count}/{total} resolved",
                  icon='ERROR')

        if total == 0:
            box.label(text="No conflicts to resolve")
            return

        # Navigation
        row = box.row(align=True)
        op_prev = row.operator("em.navigate_conflict", text="Previous",
                                icon='TRIA_LEFT')
        op_prev.direction = 'PREV'
        row.label(text=f"{idx + 1} / {total}")
        op_next = row.operator("em.navigate_conflict", text="Next",
                                icon='TRIA_RIGHT')
        op_next.direction = 'NEXT'

        # Current conflict details
        if 0 <= idx < total:
            item = conflicts[idx]

            detail_box = layout.box()

            # Status indicator
            if item.resolved:
                status = "ACCEPTED" if item.accepted else "REJECTED"
                icon = 'CHECKMARK' if item.accepted else 'X'
                detail_box.label(text=f"Status: {status}", icon=icon)
            else:
                detail_box.label(text="Status: PENDING", icon='QUESTION')

            # Node name
            detail_box.label(text=f"Node: {item.node_name}", icon='OBJECT_DATA')

            # Field
            detail_box.label(text=f"Field: {item.field_name}")

            # Type
            type_labels = {
                'value_changed': 'Value Changed',
                'edge_added': 'New Relationship',
                'edge_removed': 'Removed Relationship',
            }
            detail_box.label(
                text=f"Type: {type_labels.get(item.conflict_type, item.conflict_type)}")

            # Values comparison
            val_box = layout.box()
            col = val_box.column(align=True)
            col.label(text="Current value:", icon='FILE')
            current_text = item.current_value if item.current_value else "(empty)"
            # Split long text into multiple lines
            for line in current_text[:300].split('\n')[:5]:
                col.label(text=f"  {line}")

            col.separator()
            col.label(text="Incoming value:", icon='IMPORT')
            incoming_text = item.incoming_value if item.incoming_value else "(empty)"
            for line in incoming_text[:300].split('\n')[:5]:
                col.label(text=f"  {line}")

            # Action buttons for current conflict
            if not item.resolved:
                action_box = layout.box()
                row = action_box.row(align=True)
                row.scale_y = 1.5

                op_accept = row.operator("em.resolve_conflict",
                                          text="Accept Change", icon='CHECKMARK')
                op_accept.action = 'ACCEPT'

                op_reject = row.operator("em.resolve_conflict",
                                          text="Reject Change", icon='X')
                op_reject.action = 'REJECT'

        # Bulk actions
        layout.separator()
        bulk_box = layout.box()
        bulk_box.label(text="Bulk Actions:", icon='PRESET')
        row = bulk_box.row(align=True)
        op_all = row.operator("em.resolve_all_conflicts",
                               text="Accept All Changes", icon='CHECKMARK')
        op_all.action = 'ACCEPT_ALL'
        op_keep = row.operator("em.resolve_all_conflicts",
                                text="Keep All Original", icon='LOOP_BACK')
        op_keep.action = 'KEEP_ALL'

        # Apply / Cancel
        layout.separator()
        row = layout.row(align=True)
        row.scale_y = 1.5

        all_resolved = all(c.resolved for c in conflicts)
        sub = row.row()
        sub.enabled = all_resolved
        sub.operator("em.apply_merge", text="Apply Merge", icon='FILE_TICK')

        row.operator("em.cancel_merge", text="Cancel", icon='CANCEL')


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = [
    EM_OT_merge_xlsx_start,
    EM_OT_resolve_conflict,
    EM_OT_resolve_all_conflicts,
    EM_OT_navigate_conflict,
    EM_OT_apply_merge,
    EM_OT_cancel_merge,
    EMTOOLS_PT_conflict_resolution,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
