"""E5 · registration and unregistration walk ONE list.

`unregister_modules` kept a list of its own, which had lost seven modules: on
disabling EM Tools their PropertyGroups stayed registered, and enabling it
again said «already registered» five times (graph_info, dtc_authoring,
resources_tab, publication_deck_ui, shelf_tool). Measured in Blender by
`blender_smoke_tapestry_apart.py`, which disables and enables EM Tools: 0.
"""
import ast
import pathlib

_SRC = (pathlib.Path(__file__).resolve().parent.parent / "__init__.py").read_text()
_TREE = ast.parse(_SRC)


def _func(name):
    return next(n for n in _TREE.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _calls(fn, name):
    return any(isinstance(c, ast.Call) and getattr(c.func, "id", None) == name for c in ast.walk(fn))


def test_LE_DUE_STRADE_LEGGONO_LA_STESSA_LISTA():
    assert _calls(_func("register_modules"), "_core_independent_modules")
    assert _calls(_func("unregister_modules"), "_core_independent_modules")


def test_I_CINQUE_SONO_NELLA_LISTA():
    names = {n.id for n in ast.walk(_func("_core_independent_modules")) if isinstance(n, ast.Name)}
    for m in ("graph_info", "dtc_authoring", "resources_tab", "publication_deck_ui", "shelf_tool"):
        assert m in names, m
