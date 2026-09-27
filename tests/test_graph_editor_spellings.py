"""Il filtro del graph editor trova la legatura in ENTRAMBE le grafie.

Connections datamodel 1.6.20 (s3Dgraphy) dichiara ``spelling_of`` sulle due
grafie vecchie: ``is_bonded_to`` → ``bonded_to``, ``is_physically_equal_to`` →
``equals``. Da pyArchInit (e dall'xlsx generico) ora arriva la canonica.

Il graph editor aveva due liste scritte a mano che conoscevano solo la vecchia;
e sotto c'era un guasto più grosso: ``get_connection_rules`` importava
``s3dgraphy.graph.connection_rules``, tolto da s3Dgraphy il 2026-04-03, e
restituiva ``[]`` — nessun filtro, nessun contesto stratigrafico, per NESSUNA
grafia. Qui si carica il VERO ``graph_editor`` (utils, properties, operators)
con un ``bpy`` finto, e si esercitano i veri ``initialize_edge_filters``,
``filter_by_edge_types`` e ``get_node_context`` su un grafo s3dgraphy vero.

Le grafie non sono scritte in questo file: si leggono dal datamodel.
"""
import sys
import types
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True, scope="module")
def _restore_sys_modules():
    """Il ``bpy`` finto e il pacchetto caricato qui NON escono da questo modulo:
    altri test installano un loro ``bpy`` solo se manca, e trovandoci il nostro
    (senza ``bpy.path``) fallirebbero — misurato su
    test_import_validator_pg::test_pyarchinit_accepts_sqlite_filepath."""
    keys = ("bpy", "bpy.props", "bpy.types")
    saved = {k: sys.modules.get(k) for k in keys}
    yield
    for k in [k for k in sys.modules if k == "emt_ge_pkg" or k.startswith("emt_ge_pkg.")]:
        del sys.modules[k]
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v


def _fake_bpy():
    """Il minimo perché i tre moduli si importino: proprietà e classi base."""
    if "bpy" in sys.modules and getattr(sys.modules["bpy"], "_emt_fake", False):
        return
    bpy = types.ModuleType("bpy")
    bpy._emt_fake = True
    props = types.ModuleType("bpy.props")
    for name in ("BoolProperty", "EnumProperty", "CollectionProperty",
                 "IntProperty", "StringProperty", "FloatProperty",
                 "PointerProperty"):
        setattr(props, name, lambda *a, **k: None)
    btypes = types.ModuleType("bpy.types")
    for name in ("PropertyGroup", "Operator", "Panel", "UIList", "Menu"):
        setattr(btypes, name, type(name, (), {}))
    bpy.props, bpy.types = props, btypes
    sys.modules["bpy"] = bpy
    sys.modules["bpy.props"] = props
    sys.modules["bpy.types"] = btypes


def _load_graph_editor():
    """``emt_ge_pkg.graph_editor.{utils,properties,layout,operators}`` dai file
    veri, senza eseguire gli ``__init__`` (che registrano classi Blender)."""
    _fake_bpy()
    base = "emt_ge_pkg"
    if f"{base}.graph_editor.operators" in sys.modules:
        return (sys.modules[f"{base}.graph_editor.utils"],
                sys.modules[f"{base}.graph_editor.properties"],
                sys.modules[f"{base}.graph_editor.operators"])
    root = types.ModuleType(base); root.__path__ = [str(ROOT)]
    sys.modules[base] = root
    ge = types.ModuleType(f"{base}.graph_editor")
    ge.__path__ = [str(ROOT / "graph_editor")]
    sys.modules[f"{base}.graph_editor"] = ge

    def load(dotted, path):
        spec = spec_from_file_location(dotted, path)
        mod = module_from_spec(spec)
        sys.modules[dotted] = mod
        spec.loader.exec_module(mod)
        return mod

    load(f"{base}.us_types", ROOT / "us_types.py")
    utils = load(f"{base}.graph_editor.utils", ROOT / "graph_editor/utils.py")
    props = load(f"{base}.graph_editor.properties", ROOT / "graph_editor/properties.py")
    load(f"{base}.graph_editor.layout", ROOT / "graph_editor/layout.py")
    ops = load(f"{base}.graph_editor.operators", ROOT / "graph_editor/operators.py")
    return utils, props, ops


def _dm():
    from s3dgraphy.edges import get_connections_datamodel
    return get_connections_datamodel()


def _pairs():
    """(vecchia, canonica), dal datamodel."""
    dm = _dm()
    return sorted(
        (name, d["spelling_of"])
        for name in dm.get_all_edge_names()
        for d in [dm.get_edge_definition(name) or {}] if d.get("spelling_of"))


needs_1620 = pytest.mark.skipif(
    not hasattr(_dm(), "spellings"),
    reason="s3dgraphy senza spellings() (connections < 1.6.20): lanciare con "
           "PYTHONPATH=../s3Dgraphy/src")


# ── contesto finto: la scena ha una CollectionProperty di filtri ───────────────
class _Filters(list):
    def add(self):
        item = types.SimpleNamespace(edge_type="", label="", enabled=True, category="")
        self.append(item)
        return item


def _context(**flags):
    settings = types.SimpleNamespace(
        edge_filters=_Filters(),
        show_stratigraphic_context=flags.get("strat", True),
        show_paradata_context=flags.get("para", False),
        show_model_context=flags.get("model", False),
    )
    return types.SimpleNamespace(scene=types.SimpleNamespace(graph_editor_settings=settings))


def _graph(edges):
    from s3dgraphy import Graph
    from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit
    g = Graph(graph_id="spellings")
    ids = sorted({x for _, s, t in edges for x in (s, t)})
    for i in ids:
        g.add_node(StratigraphicUnit(node_id=i, name=i.upper()))
    for n, (et, s, t) in enumerate(edges):
        g.add_edge(f"e{n}", s, t, et)
    return g


# ── 1 · il carico delle regole non è più vuoto ─────────────────────────────────
def test_the_edge_types_come_from_the_live_datamodel():
    utils, _, _ = _load_graph_editor()
    names = {et["type"] for et in utils.get_edge_types()}
    assert names, "get_edge_types() è vuoto: il guasto di connection_rules è tornato"
    assert set(_dm().get_all_edge_names()) == names
    assert {"overlies", "is_overlain_by", "cuts"} <= names


# ── 2 · la legatura è stratigrafica in ogni grafia ─────────────────────────────
@needs_1620
def test_both_spellings_are_stratigraphic_through_the_datamodel():
    utils, _, _ = _load_graph_editor()
    pairs = _pairs()
    assert pairs == [("is_bonded_to", "bonded_to"), ("is_physically_equal_to", "equals")]
    strat = {et["type"] for et in utils.get_stratigraphic_edge_types()}
    for old, canon in pairs:
        assert {old, canon} <= strat, (old, canon)
    # la lista sola nomina la CANONICA: la vecchia arriva dal datamodel
    assert not {old for old, _ in pairs} & set(utils.STRATIGRAPHIC_RELATIONS)


@needs_1620
def test_the_datamodel_decides_not_the_fallback(monkeypatch):
    """Con spellings() disponibile il fallback letterale non viene letto."""
    utils, _, _ = _load_graph_editor()
    monkeypatch.setattr(utils, "_SPELLINGS_BEFORE_1620", {})
    assert utils.with_spellings(["bonded_to"]) == {"bonded_to", "is_bonded_to"}
    assert utils.with_spellings(["overlies"]) == {"overlies"}  # un reverse non è una grafia


def test_an_old_s3dgraphy_falls_back_to_the_literal(monkeypatch):
    """Il wheel del manifest (dev17, connections 1.6.14) non ha spellings()."""
    utils, _, _ = _load_graph_editor()
    import s3dgraphy.edges as edges
    dm = types.SimpleNamespace()  # nessun metodo spellings
    monkeypatch.setattr(edges, "get_connections_datamodel", lambda *a: dm)
    assert utils.with_spellings(["bonded_to", "equals", "cuts"]) == {
        "bonded_to", "is_bonded_to", "equals", "is_physically_equal_to", "cuts"}


@needs_1620
def test_initialize_edge_filters_puts_both_spellings_under_stratigraphic():
    _, props, _ = _load_graph_editor()
    ctx = _context()
    props.initialize_edge_filters(ctx)
    cat = {f.edge_type: f.category for f in ctx.scene.graph_editor_settings.edge_filters}
    for old, canon in _pairs():
        assert cat[old] == "STRATIGRAPHIC", old
        assert cat[canon] == "STRATIGRAPHIC", canon  # era 'OTHER'


# ── 3 · il filtro e il contesto trovano la legatura, in entrambe le grafie ─────
@needs_1620
@pytest.mark.parametrize("spelling", ["is_bonded_to", "bonded_to",
                                      "is_physically_equal_to", "equals"])
def test_filter_by_edge_types_finds_the_bond(spelling):
    _, props, ops = _load_graph_editor()
    g = _graph([(spelling, "us1", "us2"), ("overlies", "us3", "us4")])
    ctx = _context()
    props.initialize_edge_filters(ctx)
    for f in ctx.scene.graph_editor_settings.edge_filters:  # solo stratigrafici
        f.enabled = f.category == "STRATIGRAPHIC"
    found = ops.GRAPHEDIT_OT_draw_graph.filter_by_edge_types(None, g, ctx)
    assert {n.node_id for n in found} == {"us1", "us2", "us3", "us4"}


@needs_1620
@pytest.mark.parametrize("spelling", ["is_bonded_to", "bonded_to",
                                      "is_physically_equal_to", "equals"])
def test_the_stratigraphic_context_reaches_across_the_bond(spelling):
    _, _, ops = _load_graph_editor()
    g = _graph([(spelling, "us1", "us2"), ("overlies", "us1", "us3")])
    ctx = _context(strat=True)
    me = types.SimpleNamespace(get_selected_node_id=lambda c: "us1")
    got = ops.GRAPHEDIT_OT_draw_graph.get_node_context(me, g, ctx)
    assert {n.node_id for n in got} == {"us1", "us2", "us3"}
