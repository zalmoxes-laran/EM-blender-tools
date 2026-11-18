"""MICRO-U-VOCABOLARI-COME-FONT (E.D., 18 Nov 2026): EM Tools shows a controlled
value in Blender's language from the vocabularies installed on the machine (the
folder shared with EMStudio, s3dgraphy.authorities.packages), else the label
saved with it, and marks a value «not controlled». ``vocabulary_labels`` does
not import bpy; the colour schemes take the code from the same seam."""
import hashlib
import importlib.util
import io
import json
import pathlib
import zipfile

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("vocabulary_labels", _REPO / "vocabulary_labels.py")
VL = importlib.util.module_from_spec(spec)
spec.loader.exec_module(VL)

terms = pytest.importorskip("s3dgraphy.terms")
from s3dgraphy.authorities import packages as P  # noqa: E402
from s3dgraphy.nodes.property_node import PropertyNode  # noqa: E402

AAT = "http://vocab.getty.edu/aat/300011286"
NT = (f'<{AAT}> <http://www.w3.org/2004/02/skos/core#prefLabel> "limestone"@en .\n'
      f'<{AAT}> <http://www.w3.org/2004/02/skos/core#prefLabel> "calcare"@it .\n').encode()


@pytest.fixture
def machine(tmp_path, monkeypatch):
    monkeypatch.setenv("EM_VOCABULARIES_DIR", str(tmp_path / "v"))
    P._changed()
    m = {"format": P.PACKAGE_FORMAT, "id": "getty-aat-materials", "version": "2026-11-18",
         "snapshot_date": "2026-11-18", "languages": [], "license": "ODC-By 1.0", "tier": "A",
         "attribution": "Getty", "serves": ["material_type"],
         "source": {"file": "source/a.nt", "sha256": hashlib.sha256(NT).hexdigest()}}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifest.json", json.dumps(m))
        z.writestr("source/a.nt", NT)
    P.vocab_install(buf.getvalue())
    yield
    P._changed()


def _linked():
    n = PropertyNode(node_id="p", name="Material", value="calcare")
    terms.set_term(n, {"concept": AAT, "label": "calcare", "lang": "it",
                       "vocabulary": "getty-aat-materials", "version": "2026-11-18"})
    return n


def test_blender_locale_to_tag():
    assert VL.blender_lang("it_IT") == "it"
    assert VL.blender_lang("zh_HANS") == "zh-hans"
    assert VL.blender_lang("DEFAULT") == "en" and VL.blender_lang("") == "en"


def test_label_in_blender_language_then_saved_then_missing(machine):
    n = _linked()
    assert VL.display(n, "en") == ("limestone", "linked")
    assert VL.display(n, "fr") == ("calcare", "linked")
    P.vocab_remove("getty-aat-materials")
    assert VL.display(n, "en") == ("calcare", "missing")
    assert VL.list_text(n, "en") == "◆? calcare"


def test_uncontrolled_and_free(machine):
    assert VL.list_text(PropertyNode(node_id="a", name="Material", value="Limestone"), "en") == "◇ Limestone"
    assert VL.display(PropertyNode(node_id="b", name="height", value="2.3"), "en") == ("2.3", "free")


def test_the_colour_schemes_take_the_code_from_the_same_seam(machine):
    spec2 = importlib.util.spec_from_file_location("_fs", _REPO / "visual_manager" / "file_schemes.py")
    fs = importlib.util.module_from_spec(spec2)
    import sys
    sys.path.insert(0, str(_REPO))
    try:
        spec2.loader.exec_module(fs)
        assert fs.value_code_of(_linked()) == AAT
        assert fs.value_code_of(PropertyNode(node_id="x", name="Material", value="x")) is None
    finally:
        sys.path.remove(str(_REPO))
