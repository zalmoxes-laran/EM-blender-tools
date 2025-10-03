# operators/__init__.py

# Import existing modules first
from .update_graph import *

# Now import the help_popup module
from .help_popup import *

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
    "get_active_graph_code",
    "get_graph_code_from_graph",
    "node_name_to_proxy_name",
    "proxy_name_to_node_name",
    "should_use_prefix_in_ui",
    "get_proxy_from_node",
    "get_node_from_proxy"
]

print("DEBUG operators/__init__.py: Imported help_popup module and added EM_help_popup to __all__")