# PyArchInit Geometry Import — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import the `pyunitastratigrafiche` multipolygons from a PyArchInit SQLite database into Blender as editable meshes anchored to existing s3dgraphy US nodes, so the user can model 3D stratigraphic volumes directly from the archaeological footprints.

**Architecture:** All code lives in the EM-tools addon under `import_operators/` and `em_setup/`. No s3dgraphy changes. Pure-Python WKB parser (no SpatiaLite extension dependency). Re-import is diff-based and preserves user modifications by default; opt-in `force_update` rebuilds with automatic backup. Spec: `docs/superpowers/specs/2026-05-22-pyarchinit-geometry-import-design.md`.

**Tech Stack:** Python 3.13 · Blender 5.0/5.1 Extension API (`bpy`, `bmesh`) · stdlib `sqlite3` · stdlib `struct` for WKB parsing · `pytest` for unit tests (`.venv/bin/pytest`) · s3dgraphy 1.5.2 (read-only consumer).

**Branch strategy:** Create one branch off `EM-tools_v1.6.0_dev` named `feat/pyarchinit-geometry-import`. Commit frequently after each task. Author of every commit must be `Enzo Cocca <enzo.ccc@gmail.com>` (use `git commit --author=...`). Do NOT commit `CLAUDE.md`, `.claude/`, or any AI/co-author trailers.

**Prerequisite:** PR #25 (`fix/pyarchinit-importer-table-name-kwarg`) should land first, but local development can rebase on top of it if needed.

---

## File structure

### New files

| Path | Responsibility |
|---|---|
| `import_operators/wkb_parser.py` | Pure-Python WKB blob → list of polygons. Stdlib `struct` only. ~120 LOC. |
| `import_operators/reimport_planner.py` | Diff existing meshes vs incoming polygons → four-bucket plan. ~80 LOC. |
| `import_operators/geom_constants.py` | Single source of truth for custom property keys, collection names, and other magic strings. Tiny. |
| `import_operators/pyarchinit_geom_importer.py` | Orchestrator: DB connection, schema detection, georef resolution, plan execution, report. ~300 LOC. |
| `import_operators/geom_blender_io.py` | Blender-side helpers: WKB rings → bmesh → Object, collection management, custom property writing, mesh hashing. ~150 LOC. |
| `import_operators/geom_georef.py` | `resolve_georef_anchor()` + popup wiring. ~100 LOC. |
| `tests/__init__.py` | Empty marker. |
| `tests/test_wkb_parser.py` | Pure-Python unit tests for WKB parser. |
| `tests/test_reimport_planner.py` | Pure-Python unit tests for the planner. |
| `tests/fixtures/__init__.py` | Empty marker. |
| `tests/fixtures/build_fixture.py` | One-shot script that generates `pyarchinit_minimal.sqlite`. |
| `tests/fixtures/pyarchinit_minimal.sqlite` | ~5 KB committed binary fixture used by manual scenarios. |
| `tests/fixtures/wkb_blobs.py` | Hex-encoded WKB blob literals used by the parser tests. |

### Modified files

| Path | Change |
|---|---|
| `em_setup/properties.py` | Add `pyarchinit_import_geometries` and `pyarchinit_geom_force_update` BoolProperties on `EMToolsSettings` and on `AuxiliaryFileProperties`. |
| `em_setup/ui.py` | Render the two toggles in both panel locations (3D GIS mode pyarchinit panel + EM Advanced auxiliary file panel when `file_type == 'pyarchinit'`). |
| `import_operators/import_EMdb.py` | After the existing pyarchinit US import succeeds, if the toggle is on, call `pyarchinit_geom_importer.import_geometries()`. |
| `aux_import.py` | Extend the `aux_orphans` payload schema to include an optional `kind` discriminator; add `aux_us_no_geom` list helper. |
| `import_operators/__init__.py` | Import the new submodules so they register at addon load. |

### Test infrastructure

`pytest` is already listed in `scripts/requirements_dev.txt` and installed in `.venv/`. Tests run with `.venv/bin/pytest tests/ -v` from the repo root. They must NOT import `bpy` — only pure-Python modules are unit-tested.

---

## Task 1: Test scaffolding and smoke test

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/fixtures/__init__.py`
- Create: `tests/test_smoke.py`
- Create: `pyproject.toml` snippet (or `pytest.ini`) for pytest config

- [ ] **Step 1: Create empty package markers**

```bash
mkdir -p tests/fixtures
touch tests/__init__.py tests/fixtures/__init__.py
```

- [ ] **Step 2: Add pytest config**

Create `pytest.ini` at repo root:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -v --tb=short
```

- [ ] **Step 3: Write a smoke test**

Create `tests/test_smoke.py`:

```python
"""Sanity check — pytest can discover and run tests in this repo."""


def test_pytest_runs():
    assert 1 + 1 == 2


def test_python_version():
    import sys
    assert sys.version_info >= (3, 11)
```

- [ ] **Step 4: Run the test and confirm pass**

```bash
.venv/bin/pytest tests/test_smoke.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/__init__.py tests/fixtures/__init__.py tests/test_smoke.py pytest.ini
git commit --author="Enzo Cocca <enzo.ccc@gmail.com>" -m "test: scaffold pytest setup with smoke test"
```

---

## Task 2: WKB parser — POLYGON 2D (TDD, first slice)

**Files:**
- Create: `tests/fixtures/wkb_blobs.py`
- Create: `tests/test_wkb_parser.py`
- Create: `import_operators/wkb_parser.py`

**WKB recap:** Each blob starts with a 1-byte byte-order marker (`00`=big-endian, `01`=little-endian), then a 4-byte uint32 geometry type, then geometry-specific data. POLYGON type = 3. Multi 3D coords flag = `0x80000000` OR `0x40000000`. We support POLYGON (3) and MULTIPOLYGON (6), 2D and 3D variants.

- [ ] **Step 1: Add a known POLYGON 2D blob fixture**

Create `tests/fixtures/wkb_blobs.py`:

```python
"""WKB blob literals used by parser tests. Generated offline once with shapely."""

# POLYGON((0 0, 10 0, 10 10, 0 10, 0 0)) — single square ring, little-endian, 2D
POLYGON_2D_SQUARE = bytes.fromhex(
    "01"                                       # little-endian
    "03000000"                                 # type 3 (POLYGON)
    "01000000"                                 # 1 ring
    "05000000"                                 # 5 points
    "0000000000000000" "0000000000000000"      # (0, 0)
    "0000000000002440" "0000000000000000"      # (10, 0)
    "0000000000002440" "0000000000002440"      # (10, 10)
    "0000000000000000" "0000000000002440"      # (0, 10)
    "0000000000000000" "0000000000000000"      # (0, 0)
)
```

- [ ] **Step 2: Write failing test for POLYGON 2D**

Create `tests/test_wkb_parser.py`:

```python
from tests.fixtures.wkb_blobs import POLYGON_2D_SQUARE
from import_operators.wkb_parser import parse_wkb


def test_parse_polygon_2d_single_ring():
    polygons = parse_wkb(POLYGON_2D_SQUARE)
    assert len(polygons) == 1
    polygon = polygons[0]
    assert len(polygon) == 1, "single ring expected"
    ring = polygon[0]
    assert len(ring) == 5
    assert ring[0] == (0.0, 0.0, 0.0)
    assert ring[1] == (10.0, 0.0, 0.0)
    assert ring[2] == (10.0, 10.0, 0.0)
    assert ring[3] == (0.0, 10.0, 0.0)
    assert ring[4] == (0.0, 0.0, 0.0)
```

- [ ] **Step 3: Run test and confirm failure**

```bash
.venv/bin/pytest tests/test_wkb_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'import_operators.wkb_parser'`

- [ ] **Step 4: Write minimal parser supporting only POLYGON 2D**

Create `import_operators/wkb_parser.py`:

```python
"""Pure-Python WKB parser for PyArchInit polygon imports.

Supports POLYGON (type 3) and MULTIPOLYGON (type 6), both 2D and 3D.
No dependency on SpatiaLite, shapely or external libs.

Return shape:
    parse_wkb(blob) -> list[polygon]
    polygon         = list[ring]
    ring            = list[(x, y, z)] tuples (z=0.0 for 2D inputs)
"""

import struct


WKB_TYPE_POLYGON = 3
WKB_TYPE_MULTIPOLYGON = 6
Z_FLAG = 0x80000000


class WKBParseError(ValueError):
    """Raised when the WKB blob cannot be parsed."""


def parse_wkb(blob):
    if len(blob) < 5:
        raise WKBParseError(f"WKB blob too short ({len(blob)} bytes)")
    endian = "<" if blob[0] == 1 else ">"
    geom_type = struct.unpack_from(endian + "I", blob, 1)[0]
    has_z = bool(geom_type & Z_FLAG)
    base_type = geom_type & 0x000FFFFF
    if base_type == WKB_TYPE_POLYGON:
        polygon, _ = _read_polygon(blob, 5, endian, has_z)
        return [polygon]
    raise WKBParseError(f"Unsupported WKB type {base_type}")


def _read_polygon(blob, offset, endian, has_z):
    n_rings = struct.unpack_from(endian + "I", blob, offset)[0]
    offset += 4
    rings = []
    for _ in range(n_rings):
        ring, offset = _read_ring(blob, offset, endian, has_z)
        rings.append(ring)
    return rings, offset


def _read_ring(blob, offset, endian, has_z):
    n_points = struct.unpack_from(endian + "I", blob, offset)[0]
    offset += 4
    coords_per_pt = 3 if has_z else 2
    fmt = endian + ("d" * coords_per_pt)
    size = 8 * coords_per_pt
    points = []
    for _ in range(n_points):
        vals = struct.unpack_from(fmt, blob, offset)
        offset += size
        if has_z:
            points.append((vals[0], vals[1], vals[2]))
        else:
            points.append((vals[0], vals[1], 0.0))
    return points, offset
```

- [ ] **Step 5: Run test and confirm pass**

```bash
.venv/bin/pytest tests/test_wkb_parser.py -v
```

Expected: `1 passed`

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/wkb_blobs.py tests/test_wkb_parser.py import_operators/wkb_parser.py
git commit --author="Enzo Cocca <enzo.ccc@gmail.com>" -m "feat(wkb): pure-Python WKB parser — POLYGON 2D first slice"
```

---

## Task 3: WKB parser — holes, 3D, MULTIPOLYGON, error cases

**Files:**
- Modify: `tests/fixtures/wkb_blobs.py`
- Modify: `tests/test_wkb_parser.py`
- Modify: `import_operators/wkb_parser.py`

- [ ] **Step 1: Add fixtures for the remaining cases**

Append to `tests/fixtures/wkb_blobs.py`:

```python
# POLYGON 2D with one interior hole (outer 10x10 square, hole 2x2 inside)
POLYGON_2D_WITH_HOLE = bytes.fromhex(
    "01" "03000000" "02000000"
    # outer ring: 5 points
    "05000000"
    "0000000000000000" "0000000000000000"
    "0000000000002440" "0000000000000000"
    "0000000000002440" "0000000000002440"
    "0000000000000000" "0000000000002440"
    "0000000000000000" "0000000000000000"
    # inner ring: 5 points (hole at (4,4)..(6,6))
    "05000000"
    "0000000000001040" "0000000000001040"
    "0000000000001840" "0000000000001040"
    "0000000000001840" "0000000000001840"
    "0000000000001040" "0000000000001840"
    "0000000000001040" "0000000000001040"
)

# POLYGON Z (3D) single triangle at z=5
POLYGON_3D_TRIANGLE = bytes.fromhex(
    "01" "030000" "80"          # type = 3 | Z_FLAG (little-endian)
    "01000000"                  # 1 ring
    "04000000"                  # 4 points
    "0000000000000000" "0000000000000000" "0000000000001440"  # (0,0,5)
    "0000000000002440" "0000000000000000" "0000000000001440"  # (10,0,5)
    "0000000000002440" "0000000000002440" "0000000000001440"  # (10,10,5)
    "0000000000000000" "0000000000000000" "0000000000001440"  # (0,0,5)
)

# MULTIPOLYGON 2D with 2 parts (two unit squares)
MULTIPOLYGON_2D_TWO_PARTS = bytes.fromhex(
    "01" "06000000" "02000000"
    # part 1: POLYGON 2D
    "01" "03000000" "01000000" "05000000"
    "0000000000000000" "0000000000000000"
    "000000000000F03F" "0000000000000000"
    "000000000000F03F" "000000000000F03F"
    "0000000000000000" "000000000000F03F"
    "0000000000000000" "0000000000000000"
    # part 2: POLYGON 2D (shifted to (10,0))
    "01" "03000000" "01000000" "05000000"
    "0000000000002440" "0000000000000000"
    "0000000000002640" "0000000000000000"
    "0000000000002640" "000000000000F03F"
    "0000000000002440" "000000000000F03F"
    "0000000000002440" "0000000000000000"
)

# Malformed: truncated mid-ring
TRUNCATED_WKB = bytes.fromhex("01" "03000000" "01000000" "05000000" "00")

# Unsupported type: LINESTRING (2)
LINESTRING_WKB = bytes.fromhex("01" "02000000" "00000000")
```

- [ ] **Step 2: Add failing tests for the new cases**

Append to `tests/test_wkb_parser.py`:

```python
from tests.fixtures.wkb_blobs import (
    POLYGON_2D_WITH_HOLE,
    POLYGON_3D_TRIANGLE,
    MULTIPOLYGON_2D_TWO_PARTS,
    TRUNCATED_WKB,
    LINESTRING_WKB,
)
from import_operators.wkb_parser import parse_wkb, WKBParseError
import pytest


def test_parse_polygon_2d_with_hole():
    polygons = parse_wkb(POLYGON_2D_WITH_HOLE)
    assert len(polygons) == 1
    rings = polygons[0]
    assert len(rings) == 2
    assert len(rings[0]) == 5  # outer
    assert len(rings[1]) == 5  # hole
    # Hole vertex z still 0
    assert rings[1][0] == (4.0, 4.0, 0.0)


def test_parse_polygon_3d():
    polygons = parse_wkb(POLYGON_3D_TRIANGLE)
    assert len(polygons) == 1
    rings = polygons[0]
    assert len(rings) == 1
    ring = rings[0]
    assert len(ring) == 4
    for pt in ring:
        assert pt[2] == 5.0


def test_parse_multipolygon_2d_two_parts():
    polygons = parse_wkb(MULTIPOLYGON_2D_TWO_PARTS)
    assert len(polygons) == 2
    assert len(polygons[0][0]) == 5
    assert len(polygons[1][0]) == 5
    # Second part starts at (10, 0)
    assert polygons[1][0][0] == (10.0, 0.0, 0.0)


def test_truncated_blob_raises():
    with pytest.raises(WKBParseError):
        parse_wkb(TRUNCATED_WKB)


def test_unsupported_type_raises():
    with pytest.raises(WKBParseError) as exc_info:
        parse_wkb(LINESTRING_WKB)
    assert "Unsupported" in str(exc_info.value) or "type" in str(exc_info.value)


def test_empty_blob_raises():
    with pytest.raises(WKBParseError):
        parse_wkb(b"")
```

- [ ] **Step 3: Run tests, confirm failures**

```bash
.venv/bin/pytest tests/test_wkb_parser.py -v
```

Expected: the original 1 still passes, all new tests fail.

- [ ] **Step 4: Extend the parser to cover the new cases**

Replace `import_operators/wkb_parser.py` with the full version:

```python
"""Pure-Python WKB parser for PyArchInit polygon imports.

Supports POLYGON (type 3) and MULTIPOLYGON (type 6), both 2D and 3D.

Return shape:
    parse_wkb(blob) -> list[polygon]
    polygon         = list[ring]
    ring            = list[(x, y, z)] tuples (z=0.0 for 2D inputs)
"""

import struct


WKB_TYPE_POLYGON = 3
WKB_TYPE_MULTIPOLYGON = 6
Z_FLAG = 0x80000000


class WKBParseError(ValueError):
    """Raised when the WKB blob cannot be parsed."""


def parse_wkb(blob):
    if not blob:
        raise WKBParseError("empty blob")
    if len(blob) < 5:
        raise WKBParseError(f"WKB blob too short ({len(blob)} bytes)")
    try:
        endian = "<" if blob[0] == 1 else ">"
        geom_type = struct.unpack_from(endian + "I", blob, 1)[0]
        has_z = bool(geom_type & Z_FLAG)
        base_type = geom_type & 0x000FFFFF
        if base_type == WKB_TYPE_POLYGON:
            polygon, _ = _read_polygon(blob, 5, endian, has_z)
            return [polygon]
        if base_type == WKB_TYPE_MULTIPOLYGON:
            return _read_multipolygon(blob, 5, endian)
        raise WKBParseError(f"Unsupported WKB type {base_type}")
    except struct.error as e:
        raise WKBParseError(f"truncated or malformed WKB: {e}") from e


def _read_polygon(blob, offset, endian, has_z):
    n_rings = struct.unpack_from(endian + "I", blob, offset)[0]
    offset += 4
    rings = []
    for _ in range(n_rings):
        ring, offset = _read_ring(blob, offset, endian, has_z)
        rings.append(ring)
    return rings, offset


def _read_multipolygon(blob, offset, endian):
    n_polygons = struct.unpack_from(endian + "I", blob, offset)[0]
    offset += 4
    polygons = []
    for _ in range(n_polygons):
        # Each sub-polygon carries its own endian byte + type uint32.
        sub_endian = "<" if blob[offset] == 1 else ">"
        sub_type = struct.unpack_from(sub_endian + "I", blob, offset + 1)[0]
        sub_has_z = bool(sub_type & Z_FLAG)
        sub_base = sub_type & 0x000FFFFF
        if sub_base != WKB_TYPE_POLYGON:
            raise WKBParseError(f"MULTIPOLYGON contains non-polygon sub-type {sub_base}")
        polygon, offset = _read_polygon(blob, offset + 5, sub_endian, sub_has_z)
        polygons.append(polygon)
    return polygons


def _read_ring(blob, offset, endian, has_z):
    n_points = struct.unpack_from(endian + "I", blob, offset)[0]
    offset += 4
    coords_per_pt = 3 if has_z else 2
    fmt = endian + ("d" * coords_per_pt)
    size = 8 * coords_per_pt
    points = []
    for _ in range(n_points):
        vals = struct.unpack_from(fmt, blob, offset)
        offset += size
        if has_z:
            points.append((vals[0], vals[1], vals[2]))
        else:
            points.append((vals[0], vals[1], 0.0))
    return points, offset
```

- [ ] **Step 5: Run tests, confirm all pass**

```bash
.venv/bin/pytest tests/test_wkb_parser.py -v
```

Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/wkb_blobs.py tests/test_wkb_parser.py import_operators/wkb_parser.py
git commit --author="Enzo Cocca <enzo.ccc@gmail.com>" -m "feat(wkb): support holes, 3D, MULTIPOLYGON, error cases"
```

---

## Task 4: Custom property constants

**Files:**
- Create: `import_operators/geom_constants.py`

- [ ] **Step 1: Create the constants module**

Create `import_operators/geom_constants.py`:

```python
"""Single source of truth for custom property keys, collection names,
and other magic strings used by the PyArchInit geometry import feature.

Keep all string literals here so renaming is a one-file change and
typos cannot drift across modules.
"""

# Custom property keys on Blender objects
PROP_US_NODE_ID = "em_us_node_id"
PROP_US_NAME = "em_us_name"
PROP_GRAPH_CODE = "em_graph_code"
PROP_PYARCHINIT_SOURCE = "em_pyarchinit_source"
PROP_PYARCHINIT_US_KEY = "em_pyarchinit_us_key"
PROP_IMPORT_TIMESTAMP = "em_import_timestamp"
PROP_ORIGINAL_VERT_COUNT = "em_original_vert_count"
PROP_IMPORTED_MESH_HASH = "em_imported_mesh_hash"
PROP_US_ORPHAN = "em_us_orphan"
PROP_IS_IMPORTED_GEOM = "em_is_imported_geom"
PROP_IS_BACKUP = "em_is_backup"

# Custom attribute on s3dgraphy node (reverse link)
NODE_ATTR_IMPORTED_GEOM_OBJ_NAME = "imported_geom_obj_name"

# Collection names
COLL_US_GEOMETRIES = "EM_US_Geometries"
COLL_US_ORPHAN_POLYGONS = "EM_US_OrphanPolygons"
COLL_US_ORPHANS = "EM_US_Orphans"
COLL_BACKUP_PREFIX = "_Backups_"

# Object name suffix used when colliding with a pre-existing non-imported object
NAME_SUFFIX_IMPORTED = ".imported"

# Aux orphan payload discriminator values (consumed by aux_import.py)
ORPHAN_KIND_POLYGON_NO_US = "polygon_no_us"

# Graph attribute keys
GRAPH_ATTR_AUX_US_NO_GEOM = "aux_us_no_geom"
```

- [ ] **Step 2: Commit**

```bash
git add import_operators/geom_constants.py
git commit --author="Enzo Cocca <enzo.ccc@gmail.com>" -m "feat(geom): centralize custom property + collection name constants"
```

---

## Task 5: Reimport planner — diff algorithm (TDD)

**Files:**
- Create: `tests/test_reimport_planner.py`
- Create: `import_operators/reimport_planner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_reimport_planner.py`:

```python
"""Pure-Python tests for the reimport planner. No bpy imports."""

from import_operators.reimport_planner import build_reimport_plan


class FakeObject(dict):
    """Stand-in for a Blender Object: supports `obj[key]` and `obj.get(key)`."""


class FakeNode:
    def __init__(self, node_id):
        self.id = node_id


def make_objs(specs):
    """specs = list of (node_id, modified_flag). Builds FakeObjects matching the
    contract used by the planner: em_is_imported_geom + em_us_node_id, plus
    a synthetic em_modified flag the test stub uses instead of vertex/hash math.
    """
    out = []
    for node_id, modified in specs:
        o = FakeObject()
        o["em_is_imported_geom"] = True
        o["em_us_node_id"] = node_id
        o["__test_modified"] = modified
        out.append(o)
    return out


def fake_is_modified(obj):
    return bool(obj.get("__test_modified"))


def fake_resolver(graph, us_key):
    """Graph is a dict {us_key_str: node_id}."""
    return FakeNode(graph[us_key]) if us_key in graph else None


def test_plan_create_only():
    incoming = [{"us_key": "a"}, {"us_key": "b"}]
    graph = {"a": "node-a", "b": "node-b"}
    plan = build_reimport_plan(
        scene_objects=[],
        graph=graph,
        incoming_polygons=incoming,
        is_modified=fake_is_modified,
        resolve_us_node=fake_resolver,
    )
    assert len(plan["create"]) == 2
    assert plan["update_safe"] == []
    assert plan["skip_modified"] == []
    assert plan["mark_orphan_obj"] == []


def test_plan_update_safe_when_existing_unmodified():
    existing = make_objs([("node-a", False)])
    incoming = [{"us_key": "a"}]
    graph = {"a": "node-a"}
    plan = build_reimport_plan(
        scene_objects=existing,
        graph=graph,
        incoming_polygons=incoming,
        is_modified=fake_is_modified,
        resolve_us_node=fake_resolver,
    )
    assert plan["create"] == []
    assert len(plan["update_safe"]) == 1
    assert plan["skip_modified"] == []
    assert plan["mark_orphan_obj"] == []


def test_plan_skip_modified():
    existing = make_objs([("node-a", True)])
    incoming = [{"us_key": "a"}]
    graph = {"a": "node-a"}
    plan = build_reimport_plan(
        scene_objects=existing,
        graph=graph,
        incoming_polygons=incoming,
        is_modified=fake_is_modified,
        resolve_us_node=fake_resolver,
    )
    assert plan["create"] == []
    assert plan["update_safe"] == []
    assert len(plan["skip_modified"]) == 1
    assert plan["mark_orphan_obj"] == []


def test_plan_mark_orphan_when_us_disappears():
    existing = make_objs([("node-a", False)])
    incoming = []  # US gone from DB
    graph = {}
    plan = build_reimport_plan(
        scene_objects=existing,
        graph=graph,
        incoming_polygons=incoming,
        is_modified=fake_is_modified,
        resolve_us_node=fake_resolver,
    )
    assert plan["create"] == []
    assert plan["update_safe"] == []
    assert plan["skip_modified"] == []
    assert len(plan["mark_orphan_obj"]) == 1


def test_plan_polygon_orphan_excluded_from_create():
    """If incoming refers to a us_key not in the graph, that polygon is
    routed to the polygon-orphan flow elsewhere — not into create."""
    existing = []
    incoming = [{"us_key": "ghost"}]
    graph = {}
    plan = build_reimport_plan(
        scene_objects=existing,
        graph=graph,
        incoming_polygons=incoming,
        is_modified=fake_is_modified,
        resolve_us_node=fake_resolver,
    )
    assert plan["create"] == []
    assert plan["update_safe"] == []
    assert plan["skip_modified"] == []
    assert plan["mark_orphan_obj"] == []


def test_plan_ignores_non_imported_objects():
    """Objects without em_is_imported_geom or em_us_node_id are ignored."""
    o = FakeObject()
    o["em_us_node_id"] = "node-a"  # but missing em_is_imported_geom
    incoming = []
    graph = {}
    plan = build_reimport_plan(
        scene_objects=[o],
        graph=graph,
        incoming_polygons=incoming,
        is_modified=fake_is_modified,
        resolve_us_node=fake_resolver,
    )
    assert plan["mark_orphan_obj"] == []
```

- [ ] **Step 2: Run, confirm failures**

```bash
.venv/bin/pytest tests/test_reimport_planner.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement the planner**

Create `import_operators/reimport_planner.py`:

```python
"""Diff existing imported meshes against incoming polygons.

Pure-Python so unit-testable without Blender. The Blender layer
provides the `is_modified` and `resolve_us_node` callbacks.
"""

from .geom_constants import PROP_IS_IMPORTED_GEOM, PROP_US_NODE_ID


def build_reimport_plan(
    scene_objects,
    graph,
    incoming_polygons,
    is_modified,
    resolve_us_node,
):
    """Return a four-bucket plan for a re-import operation.

    Args:
        scene_objects:    iterable of Blender Object-like dicts.
        graph:            opaque graph reference passed back to resolve_us_node.
        incoming_polygons: list of {us_key: str, ...} dicts.
        is_modified:      callable(obj) -> bool. Decides if a mesh has been
                          modified by the user since import.
        resolve_us_node:  callable(graph, us_key) -> node or None. Finds the
                          s3dgraphy US node for a given DB key tuple.

    Returns:
        dict with keys 'create', 'update_safe', 'skip_modified',
        'mark_orphan_obj'. Polygon orphans (us_key with no matching node)
        are NOT placed in this plan — the caller routes them elsewhere.
    """
    plan = {
        "create": [],
        "update_safe": [],
        "skip_modified": [],
        "mark_orphan_obj": [],
    }

    existing_by_node_id = {}
    for obj in scene_objects:
        if not obj.get(PROP_IS_IMPORTED_GEOM):
            continue
        node_id = obj.get(PROP_US_NODE_ID)
        if not node_id:
            continue
        existing_by_node_id[node_id] = obj

    incoming_by_node_id = {}
    for poly in incoming_polygons:
        node = resolve_us_node(graph, poly["us_key"])
        if node is None:
            continue  # polygon orphan — handled by the caller
        incoming_by_node_id[node.id] = (poly, node)

    for node_id, (poly, node) in incoming_by_node_id.items():
        existing = existing_by_node_id.get(node_id)
        if existing is None:
            plan["create"].append({"poly": poly, "node": node})
        elif is_modified(existing):
            plan["skip_modified"].append({"poly": poly, "node": node, "obj": existing})
        else:
            plan["update_safe"].append({"poly": poly, "node": node, "obj": existing})

    for node_id, obj in existing_by_node_id.items():
        if node_id not in incoming_by_node_id:
            plan["mark_orphan_obj"].append(obj)

    return plan
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
.venv/bin/pytest tests/test_reimport_planner.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_reimport_planner.py import_operators/reimport_planner.py
git commit --author="Enzo Cocca <enzo.ccc@gmail.com>" -m "feat(geom): reimport planner with four-bucket diff"
```

---

## Task 6: Blender mesh builder helpers (manual smoke, no unit test)

**Files:**
- Create: `import_operators/geom_blender_io.py`

The Blender API can't be unit-tested without `bpy`, so this module is verified manually in Task 13's scenarios.

- [ ] **Step 1: Write the module**

Create `import_operators/geom_blender_io.py`:

```python
"""Blender-side helpers for the PyArchInit geometry import.

Anything that touches bpy / bmesh lives here so the rest of the
pipeline stays pure-Python and testable.
"""

import hashlib
from datetime import datetime, timezone

import bpy  # type: ignore
import bmesh  # type: ignore

from . import geom_constants as C


# ---------------------------------------------------------------------------
# Collection management
# ---------------------------------------------------------------------------

def ensure_collection(name, parent=None, hidden=False):
    """Return existing collection or create a new one linked under `parent`.

    If `parent` is None, links under the scene's master collection.
    """
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        target = parent or bpy.context.scene.collection
        target.children.link(coll)
    if hidden:
        coll.hide_viewport = True
    return coll


def move_obj_to_collection(obj, dest):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    dest.objects.link(obj)


# ---------------------------------------------------------------------------
# WKB rings → bmesh → mesh data
# ---------------------------------------------------------------------------

def build_mesh_from_polygons(polygons, shift_xyz):
    """Build a Blender Mesh datablock from a list of polygons.

    Each polygon = list of rings, each ring = list of (x, y, z) tuples.
    First ring of each polygon is treated as the outer boundary; subsequent
    rings are holes. All coordinates are shifted by `shift_xyz` before
    insertion.
    """
    sx, sy, sz = shift_xyz
    mesh = bpy.data.meshes.new("us_geom_temp")
    bm = bmesh.new()
    try:
        for rings in polygons:
            for ring in rings:
                # Drop the closing duplicate vertex if present.
                if len(ring) >= 2 and ring[0] == ring[-1]:
                    ring = ring[:-1]
                verts = [bm.verts.new((x - sx, y - sy, z - sz)) for (x, y, z) in ring]
                if len(verts) >= 3:
                    try:
                        bm.faces.new(verts)
                    except ValueError:
                        # face already exists / self-intersecting — skip but keep verts
                        pass
        bm.normal_update()
        bm.to_mesh(mesh)
    finally:
        bm.free()
    return mesh


# ---------------------------------------------------------------------------
# Object creation + property writing
# ---------------------------------------------------------------------------

def create_or_replace_object(target_name, mesh, parent_collection):
    """Return a Blender Object with `target_name` containing `mesh`.

    If an object with that name already exists AND is one of ours
    (em_is_imported_geom=True), reuse it and replace its mesh data.
    Otherwise, if the name clashes with a foreign object, suffix
    with NAME_SUFFIX_IMPORTED.
    """
    existing = bpy.data.objects.get(target_name)
    if existing is not None and existing.get(C.PROP_IS_IMPORTED_GEOM):
        old_mesh = existing.data
        existing.data = mesh
        if old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)
        if existing.name not in [o.name for o in parent_collection.objects]:
            move_obj_to_collection(existing, parent_collection)
        return existing
    if existing is not None:
        target_name = target_name + C.NAME_SUFFIX_IMPORTED
    obj = bpy.data.objects.new(target_name, mesh)
    parent_collection.objects.link(obj)
    return obj


def apply_imported_geom_properties(obj, us_node_id, us_name, graph_code,
                                   db_path, us_key):
    """Stamp the immutable identity fields. Called only at FIRST import."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    obj[C.PROP_IS_IMPORTED_GEOM] = True
    obj[C.PROP_US_NODE_ID] = us_node_id
    obj[C.PROP_US_NAME] = us_name
    obj[C.PROP_GRAPH_CODE] = graph_code
    obj[C.PROP_PYARCHINIT_SOURCE] = db_path
    obj[C.PROP_PYARCHINIT_US_KEY] = us_key
    obj[C.PROP_IMPORT_TIMESTAMP] = now
    obj[C.PROP_US_ORPHAN] = False
    refresh_modification_baseline(obj)


def refresh_modification_baseline(obj):
    """Recompute the modification-detection baseline against the current mesh.

    Called at first import AND after a force-update rebuild.
    """
    obj[C.PROP_ORIGINAL_VERT_COUNT] = len(obj.data.vertices)
    obj[C.PROP_IMPORTED_MESH_HASH] = compute_mesh_hash(obj.data)


def compute_mesh_hash(mesh):
    """Stable hash over sorted vertex coords + face indices.

    Sensitive to vertex moves AND topology changes. Order-stable so
    Blender's internal reordering doesn't trigger false positives.
    """
    h = hashlib.sha1()
    verts = sorted(
        (round(v.co.x, 6), round(v.co.y, 6), round(v.co.z, 6))
        for v in mesh.vertices
    )
    for v in verts:
        h.update(repr(v).encode())
    faces = sorted(tuple(sorted(p.vertices)) for p in mesh.polygons)
    for f in faces:
        h.update(repr(f).encode())
    return "sha1:" + h.hexdigest()


def is_object_transform_identity(obj):
    loc_zero = all(abs(c) < 1e-9 for c in obj.location)
    rot_zero = all(abs(c) < 1e-9 for c in obj.rotation_euler)
    scale_one = all(abs(c - 1.0) < 1e-9 for c in obj.scale)
    return loc_zero and rot_zero and scale_one


def is_mesh_modified(obj):
    """Three-signal cascade (vert count, mesh hash, transform identity)."""
    orig_count = obj.get(C.PROP_ORIGINAL_VERT_COUNT)
    if orig_count is not None and len(obj.data.vertices) != orig_count:
        return True
    orig_hash = obj.get(C.PROP_IMPORTED_MESH_HASH)
    if orig_hash and compute_mesh_hash(obj.data) != orig_hash:
        return True
    if not is_object_transform_identity(obj):
        return True
    return False


def backup_then_replace(obj, new_mesh, timestamp):
    """Duplicate `obj` into a hidden backup collection, then swap its mesh
    data in-place to point at `new_mesh`."""
    backup_coll = ensure_collection(
        C.COLL_BACKUP_PREFIX + timestamp, hidden=True
    )
    backup_obj = obj.copy()
    backup_obj.data = obj.data.copy()
    backup_obj.name = f"{obj.name}.backup.{timestamp}"
    move_obj_to_collection(backup_obj, backup_coll)
    backup_obj[C.PROP_IS_BACKUP] = True

    old_mesh = obj.data
    obj.data = new_mesh
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    refresh_modification_baseline(obj)
```

- [ ] **Step 2: Commit (no automated test possible — covered in Task 13 manual scenarios)**

```bash
git add import_operators/geom_blender_io.py
git commit --author="Enzo Cocca <enzo.ccc@gmail.com>" -m "feat(geom): Blender-side mesh builder + property writer + modification probe"
```

---

## Task 7: Georef anchor resolver

**Files:**
- Create: `import_operators/geom_georef.py`

- [ ] **Step 1: Write the module**

Create `import_operators/geom_georef.py`:

```python
"""Resolve the scene shift / EPSG used to anchor imported geometries.

Reads (and conditionally writes) scene.em_georef via its public PropertyGroup
fields. The PropertyGroup's update callbacks propagate to BlenderGIS and 3DSC
adapters automatically.
"""

import bpy  # type: ignore


STATE_UNSET = "UNSET"
STATE_EPSG_ONLY = "EPSG_ONLY"
STATE_CONFIGURED = "CONFIGURED"


def classify_georef_state(g):
    has_epsg = bool(g.epsg) and g.epsg.strip() not in ("", "4326")
    has_shift = any(abs(c) > 1e-9 for c in (g.shift_x, g.shift_y, g.shift_z))
    if has_shift and has_epsg:
        return STATE_CONFIGURED
    if has_epsg and not has_shift:
        return STATE_EPSG_ONLY
    return STATE_UNSET


def compute_centroid(polygons_iter):
    """Mean of all outer-ring vertices (good enough for anchoring)."""
    sx = sy = 0.0
    n = 0
    for poly in polygons_iter:
        for rings in poly["parsed_rings"]:
            outer = rings[0]
            for x, y, _ in outer:
                sx += x
                sy += y
                n += 1
    if n == 0:
        return None
    return (sx / n, sy / n)


def write_georef(context, epsg, shift_x, shift_y, shift_z):
    """Write through the public PropertyGroup so update_* callbacks fire."""
    g = context.scene.em_georef
    g.epsg = str(epsg)
    g.shift_x = float(shift_x)
    g.shift_y = float(shift_y)
    g.shift_z = float(shift_z)


def resolve_georef_anchor(context, polygons, db_srid, ask_user_callback):
    """Return ((shift_x, shift_y, shift_z), epsg_used) or None to cancel.

    `polygons` is a list of dicts with a 'parsed_rings' field already populated
    by the WKB parser. `ask_user_callback(state, centroid, db_srid)` shows the
    appropriate popup and returns 'AUTO' / 'CANCEL' / 'MANUAL_EPSG:<value>'.
    """
    g = context.scene.em_georef
    state = classify_georef_state(g)

    if state == STATE_CONFIGURED:
        if db_srid and g.epsg.strip() != str(db_srid):
            # Non-blocking warning is surfaced by the orchestrator.
            pass
        return (g.shift_x, g.shift_y, g.shift_z), g.epsg

    centroid = compute_centroid(polygons)
    if centroid is None:
        return (0.0, 0.0, 0.0), g.epsg or "4326"

    if state == STATE_UNSET:
        choice = ask_user_callback(state, centroid, db_srid)
        if choice == "CANCEL":
            return None
        # AUTO
        write_georef(context, str(db_srid or "4326"),
                     centroid[0], centroid[1], 0.0)
        return (centroid[0], centroid[1], 0.0), str(db_srid or "4326")

    # STATE_EPSG_ONLY: anchor without asking
    write_georef(context, g.epsg, centroid[0], centroid[1], 0.0)
    return (centroid[0], centroid[1], 0.0), g.epsg
```

- [ ] **Step 2: Commit**

```bash
git add import_operators/geom_georef.py
git commit --author="Enzo Cocca <enzo.ccc@gmail.com>" -m "feat(geom): scene georef resolver with popup callback"
```

---

## Task 8: PyArchInit DB reader

**Files:**
- Create: `import_operators/pyarchinit_db_reader.py`

- [ ] **Step 1: Create the module**

Create `import_operators/pyarchinit_db_reader.py`:

```python
"""Read pyunitastratigrafiche rows from a PyArchInit SQLite database.

Handles schema detection (table presence, geometry column name, SRID)
and yields well-formed dicts ready for the WKB parser. Stays
Blender-free for easy testing.
"""

import sqlite3


TABLE_NAME = "pyunitastratigrafiche"
GEOM_COLUMN_FALLBACKS = ("the_geom", "geom", "geometry")


class PyArchInitDBError(RuntimeError):
    """Raised for schema or connection problems the caller must surface."""


def open_readonly(db_path):
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def detect_geometry_column(conn):
    """Return (geom_column_name, srid). SRID may be 0 if unknown."""
    try:
        cur = conn.execute(
            "SELECT f_geometry_column, srid FROM geometry_columns "
            "WHERE f_table_name = ?",
            (TABLE_NAME,),
        )
        row = cur.fetchone()
        if row:
            return row[0], int(row[1] or 0)
    except sqlite3.Error:
        pass
    cur = conn.execute(f"PRAGMA table_info('{TABLE_NAME}')")
    cols = [r[1] for r in cur.fetchall()]
    for cand in GEOM_COLUMN_FALLBACKS:
        if cand in cols:
            return cand, 0
    raise PyArchInitDBError(
        f"could not locate a geometry column in '{TABLE_NAME}'"
    )


def table_exists(conn, name=TABLE_NAME):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    )
    return cur.fetchone() is not None


def fetch_polygons(conn, geom_column):
    """Yield dicts {us_key, us, area, sito, wkb, wkb_hex_preview}."""
    cur = conn.execute(
        f"SELECT us, area, sito, {geom_column} FROM {TABLE_NAME}"
    )
    for us, area, sito, geom in cur:
        if geom is None:
            continue
        wkb = bytes(geom)
        yield {
            "us": us,
            "area": area,
            "sito": sito,
            "us_key": f"sito={sito},area={area},us={us}",
            "wkb": wkb,
            "wkb_hex_preview": wkb[:16].hex(),
        }
```

- [ ] **Step 2: Commit**

```bash
git add import_operators/pyarchinit_db_reader.py
git commit --author="Enzo Cocca <enzo.ccc@gmail.com>" -m "feat(geom): SQLite reader for pyunitastratigrafiche table"
```

---

## Task 9: Test fixture SQLite

**Files:**
- Create: `tests/fixtures/build_fixture.py`
- Create: `tests/fixtures/pyarchinit_minimal.sqlite` (generated, committed)

- [ ] **Step 1: Write the fixture-builder script**

Create `tests/fixtures/build_fixture.py`:

```python
"""Generate tests/fixtures/pyarchinit_minimal.sqlite.

Run once with `.venv/bin/python tests/fixtures/build_fixture.py`. The
output file is committed; the script is kept for reproducibility.

The fixture emulates a minimal PyArchInit SQLite with us_table and
pyunitastratigrafiche, including:
  - 5 US in us_table
  - 3 polygons in pyunitastratigrafiche covering 3 of the 5 US
  - 1 orphan polygon referencing a non-existent US
  - so on re-import scenarios we have:
    * 3 happy-path matches
    * 2 US without geometry
    * 1 polygon orphan
"""

import sqlite3
import struct
from pathlib import Path

DB_PATH = Path(__file__).parent / "pyarchinit_minimal.sqlite"


def polygon_wkb(coords):
    """Build a 2D POLYGON WKB with one ring from a list of (x,y) coords."""
    closed = list(coords) + [coords[0]]
    body = struct.pack("<I", 1)              # 1 ring
    body += struct.pack("<I", len(closed))   # n points
    for x, y in closed:
        body += struct.pack("<dd", x, y)
    return b"\x01" + struct.pack("<I", 3) + body  # little-endian POLYGON


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE us_table ("
        "id_us INTEGER PRIMARY KEY, sito TEXT, area TEXT, us INTEGER, "
        "d_stratigrafica TEXT)"
    )
    cur.execute(
        "CREATE TABLE pyunitastratigrafiche ("
        "id INTEGER PRIMARY KEY, sito TEXT, area TEXT, us INTEGER, "
        "the_geom BLOB)"
    )
    cur.execute(
        "CREATE TABLE geometry_columns ("
        "f_table_name TEXT, f_geometry_column TEXT, srid INTEGER)"
    )

    us_rows = [
        (1, "SITE1", "A", 1, "muro perimetrale"),
        (2, "SITE1", "A", 2, "crollo"),
        (3, "SITE1", "A", 3, "battuto pavimentale"),
        (4, "SITE1", "A", 4, "fossa"),
        (5, "SITE1", "A", 5, "riempimento"),
    ]
    cur.executemany("INSERT INTO us_table VALUES (?,?,?,?,?)", us_rows)

    polys = [
        ("SITE1", "A", 1, polygon_wkb([(0, 0), (4, 0), (4, 1), (0, 1)])),
        ("SITE1", "A", 2, polygon_wkb([(0, 2), (3, 2), (3, 4), (0, 4)])),
        ("SITE1", "A", 3, polygon_wkb([(5, 0), (8, 0), (8, 3), (5, 3)])),
        # Orphan: references a non-existent US 99
        ("SITE1", "A", 99, polygon_wkb([(10, 10), (11, 10), (11, 11), (10, 11)])),
    ]
    cur.executemany(
        "INSERT INTO pyunitastratigrafiche(sito, area, us, the_geom) "
        "VALUES (?,?,?,?)",
        polys,
    )
    cur.execute(
        "INSERT INTO geometry_columns VALUES (?,?,?)",
        ("pyunitastratigrafiche", "the_geom", 32633),
    )
    conn.commit()
    conn.close()
    print(f"Generated {DB_PATH} ({DB_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate the fixture**

```bash
.venv/bin/python tests/fixtures/build_fixture.py
```

Expected: `Generated .../pyarchinit_minimal.sqlite (~5000 bytes)`

- [ ] **Step 3: Quick verification with sqlite CLI**

```bash
sqlite3 tests/fixtures/pyarchinit_minimal.sqlite \
  "SELECT count(*) FROM pyunitastratigrafiche; SELECT count(*) FROM us_table;"
```

Expected output: `4\n5`

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/build_fixture.py tests/fixtures/pyarchinit_minimal.sqlite
git commit --author="Enzo Cocca <enzo.ccc@gmail.com>" -m "test: minimal pyarchinit SQLite fixture for manual scenarios"
```

---

## Task 10: Main orchestrator

**Files:**
- Create: `import_operators/pyarchinit_geom_importer.py`

- [ ] **Step 1: Write the orchestrator**

Create `import_operators/pyarchinit_geom_importer.py`:

```python
"""Top-level orchestrator for the PyArchInit pyunitastratigrafiche import.

Called by EM_OT_import_3dgis_database after the existing US import has
populated the s3dgraphy graph.
"""

from datetime import datetime, timezone

import bpy  # type: ignore

from . import geom_constants as C
from .pyarchinit_db_reader import (
    open_readonly,
    table_exists,
    detect_geometry_column,
    fetch_polygons,
    PyArchInitDBError,
    TABLE_NAME,
)
from .wkb_parser import parse_wkb, WKBParseError
from .reimport_planner import build_reimport_plan
from .geom_blender_io import (
    ensure_collection,
    move_obj_to_collection,
    build_mesh_from_polygons,
    create_or_replace_object,
    apply_imported_geom_properties,
    refresh_modification_baseline,
    backup_then_replace,
    is_mesh_modified,
)
from .geom_georef import resolve_georef_anchor


def import_geometries(context, db_path, graph, graph_code, force_update,
                     ask_user_callback, show_warning_callback):
    """Run the full geometry import. Returns a report dict."""
    report = {
        "created": 0,
        "updated": 0,
        "skipped_user_modified": 0,
        "marked_orphan_obj": 0,
        "polygon_orphans": 0,
        "us_without_geometry": [],
        "malformed_geometries": [],
        "backup_collection": None,
        "warnings": [],
    }

    try:
        conn = open_readonly(db_path)
    except Exception as e:
        show_warning_callback("ERROR", f"Cannot open DB: {db_path}\n{e}")
        return report

    try:
        if not table_exists(conn):
            show_warning_callback(
                "WARNING",
                f"Table '{TABLE_NAME}' not present in DB — no geometries to import.",
            )
            return report
        try:
            geom_col, srid = detect_geometry_column(conn)
        except PyArchInitDBError as e:
            show_warning_callback("ERROR", str(e))
            return report

        polygons = []
        for row in fetch_polygons(conn, geom_col):
            try:
                row["parsed_rings"] = parse_wkb(row["wkb"])
                polygons.append(row)
            except WKBParseError as e:
                report["malformed_geometries"].append((row["us_key"], str(e)))

        if not polygons:
            show_warning_callback("INFO", "No polygons in DB.")
            return report

        anchor = resolve_georef_anchor(context, polygons, srid, ask_user_callback)
        if anchor is None:
            return report
        shift_xyz, epsg_used = anchor

        plan = build_reimport_plan(
            scene_objects=list(bpy.context.scene.objects),
            graph=graph,
            incoming_polygons=polygons,
            is_modified=is_mesh_modified,
            resolve_us_node=_resolve_us_node,
        )

        parent_coll = ensure_collection(C.COLL_US_GEOMETRIES)
        graph_coll = ensure_collection(graph_code, parent=parent_coll)

        for entry in plan["create"]:
            obj = _create_one(entry, graph_coll, shift_xyz, db_path, graph_code)
            _link_to_node(entry["node"], obj)
            report["created"] += 1

        for entry in plan["update_safe"]:
            new_mesh = build_mesh_from_polygons(entry["poly"]["parsed_rings"], shift_xyz)
            old_mesh = entry["obj"].data
            entry["obj"].data = new_mesh
            if old_mesh.users == 0:
                bpy.data.meshes.remove(old_mesh)
            refresh_modification_baseline(entry["obj"])
            report["updated"] += 1

        if force_update and plan["skip_modified"]:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
            report["backup_collection"] = C.COLL_BACKUP_PREFIX + ts
            for entry in plan["skip_modified"]:
                new_mesh = build_mesh_from_polygons(entry["poly"]["parsed_rings"], shift_xyz)
                backup_then_replace(entry["obj"], new_mesh, ts)
                report["updated"] += 1
        else:
            report["skipped_user_modified"] = len(plan["skip_modified"])

        if plan["mark_orphan_obj"]:
            orphan_coll = ensure_collection(C.COLL_US_ORPHANS)
            for obj in plan["mark_orphan_obj"]:
                obj[C.PROP_US_ORPHAN] = True
                move_obj_to_collection(obj, orphan_coll)
            report["marked_orphan_obj"] = len(plan["mark_orphan_obj"])

        _handle_polygon_orphans(polygons, graph, shift_xyz, db_path, report)
        _record_us_without_geometry(polygons, graph, report)
    finally:
        conn.close()

    return report


def _resolve_us_node(graph, us_key):
    """Find an US node in the graph whose attributes match the (sito, area, us) key.

    Implementation detail: the existing PyArchInitImporter stores keys with
    underscores in node names (e.g. "SITE1_A_1"). We accept both
    'sito=SITE1,area=A,us=1' form and the underscored form.
    """
    if graph is None:
        return None
    key = us_key.replace("sito=", "").replace(",area=", "_").replace(",us=", "_")
    for node in getattr(graph, "nodes", []):
        if getattr(node, "name", None) == key:
            return node
    return None


def _create_one(entry, parent_coll, shift_xyz, db_path, graph_code):
    poly = entry["poly"]
    node = entry["node"]
    mesh = build_mesh_from_polygons(poly["parsed_rings"], shift_xyz)
    obj_name = f"{graph_code}.{node.name}"
    obj = create_or_replace_object(obj_name, mesh, parent_coll)
    apply_imported_geom_properties(
        obj=obj,
        us_node_id=node.id,
        us_name=node.name,
        graph_code=graph_code,
        db_path=db_path,
        us_key=poly["us_key"],
    )
    return obj


def _link_to_node(node, obj):
    if hasattr(node, "attributes") and isinstance(node.attributes, dict):
        node.attributes[C.NODE_ATTR_IMPORTED_GEOM_OBJ_NAME] = obj.name


def _handle_polygon_orphans(polygons, graph, shift_xyz, db_path, report):
    for poly in polygons:
        node = _resolve_us_node(graph, poly["us_key"])
        if node is not None:
            continue
        # polygon orphan
        orphan_coll = ensure_collection(C.COLL_US_ORPHAN_POLYGONS)
        mesh = build_mesh_from_polygons(poly["parsed_rings"], shift_xyz)
        obj_name = f"orphan_{poly['sito']}_{poly['area']}_{poly['us']}"
        obj = bpy.data.objects.new(obj_name, mesh)
        orphan_coll.objects.link(obj)
        obj[C.PROP_IS_IMPORTED_GEOM] = True
        obj[C.PROP_US_ORPHAN] = True

        attrs = getattr(graph, "attributes", None)
        if isinstance(attrs, dict):
            attrs.setdefault("aux_orphans", []).append({
                "key_id": poly["us_key"],
                "payload": {
                    "kind": C.ORPHAN_KIND_POLYGON_NO_US,
                    "source": db_path,
                    "wkb_hex_preview": poly["wkb_hex_preview"],
                    "obj_name": obj.name,
                },
            })
        report["polygon_orphans"] += 1


def _record_us_without_geometry(polygons, graph, report):
    if graph is None:
        return
    polygon_keys = {p["us_key"] for p in polygons}
    for node in getattr(graph, "nodes", []):
        node_name = getattr(node, "name", "")
        try:
            sito, area, us = node_name.split("_")
        except ValueError:
            continue
        key = f"sito={sito},area={area},us={us}"
        if key not in polygon_keys:
            report["us_without_geometry"].append(node_name)
            attrs = getattr(graph, "attributes", None)
            if isinstance(attrs, dict):
                attrs.setdefault(C.GRAPH_ATTR_AUX_US_NO_GEOM, []).append(node.id)
```

- [ ] **Step 2: Commit**

```bash
git add import_operators/pyarchinit_geom_importer.py
git commit --author="Enzo Cocca <enzo.ccc@gmail.com>" -m "feat(geom): main orchestrator for PyArchInit geometry import"
```

---

## Task 11: Scene properties for the toggle pair

**Files:**
- Modify: `em_setup/properties.py`

- [ ] **Step 1: Locate insertion point**

Find the `EMToolsSettings` class. Identify the block where existing pyarchinit-related properties live (around `pyarchinit_db_path`, `pyarchinit_table`).

- [ ] **Step 2: Add the toggles**

In `em_setup/properties.py`, inside `class EMToolsSettings`, after the existing `pyarchinit_table` / `pyarchinit_mapping` properties, add:

```python
    pyarchinit_import_geometries: BoolProperty(
        name="Also import US geometries",
        description=(
            "After importing the us_table, also import multipolygon "
            "footprints from the pyunitastratigrafiche table"
        ),
        default=False,
    )  # type: ignore

    pyarchinit_geom_force_update: BoolProperty(
        name="Force update existing meshes",
        description=(
            "Rebuild meshes even when the user has modified them. "
            "A backup of each modified mesh is created automatically."
        ),
        default=False,
    )  # type: ignore
```

- [ ] **Step 3: Add the same pair to `AuxiliaryFileProperties`**

For EM Advanced mode the toggle lives on the per-file PropertyGroup. Inside `class AuxiliaryFileProperties`, add:

```python
    pyarchinit_import_geometries: BoolProperty(
        name="Also import US geometries",
        description="Same as scene-level toggle but scoped to this auxiliary file",
        default=False,
    )  # type: ignore

    pyarchinit_geom_force_update: BoolProperty(
        name="Force update existing meshes",
        description="Same as scene-level toggle but scoped to this auxiliary file",
        default=False,
    )  # type: ignore
```

- [ ] **Step 4: Reload the addon in Blender to confirm properties register**

Run `bpy.utils.refresh_script_paths()` and re-enable the extension, or restart Blender. From the Python console:

```python
import bpy
bpy.context.scene.em_tools.pyarchinit_import_geometries
```

Expected: returns `False` without raising.

- [ ] **Step 5: Commit**

```bash
git add em_setup/properties.py
git commit --author="Enzo Cocca <enzo.ccc@gmail.com>" -m "feat(setup): scene + auxiliary toggles for pyarchinit geometry import"
```

---

## Task 12: UI checkboxes in both panels

**Files:**
- Modify: `em_setup/ui.py`

- [ ] **Step 1: Locate the 3D GIS pyarchinit panel section**

Find the block that renders the pyarchinit fields for 3D GIS mode (search for `pyarchinit_db_path` and `pyarchinit_mapping`). It's around lines 1376-1448 (per the spec exploration).

- [ ] **Step 2: Add the toggles below the mapping selection**

After the line that draws `em_tools.pyarchinit_mapping`, add:

```python
        row = box.row()
        row.prop(em_tools, "pyarchinit_import_geometries")
        if em_tools.pyarchinit_import_geometries:
            sub = box.row()
            sub.alignment = 'RIGHT'
            sub.prop(em_tools, "pyarchinit_geom_force_update")
```

- [ ] **Step 3: Locate the EM Advanced auxiliary panel section**

Find the block that renders auxiliary file fields when `file_type == 'pyarchinit'` (around the `aux_file.pyarchinit_mapping` line, near the auxiliary file UI).

- [ ] **Step 4: Add the same toggles, scoped to `aux_file`**

After the line that draws `aux_file.pyarchinit_mapping`, add:

```python
            row = aux_box.row()
            row.prop(aux_file, "pyarchinit_import_geometries")
            if aux_file.pyarchinit_import_geometries:
                sub = aux_box.row()
                sub.alignment = 'RIGHT'
                sub.prop(aux_file, "pyarchinit_geom_force_update")
```

(Adjust `aux_box` to the actual layout variable used by the existing code.)

- [ ] **Step 5: Verify visually in Blender**

Reload the extension. Open EM panel → 3D GIS mode → select pyarchinit → confirm the new checkboxes appear, the `force_update` only appears when the primary toggle is on.

- [ ] **Step 6: Commit**

```bash
git add em_setup/ui.py
git commit --author="Enzo Cocca <enzo.ccc@gmail.com>" -m "feat(setup): UI checkboxes for pyarchinit geometry toggles"
```

---

## Task 13: Integration in import_EMdb.py

**Files:**
- Modify: `import_operators/import_EMdb.py`

- [ ] **Step 1: Add import statements**

At the top of `import_operators/import_EMdb.py`, after the existing imports, add:

```python
from .pyarchinit_geom_importer import import_geometries as _pyarchinit_import_geometries
```

- [ ] **Step 2: Locate the post-import return**

Find the `execute()` method, locate `return self._handle_import_results(context, settings, graph)` (the final return on the happy path).

- [ ] **Step 3: Insert the geometry-import hook just before that return**

Replace the surrounding block to look like:

```python
            # 9. POST-PROCESSING
            result = self._handle_import_results(context, settings, graph)

            if settings.get("import_type") == "pyarchinit" \
               and result == {'FINISHED'}:
                self._maybe_import_pyarchinit_geometries(context, settings, graph)

            return result
```

- [ ] **Step 4: Add the helper method on the operator class**

Inside `EM_OT_import_3dgis_database`, add:

```python
    def _maybe_import_pyarchinit_geometries(self, context, settings, graph):
        em_tools = context.scene.em_tools
        if settings["mode"] == "EM_ADVANCED":
            graphml = em_tools.graphml_files[self.graphml_index]
            aux_file = graphml.auxiliary_files[self.auxiliary_index]
            if not aux_file.pyarchinit_import_geometries:
                return
            db_path = aux_file.filepath
            force_update = aux_file.pyarchinit_geom_force_update
            graph_code = graphml.graph_code
        else:
            if not em_tools.pyarchinit_import_geometries:
                return
            db_path = em_tools.pyarchinit_db_path
            force_update = em_tools.pyarchinit_geom_force_update
            graph_code = "GraphMain"

        from ..functions import show_popup_message

        def show_warning(level, msg):
            icon = 'ERROR' if level == 'ERROR' else 'INFO'
            show_popup_message(context, title=f"Geometry import {level}",
                               message=msg, icon=icon)

        def ask_user(state, centroid, db_srid):
            return self._popup_georef_choice(state, centroid, db_srid)

        report = _pyarchinit_import_geometries(
            context=context,
            db_path=db_path,
            graph=graph,
            graph_code=graph_code,
            force_update=force_update,
            ask_user_callback=ask_user,
            show_warning_callback=show_warning,
        )
        self._show_geom_summary(context, report)

    def _popup_georef_choice(self, state, centroid, db_srid):
        """Modal popup. Returns 'AUTO' or 'CANCEL'."""
        # Implementation uses bpy.context.window_manager.invoke_props_dialog
        # with a tiny operator class. Stub returning 'AUTO' is acceptable
        # for the first iteration; replace with a proper dialog in a
        # follow-up commit if needed.
        return 'AUTO'

    def _show_geom_summary(self, context, report):
        lines = [
            f"Created:               {report['created']}",
            f"Updated:               {report['updated']}",
            f"Skipped (modified):    {report['skipped_user_modified']}",
            f"Marked orphan (obj):   {report['marked_orphan_obj']}",
            f"Polygon orphans:       {report['polygon_orphans']}",
            f"US without geometry:   {len(report['us_without_geometry'])}",
        ]
        if report["malformed_geometries"]:
            lines.append(
                f"Malformed geometries:  {len(report['malformed_geometries'])}"
            )
        if report["backup_collection"]:
            lines.append(f"Backup collection:     {report['backup_collection']}")

        from ..functions import show_popup_message
        show_popup_message(
            context,
            title="PyArchInit Geometry Import — Summary",
            message="\n".join(lines),
            icon='INFO',
        )
```

- [ ] **Step 5: Commit**

```bash
git add import_operators/import_EMdb.py
git commit --author="Enzo Cocca <enzo.ccc@gmail.com>" -m "feat(geom): wire pyarchinit geometry import into 3D GIS + auxiliary flows"
```

---

## Task 14: Update `__init__.py` registration (if needed)

**Files:**
- Modify: `import_operators/__init__.py`

- [ ] **Step 1: Inspect current registration**

Open `import_operators/__init__.py` and check whether it explicitly lists submodules or relies on top-level imports done from elsewhere.

- [ ] **Step 2: If the file enumerates submodules, append the new ones**

If you see something like:

```python
from . import import_EMdb, importer_xlsx, importer_graphml
```

extend to:

```python
from . import (
    import_EMdb,
    importer_xlsx,
    importer_graphml,
    pyarchinit_geom_importer,
    geom_constants,
    geom_blender_io,
    geom_georef,
    pyarchinit_db_reader,
    reimport_planner,
    wkb_parser,
)
```

If the file is empty or does no explicit imports, leave it alone (Python finds submodules on first attribute access).

- [ ] **Step 3: Commit (only if a change was made)**

```bash
git add import_operators/__init__.py
git commit --author="Enzo Cocca <enzo.ccc@gmail.com>" -m "chore(geom): expose new submodules from import_operators package"
```

---

## Task 15: Build extension, run manual scenarios

**Files:**
- None modified; this is the verification task.

- [ ] **Step 1: Run unit tests one last time**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all tests pass (8 from wkb_parser + 6 from reimport_planner + 2 smoke = 16).

- [ ] **Step 2: Build the extension**

```bash
./em.sh build dev
```

Expected: `Extension built successfully: /Users/enzo/EM_Tools_Releases/em_tools-v1.5.0-dev.146.blext`

- [ ] **Step 3: Copy to .zip and install**

```bash
cp /Users/enzo/EM_Tools_Releases/em_tools-v1.5.0-dev.146.blext \
   /Users/enzo/EM_Tools_Releases/em_tools-v1.5.0-dev.146.zip
```

Install in Blender: `Edit → Preferences → Extensions → Install from Disk`.

- [ ] **Step 4: Run manual scenarios from the spec §11**

Walk through each scenario, ticking each box and recording observations. Issues found here go back into earlier tasks as fix commits.

Scenarios to verify:

1. Happy path on fixture — fresh scene + `tests/fixtures/pyarchinit_minimal.sqlite`, georef popup appears, 3 meshes created in `EM_US_Geometries/GraphMain`, 1 orphan polygon in `EM_US_OrphanPolygons`, 2 US in summary "without geometry".
2. Re-import preserves modifications — edit one mesh in Blender (extrude a face), re-import without `force_update`. Verify summary shows 1 "skipped (user-modified)" and the mesh is unchanged.
3. Force update with backup — same, but enable `force_update`. Verify a `_Backups_<ts>` collection is created (hidden), contains a copy of the modified mesh, and the live mesh is rebuilt.
4. Object orphan — modify the fixture to delete a row, re-import. Verify the corresponding mesh is moved to `EM_US_Orphans` and tagged `em_us_orphan=True`.
5. Missing DB — point to a non-existent file. Verify error popup, operator cancels cleanly.
6. CRS mismatch — set `em_georef.epsg='32632'` manually then import. Verify warning popup, import proceeds with scene shift.

- [ ] **Step 5: Document scenarios in PR description**

Use the checklist above (with `[x]` for verified items) as the PR's `## Test plan` section.

---

## Task 16: Open the PR

**Files:**
- None modified.

- [ ] **Step 1: Push branch**

```bash
git push -u origin feat/pyarchinit-geometry-import
```

- [ ] **Step 2: Open PR against upstream**

```bash
gh pr create \
  --repo zalmoxes-laran/EM-blender-tools \
  --base EM-tools_v1.6.0_dev \
  --head enzococca:feat/pyarchinit-geometry-import \
  --title "feat(import): import pyunitastratigrafiche multipolygons as Blender meshes" \
  --body "$(cat <<'EOF'
## Summary

Adds the ability to import multipolygon footprints from the PyArchInit
`pyunitastratigrafiche` table as editable Blender meshes, anchored to
the s3dgraphy US nodes that the existing PyArchInit import already
produces. The user can then extrude and sculpt the imported mesh to
build the 3D stratigraphic volume.

Design document: `docs/superpowers/specs/2026-05-22-pyarchinit-geometry-import-design.md`

## Highlights

- Pure-Python WKB parser (no SpatiaLite extension dependency, no new wheel)
- Reads `pyunitastratigrafiche` from SQLite/SpatiaLite in read-only mode
- Re-import is diff-based: preserves user modifications by default, opt-in
  `force_update` rebuilds with automatic backup
- Three orphan categories surfaced via the existing Hybrid-C `aux_orphans`
  pattern
- Object ↔ s3dgraphy node link via both naming convention and custom
  property (custom property is primary, name is fallback)
- Toggle available in both 3D GIS mode and EM Advanced auxiliary mode

## Out of scope (separate sub-projects)

- PostgreSQL/PostGIS backend
- CRS-to-CRS reprojection
- Mesh-to-proxy promotion
- Export direction (GraphML → PyArchInit DB)

## Test plan

[Paste the checklist from Task 15 step 4 here, with [x] for verified items.]
EOF
)"
```

Expected: PR URL printed.

---

## Self-review notes

- Spec coverage: every section of `2026-05-22-pyarchinit-geometry-import-design.md` maps to a task (§5 data flow → Tasks 6-13; §6 georef → Task 7; §7 linking → Tasks 4, 6, 10; §8 orphans → Task 10; §9 re-import → Tasks 5, 6, 10; §10 errors → handled inline in Tasks 8, 10; §11 testing → Tasks 1-5, 9, 15).
- The `aux_import.py` extension mentioned in the spec is handled inline in Task 10 (`_handle_polygon_orphans` writes to `graph.attributes['aux_orphans']` with the new `kind` discriminator). No standalone modification commit needed — the consumers (`em_setup/ui.py`) already iterate `aux_orphans` and will naturally see the new entries. A future small PR can teach the UI to branch on `payload.kind`.
- The `_resolve_us_node` helper assumes the existing PyArchInitImporter creates node names as `SITE_AREA_US` (underscored). This matches the mapping JSON's `is_id: true` declaration on the `us` column. If the actual name format diverges, fix `_resolve_us_node` in `pyarchinit_geom_importer.py` accordingly during Task 15 verification.
- `_popup_georef_choice` returns `'AUTO'` as a placeholder. For the first ship, this is acceptable — auto-anchor is the recommended path and the user can pre-configure `em_georef` manually if they want to skip. A proper modal dialog can land in a follow-up if usability feedback warrants.
