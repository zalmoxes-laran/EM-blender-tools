"""Q11 · TLS that trusts what this computer trusts (sync_manager/trust.py).

Measured on 4 Oct 2026: Blender's Python verifies with its own certifi bundle,
so the dev node behind Caddy answered CERTIFICATE_VERIFY_FAILED — «Find» never
proposed it and a sign-in died at the code exchange."""
import importlib.util
import pathlib
import ssl
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("em_trust", _REPO / "sync_manager" / "trust.py")
trust = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trust)


def test_verification_is_never_turned_off():
    ctx = trust.context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname
    source = (_REPO / "sync_manager" / "trust.py").read_text(encoding="utf-8")
    assert "CERT_NONE" not in source and "_create_unverified_context" not in source


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS trust settings")
def test_only_what_the_settings_allow_and_never_a_denied_one(monkeypatch, tmp_path):
    import plistlib
    settings = {"trustList": {
        "AA" * 20: {},                                                  # always
        "BB" * 20: {"trustSettings": [{"kSecTrustSettingsPolicyName": "sslServer"}]},
        "CC" * 20: {"trustSettings": [{"kSecTrustSettingsResult": 3,
                                       "kSecTrustSettingsPolicyName": "sslServer"}]},
        "DD" * 20: {"trustSettings": [{"kSecTrustSettingsPolicyName": "SMIME"}]},
    }}

    def fake_run(cmd, **kw):
        plistlib.dump(settings, open(cmd[-1], "wb"))

        class R:
            stdout = ""
        return R()
    monkeypatch.setattr(trust.subprocess, "run", fake_run)
    assert trust._trusted_hashes(["-d"]) == {"AA" * 20, "BB" * 20}


def test_every_call_to_a_node_goes_through_it():
    """The bare stdlib call survives only as the fallback of a module loaded by
    path, outside the package (the suite)."""
    for name in ("room.py", "rooms_list.py", "asset_upload.py", "servers.py",
                 "scene_package.py", "file_states.py", "handoff.py"):
        source = (_REPO / "sync_manager" / name).read_text(encoding="utf-8")
        assert "from .trust import" in source, name
        assert source.count("urllib.request.urlopen(") <= 1, name
    finder = (_REPO / "sync_manager" / "node_choice.py").read_text(encoding="utf-8")
    assert "probe(u, fetch=trust.fetch_json)" in finder
