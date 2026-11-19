"""Community packages in EM Tools — MICRO-PL12, row W9 of the extensions plan (E.D., 18 Nov 2026).

What a community package (EM Profile 0.2) brings to Blender, read through the
SAME library every EM tool reads it with (``s3dgraphy.profiles``,
``s3dgraphy.extensions`` — in the bundled wheel since dev122) and from the SAME
machine folder (``~/.s3dgraphy``: a package installed by EMStudio is here, and
one installed here is in EMStudio):

* **the overlay of a file**: what its ``header.profiles`` declares, plus the
  newest version of every other package installed on this machine — the rule
  of EMStudio (W6, choice 1), so a package just installed is usable at once,
  and saving declares it when the content uses it (``profiles.declare``);
* **the rows of the Preferences** (Community packages): the register of
  ``s3dgraphy.extensions`` with the data-only packages the profile library
  installed by itself;
* **the confirmation before installing**: the data panel and the code panel of
  ``extensions.preview``, as lines;
* **the colour schemes of a package** as the Visual Manager applies them: a
  package writes ``{property, color_mapping: {code of the term: "#hex"}}``
  (SPEC-pacchetto §9, keyed by the CODE so it holds in every language); here it
  becomes an EM Tools .emc (linear colours, ``metadata.value_codes``) — the same
  conversion EMStudio makes for «Into the file»;
* **the vocabularies of a package** with what this machine has of them;
* **the AnnotationRegion chain read** (G14: Proxy Box and Areale READ it; the
  writing is 1.7): the points and surfaces an extractor placed in EMStudio
  carries (``Extractor ─extracted_from→ AnnotationRegion ─is_on_resource→
  model``, ``data.coords`` in the scene's glTF frame), and EM Tools' own form of
  a measured point (``x/y/z`` in the extractor's attributes, Proxy Box) — one
  reader for the two representations of the same act.

No ``bpy`` here: measured with pytest. The panels and operators are in
``ui.py`` / ``operators.py``.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

#: the host EM Tools is for the plugins (W16, MICRO-PL19): a package whose code
#: names ``blender`` in ``hosts`` can install its code here, after the trust
#: question; any other code stays out (its data come in)
HOST = "blender"


# ── the library, as the bundled wheel has it ────────────────────────────────

def library():
    """``(profiles, extensions)`` of the s3dgraphy in use, or ``(None, None)``
    with an older wheel (before dev117 there were no packages): the panels say
    so instead of failing."""
    try:
        from s3dgraphy import profiles as P
        from s3dgraphy import extensions as X
        return P, X
    except Exception:  # noqa: BLE001 — an older bundled s3dgraphy
        return None, None


def available() -> bool:
    return library()[0] is not None


def problem_text(p: Mapping[str, Any], lang: str) -> str:
    """The library's own sentence of a problem, in Italian or English."""
    if not isinstance(p, Mapping):
        return str(p)
    return str(p.get("it") if str(lang).lower().startswith("it") else p.get("en")) or str(p.get("code") or "")


def error_texts(exc: BaseException, lang: str) -> List[str]:
    """The sentences of an ``ExtensionError`` / ``ProfileError`` (its report)."""
    report = getattr(exc, "report", None)
    errors = getattr(report, "errors", None) or []
    out = [p.text(lang) if hasattr(p, "text") else str(p) for p in errors]
    return out or [str(exc)]


# ── the overlay of a file ───────────────────────────────────────────────────

def declared_of(container: Any) -> List[Dict[str, Any]]:
    """The ``header.profiles`` a file declared (empty when none)."""
    header = getattr(container, "header", None) or {}
    out = header.get("profiles") if isinstance(header, Mapping) else None
    return [dict(x) for x in (out or []) if isinstance(x, Mapping)]


def active_overlay(declared: Any = None, installed: bool = True):
    """``(overlay, missing, problems, declared_names)``: the packages a file
    declares, activated, and with ``installed`` the newest version of every
    other package of this machine — EMStudio's ``active_overlay`` (W6), the same
    answer for the same file in the two tools."""
    P, _ = library()
    if P is None:
        return None, [], [], set()
    overlay, missing, problems = P.activate(declared or [])
    active = list(overlay)
    declared_names = {p.name for p in active}
    if installed:
        seen = set(declared_names)
        for row in P.installed(all_versions=False):
            name = str(row.get("name") or "")
            if not name or name in seen:
                continue
            p = P.find(name, row.get("version"), exact=True) or P.find(name)
            if p is not None:
                active.append(p)
                seen.add(name)
        overlay = P.ProfileOverlay(active)
    return overlay, list(missing or []), list(problems or []), declared_names


def _stamp() -> Tuple[float, float]:
    """When the machine's packages last changed (index and register): the
    cache of :func:`overlay_cached` is good until one of them moves."""
    P, X = library()
    out = []
    for path in ((P.profiles_dir() / P.INDEX_FILE) if P else None,
                 (X.extensions_dir() / X.REGISTER_FILE) if X else None):
        try:
            out.append(os.path.getmtime(path) if path else 0.0)
        except OSError:
            out.append(0.0)
    return tuple(out)  # type: ignore[return-value]


_cache: Dict[str, Any] = {}


def overlay_cached(declared: Any = None):
    """:func:`active_overlay` kept until the declared list or the machine's
    packages change — a panel draws many times a second, activating reads
    the disk."""
    key = json.dumps(declared or [], sort_keys=True, default=str)
    stamp = _stamp()
    hit = _cache.get(key)
    if hit is not None and hit[0] == stamp:
        return hit[1]
    value = active_overlay(declared)
    _cache.clear()           # one file at a time is drawn: keep only the last
    _cache[key] = (stamp, value)
    return value


def forget_cache() -> None:
    _cache.clear()


def missing_line(missing: Iterable[Mapping[str, Any]]) -> str:
    """«esempio-statuaria 0.1.0, ritratti-romani 0.2.0» — the packages a file
    declares that this machine has not."""
    out = []
    for m in missing or []:
        name = m.get("name") or str(m.get("iri") or "").rstrip("/").rsplit("/", 1)[-1] or "?"
        out.append(f"{name} {m.get('version') or ''}".strip())
    return ", ".join(out)


# ── the rows of the Preferences ─────────────────────────────────────────────

@dataclass
class PackageRow:
    id: str
    name: str
    version: str
    kind: str
    source: str
    data: str            # installed · absent
    code: str            # installed · not_installed · absent
    code_reason: Any = None           # the library's problem ({code, en, it}) or None
    hosts: List[str] = field(default_factory=list)
    registered: bool = True
    incomplete: bool = False
    used_by_file: bool = False
    vocabularies: List[str] = field(default_factory=list)


def package_rows(declared_names: Iterable[str] = ()) -> List[PackageRow]:
    """One row per installed package: the register's rows and the data-only
    packages the profile library installed on its own."""
    _, X = library()
    if X is None:
        return []
    used = set(declared_names or ())
    out = []
    for r in X.installed():
        data = r.get("data") or {}
        code = r.get("code") or {}
        reason = code.get("reason") or None
        name = str(r.get("name") or r.get("id") or "")
        out.append(PackageRow(
            id=str(r.get("id") or ""), name=name, version=str(r.get("version") or data.get("version") or ""),
            kind=str(r.get("kind") or ""), source=str(r.get("source") or ""),
            data=str(data.get("status") or "absent"), code=str(code.get("status") or "absent"),
            code_reason=reason, hosts=list(code.get("hosts") or []),
            registered=bool(r.get("registered", True)), incomplete=bool(r.get("incomplete")),
            used_by_file=str(r.get("id") or "") in used or name in used,
            vocabularies=[str(v.get("scheme") or v.get("id") or v) if isinstance(v, Mapping) else str(v)
                          for v in (data.get("vocabularies") or [])]))
    return out


# ── installing from disk ────────────────────────────────────────────────────

#: a confirmation line: (text, icon, level) — level ``info`` · ``warning`` · ``error``
Line = Tuple[str, str, str]


def code_for_blender(preview: Mapping[str, Any]) -> bool:
    """The archive has code that runs in Blender and could go in (W16)."""
    code = preview.get("code") or {}
    return bool(code.get("present")) and HOST in (code.get("hosts") or []) \
        and code.get("installable", True) and not code.get("module_collision")


def plan_install(preview: Mapping[str, Any], *, with_code: bool = False) -> Dict[str, Any]:
    """What «Install» does in EM Tools for this archive:

    * ``data`` — a package with data installs its data (``parts="data"``);
      its code, if any, is registered «not installed: the user's choice (data
      only)», and EMStudio (or EM Tools, later) can install it;
    * ``all`` — (W16) the person ticked «Install the code too»: the code runs
      in Blender (``hosts`` names it), so data and code go in
      (``parts="all"``, the trust question answered by the tick);
    * ``refuse`` — a plugin with no data whose code is not for Blender or was
      not ticked, or an archive with errors.
    """
    data = preview.get("data") or {}
    code = preview.get("code") or {}
    if preview.get("errors"):
        return {"action": "refuse", "why": "errors"}
    for_blender = code_for_blender(preview)
    if with_code and for_blender:
        return {"action": "all", "code_left_out": False, "code_for_blender": True}
    if not data.get("present"):
        return {"action": "refuse", "why": "plugin_needs_trust" if for_blender else "plugin_only",
                "code_for_blender": for_blender}
    if not data.get("installable", True):
        return {"action": "refuse", "why": "errors"}
    return {"action": "data", "code_left_out": bool(code.get("present")), "code_for_blender": for_blender}


def preview_lines(preview: Mapping[str, Any], lang: str, tr=lambda s: s) -> List[Line]:
    """The two panels of the confirmation as lines (SPEC-pacchetto §16.6):
    the head, the data (vocabularies with licence and tier, what the package
    adds), the code (unverified, from disk, every permission with its why —
    D-14 — and that EM Tools leaves it out), the errors in the library's words."""
    lines: List[Line] = []
    name = preview.get("name") or preview.get("id")
    lines.append((f"{name} · {preview.get('id')} {preview.get('version') or ''}".strip(), "PACKAGE", "info"))
    if preview.get("tagline"):
        lines.append((str(preview["tagline"]), "BLANK1", "info"))
    lic = preview.get("license")
    if lic:
        lines.append((tr("Licence: {lic}").format(lic=", ".join(lic) if isinstance(lic, list) else lic),
                      "BLANK1", "info"))
    data = preview.get("data") or {}
    if data.get("present"):
        s = data.get("summary") or {}
        lines.append((tr("Data {version}: no code, read by every EM tool").format(version=data.get("version") or ""),
                      "FILE", "info"))
        for v in s.get("vocabularies") or []:
            lines.append((tr("vocabulary {scheme} {version} · {license} · tier {tier}").format(
                scheme=v.get("scheme") or v.get("path") or "?", version=v.get("version") or "",
                license=v.get("license") or "?", tier=v.get("fascia") or "?"), "BLANK1", "info"))
        counts = [(s.get("qualia"), tr("qualia")), (s.get("extractors"), tr("extractors")),
                  (s.get("landmark_sets"), tr("landmark sets")), (s.get("combiners"), tr("combiners")),
                  (s.get("forms"), tr("sheets")), (s.get("color_schemes"), tr("colour schemes"))]
        said = ", ".join(f"{n} {what}" for n, what in counts if n)
        if said:
            lines.append((said, "BLANK1", "info"))
        if s.get("primitives"):
            lines.append((tr("primitives: {p}").format(p=", ".join(s["primitives"])), "BLANK1", "info"))
        if data.get("update") == "unchanged":
            lines.append((tr("Already installed, identical: nothing changes"), "CHECKMARK", "info"))
        elif data.get("beside"):
            lines.append((problem_text(data["beside"], lang), "INFO", "warning"))
    code = preview.get("code") or {}
    if code.get("present"):
        lines.append((tr("Code {version}: NOT VERIFIED, from disk").format(version=code.get("version") or ""),
                      "SCRIPT", "warning"))
        for perm, why in sorted((code.get("permissions") or {}).items()):
            lines.append((f"{perm} — «{why}»", "BLANK1", "warning"))
        if code.get("hosts"):
            lines.append((tr("runs in: {hosts}").format(hosts=", ".join(code["hosts"])), "BLANK1", "info"))
        if code_for_blender(preview):
            if code.get("trust_needed", True):
                lines.append((tr("A Python plugin has the powers of your user: tick «Install the code too» "
                                 "only if you trust it"), "INFO", "warning"))
            else:
                lines.append((tr("Same permissions, capabilities and source as the last trust: "
                                 "no new question"), "CHECKMARK", "info"))
        else:
            lines.append((tr("The code does not run in Blender: EM Tools installs the data only "
                             "(EMStudio can install the code)"), "INFO", "warning"))
    for p in preview.get("errors") or []:
        lines.append((problem_text(p, lang), "ERROR", "error"))
    for p in (preview.get("requires") or {}).get("missing") or []:
        lines.append((problem_text(p, lang), "ERROR", "warning"))
    for p in preview.get("warnings") or []:
        lines.append((problem_text(p, lang), "INFO", "warning"))
    return lines


def install_data(source: Any) -> Dict[str, Any]:
    """Install the data of an archive (folder, zip): ``extensions.install(...,
    parts="data")``. Raises ``ExtensionError`` (nothing written) like the
    library; a plugin with no data is refused before."""
    _, X = library()
    if X is None:
        raise RuntimeError("the bundled s3dgraphy has no extensions (older than dev117)")
    pv = X.preview(source)
    plan = plan_install(pv)
    if plan["action"] != "data":
        if plan["why"] in ("plugin_only", "plugin_needs_trust"):
            raise ValueError(plan["why"])
        raise X.ExtensionError("; ".join(problem_text(p, "en") for p in pv.get("errors") or []) or "not installable")
    return X.install(source, parts="data")


def install_with_code(source: Any) -> Dict[str, Any]:
    """(W16) Data and code, the trust question answered by the person's tick:
    ``extensions.install(..., parts="all", trust=True)`` — the code becomes the
    active version (``enabled.json``), for EMStudio too where ``hosts`` says so."""
    _, X = library()
    if X is None:
        raise RuntimeError("the bundled s3dgraphy has no extensions (older than dev117)")
    pv = X.preview(source)
    plan = plan_install(pv, with_code=True)
    if plan["action"] != "all":
        if plan.get("why") == "plugin_only":
            raise ValueError("plugin_only")
        raise X.ExtensionError("; ".join(problem_text(p, "en") for p in pv.get("errors") or []) or "not installable")
    return X.install(source, parts="all", trust=True)


def active_code_ids() -> List[str]:
    """The ids whose code is active (``enabled.json``), whatever the host."""
    _, X = library()
    try:
        return [str(e.get("id")) for e in X.active_code()]
    except Exception:  # noqa: BLE001
        return []


def set_code_active(eid: str, active: bool) -> Dict[str, Any]:
    """Enable or disable an installed code (for every EM tool of this computer:
    ``enabled.json`` is one, and each host loads the codes for it)."""
    _, X = library()
    if active:
        return X.enable(eid)
    return {"disabled": bool(X.disable(eid))}


def remove_package(eid: str, *, purge_vocabularies: bool = False) -> Dict[str, Any]:
    """*Remove the package*: code, then data; the vocabularies stay unless asked
    (D-19). A data-only package the profile library installed by itself (no
    row in the register) is removed from the packages' folder."""
    P, X = library()
    if X is None:
        raise RuntimeError("the bundled s3dgraphy has no extensions")
    reg = (X.read_register().get("extensions") or {})
    if eid in reg:
        return X.remove(eid, confirm=True, purge_vocabularies=purge_vocabularies)
    removed = P.remove(eid)
    return {"id": eid, "data_removed": removed, "vocabularies": None}


def vocabularies_only_here(eid: str) -> List[str]:
    """The vocabularies nobody but this package brings (the unticked box)."""
    _, X = library()
    try:
        plan = X.removal_plan(eid)
    except Exception:  # noqa: BLE001 — not in the register
        return []
    return [str(v.get("id") or v.get("scheme") or v) if isinstance(v, Mapping) else str(v)
            for v in plan.get("vocabularies_only_here") or []]


# ── colour schemes ──────────────────────────────────────────────────────────

def _hex_to_linear(value: str) -> Tuple[float, float, float]:
    try:
        from s3dgraphy.color_schemes import hex_to_linear
        return tuple(hex_to_linear(value))  # type: ignore[return-value]
    except Exception:  # noqa: BLE001 — an older wheel: the same formula (γ 2.2)
        v = value.lstrip("#")
        return tuple(round((int(v[i:i + 2], 16) / 255.0) ** 2.2, 6) for i in (0, 2, 4))  # type: ignore


def term_label(code: str, lang: str) -> Optional[str]:
    """The label of a vocabulary's term in ``lang`` from the vocabularies
    installed here (any language as a fallback); None when no installed
    vocabulary has the code."""
    try:
        from s3dgraphy.authorities import packages as pk
    except Exception:  # noqa: BLE001
        return None
    try:
        found = pk.concept_of(code)
    except Exception:  # noqa: BLE001
        return None
    if not found:
        return None
    concept = found[1]
    hit = pk.label_in(concept, lang) or pk.label_in(concept, "en")
    if hit:
        return hit[0]
    pref = concept.get("pref") or {}
    return next(iter(pref.values()), None)


def _tail(code: str) -> str:
    return code.rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1] or code


def package_scheme_as_emc(doc: Mapping[str, Any], property_name: str, lang: str,
                          source: str = "") -> Optional[Dict[str, Any]]:
    """A package's colour scheme as EM Tools' .emc: ``color_mapping`` keyed by
    the LABEL of each term in ``lang`` (from the installed vocabulary, else the
    code's last segment) in linear colours, and ``metadata.value_codes`` label →
    code, so a value carrying that code takes the colour whatever its label
    says. An .emc already in EM Tools' form is taken as it is. None: not a
    scheme."""
    if not isinstance(doc, Mapping):
        return None
    meta = doc.get("metadata")
    mapping = doc.get("color_mapping")
    if isinstance(meta, Mapping) and isinstance(meta.get("property_name"), str) and isinstance(mapping, Mapping):
        return {"metadata": dict(meta), "color_mapping": dict(mapping)}
    if not isinstance(mapping, Mapping):
        return None
    out_map: Dict[str, List[float]] = {}
    codes: Dict[str, str] = {}
    for key, colour in mapping.items():
        if not isinstance(colour, str) or len(colour.lstrip("#")) != 6:
            continue
        try:
            rgb = _hex_to_linear(colour)
        except ValueError:
            continue
        key = str(key)
        if "://" in key:
            label = term_label(key, lang) or _tail(key)
            while label in out_map and codes.get(label) != key:
                label = f"{label} ·"
            codes[label] = key
        else:
            label = key
        out_map[label] = [float(rgb[0]), float(rgb[1]), float(rgb[2]), 1.0]
    if not out_map:
        return None
    return {"metadata": {"property_name": property_name or str(doc.get("property") or ""),
                         "description": f"Color mapping for {property_name} values",
                         "value_codes": codes, "source": source},
            "color_mapping": out_map}


def package_schemes(overlay: Any, lang: str) -> List[Dict[str, Any]]:
    """The colour schemes of the active packages: ``{id, name, property,
    profile, emc, problem}`` — ``emc`` None when the file is not a scheme
    (said, never guessed)."""
    if not overlay:
        return []
    from s3dgraphy.profiles import pick_label
    out = []
    for sid, entry in sorted(overlay.color_schemes().items()):
        doc, problem = None, None
        path = entry.get("file")
        try:
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, TypeError, ValueError) as exc:
            problem = f"not read: {exc}"
        prop = str(entry.get("property") or (doc or {}).get("property") or "")
        emc = package_scheme_as_emc(doc, prop, lang, source=str(entry.get("origin") or sid)) if doc else None
        if doc is not None and emc is None:
            problem = "not a colour scheme"
        name = pick_label(entry.get("label"), lang) or (doc or {}).get("name") or sid
        out.append({"id": sid, "name": str(name), "property": prop, "profile": entry.get("profile") or "",
                    "origin": entry.get("origin") or "", "emc": emc, "problem": problem})
    return out


def property_names(graph: Any, property_id: str, overlay: Any = None) -> List[str]:
    """The NAMES the property nodes of a quale carry in this graph, most used
    first: a package's quale is written with its label as the name and the
    prefixed id as ``property_type`` (EMStudio W6, choice 7), so a scheme for
    ``stat:fase_di_superficie`` finds «Fase della superficie» — and a node
    named with the id is found too."""
    labels = set()
    if overlay:
        try:
            _, entry = overlay.find(property_id)
        except Exception:  # noqa: BLE001
            entry = None
        lab = (entry or {}).get("label")
        if isinstance(lab, Mapping):
            labels.update(str(v) for v in lab.values())
        elif isinstance(lab, str):
            labels.add(lab)
    counts: Dict[str, int] = {}
    for n in getattr(graph, "nodes", []) or []:
        if getattr(n, "node_type", None) != "property":
            continue
        name = str(getattr(n, "name", "") or "")
        data = getattr(n, "data", None) or {}
        ptype = str(data.get("property_type") or getattr(n, "property_type", "") or "")
        if ptype == property_id or name == property_id or (name and name in labels):
            counts[name] = counts.get(name, 0) + 1
    return [k for k, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


# ── vocabularies ────────────────────────────────────────────────────────────

def package_vocabularies(overlay: Any, lang: str) -> List[Dict[str, Any]]:
    """The vocabularies the active packages control their qualia with:
    ``{property, label, scheme, version, installed, installed_version,
    concepts, profile}`` — whether this machine has them (the vocabulary
    manager's folder, the one EMStudio's «Vocabularies…» fills)."""
    if not overlay:
        return []
    from s3dgraphy.profiles import pick_label
    try:
        from s3dgraphy.authorities import packages as pk
    except Exception:  # noqa: BLE001
        pk = None
    out = []
    for q in overlay.qualia_vocabularies():
        scheme = str(q.get("scheme") or "")
        version = str(q.get("version") or "")
        found = []
        if pk is not None and scheme:
            try:
                found = pk.find_installed(scheme)
            except Exception:  # noqa: BLE001
                found = []
        have = None
        concepts = None
        for folder, m in found:
            if str(m.get("version") or "") == version or have is None:
                have = m
                try:
                    idx = pk.vocab_index(m.get("id"), m.get("version"))
                    concepts = len((idx or {}).get("concepts") or {})
                except Exception:  # noqa: BLE001
                    concepts = None
        out.append({"property": str(q.get("property_type") or ""),
                    "label": pick_label(q.get("label"), lang) or str(q.get("property_type") or ""),
                    "scheme": scheme, "version": version, "installed": have is not None,
                    "installed_version": str((have or {}).get("version") or ""),
                    "concepts": concepts, "profile": q.get("profile") or ""})
    return out


# ── the AnnotationRegion chain, read (G14) ──────────────────────────────────

def scene_to_blender(p: Sequence[float]) -> Tuple[float, float, float]:
    """The scene's glTF frame (Y-up) → Blender's world (Z-up): the conversion
    of ``scene_space`` (kept here too so this module reads alone)."""
    x, y, z = (float(v) for v in p)
    return (x, -z, y)


@dataclass
class ChainPlace:
    """One extractor and the place it read, as EM Tools reads it."""
    extractor_id: str
    name: str
    label: str
    kind: str                         # point · line · polyline · surface
    coords: List[List[float]]         # the scene's frame (glTF, Y-up)
    blender: List[Tuple[float, float, float]]
    region_id: str = ""
    on_id: str = ""                   # the model the place is on
    em_kind: str = ""
    landmark: Dict[str, Any] = field(default_factory=dict)
    source: str = "chain"             # chain · attributes (EM Tools' own x/y/z)
    area: Optional[float] = None
    perimeter: Optional[float] = None

    def as_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def _data(node: Any) -> Dict[str, Any]:
    d = getattr(node, "data", None)
    return d if isinstance(d, dict) else {}


def _label_of(ex: Any, overlay: Any, lang: str) -> str:
    data = _data(ex)
    lm = data.get("landmark") if isinstance(data.get("landmark"), Mapping) else {}
    if lm.get("label"):
        return str(lm["label"])
    kind = data.get("em_kind")
    if kind and overlay:
        try:
            lab = overlay.label(kind, lang)
        except Exception:  # noqa: BLE001
            lab = None
        if lab:
            return f"{getattr(ex, 'name', '') or ''} · {lab}".strip(" ·")
    return str(getattr(ex, "name", "") or getattr(ex, "node_id", ""))


def chain_places(graph: Any, kinds: Iterable[str] = ("point",), overlay: Any = None,
                 lang: str = "en") -> Tuple[List[ChainPlace], List[Dict[str, str]]]:
    """The extractors of the graph whose place is an AnnotationRegion of one of
    ``kinds`` with its vertices in the node (``data.coords``): ``(places,
    skipped)`` — skipped: a region whose vertices are in a .glb (above
    ``coords.inline_max_vertices``), said rather than read."""
    want = set(kinds)
    regions: Dict[str, Any] = {}
    for n in getattr(graph, "nodes", []) or []:
        if getattr(n, "node_type", None) == "annotation_region":
            regions[n.node_id] = n
    place_of: Dict[str, str] = {}
    on_of: Dict[str, str] = {}
    for e in getattr(graph, "edges", []) or []:
        if e.edge_type == "extracted_from" and e.edge_target in regions:
            place_of[e.edge_source] = e.edge_target
        elif e.edge_type == "is_on_resource" and e.edge_source in regions:
            on_of[e.edge_source] = e.edge_target
    places: List[ChainPlace] = []
    skipped: List[Dict[str, str]] = []
    for ex_id, rid in place_of.items():
        ex = graph.find_node_by_id(ex_id)
        if ex is None or getattr(ex, "node_type", None) != "extractor":
            continue
        region = regions[rid]
        rd = _data(region)
        kind = str(rd.get("geometry_kind") or getattr(region, "geometry_kind", "") or "")
        if kind not in want:
            continue
        coords = rd.get("coords") or []
        if not coords:
            skipped.append({"extractor_id": ex_id, "region_id": rid,
                            "reason": "no coords in the node (vertices in a .glb resource)"})
            continue
        try:
            pts = [[float(c) for c in p][:3] for p in coords]
        except (TypeError, ValueError):
            skipped.append({"extractor_id": ex_id, "region_id": rid, "reason": "coords not numbers"})
            continue
        data = _data(ex)
        places.append(ChainPlace(
            extractor_id=ex_id, name=str(getattr(ex, "name", "") or ex_id),
            label=_label_of(ex, overlay, lang), kind=kind, coords=pts,
            blender=[scene_to_blender(p) for p in pts], region_id=rid, on_id=on_of.get(rid, ""),
            em_kind=str(data.get("em_kind") or ""),
            landmark=dict(data.get("landmark") or {}) if isinstance(data.get("landmark"), Mapping) else {},
            area=rd.get("area"), perimeter=rd.get("perimeter")))
    places.sort(key=lambda p: (p.label.lower(), p.extractor_id))
    return places, skipped


def _xyz(ex: Any) -> Optional[Tuple[float, float, float]]:
    for src in (getattr(ex, "attributes", None) or {}, _data(ex)):
        try:
            return (float(src["x"]), float(src["y"]), float(src["z"]))
        except (KeyError, TypeError, ValueError):
            continue
    return None


def attribute_points(graph: Any) -> List[ChainPlace]:
    """EM Tools' own form of a measured point: an extractor with ``x/y/z`` in
    its attributes (Proxy Box, ``purpose: proxy_box_creator``), already in
    Blender's world. The other representation of the same act (G14)."""
    out = []
    for n in getattr(graph, "nodes", []) or []:
        if getattr(n, "node_type", None) != "extractor":
            continue
        p = _xyz(n)
        if p is None:
            continue
        attrs = getattr(n, "attributes", None) or {}
        name = str(getattr(n, "name", "") or n.node_id)
        what = attrs.get("point_type") or _data(n).get("point_type")
        out.append(ChainPlace(extractor_id=n.node_id, name=name,
                              label=f"{name} · {what}" if what else name, kind="point",
                              coords=[list(_blender_to_scene(p))], blender=[p], source="attributes"))
    out.sort(key=lambda p: (p.label.lower(), p.extractor_id))
    return out


def _blender_to_scene(p: Sequence[float]) -> Tuple[float, float, float]:
    x, y, z = (float(v) for v in p)
    return (x, z, -y)


def measured_points(graph: Any, overlay: Any = None, lang: str = "en") -> List[ChainPlace]:
    """Every measured point of the graph, in the two forms: the chain first
    (EMStudio, a package's canonical points), then EM Tools' x/y/z — an
    extractor that has both is read from the chain."""
    chain, _ = chain_places(graph, ("point",), overlay, lang)
    seen = {p.extractor_id for p in chain}
    return chain + [p for p in attribute_points(graph) if p.extractor_id not in seen]


def position_of(graph: Any, extractor_id: str) -> Optional[Tuple[Tuple[float, float, float], str]]:
    """``(position in Blender's world, source)`` of one extractor's point — the
    chain first, else its x/y/z — or None."""
    for p in measured_points(graph):
        if p.extractor_id == extractor_id:
            return p.blender[0], p.source
    return None


def surfaces(graph: Any, overlay: Any = None, lang: str = "en") -> List[ChainPlace]:
    """The surfaces placed on the models (``geometry_kind: surface``, a closed
    ring): what the Areale can be made from."""
    return chain_places(graph, ("surface",), overlay, lang)[0]


def ring_centroid(points: Sequence[Sequence[float]]) -> Tuple[float, float, float]:
    n = max(len(points), 1)
    return tuple(sum(float(p[i]) for p in points) / n for i in range(3))  # type: ignore[return-value]


def ring_problem(points: Sequence[Sequence[float]]) -> Optional[str]:
    """Why a ring cannot become an areale, or None: at least three distinct
    vertices, not all on one line."""
    pts = [tuple(float(c) for c in p) for p in points]
    distinct = list(dict.fromkeys(pts))
    if len(distinct) < 3:
        return "fewer than three distinct vertices"
    a = distinct[0]
    for i in range(1, len(distinct)):
        for j in range(i + 1, len(distinct)):
            b, c = distinct[i], distinct[j]
            u = [b[k] - a[k] for k in range(3)]
            v = [c[k] - a[k] for k in range(3)]
            cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            if sum(x * x for x in cross) > 1e-18:
                return None
    return "all the vertices on one line"


# ── the declared combiners (W4), computed here too ──────────────────────────

def measure_targets(graph: Any) -> List[Tuple[Optional[str], Optional[str]]]:
    """``[(model, subject)]`` where points were placed: every act of placing a
    landmark set (its CombinerNode's ``data.landmark_pose``), and every model
    a canonical point is on when no act names it."""
    out: List[Tuple[Optional[str], Optional[str]]] = []
    for n in getattr(graph, "nodes", []) or []:
        pose = _data(n).get("landmark_pose")
        if getattr(n, "node_type", None) == "combiner" and isinstance(pose, Mapping):
            key = (pose.get("on"), pose.get("subject"))
            if key not in out:
                out.append(key)
    named = {on for on, _ in out}
    for p in chain_places(graph, ("point",))[0]:
        if p.landmark and p.on_id and p.on_id not in named and (p.on_id, None) not in out:
            out.append((p.on_id, None))
    return out


def compute_measures(graph: Any, overlay: Any, author: Optional[str] = None) -> Tuple[int, int]:
    """``annotation.combiners.compute_available`` on every model with placed
    points: ``(computed, waiting for points)``. The same PropertyNode and
    CombinerNode EMStudio writes (idempotent ids): computing twice changes
    nothing."""
    from s3dgraphy.annotation.combiners import compute_available
    done = waiting = 0
    for on_id, subject in measure_targets(graph):
        r = compute_available(graph, overlay, on_id, subject=subject, author=author)
        done += len(r.get("computed") or [])
        waiting += len(r.get("missing") or {})
    return done, waiting
