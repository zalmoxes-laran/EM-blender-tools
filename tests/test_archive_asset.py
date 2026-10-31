"""MICRO-ARCHIVE-ASSET (31 Oct 2026) · EM Tools' half, bpy-free: the list of
the assets is EMStudio's Archive › Asset; the Deck › Heriverse says the
summary in one row and «Open in EMStudio › Archive › Asset» reaches EMStudio
through the Sidecar or the room's link, as «Prepare in EMStudio» does."""

import importlib.util
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("_emtools_publication_heriverse_aa",
                                               _REPO / "publication_heriverse.py")
PH = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = PH
_spec.loader.exec_module(PH)


def test_the_summary_is_one_row():
    cons = {"counts": {"models": 98, "with_base": 1, "too_heavy": 3, "tileset_master": 1,
                       "status": {"ok": 2, "necessary": 96}}}
    line = PH.consolidation_summary(cons)
    assert line.startswith("98 models · 1 with the mobile base · 96 to do")
    assert "3 too heavy" in line and "1 tileset master to declare" in line
    assert PH.consolidation_summary({"counts": {"models": 1, "status": {"ok": 1}}}).endswith("nothing to do")


def test_the_link_to_archive_asset():
    s = PH.asset_list_link(sidecar_clients=1, room={}, platform="aton")
    assert s["way"] == "sidecar" and s["envelope"] == {"type": "open", "what": "assets", "target": "web"}
    r = PH.asset_list_link(sidecar_clients=0, room={"server": "https://n.example/em", "room": "templu"})
    assert r["way"] == "link" and r["url"].startswith("stratigraph://open?")
    assert "view=assets" in r["url"] and "target=web" in r["url"] and "room=templu" in r["url"]
    off = PH.asset_list_link(sidecar_clients=0, room={})
    assert off["way"] is None and "Archive › Asset" in off["say"]


def test_the_deck_draws_no_list_any_more():
    src = (_REPO / "publication_deck_ui" / "heriverse.py").read_text(encoding="utf-8")
    body = src[src.index("def _draw_consolidated"):src.index("    def draw(self, context):")]
    assert "em.deck_open_asset_list" in body and "consolidation_summary" in body
    assert not re.search(r"for row in rows\[", body) and "em.deck_heriverse_prepare" not in body
    assert "EM_OT_deck_open_asset_list" in src[src.index("CLASSES = ("):]
