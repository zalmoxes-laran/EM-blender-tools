"""Write-lock guard for GraphML files.

Every EMtools code path that writes to an existing .graphml on disk
(volatile Save GraphML, Bake Paradata, Create Host persistence,
Proxy Box Creator, StratiMiner export, xlsx→graphml, etc.) must
confirm the target file is actually writable BEFORE starting work.
The most common failure mode is the user keeping the .graphml open
in yEd: on Windows yEd holds an exclusive share lock, so our write
silently fails or corrupts the file; on macOS/Linux yEd does not
lock, but if we write while yEd is editing, the next yEd Save
overwrites our changes.

The helpers here are deliberately cheap and portable. Call
:func:`abort_if_graphml_locked` at the top of an operator's
``execute`` (or invoke): if it returns ``False`` the operator
already reported a user-facing error and should return
``{'CANCELLED'}``.
"""

from __future__ import annotations

import os
import platform
from typing import Tuple


def check_graphml_writable(path: str) -> Tuple[bool, str]:
    """Return ``(ok, reason)``. When ``ok`` is True, ``reason`` is empty.

    A non-existing file counts as writable provided its parent directory
    is writable — the caller is about to create it. For an existing
    file we (1) verify the OS-level write permission, (2) open it in
    ``r+b`` mode to flush out read-only holders, and (3) on Windows
    attempt a rename-to-self which fails if another process (yEd
    being the usual suspect) holds the file open exclusively.
    """
    if not path:
        return False, "No filepath provided"
    if not os.path.exists(path):
        parent = os.path.dirname(path) or "."
        if not os.access(parent, os.W_OK):
            return False, f"Parent directory not writable: {parent}"
        return True, ""
    if not os.access(path, os.W_OK):
        return False, f"File not writable (permissions): {path}"
    try:
        with open(path, "r+b"):
            pass
    except OSError as e:
        return False, f"Cannot open for write ({type(e).__name__}): {e}"
    if platform.system() == "Windows":
        # Rename-to-self is atomic on NTFS and raises PermissionError
        # when another process holds the file with deny-rename sharing
        # (e.g. yEd while editing).
        try:
            os.rename(path, path)
        except OSError as e:
            return False, (
                f"File is held by another process "
                f"(close yEd or other writers and retry): {e}"
            )
    return True, ""


def abort_if_graphml_locked(operator, path: str) -> bool:
    """Pre-flight check for Blender operators.

    Returns True when the caller can proceed. Returns False after
    calling ``operator.report({'ERROR'}, ...)`` with a user-facing
    message explaining why the .graphml is not writable.
    """
    ok, reason = check_graphml_writable(path)
    if not ok:
        operator.report(
            {'ERROR'},
            f"GraphML write-lock check failed: {reason}. "
            f"Close the file in yEd (or any other editor) and retry."
        )
    return ok
