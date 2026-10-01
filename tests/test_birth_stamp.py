"""VLONG-DEV27 · D2/D3 — the stamp born with the file (``birth_stamp``).

Outside Blender: the files are made here, the stamps are dtcstamp's. The four
cases of the prompt — a glb is a ``file`` with its master, an obj with mtl and
textures a ``file_set`` whose digest is ``dtcstamp.members_digest``, a packed
tileset an ``archive`` whose ``content_digest`` is the folder's, and a second
export with other bytes a revision — plus what the format asks of ``from``
(no path) and of an unsaved ``.blend``.
"""

from __future__ import annotations

import base64
import json
import os
import pathlib
import shutil

import birth_stamp as bs
import resource_digest as rd

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONF = ROOT / "tests" / "fixtures" / "dtcstamp"

MASTER = {"resource_id": "US01_model_res_blend", "label": "OB_US01",
          "locator": "blend://scavo.blend#Object/OB_US01",
          "blend_digest": "sha256:" + "b" * 64, "blend_saved": True,
          "fingerprint": "struct:f=12:v=8"}
HOW = {"dtc_kind": bs.KIND_EXPORT, "technique": "glTF export (GLB)",
       "parameters": {"operator": "glb.exportbatch", "export_format": "GLB"},
       "software": [{"name": "Blender", "version": "5.2.0"},
                    {"name": "EM Tools", "version": "1.6.0-dev.10", "commit": "0f660c7"}]}


def _materialise(tmp_path, files):
    for rel, spec in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if "text" in spec:
            p.write_text(spec["text"], encoding="utf-8")
        else:
            p.write_bytes(base64.b64decode(spec["base64"]))


def test_un_glb_e_un_file_col_suo_master(tmp_path):
    glb = tmp_path / "OB_US01.glb"
    glb.write_bytes(b"glTF\x02\x00\x00\x00" + b"\x01" * 200)
    res = bs.stamp_export(str(glb), masters=[MASTER], how=HOW, when="2026-10-31T10:00:00Z")
    assert res["state"] == "stamped", res["line"]
    stamp = json.loads(pathlib.Path(res["stamp_path"]).read_text(encoding="utf-8"))
    assert res["stamp_path"].endswith("OB_US01.glb.stamp.json")
    me = stamp["self"]
    assert me["packaging"] == "file" and me["tier"] == "distribution"
    assert me["digest"] == rd.dtcstamp().file_digest(str(glb))
    assert me["digest_covers"] == "artifact" and me["format"] == "glb"
    assert me["resource_id"] == bs.default_resource_id(me["digest"])
    parent = stamp["from"][0]
    assert parent["resource_id"] == "US01_model_res_blend"
    assert parent["tier"] == "master" and parent["packaging"] == "datablock"
    # dtcstamp 0.1.3 `from[].state`: fingerprint · sha256 · saved
    assert parent["state"] == {"sha256": MASTER["blend_digest"], "saved": True,
                               "fingerprint": "struct:f=12:v=8"}
    #: from names by identity, never by path: the locator is a private hint
    assert "blend://" not in json.dumps(stamp["from"])
    # …in the ONE <asset>.hints.json (0.1.3): the asset seen here, the master under from
    assert res["hints_path"].endswith("OB_US01.glb.hints.json")
    hints = json.loads(pathlib.Path(res["hints_path"]).read_text(encoding="utf-8"))
    assert hints["digest"] == me["digest"]
    assert hints["seen"][0]["locator"] == str(glb) and hints["seen"][0]["scope"] == "private"
    master_seen = hints["from"]["US01_model_res_blend"]
    assert master_seen[0]["locator"] == MASTER["locator"]
    assert master_seen[0]["kind"] == "blend" and master_seen[0]["scope"] == "private"
    assert not pathlib.Path(str(glb) + ".from.hints.json").exists()
    # the gesture, or its dev27 equivalent when the bundled vocabulary lacks it
    assert stamp["how"]["dtc_kind"] == bs.resolve_kind(bs.KIND_EXPORT)
    assert stamp["how"]["dtc_kind"] in ("export", "format_conversion")
    assert stamp["by"] == {"at": "2026-10-31T10:00:00Z"}     # nobody named: no operator
    assert rd.dtcstamp().validate_stamp(stamp) is stamp


def test_un_blend_non_salvato_lo_dice(tmp_path):
    glb = tmp_path / "a.glb"
    glb.write_bytes(b"glTF" + b"\x02" * 50)
    res = bs.stamp_export(str(glb), masters=[{**MASTER, "blend_saved": False}], how=HOW)
    state = res["stamp"]["from"][0]["state"]
    assert state["saved"] is False and "unsaved" in state["note"]


def test_l_operatore_c_e_solo_se_emtools_lo_conosce(tmp_path):
    glb = tmp_path / "a.glb"
    glb.write_bytes(b"glTF" + b"\x03" * 50)
    res = bs.stamp_export(str(glb), how=HOW,
                          operator={"id": "https://orcid.org/0000-0002-5065-7970"})
    assert res["stamp"]["by"]["operator"] == {"id": "https://orcid.org/0000-0002-5065-7970"}
    assert res["stamp"]["from"] == []


def test_un_obj_con_mtl_e_texture_e_un_file_set(tmp_path):
    case = json.loads((CONF / "19-file-set-obj.json").read_text(encoding="utf-8"))
    _materialise(tmp_path, case["file_set"]["files"])
    door = tmp_path / case["file_set"]["entry_point"]
    res = bs.stamp_export(str(door), masters=[MASTER], how=HOW)
    me = res["stamp"]["self"]
    assert me["packaging"] == "file_set" and me["digest_covers"] == "members"
    assert me["digest"] == case["expect"]["members_digest"]
    assert me["digest"] == rd.dtcstamp().members_digest(me["members"])
    assert [m["path"] for m in me["members"]] == [m["path"] for m in case["expect"]["members"]]
    assert res["stamp_path"] == str(door) + ".stamp.json"
    assert "_followed" not in json.loads(pathlib.Path(res["stamp_path"]).read_text())


def test_un_tileset_impacchettato_e_un_archive_col_contenuto_della_cartella(tmp_path):
    case = json.loads((CONF / "20-tileset-folder-and-3tz.json").read_text(encoding="utf-8"))
    folder = tmp_path / "small"
    _materialise(folder, case["tree"]["files"])
    archive = tmp_path / "small.3tz"
    shutil.copy2(CONF / "data" / "small-tileset-canonical.3tz", archive)

    tree = bs.stamp_export(str(folder), masters=[MASTER],
                           how={**HOW, "dtc_kind": bs.KIND_TILING})
    packed = bs.stamp_export(str(archive), parents=[{
        "resource_id": tree["stamp"]["self"]["resource_id"],
        "digest": tree["stamp"]["self"]["digest"], "label": "small"}],
        how={**HOW, "technique": "3tz packing"})
    t, a = tree["stamp"]["self"], packed["stamp"]["self"]
    assert t["packaging"] == "directory" and t["digest_covers"] == "members"
    assert a["packaging"] == "archive" and a["digest_covers"] == "artifact"
    assert a["digest"] == case["expect"]["archive_sha256"]
    assert a["content_digest"]["digest"] == t["content_digest"]["digest"] \
        == case["expect"]["content_digest"]
    assert a["content_digest"]["computed_by"] == "producer"
    assert rd.dtcstamp().same_content(tree["stamp"], packed["stamp"])
    assert tree["stamp_path"] == str(tmp_path / "small.stamp.json")


def test_un_secondo_export_diverso_e_una_revisione(tmp_path):
    glb = tmp_path / "OB_US01.glb"
    glb.write_bytes(b"glTF" + b"\x01" * 100)
    first = bs.stamp_export(str(glb), masters=[MASTER], how=HOW)
    glb.write_bytes(b"glTF" + b"\x01" * 100 + b"\x09")
    second = bs.stamp_export(str(glb), masters=[MASTER], how=HOW)
    assert second["state"] == "revised"
    old = first["stamp"]["self"]
    assert second["stamp"]["self"]["was_revision_of"] == {"resource_id": old["resource_id"],
                                                          "digest": old["digest"]}
    assert second["stamp"]["self"]["resource_id"] != old["resource_id"]
    #: the previous stamp stays: a true statement about bytes no longer there
    kept = json.loads(pathlib.Path(second["previous_path"]).read_text(encoding="utf-8"))
    assert kept["self"]["digest"] == old["digest"]
    assert os.path.basename(second["previous_path"]) == \
        f"OB_US01.glb.prev-{old['digest'][7:19]}.stamp.json"
    #: the same object, the same master, across the two exports
    assert second["stamp"]["from"][0]["resource_id"] == first["stamp"]["from"][0]["resource_id"]


def test_gli_stessi_byte_non_riscrivono_il_timbro(tmp_path):
    glb = tmp_path / "a.glb"
    glb.write_bytes(b"glTF" + b"\x04" * 60)
    first = bs.stamp_export(str(glb), how=HOW, when="2026-10-31T10:00:00Z")
    raw = pathlib.Path(first["stamp_path"]).read_bytes()
    again = bs.stamp_export(str(glb), how=HOW, when="2026-10-31T11:00:00Z")
    assert again["state"] == "unchanged"
    assert pathlib.Path(first["stamp_path"]).read_bytes() == raw


def test_un_id_dato_che_cambia_byte_prende_un_id_di_revisione(tmp_path):
    glb = tmp_path / "a.glb"
    glb.write_bytes(b"glTF" + b"\x05" * 60)
    bs.stamp_export(str(glb), how=HOW, resource_id="US01_model_link")
    glb.write_bytes(b"glTF" + b"\x06" * 60)
    second = bs.stamp_export(str(glb), how=HOW, resource_id="US01_model_link")
    me = second["stamp"]["self"]
    assert me["was_revision_of"]["resource_id"] == "US01_model_link"
    assert me["resource_id"].startswith("US01_model_link.r")


def test_niente_da_timbrare_lo_dice_e_non_solleva(tmp_path):
    res = bs.stamp_export(str(tmp_path / "missing.glb"), how=HOW)
    assert res["state"] == "failed" and "nothing at" in res["line"]
    assert bs.report_line([res]).startswith("Stamps: 1 not stamped")


def test_uno_zip_qualunque_e_un_archive_dei_suoi_byte(tmp_path):
    import zipfile
    z = tmp_path / "out.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("out/tileset.json", "{}")
    res = bs.stamp_export(str(z), how=HOW)
    me = res["stamp"]["self"]
    assert me["packaging"] == "archive" and me["digest_covers"] == "artifact"
    assert "content_digest" not in me


def test_il_rapporto_conta(tmp_path):
    rows = [{"state": "stamped", "line": ""}, {"state": "revised", "line": ""},
            {"state": "failed", "line": "not stamped: boom"}]
    assert bs.report_line(rows) == "Stamps: 1 stamped, 1 revised, 1 not stamped (not stamped: boom)"


# ── VLONG-DEV28 · E2/E3 — the local identity, the 0.1.3 format, the gestures ──

import importlib.util  # noqa: E402

import local_identity as li  # noqa: E402

GOOD = "0000-0002-1825-0097"         # ORCID's own example iD
SWAPPED = "0000-0002-1825-0079"      # two digits swapped: the check digit fails


def test_l_identita_locale_controlla_la_cifra():
    assert li.orcid_problem(GOOD) is None
    assert li.orcid_problem(f"https://orcid.org/{GOOD}") is None
    assert li.orcid_problem("0000 0002 1825 0097") is None
    assert li.orcid_problem(SWAPPED) == li.CHECKSUM
    assert li.orcid_problem("1234") == li.SHAPE
    assert li.orcid_problem("") == li.EMPTY
    # the same algorithm as EMStudio's identity.ts, on iDs with an X
    assert li.is_valid_orcid("0000-0002-9079-593X")


def test_un_timbro_con_l_identita_locale(tmp_path):
    glb = tmp_path / "a.glb"
    glb.write_bytes(b"glTF" + b"\x04" * 50)
    op = li.declared_operator(GOOD, "Emanuel Demetrescu")
    assert op == {"id": f"https://orcid.org/{GOOD}", "label": "Emanuel Demetrescu",
                  "auth": {"mode": "declared"}}
    res = bs.stamp_export(str(glb), how=HOW, operator=op)
    assert res["stamp"]["by"]["operator"] == op
    assert rd.dtcstamp().validate_stamp(res["stamp"])


def test_un_timbro_senza_identita_resta_senza_operatore(tmp_path):
    glb = tmp_path / "a.glb"
    glb.write_bytes(b"glTF" + b"\x05" * 50)
    res = bs.stamp_export(str(glb), how=HOW, operator=bs.local_operator())
    assert "operator" not in res["stamp"]["by"]     # no Blender prefs here: nobody


def test_un_iD_con_la_cifra_sbagliata_non_firma():
    assert li.declared_operator(SWAPPED, "Qualcuno") is None
    assert li.declared_operator("", "Qualcuno") is None


def test_due_master_due_chiavi(tmp_path):
    """The defect of the first form: two masters under the first one's id."""
    tileset = tmp_path / "tiles"
    tileset.mkdir()
    (tileset / "tileset.json").write_text('{"asset": {"version": "1.0"}}')
    other = {**MASTER, "resource_id": "US02_model_res_blend",
             "locator": "blend://scavo.blend#Object/OB_US02"}
    res = bs.stamp_export(str(tileset), masters=[MASTER, other],
                          how={**HOW, "dtc_kind": bs.KIND_TILING})
    hints = json.loads(pathlib.Path(res["hints_path"]).read_text(encoding="utf-8"))
    assert {k: [e["locator"] for e in v] for k, v in hints["from"].items()} == {
        "US01_model_res_blend": [MASTER["locator"]],
        "US02_model_res_blend": [other["locator"]]}


def test_il_file_vecchio_delle_piste_si_ripiega(tmp_path):
    glb = tmp_path / "a.glb"
    glb.write_bytes(b"glTF" + b"\x06" * 50)
    legacy = tmp_path / "a.glb.from.hints.json"
    legacy.write_text(json.dumps({"hints": 1, "digest": "blend:old",
                                  "seen": [{"locator": "blend://old.blend#Object/X",
                                            "kind": "blend", "scope": "private",
                                            "when": "2026-10-01T10:00:00Z"}]}))
    res = bs.stamp_export(str(glb), masters=[MASTER], how=HOW)
    hints = json.loads(pathlib.Path(res["hints_path"]).read_text(encoding="utf-8"))
    assert hints["from"]["blend:old"][0]["locator"] == "blend://old.blend#Object/X"
    assert legacy.exists()                          # folded in, never deleted


def test_una_revisione_dice_cosa_rivede(tmp_path):
    glb = tmp_path / "a.glb"
    glb.write_bytes(b"glTF" + b"\x07" * 50)
    first = bs.stamp_export(str(glb), masters=[MASTER], how=HOW)
    glb.write_bytes(b"glTF" + b"\x08" * 50)
    second = bs.stamp_export(str(glb), masters=[MASTER], how=HOW)
    assert second["state"] == "revised"
    assert second["stamp"]["self"]["was_revision_of"] == {
        "resource_id": first["stamp"]["self"]["resource_id"],
        "digest": first["stamp"]["self"]["digest"]}


def test_i_gesti_e_il_vocabolario():
    old = ["photogrammetry", "transformation", "decimation", "format_conversion"]
    new = old + ["export", "lod_generation", "tiling", "packing"]
    assert [bs.resolve_kind(k, old) for k in (bs.KIND_EXPORT, bs.KIND_LOD, bs.KIND_TILING, bs.KIND_PACKING)] \
        == ["format_conversion", "decimation", "transformation", "format_conversion"]
    assert [bs.resolve_kind(k, new) for k in (bs.KIND_EXPORT, bs.KIND_LOD, bs.KIND_TILING, bs.KIND_PACKING)] \
        == ["export", "lod_generation", "tiling", "packing"]
    assert bs.resolve_kind("georeferencing", old) == "georeferencing"


def _dtcstamp_013():
    src = ROOT.parent / "dtcstamp" / "dtcstamp.py"
    if not src.is_file():
        return None
    spec = importlib.util.spec_from_file_location("dtcstamp_013", src)
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules["dtcstamp_013"] = mod           # a dataclass asks for its module
    spec.loader.exec_module(mod)
    return mod if hasattr(mod, "note_parent_seen") else None


def test_con_dtcstamp_013_le_stesse_piste_e_lo_stato_si_leggono(tmp_path, monkeypatch):
    """Written by hand with 0.1.2, through note_parent_seen with 0.1.3: one shape,
    and 0.1.3 reads back the state and the revision it fixes."""
    import pytest
    d13 = _dtcstamp_013()
    if d13 is None:
        pytest.skip("no dtcstamp 0.1.3 checkout beside this one")
    glb = tmp_path / "a.glb"
    glb.write_bytes(b"glTF" + b"\x09" * 50)
    by_hand = bs.stamp_export(str(glb), masters=[MASTER], how=HOW, when="2026-11-01T10:00:00Z")
    hand = json.loads(pathlib.Path(by_hand["hints_path"]).read_text(encoding="utf-8"))
    monkeypatch.setattr(rd, "dtcstamp", lambda: d13)
    glb2 = tmp_path / "b.glb"
    glb2.write_bytes(glb.read_bytes())
    lib = bs.stamp_export(str(glb2), masters=[MASTER], how=HOW, when="2026-11-01T10:00:00Z")
    via = json.loads(pathlib.Path(lib["hints_path"]).read_text(encoding="utf-8"))
    assert via["from"] == hand["from"]
    assert d13.parent_state(lib["stamp"]["from"][0]) == {
        "fingerprint": "struct:f=12:v=8", "sha256": MASTER["blend_digest"], "saved": True}
    assert d13.parent_hints(via, "US01_model_res_blend")["seen"][0]["locator"] == MASTER["locator"]

