"""Pytest conftest at the repo root — intentionally near-empty.

This file used to physically rename the addon's ``__init__.py`` aside
during the pytest session and restore it on exit. The rename was
needed because the rootdir's ``__init__.py`` does ``import bpy`` at
module level — that import fails outside Blender's addon loader, and
pytest's discovery walked into the rootdir as if it were a package
and triggered the import.

The new strategy avoids touching the working tree entirely. See
``pytest.ini``:

    addopts = ... --rootdir=tests --confcutdir=tests

Those two flags tell pytest that the project root for the run is
``tests/`` (where there is no ``__init__.py``), and that conftest
discovery stops there too. With this, the rootdir's ``__init__.py``
is never imported by pytest, so ``import bpy`` is never executed
outside Blender. Tests still resolve ``import_operators`` etc. via
``pythonpath = . tests`` in ``pytest.ini`` (paths are read relative
to the directory of ``pytest.ini``, i.e. the actual repo root, so
the addon source remains importable for the tests that need it).

This file is kept as a placeholder for two reasons:

1. To document the migration (so a future contributor doesn't bring
   back the rename hack on autopilot).
2. To avoid the situation where some external runner (an IDE, an
   unusual CI invocation) finds no conftest at the rootdir and
   decides to walk upward.

Real test-time setup, if it ever becomes necessary, belongs in
``tests/conftest.py`` (under the ``--confcutdir`` boundary).
"""
