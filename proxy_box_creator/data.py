"""Data structures for the Proxy Box Creator (DP-47 / DP-07 flow).

The ProxyBox Creator is anchored on a DocumentNode (Step 1); the seven
measurement points (Step 2) then inherit that document by default, so
the extractors end up chained to a single source. The proxy name is
derived from the active Stratigraphic Unit at Create time — it is not
stored on the settings.

PropertyGroup registration lives in :mod:`em_props`.
"""

import bpy  # type: ignore
from bpy.props import (  # type: ignore
    StringProperty,
    BoolProperty,
    FloatVectorProperty,
    CollectionProperty,
    EnumProperty,
)
from bpy.types import PropertyGroup  # type: ignore


def _us_type_items():
    """Thin wrapper around :func:`us_types.get_us_type_items` that
    keeps the import lazy — Blender evaluates the EnumProperty
    ``items`` callback at UI draw time, not at module load, so
    deferring the ``us_types`` import avoids circular-import snarls
    during add-on registration.

    The returned list is cached inside ``us_types`` (the macOS GC
    protection the brief calls out); we just forward the reference.
    """
    from ..us_types import get_us_type_items
    return get_us_type_items(
        include_series=True, include_special=False)


def _proxybox_activity_filter(self, context):
    """Re-filter the Activity picker's backing collection whenever
    the ProxyBox epoch field changes. Delegates to the shared
    helper so every "new US" flow (ProxyBox, Surface Areas, Strat
    Manager) reacts the same way.
    """
    from ..us_helpers import update_activity_filter
    update_activity_filter(self, context)


# ══════════════════════════════════════════════════════════════════════
# ``target_us_name`` is computed: it always reflects the Stratigraphy
# Manager's currently-active unit, and writing to it updates
# ``strat.units_index``. This gives us bidirectional sync between the
# ProxyBox panel's ``prop_search`` and the Stratigraphy Manager UI
# without any update callbacks or sentinels — prop_search reads via
# the getter and writes via the setter, and changes made elsewhere
# (Stratigraphy Manager UIList click, auto-selection on import, etc.)
# are picked up on the next draw.
# ══════════════════════════════════════════════════════════════════════


def _get_target_us_name(self):
    scene = self.id_data
    try:
        strat = scene.em_tools.stratigraphy
        if strat.units and 0 <= strat.units_index < len(strat.units):
            return strat.units[strat.units_index].name or ""
    except Exception:
        pass
    return ""


def _set_target_us_name(self, value):
    scene = self.id_data
    if not value:
        return
    try:
        strat = scene.em_tools.stratigraphy
        for i, u in enumerate(strat.units):
            if u.name == value:
                if strat.units_index != i:
                    strat.units_index = i
                return
    except Exception:
        pass


class ProxyBoxPointSettings(PropertyGroup):
    """Per-point state for one of the seven measurement points."""

    position: FloatVectorProperty(
        name="Position",
        description="3D coordinates of this point",
        subtype='XYZ',
        default=(0.0, 0.0, 0.0),
        precision=4,
    )  # type: ignore

    is_recorded: BoolProperty(
        name="Is Recorded",
        description="Whether this point has been recorded",
        default=False,
    )  # type: ignore

    point_type: StringProperty(
        name="Point Type",
        description="Semantic type of this point",
        default="",
    )  # type: ignore

    # Document and extractor bookkeeping (per-point override; populated
    # automatically from ``ProxyBoxSettings.document_node_{id,name}``
    # on Record when ``propagate_doc_to_points`` is True).
    #
    # ``source_document_id`` is the authoritative UUID: Create uses it
    # to resolve the exact anchor DocumentNode in the graph, avoiding
    # name collisions when multiple documents share the same display
    # name (e.g. a legacy "D.01" + a freshly-created "D.01" elsewhere
    # in the paradata chain).
    source_document: StringProperty(
        name="Source Document",
        description="Document display name (e.g. D.10) — used for UI. "
                    "The Create flow resolves the actual node via "
                    "``source_document_id`` (UUID) instead to dodge "
                    "name collisions.",
        default="",
    )  # type: ignore

    source_document_id: StringProperty(
        name="Source Document Node ID",
        description="UUID of the DocumentNode this point was extracted "
                    "from — authoritative for graph lookups.",
        default="",
    )  # type: ignore

    source_document_name: StringProperty(
        name="Source Document Name",
        description="Display name of the source document",
        default="",
    )  # type: ignore

    extractor_id: StringProperty(
        name="Extractor Node ID",
        description="Display name of the extractor node created for "
                    "this point (e.g., D.10.11).",
        default="",
    )  # type: ignore


class ProxyBoxSettings(PropertyGroup):
    """Top-level Proxy Box Creator state.

    Organised around the two-step flow:

    - Step 1 anchor Document → ``document_node_id`` / ``document_node_name``,
      optionally propagated to each point via ``propagate_doc_to_points``.
    - Step 2 measurement points → :class:`ProxyBoxPointSettings` collection.
    """

    # ── Step 2: 7 measurement points ─────────────────────────────────
    points: CollectionProperty(
        type=ProxyBoxPointSettings,
        name="Measurement Points",
    )  # type: ignore

    # ── Step 1: Document anchor ──────────────────────────────────────
    document_node_id: StringProperty(
        name="Document node id",
        description="UUID of the DocumentNode chosen as the Step-1 anchor",
        default="",
    )  # type: ignore

    document_node_name: StringProperty(
        name="Document name",
        description="Display name (e.g. D.10) of the Step-1 anchor document",
        default="",
    )  # type: ignore

    propagate_doc_to_points: BoolProperty(
        name="Propagate to all 7 points",
        description="Automatically inherit the Step-1 document on every "
                    "recorded point (Record fills source_document and "
                    "extractor_id). When off, each point keeps its own "
                    "document picker.",
        default=True,
    )  # type: ignore

    # Transient state for the Step 1 document picker dialog.
    pending_doc_search: StringProperty(
        name="Document",
        description="Document chosen in the Step-1 picker dialog",
        default="",
    )  # type: ignore

    # ── Parameters ───────────────────────────────────────────────────
    pivot_location: EnumProperty(
        name="Pivot Location",
        description="Location of the proxy mesh's pivot point",
        items=[
            ('BOTTOM', "Bottom", "Pivot at the bottom face (min Z)"),
            ('CENTER', "Center", "Pivot at geometric center"),
            ('TOP', "Top", "Pivot at the top face (max Z)"),
        ],
        default='BOTTOM',
    )  # type: ignore

    use_proxy_collection: BoolProperty(
        name="Use Proxy Collection",
        description="Place the created proxy in the 'Proxy' collection. "
                    "If disabled, uses the active collection.",
        default=True,
    )  # type: ignore

    # Persist the paradata chain to the .graphml immediately after
    # Create. Default True because the Create operator produces a
    # non-trivial chain (US + PropertyNode + up to 7 Extractors +
    # Combiner + has_representation_model edge) and losing it to a
    # Blender crash is expensive — the graphml write-lock guard has
    # already checked that yEd isn't holding the file.
    persist_after_create: BoolProperty(
        name="Save GraphML immediately",
        description="Persist the paradata chain to the .graphml file "
                    "right after Create. Recommended: the proxy "
                    "creates a lot of new nodes/edges and keeping "
                    "them only in memory means a crash throws them "
                    "away.",
        default=True,
    )  # type: ignore

    show_chain_summary: BoolProperty(
        name="Show Chain Summary",
        description="Toggle the narrative summary of the paradata "
                    "chain that will be created on Create.",
        default=False,
    )  # type: ignore

    # Active US — bound bidirectionally to
    # ``em_tools.stratigraphy.units_index`` via the module-level
    # get/set callbacks. Reading always yields the currently-active
    # unit's name (kept fresh whenever the Stratigraphy Manager
    # changes selection); writing via ``prop_search`` picks the unit
    # with the matching name and updates ``units_index`` in place. No
    # drift: there is no backing storage here, so the panel is always
    # showing the single authoritative value.
    target_us_name: StringProperty(
        name="Active US",
        description="Stratigraphic Unit this proxy belongs to; also "
                    "used as the proxy mesh name. Bidirectionally "
                    "linked to the Stratigraphy Manager's active US.",
        get=_get_target_us_name,
        set=_set_target_us_name,
    )  # type: ignore

    # ── Create-new-US branch (mirrors Surface Areas) ─────────────────
    create_new_us: BoolProperty(
        name="Create new US",
        description="Create a fresh Stratigraphic Unit for this proxy "
                    "instead of reusing the active one. The new US is "
                    "created and becomes active before the proxy is "
                    "built.",
        default=False,
    )  # type: ignore

    # Items are sourced dynamically from the JSON datamodel via
    # :mod:`us_types` so adding a new US type to s3dgraphy propagates
    # here automatically. Series types are included — aggregates are
    # legitimate creation targets (the proxy anchors the combiner to
    # their PropertyNode in exactly the same way).
    new_us_type: EnumProperty(
        name="US Type",
        description="Type of stratigraphic unit to create",
        items=lambda self, context: _us_type_items(),
    )  # type: ignore

    new_us_name: StringProperty(
        name="New US Name",
        description="Name for the new stratigraphic unit "
                    "(use the '+' button to auto-suggest)",
        default="",
    )  # type: ignore

    new_us_epoch: StringProperty(
        name="Epoch",
        description="Epoch to assign the new US to",
        default="",
        update=lambda self, ctx: _proxybox_activity_filter(self, ctx),
    )  # type: ignore

    # Optional Activity containment: when set, the new US is wired
    # via ``is_in_activity`` to the named ActivityNodeGroup so the
    # GraphMLPatcher places both the US and its PD group physically
    # inside the Activity's yEd group at save time.
    new_us_activity: StringProperty(
        name="Activity",
        description="ActivityNodeGroup this US belongs to (optional). "
                    "Wires an is_in_activity edge and places the US "
                    "(and its paradata nodegroup) inside the activity "
                    "container in yEd.",
        default="",
    )  # type: ignore

    # Numbering pool for the ``+ suggest next`` button.
    # False (default): per-type — US has its own series, SF another,
    # UL another, etc. ``SF.1`` is proposed even if ``US.1`` exists.
    # True: shared — every stratigraphic type draws from the same
    # numeric pool. If ``US.1``, ``US.2``, ``SF.1`` are used, the
    # next SF suggestion is ``SF.3`` (first free number globally).
    share_numbering_across_types: BoolProperty(
        name="Shared numbering across US types",
        description="Share the numeric pool across all stratigraphic "
                    "types: if ``US.1`` / ``US.2`` already exist, "
                    "the '+' button proposes ``SF.3`` instead of "
                    "``SF.1``. Off (default) keeps each type on its "
                    "own series.",
        default=False,
    )  # type: ignore

    # ── Combiner bookkeeping (auto-populated on Create) ──────────────
    combiner_id: StringProperty(
        name="Combiner ID",
        description="ID of the combiner node that will be created "
                    "(e.g., C.10)",
        default="",
    )  # type: ignore


# PropertyGroup registration is handled centrally in :mod:`em_props`.
classes: list = []


def register() -> None:
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError as e:
            print(f"[proxy_box/data] Warning: Could not register "
                  f"{cls.__name__}: {e}")


def unregister() -> None:
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()
