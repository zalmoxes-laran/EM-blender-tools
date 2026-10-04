"""U4 · «Import from tables»: the pure decisions — the graph's code and the
em.json it is saved in — measured by tests/test_import_from_table.py."""

import os
import re
from typing import Callable, Dict, Optional


def graph_code_for(import_type: str, source: str, filters: Optional[Dict[str, str]] = None,
                   typed: str = "") -> str:
    """The code of the new graph: the one typed, else the table's name — the
    file's for an Excel or a SQLite database, the database's for PostgreSQL —
    followed by the values of the pyArchInit filters (one site, one area: the
    graph of that site)."""
    if typed.strip():
        return _safe(typed.strip())
    base = ""
    src = str(source or "")
    if src.startswith(("postgresql", "postgres")):
        base = src.rsplit("/", 1)[-1].split("?", 1)[0]
    elif src:
        name = os.path.basename(src)
        base = name.split(".", 1)[0] if name else ""
    parts = [base or import_type] + [str(v) for v in (filters or {}).values() if str(v).strip()]
    return _safe("_".join(parts))


def _safe(text: str) -> str:
    out = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return out or "graph"


def emjson_path_for(code: str, folder: str, exists: Callable[[str], bool] = os.path.exists,
                    typed: str = "") -> str:
    """Where the new graph is saved: the path typed (with .em.json added), else
    ``<folder>/<code>.em.json``; never over a file that is there — the next free
    ``<code>_2.em.json``, ``_3``… — because a table import must not overwrite
    somebody's project."""
    if typed.strip():
        path = typed.strip()
        if not path.endswith(".em.json"):
            path = (path[:-5] if path.endswith(".json") else path) + ".em.json"
    else:
        path = os.path.join(folder, f"{code}.em.json")
    if not exists(path):
        return path
    stem = path[: -len(".em.json")]
    n = 2
    while exists(f"{stem}_{n}.em.json"):
        n += 1
    return f"{stem}_{n}.em.json"
