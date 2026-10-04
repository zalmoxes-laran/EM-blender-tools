"""I1 · every state of s3Dgraphy's list has its sign in EMtools, and EMtools
draws no state that is not in the list."""
import importlib.util
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
if _S3D.is_dir() and str(_S3D) not in sys.path:
    sys.path.insert(0, str(_S3D))

spec = importlib.util.spec_from_file_location("_em_state_symbols", _REPO / "state_symbols.py")
ss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss)


def test_every_state_has_its_sign_and_none_is_invented():
    listed = set(ss.symbols()["states"])
    assert set(ss.ICONS) == listed, (set(ss.ICONS) ^ listed)


def test_the_sign_carries_the_glyph_and_the_meaning_of_the_list():
    icon, text, meaning = ss.sign("file.on_disk", "it")
    assert icon == "DISK_DRIVE" and text == "● sul disco" and "questo computer" in meaning
    assert ss.sign("file.empty_copy")[1] == "◌ empty copy"
