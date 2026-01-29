# operators/__init__.py

# Import existing modules first
from .update_graph import *

# Now import the help_popup module
from .help_popup import *

# Import XLSX to GraphML converter
from .xlsx_to_graphml import *

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
    "XLSX_OT_to_graphml",
    "get_active_graph_code",
    "get_graph_code_from_graph",
    "node_name_to_proxy_name",
    "proxy_name_to_node_name",
    "should_use_prefix_in_ui",
    "get_proxy_from_node",
    "get_node_from_proxy"
]

print("DEBUG operators/__init__.py: Imported help_popup module and added EM_help_popup to __all__")


def register():
    """Register all operators in this module."""
    # Import submodules that have register() functions
    from . import update_graph
    from . import help_popup
    from . import xlsx_to_graphml

    # Register each submodule
    update_graph.register()
    help_popup.register()
    xlsx_to_graphml.register()
    print("DEBUG operators/__init__.py: All operators registered")


def unregister():
    """Unregister all operators in this module."""
    # Import submodules
    from . import update_graph
    from . import help_popup
    from . import xlsx_to_graphml

    # Unregister in reverse order
    xlsx_to_graphml.unregister()
    help_popup.unregister()
    update_graph.unregister()
    print("DEBUG operators/__init__.py: All operators unregistered")