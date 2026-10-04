"""U5 · the images of the units and of the finds, decided without Blender.

MICRO-EMTOOLS-MENO-E-MEGLIO (Analysis 3 of the UI audit, 4 October 2026):

1. every image found is a RESOURCE — its sha256 and its positions, read by the
   one resolver R1 — not a path;
2. the link image → unit is PROPOSED by a naming convention (a configurable
   pattern, ``US012_*.jpg``) and CONFIRMED by the person;
3. the thumbnails are a DERIVED cache keyed by sha256, never sent to the room:
   rebuilt anywhere;
4. they are seen in the Stratigraphy Manager with the file's state (R2);
5. the folder searched first is the EM standard tree's (C1), not a field of an
   auxiliary file.

Before, the images depended on the ``resource_folder`` of the active
auxiliary file and, without one, the operator answered «Use Resource
Collections instead», a concept that no longer exists.
"""

import os
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp")
#: ``{unit}`` stands for the unit's code; the rest is fnmatch (``*`` any text)
DEFAULT_PATTERN = "{unit}_*"
#: the EM standard tree's folders searched first (C1), in this order
TREE_FOLDERS = ("EM/DosCo", "EM", "RB", "SB")
THUMB_SIZE = 256

_CODE = re.compile(r"^([A-Za-z]+)0*(\d+)([A-Za-z]*)$")


def normal_code(text: str) -> str:
    """``US012`` → ``us12``: letters and number, case and leading zeros apart.
    A code without that shape is only lower-cased."""
    t = str(text or "").strip()
    m = _CODE.match(t)
    if m:
        return f"{m.group(1).lower()}{int(m.group(2))}{m.group(3).lower()}"
    return t.lower()


def unit_keys(name: str) -> List[str]:
    """The forms a unit's name can take in a file name: the whole name and its
    last part — ``1.US10`` (pyArchInit: area + code) is ``US10`` on a photo,
    ``GT16.USV118`` (a prefixed proxy) is ``USV118`` — normalised."""
    n = str(name or "").strip()
    keys = [normal_code(n)]
    last = n.rsplit(".", 1)[-1]
    if last != n:
        keys.append(normal_code(last))
    return [k for i, k in enumerate(keys) if k and k not in keys[:i]]


def _pattern_regex(pattern: str):
    """``{unit}_*`` → a regex with the unit's code as a group: ``*`` any text,
    ``?`` one character, ``{unit}`` letters + number (+ letters)."""
    out = []
    for part in re.split(r"(\{unit\}|\*|\?)", pattern):
        if part == "{unit}":
            out.append(r"(?P<unit>[A-Za-z]+\d+[A-Za-z]*)")
        elif part == "*":
            out.append(".*")
        elif part == "?":
            out.append(".")
        elif part:
            out.append(re.escape(part))
    return re.compile("".join(out), re.I)


def code_in_filename(filename: str, pattern: str = DEFAULT_PATTERN) -> Optional[str]:
    """The unit code a file name carries under ``pattern`` (normalised), or
    None. ``US012_north.jpg`` with ``{unit}_*`` → ``us12``. The pattern is
    matched against the name without its extension (and with it, for a
    pattern that names one)."""
    if "{unit}" not in pattern:
        return None
    name = os.path.basename(str(filename))
    rx = _pattern_regex(pattern)
    for candidate in (os.path.splitext(name)[0], name):
        m = rx.fullmatch(candidate)
        if m:
            return normal_code(m.group("unit"))
    return None


def is_image(path: str) -> bool:
    return os.path.splitext(str(path))[1].lower() in IMAGE_EXTENSIONS


def propose(files: Iterable[str], units: Sequence[Tuple[str, str]],
            pattern: str = DEFAULT_PATTERN) -> List[Dict[str, str]]:
    """The links the convention proposes: ``[{path, unit_id, unit_name}]``, one
    per image whose name carries the code of a unit (``units`` = ``[(node_id,
    name)]``). Nothing is linked here: the person confirms."""
    index: Dict[str, Tuple[str, str]] = {}
    for uid, uname in units:
        for k in unit_keys(uname):
            index.setdefault(k, (uid, uname))
    out = []
    for path in sorted(files):
        if not is_image(path):
            continue
        code = code_in_filename(path, pattern)
        hit = index.get(code) if code else None
        if hit:
            out.append({"path": path, "unit_id": hit[0], "unit_name": hit[1]})
    return out


def start_folders(project_root: Optional[str]) -> List[str]:
    """Where the search starts (C1): the folders of the EM standard tree that
    exist, ``EM/DosCo`` first."""
    if not project_root:
        return []
    out = [os.path.join(project_root, *rel.split("/")) for rel in TREE_FOLDERS]
    return [p for p in out if os.path.isdir(p)]


def images_under(folders: Iterable[str]) -> List[str]:
    """Every image under the folders (recursively), each path once."""
    seen, out = set(), []
    for folder in folders:
        for dirpath, _dirs, names in os.walk(folder):
            for n in names:
                p = os.path.join(dirpath, n)
                if is_image(p) and p not in seen:
                    seen.add(p)
                    out.append(p)
    return out


def locator_for(path: str, project_root: Optional[str]) -> str:
    """The position written in the graph: a path of the STUDY (``/EM/DosCo/…``,
    read by the resolver against the project) when the file is inside the
    project, else the absolute path."""
    if project_root:
        try:
            rel = os.path.relpath(path, project_root)
        except ValueError:
            rel = ""
        if rel and not rel.startswith(".."):
            return "/" + rel.replace(os.sep, "/")
    return path


def thumb_path(cache_root: str, sha256: str, size: int = THUMB_SIZE) -> str:
    """The thumbnail of a file in the derived cache, keyed by its sha256:
    ``<cache>/ab/abcdef…_256.png``."""
    hexd = str(sha256 or "").split(":", 1)[-1].lower()
    return os.path.join(cache_root, hexd[:2], f"{hexd}_{size}.png")
