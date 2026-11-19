"""EM Tools, a client of the repositories — MICRO-PL26, row X6 of the extensions plan (E.D., 18-19 Nov 2026).

The Preferences of EM Tools read the SAME repositories EMStudio reads (the
machine's ``~/.s3dgraphy/extensions/repositories.json``, written by
``s3dgraphy.extensions.remote``, X2): a repository added in one tool is in
the other, an index read in one is read for both, an extension installed
from a repository by one is installed for both. Nothing here re-implements
the client: the index, the archive checked against ``archive_hash``, the
``blocklist``, ``[requires]``, tier C, «Update all», the reviews (X1–X4) are
the library's. What is EM Tools' own:

* **what Blender is offered**: the community packages (every archive with
  data) and the plugins whose code names ``blender`` in ``hosts`` — a plugin
  for EMStudio only is not listed, it is counted («n plugins for EMStudio
  only»); a mixed package whose code is not for Blender installs its data
  (PL12's rule, unchanged);
* **Blender's own switch**: with Blender's «Allow Online Access» off
  (``bpy.app.online_access``) EM Tools does not go online even when the
  machine's switch is on — :func:`respect_blender` sets
  ``S3DGRAPHY_ONLINE_ACCESS=0`` in THIS process only (the machine's switch
  is not touched, EMStudio is not affected); ``file://`` works all the same;
* **the plan, said as lines** of the confirmation (from which repository,
  the archive the index names, what installs first, what nobody offers, the
  optional offers, tier C, a cycle);
* **the trust of the requirements**: their code goes in with the person's
  tick only when every one of them runs in Blender (the tick answers for
  what EM Tools runs; another code is left for EMStudio);
* **«Update all» from Blender**: the updates whose code would ask the trust
  again are trusted with one tick only when their code runs in Blender; the
  others wait for EMStudio («update it in EMStudio»).

No ``bpy`` here: measured with pytest. The panels and the operators are in
``ui.py`` / ``repo_operators.py``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from . import core

HOST = core.HOST

#: set when EM Tools itself turned the network off for Blender's switch (the
#: value of the environment before, to give it back)
_SENTINEL = object()
_env_before: Any = _SENTINEL


# ── the library, as the bundled wheel has it ────────────────────────────────

def library():
    """``s3dgraphy.extensions`` when it is a client of repositories (X2,
    after dev124), else None: the Preferences say so instead of failing."""
    _, X = core.library()
    if X is None or not hasattr(X, "install_from") or not hasattr(X, "check_updates"):
        return None
    return X


def available() -> bool:
    return library() is not None


def problem_text(p: Any, lang: str) -> str:
    return core.problem_text(p, lang)


# ── Blender's «Allow Online Access» ─────────────────────────────────────────

def respect_blender(blender_online: Optional[bool]) -> bool:
    """Blender's switch over ours, in this process: off → the library's
    ``S3DGRAPHY_ONLINE_ACCESS`` is ``0`` (the environment wins over the
    machine's switch); on again → the environment as it was. ``None`` (a
    Blender without the switch): nothing changes. Returns whether EM Tools
    may go online now."""
    global _env_before
    X = library()
    env = getattr(X, "ONLINE_ENV", "S3DGRAPHY_ONLINE_ACCESS") if X else "S3DGRAPHY_ONLINE_ACCESS"
    if blender_online is False:
        if _env_before is _SENTINEL:
            _env_before = os.environ.get(env)
        os.environ[env] = "0"
    elif _env_before is not _SENTINEL:
        if _env_before is None:
            os.environ.pop(env, None)
        else:
            os.environ[env] = _env_before
        _env_before = _SENTINEL
    return bool(X.online_access()) if X else False


def blocked_by_blender() -> bool:
    """EM Tools turned the network off because Blender's switch is off."""
    return _env_before is not _SENTINEL


def online_state() -> Dict[str, Any]:
    """``{on, setting, env, blender_off}``: what the switch row draws."""
    X = library()
    if X is None:
        return {"on": False, "setting": False, "env": None, "blender_off": False}
    out = dict(X.online_access_setting())
    out["blender_off"] = blocked_by_blender()
    if out["blender_off"]:
        out["env"] = None          # it is Blender's, said as Blender's
    return out


# ── what is offered to Blender ──────────────────────────────────────────────

def _index_entry(repo: str, eid: str, version: Optional[str] = None) -> Dict[str, Any]:
    X = library()
    idx = (X.cached_index(repo) if X else None) or {}
    for e in idx.get("data") or []:
        if isinstance(e, Mapping) and e.get("id") == eid and (version is None or str(e.get("version")) == version):
            return dict(e)
    return {}


def code_hosts(sections: Mapping[str, Any]) -> List[str]:
    code = (sections or {}).get("code") or {}
    return [str(h) for h in code.get("hosts") or []]


def for_blender(sections: Mapping[str, Any]) -> str:
    """What an entry (its index ``sections``) is for EM Tools: ``data`` (data,
    no code), ``mixed`` (data, and a code that runs in Blender), ``data_only``
    (data, a code for other hosts: the data come in), ``code`` (a plugin for
    Blender), ``elsewhere`` (a plugin for other hosts: not listed)."""
    secs = sections or {}
    has_data, has_code = "data" in secs, "code" in secs
    runs = HOST in code_hosts(secs)
    if has_data and not has_code:
        return "data"
    if has_data:
        return "mixed" if runs else "data_only"
    return "code" if runs else "elsewhere"


@dataclass
class Offer:
    repo: str
    id: str
    name: str
    version: str
    kind: str                       # for_blender()
    type: str = ""
    tagline: str = ""
    installed: Optional[str] = None
    update: bool = False
    same_source: bool = False
    verified: bool = False
    reviewed: Any = None
    versions: List[str] = field(default_factory=list)


def offers() -> Dict[str, Any]:
    """What the repositories offer this Blender, updates first, then the
    rest by name: ``{offers: [Offer], elsewhere: n, blocked: [problem],
    other_platforms: [problem], online_access}``. Read from the cached
    indexes only: nothing goes to the network here."""
    X = library()
    if X is None:
        return {"offers": [], "elsewhere": 0, "blocked": [], "other_platforms": [], "online_access": False}
    got = X.available()
    out: List[Offer] = []
    elsewhere = 0
    for a in got.get("available") or []:
        kind = for_blender(a.get("sections") or {})
        if kind == "elsewhere":
            elsewhere += 1
            continue
        name = a.get("name")
        if isinstance(name, Mapping):
            name = name.get("en") or next(iter(name.values()), "")
        out.append(Offer(repo=str(a["repo"]), id=str(a["id"]), name=str(name or a["id"]),
                         version=str(a.get("version") or ""), kind=kind, type=str(a.get("type") or ""),
                         tagline=str(a.get("tagline") or ""), installed=a.get("installed"),
                         update=bool(a.get("update")), same_source=bool(a.get("same_source")),
                         verified=bool(a.get("verified")), reviewed=a.get("reviewed"),
                         versions=list(a.get("versions") or [])))
    out.sort(key=lambda o: (not o.update, o.installed is not None and not o.update, o.name.lower(), o.repo))
    return {"offers": out, "elsewhere": elsewhere,
            "blocked": [b["problem"] for b in got.get("blocked") or []],
            "other_platforms": [b["problem"] for b in got.get("other_platforms") or []],
            "online_access": bool(got.get("online_access"))}


def _stamp() -> Tuple[float, ...]:
    """When what the offers are made of last changed: the repositories, their
    cached indexes, the register."""
    X = library()
    if X is None:
        return ()
    base = X.extensions_dir()
    paths = [base / "repositories.json", base / X.REGISTER_FILE]
    repos = base / "repos"
    try:
        paths += sorted(p / "sync.json" for p in repos.iterdir() if p.is_dir())
    except OSError:
        pass
    out = []
    for p in paths:
        try:
            out.append(os.path.getmtime(p))
        except OSError:
            out.append(0.0)
    return tuple(out) + (float(os.environ.get(getattr(X, "ONLINE_ENV", ""), "") == "0"),)


_cache: Dict[str, Any] = {}


def offers_cached() -> Dict[str, Any]:
    """:func:`offers` kept until a repository, an index or the register moves
    (the Preferences draw many times a second)."""
    stamp = _stamp()
    hit = _cache.get("offers")
    if hit is not None and hit[0] == stamp:
        return hit[1]
    value = offers()
    _cache["offers"] = (stamp, value)
    return value


def forget_cache() -> None:
    _cache.clear()


def repositories() -> List[Dict[str, Any]]:
    X = library()
    return list(X.repositories()) if X else []


# ── adding a repository ─────────────────────────────────────────────────────

def add_and_read(url: str, *, name: str = "", token: str = "", check_on_startup: bool = False) -> Dict[str, Any]:
    """*Add repository*: added (the library checks the address and the name),
    then read once — as EMStudio does. Returns ``{repository, sync}``; the
    reading's problems are in ``sync`` (a repository that cannot be read yet
    stays added, its problem said)."""
    X = library()
    if X is None:
        raise RuntimeError("the bundled s3dgraphy has no repositories (older than dev125)")
    r = X.add_repository(url.strip(), name=name.strip() or None, token=token or None,
                         check_on_startup=check_on_startup)
    forget_cache()
    res = X.sync(r["name"])
    forget_cache()
    return {"repository": r, "sync": res}


def sync_lines(res: Mapping[str, Any], lang: str, tr: Callable[[str], str] = lambda s: s) -> List[str]:
    """One line per repository read: entries, or the problem in the library's words."""
    out = []
    for r in res.get("repositories") or []:
        if r.get("ok"):
            out.append(tr("{name}: {n} entries read").format(name=r["name"], n=r.get("entries") or 0))
        else:
            probs = r.get("problems") or []
            out.append(f"{r['name']}: " + ("; ".join(problem_text(p, lang) for p in probs[:2]) or "?"))
    return out


# ── installing from a repository ────────────────────────────────────────────

def preview(repo: str, eid: str, version: Optional[str] = None) -> Dict[str, Any]:
    """The two panels for an entry, the archive downloaded and checked first
    (``preview_from``), with its plan and whether each requirement's code runs
    in Blender."""
    X = library()
    pv = X.preview_from(repo, eid, version)
    for st in (pv.get("plan") or {}).get("steps") or []:
        e = _index_entry(st["repo"], st["id"], st["version"])
        st["hosts"] = code_hosts(e.get("sections") or {})
    return pv


def trust_requires(pv: Mapping[str, Any], with_code: bool) -> bool:
    """The tick answers for the requirements' code too (EMStudio's choice 13
    of PL22) — in EM Tools only when every requirement with code runs in
    Blender: the tick is a trust in what Blender runs."""
    if not with_code:
        return False
    for st in (pv.get("plan") or {}).get("steps") or []:
        if st.get("requested") or "code" not in (st.get("sections") or []):
            continue
        if HOST not in (st.get("hosts") or []):
            return False
    return True


def plan_lines(pv: Mapping[str, Any], lang: str, tr: Callable[[str], str] = lambda s: s) -> List[core.Line]:
    """The plan under the two panels: the archive the index names, what is
    installed first (and with code), what nobody offers, the optional offers,
    tier C, a cycle."""
    lines: List[core.Line] = []
    rp = pv.get("repository") or {}
    plan = pv.get("plan") or {}
    if rp:
        h = str(rp.get("archive_hash") or "")
        lines.append((tr("The archive is the one the index of {repo} names ({hash})").format(
            repo=rp.get("name") or "?", hash=h[:20] + ("…" if len(h) > 20 else "")), "LOCKED", "info"))
    if plan.get("cycle"):
        lines.append((tr("The requirements go round in a circle: {cycle}").format(
            cycle=" → ".join(plan["cycle"])), "ERROR", "error"))
    first = [s for s in plan.get("steps") or [] if not s.get("requested")]
    if first:
        lines.append((tr("Installed first, because it requires them:"), "SORTSIZE", "info"))
        for s in first:
            text = f"{s.get('name') or s['id']} {s['version']} · {tr('from {repo}').format(repo=s['repo'])}"
            if "code" in (s.get("sections") or []):
                text += " · " + (tr("with code that runs in Blender, not verified") if HOST in (s.get("hosts") or [])
                                 else tr("with code for {hosts}: left for EMStudio").format(
                                     hosts=", ".join(s.get("hosts") or []) or "?"))
            lines.append((text, "BLANK1", "info"))
    for u in plan.get("unresolved") or []:
        lines.append((problem_text(u.get("problem") or {}, lang) or u.get("id"), "ERROR", "warning"))
    for o in plan.get("offers") or []:
        where = tr("from {repo}").format(repo=o["repo"]) if o.get("repo") else tr("no repository has it")
        lines.append((tr("Offers {id} {range} (optional, not installed): {where}").format(
            id=o["id"], range=o.get("range") or "", where=where), "INFO", "info"))
    for t in plan.get("tier_c") or []:
        if t.get("will_fetch"):
            lines.append((tr("Tier C vocabulary {scheme}: downloaded to this computer from {url}").format(
                scheme=t.get("scheme") or "?", url=t.get("url") or "?"), "URL", "warning"))
        else:
            lines.append((tr("Tier C vocabulary {scheme}: not downloaded now («Download locally» later)").format(
                scheme=t.get("scheme") or "?"), "URL", "warning"))
    return lines


def install(repo: str, eid: str, version: Optional[str], pv: Mapping[str, Any], *, with_code: bool) -> Dict[str, Any]:
    """Install (or update) an entry the way EM Tools' confirmation said:
    ``core.plan_install`` decides data or all (a code not for Blender stays
    out, as from disk); the trust passed only when the code asks for it (a
    reviewed code, or one with the same permissions, capabilities and source,
    goes in without); the requirements' code with :func:`trust_requires`."""
    X = library()
    plan = core.plan_install(pv, with_code=with_code)
    if (pv.get("plan") or {}).get("cycle"):
        plan = {"action": "refuse", "why": "cycle"}
    if plan["action"] not in ("data", "all"):
        raise ValueError(plan.get("why") or "errors")
    code = pv.get("code") or {}
    trust = plan["action"] == "all" and bool(code.get("trust_needed", True))
    ans = X.install_from(repo, eid, pv.get("version") or version,
                         parts="all" if plan["action"] == "all" else "data", trust=trust,
                         trust_requires=trust_requires(pv, plan["action"] == "all"))
    forget_cache()
    core.forget_cache()
    ans["action"] = plan["action"]
    ans["code_left_out"] = bool(plan.get("code_left_out"))
    return ans


def install_lines(ans: Mapping[str, Any], lang: str, tr: Callable[[str], str] = lambda s: s) -> List[str]:
    """What an installation from a repository did, one line each (the report and the console)."""
    top = ans.get("installed") or {}
    out = []
    for r in ans.get("requires") or []:
        out.append(tr("Installed first: {id} {version} from {repo}").format(
            id=r.get("id"), version=r.get("version") or "", repo=r.get("repo")))
    for t in ans.get("tier_c") or []:
        if t.get("fetched"):
            out.append(tr("Tier C vocabulary {scheme}: downloaded").format(scheme=t.get("id")))
    for w in ans.get("warnings") or []:
        out.append(problem_text(w, lang))
    if top.get("incomplete"):
        out.append(tr("incomplete: a required package is missing"))
    return out


# ── «Update all» from Blender ───────────────────────────────────────────────

@dataclass
class Update:
    repo: str
    id: str
    installed: str
    version: str
    trust_needed: bool = False
    trust_changes: List[str] = field(default_factory=list)
    for_blender: bool = True        # the new code runs in Blender (or there is no code to ask about)
    verified: bool = False
    code_left_out: bool = False


def updates(*, read: bool = False) -> List[Update]:
    """What «Update all» would do, said before (``check_updates``): each
    update with whether it asks the trust again, and whether its code runs in
    Blender (the tick of EM Tools can answer only for those)."""
    X = library()
    if X is None:
        return []
    out = []
    for u in X.check_updates(read=read)["updates"]:
        e = _index_entry(u["repo"], u["id"], u["version"])
        secs = e.get("sections") or {}
        out.append(Update(repo=u["repo"], id=u["id"], installed=str(u.get("installed") or ""),
                          version=str(u["version"]), trust_needed=bool(u.get("trust_needed")),
                          trust_changes=list(u.get("trust_changes") or []),
                          for_blender="code" not in secs or HOST in code_hosts(secs),
                          verified=bool(u.get("verified")), code_left_out=bool(u.get("code_left_out"))))
    forget_cache()
    return out


def update_all(*, trust_blender: bool = False) -> Dict[str, Any]:
    """«Update all»: the library's, with ``trust`` = the updates that ask the
    trust again AND run in Blender, when the person ticked it. The others
    that ask wait (``needs_trust``); one that fails does not stop the rest."""
    X = library()
    ups = updates()
    trust = [u.id for u in ups if u.trust_needed and u.for_blender] if trust_blender else []
    res = X.update_all(trust=trust)
    forget_cache()
    core.forget_cache()
    wait_emstudio = {u.id for u in ups if u.trust_needed and not u.for_blender}
    for n in res.get("needs_trust") or []:
        n["emstudio"] = n["id"] in wait_emstudio
    return res


def update_lines(res: Mapping[str, Any], lang: str, tr: Callable[[str], str] = lambda s: s) -> List[str]:
    out = []
    for u in res.get("updated") or []:
        out.append(tr("Updated: {id} {old} → {new} ({repo})").format(
            id=u["id"], old=u.get("from") or "?", new=u.get("to") or "?", repo=u["repo"]))
    for n in res.get("needs_trust") or []:
        out.append((tr("Not updated, it asks the trust again: {id} {version} — update it in EMStudio")
                    if n.get("emstudio") else
                    tr("Not updated, it asks the trust again: {id} {version}")).format(
            id=n["id"], version=n.get("version") or ""))
    for f in res.get("failed") or []:
        why = "; ".join(problem_text(p, lang) for p in (f.get("problems") or [])[:2])
        out.append(tr("Not updated: {id} ({why})").format(id=f["id"], why=why or "?"))
    if res.get("up_to_date"):
        out.append(tr("Everything is up to date"))
    return out


# ── at start-up ─────────────────────────────────────────────────────────────

_startup: Dict[str, Any] = {"done": False, "updates": [], "problems": []}


def startup_check() -> Dict[str, Any]:
    """Once, a little after Blender starts: the repositories with «Check for
    updates at start-up» read (http(s) only with the switch on), what is
    newer said — never installed. Nothing at all when no repository asks."""
    X = library()
    _startup["done"] = True
    if X is None or not any(r.get("check_on_startup") and r.get("enabled", True) for r in X.repositories()):
        return dict(_startup)
    try:
        res = X.check_updates(read=True, startup=True)
    except Exception as exc:  # noqa: BLE001 — a start-up never fails for a repository
        _startup["problems"] = [{"en": str(exc), "it": str(exc)}]
        return dict(_startup)
    _startup["updates"] = [dict(u) for u in res.get("updates") or []]
    _startup["problems"] = [p for r in res.get("repositories") or [] for p in r.get("problems") or []]
    forget_cache()
    return dict(_startup)


def startup_state() -> Dict[str, Any]:
    return dict(_startup)


def startup_line(state: Mapping[str, Any], tr: Callable[[str], str] = lambda s: s) -> Optional[str]:
    ups = state.get("updates") or []
    if not ups:
        return None
    return tr("Updates available: {list}").format(
        list=", ".join(f"{u['id']} {u.get('installed') or '?'} → {u['version']}" for u in ups))

