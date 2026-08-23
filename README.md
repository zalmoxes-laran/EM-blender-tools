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

### Linking and demoting proxies

A proxy mesh is bound to a stratigraphic node (US, USV, SF…) by name matching:
the link button in the Stratigraphy Manager renames the selected mesh after the
active node. The reverse operation is **Demote proxy** (broken-chain icon, in
the Visual Manager toolbar and next to the link button in the Stratigraphy
Manager; also reachable via F3 search). The button requires a loaded graph and
is greyed out otherwise. Demoting severs the binding in a single
click without deleting anything: the object keeps its mesh, transforms and
modifiers, is renamed with the `_demoted` suffix and immediately repainted with
the magenta "unlinked" colour, so no manual colour-scheme toggle is needed. The
demoted object is unhidden and left selected, so the result is visible even
when the proxy is buried under other geometry. Use it when a mesh was linked to
the wrong node, or to free a temporary geometry from the formal stratigraphy
before joining or re-linking it. `Ctrl+Z` reverses the demotion; selecting
several bound proxies demotes them all at once.

## Documentation

- [**User Manual**](https://docs.extendedmatrix.org/projects/EM-tools/en/1.5/) - Complete documentation
- [**Installation Guide**](https://docs.extendedmatrix.org/projects/EM-tools/en/1.5/installation.html) - Setup instructions
- [**API Reference**](https://docs.extendedmatrix.org/projects/EM-tools/en/1.5/api_reference.html) - Developer documentation

## Community

- [Telegram Group](https://t.me/UserGroupEM) - Join our community
- [Facebook Group](https://www.facebook.com/groups/extendedmatrix) - Extended Matrix users
- [EM Website](https://www.extendedmatrix.org) - Official website

## Where this sits

EMtools is the **3D end** of the Extended Matrix ecosystem: where the *geometry*
of the reasoning lives. Proxies for stratigraphic units, reconstruction models,
orthophotos, georeferencing — all attached to the same graph that
[EMStudio](../EMStudio) edits as a matrix and that [s3Dgraphy](../s3Dgraphy)
knows the meaning of. It can also **publish** a model into a room's asset store,
so a `.blend` stops having to be both the workshop and the archive.

**The whole map:** [`ARCHITECTURE-SYSTEM.md`](../em-server/docs/ARCHITECTURE-SYSTEM.md).

## Installation

### For Users

1. Go to the [Releases](https://github.com/zalmoxes-laran/EM-blender-tools/releases) page
2. Download the file matching your **platform** and **Blender version**:
   - Blender 5.0.x &rarr; `blender50` files (Python 3.11)
   - Blender 5.1+ &rarr; `blender51` files (Python 3.13)
3. In Blender: **Extensions &rarr; Install from Disk**
4. Select the downloaded file (do not unzip) and enable the extension

### Using it, once installed

The addon adds an **EM** tab to the 3D viewport's sidebar (`N` to open it). The
short version of a working session:

1. **Load a graph.** The *EM setup* panel takes a `.graphml` (a yEd matrix) or an
   `.em.json`. Several graphs can be loaded at once — a landscape of studies —
   and each one says whether it is publishable.
2. **Match the 3D to the graph.** Proxies (the boxes that stand for
   stratigraphic units) are named after their US; the panels list what is in the
   graph, what is in the scene, and what is missing from either side. That list
   *is* the job: a US with no proxy and a proxy with no US are both errors you
   want to see.
3. **Work with time.** The epoch manager filters the scene by period, so the
   viewport shows the site as it was rather than everything at once.
4. **Publish.** *Export* writes the Heriverse payload (graph + proxies + models)
   or an RDF projection; a deleted US is **absent** from those, not marked in
   them.
5. **Stay in step with EMStudio.** With the sync panel connected, edits travel
   both ways while you work: the matrix in one window, the 3D in the other, one
   graph underneath.

### For Developers

```bash
# Clone the development branch
git clone --branch EMtools_dev1.5.0Beta3 https://github.com/zalmoxes-laran/EM-blender-tools.git
cd EM-blender-tools

# One-time: create dev venv for VSCode IntelliSense (run once after cloning)
chmod +x em.sh
./em.sh first_setup      # creates .venv/ and points VSCode at it
# On Windows: .\em.bat first_setup

# Setup development environment (downloads platform wheels)
# For macOS / Linux
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

**Build and test, verified on macOS:**

```bash
./em.sh build dev                          # → ../EM_Tools_Releases/em_tools-v<version>.blext
.venv/bin/python -m pytest tests -q        # 127 passed, 1 skipped
./em.sh s3d status                         # which s3dgraphy the Blender extension is using
```

`build` does **not** change the version (that is `./em.sh dev`), and the artefact
lands **outside** the repository, in a sibling `EM_Tools_Releases/` folder — so a
build never dirties the working tree. The tests run headless: they exercise the
parts that do not need `bpy`, and the ones that do are named as such rather than
faked.

> The tests put the sibling **s3Dgraphy checkout** ahead of the installed wheel,
> so they measure the library as it is now. Before using EMtools *inside Blender*
> against a changed library, re-run `./em.sh s3d` — otherwise Blender keeps the
> wheel it was given, and the two disagree in a way that looks like a bug.

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

This project is licensed under the GNU General Public License v3.0 - see [GPL3-license.txt](GPL3-license.txt) for details.

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
