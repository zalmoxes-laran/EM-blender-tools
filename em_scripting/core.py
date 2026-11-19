"""``em`` in Blender — MICRO-PL19, row W16 of the extensions plan (E.D., 18 Nov 2026).

The scripting API of s3Dgraphy (``from s3dgraphy import em``, W11) is the same
in EMStudio, in EM Tools and in a script with no application: what differs is
the HOST, which says which graph is open, who is working, who is calling, and
how a delta becomes a step (SPEC-plugin §2, §11). This module is EM Tools' host,
the half that does not need Blender:

* :class:`BlenderHost` — ``graph``/``overlay``/``author``/``caller``/``language``
  come from callables the add-on gives (the active graph of the EM Setup list,
  the overlay of community packages, the room's or the Preferences' identity);
  :meth:`BlenderHost.apply` is ONE step: the act's DTC process (a
  ``dtc_process`` node naming the console, the script or the plugin — with the
  code of a script, D-8), the delta through the seam on the live graph
  (``apply_delta_to_graph``, G2), its INVERSE kept for «Undo», a line in the
  host's Log, ``graph-changed``; then the add-on refreshes its lists and sends
  the same operations to a room or to EMStudio (``after_apply``);
* :func:`inverse` — the act that brings the graph back, from two snapshots:
  Blender's undo does not hold the graph (it lives in Python, outside
  ``bpy.data``), so an EM write is undone by an EM write through the seam;
* the plugins' menu: every loaded plugin whose ``hosts`` names ``blender``, its
  commands with ``when`` held against Blender's selection, the mark
  «not verified» / «development» (W15a), the slots filled from what Blender
  knows (``id`` ← the selected nodes in order, ``ids`` ← all, ``path`` ← a file
  the person chose), never invented (PL17 S-8);
* the camera in the scene's frame (Y-up, metres: EMStudio's ``{pos, target}``),
  so a script that reads or sets it says the same thing in both applications.

No ``bpy`` here: pytest measures it with a plain s3Dgraphy graph.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

HOST = "blender"
CONSOLE_CALLER = "emtools.console"
SCRIPT_CALLER = "emtools.script"
UNDO_CALLER = "emtools.undo"

#: D-8 · the code of an act kept in its DTC up to 4 kB; beyond, its hash and a copy
CODE_MAX = 4096

#: what the host says when no graph is active (EN, IT: an em result carries both)
NO_GRAPH = {"en": "no graph is active in EM Tools: load one in EM Setup",
            "it": "nessun grafo attivo in EM Tools: caricane uno in EM Setup"}

#: how many steps the host's Log keeps (the oldest go; their undo with them)
LOG_MAX = 50


# ── the library, as this Blender has it ────────────────────────────────────

def em_module():
    """``s3dgraphy.em`` with its plugin loader, or None: the bundled wheel
    may be older than ``em`` (dev124) — the menus say so instead of failing."""
    try:
        from s3dgraphy import em
        from s3dgraphy.em import plugins  # noqa: F401 — W14's loader, needed for the menu
        return em
    except Exception:  # noqa: BLE001 — an older s3dgraphy
        return None


def available() -> bool:
    return em_module() is not None


def _version(addon_version: Optional[str]) -> str:
    return addon_version or "?"


def _descriptor(name: str, description: str, addon_version: Optional[str],
                capabilities: Sequence[str] = ("read-graph", "write-graph", "ingest-batch")):
    from s3dgraphy import __version__
    from s3dgraphy.contract import ConnectorDescriptor, current_versions
    return ConnectorDescriptor(
        name=name, host="app-side", transport=["direct"], capabilities=list(capabilities),
        versions=current_versions(), provenance="derivation", service="emtools",
        description=description,
        vendor={"s3dgraphy": __version__, "version": f"EM Tools {_version(addon_version)}"})


def console_caller(addon_version: Optional[str] = None):
    """Blender's Python console with ``em``: it reads, writes and proposes,
    speaks this build's versions (so the 1.1 ops pass) — EMStudio's console twin."""
    return _descriptor(CONSOLE_CALLER, "Blender's Python console (em in EM Tools)", addon_version)


def script_caller(addon_version: Optional[str] = None):
    """A text of Blender's Text Editor run as an EM script (its code in the DTC)."""
    return _descriptor(SCRIPT_CALLER, "a script of Blender's Text Editor run through em (EM Tools)",
                       addon_version)


def undo_caller(addon_version: Optional[str] = None):
    """Who writes an «Undo»: EM Tools itself, and it only changes the graph."""
    return _descriptor(UNDO_CALLER, "EM Tools undoing an em write", addon_version,
                       capabilities=("read-graph", "write-graph"))


# ── D-8 · the code of a script, as its DTC keeps it ─────────────────────────

def console_dir() -> Path:
    env = os.environ.get("S3DGRAPHY_CONSOLE_DIR")
    return Path(env).expanduser() if env else Path.home() / ".s3dgraphy" / "console"


def code_record(code: Optional[str]) -> Dict[str, Any]:
    """The text up to 4 kB; beyond, its sha256 and the copy this machine keeps
    (``~/.s3dgraphy/console/scripts/<sha256>.py``) — the keys of EMStudio's."""
    if not code:
        return {}
    raw = code.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    out: Dict[str, Any] = {"code_sha256": digest, "code_bytes": len(raw)}
    if len(raw) <= CODE_MAX:
        out["code"] = code
        return out
    try:
        folder = console_dir() / "scripts"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{digest}.py"
        if not target.exists():
            target.write_bytes(raw)
        out["code_ref"] = (str(target) if "S3DGRAPHY_CONSOLE_DIR" in os.environ
                           else f"~/.s3dgraphy/console/scripts/{digest}.py")
    except OSError as exc:
        out["code_ref"] = None
        out["code_ref_error"] = str(exc)
    return out


# ── snapshots and the inverse act ───────────────────────────────────────────

Snapshot = Tuple[Dict[str, Dict[str, Any]], Dict[Tuple[str, str, str], str]]


def snapshot(graph: Any) -> Snapshot:
    """The graph as ``em.write`` sees it (payload of every node without the
    seam's stamps, relations by triple) — the same words its diff uses."""
    from s3dgraphy.em.write import _snapshot
    return _snapshot(graph)


def _same(a: Any, b: Any) -> bool:
    try:
        return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return a == b


def inverse(before: Snapshot, after: Snapshot, author: Optional[str] = None):
    """The delta that turns ``after`` back into ``before``: the nodes the act
    removed come back (with their relations), the fields it changed take their
    old value (or are emptied), what it added goes. The seam's stamps are not
    in a snapshot: a node that comes back is stamped again by the undo."""
    from s3dgraphy.contract import Delta
    from s3dgraphy.em.write import _NOT_DIFFED
    b_nodes, b_edges = before
    a_nodes, a_edges = after
    d = Delta(author=author)
    for nid, payload in b_nodes.items():
        if nid not in a_nodes:
            d.nodes.append(copy.deepcopy(payload))
    for nid, now in a_nodes.items():
        old = b_nodes.get(nid)
        if old is None:
            continue
        for fld in ("name", "description"):
            if not _same(old.get(fld), now.get(fld)):
                if old.get(fld) in (None, ""):
                    d.update_field(nid, fld, remove=True)
                else:
                    d.update_field(nid, fld, old.get(fld))
        od, nd = old.get("data") or {}, now.get("data") or {}
        for key in sorted(set(od) | set(nd)):
            if key in _NOT_DIFFED:
                continue
            if key not in od:
                d.update_field(nid, f"data.{key}", remove=True)
            elif key not in nd or not _same(od[key], nd[key]):
                d.update_field(nid, f"data.{key}", copy.deepcopy(od[key]))
    born = [nid for nid in a_nodes if nid not in b_nodes]
    gone = set(born)
    for triple, eid in b_edges.items():
        if triple not in a_edges:
            d.edges.append({"id": eid, "source": triple[0], "edge_type": triple[1], "target": triple[2]})
    for triple, eid in a_edges.items():
        # a relation of a node the undo removes goes with it
        if triple not in b_edges and triple[0] not in gone and triple[2] not in gone:
            d.remove_edge(eid)
    for nid in born:
        d.remove_node(nid)
    return d


def wire_ops(delta) -> List[Dict[str, Any]]:
    """The delta as the local changes ``sync_manager.emit_op`` sends to a room
    or to EMStudio (``s3dgraphy.crdt.ops_for_local_change`` reads them): the
    same operations, so whoever shares the graph sees the act."""
    out: List[Dict[str, Any]] = []
    for n in delta.nodes:
        out.append({"op": "add_node", "node": copy.deepcopy(n)})
    for e in delta.edges:
        src, et, tgt = e.get("source"), e.get("edge_type"), e.get("target")
        out.append({"op": "add_edge", "id": e.get("id") or f"{src}__{et}__{tgt}",
                    "source": src, "target": tgt, "edge_type": et})
    for op in delta.ops:
        out.append({k: copy.deepcopy(v) for k, v in op.items() if k not in ("ts", "author")})
    return out


def structural(delta) -> bool:
    """True when the lists must be rebuilt (a node or relation came or went);
    a field lands in place."""
    return bool(delta.nodes or delta.edges or any(op.get("op") != "update_field" for op in delta.ops))


# ── the host's Log ──────────────────────────────────────────────────────────

@dataclass
class Step:
    """One applied act: a line of the Log and, until undone, its «Undo»."""
    label: str
    author: Optional[str]
    caller: str
    when: str
    ids: List[str]
    applied: Dict[str, Any]
    refused: List[Dict[str, Any]]
    volatile: bool
    dtc: Optional[str]
    undo: Any = None                  # the inverse delta
    plugin: Optional[Dict[str, Any]] = None
    undone: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {"label": self.label, "author": self.author, "caller": self.caller, "when": self.when,
                "ids": list(self.ids), "applied": self.applied, "refused": list(self.refused),
                "volatile": self.volatile, "dtc": self.dtc, "plugin": self.plugin, "undone": self.undone}


# ── the host ────────────────────────────────────────────────────────────────

class BlenderHost:
    """The host of ``em`` inside EM Tools. ``graph``, ``overlay``, ``author``,
    ``language`` are callables (the add-on reads Blender at each call: the
    active graph changes with the EM Setup list); ``app`` is ``em.app``;
    ``after_apply(step, delta, result)`` is told of every applied act (and of
    every undo), after the seam and before ``graph-changed``."""

    name = HOST

    def __init__(self, *, graph: Callable[[], Any], overlay: Optional[Callable[[], Any]] = None,
                 author: Optional[Callable[[], Optional[str]]] = None,
                 language: Optional[Callable[[], Optional[str]]] = None,
                 app: Any = None, after_apply: Optional[Callable[..., None]] = None,
                 addon_version: Optional[str] = None, session: Optional[str] = None):
        from s3dgraphy.em.host import NoApp
        self._graph = graph
        self._overlay = overlay
        self._author = author or (lambda: None)
        self._language = language or (lambda: None)
        self.app = app if app is not None else NoApp(HOST)
        self.after_apply = after_apply
        self.addon_version = addon_version
        self.session = session or uuid.uuid4().hex[:12]
        self._console = console_caller(addon_version)
        self._caller = None                       # a script's descriptor while it runs
        self.code: Optional[str] = None           # D-8 · the code of the script running
        self.steps: List[Step] = []
        self.proofs: List[Dict[str, Any]] = []
        self.force_dry_run = False
        self._dtc_n = 0

    # what em reads
    def graph(self) -> Any:
        return self._graph()

    def overlay(self) -> Any:
        ov = self._overlay() if self._overlay else None
        if ov is not None:
            return ov
        from s3dgraphy.profiles import EMPTY
        return EMPTY

    def author(self) -> Optional[str]:
        a = self._author()
        return str(a) if a else None

    def caller(self) -> Any:
        return self._caller or self._console

    def language(self) -> Optional[str]:
        return self._language()

    def commands(self) -> List[str]:
        """The loaded plugins' commands (W14): «plugin/command — label»."""
        em = em_module()
        if em is None:
            return []
        lg = "it" if str(self.language() or "").startswith("it") else "en"
        return [f"{c.name} — {c.label_in(lg)}" for c in em.plugins.commands()]

    def proved(self, result: Any) -> None:
        """A proof (``dry_run``): said in the Log, applied nowhere."""
        try:
            d = result.delta
            self.proofs.append({"label": result.label, "nodes": len(d.nodes), "edges": len(d.edges),
                                "ops": len(d.ops), "ok": bool(result.ok)})
            del self.proofs[:-LOG_MAX]
        except Exception:  # noqa: BLE001 — a proof is information
            pass

    # a script of the Text Editor
    def running(self, code: Optional[str]):
        """``with host.running(code):`` — the writes of this block are the
        SCRIPT's (its descriptor, its code in the DTC)."""
        host = self

        class _Run:
            def __enter__(self_inner):
                host._caller, host.code = script_caller(host.addon_version), code
                return host

            def __exit__(self_inner, *exc):
                host._caller, host.code = None, None
                return False
        return _Run()

    # the DTC of an act
    def dtc_node(self, label: str, descriptor: Any, ids: List[str]) -> Tuple[str, Dict[str, Any]]:
        em = em_module()
        self._dtc_n += 1
        gid = getattr(self.graph(), "graph_id", "") or ""
        nid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"emtools:em:{gid}:{self.session}:{self._dtc_n}"))
        vendor = descriptor.vendor or {}
        params: Dict[str, Any] = {"label": label, "host": HOST, "touched": ids[:200]}
        if vendor.get("plugin"):
            # the act of a plugin: which one, which command, from where, unverified (PL17)
            from s3dgraphy.em.plugins import calling_now
            now = calling_now()
            cmd = getattr(getattr(now, "command", None), "id", None) if now else None
            params.update({"plugin": vendor.get("plugin"), "plugin_version": vendor.get("version"),
                           "source": vendor.get("source"), "verified": bool(vendor.get("verified")),
                           **({"package": vendor["package"]} if vendor.get("package") else {}),
                           **({"command": cmd} if cmd else {})})
        elif self.code is not None:
            params.update(code_record(self.code))
            params["source"] = "Text Editor"
        else:
            params["source"] = "Python console"
        return nid, {
            "id": nid, "node_type": "dtc_process", "name": label,
            "description": "Python (em) · " + descriptor.name,
            "data": {"dtc_kind": "transformation", "technique": "Python (em)",
                     "software": [{"name": descriptor.name, "version": vendor.get("version")},
                                  {"name": "s3dgraphy.em", "version": getattr(em, "API_VERSION", None)}],
                     "parameters": params}}

    def _no_graph(self):
        from s3dgraphy.contract import Result
        msgs = dict(NO_GRAPH)
        return Result(ok=False, message=msgs["en"], data={"reason": "no-graph", "messages": msgs})

    def apply(self, delta: Any, *, descriptor: Any, capability: str, label: str) -> Any:
        """ONE step: the DTC process, the delta through the seam on the live
        graph, the inverse kept, the Log, the add-on told, ``graph-changed``."""
        from s3dgraphy.contract import apply_delta_to_graph
        from s3dgraphy.em import events
        from s3dgraphy.em.host import process_of, touched_ids
        graph = self.graph()
        if graph is None:
            return self._no_graph()
        delta.process = delta.process or process_of(descriptor, label, host=HOST)
        ids = touched_ids(delta)
        dtc_id = None
        if delta.writes:
            dtc_id, node = self.dtc_node(label, descriptor, ids)
            delta.nodes.append(node)
        before = snapshot(graph)
        result = apply_delta_to_graph(graph, descriptor, capability, delta)
        if not result.ok:
            return result
        after = snapshot(graph)
        vendor = descriptor.vendor or {}
        step = Step(label=label, author=delta.author, caller=descriptor.name,
                    when=time.strftime("%H:%M:%S"), ids=ids,
                    applied=dict(result.data.get("applied") or {}),
                    refused=list(result.data.get("refused") or []),
                    volatile=bool(result.data.get("volatile")), dtc=dtc_id,
                    undo=inverse(before, after),
                    plugin=({"id": vendor.get("plugin"), "version": vendor.get("version"),
                             "source": vendor.get("source"), "verified": bool(vendor.get("verified"))}
                            if vendor.get("plugin") else None))
        self.steps.append(step)
        del self.steps[:-LOG_MAX]
        self._tell(step, delta, result)
        events.emit("graph-changed", {"label": label, "ids": ids, "volatile": step.volatile})
        return result

    def _tell(self, step: Step, delta: Any, result: Any) -> None:
        if self.after_apply is None:
            return
        try:
            self.after_apply(step, delta, result)
        except Exception as exc:  # noqa: BLE001 — the act is applied; the refresh is said
            print(f"[em] after the write «{step.label}»: {exc}")

    def last_undoable(self) -> Optional[Step]:
        for s in reversed(self.steps):
            if not s.undone:
                return s
        return None

    def undo(self) -> Tuple[Optional[Step], Any]:
        """Undo the newest act not undone yet, through the seam (EM Tools as
        the caller, the session's author). ``(step, result)``; ``(None, None)``
        when there is nothing to undo."""
        from s3dgraphy.contract import apply_delta_to_graph
        from s3dgraphy.em import events
        step = self.last_undoable()
        if step is None:
            return None, None
        graph = self.graph()
        if graph is None:
            return step, self._no_graph()
        d = copy.deepcopy(step.undo)
        d.author = self.author()
        result = apply_delta_to_graph(graph, undo_caller(self.addon_version), "write-graph", d)
        if result.ok:
            step.undone = True
            from s3dgraphy.em.host import touched_ids
            self._tell(Step(label=f"undo: {step.label}", author=d.author, caller=UNDO_CALLER,
                            when=time.strftime("%H:%M:%S"), ids=touched_ids(d),
                            applied=dict(result.data.get("applied") or {}),
                            refused=list(result.data.get("refused") or []), volatile=False, dtc=None),
                       d, result)
            events.emit("graph-changed", {"label": f"undo: {step.label}", "ids": touched_ids(d),
                                          "volatile": False})
        return step, result

    def __repr__(self) -> str:
        gid = getattr(self.graph(), "graph_id", None)
        return f"<em host: blender · graph {gid!r}>"


# ── selection, nodes and objects ────────────────────────────────────────────

def selected_types(graph: Any, ids: Iterable[str]) -> List[str]:
    out = []
    for i in ids:
        n = graph.find_node_by_id(i) if graph is not None else None
        if n is not None:
            out.append(str(getattr(n, "node_type", "") or ""))
    return out


def fill_slots(slots: Sequence[Mapping[str, Any]], selection: Sequence[str],
               path: Optional[str] = None) -> Dict[str, Any]:
    """What Blender knows, into a command's slots — EMStudio's ``fillSlots``:
    ``id`` ← the next selected node, ``ids`` ← all of them, ``path`` ← the file
    the person chose. ``string``/``number`` never: the contract asks for them."""
    out: Dict[str, Any] = {}
    nxt = 0
    for s in slots:
        kind, name = s.get("kind", "string"), s.get("name")
        if kind == "id" and nxt < len(selection):
            out[name] = selection[nxt]
            nxt += 1
        elif kind == "ids" and selection:
            out[name] = list(selection)
        elif kind == "path" and path:
            out[name] = path
    return out


def wants_path(slots: Sequence[Mapping[str, Any]]) -> bool:
    return any(s.get("kind") == "path" for s in slots)


# ── the plugins' menu (EM ▸ Plugin) ─────────────────────────────────────────

@dataclass
class MenuCommand:
    plugin: str
    id: str
    label: str
    enabled: bool
    off: List[str] = field(default_factory=list)       # slots of phase 2 / unknown: said
    path: bool = False
    exporter: bool = False
    writes: bool = False


@dataclass
class MenuSection:
    plugin: str
    name: str
    version: str
    state: str
    badge: str                       # "" · "not verified" · "development"
    why: str = ""
    commands: List[MenuCommand] = field(default_factory=list)


def badge_of(source: str, verified: bool) -> str:
    """W15a · the mark seen in the menu: «not verified» from disk, «development»
    from the development folder, nothing for a verified one (phase 2)."""
    if verified:
        return ""
    return "development" if source == "dev" else "not verified"


def menu_sections(lang: str = "en", *, document: bool = True,
                  types: Sequence[str] = ()) -> List[MenuSection]:
    """Every plugin of this Blender (loaded or not, with the why), its commands
    with ``when`` held against the selection. In Blender every command of a
    plugin goes under EM ▸ Plugin (SPEC-plugin §11), wherever its ``in`` puts
    it in EMStudio."""
    em = em_module()
    if em is None:
        return []
    from s3dgraphy.extensions.slots import when_holds
    lg = "it" if str(lang).startswith("it") else "en"
    out: List[MenuSection] = []
    for p in em.plugins.loaded():
        why = ""
        if p.state != "loaded" and p.problems:
            why = p.problems[-1].get(lg) or p.problems[-1].get("en") or ""
        sec = MenuSection(plugin=p.id, name=_name_of(p, lg), version=p.version, state=p.state,
                          badge=badge_of(p.source, bool(p.meta.get("verified"))), why=why or p.state)
        if p.state == "loaded":
            for c in p.commands.values():
                where = [w.split("@")[0] for w in c.where]
                sec.commands.append(MenuCommand(
                    plugin=p.id, id=c.id, label=c.label_in(lg),
                    enabled=(c.id in p.handlers) and when_holds(c.when or "", document=document,
                                                                 selected_types=list(types)),
                    path=wants_path(c.slots), exporter=any(w.startswith("menu.file.export")
                                                           or w.startswith("export.") for w in where),
                    writes=bool(c.writes)))
        out.append(sec)
    return out


def _name_of(p: Any, lg: str) -> str:
    n = p.meta.get("name") if isinstance(p.meta, Mapping) else None
    if isinstance(n, Mapping):
        return str(n.get(lg) or n.get("en") or next(iter(n.values()), p.id))
    return str(n or p.id)


def plugin_badge_text(badge: str, tr=lambda s: s) -> str:
    return tr(badge) if badge else ""


# ── the camera in the scene's frame ─────────────────────────────────────────

def blender_to_scene(p: Sequence[float]) -> List[float]:
    """Blender (Z-up) → the scene's glTF frame (Y-up): ``(x, y, z) → (x, z, −y)``,
    the inverse of ``community_packages.core.scene_to_blender``."""
    x, y, z = (float(v) for v in p)
    return [x, z, -y]


def scene_to_blender(p: Sequence[float]) -> List[float]:
    x, y, z = (float(v) for v in p)
    return [x, -z, y]


def camera_state(location: Sequence[float], forward: Sequence[float], distance: float) -> Dict[str, List[float]]:
    """A 3D view as EMStudio's ``CamState`` (``{pos, target}``, scene frame):
    ``location`` is the view's pivot, ``forward`` the direction it looks at
    (Blender frame), ``distance`` from the eye to the pivot."""
    tx, ty, tz = (float(v) for v in location)
    fx, fy, fz = (float(v) for v in forward)
    eye = [tx - fx * distance, ty - fy * distance, tz - fz * distance]
    return {"pos": [round(v, 6) for v in blender_to_scene(eye)],
            "target": [round(v, 6) for v in blender_to_scene((tx, ty, tz))]}


def view_of(camera: Mapping[str, Any]) -> Tuple[List[float], List[float], float]:
    """``{pos, target}`` (scene frame) → ``(pivot, forward, distance)`` in
    Blender's frame, for a 3D view. Raises ``ValueError`` for a camera with no
    ``target`` or ``pos``, or with the eye on the target."""
    try:
        pos = scene_to_blender(camera["pos"])
        tgt = scene_to_blender(camera["target"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("a camera is {pos: [x, y, z], target: [x, y, z]}") from exc
    d = [t - p for p, t in zip(pos, tgt)]
    dist = sum(v * v for v in d) ** 0.5
    if dist <= 1e-9:
        raise ValueError("the camera's pos and target are the same point")
    return tgt, [v / dist for v in d], dist


__all__ = ["HOST", "BlenderHost", "Step", "available", "em_module", "console_caller", "script_caller",
           "undo_caller", "code_record", "snapshot", "inverse", "wire_ops", "structural",
           "selected_types", "fill_slots", "wants_path", "MenuSection", "MenuCommand", "menu_sections",
           "badge_of", "camera_state", "view_of", "blender_to_scene", "scene_to_blender"]
