"""P3 · the RESOURCE INVENTORY of a graph, before it goes into a room.

MICRO-LA-BARRA-E-LE-STANZE, «Bring into a room…». Before anything is sent, the
person sees where every resource of the graph IS, in four groups:

* **found** — on this disk: a path that resolves to a file. Default: upload;
* **stored** — already in the room's store (HEAD on its sha256 → 200): nothing
  to send, and a second «Bring into a room» finds everything here;
* **elsewhere** — the node has the bytes but they are AT HOME IN ANOTHER ROOM
  (HEAD answers `X-EM-Home-Room`). A file lives in one room (F1, E.D. 3 Oct,
  evening): the proposal is «Move here» — the home and its rights change, no
  byte travels — confirmed after the rooms whose graphs cite it are listed;
  otherwise it stays a reference to that room;
* **external** — a URL, a NAS share, or a resource the graph declares a
  `reference` whose path is not on this machine: it stays where it is, counted;
* **missing** — a path that does not resolve, or no locator at all.

…with count and size. For the found ones: upload (default) / leave as
reference / skip, per group or one by one. **Everything goes up, raw photos
included** (E.D., 3 Oct 2026: it is also the safety copy) — and raw photos go as
their ACQUISITION: the resources a `dtc_acquisition` brought in
(`dtc_had_output`) are shown and chosen as ONE batch line, never as hundreds of
rows (s3dgraphy `dtc.ingest`: «the serial node is the acquisition»).

**The lot rule** (L1, E.D. 3 Oct evening): a file named like an EM document
(`D.01`, `D.07.03`, `D.11 Zenitale` — `is_em_document_name`) stays a document,
nothing in a DosCo is ever a lot, and a lot is PROPOSED only for the photos of
one session — same camera (EXIF make + model + body serial), EXIF times at most
`SESSION_GAP_SECONDS` apart, at least `SESSION_MIN_PHOTOS` — and becomes one
acquisition only when the person confirms it (`propose_sessions`). The same
cases as EMStudio's `room-inventory.ts` (`check-room-inventory.mjs`, part 6).

**Rights.** Nothing is written here about rights: they are already on the
resource node or on its batch (licence, embargo, author — `rights_for_digest`
reads the batch for a member that says nothing), and the node applies them to
the bytes. With no licence anywhere the node's default is the room's
participants only (D-C, stratigraph-server 93df96a) — which is the «room only»
default E.D. chose, enforced where it can be enforced.

**A resource becomes store-backed WITHOUT losing its path**
(`make_store_backed`): `data.url` becomes the store's address, `checksum` and
`residency: resident` are written, and the disk path stays as a second address
of the SAME bytes in `data.addresses` — the field s3dgraphy already has for
exactly this (`resources.addresses`, dev27 A4). No new key is invented.

Pure: no `bpy`, the network behind two parameters (`has_asset`, `hasher`), so
this module can move to s3Dgraphy as it is. Measured by
`tests/test_inventory.py`.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from typing import Any, Callable, Dict, Iterable, List, Optional

GROUP_FOUND = "found"
GROUP_STORED = "stored"
GROUP_ELSEWHERE = "elsewhere"
GROUP_EXTERNAL = "external"
GROUP_MISSING = "missing"
GROUPS = (GROUP_FOUND, GROUP_STORED, GROUP_ELSEWHERE, GROUP_EXTERNAL, GROUP_MISSING)

CHOICE_UPLOAD = "upload"
CHOICE_REFERENCE = "reference"
CHOICE_SKIP = "skip"
CHOICE_MOVE = "move"
CHOICES = (CHOICE_UPLOAD, CHOICE_REFERENCE, CHOICE_SKIP)

#: The words a person reads for each group, one sentence each in the report.
GROUP_LABELS = {
    GROUP_FOUND: "found on this disk",
    GROUP_STORED: "already in the room's storage",
    GROUP_ELSEWHERE: "at home in another room",
    GROUP_EXTERNAL: "external references (NAS, URL)",
    GROUP_MISSING: "missing",
}

_REMOTE_SCHEMES = ("http", "https", "ftp", "ftps", "s3", "smb", "nfs", "afp",
                   "sftp", "webdav", "dav")

#: extension → media type, for the upload's declaration. Unknown is octet-stream:
#: the node stores the bytes either way, and a wrong type is worse than none.
_MEDIA = {
    ".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".obj": "model/obj",
    ".stl": "model/stl", ".ply": "application/x-ply", ".fbx": "application/octet-stream",
    ".3tz": "application/vnd.3dtiles+zip", ".zip": "application/zip",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".tif": "image/tiff", ".tiff": "image/tiff", ".webp": "image/webp",
    ".dng": "image/x-adobe-dng", ".cr2": "image/x-canon-cr2", ".nef": "image/x-nikon-nef",
    ".pdf": "application/pdf", ".txt": "text/plain", ".csv": "text/csv",
    ".json": "application/json", ".xml": "application/xml",
    ".mp4": "video/mp4", ".mov": "video/quicktime",
    ".blend": "application/x-blender",
}


def media_type_for(path: str) -> str:
    return _MEDIA.get(os.path.splitext(str(path or ""))[1].lower(),
                      "application/octet-stream")


def _data(node: Any) -> Dict[str, Any]:
    data = getattr(node, "data", None)
    return data if isinstance(data, dict) else {}


def _alive(item: Any) -> bool:
    """Tombstones are not resources to bring (s3dgraphy's own reading of one)."""
    try:
        from s3dgraphy.crdt import is_removed
    except ImportError:                 # pragma: no cover — an older wheel
        return True
    payload = item if isinstance(item, dict) else getattr(item, "__dict__", {}) or {}
    try:
        return not is_removed(payload)
    except Exception:  # noqa: BLE001 — a shape crdt cannot read is alive
        return True


def _hex(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text[len("sha256:"):] if text.startswith("sha256:") else text


def locator_kind(locator: str) -> str:
    """`url` (a scheme that is not this disk), `share` (a UNC/NAS path),
    `file` (a `file://` URL), `path`, or `` (no locator)."""
    text = str(locator or "").strip()
    if not text:
        return ""
    if text.startswith("\\\\") or text.startswith("//"):
        return "share"
    scheme = urllib.parse.urlsplit(text).scheme.lower()
    if scheme == "file":
        return "file"
    if scheme == "blend":
        return "blend"
    if scheme in _REMOTE_SCHEMES:
        return "url"
    if len(scheme) == 1:                    # a Windows drive letter, C:\…
        return "path"
    if scheme and "://" in text:
        return "url"
    return "path"


def resolve_path(locator: str, base_dirs: Iterable[str] = ()) -> Optional[str]:
    """The file a local locator points at, or None. Relative paths are tried
    against `base_dirs` in order (the DosCo folder, the em.json's folder, the
    .blend's folder), `//` Blender-relative ones too.

    R1 (E.D., 4 Oct 2026) · through s3dgraphy's ONE resolver
    (`resources.locate.local_candidates`): `/DosCo/D.32.jpg` is a path of the
    STUDY, and read as absolute it made D.32 «missing» while it was on the
    disk. The old reading stays only for an s3dgraphy without the resolver."""
    try:
        from s3dgraphy.resources.locate import local_candidates
    except ImportError:
        local_candidates = None
    if local_candidates is not None and str(locator or "").strip():
        if locator_kind(str(locator).strip()) not in ("url", "blend"):
            for cand in local_candidates(str(locator), list(base_dirs or ())):
                if os.path.exists(cand):
                    return cand
            return None
    text = str(locator or "").strip()
    if locator_kind(text) == "file":
        text = urllib.parse.unquote(urllib.parse.urlsplit(text).path)
    if text.startswith("//") and locator_kind(locator) != "share":
        text = text[2:]
    text = os.path.expanduser(text)
    if os.path.isabs(text):
        return text if os.path.exists(text) else None
    for base in base_dirs or ():
        if not base:
            continue
        candidate = os.path.normpath(os.path.join(base, text))
        if os.path.exists(candidate):
            return candidate
    return None


def _batches(graph: Any) -> Dict[str, Dict[str, str]]:
    """resource id → {id, name} of the `dtc_acquisition` that brought it in."""
    nodes = {n.node_id: n for n in getattr(graph, "nodes", []) or [] if _alive(n)}
    out: Dict[str, Dict[str, str]] = {}
    for edge in getattr(graph, "edges", []) or []:
        if not _alive(edge) or getattr(edge, "edge_type", "") != "dtc_had_output":
            continue
        source = nodes.get(getattr(edge, "edge_source", None))
        if source is None or getattr(source, "node_type", "") != "dtc_acquisition":
            continue
        target = getattr(edge, "edge_target", None)
        if target and target not in out:
            out[target] = {"id": source.node_id,
                           "name": str(getattr(source, "name", "") or source.node_id)}
    return out


def resource_entries(graph: Any) -> List[Dict[str, Any]]:
    """One entry per live ResourceNode: `{id, name, locator, checksum,
    residency, batch_id, batch_name}` — read only."""
    batches = _batches(graph)
    out = []
    for node in getattr(graph, "nodes", []) or []:
        if getattr(node, "node_type", "") != "resource" or not _alive(node):
            continue
        data = _data(node)
        batch = batches.get(node.node_id) or {}
        out.append({
            "id": node.node_id,
            "name": str(getattr(node, "name", "") or node.node_id),
            "locator": str(data.get("url") or getattr(node, "url", "") or ""),
            "checksum": _hex(data.get("checksum")),
            "residency": str(data.get("residency") or ""),
            "batch_id": batch.get("id", ""),
            "batch_name": batch.get("name", ""),
        })
    out.sort(key=lambda e: (e["batch_name"], e["name"], e["id"]))
    return out


def _is_store_url(locator: str) -> bool:
    return "/v1/rooms/" in locator and "/asset/sha256:" in locator


def classify(entries: List[Dict[str, Any]], *,
             base_dirs: Iterable[str] = (),
             has_asset: Optional[Callable[[str], bool]] = None,
             hasher: Optional[Callable[[str], str]] = None,
             asset_home: Optional[Callable[[str], Any]] = None,
             room_id: str = "") -> List[Dict[str, Any]]:
    """Put every entry in its group. → the entries, each with `group`, `path`,
    `size`, `sha256`, `choice`, `note` (and `home` for «elsewhere»).

    `has_asset(hex)` is the room's HEAD (None: no room to ask yet, nothing is
    «stored»). `hasher(path)` the sha256 of a file — the found ones are hashed
    so the HEAD can answer for them too: a file on this disk that the room
    already holds is «stored», not «found», and is not sent again.

    `asset_home(hex)` → `(present, home)`, the same HEAD read whole (F1): when
    given it answers instead of `has_asset`, and bytes present but at home in a
    room other than `room_id` are «elsewhere», with the proposal «Move here».
    """
    bases = list(base_dirs or ())
    if asset_home is not None:
        def _where(hexd: str) -> str:
            present, home = asset_home(hexd)
            if not present:
                return ""
            return home if home and home != room_id else room_id or "here"
    elif has_asset is not None:
        def _where(hexd: str) -> str:
            return (room_id or "here") if has_asset(hexd) else ""
    else:
        _where = None

    def _held(row: Dict[str, Any], hexd: str, note: str) -> bool:
        """The node has these bytes: «stored» here, or «elsewhere»."""
        where = _where(hexd) if _where else ""
        if not where:
            return False
        if where != (room_id or "here"):
            row.update(group=GROUP_ELSEWHERE, choice=CHOICE_MOVE, home=where,
                       note=f"at home in the room {where}")
        else:
            row.update(group=GROUP_STORED, choice=CHOICE_SKIP, note=note)
        return True

    out = []
    for entry in entries:
        row = dict(entry)
        row.update({"group": GROUP_MISSING, "path": "", "size": 0,
                    "sha256": row.get("checksum", ""), "choice": CHOICE_SKIP,
                    "note": "", "home": ""})
        loc = row.get("locator", "")
        kind = locator_kind(loc)
        recorded = row.get("checksum", "")
        # 1 · resident with a digest the room confirms
        if recorded and _where is not None and (
                row.get("residency") == "resident" or _is_store_url(loc)):
            if _held(row, recorded, "in the room's store"):
                out.append(row)
                continue
        if kind == "share" and resolve_path(loc, bases):
            # R1 · `//DosCo/D.33.jpg` is the study's (a double slash read as
            # one, as s3dgraphy's resolver reads it), not a network share
            kind = "path"
        if kind in ("url", "share"):
            if _is_store_url(loc):
                row.update(group=GROUP_MISSING,
                           note="the graph points at a store this room does not answer for")
            else:
                row.update(group=GROUP_EXTERNAL, choice=CHOICE_REFERENCE,
                           note="stays where it is" if kind == "url" else "a network share")
            out.append(row)
            continue
        if kind == "blend":
            # the bytes are a datablock of THIS .blend: not a file to send. The
            # scene's model is published instead (promote_model), as a glTF.
            row.update(group=GROUP_FOUND, choice=CHOICE_REFERENCE,
                       note="a datablock in the .blend: its model is published "
                            "from the scene")
            out.append(row)
            continue
        if not kind:
            row.update(note="no locator: the graph does not say where the file is")
            out.append(row)
            continue
        path = resolve_path(loc, bases)
        if path is None:
            if row.get("residency") == "reference" or str(loc).startswith("/Volumes/"):
                row.update(group=GROUP_EXTERNAL, choice=CHOICE_REFERENCE,
                           note="a reference not on this machine")
            else:
                row.update(note=f"not on this disk: {loc}")
            out.append(row)
            continue
        row["path"] = path
        if os.path.isdir(path):
            # a folder (a tileset, a photo directory) is not ONE object: it is
            # left as a reference until somebody packs it (.3tz) or makes it a
            # batch — said, not silently skipped
            row.update(group=GROUP_FOUND, choice=CHOICE_REFERENCE,
                       size=_tree_size(path),
                       note="a folder: pack it (.3tz) to upload it as one asset")
            out.append(row)
            continue
        row["size"] = os.path.getsize(path)
        digest = hasher(path) if hasher else ""
        row["sha256"] = digest
        if digest and recorded and digest != recorded:
            row["note"] = ("the file on disk is not the bytes the graph "
                           "recorded: its current bytes will be uploaded")
        if not (digest and _held(row, digest, row["note"] or "already in the room's store")):
            row.update(group=GROUP_FOUND, choice=CHOICE_UPLOAD)
        out.append(row)
    return out


def _tree_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def apply_choices(rows: List[Dict[str, Any]], *,
                  per_group: Optional[Dict[str, str]] = None,
                  per_batch: Optional[Dict[str, str]] = None,
                  per_item: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """The person's choices, most specific wins: item > batch > group.

    Only FOUND rows can be uploaded; a choice of upload on any other group is
    ignored (there is nothing on this disk to send). ELSEWHERE rows take only
    `move` or `reference`."""
    for row in rows:
        if row["group"] == GROUP_ELSEWHERE:
            # F1 · at home in another room: move it here, or leave a reference
            choice = (per_item or {}).get(row["id"]) \
                or (per_group or {}).get(GROUP_ELSEWHERE) or row["choice"]
            if choice in (CHOICE_MOVE, CHOICE_REFERENCE):
                row["choice"] = choice
            continue
        if row["group"] != GROUP_FOUND:
            continue
        if not row.get("path") or os.path.isdir(row["path"]):
            continue                     # a folder or a datablock stays a reference
        choice = (per_group or {}).get(GROUP_FOUND) or row["choice"]
        if row.get("batch_id"):
            choice = (per_batch or {}).get(row["batch_id"], choice)
        choice = (per_item or {}).get(row["id"], choice)
        if choice in CHOICES:
            row["choice"] = choice
    return rows


def summarise(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Counts and sizes per group, and per batch inside «found». The batch is
    ONE line however many photographs it holds."""
    groups = {g: {"count": 0, "size": 0} for g in GROUPS}
    batches: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        bucket = groups[row["group"]]
        bucket["count"] += 1
        bucket["size"] += int(row.get("size") or 0)
        if row.get("batch_id"):
            b = batches.setdefault(row["batch_id"], {
                "id": row["batch_id"], "name": row.get("batch_name") or row["batch_id"],
                "count": 0, "size": 0, "groups": {},
                "proposed": bool(row.get("batch_proposed"))})
            b["count"] += 1
            b["size"] += int(row.get("size") or 0)
            b["groups"][row["group"]] = b["groups"].get(row["group"], 0) + 1
    to_upload = [r for r in rows if r["group"] == GROUP_FOUND and r["choice"] == CHOICE_UPLOAD]
    return {"groups": groups, "batches": list(batches.values()),
            "upload": {"count": len(to_upload),
                       "size": sum(int(r.get("size") or 0) for r in to_upload)}}


def human_size(n: int) -> str:
    size = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def sentences(summary: Dict[str, Any]) -> List[str]:
    """One sentence per group (and per batch), for the panel and the console."""
    out = []
    for group in GROUPS:
        g = summary["groups"][group]
        line = f"{g['count']} {GROUP_LABELS[group]}"
        if g["size"]:
            line += f" ({human_size(g['size'])})"
        out.append(line)
    for b in summary["batches"]:
        out.append(f"{'proposed lot' if b.get('proposed') else 'batch'} "
                   f"«{b['name']}»: {b['count']} file(s), {human_size(b['size'])}")
    return out


# ── L1 · the lot rule ────────────────────────────────────────────────────────

_PHOTO_EXT = (".jpg", ".jpeg", ".tif", ".tiff", ".png", ".dng", ".cr2", ".cr3",
              ".nef", ".arw", ".orf", ".rw2", ".heic", ".raf")
#: two shots of one camera further apart than this are two sessions. 30
#: minutes: a battery or card swap, a ladder moved, a drone relaunched stay in
#: the session; the morning and the afternoon, or two days, do not.
SESSION_GAP_SECONDS = 30 * 60
#: fewer photos than this are files, not a lot worth proposing
SESSION_MIN_PHOTOS = 5

_EM_DOCUMENT = re.compile(r"^D\.\d+(?:\.\d+)?(?=$|[\s._-])")
_EXIF_TIME = re.compile(r"^(\d{4})[:-](\d{2})[:-](\d{2})[ T](\d{2}):(\d{2}):(\d{2})")


def is_em_document_name(leaf: str) -> bool:
    """A file named like an EM document — `D.01`, `D.1`, `D.12.jpg`,
    `D.07.03.jpg`, `D.11 Zenitale.png`: the prefix s3Dgraphy's DosCo scanner
    reads (`fs_backend._EM_ID_PREFIX`), then the end, an extension, a space,
    `_` or `-`. A document stays a document: never a lot."""
    return bool(_EM_DOCUMENT.match(str(leaf or "").strip()))


def in_dosco(path: str, dosco_dirs: Iterable[str] = ()) -> bool:
    """Inside a DosCo — a declared DosCo folder, or a folder named DosCo on the
    way. The DosCo is documentation: never a lot."""
    p = str(path or "").replace("\\", "/")
    if any(seg.lower() == "dosco" for seg in p.split("/")[:-1]):
        return True
    for d in dosco_dirs or ():
        folder = str(d or "").replace("\\", "/").rstrip("/")
        if folder and (p == folder or p.startswith(folder + "/")):
            return True
    return False


def exif_seconds(taken_at: Optional[str]) -> Optional[float]:
    """`2024:05:12 10:22:33` → seconds, or None. Naive time: one camera's clock
    against itself, so the zone does not matter."""
    import calendar
    m = _EXIF_TIME.match(str(taken_at or "").strip())
    if not m or int(m.group(1)) <= 1900:
        return None
    try:
        return float(calendar.timegm(tuple(int(x) for x in m.groups()) + (0, 0, 0)))
    except (ValueError, OverflowError):
        return None


def session_lots(files: Iterable[Dict[str, Any]], *, dosco_dirs: Iterable[str] = (),
                 gap_seconds: float = SESSION_GAP_SECONDS,
                 min_photos: int = SESSION_MIN_PHOTOS) -> List[Dict[str, Any]]:
    """The photo SESSIONS among `files` (`{id, path, exif: {camera, taken_at}}`):
    same camera, EXIF times at most `gap_seconds` apart, at least `min_photos`.
    A document-named file, a file in a DosCo, a file that is not a photo, a
    photo with no camera or no time: never in a session.
    → `[{key, name, ids, camera, from, to}]`."""
    per_camera: Dict[str, List[tuple]] = {}
    dosco = list(dosco_dirs or ())
    for f in files:
        path = str(f.get("path") or "")
        leaf = os.path.basename(path.replace("\\", "/"))
        if not leaf.lower().endswith(_PHOTO_EXT) or is_em_document_name(leaf) \
                or in_dosco(path, dosco):
            continue
        exif = f.get("exif") or {}
        camera = str(exif.get("camera") or "").strip()
        at = exif_seconds(exif.get("taken_at"))
        if not camera or at is None:
            continue
        per_camera.setdefault(camera, []).append((at, str(f["id"]), str(exif["taken_at"])))
    out = []
    for camera, shots in per_camera.items():
        shots.sort()
        run: List[tuple] = []

        def close():
            if len(run) >= min_photos:
                first, last = run[0][2], run[-1][2]
                out.append({
                    "key": f"session:{camera}@{first}", "camera": camera,
                    "from": first, "to": last, "ids": [s[1] for s in run],
                    "name": f"{camera} · {first[:10].replace(':', '-')} "
                            f"{first[11:16]}–{last[11:16]}"})

        for shot in shots:
            if run and shot[0] - run[-1][0] > gap_seconds:
                close()
                run = []
            run.append(shot)
        close()
    return out


def propose_sessions(rows: List[Dict[str, Any]], *,
                     exif_of: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
                     dosco_dirs: Iterable[str] = (),
                     gap_seconds: float = SESSION_GAP_SECONDS,
                     min_photos: int = SESSION_MIN_PHOTOS) -> List[Dict[str, Any]]:
    """The sessions among the rows that have a file here and no batch yet,
    PROPOSED: each row gets the session as its batch (`batch_proposed`), and
    the returned lots are `confirmed: False` until the person says yes —
    only a confirmed one becomes an acquisition."""
    files = []
    for row in rows:
        if row.get("batch_id") or not row.get("path") \
                or row.get("group") not in (GROUP_FOUND, GROUP_STORED):
            continue
        exif = exif_of(row["path"]) if exif_of else row.get("exif")
        files.append({"id": row["id"], "path": row["path"], "exif": exif})
    lots = session_lots(files, dosco_dirs=dosco_dirs, gap_seconds=gap_seconds,
                        min_photos=min_photos)
    by_id = {r["id"]: r for r in rows}
    for lot in lots:
        lot["confirmed"] = False
        for rid in lot["ids"]:
            by_id[rid].update(batch_id=lot["key"], batch_name=lot["name"],
                              batch_proposed=True)
    return lots


# ── F1 · «Move here» ─────────────────────────────────────────────────────────

def move_plan(rows: List[Dict[str, Any]], views: Dict[str, Dict[str, Any]]
              ) -> Dict[str, Any]:
    """The confirmation, before the yes: of the «elsewhere» rows chosen to
    move, which may (the node's `can_move`), which may not and why, the rooms
    they leave and the rooms whose graphs will hold a reference. `views` is
    row id → the node's `GET …/asset-home/{ref}` answer (or `{"error": …}`)."""
    movable, blocked, leave, refs = [], [], set(), set()
    for row in rows:
        if row.get("group") != GROUP_ELSEWHERE or row.get("choice") != CHOICE_MOVE:
            continue
        view = views.get(row["id"])
        if not view or "error" in view:
            blocked.append({"row": row, "why": (view or {}).get("error") or "not asked"})
            continue
        if not view.get("can_move"):
            blocked.append({"row": row, "why": view.get("why_not") or "not allowed"})
            continue
        movable.append(row)
        leave.update([view["home"]] if view.get("home") else view.get("legacy_homes") or [])
        refs.update(view.get("references") or [])
    return {"movable": movable, "blocked": blocked, "leave": sorted(leave),
            "references": sorted(refs)}


def make_store_backed(resource: Any, *, url: str, sha256: str,
                      residency: str = "resident") -> List[Dict[str, Any]]:
    """The resource now lives in the room's store — and keeps its path.

    `data.url` becomes the store's address (what every consumer reads first),
    `checksum` and `residency: resident` are written, and the old locator stays
    as a second address of the same bytes (`data.addresses`, s3dgraphy's own
    field). → the resource's addresses."""
    from s3dgraphy.resources.addresses import add_address, addresses

    data = getattr(resource, "data", None)
    if not isinstance(data, dict):
        data = {}
        resource.data = data
    digest = f"sha256:{_hex(sha256)}"
    old = str(data.get("url") or getattr(resource, "url", "") or "")
    data["checksum"] = digest
    data["url"] = url
    if hasattr(resource, "url"):
        try:
            resource.url = url
        except Exception:  # noqa: BLE001 — a read-only attribute on an odd node
            pass
    # `reference` (F1): the bytes are kept in ANOTHER room's store — this
    # graph cites them there, it does not hold them
    if hasattr(resource, "set_residency"):
        resource.set_residency(residency)
    else:
        data["residency"] = residency
    if old and old != url:
        add_address(resource, old, checksum=digest)
    return addresses(resource)


def seed_ops(graph: Any, section: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The operations that seat this graph in a room: every node, then every
    edge — EMStudio's `seedOpsForContainer`, in Python.

    `section` is the graph's em.json section (`build_emjson(graph)["graph"]`).
    The language a text node is born in travels IN the op (s3dgraphy dev28,
    decision 12): the node's own `data.lang`, else the study's working
    language, else `und` — never guessed beyond that.
    """
    try:
        from s3dgraphy.crdt import is_text_node
    except ImportError:                 # pragma: no cover — an older wheel
        def is_text_node(_payload):
            return False
    try:
        from s3dgraphy.language import working_language
        study = working_language(graph)
    except Exception:  # noqa: BLE001
        study = None
    ops: List[Dict[str, Any]] = []
    for node in section.get("nodes") or []:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        payload = dict(node)
        data = dict(payload.get("data") or {})
        if is_text_node(payload) and not str(data.get("lang") or "").strip():
            data["lang"] = study or "und"
            payload["data"] = data
        op = {"op": "add_node", "id": node_id, "node": payload}
        stamp = data.get("modified_at") or data.get("created_at")
        if stamp:
            op["ts"] = stamp
        ops.append(op)
    for edge in section.get("edges") or []:
        edge_id = str(edge.get("id") or "")
        if not edge_id:
            continue
        ops.append({"op": "add_edge", "id": edge_id, "source": edge.get("source"),
                    "target": edge.get("target"), "edge_type": edge.get("edge_type")})
    return ops
