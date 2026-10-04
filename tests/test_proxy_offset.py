"""U2 · «Offset proxy»: the decisions without Blender. The Blender side in
tests/blender_smoke_proxy_offset.py, the shots in tests/blender_shots_proxy_offset.py."""
import importlib.util
import pathlib

_P = pathlib.Path(__file__).resolve().parent.parent / "proxy_offset" / "__init__.py"
spec = importlib.util.spec_from_file_location("_proxy_offset", _P)
po = importlib.util.module_from_spec(spec)
spec.loader.exec_module(po)


def test_the_offset_is_one_named_modifier():
    assert po.offset_names(["GT16.USV140_inflate", "EM offset", "Bevel"]) == ["EM offset"]


def test_the_old_inflation_is_recognised_by_its_suffix():
    assert po.old_inflate_names(["USV153_inflate", "EM offset", "Solidify"]) == ["USV153_inflate"]


def test_the_default_is_the_measured_centimetre():
    assert po.DEFAULT_DISTANCE == 0.01


def test_the_sentences():
    assert po.said("offset", 1, 0.01) == "1 proxy offset by 10 mm from the surface"
    assert po.said("offset", 34, 0.005) == "34 proxies offset by 5 mm from the surface"
    assert po.said("remove", 2, 0.01) == "2 proxies back on the surface"
    assert po.said("offset", 0, 0.01) == "no proxy to offset here"
    assert po.said("remove", 0, 0.01) == "no proxy to bring back here"
