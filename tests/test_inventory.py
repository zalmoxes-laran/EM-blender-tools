"""P3 · «Bring into a room…» — EM Tools' half, around s3Dgraphy's engine.

The inventory (`inventory`), the node's doors (`asset_upload` → `node`) and
their tests moved to s3Dgraphy on 15 Oct 2026 (`room_import`, measured there by
`tests/test_room_import_inventory.py` and `tests/test_room_import.py` against
a fake node and a real one). What stays here is what only EM Tools decides:
the lot thresholds from the add-on preferences (D3), the study handed to the
engine as it is held in memory, where the journal goes.
"""

import importlib.util
import os
import pathlib
import sys
import types

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
if _S3D.is_dir() and str(_S3D) not in sys.path:
    sys.path.insert(0, str(_S3D))

from s3dgraphy.room_import import inventory as inv  # noqa: E402


def _bring():
    if "_p3_pkg" not in sys.modules:
        pkg = types.ModuleType("_p3_pkg")
        pkg.__path__ = [str(_REPO / "sync_manager")]
        sys.modules["_p3_pkg"] = pkg
    for name in ("room", "exif_lite", "bring"):
        if f"_p3_pkg.{name}" not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                f"_p3_pkg.{name}", _REPO / "sync_manager" / f"{name}.py")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
    return sys.modules["_p3_pkg.bring"]


def _at(seconds: float) -> str:
    import datetime
    return (datetime.datetime(2026, 9, 1, 10, 0, 0)
            + datetime.timedelta(seconds=seconds)).strftime("%Y:%m:%d %H:%M:%S")


def test_the_study_goes_to_the_engine_as_it_is_held():
    """The scene's LIVE graphs and the file's shelf: the engine rewrites them in
    place; the DTC corpus stays out, as in the engine."""
    from s3dgraphy.graph import Graph
    bring = _bring()
    g1, shelf, corpus = Graph("g1"), Graph("shelf"), Graph("corpus")
    c = bring.container_of({"graphs": {"g1": g1}, "shelf": shelf, "corpus": corpus,
                            "active": "g1", "header": {"x": 1}})
    assert c.graphs["g1"] is g1 and c.shelf is shelf and c.corpus is None
    assert c.active_graph_id == "g1" and c.header == {"x": 1}
    from s3dgraphy.room_import.engine import _members
    assert [gid for gid, _g in _members(c)] == ["g1", "shelf"]


def test_the_journal_goes_beside_the_study(tmp_path):
    bring = _bring()
    em = tmp_path / "a.em.json"
    assert bring.journal_path({"path": str(em)}) == str(tmp_path / ".em_room_import.json")
    assert os.path.basename(bring.journal_path({})) == ".em_room_import.json"


def test_d3_the_lot_thresholds_come_from_the_preferences():
    """D3 (E.D., 4 Oct 2026): 30 minutes and 5 photos are the defaults,
    changeable in the add-on preferences; the lot stays a proposal."""
    bring = _bring()
    no_prefs = types.SimpleNamespace(preferences=types.SimpleNamespace(addons={}))
    assert bring.lot_thresholds(no_prefs) == (1800.0, 5)
    prefs = types.SimpleNamespace(lot_gap_minutes=45, lot_min_photos=3)
    ctx = types.SimpleNamespace(preferences=types.SimpleNamespace(
        addons={"_p3_pkg": types.SimpleNamespace(preferences=prefs)}))
    gap, least = bring.lot_thresholds(ctx)
    assert (gap, least) == (2700.0, 3)
    shots = [{"id": f"w{i}", "path": f"/w/{i}.jpg",
              "exif": {"camera": "X", "taken_at": _at(2400 * i)}} for i in range(3)]
    assert inv.session_lots(shots) == []
    rows = [dict(s, group=inv.GROUP_FOUND) for s in shots]
    lots = inv.propose_sessions(rows, gap_seconds=gap, min_photos=least)
    assert [len(l["ids"]) for l in lots] == [3] and lots[0]["confirmed"] is False
