# Changelog

All notable changes to EM Tools will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
