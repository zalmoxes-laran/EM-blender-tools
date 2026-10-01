"""MICRO-EMTOOLS-DEV26, parte 2 — il sigillo: le parole, la verifica, i dettagli.

Il file set è il caso 19 di dtcstamp (un .obj, il suo .mtl, due texture). La
verifica di un file set è membro per membro: una texture cambiata dietro una
porta intatta è ▲, ed è il difetto che EMStudio ha corretto nel NIGHT-CAMPAGNA.
"""

from __future__ import annotations

import base64
import json
import pathlib
import shutil

import dtcstamp
import pytest

import resource_seal as rs

CONF = pathlib.Path(__file__).resolve().parent / "fixtures" / "dtcstamp"

BLOCKS = {
    "from": [{"resource_id": "urn:em:rm:podio_lod0", "label": "OB_PODIO_LOD0"}],
    "how": {"dtc_kind": "decimation",
            "software": [{"name": "Blender", "version": "5.2.0"},
                         {"name": "EMtools", "version": "1.6.0-dev.10"}]},
    "by": {"at": "2026-10-01T15:00:00Z",
           "operator": {"id": "https://orcid.org/0000-0002-1825-0097",
                        "label": "Emanuel Demetrescu"}},
}


def _file_set(tmp_path):
    case = json.loads((CONF / "19-file-set-obj.json").read_text(encoding="utf-8"))
    for rel, spec in case["file_set"]["files"].items():
        target = tmp_path.joinpath(*rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(spec["base64"]) if "base64" in spec
                           else spec["text"].encode("utf-8"))
    door = tmp_path / case["file_set"]["entry_point"]
    stamp = dtcstamp.new_file_set_stamp(str(door), "urn:em:rm:podio_lod1", **BLOCKS)
    dtcstamp.write_stamp(stamp, dtcstamp.file_set_stamp_path(str(door)))
    rs.forget()
    return door, case


def test_il_timbro_si_trova_accanto_alla_porta(tmp_path):
    door, _ = _file_set(tmp_path)
    assert rs.find_stamp(str(door)) == str(tmp_path / "model.obj.stamp.json")
    assert rs.find_stamp(str(tmp_path / "model.mtl")) is None


def test_le_parole_del_sigillo(tmp_path):
    door, _ = _file_set(tmp_path)
    seal = rs.seal_of(str(door))
    w = seal["words"]
    assert w["what"] == ("One resource, 4 files: model.obj and the files it calls "
                         "(model.mtl, stone normal.png, stone_diffuse.png).")
    assert w["origin"] == "Comes from OB_PODIO_LOD0 — decimation"
    assert w["who"] == "Emanuel Demetrescu · 0000-0002-1825-0097"
    assert w["when"] == "2026-10-01T15:00:00Z"
    assert w["with_what"] == "Blender 5.2.0, EMtools 1.6.0-dev.10"


def test_i_dettagli_tecnici_sono_quelli_del_timbro(tmp_path):
    door, case = _file_set(tmp_path)
    seal = rs.seal_of(str(door))
    tech = dict(seal["technical"])
    assert tech["digest"] == case["expect"]["members_digest"]
    assert tech["digest_covers"] == "members" and tech["packaging"] == "file_set"
    assert seal["canonical"] == [f"{m['role']} ␀ {m['path']} ␀ {m['digest']}"
                                 for m in case["expect"]["members"]]
    # «Copy JSON» copia il file com'è
    assert seal["raw"] == (tmp_path / "model.obj.stamp.json").read_text(encoding="utf-8")


def test_i_byte_corrispondono(tmp_path):
    door, _ = _file_set(tmp_path)
    check = rs.seal_of(str(door))["check"]
    assert check["state"] == "ok" and rs.MARK[check["state"]] == "✓"
    assert "all 4 members" in check["line"]


def test_una_texture_cambiata_dietro_la_porta_intatta_e_un_triangolo(tmp_path):
    door, _ = _file_set(tmp_path)
    before = door.read_bytes()
    (tmp_path / "textures" / "stone normal.png").write_bytes(b"other bytes")
    check = rs.seal_of(str(door))["check"]
    assert door.read_bytes() == before          # the door did not move
    assert check["state"] == "differs" and rs.MARK[check["state"]] == "▲"
    assert check["changed"] == ["textures/stone normal.png"]
    assert "1 changed: textures/stone normal.png" in check["line"]


def test_un_membro_sparito(tmp_path):
    door, _ = _file_set(tmp_path)
    (tmp_path / "model.mtl").unlink()
    check = rs.seal_of(str(door))["check"]
    assert check["state"] == "differs" and "model.mtl" in check["missing"]


def test_un_file_solo(tmp_path):
    f = tmp_path / "relazione.pdf"
    f.write_bytes(b"%PDF-1.7 la relazione")
    stamp = {"stamp": dtcstamp.STAMP_VERSION,
             "self": {"resource_id": "urn:em:doc:rel", "label": "Relazione 2026",
                      "digest": dtcstamp.file_digest(str(f)),
                      "digest_covers": "artifact", "packaging": "file"}}
    dtcstamp.write_stamp(stamp, rs.stamp_path_for(str(f)))
    seal = rs.seal_of(str(f))
    assert seal["words"]["what"] == "One file: Relazione 2026."
    assert seal["words"]["origin"] == "Origin: —"
    assert seal["check"]["state"] == "ok"
    f.write_bytes(b"%PDF-1.7 un'altra relazione")
    assert rs.seal_of(str(f))["check"]["state"] == "differs"


@pytest.mark.parametrize("name", ["20-tileset-folder-and-3tz.json"])
def test_un_archivio_3tz(tmp_path, name):
    case = json.loads((CONF / name).read_text(encoding="utf-8"))
    archive = tmp_path / "tiles.3tz"
    shutil.copy2(CONF / case["tree"]["archive"], archive)
    stamp = dtcstamp.new_tree_stamp(str(archive), "urn:em:rm:tiles")
    dtcstamp.write_stamp(stamp, rs.stamp_path_for(str(archive)))
    seal = rs.seal_of(str(archive))
    assert seal["words"]["what"].startswith("One resource: the archive")
    assert seal["check"]["state"] == "ok"
    assert dict(seal["technical"])["content_digest"].startswith(
        case["expect"]["content_digest"])


def test_un_timbro_che_non_si_legge(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("a")
    (tmp_path / "a.txt.stamp.json").write_text("{not json")
    seal = rs.seal_of(str(f))
    assert "error" in seal and seal["stamp_path"].endswith("a.txt.stamp.json")
