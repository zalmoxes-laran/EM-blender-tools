# Changelog

All notable changes to EM Tools will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Development setup scripts for contributors
- Automated wheel management system
- Hot reload support for VSCode development

### Changed
- Improved error handling for missing dependencies
- Updated documentation structure

## [1.5.0] - 2025-01-15

### Added
- Converted from Blender add-on to Blender Extension format
- Automatic dependency management via wheels
- GitHub Actions workflow for automated releases
- Heriverse export functionality with texture optimization
- GPU instancing support for improved performance
- Advanced export options (Draco compression, separate textures)
- ParaData objects export (Documents, Extractors, Combiners)
- Special Finds models export capability
- Development scripts: `setup_development.py`, `switch_dev_mode.py`
- Comprehensive installation documentation

### Changed
- Migrated configuration to `blender_manifest.toml` format
- Simplified installation process - no manual pip installs needed
- Updated minimum Blender version requirement to 4.0
- Modernized Python dependencies (pandas 2.x, numpy 1.26.x)
- Restructured codebase for better maintainability
- Enhanced export dialog with collapsible sections

### Removed
- Manual dependency installation UI (EmPreferences)
- External modules installer (`external_modules_install.py`)
- Legacy pip installation methods
- Redundant dependency checking code

### Fixed
- Compatibility issues with Blender 4.x series
- Dependency conflicts with system Python installations
- Export errors with large archaeological datasets
- Memory issues during batch exports

## [1.4.0] - 2024-05-20

### Added
- Time branch management system
- Property density visualization
- XLSX import for stratigraphic data
- Batch export capabilities
- Volume calculation tools
- Source type statistics

### Changed
- Enhanced GraphML parser performance
- Improved memory management for large projects
- Updated CIDOC-CRM mapping

### Fixed
- Period manager synchronization issues
- Label creation in orthographic views
- Proxy model visibility toggling

## [1.3.2] - 2024-02-15

### Fixed
- Critical bug in epoch management
- GraphML import for complex hierarchies
- Memory leak in paradata streaming

## [1.3.1] - 2024-01-10

### Added
- Paradata streaming mode
- Real-time graph synchronization
- Enhanced error reporting

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
- Enhanced period visualization system
- Improved proxy-EM synchronization

### Deprecated
- Old EMviq export format (will be removed in 2.0)

## [1.2.0] - 2023-07-15

### Added
- Support for negative stratigraphic units
- DosCo folder integration
- Custom material system for Epochs
- Soloing mode for epochs

### Changed
- Refactored visual manager
- Updated to support Blender 3.6
- Improved GraphML compatibility

## [1.1.0] - 2023-03-20

### Added
- Basic GraphML import/export
- US/USV manager
- Period manager
- Simple visualization tools

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
- MINOR version: New functionality (backwards compatible)
- PATCH version: Bug fixes (backwards compatible)

[Unreleased]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.5.0...HEAD
[1.5.0]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.3.2...v1.4.0
[1.3.2]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.3.1...v1.3.2
[1.3.1]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/zalmoxes-laran/EM-blender-tools/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/zalmoxes-laran/EM-blender-tools/releases/tag/v1.0.0
