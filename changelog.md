# Changelog

All notable changes to EM Tools will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — US creation workflow unification (2026-04)

- **Unified "Add Stratigraphic Unit" dialog** (`strat.add_us`):
  single floating form used by the Stratigraphy Manager (new
  `+ Add US` button under the list), the Proxy Box Creator (`+` next
  to the Active US picker), and Surface Areas (`+` next to the
  Existing US picker). Fields: Type, Name (+ gap-aware suggest-next
  button), Description, Shared-numbering toggle (default ON — one
  global numeric pool across every US type), Epoch (mandatory,
  drives the Activity filter), Activity (optional → `is_in_activity`
  edge), optional stratigraphic link (is_after / is_before). OK
  optionally saves the graphml to disk and pins the new unit as
  active so every panel picks it up via `target_us_name`.
- **`us_helpers.create_us_node(...)` factory**: one entry point for
  US creation (Stratigraphy Manager dialog, ProxyBox, Surface Areas
  all delegate here). Writes the node, `has_first_epoch`, optional
  `is_in_activity` (with a mirror on the PD nodegroup when the
  ProxyBox creates one), optional stratigraphic relation, and
  populates `scene.em_tools.stratigraphy.units` in a single pass.
- **`us_types.py` facade**: JSON-driven US type registry derived
  from s3Dgraphy's `s3Dgraphy_node_datamodel.json` v1.5.2 (patch) and its
  new `classification` API. Exposes `get_us_type_items()` for
  EnumProperty pickers (cached, macOS GC-safe), `US_PROPER_TYPES`,
  `us_material_names()`, plus re-exports of `is_real / is_virtual /
  is_series`.
- **Activity picker filtered by epoch**:
  `scene.activity_manager.filtered_activities` +
  `ACTIVITY_OT_filter_by_epoch` operator +
  `us_helpers.draw_activity_picker(..., epoch_name=…)` widget.
  Direct populator invocation from update callbacks (no silent
  `bpy.ops` failures), inline refresh icon, "no activities for
  epoch" warning.
- **ParadataNodeGroup per US** (`<US>_PD`): Proxy Box Creator now
  wraps every new paradata chain (Document instance clone →
  Extractors → Combiner → PropertyNode) inside a per-US
  ParadataNodeGroup. When the US has an `is_in_activity` edge the
  PD group inherits it, so both sit inside the Activity container
  at save time.
- **Document instance cloning**: Proxy Box Creator duplicates the
  Step-1 anchor Document into a fresh instance (same display name,
  new UUID, copied three-axis classification) for each run so the
  new extractors never attach to a Document already wrapped inside
  another PD group.
- **Chain summary box** in Proxy Box Creator — collapsible
  narrative of the paradata chain that will be written on Create.
- **Save-after-create toggle** (`persist_after_create`, default ON)
  on both the Add-US dialog and the Proxy Box Creator — the
  paradata chain is persisted to .graphml via
  `export.graphml_update` immediately after Create (write-lock
  guard handles yEd conflict detection).
- **Add-US button icon** (`proxies_rows_add`): visually distinct
  from the `+` "suggest next number" button inside the dialog.
- **Next-number gap-aware from 1**: `get_next_numbered_name` and
  `_next_extractor_for_doc` fill the first gap starting at 1
  (previously scanned `[min(used), max(used)]`, leaving `US.1..4`
  unreachable when only `US.5+` existed). Shared-pool mode counts
  trailing digits across every US type, so `SU001` ≡ `US.1` in the
  numbering pool.
- **Legacy prefix aliases** in the numbering helper: Italian `SU…`
  treated as alias of English `US…` (and `USNEG` / `US_NEG` as
  alias of `USN`), so the "+" button never proposes a name that
  collides with legacy-style entries.
- **Negative Stratigraphic Unit (USN)**: new canonical type in every
  US picker (rendered with dashed border in yEd via
  `em_visual_rules.json`). Replaces the ad-hoc `US_NEG` UI-only
  placeholder with a proper s3dgraphy class.

### Changed — US creation workflow unification (2026-04)

- **US creation consolidated to one form**: the inline
  `create_new_us` toggle in ProxyBox and Surface Areas is gone;
  both now launch the shared `strat.add_us` dialog. Single
  changepoint for future US creation rules.
- **Proxy Box Creator edge direction/types**: extractors → Document
  edge is now `extracted_from` (canonical, dashed) instead of the
  non-canonical `has_extractor` (rendered as solid); Combiner →
  Extractors is `combines` instead of `is_combined_in`.
- **Proxy Box Creator PropertyNode** named after the canonical
  qualia ("Proxy Geometry", `property_type="proxy_geometry"`, new
  entry in `em_qualia_types_additions.json`) instead of
  `<US>_proxy_geometry`. Per-US distinction comes from the
  containing PD group, not from the PN name.
- **Centralised hardcoded US-type lists**: 15 occurrences in
  `functions.py`, `populate_lists.py`, `debug_graph_connections.py`,
  `stratigraphy_manager/filters.py` (×3),
  `stratigraphy_manager/operators.py` (×4),
  `landscape_system/populate_functions.py`,
  `visual_manager/utils.py` (×2), `graph_editor/operators.py`,
  `export_operators/heriverse/operator.py` now import
  `US_PROPER_TYPES` / `ALL_US_TYPES` from `us_types.py`. Three
  were incomplete (missing UL + series types) — fixed
  incidentally.

### Removed — US creation workflow unification (2026-04)

- `PROXYBOX_OT_suggest_next_us`, `EMTOOLS_OT_suggest_next_us`
  operators; the `create_new_us` / `new_us_*` / `share_numbering_
  across_types` fields on `ProxyBoxSettings`; the `create_new_us` /
  `new_us_*` / `link_to_existing_us` / `add_stratigraphic_link` /
  `link_relation_type` fields on `SurfaceArealeSettings`.
- `_create_and_activate_new_us` (ProxyBox) and `_create_us_node` /
  `_link_us_to_epoch` / `_link_us_stratigraphically` (Surface
  Areas) — replaced by `us_helpers.create_us_node`.
- `GENERIC` placeholder from the Surface Areas US type picker —
  replaced by the proper typed flow backed by the JSON datamodel.

### Fixed — US creation workflow unification (2026-04)

- **Paradata chain edges rendered as solid lines** in yEd because
  `has_extractor` / `is_in_combiner` weren't canonical edge types.
  Now dashed and in the correct direction.
- **Extractor / Combiner NodeLabel** positioned as Corner-NorthWest
  (matches the reference TempluMare graphml); previously the
  GraphMLPatcher left `modelName=Internal / modelPosition=Center`,
  overlapping the SVG glyph.
- **ParadataNodeGroup positioning**: new PD groups anchored to the
  host US's epoch Y instead of (0,0) (fell outside any swimlane
  row in yEd) and their paradata children nested inside the PD's
  `<graph>`.
- **ActivityNodeGroup containment**: children with `is_in_activity`
  are nested inside the Activity's `<graph>` at save time — the US
  and its PD visibly sit inside the right Activity yEd group.
- **Document instance collisions**: Proxy Box Creator used to
  attach extractors to whichever `D.XX` was encountered first in
  the graph (often one already in another PD group). Now it
  resolves the Step-1 anchor by UUID and clones it locally.
- **Activity filter not refreshing silently**: epoch-change
  callback invoked `bpy.ops.activity.filter_by_epoch` via the
  operator layer, which Blender silently rejects inside property
  update callbacks. Now calls the populator directly.
- **Add-US "not on operator stack"** warning when clicking the
  `+ next number` button: the operator stack is populated only
  after a dialog FINISHES, so the cross-operator lookup always
  failed. Replaced with a shared scene-level sentinel
  (`scene.em_tools.stratigraphy.pending_us_name`).

### Added
- **StratiMiner workflow panel in EM Bridge** (replaces the legacy
  "GraphML Wizard" 3-step panel). The new panel lives at
  ``VIEW3D_PT_stratiminer_bridge`` and exposes three stacked actions:
  - **Prepare AI prompt** — copies the v5.0 extraction prompt to the
    clipboard, with optional documents-folder path and toggles for
    the validation script, the end-of-session checklist and the
    stratigraphy-only appendix.
  - **Action A — Import em_data.xlsx** — parses the unified 5-sheet
    xlsx via ``UnifiedXLSXImporter`` into a fresh in-memory graph and
    optionally writes out a ``.graphml`` in a single pass.
  - **Action B — Merge into active graph** — delegates to the existing
    ``em.merge_xlsx_start`` button (still present in the EM tree tab);
    the operator was updated to auto-detect the unified schema by
    sheet presence and fall back to the legacy ``stratigraphy.xlsx``
    format for backward compatibility.
  New scene properties to drive the panel:
  ``stratiminer_documents_folder``, ``stratiminer_input_xlsx``,
  ``stratiminer_output_graphml``, ``stratiminer_export_on_import``.
  New operator ``emtools.save_em_data_template`` saves the unified
  ``em_data_template.xlsx`` to a chosen directory. The obsolete 2-step
  xlsx wizard (``xlsx_wizard.convert_stratigraphy`` +
  ``xlsx_wizard.enrich_paradata``) is no longer surfaced in any panel;
  its operators remain registered for external scripts.
- **Propagative metadata section collapsed only in Stratigraphy
  Manager**. The Epoch Manager and Document Manager now render the
  section inline (no triangle toggle) — the information is compact
  enough that hiding it adds no value. The shared
  ``scene.em_tools.show_propagative_metadata`` property still drives
  the Stratigraphy Manager's collapse.

- **Propagative metadata (DP-32) in the EM panels**. Each of the three main panels now shows a "Propagative metadata" subsection for the selected context node, resolved through the s3Dgraphy 3-level resolver (node → swimlane → graph), with an inline source tag (`[node]` / `[swimlane]` / `[graph]`) so the user can tell where each value is coming from:
  - **Epochs Manager** — for the active epoch: author, license, embargo (start/end time already shown above, not duplicated).
  - **Stratigraphy Manager** — for the selected US: start time, end time, author, license, embargo.
  - **Document Manager** — for the selected document: author, license, embargo (document-specific chronology already shown).
- Shared helpers in `functions.py`:
  - `resolve_propagative_property(context, node_id, rule_id, default=None)` — safe wrapper around the s3Dgraphy resolver; returns `(value, source_level)` and never raises.
  - `draw_propagative_metadata(layout, context, node_id, ...)` — renders the uniform metadata box, with per-rule toggles so each panel can hide properties it shows elsewhere.
- **Landscape mode (multi-graph)**: manage 2+ archaeological graphs simultaneously in a single Blender scene
- **CronoFilter**: chronological horizons manager for landscape mode — define custom time ranges with colours to filter and visualize across multiple graphs
- **Horizon-based filtering**: Stratigraphy Manager filters nodes by temporal overlap between computed chronology (CALCUL_START_T / CALCUL_END_T) and CronoFilter horizons
- **Horizon-based colouring**: Visual Manager "Horizons" display mode applies CronoFilter colours to 3D proxy objects based on temporal overlap
- **RM visibility sync with horizons**: in landscape mode, Representation Models are shown/hidden based on their epoch's overlap with the active horizon
- **Graph badges in Stratigraphy list**: coloured NODE_SOCKET dot icons and graph code labels differentiate nodes from different graphs
- **Active graph indicator**: Anastylosis Manager and RM Manager show the active graph code with coloured dot in their header row
- **Landscape-aware graph reload**: reloading a GraphML in landscape mode correctly repopulates lists with badges and source_graph tracking
- **Proxy detection in landscape**: uses `GRAPH_CODE.NODE_NAME` naming convention (e.g., `GT16.USM100`) for 3D proxy object resolution
- Support for detecting placeholder dates (XX) in epochs
- Warnings for incomplete or malformed GraphML files in EM Setup
- Flag system for experimental features
- Improved UI synchronization controls in the Paradata Manager panel
- Moved the "Create Collections" button to Utilities & Settings
- Handling of object prefixes based on graph code

### Changed
- Epoch Manager becomes "Horizons" label in Visual Manager when in landscape mode
- Stratigraphy Manager filter label shows "By Horizon" with horizon name in landscape mode
- CronoFilter simplified: removed filter/reset buttons, now purely a chronology/horizon editor
- `EM_select_from_list_item` resolves target objects via `source_graph` property in landscape mode
- `SET_materials_using_epoch_list` refactored with separate single/landscape execution paths
- `sync_rm_visibility` refactored with separate single/landscape paths and epoch→time-range lookup
- Improved robustness of the GraphML import system
- Optimized Paradata updates (reduced UI overhead)
- Reorganized the Stratigraphy Manager panel
- Separated filter and synchronization controls in the Stratigraphy Manager
- Improved index handling for empty lists
- Renamed panel from "US/USV Manager" to "Stratigraphy Manager"

### Removed
- EMviq exporter from the main UI (moved to experimental features)
- Proxy inflation tool from the main UI (moved to experimental features)
- 3D GIS mode from 1.5.0 (moved to 1.6.0)
- Soloing functionality, toggle reconstruction, and toggle selectable from the Epoch Manager

### Hidden in Landscape Mode
- Activity Manager panel (not yet multi-graph aware)
- "By Activity" filter option in Stratigraphy Manager
- Proxy Box Creator panels (operates on single-graph proxy geometry)

### Fixed
- `RuntimeError: Object cannot be hidden because it is not in View Layer` — wrapped all `hide_set()` calls in try/except
- `IndexError` when disabling horizon filter with stale list index — added upper bounds check in `draw_documents_section`
- GraphML import bug with "XX" date format
- Index handling errors in empty lists
- Memory Error during UI updates
- Label visibility for collections with proxies
- Infinite UI update loops in the Paradata Manager

## [1.5.0.dev71] - 2025-01-20

### Added
- Conversion from Blender add-on to Blender Extension
- Automatic dependency management via wheels
- GitHub Actions workflow for automated releases
- Heriverse export functionality with texture optimization
- GPU instancing support for improved performance
- Advanced export options (Draco compression, separate textures)
- Export of ParaData objects (Documents, Extractors, Combiners)
- Special Finds model export capability
- Development scripts: `setup_development.py`, `switch_dev_mode.py`
- Full installation documentation

### Changed
- Configuration migrated to `blender_manifest.toml` format
- Simplified installation process – no manual pip install required
- Minimum Blender version updated to 4.0
- Updated Python dependencies (pandas 2.x, numpy 1.26.x)
- Refactored core code for better maintainability
- Improved export dialog with collapsible sections

### Removed
- Manual UI installation of dependencies (EmPreferences)
- External module installer (`external_modules_install.py`)
- Legacy pip install methods
- Redundant dependency check code

### Fixed
- Compatibility issues with Blender 4.x series
- Dependency conflicts with system Python installations
- Export errors with large archaeological datasets
- Memory issues during batch exports

## [1.4.0] - 2024-05-20

### Added
- XLSX import for stratigraphic data
- Batch export capabilities
- Volume calculation tools


### Changed
- Improved performance of GraphML parser
- Better memory handling for large projects
- Updated CIDOC-CRM mapping

### Fixed
- Synchronization issues in period manager
- Label creation in orthographic views
- Visibility toggle for proxy models

## [1.3.2] - 2024-02-15

### Fixed
- Critical bug in epoch handling
- GraphML import for complex hierarchies
- Memory leak in paradata streaming

## [1.3.1] - 2024-01-10

### Added
- Paradata streaming mode
- Real-time graph synchronization
- Improved error reporting

### Changed
- Optimized 3D view updates
- Improved collection management

## [1.3.0] - 2023-11-30

### Added
- EMviq web export functionality
- ATON framework integration
- Reconstruction uncertainty visualization
- Multi-graph support (experimental)

### Changed
- Redesigned export manager interface
- Improved period visualization system
- Improved proxy-EM synchronization

### Deprecated
- Old EMviq export format (to be removed in 2.0)

## [1.2.0] - 2023-07-15

### Added
- Support for negative stratigraphic units
- DosCo folder integration
- Custom material system for Epochs
- Soloing mode for epochs

### Changed
- Visual manager refactored
- Updated for Blender 3.6 support
- Improved GraphML compatibility

## [1.1.0] - 2023-03-20

### Added
- Basic GraphML import/export
- US/USV manager
- Period manager
- Basic visualization tools

### Fixed
- Initial stability issues
- Basic functionality bugs

## [1.0.0] - 2022-12-01

### Added
- Initial release
- Core Extended Matrix functionality
- Basic 3D visualization
- Simple export capabilities

## Version Naming Convention

- MAJOR version: Incompatible API changes
- MINOR version: New features (backward compatible)
- PATCH version: Bug fixes (backward compatible)

[Unreleased]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.5.0...HEAD  
[1.5.0]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.4.0...v1.5.0  
[1.4.0]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.3.2...v1.4.0  
[1.3.2]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.3.1...v1.3.2  
[1.3.1]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.3.0...v1.3.1  
[1.3.0]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.2.0...v1.3.0  
[1.2.0]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.1.0...v1.2.0  
[1.1.0]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.0.0...v1.1.0  
[1.0.0]: https://github.com/zalmoxes-laran/EM-blender-tools/releases/tag/v1.0.0
