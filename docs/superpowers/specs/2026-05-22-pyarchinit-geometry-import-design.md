# PyArchInit Geometry Import — Design

- **Date**: 2026-05-22
- **Status**: Draft, awaiting implementation plan
- **Target branch**: `EM-tools_v1.6.0_dev`
- **Author**: Enzo Cocca
- **Depends on**: PR #25 (`fix/pyarchinit-importer-table-name-kwarg`) — must land first so the baseline US-table import works.

## 1. Context

EM-tools can already import the `us_table` from a PyArchInit SQLite database as nodes in the s3dgraphy graph (`PyArchInitImporter` in s3dgraphy, wired through `import_operators/import_EMdb.py`). The resulting US nodes carry attributes (descriptions, periodization, activities) but no geometry.

In real PyArchInit installations the multipolygon footprint of each stratigraphic unit is drawn in QGIS and stored in a separate spatial table, conventionally `pyunitastratigrafiche`. That table is the *de facto* archaeological canvas: it's the only place where the spatial extent of each US lives.

Today there is no way to bring those multipolygons into Blender. As a result, after a PyArchInit import the user has no 3D context to model against — they have to either rebuild footprints manually or skip 3D modeling altogether.

## 2. Goal

Let the user import the `pyunitastratigrafiche` multipolygons from a PyArchInit database into Blender as editable meshes, anchored to the s3dgraphy US nodes that the existing import already produces. The meshes become the starting surface from which the user models the 3D stratigraphic volumes (extrude, sculpt, edit).

Promoting modeled meshes into formal s3dgraphy proxies (via the existing `proxy_box_creator` flow or a new operator) is **out of scope** for this iteration. See §13.

## 3. Non-goals

- PostgreSQL/PostGIS backend support. Only SQLite/SpatiaLite is targeted here. PostgreSQL is a separate, sequenced sub-project (§13).
- CRS reprojection (e.g. WGS84 → UTM). The existing `georef_manager` module explicitly defers reprojection to Phase 2; this design respects that boundary.
- Automatic generation of s3dgraphy `proxy` nodes from imported meshes.
- Export direction (GraphML → PyArchInit DB). Tracked separately (§13).
- Schema migrations or write-back to the PyArchInit DB.
- Smart "skip if DB unchanged" detection. Re-import is always an explicit user action.

## 4. Architecture overview

All new code lives inside the EM-tools addon under `import_operators/`. s3dgraphy is consumed read-only; no upstream changes required for this feature.

```
EM-tools addon (1.6.0-dev)
│
├─ em_setup/
│   ├─ properties.py      : new BoolProperty
│   │                       'pyarchinit_import_geometries'
│   │                       new BoolProperty
│   │                       'pyarchinit_geom_force_update'
│   └─ ui.py              : checkbox in 3D GIS and EM Advanced
│                            panels (when file_type=pyarchinit)
│
├─ import_operators/
│   ├─ import_EMdb.py            (existing, lightly modified)
│   │     └─ after the existing PyArchInit US import,
│   │        if toggle on → call pyarchinit_geom_importer
│   │
│   ├─ pyarchinit_geom_importer.py   (NEW)
│   │     ├─ open second sqlite3 connection (read-only)
│   │     ├─ detect schema (table + geometry column + SRID)
│   │     ├─ resolve georef anchor (popup if scene is unset)
│   │     ├─ query polygons
│   │     ├─ build re-import plan via reimport_planner
│   │     ├─ for each plan entry: parse WKB → bmesh → object
│   │     ├─ apply naming + custom properties
│   │     ├─ collect orphans into graph.attributes['aux_orphans']
│   │     └─ assemble and present summary dialog
│   │
│   ├─ wkb_parser.py             (NEW, ~80 LOC pure-Python)
│   │     └─ parse_wkb(blob) → list of polygons,
│   │                          each polygon = list of rings,
│   │                          each ring = list of (x, y, z?) tuples
│   │
│   └─ reimport_planner.py       (NEW, small)
│         └─ diff_against_scene(incoming, scene, graph)
│              → {create, update_safe, skip_modified, mark_orphan_obj}
│
├─ aux_import.py    (existing, lightly extended)
│   └─ aux_orphans payload gains a 'kind' discriminator;
│      new aux_us_no_geom list (US nodes without polygons)
│
└─ georef_manager   (existing, consumed read-only here)
    └─ scene.em_georef provides epsg + shift_x/y/z
```

Key principles:

- No new wheels. `sqlite3` is stdlib; WKB parsing is pure Python.
- No s3dgraphy modification. The graph is already populated by the existing US import; this feature only **reads** node IDs and **appends** an attribute (`imported_geom_obj_name`).
- `georef_manager` is the canonical source of scene CRS/shift. We write to it only via its public PropertyGroup fields (which trigger its existing update callbacks to BlenderGIS and 3DSC), never via private internals.

## 5. Data flow

### Trigger

User is in `em_setup` panel (3D GIS mode or EM Advanced mode), file type is `pyarchinit`, ticks **"Also import US geometries from `pyunitastratigrafiche`"**, optionally ticks **"Force update existing meshes (creates backup)"**, then presses **Import**.

### Steps

1. The existing `EM_OT_import_3dgis_database` operator runs the PyArchInit US table import (after PR #25 lands, this works).
2. If `scene.em_tools.pyarchinit_import_geometries` is true, it then calls `pyarchinit_geom_importer.import_geometries(context, db_path, graph, source_id)`.
3. The geometry importer:
   1. Opens a second SQLite connection in read-only URI mode (`file:{path}?mode=ro`).
   2. Detects the schema: looks up `pyunitastratigrafiche` in `sqlite_master`, then queries `geometry_columns` for the geometry column name and SRID. Falls back to probing `the_geom`, `geom`, `geometry` in order if `geometry_columns` is empty.
   3. Resolves the georef anchor (see §6).
   4. Reads all polygon rows: `SELECT us, area, sito, <geom_col> FROM pyunitastratigrafiche`.
   5. Builds a re-import plan (see §9).
   6. Executes the plan: for each polygon to create or safely update, parse the WKB, shift coordinates by the resolved georef shift, build a Blender mesh through bmesh, attach custom properties, link to the matching s3dgraphy node.
   7. Handles orphans: polygons with no matching US node go into the `EM_US_OrphanPolygons` collection and into `graph.attributes['aux_orphans']`; existing meshes whose US disappeared get tagged `em_us_orphan=True` and moved to `EM_US_Orphans` collection; US nodes without polygons are listed in `graph.attributes['aux_us_no_geom']`.
   8. Closes the connection, assembles the report, shows the summary dialog.

### Scene layout after import

```
Scene Collection
├─ EM_US_Geometries
│   └─ <GRAPH_CODE>/
│       ├─ <GRAPH_CODE>.US42        ← imported, linked to graph node
│       ├─ <GRAPH_CODE>.US43
│       └─ ...
├─ EM_US_OrphanPolygons             ← polygons with no matching US node
│   └─ orphan_<sito>_<area>_<us>
├─ EM_US_Orphans                    ← objects whose US vanished at re-import
│   └─ <GRAPH_CODE>.US999 (em_us_orphan=True)
└─ _Backups_2026-05-22T08-30-00     ← only present if force_update overwrote modified meshes
    └─ <GRAPH_CODE>.US42.backup.2026-05-22T08-30-00
```

### Performance notes

- Single bmesh pass per polygon; one `bm.to_mesh()` call per object.
- One depsgraph update at the end of the whole loop (not per object).
- For DBs with ~1000 polygons the bottleneck is mesh creation, not the DB read.

### Supported WKB

- `POLYGON` (type 3), 2D and 3D
- `MULTIPOLYGON` (type 6), 2D and 3D
- Other geometry types (POINT, LINESTRING, etc.) → row skipped, logged as warning.

A 3D polygon uses its Z. A 2D polygon places the mesh at Z=0; the user extrudes manually.

A MULTIPOLYGON becomes a single Blender object whose mesh contains one disconnected face per polygon part.

## 6. CRS / georef integration

The scene's CRS and shift live in `scene.em_georef` (already managed by the `georef_manager` module). This feature is a **read-only consumer** of that state, with one exception: when the scene's georef is unset and the user opts in via popup, we write the shift through the same public update callbacks that `georef_manager` already exposes — this ensures BlenderGIS and 3D Survey Collection stay in sync via the existing adapters.

### Georef state classification

| `epsg`              | `shift_x/y/z`    | State        |
|---------------------|------------------|--------------|
| `""` or `"4326"`    | all zero         | `UNSET`      |
| valid EPSG          | all zero         | `EPSG_ONLY`  |
| valid EPSG          | non-zero         | `CONFIGURED` |

### Popup behavior

- `CONFIGURED`: use existing values. If the DB SRID disagrees with the scene EPSG, show a non-blocking warning popup and continue using the scene values.
- `UNSET`: compute the centroid of incoming polygons in DB CRS, then ask the user via popup whether to auto-anchor (recommended, sets shift = centroid and epsg = SRID) or cancel and configure manually.
- `EPSG_ONLY`: auto-anchor without asking — the CRS commitment is already explicit, only the shift is missing.

### Write API

The popup-driven write path uses only the `scene.em_georef` PropertyGroup setters:

```python
g = context.scene.em_georef
g.epsg = str(srid)
g.shift_x = cx
g.shift_y = cy
g.shift_z = 0.0
```

The existing `update_*` callbacks on the PropertyGroup propagate to BlenderGIS and 3D Survey Collection. No private API, no reimplementation.

### Edge cases

- DB SRID = 0 (no metadata) → popup asks user to enter EPSG manually; if skipped, assume the current `em_georef.epsg` or fall back to 4326.
- DB SRID ≠ scene EPSG → warning popup, but the import continues using scene shift values. Reprojection is explicitly out of scope.
- Polygons span > 50 km → warning in the post-import summary suggesting the user re-anchor.
- The `em_georef.move_objects_on_change` toggle is **not** considered by this import: we apply shift to incoming coordinates **before** building meshes, so the toggle's side-effect path is never engaged.

## 7. Linking & naming

### Custom properties on each imported object

```
em_us_node_id          : str   s3dgraphy node UUID — primary link
em_us_name             : str   human-readable US code, e.g. "USM100"
em_graph_code          : str   GRAPH_CODE (landscape-mode-aware)
em_pyarchinit_source   : str   absolute path to source DB (re-import tracking)
em_pyarchinit_us_key   : str   tuple key from DB, "sito=X,area=A,us=42"
em_import_timestamp    : str   ISO UTC datetime of import
em_original_vert_count : int   vertex count immediately after import (modification probe)
em_imported_mesh_hash  : str   "sha1:<hex>" hash of the mesh data as built at import time
                               (sorted vertex coords + face indices) — used to detect
                               user modifications that preserve vertex count
em_us_orphan           : bool  set True at re-import if the US disappeared from the DB
em_is_imported_geom    : bool  True — distinguishes our meshes from anything else
```

### Object naming convention

```
<GRAPH_CODE>.<US_NAME>
```

This is identical to the convention already used by the addon's proxy resolver (`EM_select_from_list_item`), so no new name-resolution logic is introduced.

### Name conflicts

If an object with the target name already exists and is **not** one of our imports (i.e. lacks `em_is_imported_geom=True`):

- Append suffix `.imported` (e.g. `GT16.USM100.imported`).
- Surface this in the summary dialog as a warning.
- The user decides whether to delete the pre-existing object and re-import.

### Resolver lookup

```python
def find_imported_geom_for_node(node_id):
    # 1. Primary: custom property (survives renames)
    for obj in bpy.data.objects:
        if obj.get('em_us_node_id') == node_id and obj.get('em_is_imported_geom'):
            return obj
    # 2. Fallback: name convention
    node = get_node_by_id(node_id)
    candidate = f"{node.graph_code}.{node.name}"
    obj = bpy.data.objects.get(candidate)
    if obj and obj.get('em_is_imported_geom'):
        return obj
    return None
```

### Reverse link on the graph node

The s3dgraphy node gains one attribute (no schema change required, just a dict entry):

```
node.attributes['imported_geom_obj_name'] = '<GRAPH_CODE>.<US_NAME>'
```

This coexists with any pre-existing `proxy_obj_name` attribute used by formal proxies.

### What we don't do

- We do **not** auto-rename the object if the user later changes `US_NAME`. The custom property holds the link; auto-renaming would be invasive.
- We do **not** use Blender's `PointerProperty` to objects for the link — those don't survive save/load reliably in Extension context.

## 8. Orphans & report

### Three orphan categories

| Category | Source | Destination |
|---|---|---|
| Polygon orphan | Row in `pyunitastratigrafiche` whose (sito, area, us) matches no US node in the graph | Mesh created, collection `EM_US_OrphanPolygons`, tracked in `graph.attributes['aux_orphans']` with payload `kind='polygon_no_us'` |
| US without geometry | US node exists in graph, no polygon in DB | Metadata only — appended to `graph.attributes['aux_us_no_geom']` (list of node IDs). No mesh created. |
| Object orphan at re-import | Imported mesh exists in scene, but its US disappeared from the DB | Mesh kept. `obj['em_us_orphan'] = True`, moved to `EM_US_Orphans` collection. |

### Extension to `aux_import.py`

The Hybrid-C pattern is already in place. Two minimal extensions:

1. The `aux_orphans` list payload gains an optional `kind` field. Existing producers that don't set it remain valid (consumers default to a generic "unknown").
2. A new `aux_us_no_geom` list of node IDs.

```python
graph.attributes.setdefault('aux_orphans', []).append({
    'key_id': f"sito={sito},area={area},us={us}",
    'payload': {
        'kind': 'polygon_no_us',
        'source': db_path,
        'wkb_hex_preview': wkb_hex[:32],
        'obj_name': created_obj.name,
    },
})

graph.attributes.setdefault('aux_us_no_geom', []).append(node_id)
```

### Summary dialog

Modal dialog shown at the end of the import (via `window_manager.invoke_props_dialog`):

```
PyArchInit Geometry Import — Summary
─────────────────────────────────────────────
Created:                  N new meshes
Updated:                  N unchanged meshes
Skipped (user-modified):  N meshes
Marked orphan (US gone):  N existing meshes

Polygon orphans:          N polys without US
  → see "Orphans" panel for details
US without geometry:      N US codes
  → US42, US43, ...

Backup created:           _Backups_<timestamp>  (or "none")

[OK]  [Open Orphans panel]
```

### UI integration

The existing `aux_orphans` UI in `em_setup/ui.py` continues to work. Two small additions:

1. A new collapsible section "US without geometry" under the existing orphans block, listing node IDs from `aux_us_no_geom` with click-to-select in the graph.
2. When rendering an orphan row, branch on `payload.kind` to pick the appropriate icon (`MESH_DATA` for `polygon_no_us`, the existing icon otherwise).

### What we don't do

- We do **not** auto-create US nodes for polygon orphans — that would synthesize data. The user inspects `EM_US_OrphanPolygons`, decides whether to fix the DB or accept the polygon as-is and create a US manually.
- We do **not** auto-delete object orphans. A US disappearing from the DB might be temporary (the colleague will re-add it). Deletion is always a deliberate user action.

## 9. Re-import behavior

### Algorithm

```python
def build_reimport_plan(scene, graph, incoming_polygons):
    plan = {'create': [], 'update_safe': [], 'skip_modified': [],
            'mark_orphan_obj': []}

    existing_by_node_id = {
        obj['em_us_node_id']: obj
        for obj in scene.objects
        if obj.get('em_is_imported_geom') and obj.get('em_us_node_id')
    }

    incoming_by_node_id = {}
    for poly in incoming_polygons:
        node = resolve_us_node(graph, poly['us_key'])
        if node is None:
            continue  # handled separately as polygon orphan
        incoming_by_node_id[node.id] = (poly, node)

    for node_id, (poly, node) in incoming_by_node_id.items():
        existing = existing_by_node_id.get(node_id)
        if existing is None:
            plan['create'].append((poly, node))
        elif is_mesh_modified(existing):
            plan['skip_modified'].append((poly, node, existing))
        else:
            plan['update_safe'].append((poly, node, existing))

    for node_id, obj in existing_by_node_id.items():
        if node_id not in incoming_by_node_id:
            plan['mark_orphan_obj'].append(obj)

    return plan
```

### Detection: "has the user modified this mesh?"

Three signals in cascade, from strongest to weakest:

```python
def is_mesh_modified(obj):
    # 1. Vertex count changed since import
    if obj.get('em_original_vert_count') is not None \
       and len(obj.data.vertices) != obj['em_original_vert_count']:
        return True
    # 2. Mesh hash differs from import-time hash (same count, but moved/edited vertices)
    if obj.get('em_imported_mesh_hash'):
        if compute_mesh_hash(obj.data) != obj['em_imported_mesh_hash']:
            return True
    # 3. Object transform diverged from identity
    if not is_object_transform_identity(obj):
        return True
    return False
```

`em_original_vert_count` and `em_imported_mesh_hash` are written **at first import** and never overwritten while the mesh lives. They are the immutable reference for modification detection.

### Force update + backup

A second toggle `pyarchinit_geom_force_update` (BoolProperty, default False) decides what happens to `plan['skip_modified']`:

- `False` (default): modified meshes are left alone; summary reports them as "skipped (user-modified)".
- `True`: each affected mesh is **first duplicated** into a `_Backups_<timestamp>` collection (hidden by default), then its mesh data is rebuilt in place.

```python
def backup_then_replace(obj, new_poly):
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    backup_coll = ensure_collection(f"_Backups_{ts}", hidden=True)

    backup_obj = obj.copy()
    backup_obj.data = obj.data.copy()
    backup_obj.name = f"{obj.name}.backup.{ts}"
    move_obj_to_collection(backup_obj, backup_coll)
    backup_obj['em_is_backup'] = True

    replace_mesh_in_place(obj, new_poly)
    refresh_modification_baseline(obj)  # rewrites em_original_vert_count + em_imported_mesh_hash
```

### What we don't do

- We do **not** overwrite without a backup when `force_update=True`. Backup is automatic, not opt-in.
- We do **not** garbage-collect old `_Backups_*` collections. Cleanup is an explicit user action (a future "Clean old backups" operator can be added in a follow-up PR).
- We do **not** compare the DB file mtime/hash to skip "no-op" re-imports. Re-import is always intentional.

## 10. Error handling

| Failure | Failure point | Behavior |
|---|---|---|
| DB file missing or permissions denied | `sqlite3.connect` | `ERROR` popup with path + errno; operator returns `{'CANCELLED'}`; no side effects. |
| `pyunitastratigrafiche` table missing | Schema detection | `WARNING` popup: US table import succeeded, no geometries imported; operator returns `{'FINISHED'}`. |
| Geometry column name unrecognized | Schema detection | Try fallback names (`the_geom`, `geom`, `geometry`); if all fail, `ERROR` popup, `{'CANCELLED'}`. |
| Malformed WKB on a single row | `wkb_parser.parse` | Row skipped; logged in summary as "N malformed geometries"; other rows continue. Never blocks the whole import. |
| Unsupported WKB geometry type (not POLYGON/MULTIPOLYGON) | `wkb_parser.parse` | Row skipped; logged with US code; warning in summary. |
| `SRID = 0` | Schema detection | Popup asks for manual EPSG; if user skips, fall back to current `em_georef.epsg` or `4326`. |
| Polygon ring self-intersecting | bmesh build | bmesh accepts it but triangulation may produce a degenerate face. Logged as warning; mesh created anyway so the user sees and fixes manually. |
| Empty DB (no rows in `pyunitastratigrafiche`) | After `SELECT` | No georef popup, summary "No polygons in DB", `{'FINISHED'}`. |
| DB locked / connection dropped mid-fetch | Any fetch | `try/except` with connection cleanup, `ERROR` popup, `{'CANCELLED'}`. |
| Pre-existing object with same target name | `create_or_replace_object` | Suffix `.imported` (see §7); warning in summary. |
| Operator invoked out of context | Operator entry | Standard `poll()` check: requires a valid `context.scene`. |

### Idempotency

There is no transactional guarantee — Blender data API isn't transactional. Mitigations:

- All meshes created carry full custom properties immediately, so a partial failure mid-loop leaves a recoverable state: a subsequent re-import will treat the partially-imported meshes as "already present" and update or skip as usual.
- The `mark_orphan_obj` step runs near the end, so a mid-import failure can't accidentally tag and move otherwise-good meshes.

### Logging

All non-popup diagnostics go through a single logger helper (`_em_log` already exists in `georef_manager`; we reuse it or its equivalent). Default level `INFO`; verbose WKB tracing gated by a scene-level `em_tools.debug_geom_import` flag.

## 11. Testing strategy

No Blender headless test harness is in place yet, so testing is split:

### Unit tests (no Blender required)

`tests/test_wkb_parser.py` — the WKB parser is pure Python and isolated. Fixtures are blob literals (hex strings decoded to bytes) generated once with shapely offline and committed:

- `POLYGON` 2D — single ring
- `POLYGON` 2D — outer + 1 hole
- `POLYGON` 3D
- `MULTIPOLYGON` 2D — 3 parts
- `MULTIPOLYGON` 3D
- Malformed: truncated blob, unsupported type byte

Run with `.venv/bin/pytest tests/test_wkb_parser.py`. Suitable for CI.

`tests/test_reimport_planner.py` — pure-Python diff logic. Mocks `scene.objects` and `graph.nodes`. Verifies the four-bucket plan against synthetic inputs.

### Integration tests (manual, documented)

A `tests/fixtures/pyarchinit_minimal.sqlite` (~5 KB) is generated once by `tests/fixtures/build_fixture.py` (committed) and used as a known-good DB for manual scenarios:

1. **Happy path** — fresh scene, no georef. Import. Verify popup appears, auto-anchor works, meshes appear in `EM_US_Geometries`, custom properties are set, link to graph nodes verified via select-from-list.
2. **Re-import preserves modifications** — after (1), enter edit mode on one mesh, extrude. Re-import without force. Verify that the modified mesh is skipped, summary shows "1 skipped (user-modified)".
3. **Force update with backup** — re-import with `force_update=True`. Verify backup collection is created, mesh is rebuilt, `em_original_vert_count` refreshed.
4. **Polygon orphan** — DB row with `us=999` not in `us_table`. Verify mesh ends up in `EM_US_OrphanPolygons`, entry in `aux_orphans` with `kind='polygon_no_us'`.
5. **US without geometry** — `us_table` has 5 records, `pyunitastratigrafiche` has 3. Verify 3 meshes created, summary lists 2 US without geometry.
6. **Missing / corrupted DB** — non-existent path → error popup, operator cancelled. Non-SQLite file → graceful failure.
7. **CRS mismatch** — scene `em_georef.epsg='32632'`, DB SRID `32633` → warning popup, import proceeds using scene shift.
8. **MultiPolygon** — fixture row with MULTIPOLYGON of 3 parts → resulting mesh has 3 disconnected faces in one object.

Manual scenarios are checklisted in the PR description.

### What we don't test (yet)

- Blender headless integration tests. Out of scope for the first PR.
- Coverage thresholds. This is import-and-display code, not core logic.

## 12. Decisions summary

| # | Decision | Choice |
|---|---|---|
| 1 | Geometry table name | Fixed `pyunitastratigrafiche` (configurable via mapping JSON later if needed) |
| 2 | Proxy promotion from imported mesh | Out of scope (parking lot for follow-up) |
| 3 | CRS handling | Popup with auto-anchor / cancel; no reprojection |
| 4 | Object ↔ node link | Naming convention `<GRAPH>.<US>` AND custom property `em_us_node_id` (custom property is primary, name is fallback) |
| 5 | Orphan handling | Best-effort: import with tagging; surface in `aux_orphans` + new `aux_us_no_geom` |
| 6 | Re-import default | Preserve user modifications; opt-in `force_update` with automatic backup |
| 7 | UI placement | Toggle visible in both 3D GIS and EM Advanced auxiliary modes when file_type=pyarchinit |
| 8 | Code location | Entirely in EM-tools addon (`import_operators/`); no s3dgraphy changes |
| 9 | WKB parsing | Pure-Python parser, no SpatiaLite extension dependency, no new wheel |

## 13. Out of scope / future work

Parked for follow-up sub-projects (independent specs):

- **PostgreSQL backend**. The user has PyArchInit databases on Postgres in team setups. Requires (a) a connection abstraction layer in this importer (or in s3dgraphy's `PyArchInitImporter`), (b) bundling `psycopg2-binary` or `pg8000` as a wheel. Sequenced after this iteration ships.
- **Promote imported mesh to formal proxy**. Two viable approaches:
  - *Operator*: "Promote US Mesh to Proxy" — converts the modeled mesh into a formal s3dgraphy proxy, reusing routines from `proxy_box_creator` where applicable (skipping the seven measurement points because the geometry already exists).
  - *Always-proxy*: imported meshes are formal proxies from the first instant; no separate "promotion" step.
- **Export GraphML → PyArchInit DB**. Inverse direction. Significantly larger scope: schema-aware writes, conflict resolution (update vs insert), ID generation, optional DB creation from scratch. Independent design needed.
- **Reprojection on the fly** (CRS A → CRS B). Tracked by `georef_manager` as Phase 2.
- **`_Backups_*` cleanup operator**. Small follow-up convenience PR.
- **Schema mappings for SITE and PERIODIZATION** PyArchInit tables (only `us_table` has a JSON mapping today in s3dgraphy).

## 14. Open questions

None at the time of writing. All design decisions are committed; remaining specificity belongs in the implementation plan.
