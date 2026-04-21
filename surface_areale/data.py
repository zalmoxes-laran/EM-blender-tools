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
    us_type: EnumProperty(
        name="US Type",
        description="Type of stratigraphic unit for this areale",
        items=[
            ('UL', 'Working Unit (UL)', 'Traces of stone working, toolmarks, reworkings'),
            ('TSU', 'Transformation (TSU)', 'Transformation unit: degradation, abrasion, cracks'),
            ('US_NEG', 'US Negative', 'Lacunae, removals, negative stratigraphic unit'),
            ('US', 'US Generic', 'Generic stratigraphic unit'),
            ('GENERIC', 'Generic Proxy', 'Associate to a US later'),
        ],
        default='UL'
    )

    # ── US Linking ─────────────────────────────────────────────────────
    linked_us_name: StringProperty(
        name="Linked US",
        description="Name of existing US to link this areale to (leave empty to create new)"
    )

    create_new_us: BoolProperty(
        name="Create New US",
        description="Create a new stratigraphic unit for this areale",
        default=True
    )

    new_us_name: StringProperty(
        name="New US Name",
        description="Name for the new stratigraphic unit"
    )

    new_us_epoch: StringProperty(
        name="Epoch",
        description="Epoch to assign the new US to"
    )

    link_to_existing_us: StringProperty(
        name="Stratigraphic Link",
        description="Optional: existing US to connect stratigraphically"
    )

    add_stratigraphic_link: BoolProperty(
        name="Add Stratigraphic Link",
        description=(
            "Optionally create a stratigraphic relation edge between "
            "the new US and another existing US. Leave unchecked if "
            "you don't want to declare a relation now."
        ),
        default=False
    )

    link_relation_type: EnumProperty(
        name="Relation",
        description=(
            "Direction of the stratigraphic relation between the new "
            "US (source) and the linked US (target)"
        ),
        items=[
            ('is_after', 'is_after',
             "The new US lies above / is more recent than the linked US"),
            ('is_before', 'is_before',
             "The new US lies below / is older than the linked US"),
        ],
        default='is_after'
    )

    # ── Document ───────────────────────────────────────────────────────
    linked_document: StringProperty(
        name="Document",
        description="Document auto-detected from RM graph connections (read-only display)"
    )

    create_new_document: BoolProperty(
        name="Create New Document",
        description="Create a new document node for this RM",
        default=True
    )

    existing_document: StringProperty(
        name="Existing Document",
        description="Name of an existing document node to associate with this RM"
    )

    new_doc_name: StringProperty(
        name="Document Name",
        description="Name for the new document (e.g. D.15)"
    )

    new_doc_date: StringProperty(
        name="Date",
        description="Date of the document (e.g., survey date like '2016')"
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
