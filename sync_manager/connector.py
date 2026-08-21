"""EMtools as a CONNECTOR — reference #1, declared.

Nothing new is built here. EMtools already does the four things a connector does:
it **adopts a room**, it **materialises** proxies from the graph (DP-76), it
**publishes** a GLB into the object store, and it **syncs** selection and
operations. What was missing is the DECLARATION — a descriptor that says, before
anything happens, what this host is, how it can be reached, what it speaks and
what it can do.

That declaration is the whole interoperability surface (the contract lives in
``s3dgraphy.contract``): a Heriverse viewer, a Tropy import or a PyArchInit sync
becomes a connector by writing one of these and wiring a handler — and this file
is the template they copy, which is why it says WHY for each field rather than
just filling it in.

It rides on ``host_info``, the frame where this host already says what it is:
``tool`` and ``accepts_commands`` were the first two answers to the same
question, asked one capability at a time.

**Purity.** No Blender import at module level and no network: the descriptor is
data, and a test (or EMStudio, reading the wire) must be able to look at it
without a running Blender.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

#: The name EMStudio's registry keys this connector by. Stable — a rename would
#: read as a different connector arriving.
CONNECTOR_NAME = "blender"

#: The connector API version this descriptor's SHAPE conforms to. Must match
#: ``s3dgraphy.contract.connector.CONNECTOR_API_VERSION``; the handshake on the
#: other side compares it, and a mismatch is refused with the reason.
CONNECTOR_API_VERSION = "1.0.0"

#: What EMtools can do, from the contract's closed set. Each one is something the
#: addon ALREADY does — a capability declared and not implemented would draw an
#: affordance in EMStudio that does nothing, which is worse than not offering it:
#:
#:  * ``read-graph``     · it opens em.json / GraphML and holds the graph
#:  * ``write-graph``    · proxies, geo, and the operations it emits back
#:  * ``subscribe``      · it hosts the socket and rebroadcasts what changes
#:  * ``link-selection`` · selection mirroring (ephemeral, never in the document)
#:  * ``attach-asset``   · a resource promoted into the room's store
#:  * ``materialize-3D`` · DP-76: the graph's proxies become objects in the scene
#:  * ``publish-3D``     · a GLB published as content-addressed bytes
#:
#: NOT declared, on purpose: ``presence`` (there is one Blender at the other end
#: of a pairing — a roster of one is not presence), ``ingest-batch`` (EMtools
#: imports a document, it does not propose a lot), ``resolve-uri`` (no authority
#: resolution lives here).
CAPABILITIES: List[str] = [
    "read-graph",
    "write-graph",
    "subscribe",
    "link-selection",
    "attach-asset",
    "materialize-3D",
    "publish-3D",
]

#: How EMtools can be reached. All three, and each is a real path today: a socket
#: on this machine (EMStudio in a browser next to Blender), the same on the LAN (a
#: field laptop), and a room on em-server (P4.4's client).
TRANSPORT: List[str] = ["direct", "lan", "cloud"]

#: How what it writes is attributed: a DERIVATION. A materialised proxy comes out
#: of the graph plus this tool, and that is a `crmdig:D7` with inputs — never an
#: acquisition (nothing entered the study) and never unattributed.
PROVENANCE = "derivation"


def addon_version() -> Optional[str]:
    """The addon's own version, for the descriptor's ``vendor`` block.

    Read from the manifest at run time rather than restated here: a version
    written twice is a version that disagrees with itself on the day it matters.
    Returns None when the manifest cannot be read — an unknown version is stated
    as unknown, and a connector is not refused for it.
    """
    import pathlib
    manifest = pathlib.Path(__file__).resolve().parent.parent / "blender_manifest.toml"
    try:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("version"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def datamodel_version() -> Optional[str]:
    """The connections datamodel this build speaks — asked of s3Dgraphy, which
    owns it (ADR-001). The handshake is strict on this one: it IS the EM
    language, and a peer a minor behind writes edges the other side resolves
    differently."""
    try:
        from s3dgraphy.contract.connector import current_versions
        return current_versions().datamodel
    except Exception:  # noqa: BLE001 — an older s3Dgraphy, or none
        pass
    # Older s3Dgraphy without the contract module: read the JSON it ships.
    try:
        import json
        import s3dgraphy
        import pathlib
        path = (pathlib.Path(s3dgraphy.__file__).parent / "JSON_config"
                / "s3Dgraphy_connections_datamodel.json")
        return json.loads(path.read_text(encoding="utf-8")).get(
            "s3Dgraphy_connections_model_version")
    except Exception:  # noqa: BLE001
        return None


def emjson_version() -> Optional[str]:
    """The em.json schema this build reads and writes — s3Dgraphy's exporter
    constant, not a number typed here."""
    try:
        from s3dgraphy.exporter.emjson_exporter import SCHEMA_VERSION
        return str(SCHEMA_VERSION)
    except Exception:  # noqa: BLE001
        return None


def descriptor(*, accepts_commands: bool = False,
               extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The wire form of EMtools' ConnectorDescriptor.

    A dict, and deliberately so: this has to be sendable from inside Blender,
    where s3Dgraphy may be a vendored copy and where importing a dataclass to
    serialise it immediately would buy nothing. The SHAPE is
    ``s3dgraphy.contract.ConnectorDescriptor.as_dict()`` — one serialisation,
    which is what lets EMStudio's registry read a shape instead of guessing one.

    ``accepts_commands`` is passed in rather than read here: the consent lives in
    the scene (CMD1) and this module stays free of Blender.
    """
    vendor: Dict[str, Any] = {"addon_version": addon_version(),
                              "accepts_commands": bool(accepts_commands)}
    if extra:
        vendor.update(extra)
    return {
        "name": CONNECTOR_NAME,
        "description": "Blender · EMtools",
        "host": "app-side",          # it runs inside another application
        "service": "app",
        "transport": list(TRANSPORT),
        "capabilities": list(CAPABILITIES),
        "versions": {
            "emjson": emjson_version(),
            "datamodel": datamodel_version(),
            "connector_api": CONNECTOR_API_VERSION,
        },
        "provenance": PROVENANCE,
        "writes": True,              # so the contract's no-author refusal applies
        "vendor": vendor,
    }


def as_contract_descriptor(*, accepts_commands: bool = False):
    """The same declaration as a real :class:`ConnectorDescriptor`.

    Used where s3Dgraphy is importable and the OBJECT is wanted — a test, a
    registry inside a Python host — so the fields are validated by the contract
    itself (an unknown capability, an unknown host and an empty transport list
    each raise here rather than becoming a dead affordance far away).
    """
    from s3dgraphy.contract import ConnectorDescriptor, Versions
    wire = descriptor(accepts_commands=accepts_commands)
    return ConnectorDescriptor(
        name=wire["name"], description=wire["description"],
        service=wire["service"], host=wire["host"],
        transport=wire["transport"], capabilities=wire["capabilities"],
        versions=Versions(**wire["versions"]),
        provenance=wire["provenance"], vendor=wire["vendor"],
        intents=[CONNECTOR_NAME, "emtools", "blender"])
