"""
Scene properties for Graph Editor filtering and configuration
"""

import bpy
from bpy.props import BoolProperty, EnumProperty, CollectionProperty, IntProperty
from bpy.types import PropertyGroup

class EdgeTypeFilter(PropertyGroup):
    """Singolo filtro per tipo di edge"""
    edge_type: bpy.props.StringProperty(
        name="Edge Type",
        description="Type of edge/connection"
    )
    
    label: bpy.props.StringProperty(
        name="Label",
        description="Human readable label"
    )
    
    enabled: bpy.props.BoolProperty(
        name="Show",
        description="Include this edge type in graph",
        default=True
    )
    
    category: bpy.props.EnumProperty(
        name="Category",
        items=[
            ('STRATIGRAPHIC', "Stratigraphic", "Physical relationships"),
            ('TEMPORAL', "Temporal", "Time relationships"),
            ('PARADATA', "Paradata", "Documentation"),
            ('MODEL', "3D Models", "Representation models"),
            ('OTHER', "Other", "Other connections"),
        ],
        default='OTHER'
    )


class GraphEditorSettings(PropertyGroup):
    """Settings per Graph Editor"""
    
    # Filter mode
    active_filter_mode: EnumProperty(
        name="Filter Mode",
        items=[
            ('ALL', "All Nodes", "Show all nodes in graph"),
            ('STRATIGRAPHIC', "Stratigraphic", "Show only stratigraphic nodes"),
            ('US_ONLY', "US Only", "Show only US nodes"),
            ('FROM_UILIST', "From UI List", "Show only nodes in current UI list"),
            ('NEIGHBORHOOD', "Neighborhood", "Show node + connected neighbors"),
            ('NODE_CONTEXT', "Node + Context", "Show node with stratigraphic neighbors and all paradata"),
            ('EDGE_FILTERED', "Custom Edge Filter", "Filter by selected edge types"),
        ],
        default='ALL'
    )
    
    # Neighborhood settings
    neighborhood_depth: IntProperty(
        name="Neighborhood Depth",
        description="Number of connection levels to show",
        default=1,
        min=1,
        max=5
    )
    
    # Node + Context settings
    show_stratigraphic_context: BoolProperty(
        name="Stratigraphic Context",
        description="Show stratigraphic connections (is_before, overlies, etc.)",
        default=True
    )
    
    show_paradata_context: BoolProperty(
        name="Paradata Context",
        description="Show all paradata (has_property, extracted_from, etc.)",
        default=True
    )
    
    show_model_context: BoolProperty(
        name="Model Context",
        description="Show 3D model connections",
        default=True
    )
    
    # Edge type filters (populated dynamically)
    edge_filters: CollectionProperty(type=EdgeTypeFilter)
    
    # UI helpers
    show_edge_filter_panel: BoolProperty(
        name="Show Edge Filters",
        description="Show panel to configure edge type filters",
        default=False
    )


def initialize_edge_filters(context):
    """Inizializza i filtri edge dalla configurazione s3dgraphy"""
    from .utils import get_edge_types
    
    settings = context.scene.graph_editor_settings
    settings.edge_filters.clear()
    
    edge_types = get_edge_types()
    
    # Categorizza gli edge types
    stratigraphic = ['is_before', 'is_after', 'has_same_time', 'changed_from',
                     'overlies', 'is_overlain_by', 'abuts', 'is_abutted_by',
                     'cuts', 'is_cut_by', 'fills', 'is_filled_by', 'rests_on',
                     'is_bonded_to', 'is_physically_equal_to']
    
    temporal = ['has_first_epoch', 'survive_in_epoch', 'has_timebranch', 
                'is_in_timebranch', 'contrasts_with']
    
    paradata = ['has_property', 'has_data_provenance', 'extracted_from',
                'combines', 'has_documentation', 'is_in_paradata_nodegroup',
                'has_paradata_nodegroup', 'is_in_activity']
    
    model = ['has_representation_model', 'has_semantic_shape', 'has_linked_resource']
    
    for et in edge_types:
        item = settings.edge_filters.add()
        item.edge_type = et['type']
        item.label = et['label']
        item.enabled = True  # Tutti abilitati di default
        
        # Determina categoria
        if et['type'] in stratigraphic:
            item.category = 'STRATIGRAPHIC'
        elif et['type'] in temporal:
            item.category = 'TEMPORAL'
        elif et['type'] in paradata:
            item.category = 'PARADATA'
        elif et['type'] in model:
            item.category = 'MODEL'
        else:
            item.category = 'OTHER'
    
    print(f"✓ Initialized {len(settings.edge_filters)} edge type filters")


classes = (
    EdgeTypeFilter,
    GraphEditorSettings,
)

def register_properties():
    """Register property classes"""
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
    
    # Add to Scene
    bpy.types.Scene.graph_editor_settings = bpy.props.PointerProperty(type=GraphEditorSettings)
    
    print("✓ Graph Editor properties registered")

def unregister_properties():
    """Unregister property classes"""
    # Remove from Scene
    if hasattr(bpy.types.Scene, 'graph_editor_settings'):
        del bpy.types.Scene.graph_editor_settings
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass