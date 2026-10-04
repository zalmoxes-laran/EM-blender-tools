"""Which StratiGraph Servers this Blender knows about — the saved list, and the probe.

Two questions, and they are not the same one:

* **where is a server?** On a dig that is a laptop on the local network; at an
  institution it is a name somebody gave you once. So: a **saved list** that
  survives the session, and to which you add the institutional ones by hand.
* **is it really there?** A URL you typed is a hope. A **probe** turns it into a
  fact: `/v1/health` answers with what that server is, whether it enforces
  tokens, and how many rooms it holds. Filling the field with an address nobody
  has answered from is how "join" becomes a stare at a spinner.

**mDNS browsing is NOT here, and it is not simulated.** Blender's Python has no
`zeroconf` (measured: `No module named 'zeroconf'` on 3.13.9), so this addon
cannot listen for `_StratiGraph Server._tcp` announcements. What it does instead is what
the network already gives us for free: **probe the Bonjour names directly**. The
walkthrough already tells people to reach the other Mac as `<name>.local`, and a
directed probe of a candidate name is a real answer about a real host — not a
discovery pretending to have browsed anything.

If somebody installs `zeroconf` into Blender's Python, the seam for browsing is
`discover()` below: it returns candidates, and where they come from is its own
business.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


def _urlopen(request, timeout=None):
    """Every call to a node verifies TLS against what this computer trusts
    (`trust.py`: the dev node behind Caddy included)."""
    try:
        from .trust import urlopen
    except ImportError:          # loaded by path, outside the package (the suite)
        import urllib.request
        return urllib.request.urlopen(request, timeout=timeout)
    return urlopen(request, timeout=timeout)

#: Where the saved list lives: a JSON file beside Blender's user config, because
#: a list of servers is a property of THIS INSTALLATION, not of a .blend. Saving
#: it in the scene would make it travel with a file somebody sends you, which is
#: both surprising and, for an institutional address, mildly rude.
_FILE = "em_servers.json"


def _path() -> str:
    import os

    import bpy  # type: ignore

    folder = bpy.utils.user_resource("CONFIG", path="EM", create=True)
    return os.path.join(folder, _FILE)


def saved() -> List[Dict[str, Any]]:
    """The list, or an empty one. A file that will not parse is EMPTY and says
    so in the console: a corrupted list must not take the panel down with it."""
    try:
        with open(_path(), encoding="utf-8") as handle:
            data = json.load(handle)
        servers = data.get("servers") if isinstance(data, dict) else data
        return [s for s in (servers or []) if isinstance(s, dict) and s.get("url")]
    except FileNotFoundError:
        return []
    except Exception as exc:  # noqa: BLE001
        print(f"[em] the saved server list will not read ({exc}); starting empty")
        return []


def save(servers: List[Dict[str, Any]]) -> None:
    import os

    path = _path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump({"servers": servers}, handle, ensure_ascii=False, indent=1)
    os.replace(tmp, path)      # atomic: a half-written list is never read


def remember(url: str, label: str = "", **extra: Any) -> List[Dict[str, Any]]:
    """Add (or update) a server. Keyed by URL — the same address twice is one
    entry, whatever somebody called it the second time."""
    url = (url or "").strip().rstrip("/")
    if not url:
        return saved()
    servers = [s for s in saved() if s.get("url") != url]
    servers.append({"url": url, "label": (label or url).strip(), **extra})
    servers.sort(key=lambda s: s.get("label", ""))
    save(servers)
    return servers


def forget(url: str) -> List[Dict[str, Any]]:
    servers = [s for s in saved() if s.get("url") != (url or "").strip().rstrip("/")]
    save(servers)
    return servers


# ── is it there? ─────────────────────────────────────────────────────────────

def probe(url: str, timeout: float = 2.5) -> Dict[str, Any]:
    """Ask a candidate what it is. Never raises — it reports.

    A probe that threw would make "check this address" a thing you can only do
    once; and the interesting answers here are the failures, which is why they
    come back as text rather than as an exception somebody has to catch.
    """
    base = (url or "").strip().rstrip("/")
    if not base:
        return {"ok": False, "url": base, "error": "no address"}
    if "://" not in base:
        base = "http://" + base
    try:
        with _urlopen(f"{base}/v1/health", timeout=timeout) as answer:
            body = json.loads(answer.read().decode("utf-8"))
        return {"ok": True, "url": base,
                "service": body.get("service"), "version": body.get("version"),
                "auth": body.get("auth"), "rooms": body.get("rooms"),
                "snapshot_store": body.get("snapshot_store")}
    except urllib.error.HTTPError as exc:
        # It answered — that is already the useful half: something IS there.
        return {"ok": False, "url": base, "error": f"HTTP {exc.code}",
                "reachable": True}
    except Exception as exc:  # noqa: BLE001 — DNS, refused, TLS, timeout…
        return {"ok": False, "url": base, "error": f"{type(exc).__name__}: {exc}"}


def candidates() -> List[str]:
    """Addresses worth trying on this network, without pretending to browse.

    This machine — the personal node, then the address behind Caddy that EMStudio
    uses (`https://em.localhost:8443/em`, the node's own name in `/v1/auth-config`),
    then the server's bare port —, and this machine's own Bonjour name, which is
    what the walkthrough tells people to use for the other Mac and which resolves
    without any mDNS library because the operating system already speaks it.

    The list of this computer is s3dgraphy's (`node_finder.LOCAL_CANDIDATES`), so
    «Find» and «Choose the node» try the same doors. Measured on 4 Oct 2026: the
    Caddy one was missing here, and even listed it could not answer, because
    Blender's Python did not trust Caddy's root (`trust.py`).
    """
    try:
        from s3dgraphy.tools.node_finder import LOCAL_CANDIDATES
        local = list(LOCAL_CANDIDATES)
    except ImportError:          # an s3dgraphy from before the finder
        local = ["http://127.0.0.1:8777", "http://localhost:8000",
                 "https://em.localhost:8443/em"]
    caddy = [u for u in local if u.startswith("https://")]
    out = ([u for u in local if "127.0.0.1" in u] + caddy
           + [u for u in local if u not in caddy and "127.0.0.1" not in u])
    try:
        host = socket.gethostname().split(".")[0]
        if host:
            out.append(f"http://{host}.local:8000")
    except Exception:  # noqa: BLE001
        pass
    return out


def discover(timeout: float = 2.5) -> Dict[str, Any]:
    """What can be found on this network right now.

    `browsed` is empty and says why: without `zeroconf` there is no mDNS
    browsing in this Python, and inventing a list would be worse than an empty
    one. `probed` is real: the candidates above, asked directly.
    """
    try:
        import zeroconf  # noqa: F401
        browsing = None
    except ImportError:
        browsing = ("no mDNS browsing in this Blender: `zeroconf` is not "
                    "installed in its Python. The probes below are direct — a "
                    "real answer from a real host — and an StratiGraph Server on another "
                    "Mac is reachable as <name>.local, which the OS resolves "
                    "without any library.")
    found = [p for p in (probe(url, timeout) for url in candidates()) if p.get("ok")]
    return {"browsed": [], "browsing_unavailable": browsing, "found": found}
