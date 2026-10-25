"""A tileset as it arrives: what it is, where it falls, how to make it a package.

MICRO tileset-cartella (E.D., 25 Oct 2026). The Basilica Iulia came out of
RealityScan 2.2 as ``tileset_Basilica_TLS_ED.json`` BESIDE the folder
``tileset_Basilica_TLS_ED/`` (Geometry/*.b3dm and 272 ``tileset_lod*.json``),
the root's contents written ``tileset_Basilica_TLS_ED/Geometry/lod5_0.b3dm``;
and ``Archivio.zip`` held the folder alone. EM Tools said «no tileset.json in
Archivio.zip» and stopped there. Here the forms are recognised and said:

* ``package``     — a .3tz / .zip with ``tileset.json`` (as today);
* ``folder``      — a folder with ``tileset.json`` at its root;
* ``pair``        — the RealityScan / RealityCapture form: ``X.json`` with a
  ``root`` beside the folder ``X/`` (chosen as ``X/``, as ``X.json`` or as the
  folder that holds both);
* ``zip_pair``    — a zip holding ``X.json`` and ``X/`` with no ``tileset.json``;
* ``zip_no_root`` — a zip holding ``X/`` alone: the root is looked for beside
  the zip (``X.json`` there, its contents pointing into ``X/``);
* ``unknown``     — none of these: the message says what is inside.

:func:`prepare` writes the package BESIDE what was chosen (never inside it,
never over a file: a ``-2``, ``-3``… suffix), with ``tileset.json`` at its
root: a .3tz through 3D Survey Collection's writer when it is there (EM Tools
writes no .3tz of its own: one profile, one writer), otherwise a plain .zip.
The original is only read.

:func:`position` reads where the root's ``transform`` puts the tileset (its
translation as ECEF → WGS84) and says when the numbers look like projected
coordinates written as geocentric ones: nothing is corrected.

No ``bpy`` here: measured outside Blender (tests/test_tileset_shape.py).
"""

from __future__ import annotations

import json
import math
import os
import posixpath
import shutil
import tempfile
import time
import zipfile
from typing import Any, Callable, Dict, List, Optional

PACKAGE_EXTENSIONS = (".3tz", ".zip")
ENTRY = "tileset.json"

PREPARE_QUESTION = ("This folder is not a package yet. Shall I prepare it? "
                    "(.3tz with 3D Survey Collection, otherwise .zip)")
GEOCENTRIC_WARNING = ("the coordinates look written as geocentric: re-export from "
                      "RealityScan with the project's coordinate system")


# ── recognising ──────────────────────────────────────────────────────────────

def _load_json(raw: bytes) -> Optional[Dict[str, Any]]:
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def _is_root_doc(doc: Optional[Dict[str, Any]]) -> bool:
    return isinstance(doc, dict) and isinstance(doc.get("root"), dict)


def _first_uri(doc: Dict[str, Any]) -> str:
    """The first content of the tree (``uri`` or the 1.0 ``url``)."""
    stack = [doc.get("root") or {}]
    while stack:
        t = stack.pop(0)
        c = t.get("content") or {}
        u = c.get("uri") or c.get("url")
        if isinstance(u, str) and u:
            return u
        stack.extend(t.get("children") or [])
    return ""


def _points_into(doc: Dict[str, Any], folder_name: str) -> bool:
    """Whether the root's contents are written inside ``folder_name/`` (the
    RealityScan root says ``X/Geometry/lod5_0.b3dm``)."""
    u = _first_uri(doc).lstrip("./")
    return u.split("/", 1)[0] == folder_name


def _read_file(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "rb") as fh:
            return _load_json(fh.read())
    except OSError:
        return None


def _folder_summary(path: str) -> str:
    n_json = n_tiles = 0
    for _d, _s, files in os.walk(path):
        for f in files:
            fl = f.lower()
            if fl.endswith(".json"):
                n_json += 1
            elif fl.endswith((".b3dm", ".glb", ".i3dm", ".pnts", ".cmpt", ".gltf")):
                n_tiles += 1
    return f"{n_json} json, {n_tiles} tiles"


def _zip_summary(names: List[str]) -> str:
    tops: Dict[str, List[int]] = {}
    for n in names:
        if n.endswith("/"):
            continue
        head = n.split("/", 1)[0] + ("/" if "/" in n else "")
        c = tops.setdefault(head, [0, 0])
        if n.lower().endswith(".json"):
            c[0] += 1
        elif n.lower().endswith((".b3dm", ".glb", ".i3dm", ".pnts", ".cmpt", ".gltf")):
            c[1] += 1
    parts = [f"{k} ({v[0]} json, {v[1]} tiles)" if k.endswith("/") else k
             for k, v in sorted(tops.items())[:6]]
    if len(tops) > 6:
        parts.append(f"… {len(tops) - 6} more")
    return ", ".join(parts) or "nothing"


def _pair_in(folder: str) -> Optional[Dict[str, str]]:
    """``X.json`` (with a root) and ``X/`` side by side inside ``folder``."""
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return None
    for n in names:
        stem, ext = os.path.splitext(n)
        if ext.lower() != ".json" or n.lower() == ENTRY:
            continue
        sub = os.path.join(folder, stem)
        if not os.path.isdir(sub):
            continue
        doc = _read_file(os.path.join(folder, n))
        if _is_root_doc(doc):
            return {"root_json": os.path.join(folder, n), "folder": sub, "name": stem}
    return None


def recognise(path: str) -> Dict[str, Any]:
    """What ``path`` is. → ``{form, path, name, ready, root_json, folder,
    zip, zip_prefix, root_doc, says, inside}``:

    ``ready`` — usable as it is (a package, or a folder with tileset.json);
    ``preparable`` — :func:`prepare` can write a package from it;
    ``says`` — the sentence for the dialog / the error, in English;
    ``inside`` — for a zip, what it holds (top level)."""
    p = os.path.abspath(os.path.expanduser(path)).rstrip(os.sep)
    out: Dict[str, Any] = {"form": "unknown", "path": p, "name": "", "ready": False,
                           "preparable": False, "root_json": "", "folder": "",
                           "zip": "", "zip_prefix": "", "root_doc": None,
                           "says": "", "inside": ""}
    base = os.path.basename(p)
    stem, ext = os.path.splitext(base)

    if os.path.isdir(p):
        out["name"] = base
        if os.path.isfile(os.path.join(p, ENTRY)):
            out.update(form="folder", ready=True, preparable=True,
                       root_json=os.path.join(p, ENTRY), folder=p,
                       root_doc=_read_file(os.path.join(p, ENTRY)),
                       says=f"A tileset folder ({ENTRY} at its root, {_folder_summary(p)})")
            return out
        sibling = p + ".json"
        doc = _read_file(sibling) if os.path.isfile(sibling) else None
        if _is_root_doc(doc):
            out.update(form="pair", preparable=True, root_json=sibling, folder=p, root_doc=doc,
                       says=f"The RealityScan form: {base}.json beside the folder {base}/ "
                            f"({_folder_summary(p)}), no {ENTRY}")
            return out
        pair = _pair_in(p)
        if pair:
            doc = _read_file(pair["root_json"])
            out.update(form="pair", preparable=True, root_json=pair["root_json"],
                       folder=pair["folder"], root_doc=doc, name=pair["name"],
                       says=f"The RealityScan form inside {base}/: {pair['name']}.json beside "
                            f"{pair['name']}/ ({_folder_summary(pair['folder'])}), no {ENTRY}")
            return out
        out["says"] = (f"No tileset in the folder {base}/: neither {ENTRY} at its root, nor "
                       f"X.json beside a folder X/ (the RealityScan form)")
        return out

    if not os.path.isfile(p):
        out["says"] = f"{base}: not found"
        return out

    if ext.lower() == ".json":
        doc = _read_file(p)
        if base.lower() == ENTRY and _is_root_doc(doc):
            d = os.path.dirname(p)
            out.update(form="folder", ready=True, preparable=True, root_json=p, folder=d,
                       name=os.path.basename(d), root_doc=doc,
                       says=f"A tileset folder ({ENTRY} at its root, {_folder_summary(d)})")
            return out
        sub = os.path.join(os.path.dirname(p), stem)
        if _is_root_doc(doc) and os.path.isdir(sub):
            out.update(form="pair", preparable=True, root_json=p, folder=sub, name=stem,
                       root_doc=doc,
                       says=f"The RealityScan form: {base} beside the folder {stem}/ "
                            f"({_folder_summary(sub)}), no {ENTRY}")
            return out
        out["says"] = (f"{base} is not the root of a tileset" if not _is_root_doc(doc) else
                       f"{base} is a tileset's root, but the folder {stem}/ its contents "
                       f"live in is not beside it")
        return out

    if ext.lower() in PACKAGE_EXTENSIONS:
        out["name"] = stem
        try:
            z = zipfile.ZipFile(p)
        except (zipfile.BadZipFile, OSError) as exc:
            out["says"] = f"{base} is not a readable archive: {exc}"
            return out
        with z:
            names = z.namelist()
            out["inside"] = _zip_summary(names)
            entries = [n for n in names if n.endswith(ENTRY)]
            if entries:
                e = min(entries, key=lambda n: (n.count("/"), len(n)))
                out.update(form="package", ready=True, zip=p, zip_prefix=e[: -len(ENTRY)],
                           root_doc=_load_json(z.read(e)),
                           says=f"A tileset package ({ENTRY} "
                                + ("at its root)" if e == ENTRY else f"in {e[: -len(ENTRY)]})"))
                return out
            tops = {n.split("/", 1)[0] for n in names if "/" in n}
            # X.json and X/ inside the zip
            for n in names:
                if "/" in n.rstrip("/"):
                    continue
                s, e2 = os.path.splitext(n)
                if e2.lower() == ".json" and s in tops:
                    doc = _load_json(z.read(n))
                    if _is_root_doc(doc):
                        out.update(form="zip_pair", preparable=True, zip=p, root_doc=doc,
                                   name=s, root_json=n, folder=s,
                                   says=f"The RealityScan form inside {base}: {n} beside "
                                        f"{s}/, no {ENTRY}")
                        return out
            # X/ alone: its root beside the zip
            here = os.path.dirname(p)
            for t in sorted(tops):
                cand = os.path.join(here, t + ".json")
                doc = _read_file(cand) if os.path.isfile(cand) else None
                if _is_root_doc(doc) and _points_into(doc, t):
                    out.update(form="zip_no_root", preparable=True, zip=p, root_doc=doc,
                               name=t, root_json=cand, folder=t,
                               says=f"{base} holds {t}/ without its root ({ENTRY} is "
                                    f"missing); the root {t}.json is beside the zip "
                                    f"(the RealityScan form)")
                    return out
            tiled = [t for t in sorted(tops) if any(
                n.startswith(t + "/") and n.lower().endswith((".b3dm", ".glb", ".i3dm", ".pnts",
                                                              ".cmpt", ".gltf")) for n in names)]
            hint = (f"; it looks like a RealityScan export without its root: put "
                    f"{tiled[0]}.json beside the zip, or choose the folder that holds "
                    f"{tiled[0]}.json and {tiled[0]}/") if tiled else \
                "; a tileset package holds tileset.json and the tiles it calls"
            out["says"] = (f"No {ENTRY} in {base}: it holds {out['inside']}{hint}")
        return out

    out["says"] = (f"{base} is neither a folder, a .3tz, a .zip nor the .json root "
                   f"of a tileset")
    return out


# ── where it falls ───────────────────────────────────────────────────────────

_A = 6378137.0
_F = 1 / 298.257223563
_E2 = _F * (2 - _F)


def ecef_to_geodetic(x: float, y: float, z: float):
    """WGS84 (lat°, lon°, h m) of an ECEF point (iterative, < 1 mm)."""
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    if p < 1e-9:
        return (90.0 if z >= 0 else -90.0, 0.0, abs(z) - _A * math.sqrt(1 - _E2))
    lat = math.atan2(z, p * (1 - _E2))
    h = 0.0
    for _ in range(10):
        n = _A / math.sqrt(1 - _E2 * math.sin(lat) ** 2)
        h = p / math.cos(lat) - n
        lat = math.atan2(z, p * (1 - _E2 * n / (n + h)))
    return math.degrees(lat), math.degrees(lon), h


def position(root_doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Where the root's ``transform`` puts the tileset. → ``{kind, lat, lon,
    h, translation, warn, line}``; ``kind`` ``earth`` (an ECEF translation),
    ``local`` (no transform, or one that moves less than 1 km: a local frame)
    or ``unknown``. ``warn`` when the place looks like projected coordinates
    read as geocentric: within ~1 km of the equator (the height written as
    Z), at «null island», or far under/over the ellipsoid. Measured on the
    Basilica Iulia: lat 0.0001°, lon 10.51°, h 3.7 m — the Gulf of Guinea."""
    root = (root_doc or {}).get("root") if isinstance(root_doc, dict) else None
    m = root.get("transform") if isinstance(root, dict) else None
    if not (isinstance(m, list) and len(m) == 16):
        return {"kind": "local", "warn": False, "translation": None,
                "line": "Position: no transform at the root — a local frame, "
                        "not placed on the Earth"}
    t = [float(m[12]), float(m[13]), float(m[14])]
    r = math.sqrt(sum(c * c for c in t))
    if r < 1000:
        return {"kind": "local", "warn": False, "translation": t,
                "line": f"Position: a local frame (translation {r:.1f} m), "
                        f"not placed on the Earth"}
    lat, lon, h = ecef_to_geodetic(*t)
    warn = abs(lat) < 0.01 or (abs(lat) < 0.05 and abs(lon) < 0.05) or h < -500 or h > 10000
    line = f"Position: lat {lat:.4f}°, lon {lon:.4f}°, h {h:.1f} m (from the root's transform)"
    if warn:
        line += f" — {GEOCENTRIC_WARNING}"
    return {"kind": "earth", "lat": lat, "lon": lon, "h": h, "translation": t,
            "warn": warn, "line": line}


# ── preparing ────────────────────────────────────────────────────────────────

def _free(path: str) -> str:
    stem, ext = os.path.splitext(path)
    k = 2
    while os.path.exists(path) or os.path.exists(path + ".part"):
        path = f"{stem}-{k}{ext}"
        k += 1
    return path


def package_path(rec: Dict[str, Any], ext: str) -> str:
    """Beside what was chosen, never inside it: ``X.3tz`` / ``X.zip`` next to
    ``X/`` or ``X.json``; next to the chosen folder (its name) when the pair
    was found inside it; next to the zip (named after its root) for a zip."""
    p = rec["path"]
    if rec["form"] in ("zip_pair", "zip_no_root"):
        where, name = os.path.dirname(p), rec["name"]
    elif rec["form"] == "pair" and os.path.isdir(p) and rec["folder"] != p:
        where, name = os.path.dirname(p), os.path.basename(p)
    elif rec["form"] == "pair":
        where, name = os.path.dirname(rec["folder"]), rec["name"]
    elif rec["form"] == "folder":
        where, name = os.path.dirname(rec["folder"]), os.path.basename(rec["folder"])
    else:
        raise ValueError(f"{rec['form']}: nothing to prepare")
    return _free(os.path.join(where, name + ext))


def _members(rec: Dict[str, Any]):
    """``(archive path, opener)`` of the package's files: ``tileset.json`` the
    root's bytes, the rest the folder's (paths as the root writes them)."""
    form = rec["form"]
    out = []
    if form == "folder":
        top = rec["folder"]
        for d, dirs, files in os.walk(top):
            dirs.sort()
            for f in sorted(files):
                if f in (".DS_Store", "Thumbs.db"):
                    continue
                disk = os.path.join(d, f)
                rel = os.path.relpath(disk, top).replace(os.sep, "/")
                out.append((rel, (lambda q=disk: open(q, "rb")), os.path.getsize(disk)))
        return out
    if form == "pair" or form == "zip_no_root":
        rj = rec["root_json"]
        out.append((ENTRY, (lambda q=rj: open(q, "rb")), os.path.getsize(rj)))
    if form == "pair":
        top = rec["folder"]
        parent = os.path.dirname(top)
        for d, dirs, files in os.walk(top):
            dirs.sort()
            for f in sorted(files):
                if f in (".DS_Store", "Thumbs.db"):
                    continue
                disk = os.path.join(d, f)
                rel = os.path.relpath(disk, parent).replace(os.sep, "/")
                out.append((rel, (lambda q=disk: open(q, "rb")), os.path.getsize(disk)))
        return out
    z = zipfile.ZipFile(rec["zip"])
    for info in z.infolist():
        if info.is_dir():
            continue
        n = info.filename
        if form == "zip_pair" and n == rec["root_json"]:
            out.append((ENTRY, (lambda i=info: z.open(i)), info.file_size))
        elif n.split("/", 1)[0] == rec["folder"] and "/" in n:
            if posixpath.normpath(n).startswith(".."):
                continue
            out.append((n, (lambda i=info: z.open(i)), info.file_size))
    out.sort(key=lambda r: r[0])
    return out


def write_zip(rec: Dict[str, Any], out_path: str,
              progress: Optional[Callable[[int, int], None]] = None) -> Dict[str, Any]:
    """A plain .zip (stored, zip64) with ``tileset.json`` at its root, written
    to ``.part`` and renamed at the end."""
    t0 = time.time()
    members = _members(rec)
    part = out_path + ".part"
    total = 0
    try:
        with zipfile.ZipFile(part, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
            for i, (rel, opener, size) in enumerate(members, 1):
                with opener() as r, zf.open(zipfile.ZipInfo(rel, (1980, 1, 1, 0, 0, 0)), "w",
                                            force_zip64=size >= 0x7FFFFFFF) as w:
                    shutil.copyfileobj(r, w, 1 << 20)
                total += size
                if progress:
                    progress(i, len(members))
        os.replace(part, out_path)
    finally:
        if os.path.exists(part):
            os.remove(part)
    return {"path": out_path, "entries": len(members), "bytes": total,
            "seconds": round(time.time() - t0, 2), "format": "zip"}


def _staged(rec: Dict[str, Any], where: str) -> str:
    """A folder with ``tileset.json`` at its root built from ``rec``, for a
    writer that packs folders: hard links where the disk allows (no bytes
    copied, the original untouched), copies otherwise."""
    stage = tempfile.mkdtemp(prefix=".em-tileset-", dir=where)
    for rel, opener, _size in _members(rec):
        target = os.path.join(stage, *rel.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        src = None
        if rec["form"] == "folder":
            src = os.path.join(rec["folder"], *rel.split("/"))
        elif rec["form"] == "pair":
            src = rec["root_json"] if rel == ENTRY else os.path.join(
                os.path.dirname(rec["folder"]), *rel.split("/"))
        elif rel == ENTRY and rec["form"] == "zip_no_root":
            src = rec["root_json"]
        if src:
            try:
                os.link(src, target)
                continue
            except OSError:
                shutil.copy2(src, target)
                continue
        with opener() as r, open(target, "wb") as w:
            shutil.copyfileobj(r, w, 1 << 20)
    return stage


def prepare(rec: Dict[str, Any], writer_3tz: Optional[Callable[..., Dict[str, Any]]] = None,
            progress: Optional[Callable[[int, int], None]] = None) -> Dict[str, Any]:
    """The package of ``rec``, beside it. ``writer_3tz(src_dir, out_path)`` is
    3D Survey Collection's ``archive_3tz.write_3tz`` when it is there: a .3tz;
    without it a .zip. → ``{path, format, entries, bytes, seconds}``."""
    if not rec.get("preparable"):
        raise ValueError(rec.get("says") or "nothing to prepare")
    if writer_3tz is None:
        return write_zip(rec, package_path(rec, ".zip"), progress)
    out = package_path(rec, ".3tz")
    if rec["form"] == "folder":
        info = dict(writer_3tz(rec["folder"], out) or {})
    else:
        stage = _staged(rec, os.path.dirname(out))
        try:
            info = dict(writer_3tz(stage, out) or {})
        finally:
            shutil.rmtree(stage, ignore_errors=True)
    info.update(path=out, format="3tz")
    return info
