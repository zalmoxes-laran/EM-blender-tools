"""The Shelf tool as part of the PROJECT — Traccia C, measured bpy-free.

The correction this file is about: **Blender does not export the shelf.** The
shelf is already a member of the container (a ShelfGraph in the em.json), so what
EMTools does is LIST it and bring one entry at a time into the scene. So the
tests below are about the three ways that could go quietly wrong:

* **listing the wrong shelf.** A project's own ShelfGraph must be found by its
  MARKER, not by an id convention — a project that came from EMStudio or from
  Heriverse used its own id, and a tool that looked for `<name>__shelf` would
  show an empty library over a full one;
* **answering the three columns here.** Residence, role and mode are the
  library's to answer (`api.shelf_table`). Computing them in this module would be
  a second answer, and a shelf with two opinions about "is this in use?" is worse
  than one with no badge. So they are read, and the test checks they are read;
* **the mode asked of the wrong subject.** A resource sits on the SHELF and is
  hatted into a STUDY graph. Ask the shelf alone and everything reads
  `only_shelf` for ever — including the model standing in the viewport.

`shelf_backend` is bpy-free by design (like `resource_backend`), which is what
makes this measurable outside Blender. The panel, the UIList and the mesh import
are not exercised here: they need bpy, and that limit is stated in the end-of
report rather than papered over.
"""

import importlib.util
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent

# the s3Dgraphy CHECKOUT wins over any installed wheel — `shelf_table` is new,
# and a stale wheel in the dev venv would make this untestable
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))

api = pytest.importorskip("s3dgraphy.api",
                          reason="s3dgraphy not importable (checkout or wheel)")
if not hasattr(api, "shelf_table"):  # pragma: no cover
    pytest.skip("s3dgraphy without shelf_table (pre-Traccia A)",
                allow_module_level=True)

from s3dgraphy.graph import Graph                                   # noqa: E402
from s3dgraphy.multigraph.multigraph import multi_graph_manager     # noqa: E402
from s3dgraphy.nodes.epoch_node import EpochNode                    # noqa: E402


def _load(module_name: str, relative: str):
    """Load one addon module by path — the package `__init__` imports bpy."""
    spec = importlib.util.spec_from_file_location(module_name, _REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


backend = _load("_emtools_shelf_backend", "shelf_tool/shelf_backend.py")


@pytest.fixture(autouse=True)
def clean_multigraph():
    """The multigraph is a SINGLETON — a test that left graphs in it would make
    the next one read somebody else's project."""
    before = dict(multi_graph_manager.graphs)
    multi_graph_manager.graphs.clear()
    backend.new_shelf()
    yield
    multi_graph_manager.graphs.clear()
    multi_graph_manager.graphs.update(before)


def a_project():
    """A project as Blender holds it: a study graph and a shelf, both members of
    the multigraph. The shelf's id is deliberately NOT `<project>__shelf`: it came
    from somewhere else, which is the case the marker exists for."""
    study = Graph(graph_id="scavo")
    study.add_node(EpochNode(node_id="ep1", name="Fase 1", start_time=-100,
                             end_time=0))
    shelf = api.new_shelf(graph_id="una-libreria-di-qualcun-altro")
    mine = api.add_to_shelf(
        shelf, "s3://em-assets/aabbcc", name="tempio (mio)",
        checksum="sha256:aabbcc", scope="own-study", residency="resident",
        role="comparandum", media_type="model/gltf-binary", size=104857,
        origin={"repo": "minio"})
    theirs = api.add_to_shelf(
        shelf, "https://zenodo.org/records/12345/files/t.glb",
        name="tempio (altrove)", scope="other-HDT", role="internal_source",
        media_type="model/gltf-binary", access={"mode": "subscribe"})
    multi_graph_manager.graphs["scavo"] = study
    multi_graph_manager.graphs[shelf.graph_id] = shelf
    return study, shelf, mine, theirs


# ── listing the project's own shelf ─────────────────────────────────────────

def test_the_projects_shelf_is_found_by_its_marker_not_its_id():
    study, shelf, _m, _t = a_project()
    found = backend.project_shelf()
    assert found is shelf, "the ShelfGraph was not recognised"
    # …and a study graph is never mistaken for one
    multi_graph_manager.graphs.pop(shelf.graph_id)
    assert backend.project_shelf() is None


def test_adopting_it_lists_it_without_a_file():
    """No path, no import: the entries came with the em.json."""
    _study, shelf, _m, _t = a_project()
    report = backend.adopt_project_shelf()
    assert report == {"adopted": True,
                      "graph_id": "una-libreria-di-qualcun-altro", "count": 2}
    assert backend.active_shelf() is shelf
    assert backend.active_path() is None, "a project shelf is not a file"
    assert {c["name"] for c in backend.cards()} == {"tempio (mio)",
                                                   "tempio (altrove)"}


def test_a_project_with_no_shelf_says_so_instead_of_inventing_one():
    study = Graph(graph_id="scavo")
    multi_graph_manager.graphs["scavo"] = study
    assert backend.project_shelf() is None
    assert backend.adopt_project_shelf() == {"adopted": False, "graph_id": None,
                                             "count": 0}


# ── the three columns come from the library ─────────────────────────────────

def test_the_cards_carry_residence_role_and_mode_from_the_library():
    study, _shelf, mine, theirs = a_project()
    backend.adopt_project_shelf()
    cards = {c["name"]: c for c in backend.refresh(study)}
    assert cards["tempio (mio)"]["residence"] == "minio"
    assert cards["tempio (mio)"]["role"] == "comparandum"
    assert cards["tempio (altrove)"]["residence"] == "uri"
    assert cards["tempio (altrove)"]["role"] == "internal_source"
    # …and BOTH are only on the shelf until somebody materialises one
    assert {c["mode"] for c in cards.values()} == {"only_shelf"}


def test_a_uri_entry_keeps_the_media_type_the_acquisition_recorded():
    """There is no file on disk to re-derive it from, so if the card did not take
    it from the library's row the cell would simply be empty."""
    study, _shelf, _m, _t = a_project()
    backend.adopt_project_shelf()
    cards = {c["name"]: c for c in backend.refresh(study)}
    assert cards["tempio (altrove)"]["exists"] is False, "it is not a local file"
    assert cards["tempio (altrove)"]["media_type"] == "model/gltf-binary"
    assert cards["tempio (mio)"]["size"] == 104857


def test_the_role_vocabulary_is_the_librarys():
    assert backend.resource_roles() == ["comparandum", "internal_source"]
    assert backend.table_supported() is True


# ── materialising one entry ─────────────────────────────────────────────────

def test_materialising_flips_the_mode_and_only_for_that_entry():
    """The measure the badge exists for: after hatting, the row says the resource
    is in the graph — and its neighbour still says it is not."""
    study, shelf, mine, theirs = a_project()
    backend.adopt_project_shelf()
    before = {c["name"]: c["mode"] for c in backend.refresh(study)}
    assert before == {"tempio (mio)": "only_shelf",
                      "tempio (altrove)": "only_shelf"}

    out = backend.hat_as_rm(study, mine["id"], epochs=["ep1"])
    assert out["created"] is True

    after = {c["name"]: c["mode"] for c in backend.refresh(study)}
    assert after["tempio (mio)"] == "used_in_graph"
    assert after["tempio (altrove)"] == "only_shelf", "only that one was brought in"
    # …and the resource is REFERENCED, not copied: one id, two graphs
    assert study.find_node_by_id(mine["id"]) is not None
    assert shelf.find_node_by_id(mine["id"]) is not None
    assert backend.entry_status(mine["id"], study)["in_use"] is True


def test_asking_the_shelf_alone_would_get_the_mode_wrong():
    """Why `table_subject` exists at all. The hat lives in the STUDY graph, so a
    subject that is only the shelf answers «only_shelf» over a model that is
    standing in the viewport."""
    study, shelf, mine, _t = a_project()
    backend.adopt_project_shelf()
    backend.hat_as_rm(study, mine["id"], epochs=["ep1"])
    assert api.shelf_entry_status(shelf, mine["id"])["mode"] == "only_shelf"
    assert api.shelf_entry_status([shelf, study], mine["id"])["mode"] \
        == "used_in_graph"
    # …and the backend asks the right one
    assert backend.entry_status(mine["id"], study)["mode"] == "used_in_graph"


def test_the_subject_includes_the_whole_open_project():
    """A resource hatted into ANOTHER graph of the same project is in use too —
    the multigraph is the unit, not the graph somebody happens to be editing."""
    study, _shelf, mine, _t = a_project()
    other = Graph(graph_id="altro-settore")
    other.add_node(EpochNode(node_id="ep9", name="Fase 9", start_time=-10,
                             end_time=0))
    multi_graph_manager.graphs["altro-settore"] = other
    backend.adopt_project_shelf()
    backend.hat_as_rm(other, mine["id"], epochs=["ep9"])
    # asked about the graph the user is editing — which is NOT where the hat is
    assert backend.entry_status(mine["id"], study)["mode"] == "used_in_graph"


# ── and the thing that must NOT exist ───────────────────────────────────────

def test_the_shelf_tool_has_no_export_path():
    """The correction, asserted: Blender does not export the shelf. `save_shelf`
    stays — it writes a STANDALONE library file, which is a different act and the
    one this tool had before — but nothing here exports the shelf as part of a
    project, and no new path was added to do it."""
    source = (_REPO / "shelf_tool" / "shelf_backend.py").read_text("utf8")
    code = "\n".join(line for line in source.splitlines()
                     if not line.strip().startswith("#"))
    for forbidden in ("export_shelf", "shelf_export", "export_emjson"):
        assert forbidden not in code, f"{forbidden} appeared in the shelf tool"
    # …and the project-side read does not write anything either
    assert "def adopt_project_shelf" in code
    assert "save" not in code.split("def adopt_project_shelf")[1].split("def ")[0]
