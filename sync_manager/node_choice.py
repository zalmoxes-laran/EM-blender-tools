"""N1/N2 · «Choose the node» in EM Tools — the same panel as EMStudio's.

The finding is s3dgraphy's (``tools.node_finder.find_nodes``): this computer,
the nodes of the local network that announce themselves (``dns-sd`` on macOS,
``avahi-browse`` on Linux — Blender's Python has no ``zeroconf``, and none is
added), the saved list (``servers.saved``) and one typed by hand. Each says
whether it answers, its version and the ways in, and ONE sentence says what to
do. «Turn on a node on this computer» runs the server's own launcher next door
(``stratigraph-server/scripts/personal_node.py``): this computer only, the
files stay in the project's folders; «Open to the local network» is a choice
made with a dialog that says who will be able to come in.
"""

import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

#: the last answer, for the panel (session state)
FOUND: Dict[str, Any] = {}
PERSONAL: Dict[str, Any] = {}


def launcher() -> Optional[str]:
    """The personal-node launcher of a StratiGraph server next door, or None."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [os.environ.get("EM_SERVER_CHECKOUT") or "",
                  os.path.join(os.path.dirname(os.path.realpath(here)), "stratigraph-server")]
    for c in candidates:
        script = os.path.join(c, "scripts", "personal_node.py") if c else ""
        if script and os.path.isfile(script):
            return script
    return None


def personal(action: str, root: str = "", lan: bool = False) -> Dict[str, Any]:
    script = launcher()
    if script is None:
        return {"ok": False, "error": "no StratiGraph server next door: install one to "
                                      "turn on a node on this computer"}
    server = os.path.dirname(os.path.dirname(script))
    py = os.path.join(server, ".venv", "bin", "python")
    cmd = [py if os.path.isfile(py) else sys.executable, script, action]
    if action == "start":
        cmd += ["--root", root] + (["--lan"] if lan else [])
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    try:
        out = json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        out = {"ok": False, "error": (done.stderr or done.stdout)[-300:]}
    PERSONAL.clear()
    PERSONAL.update(out)
    return out


def find(typed: str = "") -> Dict[str, Any]:
    from s3dgraphy.tools.node_finder import find_nodes, probe
    from . import servers
    from s3dgraphy.room_import import trust
    saved = [s["url"] for s in servers.saved()]
    FOUND.clear()
    # each probe verifies TLS against what this computer trusts: without it the
    # node behind Caddy never answers Blender (trust.py, measured 4 Oct 2026)
    FOUND.update(find_nodes(saved=saved, typed=typed, lang="en",
                            prober=lambda u: probe(u, fetch=trust.fetch_json)))
    return FOUND


#: address → the identity the node declares (`GET /v1/node` → `public_base`),
#: or "" when it declares none: read once per address and session
IDENTITY: Dict[str, str] = {}


def identity_of(url: str, fetch=None) -> str:
    """The node behind `url`, as it says it: its ``public_base`` (MICRO una
    verità, 13 Oct 2026: ``localhost:8000``, ``em.localhost:8443/em`` and
    ``<mac>.local:8000`` were three rows of ONE node). The node declares no id
    of its own yet: the public base is the identity it guarantees. "" if it
    does not say."""
    url = str(url or "").rstrip("/")
    if url in IDENTITY:
        return IDENTITY[url]
    if fetch is None:
        from s3dgraphy.room_import import trust
        fetch = trust.fetch_json
    try:
        said = fetch(f"{url}/v1/node", 2.0) or {}
    except Exception:  # noqa: BLE001
        said = {}
    ident = str(said.get("node_id") or said.get("public_base") or "").rstrip("/")
    IDENTITY[url] = ident
    return ident


def one_row_per_node(found: Dict[str, Any], identities: Dict[str, str], *,
                     in_use: str = "", saved=()) -> List[Dict[str, Any]]:
    """The nodes of «Choose the node», ONE row each, whatever the number of
    addresses it answers on: grouped by the identity the node declares
    (`identity_of`), shown by its public address (the others in Details).
    ``in_use`` is the address this project uses: its node is «● in use» and
    has no «Use». → ``[{url, addresses, where, reachable, version, profile,
    saved, in_use, name}]`` in the order This computer, the local network,
    Saved, typed."""
    norm = lambda u: str(u or "").rstrip("/")  # noqa: E731
    saved = {norm(u) for u in saved}
    in_use = norm(in_use)
    rows: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for group in ("local", "lan", "saved", "typed"):
        for n in found.get(group) or []:
            url = norm(n.get("url"))
            if not url:
                continue
            key = identities.get(url) or url
            row = rows.get(key)
            if row is None:
                row = {"url": key if identities.get(url) else url, "addresses": [],
                       "where": group, "reachable": False, "version": "",
                       "profile": "", "saved": False, "in_use": False, "name": ""}
                rows[key] = row
                order.append(key)
            if url not in row["addresses"]:
                row["addresses"].append(url)
            row["reachable"] = row["reachable"] or bool(n.get("reachable"))
            row["version"] = row["version"] or str(n.get("version") or "")
            row["profile"] = row["profile"] or str(n.get("profile") or "")
            row["name"] = row["name"] or str(n.get("name") or "")
            row["saved"] = row["saved"] or url in saved
            if in_use and (url == in_use or key == in_use):
                row["in_use"] = True
    out = [rows[k] for k in order]
    for row in out:
        if row["url"] not in row["addresses"]:
            # the public address is how the node is shown, even when it was
            # found through another one
            row["addresses"].insert(0, row["url"])
        if in_use and in_use in row["addresses"]:
            row["in_use"] = True
    return out


def advice(rows: List[Dict[str, Any]], *, personal_on: bool) -> Dict[str, Any]:
    """What the window suggests — only what is true: no «there is a node on
    your computer: use it» when it is already the one in use; no «Turn on a
    node» when one answers on this computer. → ``{sentence, turn_on}``."""
    using = next((r for r in rows if r["in_use"]), None)
    local = [r for r in rows if r["where"] == "local" and r["reachable"]]
    if using is not None:
        sentence = ""
    elif local:
        sentence = "There is a node on this computer: Use it to work offline."
    elif any(r["reachable"] for r in rows):
        sentence = "A node answers: Use it to enter its rooms."
    else:
        sentence = "No node found: work on this computer, or type a node's address."
    return {"sentence": sentence, "turn_on": not local and not personal_on}


def _operator_classes():  # pragma: no cover — bpy
    import bpy  # type: ignore

    class EM_OT_nodes_find(bpy.types.Operator):
        """Look for a node: this computer, the local network, the saved ones"""
        bl_idname = "em.nodes_find"
        bl_label = "Choose the node…"
        typed: bpy.props.StringProperty(default="")  # type: ignore

        def execute(self, context):
            got = find(self.typed)
            personal("status")
            self.report({"INFO"}, got["suggestion"])
            return {"FINISHED"}

    class EM_OT_node_personal(bpy.types.Operator):
        """Turn on (this computer only), open to the local network, or turn off
        the personal node"""
        bl_idname = "em.node_personal"
        bl_label = "Personal node"
        action: bpy.props.StringProperty(default="start")  # type: ignore
        lan: bpy.props.BoolProperty(default=False)  # type: ignore

        def invoke(self, context, event):
            if self.action == "start" and self.lan:
                return context.window_manager.invoke_confirm(
                    self, event, title="Open to the local network?",
                    message=("Everybody on this local network will be able to reach "
                             "this node and its rooms, without a password, until you "
                             "close it."))
            return self.execute(context)

        def execute(self, context):
            from .file_states import project_root
            root = project_root(context) or (os.path.dirname(bpy.data.filepath)
                                             if bpy.data.filepath else "")
            if self.action == "start" and not root:
                self.report({"ERROR"}, "which project? save the .blend in its EM project")
                return {"CANCELLED"}
            out = personal(self.action, root, self.lan)
            if not out.get("ok"):
                self.report({"ERROR"}, str(out.get("error")))
                return {"CANCELLED"}
            if self.action == "start":
                context.scene.em_room_url = out["url"]
                self.report({"INFO"}, f"{out['url']} · {out.get('who', '')}")
            find()
            return {"FINISHED"}

    return (EM_OT_nodes_find, EM_OT_node_personal)


def draw(layout, context) -> None:  # pragma: no cover — bpy
    box = layout.box()
    head = box.row(align=True)
    head.label(text="Choose the node", icon="WORLD")
    head.operator("em.nodes_find", text="Look", icon="VIEWZOOM")
    if not FOUND:
        box.label(text="«Look»: this computer, the local network, the saved nodes.", icon="INFO")
        return
    from ..state_symbols import sign
    box.label(text=FOUND["suggestion"], icon="LIGHT")

    def rows(title, nodes, empty):
        col = box.column(align=True)
        col.label(text=title)
        if not nodes:
            col.label(text=empty, icon="BLANK1")
        for n in nodes:
            icon = sign("node.reachable" if n["reachable"] else "node.unreachable")[0]
            line = col.row(align=True)
            facts = " · ".join(x for x in (n.get("version", ""),
                                            "personal" if n.get("profile") == "personal" else "",
                                            ", ".join(n.get("ways_in") or [])) if x)
            line.label(text=f"{n.get('name') or n['url']}  {facts}", icon=icon)
            if n["reachable"]:
                op = line.operator("em.server_use", text="Use")
                op.url = n["url"]

    rows("This computer", FOUND.get("local") or [], "none")
    acts = box.row(align=True)
    if PERSONAL.get("running") or PERSONAL.get("pid"):
        acts.label(text="Personal node on", icon="HOME")
        op = acts.operator("em.node_personal", text="Close to the network" if PERSONAL.get("lan")
                           else "Open to the local network…")
        op.action, op.lan = "start", not PERSONAL.get("lan")
        acts.operator("em.node_personal", text="Turn off").action = "stop"
        box.label(text="Personal node: the files stay in your folders; keep them on a "
                       "backed-up disk.", icon="ERROR")
    else:
        op = acts.operator("em.node_personal", text="Turn on a node on this computer", icon="PLAY")
        op.action, op.lan = "start", False
    rows("The local network (found by themselves)", FOUND.get("lan") or [],
         FOUND.get("lan_note") or "no node announces itself on this network")
    rows("Saved", FOUND.get("saved") or [], "none")
    box.label(text=FOUND.get("real_node", ""), icon="INFO")
    travaso = box.row()
    travaso.enabled = False
    travaso.label(text="Move to another node… — not available yet", icon="FORWARD")


_CLASSES: tuple = ()


def register():  # pragma: no cover — bpy
    import bpy  # type: ignore
    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():  # pragma: no cover — bpy
    import bpy  # type: ignore
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
