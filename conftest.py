"""Pytest configuration that handles Blender addon root package.

The root __init__.py imports bpy (only available in Blender), which prevents
pytest from running tests outside of Blender. This conftest temporarily
renames the root __init__.py during test discovery and execution.
"""

from pathlib import Path
import shutil


def pytest_configure(config):
    """Hide the root __init__.py before pytest imports it."""
    root_init = Path(config.rootdir) / "__init__.py"
    root_init_backup = Path(config.rootdir) / "__init__.py.bak"

    if root_init.exists() and not root_init_backup.exists():
        shutil.move(str(root_init), str(root_init_backup))


def pytest_sessionfinish(session, exitstatus):
    """Restore the root __init__.py after tests are done."""
    root = Path(session.config.rootdir)
    root_init = root / "__init__.py"
    root_init_backup = root / "__init__.py.bak"

    if root_init_backup.exists() and not root_init.exists():
        shutil.move(str(root_init_backup), str(root_init))
