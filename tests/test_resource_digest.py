"""MICRO risorsa-file, parte 3 — il tileset: stesso contenuto, due forme, e il .3tz.

I digest sono di dtcstamp (installato o vendorizzato in `_vendor/`): qui si
riproducono i suoi casi di conformità 20 e 23, e si misura la base di prova
TempluMare, cartella e `.3tz`.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import shutil

import pytest

from s3dgraphy import api
from s3dgraphy.graph import Graph
from s3dgraphy.nodes.representation_node import RepresentationModelNode

import publication_targets as pt
import resource_digest as rd
import resource_levels as rl

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONF = ROOT / "tests" / "fixtures" / "dtcstamp"
BASE = pathlib.Path.home() / ("Library/CloudStorage/OneDrive-CNR/Extended Matrix/"
                              "EM_CaseStudies/01_EM_Tempio Grande/_base_EMStudio/RM")


def test_il_vendorizzato_e_il_file_del_commit():
    readme = (ROOT / "_vendor" / "README.md").read_text(encoding="utf-8")
    digest = hashlib.sha256((ROOT / "_vendor" / "dtcstamp.py").read_bytes()).hexdigest()
    assert digest in readme
    sibling = ROOT.parent / "dtcstamp" / "dtcstamp.py"
    if sibling.is_file() and hashlib.sha256(sibling.read_bytes()).hexdigest() != digest:
        pytest.skip("the dtcstamp checkout moved past the vendored commit — "
                    "copy it again and rewrite _vendor/README.md")


def _materialise(case, folder):
    for rel, spec in case["tree"]["files"].items():
        target = folder.joinpath(*rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        if "base64" in spec:
            target.write_bytes(base64.b64decode(spec["base64"]))
        else:
            target.write_bytes(spec["text"].encode("utf-8"))


@pytest.mark.parametrize("name", ["20-tileset-folder-and-3tz.json",
                                  "23-tileset-non-ascii-name.json"])
def test_i_casi_di_conformita_di_dtcstamp(tmp_path, name):
    case = json.loads((CONF / name).read_text(encoding="utf-8"))
    folder = tmp_path / "tree"
    _materialise(case, folder)
    archive = CONF / case["tree"]["archive"]
    expect = case["expect"]
    assert rd.content_digest(str(folder)) == expect["content_digest"]
    assert rd.content_digest(str(archive)) == expect["content_digest"]
    assert "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest() == expect["archive_sha256"]


@pytest.mark.skipif(not BASE.is_dir(), reason="the TempluMare base is not on this machine")
def test_templumare_cartella_e_3tz_hanno_lo_stesso_contenuto():
    folder = rd.content_digest(str(BASE / "TempluMare_cesium"))
    archive = rd.content_digest(str(BASE / "TempluMare_cesium.3tz"))
    assert folder == archive
    assert folder.startswith("sha256:8aa6fbd3") and folder.endswith("caed")


# ── l'archivio si serve così com'è ───────────────────────────────────────────

def test_un_3tz_resta_un_3tz(tmp_path):
    src = CONF / "data" / "small-tileset-canonical.3tz"
    out = tmp_path / "tilesets"
    out.mkdir()
    path, url, copied = rl.archivio_servito(str(src), str(out), "small")
    assert url == "tilesets/small.3tz" and path.endswith("small.3tz") and copied
    assert rl.sha256_del_file(path) == rl.sha256_del_file(str(src))
    # la seconda volta non si ricopia; una sorgente cambiata sì
    assert rl.archivio_servito(str(src), str(out), "small")[2] is False
    other = tmp_path / "other.3tz"
    shutil.copy2(CONF / "data" / "small-tileset-non-ascii-canonical.3tz", other)
    assert rl.archivio_servito(str(other), str(out), "small")[2] is True


def test_un_3tz_chiede_tiles3d_e_non_di_scompattare():
    assert pt.capacita_richieste({"url": "tilesets/T.3tz", "packaging": "archive"}) == ["tiles3d"]
    assert pt.capacita_richieste({"url": "tilesets/T.zip", "packaging": "archive"}) == ["unpackArchive"]


def _tileset_graph():
    g = Graph("g")
    g.add_node(RepresentationModelNode(node_id="T_model", name="Model for T", type="RM",
                                       description=""))
    return g


def test_cartella_e_3tz_portano_lo_stesso_content_digest(tmp_path):
    """Le due distribuzioni di un tileset come le scrive l'export Heriverse
    (`_due_distribuzioni_del_tileset`): `_link` directory col contenuto come
    digest, `_archive` col suo sha256 e lo stesso `content_digest`."""
    case = json.loads((CONF / "20-tileset-folder-and-3tz.json").read_text(encoding="utf-8"))
    tilesets = tmp_path / "tilesets"
    _materialise(case, tilesets / "small")
    src = CONF / case["tree"]["archive"]
    g = _tileset_graph()
    contenuto = rd.content_digest(str(tilesets / "small"))
    rl.registra_derivata(g, derivata_id="T_model_link", url="tilesets/small/tileset.json",
                         link_to="T_model", file_esportato=str(tilesets / "small/tileset.json"),
                         packaging="directory", contenuto=contenuto,
                         peso_contenuto=rd.tree_size(str(tilesets / "small")))
    path, url, _ = rl.archivio_servito(str(src), str(tilesets), "small")
    rl.registra_derivata(g, derivata_id="T_model_archive", url=url, link_to="T_model",
                         file_esportato=path, packaging="archive",
                         contenuto=rd.content_digest(path))
    link, arch = g.find_node_by_id("T_model_link"), g.find_node_by_id("T_model_archive")
    assert link.data["checksum"] == link.data["content_digest"] == case["expect"]["content_digest"]
    assert "checksum_of" not in link.data
    assert link.data["size_bytes"] == sum(m["size_bytes"] for m in case["expect"]["members"])
    assert arch.data["content_digest"] == case["expect"]["content_digest"]
    assert arch.data["checksum"] == case["expect"]["archive_sha256"]
    assert arch.data["url"] == "tilesets/small.3tz"
    assert pt.capacita_richieste(arch.data) == ["tiles3d"]


def test_un_tileset_di_ieri_col_digest_della_porta_non_e_una_revisione(tmp_path):
    case = json.loads((CONF / "20-tileset-folder-and-3tz.json").read_text(encoding="utf-8"))
    folder = tmp_path / "tilesets" / "small"
    _materialise(case, folder)
    g = _tileset_graph()
    door = str(folder / "tileset.json")
    rl.registra_derivata(g, derivata_id="T_model_link", url="tilesets/small/tileset.json",
                         link_to="T_model", file_esportato=door, packaging="directory",
                         checksum_of="entry-point")                      # come ieri
    rl.registra_derivata(g, derivata_id="T_model_link", url="tilesets/small/tileset.json",
                         link_to="T_model", file_esportato=door, packaging="directory",
                         contenuto=rd.content_digest(str(folder)))
    assert api.current_revision(g, "T_model_link") == "T_model_link"
    n = g.find_node_by_id("T_model_link")
    assert n.data["checksum"] == case["expect"]["content_digest"]
    assert "checksum_of" not in n.data


def test_una_tile_cambiata_e_una_revisione_anche_se_la_porta_e_uguale(tmp_path):
    case = json.loads((CONF / "20-tileset-folder-and-3tz.json").read_text(encoding="utf-8"))
    folder = tmp_path / "tilesets" / "small"
    _materialise(case, folder)
    g = _tileset_graph()
    door = str(folder / "tileset.json")

    def bake():
        return rl.registra_derivata(
            g, derivata_id="T_model_link", url="tilesets/small/tileset.json",
            link_to="T_model", file_esportato=door, packaging="directory",
            contenuto=rd.content_digest(str(folder)))
    bake()
    (folder / "Data/c02/e0002.b3dm").write_bytes(b"b3dm changed")
    ok, avvisi = bake()
    new_id = api.current_revision(g, "T_model_link")
    assert ok and new_id != "T_model_link" and "revisione" in avvisi
    assert g.find_node_by_id(new_id).data["checksum"] == rd.content_digest(str(folder))


# ── la rotazione legge il tileset.json dentro l'archivio ─────────────────────

def test_il_tileset_json_si_legge_dentro_il_3tz_senza_estrarre(tmp_path):
    archive = tmp_path / "tilesets" / "small.3tz"
    archive.parent.mkdir()
    shutil.copy2(CONF / "data" / "small-tileset-canonical.3tz", archive)
    before = sorted(os.listdir(archive.parent))
    ts = rd.tileset_json(str(archive))
    assert ts["asset"]["version"] == "1.0" and ts["root"]["refine"] == "REPLACE"
    assert sorted(os.listdir(archive.parent)) == before          # niente estratto
    assert rd.tileset_json(str(tmp_path / "nothing.3tz")) is None
