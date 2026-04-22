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
    # automatically from ``ProxyBoxSettings.document_node_name`` on Record
    # when ``propagate_doc_to_points`` is True).
    source_document: StringProperty(
        name="Source Document",
        description="Document NAME (e.g. D.10) this point was extracted from",
        default="",
    )  # type: ignore

    source_document_name: StringProperty(
        name="Source Document Name",
        description="Display name of the source document",
        default="",
    )  # type: ignore

    extractor_id: StringProperty(
        name="Extractor Node ID",
        description="ID of the extractor node created for this point "
                    "(e.g., D.10.11)",
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

    # Active US — picked via ``prop_search`` on
    # ``em_tools.stratigraphy.units``. The Create flow resolves the
    # target US by this name, and the proxy mesh takes the same name.
    # When empty, the operator falls back to the Stratigraphy Manager's
    # current ``units_index``.
    target_us_name: StringProperty(
        name="Active US",
        description="Stratigraphic Unit this proxy belongs to; also "
                    "used as the proxy mesh name",
        default="",
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
