# Extended Matrix 3D tools (EMTools) v1.5

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/zalmoxes-laran/EM-blender-tools)](https://github.com/zalmoxes-laran/EM-blender-tools/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Blender](https://img.shields.io/badge/Blender-4.4%2B%20%7C%205.0%20%7C%205.1-orange.svg)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.13-blue.svg)](https://www.python.org/)

EMTools is a Blender extension that brings the formal language **Extended Matrix** within Blender 3D. Designed and developed by E. Demetrescu (CNR-ISPC), it is part of the Extended Matrix Framework (EMF).

Version 1.5 is a major rewrite featuring a modular architecture, the **s3Dgraphy** graph library, multi-platform wheel distribution, and native support for the Blender Extensions platform.

## What's new in v1.5

* **Blender Extension format** - Native `.zip` packages with bundled platform-specific wheels for Blender 5.0.x (Python 3.11) and 5.1+ (Python 3.13)
* **s3Dgraphy integration** - All graph operations (parsing, querying, export) powered by the [s3Dgraphy](https://github.com/zalmoxes-laran/s3Dgraphy) library
* **Modular architecture** - Code reorganised into dedicated managers: Stratigraphy, Epoch, Visual, Reconstruction, Paradata, Document
* **Graph Editor / Viewer** - Interactive node-graph visualisation of the Extended Matrix with dynamic sockets generated from the s3Dgraphy data-model
* **Visual Manager** - Property-based colouring, colour ramps, viewport labels and overlays
* **Landscape system** - Multi-graph support and CronoFilter horizons for landscape-scale projects
* **Proxy Box Creator** - Create proxy geometry from 3D-picked bounding points
* **Proxy-to-RM projection** - Project proxy materials onto reconstruction models
* **Tapestry integration (experimental)** - Semantic search and linked-data enrichment
* **XLSX import** - Import stratigraphic data and paradata from spreadsheets
* **Multi-platform CI/CD** - GitHub Actions builds per-platform releases automatically (`em.sh devrel`)

## Features

* **Extended Matrix Integration** - Full support for the EM formal language in Blender
* **Archaeological Workflows** - 3D stratigraphic annotation and analysis
* **Reconstruction Hypotheses** - Create and manage multiple reconstruction scenarios (RM Manager)
* **Data Export** - Export to ATON 3 (EMviq), GraphML, XLSX, OBJ and various formats
* **Period Visualisation** - Epoch-based colouring, EM display modes, property-based colouring with colour ramps
* **Statistical Tools (experimental)** - Volume calculations, source analysis, property density

## Documentation

- [**User Manual**](https://docs.extendedmatrix.org/projects/EM-tools/en/latest/) - Complete documentation
- [**Installation Guide**](https://docs.extendedmatrix.org/projects/EM-tools/en/latest/installation.html) - Setup instructions
- [**API Reference**](https://docs.extendedmatrix.org/projects/EM-tools/en/latest/api.html) - Developer documentation

## Community

- [Telegram Group](https://t.me/UserGroupEM) - Join our community
- [Facebook Group](https://www.facebook.com/groups/extendedmatrix) - Extended Matrix users
- [EM Website](https://www.extendedmatrix.org) - Official website

## Installation

### For Users

1. Go to the [Releases](https://github.com/zalmoxes-laran/EM-blender-tools/releases) page
2. Download the `.zip` matching your **platform** and **Blender version**:
   - Blender 5.0.x &rarr; `blender50` files (Python 3.11)
   - Blender 5.1+ &rarr; `blender51` files (Python 3.13)
3. In Blender: **Extensions &rarr; Install from Disk**
4. Select the downloaded zip file (do not unzip) and enable the extension

### For Developers

```bash
# Clone the development branch
git clone --branch EMtools_dev1.5.0Beta3 https://github.com/zalmoxes-laran/EM-blender-tools.git
cd EM-blender-tools

# Setup development environment (downloads platform wheels)
# For macOS / Linux
chmod +x em.sh
./em.sh setup            # Python 3.11 (Blender 5.0.x)
./em.sh setup 3.13       # Python 3.13 (Blender 5.1+)
./em.sh setup force all  # Force re-download for both versions

# For Windows
.\em.bat setup

# Activate s3dgraphy development version (if working on the library)
./em.sh s3d              # Auto-detect local s3Dgraphy repo
./em.sh s3d off          # Switch back to PyPI version

# Open in VSCode and use the "Blender Development" extension to run Blender
code .
```

See `./em.sh help` for the full list of development commands.

## Roadmap

### Current Focus (v1.5)
- ✅ Extension format migration
- ✅ Automated dependency management and multi-platform wheels
- ✅ s3Dgraphy library integration
- ✅ Modular manager architecture
- ✅ Graph Editor / Viewer
- ✅ Visual Manager with property colouring
- ✅ Landscape multi-graph system
- 🚧 Enhanced graph visualisation (dynamic node generation)
- 🔮 Hybrid enrichment: add US and paradata from XLSX pipeline to an existing in-scene GraphML

## Requirements

- Blender 4.4+ / 5.0.x / 5.1+
- Python 3.11 (Blender 5.0.x) or Python 3.13 (Blender 5.1+)
- 500 MB free disk space
- 4 GB RAM (8 GB recommended)

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md).

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the GNU General Public License v3.0 - see [LICENSE](LICENSE) for details.

## Credits

**Lead Developer**: Emanuel Demetrescu (CNR-ISPC)

**Contributors**: See [Contributors](https://github.com/zalmoxes-laran/EM-blender-tools/graphs/contributors)

## Support

- **Email**: emanuel.demetrescu@cnr.it
- **Telegram**: [@UserGroupEM](https://t.me/UserGroupEM)
- **Issues**: [GitHub Issues](https://github.com/zalmoxes-laran/EM-blender-tools/issues)

## Related Projects

- [Extended Matrix Framework](https://www.extendedmatrix.org)
- [ATON Framework](https://github.com/phoenixbf/aton)
- [s3Dgraphy Library](https://github.com/zalmoxes-laran/s3Dgraphy)

---

<p align="center">
  Made with ❤️ for the Cultural Heritage community
</p>
