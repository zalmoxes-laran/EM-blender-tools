# operators/__init__.py

# Import existing modules first
from .update_graph import *

# Now import the help_popup module
from .help_popup import *

# Update the __all__ list to include the new class
__all__ = [
    "EM_OT_update_graph",
    "EM_help_popup"  # Add our new class
]

print("DEBUG operators/__init__.py: Imported help_popup module and added EM_help_popup to __all__")