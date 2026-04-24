"""
Merge conflict resolution UI for EM-blender-tools.

Provides operators and panel for comparing an existing graph with
incoming XLSX stratigraphy data, showing conflicts, and letting the
user accept or reject each change.

Includes epoch compatibility validation: before any merge is applied,
each incoming US is checked against the existing epoch structure.
Blocking issues (straddling, missing epochs) halt the merge.
"""

import os

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
# Epoch remap plan: {strat_node_id: existing_epoch_node_id}
_epoch_remap_plan = {}


def get_active_conflicts():
    return _active_conflicts


def is_merge_active():
    return len(_active_conflicts) > 0


# NOTE: MergeConflictItem PropertyGroup is defined in em_props.py and
# registered there. It provides: node_name, field_name, current_value,
# incoming_value, conflict_type, resolved, accepted.
# Accessed via context.scene.em_tools.merge_conflicts


# ---------------------------------------------------------------------------
# Epoch compatibility analysis
# ---------------------------------------------------------------------------

def _get_best_chronology(us_node, graph):
    """
    Get the best available chronology for a US node.

    Priority: subphase > phase > period.
    Returns (start, end, level, epoch_node) or (None, None, None, None).
    """
    from s3dgraphy.nodes.epoch_node import EpochNode

    epochs_by_level = {'subphase': [], 'phase': [], 'period': []}

    for edge in graph.edges:
        if edge.edge_source == us_node.node_id and edge.edge_type == 'has_first_epoch':
            target = graph.find_node_by_id(edge.edge_target)
            if isinstance(target, EpochNode):
                level = getattr(target, 'epoch_level', 'period')
                if level in epochs_by_level:
                    epochs_by_level[level].append(target)

    for level in ['subphase', 'phase', 'period']:
        if epochs_by_level[level]:
            epoch = epochs_by_level[level][0]
            return (epoch.start_time, epoch.end_time, level, epoch)

    return (None, None, None, None)


def _classify_epoch_compatibility(us_start, us_end, existing_epochs):
    """
    Classify how a US chronology fits within the existing epoch structure.

    Returns (category, matched_epoch, overlapping_epochs):
      - EXACT_FIT: fully contained in one epoch
      - WIDER_EPOCH: overlaps one epoch but US is narrower than it
      - STRADDLING: spans across 2+ epochs
      - NO_MATCH: no chronological overlap with any epoch
    """
    if us_start is None or us_end is None:
        return 'NO_EPOCH', None, None

    containing = []   # epochs that fully contain the US
    overlapping = []  # epochs that partially overlap

    for epoch in existing_epochs:
        e_start = epoch.start_time
        e_end = epoch.end_time
        if e_start is None or e_end is None:
            continue

        if e_start <= us_start and us_end <= e_end:
            containing.append(epoch)
        elif us_start < e_end and us_end > e_start:
            overlapping.append(epoch)

    if containing:
        # Pick the tightest-fitting epoch
        best = min(containing, key=lambda e: (e.end_time or 0) - (e.start_time or 0))
        return 'EXACT_FIT', best, None
    elif len(overlapping) >= 2:
        return 'STRADDLING', None, overlapping
    elif len(overlapping) == 1:
        return 'WIDER_EPOCH', overlapping[0], None
    else:
        return 'NO_MATCH', None, None


def _build_epoch_report(existing_graph, incoming_graph):
    """
    Build a pre-merge epoch compatibility report.

    Returns a list of dicts, each with:
      node_name, category, us_start, us_end, epoch_level,
      matched_epoch_name, message, matched_epoch_node
    """
    from s3dgraphy.nodes.epoch_node import EpochNode
    from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode

    # Collect existing epochs (from GraphML — they have min_y/max_y)
    existing_epochs = [
        n for n in existing_graph.nodes
        if isinstance(n, EpochNode) and hasattr(n, 'min_y') and n.min_y is not None
    ]

    # Collect incoming stratigraphic nodes
    incoming_strat = [
        n for n in incoming_graph.nodes
        if isinstance(n, StratigraphicNode)
    ]

    # Also check which incoming nodes are truly NEW (not in existing graph)
    existing_names = set()
    for n in existing_graph.nodes:
        if isinstance(n, StratigraphicNode) and hasattr(n, 'name'):
            existing_names.add(n.name)

    report = []

    for us_node in sorted(incoming_strat, key=lambda x: x.name):
        # Skip nodes already in the existing graph (they keep their epoch)
        if us_node.name in existing_names:
            continue

        us_start, us_end, level, epoch_node = _get_best_chronology(
            us_node, incoming_graph)

        if level is None:
            # No chronological data at all
            report.append({
                'node_name': us_node.name,
                'category': 'NO_EPOCH',
                'us_start': 0.0,
                'us_end': 0.0,
                'epoch_level': '',
                'matched_epoch_name': '',
                'message': (
                    f"No chronological data (period/phase/subphase) "
                    f"in XLSX. Cannot assign to any epoch."
                ),
                'matched_epoch_node': None,
            })
            continue

        # Check completeness (fallback warning)
        completeness_note = ""
        if level == 'period':
            completeness_note = " [only period available, subphase/phase missing]"
        elif level == 'phase':
            completeness_note = " [subphase missing, using phase]"

        category, matched, overlapping = _classify_epoch_compatibility(
            us_start, us_end, existing_epochs)

        if category == 'EXACT_FIT':
            msg = (f"Fits in '{matched.name}' "
                   f"({matched.start_time}-{matched.end_time})"
                   f"{completeness_note}")
        elif category == 'WIDER_EPOCH':
            msg = (f"Narrower than '{matched.name}' "
                   f"({matched.start_time}-{matched.end_time}). "
                   f"US dates: {us_start}-{us_end}. "
                   f"Consider per-node absolute dates or a sub-epoch"
                   f"{completeness_note}")
        elif category == 'STRADDLING':
            epoch_names = ", ".join(
                f"'{e.name}' ({e.start_time}-{e.end_time})"
                for e in overlapping
            )
            msg = (f"Straddles {len(overlapping)} epochs: {epoch_names}. "
                   f"US dates: {us_start}-{us_end}. "
                   f"Need a single epoch covering {us_start}-{us_end}"
                   f"{completeness_note}")
        elif category == 'NO_MATCH':
            msg = (f"Dates {us_start}-{us_end} don't overlap any existing "
                   f"epoch. Need a new epoch for this range"
                   f"{completeness_note}")
        else:
            msg = f"Unknown category{completeness_note}"

        report.append({
            'node_name': us_node.name,
            'category': category,
            'us_start': us_start or 0.0,
            'us_end': us_end or 0.0,
            'epoch_level': level,
            'matched_epoch_name': matched.name if matched else '',
            'message': msg,
            'matched_epoch_node': matched,
        })

    return report


def _apply_epoch_remap(existing_graph, incoming_graph, remap_plan):
    """
    Remap incoming nodes' epoch edges to existing epochs per the remap plan.

    Args:
        existing_graph: The merged graph (already has incoming nodes)
        incoming_graph: The original incoming graph (for looking up epoch edges)
        remap_plan: dict {strat_node_id: existing_epoch_node_id}
    """
    import uuid as uuid_mod
    from s3dgraphy.nodes.epoch_node import EpochNode
    from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode

    # Remove all has_first_epoch edges for nodes in the remap plan
    edges_to_remove = []
    for edge in existing_graph.edges:
        if edge.edge_type == 'has_first_epoch' and edge.edge_source in remap_plan:
            edges_to_remove.append(edge.edge_id)

    for edge_id in edges_to_remove:
        try:
            existing_graph.remove_edge(edge_id)
        except (ValueError, KeyError):
            pass

    # Add new has_first_epoch edges to the correct existing epochs
    for strat_id, epoch_id in remap_plan.items():
        try:
            existing_graph.add_edge(
                edge_id=str(uuid_mod.uuid4()),
                edge_source=strat_id,
                edge_target=epoch_id,
                edge_type='has_first_epoch'
            )
        except ValueError:
            pass


def _export_epoch_report(xlsx_path, report_items):
    """
    Export the epoch compatibility report as a text file next to the XLSX.

    File name: <xlsx_name_without_ext>_conflicts.txt
    Returns the absolute path of the written file.
    """
    base = os.path.splitext(xlsx_path)[0]
    report_path = base + "_conflicts.txt"

    # Group by category
    categories = {}
    for r in report_items:
        cat = r['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    cat_labels = {
        'STRADDLING': 'BLOCKING - Straddles multiple epochs',
        'NO_EPOCH': 'BLOCKING - No chronological data',
        'NO_MATCH': 'BLOCKING - No matching epoch',
        'WIDER_EPOCH': 'WARNING - Narrower than target epoch',
        'EXACT_FIT': 'OK - Fits in existing epoch',
    }

    lines = []
    lines.append("=" * 72)
    lines.append("EPOCH COMPATIBILITY REPORT")
    lines.append(f"Source: {os.path.basename(xlsx_path)}")
    lines.append("=" * 72)
    lines.append("")

    # Summary
    total = len(report_items)
    blocking = sum(1 for r in report_items
                   if r['category'] in ('STRADDLING', 'NO_EPOCH', 'NO_MATCH'))
    lines.append(f"Total incoming US: {total}")
    lines.append(f"Blocking issues:  {blocking}")
    lines.append(f"Warnings:         {sum(1 for r in report_items if r['category'] == 'WIDER_EPOCH')}")
    lines.append(f"OK:               {sum(1 for r in report_items if r['category'] == 'EXACT_FIT')}")
    lines.append("")

    # Suggestion
    straddling = categories.get('STRADDLING', [])
    if straddling:
        all_starts = [r['us_start'] for r in straddling if r['us_start'] > 0]
        all_ends = [r['us_end'] for r in straddling if r['us_end'] > 0]
        if all_starts and all_ends:
            lines.append(f"SUGGESTION: Create or extend an epoch to cover "
                         f"{min(all_starts):.0f}-{max(all_ends):.0f}")
            lines.append("")

    # Details per category
    cat_order = ['STRADDLING', 'NO_EPOCH', 'NO_MATCH', 'WIDER_EPOCH', 'EXACT_FIT']
    for cat in cat_order:
        if cat not in categories:
            continue
        items = categories[cat]
        lines.append("-" * 72)
        lines.append(f"{cat_labels.get(cat, cat)} ({len(items)} nodes)")
        lines.append("-" * 72)
        for r in items:
            chrono = ""
            if r['us_start'] > 0 or r['us_end'] > 0:
                chrono = f" [{r['us_start']:.0f}-{r['us_end']:.0f}]"
            level_note = f" (from {r['epoch_level']})" if r['epoch_level'] else ""
            lines.append(f"  {r['node_name']}{chrono}{level_note}")
            lines.append(f"    {r['message']}")
        lines.append("")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return report_path


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class EM_OT_merge_xlsx_start(bpy.types.Operator):
    """Merge an em_data.xlsx file with the active graph"""
    bl_idname = "em.merge_xlsx_start"
    bl_label = "Merge em_data.xlsx into active graph"
    bl_description = (
        "Import an em_data.xlsx (5-sheet unified schema) and compare it "
        "with the active graph. Per-claim differences are surfaced in the "
        "Conflict Resolution panel for accept/reject. Falls back to the "
        "legacy stratigraphy.xlsx format for backward compatibility"
    )
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(
        name="XLSX File",
        description="Path to the em_data.xlsx file",
        subtype='FILE_PATH'
    )

    filter_glob: StringProperty(default="*.xlsx;*.xls", options={'HIDDEN'})

    @staticmethod
    def _refresh_ui(context, graph, graphml_file):
        """Refresh Blender UI lists and statistics after merge."""
        from ..populate_lists import (
            clear_lists, populate_blender_lists_from_graph,
            update_graph_statistics
        )
        clear_lists(context)
        populate_blender_lists_from_graph(context, graph)
        update_graph_statistics(context, graph, graphml_file)

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
        global _active_conflicts, _incoming_graph, _merger, _epoch_remap_plan

        em_tools = context.scene.em_tools
        graphml_file = em_tools.graphml_files[em_tools.active_file_index]
        existing_graph = get_graph(graphml_file.name)

        if existing_graph is None:
            self.report({'ERROR'}, "No active graph loaded")
            return {'CANCELLED'}

        # Import XLSX into a temporary graph. Two schemas are supported:
        #   - Unified em_data.xlsx (5 sheets: Units/Epochs/Claims/Authors/Documents)
        #   - Legacy stratigraphy.xlsx (24-column wide table on sheet 'Stratigraphy')
        # The schema is auto-detected by sheet presence.
        try:
            import pandas as _pd
            with _pd.ExcelFile(self.filepath, engine='openpyxl') as xl:
                sheet_names = set(xl.sheet_names)
            unified_required = {'Units', 'Epochs', 'Claims', 'Authors', 'Documents'}

            if unified_required.issubset(sheet_names):
                from s3dgraphy.importer.unified_xlsx_importer import (
                    UnifiedXLSXImporter)
                importer = UnifiedXLSXImporter(
                    filepath=self.filepath,
                    graph_id=f"incoming_{os.path.basename(self.filepath)}",
                )
                temp_graph = importer.parse()
            elif 'Stratigraphy' in sheet_names:
                from s3dgraphy.importer.mapped_xlsx_importer import (
                    MappedXLSXImporter)
                importer = MappedXLSXImporter(
                    filepath=self.filepath,
                    mapping_name='excel_to_graphml_mapping'
                )
                temp_graph = importer.parse()
            else:
                self.report(
                    {'ERROR'},
                    "Unrecognised xlsx schema. Expected either the unified "
                    "em_data.xlsx (5 sheets) or the legacy stratigraphy.xlsx "
                    "(sheet 'Stratigraphy').",
                )
                return {'CANCELLED'}

            _incoming_graph = temp_graph

        except Exception as e:
            self.report({'ERROR'}, f"Error importing XLSX: {str(e)}")
            return {'CANCELLED'}

        # ── Epoch Compatibility Check ──
        epoch_report = _build_epoch_report(existing_graph, _incoming_graph)

        has_blocking = any(
            r['category'] in ('STRADDLING', 'NO_EPOCH', 'NO_MATCH')
            for r in epoch_report
        )

        # Populate epoch report in UI
        em_tools.epoch_report.clear()
        for r in epoch_report:
            item = em_tools.epoch_report.add()
            item.node_name = r['node_name']
            item.category = r['category']
            item.us_start = r['us_start']
            item.us_end = r['us_end']
            item.epoch_level = r['epoch_level']
            item.matched_epoch = r['matched_epoch_name']
            item.message = r['message']

        if has_blocking:
            # Show epoch report and block the merge
            em_tools.epoch_report_active = True
            em_tools.epoch_report_has_errors = True
            _incoming_graph = None

            # Auto-export conflict report next to the XLSX file
            report_path = _export_epoch_report(self.filepath, epoch_report)
            em_tools.epoch_report_file = report_path

            errors = [r for r in epoch_report
                      if r['category'] in ('STRADDLING', 'NO_EPOCH', 'NO_MATCH')]

            self.report({'ERROR'},
                        f"Merge blocked: {len(errors)} epoch issues. "
                        f"Report saved to {os.path.basename(report_path)}. "
                        f"See Conflict Resolution panel (scroll down in EM sidebar).")
            return {'CANCELLED'}

        # Build epoch remap plan for non-blocking results
        _epoch_remap_plan = {}
        from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
        incoming_name_to_id = {
            n.name: n.node_id for n in _incoming_graph.nodes
            if isinstance(n, StratigraphicNode)
        }

        for r in epoch_report:
            if r['matched_epoch_node'] is not None:
                strat_id = incoming_name_to_id.get(r['node_name'])
                if strat_id:
                    _epoch_remap_plan[strat_id] = r['matched_epoch_node'].node_id

        # If there are WIDER_EPOCH warnings, show report (non-blocking)
        has_warnings = any(r['category'] == 'WIDER_EPOCH' for r in epoch_report)
        if has_warnings:
            em_tools.epoch_report_active = True
            em_tools.epoch_report_has_errors = False

        # ── Graph comparison ──
        _merger = GraphMerger()
        _active_conflicts = _merger.compare(existing_graph, _incoming_graph)

        user_conflicts = _merger.get_unresolved_conflicts(_active_conflicts)

        if not user_conflicts:
            # No conflicts - apply all changes directly
            _merger.apply_resolutions(existing_graph, _active_conflicts, _incoming_graph)

            # Apply epoch remapping
            _apply_epoch_remap(existing_graph, _incoming_graph, _epoch_remap_plan)

            _active_conflicts = []
            _incoming_graph = None
            _epoch_remap_plan = {}
            em_tools.epoch_report_active = False

            # Refresh UI
            self._refresh_ui(context, existing_graph, graphml_file)

            n_ok = sum(1 for r in epoch_report if r['category'] == 'EXACT_FIT')
            n_warn = sum(1 for r in epoch_report if r['category'] == 'WIDER_EPOCH')
            msg = f"XLSX merged successfully: {n_ok} nodes matched epochs"
            if n_warn:
                msg += f", {n_warn} with wider epoch (check report)"
            self.report({'INFO'}, msg)
            return {'FINISHED'}

        # Populate Blender property for UI display
        em_tools.merge_conflicts.clear()
        for conflict in _active_conflicts:
            if conflict.resolved:
                continue
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

        item = em_tools.merge_conflicts[idx]
        item.resolved = True
        item.accepted = (self.action == 'ACCEPT')

        unresolved = [c for c in _active_conflicts if not c.resolved]
        if idx < len(unresolved):
            unresolved[idx].resolved = True
            unresolved[idx].accepted = (self.action == 'ACCEPT')

        self._advance_to_next_unresolved(context)
        return {'FINISHED'}

    def _advance_to_next_unresolved(self, context):
        em_tools = context.scene.em_tools
        for i, item in enumerate(em_tools.merge_conflicts):
            if not item.resolved:
                em_tools.merge_conflict_index = i
                return
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
        return all(item.resolved for item in em_tools.merge_conflicts)

    def execute(self, context):
        global _active_conflicts, _incoming_graph, _merger, _epoch_remap_plan
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

        # Apply epoch remapping
        _apply_epoch_remap(existing_graph, _incoming_graph, _epoch_remap_plan)

        # Save to GraphML using the patcher
        filepath = normalize_path(graphml_file.graphml_path)
        # Write-lock pre-flight — the merge overwrites the target .graphml.
        from ..graphml_lock import abort_if_graphml_locked
        if not abort_if_graphml_locked(self, filepath):
            return {'CANCELLED'}
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

        # Refresh UI
        EM_OT_merge_xlsx_start._refresh_ui(context, existing_graph, graphml_file)

        # Clean up
        _active_conflicts = []
        _incoming_graph = None
        _merger = None
        _epoch_remap_plan = {}
        em_tools.merge_active = False
        em_tools.merge_conflicts.clear()
        em_tools.epoch_report_active = False

        return {'FINISHED'}


class EM_OT_cancel_merge(bpy.types.Operator):
    """Cancel the current merge operation"""
    bl_idname = "em.cancel_merge"
    bl_label = "Cancel Merge"
    bl_options = {'REGISTER'}

    def execute(self, context):
        global _active_conflicts, _incoming_graph, _merger, _epoch_remap_plan

        _active_conflicts = []
        _incoming_graph = None
        _merger = None
        _epoch_remap_plan = {}

        em_tools = context.scene.em_tools
        em_tools.merge_active = False
        em_tools.merge_conflicts.clear()
        em_tools.epoch_report.clear()
        em_tools.epoch_report_active = False
        em_tools.epoch_report_has_errors = False

        self.report({'INFO'}, "Merge cancelled")
        return {'FINISHED'}


class EM_OT_open_epoch_report(bpy.types.Operator):
    """Open the exported epoch conflict report in the system text editor"""
    bl_idname = "em.open_epoch_report"
    bl_label = "Open Epoch Report"

    def execute(self, context):
        report_path = context.scene.em_tools.epoch_report_file
        if not report_path or not os.path.exists(report_path):
            self.report({'ERROR'}, "Report file not found")
            return {'CANCELLED'}

        import subprocess
        import sys

        if sys.platform == 'darwin':
            subprocess.Popen(['open', report_path])
        elif sys.platform == 'win32':
            os.startfile(report_path)
        else:
            subprocess.Popen(['xdg-open', report_path])

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
        em_tools = context.scene.em_tools
        return em_tools.merge_active or em_tools.epoch_report_active

    def draw(self, context):
        layout = self.layout
        em_tools = context.scene.em_tools

        # Header help button
        header_row = layout.row(align=True)
        header_row.label(text="Conflict Resolution", icon='ERROR')
        help_op = header_row.operator("em.help_popup", text="", icon='QUESTION')
        help_op.title = "Merge Conflict Resolution"
        help_op.text = (
            "Resolve conflicts when merging a stratigraphy\n"
            "XLSX with an existing graph: keep existing,\n"
            "use incoming, or apply per-field choices. Also\n"
            "shows epoch compatibility reports."
        )
        help_op.url = "panels/em_setup.html#graphml-merge-conflict"
        help_op.project = 'em_tools'

        # ── Epoch Compatibility Report ──
        if em_tools.epoch_report_active and len(em_tools.epoch_report) > 0:
            self._draw_epoch_report(layout, em_tools)

        # ── Standard Conflict Resolution ──
        if em_tools.merge_active:
            self._draw_conflicts(layout, em_tools)

    def _draw_epoch_report(self, layout, em_tools):
        """Draw the epoch compatibility report section."""
        report = em_tools.epoch_report
        is_blocking = em_tools.epoch_report_has_errors

        # Header
        header_box = layout.box()
        if is_blocking:
            header_box.label(
                text="MERGE BLOCKED: Epoch Incompatibilities",
                icon='ERROR')
            header_box.label(
                text="Fix the XLSX data or modify graph epochs, then retry.")
        else:
            header_box.label(
                text="Epoch Report (warnings only)",
                icon='INFO')

        # Group by category
        categories = {}
        for item in report:
            cat = item.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)

        # Draw blocking issues first
        cat_order = ['STRADDLING', 'NO_EPOCH', 'NO_MATCH', 'WIDER_EPOCH', 'EXACT_FIT']
        cat_icons = {
            'STRADDLING': 'ERROR',
            'NO_EPOCH': 'ERROR',
            'NO_MATCH': 'ERROR',
            'WIDER_EPOCH': 'QUESTION',
            'EXACT_FIT': 'CHECKMARK',
            'INCOMPLETE': 'INFO',
        }
        cat_labels = {
            'STRADDLING': 'Straddling (blocks merge)',
            'NO_EPOCH': 'No chronology (blocks merge)',
            'NO_MATCH': 'No matching epoch (blocks merge)',
            'WIDER_EPOCH': 'Wider epoch (warning)',
            'EXACT_FIT': 'Exact fit',
        }

        for cat in cat_order:
            if cat not in categories:
                continue

            items = categories[cat]
            box = layout.box()
            icon = cat_icons.get(cat, 'DOT')
            label = cat_labels.get(cat, cat)
            box.label(text=f"{label}: {len(items)} nodes", icon=icon)

            # Show details for blocking categories and warnings
            if cat in ('STRADDLING', 'NO_EPOCH', 'NO_MATCH', 'WIDER_EPOCH'):
                col = box.column(align=True)
                for item in items[:10]:  # Limit display
                    row = col.row()
                    row.scale_y = 0.8
                    row.label(text=f"  {item.node_name}: {item.message[:80]}")
                if len(items) > 10:
                    col.label(text=f"  ... and {len(items) - 10} more")

        # Suggestion box for straddling
        if 'STRADDLING' in categories:
            suggest_box = layout.box()
            suggest_box.label(text="Suggestion:", icon='LIGHT')

            # Find the needed epoch range
            all_starts = [i.us_start for i in categories['STRADDLING']
                          if i.us_start > 0]
            all_ends = [i.us_end for i in categories['STRADDLING']
                        if i.us_end > 0]
            if all_starts and all_ends:
                needed_start = min(all_starts)
                needed_end = max(all_ends)
                suggest_box.label(
                    text=f"  Create/extend an epoch to cover "
                         f"{needed_start:.0f}-{needed_end:.0f}")

        # Report file info and actions
        if em_tools.epoch_report_file:
            file_box = layout.box()
            file_box.label(text="Report exported:", icon='FILE_TEXT')
            file_box.label(text=f"  {os.path.basename(em_tools.epoch_report_file)}")
            row = file_box.row(align=True)
            op = row.operator("em.open_epoch_report", text="Open Report",
                              icon='FILEBROWSER')

        # Cancel button (always available for epoch report)
        if is_blocking:
            layout.separator()
            row = layout.row()
            row.scale_y = 1.5
            row.operator("em.cancel_merge", text="Close Report", icon='CANCEL')

    def _draw_conflicts(self, layout, em_tools):
        """Draw the standard conflict resolution UI."""
        conflicts = em_tools.merge_conflicts
        total = len(conflicts)
        resolved_count = sum(1 for c in conflicts if c.resolved)
        idx = em_tools.merge_conflict_index

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

            if item.resolved:
                status = "ACCEPTED" if item.accepted else "REJECTED"
                icon = 'CHECKMARK' if item.accepted else 'X'
                detail_box.label(text=f"Status: {status}", icon=icon)
            else:
                detail_box.label(text="Status: PENDING", icon='QUESTION')

            detail_box.label(text=f"Node: {item.node_name}", icon='OBJECT_DATA')
            detail_box.label(text=f"Field: {item.field_name}")

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
            for line in current_text[:300].split('\n')[:5]:
                col.label(text=f"  {line}")

            col.separator()
            col.label(text="Incoming value:", icon='IMPORT')
            incoming_text = item.incoming_value if item.incoming_value else "(empty)"
            for line in incoming_text[:300].split('\n')[:5]:
                col.label(text=f"  {line}")

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
    EM_OT_open_epoch_report,
    EMTOOLS_PT_conflict_resolution,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
