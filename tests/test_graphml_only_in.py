"""G1 · the GraphML comes in once, and nothing writes one again.

Decision of E.D. (4 Oct 2026): a GraphML is read for a one-time import, the
graph then lives in an em.json beside it (name confirmed by the person), and no
gesture of the add-on writes a GraphML. Measured here without Blender: the
em.json name proposed beside the GraphML never names an existing file, and no
module the add-on loads calls a GraphML writer. The Blender half (the slot
becoming the em.json, the models and proxies in it) is
`tests/blender_smoke_graphml_into_emjson.py`.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _entry():
    spec = importlib.util.spec_from_file_location(
        "_emt_graphml_entry", _REPO / "em_setup" / "graphml_entry.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


entry = _entry()


def test_the_em_json_is_proposed_beside_the_graphml(tmp_path):
    graphml = tmp_path / "TempluMare_EM_converted_converted 3.graphml"
    graphml.write_text("<graphml/>")
    assert entry.proposed_emjson_path(str(graphml)) == str(
        tmp_path / "TempluMare_EM_converted_converted 3.em.json")


def test_the_proposal_never_names_an_existing_file(tmp_path):
    graphml = tmp_path / "scavo.graphml"
    graphml.write_text("<graphml/>")
    (tmp_path / "scavo.em.json").write_text("{}")
    (tmp_path / "scavo-2.em.json").write_text("{}")
    assert entry.proposed_emjson_path(str(graphml)) == str(tmp_path / "scavo-3.em.json")


def test_a_typed_name_gets_exactly_one_em_json():
    assert entry.normalised_emjson_path("/a/b/scavo") == "/a/b/scavo.em.json"
    assert entry.normalised_emjson_path("/a/b/scavo.json") == "/a/b/scavo.em.json"
    assert entry.normalised_emjson_path("/a/b/scavo.graphml") == "/a/b/scavo.em.json"
    assert entry.normalised_emjson_path("/a/b/scavo.em.json") == "/a/b/scavo.em.json"


#: the one module allowed to write a .graphml: «Convert 1.x → 1.5» prepares an
#: OLD GraphML for reading (a new `_converted.graphml`, the source untouched) —
#: it belongs to the way in
_WAY_IN = {"operators/graphml_converter.py"}

#: a CALL or an IMPORT of a writer, or an operator id drawn — not a word in a
#: docstring
_WRITERS = re.compile(
    r"(GraphMLExporter|GraphMLPatcher|graph_to_graphml)\s*\(|"
    r"import\s.*\b(GraphMLExporter|GraphMLPatcher|graph_to_graphml)\b|"
    r"graphml_(update|saveas)\s*\(|"
    r"[\"'](export\.graphml_update|export\.graphml_saveas|paradata\.bake_to_graphml)[\"']")


def test_no_module_of_the_addon_writes_a_graphml():
    offenders = []
    for path in _REPO.rglob("*.py"):
        rel = path.relative_to(_REPO).as_posix()
        if rel.startswith(("_dead_code/", "tests/", "build/", ".venv/", "wheels/")) \
                or rel in _WAY_IN:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if _WRITERS.search(code):
                offenders.append(f"{rel}:{n}: {line.strip()}")
    assert offenders == [], "\n".join(offenders)


def test_save_as_offers_em_json_only():
    source = (_REPO / "export_operators" / "exporter_emjson.py").read_text(encoding="utf-8")
    assert '("GRAPHML"' not in source
    assert "*.graphml" not in source


def test_loading_a_graphml_ends_in_its_em_json():
    source = (_REPO / "import_operators" / "importer_graphml.py").read_text(encoding="utf-8")
    assert "from ..em_setup.graphml_entry import convert" in source
    assert "invoke_props_dialog" in source and "emjson_path" in source
