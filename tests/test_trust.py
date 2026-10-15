"""Q11 · TLS that trusts what this computer trusts — EM Tools' half.

Measured on 4 Oct 2026: Blender's Python verifies with its own certifi bundle,
so the dev node behind Caddy answered CERTIFICATE_VERIFY_FAILED — «Find» never
proposed it and a sign-in died at the code exchange.

The trust module moved to s3Dgraphy on 15 Oct 2026 (`room_import.trust`,
measured there by `tests/test_room_import_trust.py`: verification never turned
off, only the certificates the macOS settings allow). What stays here: every
call EM Tools makes to a node goes through it (or through `access`, which sends
through it), and EM Tools keeps no copy of the moved modules."""
import pathlib

_REPO = pathlib.Path(__file__).resolve().parent.parent
_MOVED = ("inventory.py", "asset_upload.py", "access.py", "trust.py")


def test_every_call_to_a_node_goes_through_it():
    """The bare stdlib call survives only as the fallback of a module loaded by
    path, outside the package (the suite). X1 · a call that carries an access
    goes through `access.urlopen`, which renews it and sends through `trust`."""
    for name in ("room.py", "servers.py", "scene_package.py", "file_states.py",
                 "handoff.py"):
        source = (_REPO / "sync_manager" / name).read_text(encoding="utf-8")
        assert ("from s3dgraphy.room_import.trust import" in source
                or "from s3dgraphy.room_import.access import" in source), name
        assert source.count("urllib.request.urlopen(") <= 1, name
    finder = (_REPO / "sync_manager" / "node_choice.py").read_text(encoding="utf-8")
    assert "probe(u, fetch=trust.fetch_json)" in finder
    assert "from s3dgraphy.room_import import trust" in finder


def test_the_moved_modules_have_no_copy_here():
    """MICRO-BRING-CHIAMA-IL-MOTORE · `inventory`, `asset_upload`, `access`,
    `trust` live in s3Dgraphy (`room_import`): two copies are two behaviours
    to correct. Nothing in the add-on imports them from here any more."""
    for name in _MOVED:
        assert not (_REPO / "sync_manager" / name).exists(), name
    stems = [n[:-3] for n in _MOVED]
    for path in _REPO.rglob("*.py"):
        rel = path.relative_to(_REPO).as_posix()
        if rel.startswith(("_dead_code/", "tests/", ".venv/", "build/", "wheels/")):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        for stem in stems:
            for bad in (f"from .{stem} import", f"from ..sync_manager.{stem} import",
                        f"from .sync_manager.{stem} import", f"sync_manager.{stem}\")"):
                assert bad not in source, f"{rel}: {bad}"
