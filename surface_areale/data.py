"""
PropertyGroup definitions for the Surface Areale system.
Stores settings and state for surface proxy creation on Representation Models.
"""

import bpy
from bpy.props import (
    PointerProperty, EnumProperty, BoolProperty,
    StringProperty, FloatProperty, IntProperty,
    FloatVectorProperty
)
from bpy.types import PropertyGroup


def _mesh_poll(self, obj):
    """Filter for mesh objects only."""
    return obj.type == 'MESH'


def _us_type_items():
    """Thin wrapper around :func:`us_types.get_us_type_items` — the
    datamodel JSON (via s3dgraphy's classification API) is the single
    source of truth. Deferred import so PropertyGroup registration
    never depends on module-level order.

    Kept because ``us_type`` still drives the areale material colour
    (``assign_em_material`` in postprocess). US creation itself has
    moved to the shared ``strat.add_us`` dialog.
    """
    from ..us_types import get_us_type_items
    return get_us_type_items(
        include_series=True, include_special=False)


class SurfaceArealeSettings(PropertyGroup):
    """Settings for the Surface Areale creation tool."""

    # ── Target RM ──────────────────────────────────────────────────────
    target_rm: PointerProperty(
        type=bpy.types.Object,
        name="Target RM",
        description="The Representation Model to create the surface areale on",
        poll=_mesh_poll
    )

    # ── US Type ────────────────────────────────────────────────────────
    # Items sourced dynamically from the JSON datamodel — see us_types.
    # The legacy ``GENERIC`` option (associate-later placeholder) has
    # been dropped: if the user doesn't want to commit to a US, they
    # can use the existing-US branch with the picker left empty, or
    # link the areale after the fact.
    us_type: EnumProperty(
        name="US Type",
        description="Type of stratigraphic unit for this areale",
        items=lambda self, context: _us_type_items(),
    )

    # ── US Linking ─────────────────────────────────────────────────────
    # Single path: pick an existing US. Need a new one? The UI row
    # includes a ``+`` button that launches the shared
    # ``strat.add_us`` dialog — after the dialog closes the new unit
    # is already the active one, so the user just picks it here.
    linked_us_name: StringProperty(
        name="Linked US",
        description="Name of the Stratigraphic Unit this areale "
                    "belongs to. Use the ``+`` next to the picker to "
                    "create a new one via the shared Add-US dialog."
    )

    # ── Document ───────────────────────────────────────────────────────
    # DP-07 unified flow: documents are created via the shared
    # Master-Document dialog (docmanager.create_master_document), not
    # inline. The Surface Areas picker now uses
    # ``draw_document_picker_with_create_button`` — it writes the chosen
    # document's name into ``existing_document`` (also populated by the
    # "+ Add New Document..." wrapper after a fresh create).
    linked_document: StringProperty(
        name="Document",
        description="Document auto-detected from RM graph connections "
                    "(read-only display)"
    )

    existing_document: StringProperty(
        name="Document",
        description="Name of the document node to associate with this "
                    "RM (picked via the shared Document Manager picker)"
    )

    # ── Strategy ───────────────────────────────────────────────────────
    strategy: EnumProperty(
        name="Strategy",
        description="Generation strategy for the surface areale",
        items=[
            ('AUTO', 'Auto', 'Automatically classify surface complexity and choose best strategy'),
            ('PROJECTIVE', 'Projective', 'For nearly-planar surfaces — fast (frescoes, slabs, floors)'),
            ('SHRINKWRAP', 'Shrinkwrap', 'For surfaces with edges/corners — medium (architraves, cornices)'),
            ('BOOLEAN', 'Boolean', 'For fully 3D surfaces — slower but most accurate (capitals, reliefs)'),
        ],
        default='AUTO'
    )

    # ── Paradata (pre-filled, editable) ──────────────────────────────
    extractor_name: StringProperty(
        name="Extractor Method",
        description="Method used to extract the geometry from the RM",
        default="3D drawing on surface"
    )

    property_name: StringProperty(
        name="Property Name",
        description="Name of the property node linking US to its proxy geometry",
        default="geometry"
    )

    show_chain_summary: BoolProperty(
        name="Show Chain Summary",
        description="Toggle the narrative summary of the graph chain to be created",
        default=False
    )

    # ── Geometry Parameters ────────────────────────────────────────────
    offset_distance: FloatProperty(
        name="Normal Offset",
        description="Distance to offset the areale from the RM surface (anti z-fighting)",
        default=0.001,
        min=0.0001,
        max=0.01,
        precision=4,
        subtype='DISTANCE',
        unit='LENGTH'
    )

    max_triangles: IntProperty(
        name="Max Triangles",
        description="Maximum number of triangles for the areale mesh",
        default=500,
        min=50,
        max=10000
    )

    resample_distance: FloatProperty(
        name="Resample Distance",
        description="Distance between resampled contour points",
        default=0.003,
        min=0.001,
        max=0.05,
        precision=4,
        subtype='DISTANCE',
        unit='LENGTH'
    )

    subdivision_iterations: IntProperty(
        name="Subdivision Iterations",
        description="Max adaptive subdivision iterations for surface conformity",
        default=3,
        min=1,
        max=6
    )

    conformity_threshold: FloatProperty(
        name="Conformity Threshold",
        description="Max allowed distance from RM surface before subdividing",
        default=0.001,
        min=0.0001,
        max=0.01,
        precision=4,
        subtype='DISTANCE',
        unit='LENGTH'
    )

    # ── LOD for Boolean Strategy ──────────────────────────────────────
    use_lod: BoolProperty(
        name="Use LOD",
        description=(
            "Use a decimated copy of the RM for Boolean operation "
            "(faster for high-poly meshes, result is re-projected onto full-res RM)"
        ),
        default=False
    )

    lod_factor: FloatProperty(
        name="LOD Factor",
        description="Decimation ratio for the LOD copy (0.1 = 10% of original polygons)",
        default=0.3,
        min=0.05,
        max=1.0,
        precision=2,
        subtype='FACTOR'
    )

    # ── GP Drawing Preferences ────────────────────────────────────────
    gp_stroke_color: FloatVectorProperty(
        name="Stroke Color",
        description="Color of the Grease Pencil stroke for drawing areale contours",
        subtype='COLOR',
        default=(0.0, 1.0, 0.2),  # Bright green
        min=0.0, max=1.0,
        size=3
    )

    gp_stroke_thickness: IntProperty(
        name="Stroke Thickness",
        description="Pixel thickness of the Grease Pencil stroke",
        default=5,
        min=1,
        max=20
    )

    # ── Workflow State ─────────────────────────────────────────────────
    is_drawing: BoolProperty(
        name="Drawing Active",
        default=False
    )

    drawing_phase: EnumProperty(
        name="Phase",
        items=[
            ('IDLE', 'Idle', ''),
            ('CONTOUR', 'Drawing Contour', ''),
            ('WHISKER', 'Drawing Whisker', ''),
        ],
        default='IDLE'
    )


def register():
    # SurfaceArealeSettings is registered by em_props.py (required before EM_Tools)
    pass


def unregister():
    # SurfaceArealeSettings is unregistered by em_props.py
    pass
