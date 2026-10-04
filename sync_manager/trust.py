"""TLS that trusts what this computer trusts — the node behind Caddy included.

MEASURED on 4 October 2026, Blender 5.2 on macOS: Blender's Python verifies TLS
with its own `certifi` bundle (`ssl.get_default_verify_paths().cafile` points
inside the app) and never asks the system. The dev node's Caddy signs
`https://em.localhost:8443` with its local root, which `fcn-trust-ca.sh` puts in
the System keychain: Safari and EMStudio trust it, Blender answered
`CERTIFICATE_VERIFY_FAILED`. Two consequences, both seen: «Find» never proposed
the address EMStudio uses, and a sign-in against a node at
`http://localhost:8000` still died at the code exchange, because the realm's
token endpoint is the https one.

So every call of this addon to a node goes through ONE context: Python's
default (certifi, and `SSL_CERT_FILE` / `SSL_CERT_DIR` when set) **plus** the
roots the person told macOS to trust — the admin and user trust settings, read
with `security`, each certificate kept only when its setting does not deny it
and does not restrict it to something other than a TLS server. Nothing is
trusted that the computer does not already trust, and verification is never
turned off. On Linux and Windows the default context is already the system's
(or the env vars say otherwise), and nothing is added.

Stdlib only, and computed once per Blender session.
"""

from __future__ import annotations

import os
import plistlib
import re
import ssl
import subprocess
import sys
import tempfile
import urllib.request
from typing import List, Optional, Set

_CONTEXT: Optional[ssl.SSLContext] = None
#: how many roots came from the system — said by `describe()`, asserted by tests
ADDED: List[str] = []

_SSL_POLICIES = {None, "sslServer", "SSL"}
_DENY = 3


def _trusted_hashes(domain_flag: List[str]) -> Set[str]:
    """SHA-1s the trust settings of one domain allow for TLS (macOS)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "trust.plist")
        try:
            subprocess.run(["security", "trust-settings-export", *domain_flag, out],
                           capture_output=True, timeout=10, check=True)
            with open(out, "rb") as fh:
                data = plistlib.load(fh)
        except Exception:  # noqa: BLE001 — no settings in that domain, no `security`
            return set()
    keep = set()
    for sha1, entry in (data.get("trustList") or {}).items():
        settings = entry.get("trustSettings")
        if not settings:                 # absent or empty: trusted for everything
            keep.add(sha1.upper())
            continue
        for s in settings:
            if s.get("kSecTrustSettingsResult", 1) == _DENY:
                continue
            if s.get("kSecTrustSettingsPolicyName") in _SSL_POLICIES:
                keep.add(sha1.upper())
                break
    return keep


def _pems_of(keychain: str) -> List[tuple]:
    """(SHA-1, PEM) of every certificate in a keychain."""
    try:
        text = subprocess.run(["security", "find-certificate", "-a", "-Z", "-p", keychain],
                              capture_output=True, text=True, timeout=10).stdout
    except Exception:  # noqa: BLE001
        return []
    found = re.findall(r"SHA-1 hash: ([0-9A-F]{40})\s.*?(-----BEGIN CERTIFICATE-----.*?"
                       r"-----END CERTIFICATE-----)", text, re.S)
    return [(h.upper(), pem) for h, pem in found]


def system_roots() -> List[str]:
    """The PEMs macOS was told to trust (admin + user settings); [] elsewhere."""
    if sys.platform != "darwin":
        return []
    allowed = _trusted_hashes(["-d"]) | _trusted_hashes([])
    if not allowed:
        return []
    keychains = ["/Library/Keychains/System.keychain",
                 os.path.expanduser("~/Library/Keychains/login.keychain-db")]
    pems, seen = [], set()
    for kc in keychains:
        for sha1, pem in _pems_of(kc):
            if sha1 in allowed and sha1 not in seen:
                seen.add(sha1)
                pems.append(pem)
    return pems


def context() -> ssl.SSLContext:
    """The one verifying context for every call to a node."""
    global _CONTEXT
    if _CONTEXT is None:
        ctx = ssl.create_default_context()
        ADDED.clear()
        for pem in system_roots():
            try:
                ctx.load_verify_locations(cadata=pem)
                ADDED.append(pem)
            except ssl.SSLError:
                pass                     # a certificate this OpenSSL cannot read
        _CONTEXT = ctx
    return _CONTEXT


def urlopen(request, timeout: Optional[float] = None):
    """`urllib.request.urlopen` with this context — same signature, same errors."""
    if timeout is None:
        return urllib.request.urlopen(request, context=context())
    return urllib.request.urlopen(request, timeout=timeout, context=context())


def fetch_json(url: str, timeout: float):
    """For `s3dgraphy.tools.node_finder.probe(fetch=…)`: JSON or None."""
    import json
    try:
        with urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}),
                     timeout) as answer:
            return json.loads(answer.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 — not there, not JSON, refused: no answer
        return None


def describe() -> str:
    context()
    return (f"TLS: Python's roots + {len(ADDED)} the system trusts"
            if ADDED else "TLS: Python's roots")
