"""Shared helpers for creating Stratigraphic Units across flows.

The three consumer flows — ProxyBox Creator, Surface Areas, and the
Stratigraphy Manager's ``+ Add US`` button — used to duplicate the US
creation logic (type factory, epoch binding, graph mutation, list
population). This module centralises:

- :func:`create_us_node` — single entry point that materialises the
  US node in the graph, wires ``has_first_epoch`` + optional
  ``is_in_activity`` + optional stratigraphic relation, populates
  the Stratigraphy Manager list, and pins ``units_index`` on the new
  unit. Returns ``(ok, us_node, error_msg)``.
- :func:`draw_activity_picker` — a reusable UI widget (``prop_search``
  over ``scene.activity_manager.activities``) that also surfaces a
  warning when the picked Activity's epoch disagrees with the US's.
- :func:`draw_us_create_widget` — a ready-made form combining type,
  name (with ``+`` suggest), epoch, activity, and optional
  stratigraphic link. Accepts toggles to hide any section so a
  consumer can choose the scope.
- :func:`refresh_activity_list` — small wrapper that re-runs
  ``activity.refresh_list`` for the active graphml, keeping the
  Activity dropdown fresh after an import or manual edit.

All Activity-related helpers read ``scene.activity_manager.activities``
(populated by :class:`ACTIVITY_OT_refresh_list` from
``ActivityNodeGroup`` nodes in the graph).
"""

from __future__ import annotations

import uuid
from typing import Optional, Tuple


# ══════════════════════════════════════════════════════════════════
# Backend — US creation factory
# ══════════════════════════════════════════════════════════════════

def create_us_node(scene,
                   graph,
                   us_type: str,
                   name: str,
                   epoch_name: str,
                   activity_name: Optional[str] = None,
                   description: str = "",
                   strat_link_target: Optional[str] = None,
                   strat_link_rel: str = "is_after"
                   ) -> Tuple[bool, Optional[object], str]:
    """Create a Stratigraphic Unit in ``graph`` and expose it through
    the Stratigraphy Manager list.

    Parameters
    ----------
    scene : bpy.types.Scene
        Host scene — used to populate ``em_tools.stratigraphy.units``
        and pin ``units_index`` on the new US.
    graph : :class:`s3dgraphy.Graph`
        Target graph.
    us_type : str
        Canonical node_type (``US``, ``USN``, ``USVs``, …). Dispatched
        through :func:`us_types.get_us_class` so new types added to the
        JSON datamodel propagate here automatically.
    name : str
        Display name (e.g. ``US.5``). Must be non-empty and unique in
        ``scene.em_tools.stratigraphy.units`` — the check catches
        duplicates introduced by concurrent create flows.
    epoch_name : str
        Name of the EpochNode in ``graph``. Mandatory: every US owns a
        first-epoch anchor (EM convention — no year required, but the
        epoch binding IS).
    activity_name : str, optional
        Name of an :class:`ActivityNodeGroup` in ``graph``. When
        provided, an ``is_in_activity`` edge from the US to the
        Activity is written — at save time the GraphMLPatcher places
        the US XML inside the Activity's nested ``<graph>``.
    description : str, optional
        Stored on the new node's ``description`` attribute.
    strat_link_target : str, optional
        Name of an existing US in the graph. When set, a stratigraphic
        relation edge (``is_after`` / ``is_before``) is written from
        the new US to the target.
    strat_link_rel : str
        ``"is_after"`` (default) or ``"is_before"`` — direction of the
        stratigraphic relation. Anything else falls back to
        ``is_after``.

    Returns
    -------
    (ok, us_node, error_msg) : tuple
        On failure ``us_node`` is ``None`` and ``error_msg`` holds a
        human-readable reason suitable for ``Operator.report``.
    """
    name = (name or "").strip()
    if not name:
        return False, None, "US name is empty"
    if not epoch_name:
        return False, None, (
            "US needs a first-epoch anchor — pick one before creating.")
    strat = scene.em_tools.stratigraphy
    for u in strat.units:
        if u.name == name:
            return False, None, (
                f"Stratigraphic Unit {name!r} already exists — pick "
                f"it from the list instead of creating a duplicate.")

    # Factory via us_types (single source of truth — JSON datamodel).
    try:
        from .us_types import get_us_class
    except ImportError:
        from us_types import get_us_class  # running outside package
    node_class = get_us_class(us_type)
    if node_class is None:
        from s3dgraphy.nodes import StratigraphicUnit
        node_class = StratigraphicUnit

    try:
        us_node = node_class(
            node_id=str(uuid.uuid4()), name=name,
            description=description or "")
        graph.add_node(us_node)
    except Exception as e:
        return False, None, f"Failed to create US node: {e}"

    # ── Epoch anchoring ───────────────────────────────────────────
    linked_epoch = False
    for n in graph.nodes:
        if (getattr(n, 'name', '') == epoch_name
                and type(n).__name__ == 'EpochNode'):
            _ensure_edge(graph, us_node.node_id, n.node_id,
                         "has_first_epoch")
            linked_epoch = True
            break
    if not linked_epoch:
        return False, None, (
            f"Epoch {epoch_name!r} not found in graph — refresh the "
            f"epoch list and retry.")

    # ── Optional activity containment ─────────────────────────────
    if activity_name:
        activity_ok, activity_err = _link_us_to_activity(
            graph, us_node, activity_name)
        if not activity_ok:
            # Don't roll back the US — just surface the error so the
            # caller can report the partial result.
            return False, us_node, activity_err

    # ── Optional stratigraphic relation ───────────────────────────
    if strat_link_target:
        strat_rel = (strat_link_rel
                     if strat_link_rel in ("is_after", "is_before")
                     else "is_after")
        matched = False
        for n in graph.nodes:
            if (getattr(n, 'name', '') == strat_link_target
                    and getattr(n, 'node_type', '') not in (
                        '', 'ActivityNodeGroup', 'ParadataNodeGroup',
                        'document', 'property', 'combiner',
                        'extractor')):
                _ensure_edge(graph, us_node.node_id, n.node_id,
                             strat_rel)
                matched = True
                break
        if not matched:
            return False, us_node, (
                f"Stratigraphic link target {strat_link_target!r} "
                f"not found or not a stratigraphic node.")

    # ── Populate the Stratigraphy Manager list + pin as active ────
    try:
        from .populate_lists import (
            populate_stratigraphic_node, build_instance_chains)
    except ImportError:
        from populate_lists import (
            populate_stratigraphic_node, build_instance_chains)
    try:
        idx = len(strat.units)
        chains = build_instance_chains(graph)
        populate_stratigraphic_node(
            scene, us_node, idx,
            graph=graph, instance_chains=chains)
        strat.units_index = idx
    except Exception as e:
        return False, us_node, f"Failed to populate US list: {e}"

    return True, us_node, ""


def _ensure_edge(graph, source_id: str, target_id: str,
                  edge_type: str) -> None:
    """Add an edge only when no matching one exists (same source,
    target, type). Keeps the Create flow idempotent on retries.
    """
    for e in graph.edges:
        if (e.edge_source == source_id
                and e.edge_target == target_id
                and e.edge_type == edge_type):
            return
    edge_id = f"{source_id}_{edge_type}_{target_id}"
    graph.add_edge(
        edge_id=edge_id,
        edge_source=source_id,
        edge_target=target_id,
        edge_type=edge_type,
    )


def _link_us_to_activity(graph, us_node,
                           activity_name: str) -> Tuple[bool, str]:
    """Write ``US --is_in_activity--> Activity`` when the named
    ActivityNodeGroup exists. Returns ``(ok, err)``.
    """
    from s3dgraphy.nodes.group_node import ActivityNodeGroup
    for n in graph.nodes:
        if (isinstance(n, ActivityNodeGroup)
                and getattr(n, 'name', '') == activity_name):
            _ensure_edge(graph, us_node.node_id, n.node_id,
                         "is_in_activity")
            return True, ""
    return False, (
        f"Activity {activity_name!r} not found in graph — refresh "
        f"the Activity list and retry.")


def propagate_us_activity_to_pd(graph, us_node_id: str,
                                  pd_group_id: str) -> None:
    """If ``us_node_id`` has an ``is_in_activity`` edge, mirror it
    onto ``pd_group_id`` so the PD nodegroup sits inside the same
    Activity at save time.

    Called by the ProxyBox / Surface Areas flows right after they
    create the per-US PD group. Keeping the US and its PD in the
    same Activity container is the EM convention — splitting them
    would leave the PD floating in the swimlane while the US is
    nested under the Activity.
    """
    for edge in graph.edges:
        if (edge.edge_source == us_node_id
                and edge.edge_type == "is_in_activity"):
            _ensure_edge(graph, pd_group_id, edge.edge_target,
                         "is_in_activity")
            return


def refresh_activity_list(context) -> bool:
    """Re-populate ``scene.activity_manager.activities`` from the
    active GraphML. Returns True on success.

    Called after Activity imports or when the user clicks a refresh
    button. Internally dispatches to ``activity.refresh_list`` with
    the active graphml index.
    """
    import bpy
    em_tools = context.scene.em_tools
    if em_tools.active_file_index < 0:
        return False
    try:
        bpy.ops.activity.refresh_list(
            graphml_index=em_tools.active_file_index)
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════
# UI widgets
# ══════════════════════════════════════════════════════════════════

def draw_add_us_button(layout, text: str = ""):
    """Draw a button that launches the shared ``strat.add_us`` dialog.

    Uses the custom ``proxies_rows_add`` icon when available so the
    button is visually distinct from the generic ``ADD`` (``+``) used
    by the "next number" suggestion inside the dialog itself. Falls
    back to the built-in ``ADD`` icon when the custom icon is missing.

    Returns the operator handle so callers can chain ``.property =
    value`` if future parameters are added.
    """
    try:
        from . import icons_manager
    except ImportError:
        import icons_manager  # running outside package
    icon_id = icons_manager.get_custom_icon("proxies_rows_add")
    if icon_id:
        return layout.operator(
            "strat.add_us", text=text, icon_value=icon_id)
    return layout.operator(
        "strat.add_us", text=text, icon='ADD')


def update_activity_filter(self, context):
    """Update callback for epoch fields — re-runs the Activity
    filter so the Activity picker only lists units that belong to
    the current epoch.

    Works for every owner that exposes either ``new_us_epoch``
    (ProxyBox / Surface Areas settings) or ``epoch_name`` (Operator
    transient props like ``STRAT_OT_add_us``).

    Implementation note: we **do not** call ``bpy.ops`` from here.
    Blender silently rejects operator invocations during property
    update callbacks because the operator context isn't ready — the
    symptom is "the filter never runs" even though no error
    surfaces. We reach into the populator helper directly instead,
    which only needs the ``activity_manager`` PropertyGroup.
    """
    epoch = (getattr(self, 'new_us_epoch', '')
             or getattr(self, 'epoch_name', '')
             or '')
    amgr = getattr(context.scene, 'activity_manager', None)
    if amgr is None:
        return
    try:
        from .activity_manager.operators import (
            _populate_filtered_activities)
    except ImportError:
        try:
            from activity_manager.operators import (
                _populate_filtered_activities)
        except Exception as e:
            print(f"[us_helpers] Activity populator import failed: {e}")
            return
    try:
        _populate_filtered_activities(amgr, epoch)
    except Exception as e:
        # Visible print — silent-fail was masking real bugs here.
        print(f"[us_helpers] Activity filter failed "
              f"(epoch={epoch!r}): {e}")


def draw_activity_picker(layout, scene, target_owner,
                          target_prop_name: str,
                          epoch_name: Optional[str] = None,
                          text: str = "Activity",
                          refresh_button: bool = True):
    """Draw an Activity picker (``prop_search`` on
    ``scene.activity_manager.filtered_activities``) — the
    pre-filtered view populated by
    :class:`ACTIVITY_OT_filter_by_epoch`. When the owner's epoch
    field has an ``update_activity_filter`` callback wired, the list
    follows the selection automatically. The refresh icon re-filters
    on demand (e.g. after an Activity list import).

    Parameters
    ----------
    layout, scene : Blender UI handles.
    target_owner : the PropertyGroup that owns ``target_prop_name``
        (where the picked name lands).
    target_prop_name : str
        Name of the StringProperty to write into.
    epoch_name : str, optional
        Bound to the refresh button — re-filters the picker for this
        epoch when the button is pressed. Also surfaces the "no
        activities for this epoch" hint when the filtered list is
        empty.
    text : str
        Label next to the picker.
    refresh_button : bool
        Include a refresh icon that re-runs the epoch filter
        (``ACTIVITY_OT_filter_by_epoch``).
    """
    amgr = getattr(scene, 'activity_manager', None)
    if amgr is None:
        layout.label(text="(activity_manager not available)",
                     icon='ERROR')
        return

    # No activities at all → prompt the user to refresh from the graph.
    if not amgr.activities:
        row = layout.row(align=True)
        row.label(text="(no activities — load a graph with "
                       "activities first)",
                  icon='INFO')
        if refresh_button:
            op = row.operator("activity.refresh_list",
                              text="", icon='FILE_REFRESH')
            em_tools = getattr(scene, 'em_tools', None)
            if em_tools is not None:
                op.graphml_index = em_tools.active_file_index
        return

    # prop_search over the filtered view. When the filter hasn't been
    # primed yet (e.g. first panel draw after graph load), fall back
    # to the unfiltered list so the user sees SOMETHING and can click
    # refresh to narrow down.
    picker_collection = (amgr.filtered_activities
                         if len(amgr.filtered_activities) > 0
                         else amgr.activities)
    picker_prop = ("filtered_activities"
                   if picker_collection is amgr.filtered_activities
                   else "activities")
    row = layout.row(align=True)
    row.prop_search(target_owner, target_prop_name,
                    amgr, picker_prop,
                    text=text, icon='GROUP')
    if refresh_button:
        op = row.operator("activity.filter_by_epoch",
                          text="", icon='FILE_REFRESH')
        op.epoch_name = epoch_name or ""

    # Informative lines below the picker.
    if epoch_name and picker_prop == "filtered_activities" \
            and len(amgr.filtered_activities) == 0:
        warn = layout.row()
        warn.alert = True
        warn.label(
            text=f"⚠ No activities for epoch "
                 f"{epoch_name!r} — pick one manually or create a "
                 f"new activity.",
            icon='ERROR')
    elif epoch_name and picker_prop == "activities":
        # Filter not primed yet — tell the user to hit refresh.
        hint = layout.row()
        hint.label(
            text=f"(filter not primed — click ↻ to restrict "
                 f"to epoch {epoch_name!r})",
            icon='INFO')


def draw_us_create_widget(layout, scene, owner,
                            *,
                            type_prop: str = "new_us_type",
                            name_prop: str = "new_us_name",
                            epoch_prop: str = "new_us_epoch",
                            activity_prop: Optional[str] = "new_us_activity",
                            suggest_op: str = "proxybox.suggest_next_us",
                            show_type: bool = True,
                            show_epoch: bool = True,
                            show_activity: bool = True):
    """Draw the standard "new US" form: type → name (+ suggest) →
    epoch → activity. Each section is togglable so niche flows can
    omit what they don't need (e.g. Stratigraphy Manager may want all
    sections, Surface Areas may opt out of activity).

    Required StringProperties on ``owner``:
    ``{type_prop, name_prop, epoch_prop[, activity_prop]}``.
    ``suggest_op`` is the bl_idname of the "+ next number" operator
    (per flow: ``proxybox.suggest_next_us``, ``emtools.suggest_next_us``
    for Surface Areas, or a Stratigraphy-side one).
    """
    em_tools = scene.em_tools

    if show_type:
        layout.prop(owner, type_prop, text="Type")

    name_row = layout.row(align=True)
    name_row.prop(owner, name_prop, text="Name")
    if suggest_op:
        name_row.operator(suggest_op, text="", icon='ADD')

    if show_epoch:
        epochs = getattr(em_tools, 'epochs', None)
        if epochs is not None and epochs.list:
            epoch_row = layout.row(align=True)
            epoch_row.alert = not bool(getattr(owner, epoch_prop, ""))
            epoch_row.prop_search(owner, epoch_prop,
                                   epochs, "list",
                                   text="Epoch *")
        else:
            layout.label(text="No epochs defined — create one first.",
                         icon='ERROR')

    if show_activity and activity_prop:
        picked_epoch = getattr(owner, epoch_prop, "") \
            if show_epoch else None
        draw_activity_picker(layout, scene, owner, activity_prop,
                              epoch_name=picked_epoch or None,
                              text="Activity")
