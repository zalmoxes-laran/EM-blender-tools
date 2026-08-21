"""EMtools declares itself as a connector — reference #1.

What this defends is the DECLARATION, not the plumbing (the plumbing is the same
adopt-room / materialise / publish / sync that already has its own tests):

* the descriptor is valid against the contract in s3Dgraphy — an unknown
  capability, an unknown host or an empty transport list raises HERE rather than
  becoming an affordance in EMStudio that does nothing;
* it declares only what EMtools actually does, and the things it does NOT do are
  absent on purpose (`ingest-batch`, `presence`, `resolve-uri`);
* the versions are ASKED of s3Dgraphy, never typed here, so a handshake against
  the same build accepts and a stale peer is refused with a reason;
* and a write from this connector enters as an attributed DTC act, while the same
  write with no author is refused.

Run outside Blender: the module under test imports no `bpy`, which is itself part
of the contract (a descriptor is data).
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
S3D = ROOT.parent / "s3Dgraphy" / "src"
if S3D.exists():
    sys.path.insert(0, str(S3D))

contract = pytest.importorskip(
    "s3dgraphy.contract",
    reason="the connector contract lives in s3Dgraphy (a sibling checkout)")


def load_connector():
    """Import `sync_manager/connector.py` ALONE — the package's `__init__`
    imports the operators, which import `bpy`. That the descriptor can be read
    without Blender is the point, so the test reads it that way."""
    spec = importlib.util.spec_from_file_location(
        "emtools_connector", ROOT / "sync_manager" / "connector.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)          # type: ignore[union-attr]
    return module


def test_the_descriptor_is_valid_against_the_contract():
    connector = load_connector()
    d = connector.as_contract_descriptor(accepts_commands=True)
    assert d.name == "blender" and d.host == "app-side"
    assert set(d.transport) == {"direct", "lan", "cloud"}
    # what EMtools does, grouped the way the registry groups it
    assert d.layers["document"] == ["read-graph", "write-graph", "subscribe"]
    assert d.layers["interaction"] == ["link-selection"]
    assert d.layers["asset"] == ["attach-asset", "materialize-3D", "publish-3D"]
    # …and what it does NOT do is absent, not declared-and-unimplemented
    for absent in ("ingest-batch", "presence", "resolve-uri"):
        assert not d.can(absent), f"{absent} is not something EMtools does"
    # a write from here is a derivation: a materialised proxy came OUT of the
    # graph plus this tool — never an acquisition, nothing entered the study
    assert d.provenance == "derivation"


def test_the_wire_form_is_what_emstudio_reads():
    connector = load_connector()
    wire = connector.descriptor(accepts_commands=False)
    # the shape EMStudio's ConnectorRegistry consumes
    for key in ("name", "host", "transport", "capabilities", "versions"):
        assert key in wire, key
    assert wire["versions"]["connector_api"] == connector.CONNECTOR_API_VERSION
    assert wire["vendor"]["accepts_commands"] is False
    assert wire["vendor"]["addon_version"], "the addon says which build it is"
    # …and it is JSON, because it travels on a socket
    import json
    assert json.loads(json.dumps(wire)) == wire


def test_the_versions_are_asked_of_s3dgraphy_not_typed_here():
    connector = load_connector()
    current = contract.current_versions()
    wire = connector.descriptor()
    assert wire["versions"]["datamodel"] == current.datamodel
    assert wire["versions"]["emjson"] == current.emjson


def test_the_handshake_accepts_this_build_and_refuses_a_stale_one():
    connector = load_connector()
    accepted = contract.handshake(connector.as_contract_descriptor())
    assert accepted.ok, accepted.message

    stale = connector.as_contract_descriptor()
    stale.versions = contract.Versions(
        emjson=stale.versions.emjson, datamodel="1.6.2",
        connector_api=stale.versions.connector_api)
    refused = contract.handshake(stale)
    assert refused.ok is False
    assert refused.data["field"] == "datamodel"
    assert "1.6.2" in refused.message and "update" in refused.message.lower()


def test_a_write_from_blender_is_an_attributed_act_and_refused_without_one():
    """The two halves of the same rule, at the seam a connector's write passes."""
    connector = load_connector()
    d = connector.as_contract_descriptor()
    section = {"nodes": [], "edges": []}

    # what a materialisation writes back: a proxy for a unit, derived
    delta = contract.Delta(
        author="0000-0002-1825-0097",
        nodes=[{"id": "us-1", "node_type": "US", "name": "US 1"},
               {"id": "proxy-us-1", "node_type": "semantic_shape",
                "name": "US 1 · proxy"}],
        # the direction the datamodel declares: the UNIT has a shape, not the
        # other way round (measured — the seam refused the reverse, which is
        # exactly what it is for)
        edges=[{"id": "e1", "source": "us-1", "target": "proxy-us-1",
                "edge_type": "has_semantic_shape"}])
    out = contract.apply_delta(section, d, "write-graph", delta)
    assert out.ok, out.message
    stamped = [n for n in section["nodes"]
               if (n.get("data") or {}).get("created_by") == "0000-0002-1825-0097"]
    assert len(stamped) == 2, "every node it wrote carries who wrote it"

    # …and the same write with nobody behind it does not happen
    fresh = {"nodes": [], "edges": []}
    anonymous = contract.Delta(nodes=[{"id": "us-2", "node_type": "US"}])
    refused = contract.apply_delta(fresh, d, "write-graph", anonymous)
    assert refused.ok is False and refused.data["reason"] == "no-author"
    assert fresh == {"nodes": [], "edges": []}, "and nothing was applied"


def test_a_capability_blender_did_not_declare_is_refused():
    connector = load_connector()
    d = connector.as_contract_descriptor()
    out = contract.guard_write(
        d, "ingest-batch",
        contract.Delta(author="0000-0002-1825-0097",
                       nodes=[{"id": "x", "node_type": "resource"}]))
    assert out.data["reason"] == "capability-not-declared"
