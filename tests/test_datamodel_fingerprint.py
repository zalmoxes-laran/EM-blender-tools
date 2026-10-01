"""Parte 0 — the datamodel the wheel carries, against the one the pin promises.

EMtools reads the datamodel from the s3dgraphy wheel, so the expectation
(`em_setup/datamodel.fingerprint.json`) must be the bundled wheel's own, the pin
must ask for at least that version, and a different datamodel must be SAID.
"""

import importlib.util
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location(
    "_emtools_test_version_banner_fp", ROOT / "em_setup" / "version_banner.py")
banner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(banner)


def test_l_atteso_e_quello_della_ruota_importata():
    result = banner.check_datamodel()
    assert result["state"] == "aligned", result
    assert banner.format_datamodel_check(result) == ""


def test_il_pin_chiede_almeno_la_versione_dell_impronta():
    expected = banner.expected_fingerprint()
    pin = re.search(r"^s3dgraphy>=([^,\s]+)",
                    (ROOT / "scripts" / "requirements_wheels.txt").read_text(),
                    re.MULTILINE).group(1)
    assert expected["s3dgraphy"] == pin


def test_la_ruota_nel_bundle_e_quella_del_pin():
    expected = banner.expected_fingerprint()
    for tag in ("cp311", "cp313"):
        wheels = sorted((ROOT / "wheels" / tag).glob("s3dgraphy-*.whl"))
        if not wheels:  # a checkout without the bundle (CI): nothing to compare
            continue
        assert len(wheels) == 1, wheels
        assert wheels[0].name.startswith(f"s3dgraphy-{expected['s3dgraphy']}-")


def test_una_deriva_si_dice_per_nome():
    expected = banner.expected_fingerprint()
    found = {**expected, "digest": "sha256:other",
             "versions": {**expected["versions"], "nodes": "1.6.99"}}
    result = banner.check_datamodel(expected=expected, found=found)
    assert result["state"] == "differs"
    assert any("nodes" in line for line in result["differences"])
    assert "Datamodel differs" in banner.format_datamodel_check(result)


def test_senza_attesa_non_si_inventa_nulla():
    result = banner.check_datamodel(expected={})
    assert result["state"] == "unchecked"
    assert banner.format_datamodel_check(result).startswith("Datamodel not checked")
