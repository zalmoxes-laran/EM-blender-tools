"""F6 — an empty EPSG field means "not georeferenced", never EPSG 4326.

Until this was pinned, both ways the georef panel propagates its values —
the update callback on ``scene.em_georef`` (``props._on_georef_changed``) and
the "Propagate coordinates" operator (``EM_OT_georef_sync_all``) — read the
EPSG as ``g.epsg or '4326'``. A scene where nobody had chosen a CRS therefore
told BlenderGIS ``EPSG:4326`` and told 3D Survey Collection ``4326``: a CRS in
degrees, paired with a shift in metres, invented on the user's behalf. It is
the same lie s3Dgraphy dev29 (A6) and ``graph_sync`` already refuse for the
GeoPositionNode.

The rule pinned here:

- no EPSG → BlenderGIS is not given a CRS at all (its state is left alone),
  3DSC gets its own "absent" sentinel (``NotSet``), and the panel SAYS the scene
  is not georeferenced;
- an EPSG that IS set travels exactly as before.

The real ``props.py``, ``operators.py`` and ``panel.py`` are loaded from file
into a throw-away package with a minimal fake ``bpy`` (the approach of
``test_graph_editor_spellings``); the two adapters are replaced by recorders,
so what is asserted is what the callers actually hand to BlenderGIS and 3DSC.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_GEOREF = _REPO / "georef_manager"
_PKG = "emt_georef_pkg"


# ── fake bpy + package loading ────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _restore_sys_modules():
    """The fake ``bpy`` and the package loaded here do not leak out of this
    module: other tests install their own ``bpy`` only when it is missing."""
    keys = ("bpy", "bpy.props", "bpy.types", "bpy_extras", "bpy_extras.io_utils")
    saved = {k: sys.modules.get(k) for k in keys}
    yield
    for k in [k for k in sys.modules if k == _PKG or k.startswith(_PKG + ".")]:
        del sys.modules[k]
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v


def _fake_bpy():
    bpy = types.ModuleType("bpy")
    props = types.ModuleType("bpy.props")
    for name in ("BoolProperty", "EnumProperty", "CollectionProperty",
                 "IntProperty", "StringProperty", "FloatProperty",
                 "PointerProperty"):
        setattr(props, name, lambda *a, **k: None)
    btypes = types.ModuleType("bpy.types")
    for name in ("PropertyGroup", "Operator", "Panel"):
        setattr(btypes, name, type(name, (), {}))
    btypes.Scene = type("Scene", (), {})
    bpy.props = props
    bpy.types = btypes
    extras = types.ModuleType("bpy_extras")
    io_utils = types.ModuleType("bpy_extras.io_utils")
    io_utils.ImportHelper = type("ImportHelper", (), {})
    io_utils.ExportHelper = type("ExportHelper", (), {})
    extras.io_utils = io_utils
    sys.modules.update({
        "bpy": bpy, "bpy.props": props, "bpy.types": btypes,
        "bpy_extras": extras, "bpy_extras.io_utils": io_utils,
    })


class _Recorder:
    """Stands in for ``bgis_adapter`` / ``dsc_adapter``: always installed,
    no prior state, and every ``write_state`` call is kept."""

    def __init__(self):
        self.calls = []

    def is_available(self):
        return True

    def read_state(self, scene):
        return {'epsg': None, 'shift_x': None, 'shift_y': None, 'shift_z': None}

    def write_state(self, scene, epsg, *args, **kwargs):
        self.calls.append((epsg, args, kwargs))
        return True, "recorded"


def _load():
    """Real georef modules in a package whose adapters are recorders."""
    _fake_bpy()
    pkg = types.ModuleType(_PKG)
    pkg.__path__ = [str(_GEOREF)]
    sys.modules[_PKG] = pkg
    bgis, dsc = _Recorder(), _Recorder()
    # ``from . import bgis_adapter, dsc_adapter`` (module-level in operators and
    # panel, inside the callback in props) resolves to these.
    for name, fake in (("bgis_adapter", bgis), ("dsc_adapter", dsc)):
        mod = types.ModuleType(f"{_PKG}.{name}")
        mod.is_available = fake.is_available
        mod.read_state = fake.read_state
        mod.write_state = fake.write_state
        sys.modules[f"{_PKG}.{name}"] = mod
        setattr(pkg, name, mod)
    loaded = {}
    for name in ("shift_io", "graph_sync", "propagation", "props",
                 "operators", "panel"):
        path = _GEOREF / f"{name}.py"
        if not path.exists():  # propagation.py does not exist before F6
            continue
        spec = importlib.util.spec_from_file_location(f"{_PKG}.{name}", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"{_PKG}.{name}"] = mod
        setattr(pkg, name, mod)
        spec.loader.exec_module(mod)
        loaded[name] = mod
    loaded["graph_sync"].get_active_graph = lambda: None
    return loaded, bgis, dsc


def _context(epsg):
    g = types.SimpleNamespace(
        epsg=epsg, shift_x=291960.5, shift_y=4640631.8, shift_z=12.0,
        rotation=0.0, move_objects_on_change=False, sync_lat_lon=False,
    )
    scene = types.SimpleNamespace(em_georef=g)
    return types.SimpleNamespace(scene=scene)


def _epsgs(recorder):
    return [c[0] for c in recorder.calls]


# ── what reaches BlenderGIS and 3DSC ──────────────────────────────────────

@pytest.mark.parametrize("empty", ["", "   "])
def test_update_callback_without_epsg_passes_no_epsg(empty):
    mods, bgis, dsc = _load()
    ctx = _context(empty)
    mods["props"]._on_georef_changed(ctx.scene.em_georef, ctx)

    assert "4326" not in [str(e) for e in _epsgs(bgis) + _epsgs(dsc)]
    # BlenderGIS is not given a CRS at all: no call, its state stays as it was.
    assert bgis.calls == []
    # 3DSC still receives the shift, with no EPSG (its adapter writes NotSet).
    assert len(dsc.calls) == 1
    assert dsc.calls[0][0] is None
    assert dsc.calls[0][1] == (291960.5, 4640631.8, 12.0)


@pytest.mark.parametrize("empty", ["", "   "])
def test_propagate_operator_without_epsg_passes_no_epsg(empty):
    mods, bgis, dsc = _load()
    op = mods["operators"].EM_OT_georef_sync_all()
    reports = []
    op.report = lambda level, msg: reports.append(msg)

    assert op.execute(_context(empty)) == {'FINISHED'}
    assert "4326" not in [str(e) for e in _epsgs(bgis) + _epsgs(dsc)]
    assert bgis.calls == []
    assert [c[0] for c in dsc.calls] == [None]
    assert any("no EPSG" in m for m in reports), reports


def test_a_set_epsg_travels_unchanged():
    mods, bgis, dsc = _load()
    ctx = _context("32633")
    mods["props"]._on_georef_changed(ctx.scene.em_georef, ctx)
    op = mods["operators"].EM_OT_georef_sync_all()
    op.report = lambda level, msg: None
    op.execute(ctx)

    assert _epsgs(bgis) == ["32633", "32633"]
    assert _epsgs(dsc) == ["32633", "32633"]
    assert bgis.calls[0][1] == (291960.5, 4640631.8)


def test_bgis_adapter_refuses_to_set_a_crs_from_no_epsg(monkeypatch):
    """Belt and braces: even called directly, the adapter never writes
    ``EPSG:`` / ``EPSG:None`` into BlenderGIS."""
    spec = importlib.util.spec_from_file_location(
        "_emt_bgis_adapter", _GEOREF / "bgis_adapter.py")
    bgis_adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bgis_adapter)

    written = []

    class FakeGeoScene:
        hasOriginGeo = hasOriginPrj = hasValidCRS = False

        @property
        def crs(self):
            return None

        @crs.setter
        def crs(self, value):
            written.append(value)

        def setOriginPrj(self, *a, **k):
            written.append(("origin", a))

    monkeypatch.setattr(bgis_adapter, "is_available", lambda: True)
    monkeypatch.setattr(bgis_adapter, "_get_geoscene", lambda scene: FakeGeoScene())
    for empty in (None, "", "  "):
        ok, msg = bgis_adapter.write_state(object(), empty, 1.0, 2.0)
        assert ok is False and "EPSG" in msg
    assert written == []


# ── what the panel says ───────────────────────────────────────────────────

class _Layout:
    """Records every label the panel draws; everything else is a no-op."""

    def __init__(self, labels):
        self._labels = labels
        self.enabled = True
        self.scale_y = 1.0

    def _child(self, *a, **k):
        return _Layout(self._labels)

    column = row = box = _child

    def label(self, text="", icon='NONE'):
        self._labels.append(text)

    def prop(self, *a, **k):
        pass

    def separator(self, *a, **k):
        pass

    def operator(self, *a, **k):
        return types.SimpleNamespace()

    def panel(self, *a, **k):
        return _Layout(self._labels), None


def _panel_labels(epsg):
    mods, _bgis, _dsc = _load()
    labels = []
    panel = mods["panel"].EM_PT_georef()
    panel.layout = _Layout(labels)
    panel.draw(_context(epsg))
    return labels


def test_panel_says_not_georeferenced_without_epsg():
    labels = _panel_labels("")
    assert any("not georeferenced" in t.lower() for t in labels), labels


def test_panel_does_not_say_it_with_an_epsg():
    labels = _panel_labels("32633")
    assert not any("not georeferenced" in t.lower() for t in labels), labels
