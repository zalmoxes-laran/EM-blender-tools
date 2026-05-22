"""Pytest configuration that safely handles Blender addon root __init__.py.

The root __init__.py imports bpy (only available in Blender), which prevents
pytest from running tests outside of Blender. This conftest temporarily
renames it during test collection/execution, using try/finally to ensure
safe restoration even on failure.
"""

from pathlib import Path
import shutil
import atexit


def pytest_configure(config):
    """Hide the root __init__.py before pytest imports it."""
    root_init = Path(config.rootdir) / "__init__.py"
    root_init_backup = Path(config.rootdir) / "__init__.py.bak"

    # Only rename if it exists and backup doesn't already exist
    if root_init.exists() and not root_init_backup.exists():
        shutil.move(str(root_init), str(root_init_backup))
        
        # Register cleanup in case of crash
        def cleanup():
            if root_init_backup.exists() and not root_init.exists():
                shutil.move(str(root_init_backup), str(root_init))
        
        atexit.register(cleanup)


def pytest_sessionfinish(session, exitstatus):
    """Restore the root __init__.py after tests are done."""
    root = Path(session.config.rootdir)
    root_init = root / "__init__.py"
    root_init_backup = root / "__init__.py.bak"

    if root_init_backup.exists() and not root_init.exists():
        shutil.move(str(root_init_backup), str(root_init))
