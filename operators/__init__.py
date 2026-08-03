# operators/__init__.py

# Import existing modules first
from .update_graph import *

# Now import the help_popup module
from .help_popup import *

# Import XLSX to GraphML converter
from .xlsx_to_graphml import *

# Import save template operators
from .save_template import *

# Import bake paradata operator
from .bake_paradata import *

# Import XLSX wizard operators (legacy 3-step stratigraphy.xlsx -> GraphML).
# The StratiMiner authoring flow that used to sit beside this one moved OUT of
# EMtools in SM3 (2026-08-03): folder -> em_data.xlsx -> em.json is data work, not
# Blender modelling, and it now lives in EMStudio over s3Dgraphy's api. What stays
# here is what touches the ACTIVE graph: see `merge_conflict_ui`.
from .xlsx_wizard import *

# Import Hybrid-C auxiliary-lifecycle operators (orphan list + bake)
from .aux_lifecycle import *

from .addon_prefix_helpers import (
    get_active_graph_code,
    get_graph_code_from_graph,
    node_name_to_proxy_name,
    proxy_name_to_node_name,
    should_use_prefix_in_ui,
    get_proxy_from_node,
    get_node_from_proxy
)

# Update the __all__ list to include the new class
__all__ = [
    "EM_OT_update_graph",
    "EM_help_popup",
    "EM_open_docs",
    "XLSX_OT_to_graphml",
    "EMTOOLS_OT_save_stratigraphy_template",
    "EMTOOLS_OT_save_em_paradata_template",
    "PARADATA_OT_bake",
    "XLSX_WIZARD_OT_convert_stratigraphy",
    "XLSX_WIZARD_OT_export_graphml",
    "AUX_OT_create_host_for_orphan",
    "AUX_OT_revert_injector",
    "AUX_OT_bake_to_graphml",
    "get_active_graph_code",
    "get_graph_code_from_graph",
    "node_name_to_proxy_name",
    "proxy_name_to_node_name",
    "should_use_prefix_in_ui",
    "get_proxy_from_node",
    "get_node_from_proxy"
]



def register():
    """Register all operators in this module."""
    # Import submodules that have register() functions
    from . import update_graph
    from . import help_popup
    from . import xlsx_to_graphml
    from . import save_template
    from . import bake_paradata
    from . import xlsx_wizard
    from . import aux_lifecycle
    from . import merge_conflict_ui

    # Register each submodule
    update_graph.register()
    help_popup.register()
    xlsx_to_graphml.register()
    save_template.register()
    bake_paradata.register()
    xlsx_wizard.register()
    aux_lifecycle.register()
    merge_conflict_ui.register()


def unregister():
    """Unregister all operators in this module."""
    # Import submodules
    from . import update_graph
    from . import help_popup
    from . import xlsx_to_graphml
    from . import save_template
    from . import bake_paradata
    from . import xlsx_wizard
    from . import aux_lifecycle
    from . import merge_conflict_ui

    # Unregister in reverse order
    merge_conflict_ui.unregister()
    aux_lifecycle.unregister()
    xlsx_wizard.unregister()
    bake_paradata.unregister()
    save_template.unregister()
    xlsx_to_graphml.unregister()
    help_popup.unregister()
    update_graph.unregister()
