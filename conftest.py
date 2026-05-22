"""Pytest conftest at the repo root.

Why this exists: the Blender addon's `__init__.py` at this same level
does `import bpy` and relative imports (`from . import icons_manager`)
that only resolve inside Blender's addon loader. Pytest's discovery
walks past the rootdir `__init__.py` and Python tries to execute it,
which crashes outside Blender.

We temporarily rename `__init__.py` to `__init__.py.pytest-hidden`
during the pytest session and restore it via three independent safety
nets: pytest_sessionfinish, atexit, and SIGINT/SIGTERM handlers. Even
on a crashed pytest session the original file is restored.
"""

import atexit
import signal
import sys
from pathlib import Path


_ROOT = Path(__file__).parent
_INIT = _ROOT / "__init__.py"
_HIDDEN = _ROOT / "__init__.py.pytest-hidden"


def _restore():
    if _HIDDEN.exists() and not _INIT.exists():
        _HIDDEN.rename(_INIT)


def _signal_restore(signum, frame):
    _restore()
    sys.exit(1)


def pytest_configure(config):
    if _INIT.exists() and not _HIDDEN.exists():
        _INIT.rename(_HIDDEN)
        atexit.register(_restore)
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _signal_restore)
            except (ValueError, OSError):
                pass


def pytest_sessionfinish(session, exitstatus):
    _restore()
