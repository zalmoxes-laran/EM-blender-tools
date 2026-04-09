# Extended Matrix 3D tools (EMTools)

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/zalmoxes-laran/EM-blender-tools)](https://github.com/zalmoxes-laran/EM-blender-tools/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Blender](https://img.shields.io/badge/Blender-4.0+-orange.svg)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)

EMTools is a Blender extension that brings the formal language Extended Matrix within Blender 3D. Designed and developed by E. Demetrescu (CNR-ISPC), it's part of the Extended Matrix Framework (EMF).

## 🚀 Features

* **Extended Matrix Integration** - Full support for EM language in Blender
* **Archaeological Workflows** - 3D stratigraphic annotation and analysis
* **Reconstruction Hypotheses** - Create and manage multiple reconstruction scenarios
* **Data Export** - Export to ATON 3 (EMviq app) and various formats
* **Visual Analysis** - Period-based visualization, custom display modes
* **Statistical Tools (experimental)** - Volume calculations, source analysis, property density

## 📚 Documentation

- [**User Manual**](https://docs.extendedmatrix.org/projects/EM-tools/en/latest/) - Complete documentation
- [**Installation Guide**](https://docs.extendedmatrix.org/projects/EM-tools/en/latest/installation.html) - Setup instructions
- [**API Reference**](https://docs.extendedmatrix.org/projects/EM-tools/en/latest/api.html) - Developer documentation

## 💬 Community

- [Telegram Group](https://t.me/UserGroupEM) - Join our community
- [Facebook Group](https://www.facebook.com/groups/extendedmatrix) - Extended Matrix users
- [EM Website](https://www.extendedmatrix.org) - Official website

## 🔧 Installation

### For Users

1. Download the latest `.blext` file from [Releases](https://github.com/zalmoxes-laran/EM-blender-tools/releases)
2. In Blender: `Edit → Preferences → Add-ons → Install from Disk`
3. Select the downloaded file and enable the addon

### For Developers

```bash
# Clone repository in a folder (not in the Blender paths..)
git clone --branch EMtools_3dgraphy https://github.com/zalmoxes-laran/EM-blender-tools.git
cd EM-blender-tools

# Setup development environment

# For windows
.\em.bat setup

# For mac/linux
chmod +x em.sh
./em.sh setup

# Open in VSCode
code .

# Install "blender Development" addon for Visual Studio Code and use it to run Blender

```

See [Development Guide](docs/installation.rst#development-setup) for detailed instructions.

## 🗺️ Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features and development timeline.

### Current Focus (v1.5)
- ✅ Extension format migration
- ✅ Automated dependency management
- 🚧 Enhanced graph visualization
- 🔮 Hybrid enrichment: add US and paradata from XLSX pipeline to an existing in-scene GraphML

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md).

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📋 Requirements

- Blender 4.0+
- Python 3.11 (bundled with Blender)
- 500MB free disk space
- 4GB RAM (8GB recommended)

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see [LICENSE](LICENSE) for details.

## 🏆 Credits

**Lead Developer**: Emanuel Demetrescu (CNR-ISPC)

**Contributors**: See [Contributors](https://github.com/zalmoxes-laran/EM-blender-tools/graphs/contributors)

## 📞 Support

- 📧 **Email**: emanuel.demetrescu@cnr.it
- 💬 **Telegram**: [@UserGroupEM](https://t.me/UserGroupEM)
- 🐛 **Issues**: [GitHub Issues](https://github.com/zalmoxes-laran/EM-blender-tools/issues)

## 🔗 Related Projects

- [Extended Matrix Framework](https://www.extendedmatrix.org)
- [ATON Framework](https://github.com/phoenixbf/aton)
- [s3Dgraphy Library](https://github.com/zalmoxes-laran/s3Dgraphy) *(coming soon)*

---

<p align="center">
  Made with ❤️ for the Cultural Heritage community
</p>
