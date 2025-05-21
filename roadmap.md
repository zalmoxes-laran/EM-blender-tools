# EM Tools Roadmap

This document outlines the development roadmap for EM Tools and the Extended Matrix Framework.

## Version 1.5 (Current Development - Q1 2025)

### EM-tools for Blender

#### ✅ Completed

- [x] Migration to Blender Extension format  
- [x] Automatic dependency management via wheels  
- [x] GitHub Actions for automated releases  
- [x] Heriverse export functionality  
- [x] GPU instancing support  
- [x] Development scripts and improved contributor workflow  
- [x] Detection of placeholder dates in GraphML (XX)  
- [x] Improved robustness of GraphML import  
- [x] Warning system for incomplete GraphML files  
- [x] Support for graph code prefixes in objects and nodes  
- [x] Reduced UI overhead in Paradata Manager  
- [x] Reorganization of "Utilities & Settings" section  

#### 🚧 In Progress

- [ ] Complete multigraph management with graph ID prefixes  
- [ ] New labeling system for better visualization  
- [ ] Epoch Manager operators simplification  
  - [ ] Select functionality  
  - [ ] Remove Set unselectable  
  - [ ] Remove Toggle reconstruction  
  - [ ] Remove Soloing mode with new node-based approach  

#### 📋 Planned

- [ ] 3D GIS mode for EM tools  
  - [ ] UI section for simple 3D GIS switching  
  - [ ] XLSX/CSV parser with JSON mapping schema  
  - [ ] Fallback importer for basic ID column support  
  - [ ] Property-based visualization in Visual Manager  
  - [ ] Color ramp tools for proxy colorization  
  - [ ] Complete documentation for GIS features  

- [ ] Special Finds (SF) extended visualization panel  
  - [ ] File path entry in EMsetup panel  
  - [ ] Automatic XLSX loader at GraphML import  
  - [ ] Extended info panel integration  
  - [ ] Comprehensive testing  

### s3Dgraphy Library

*Note: This library is currently developed within EM-tools but will become a standalone library*

#### ✅ Completed

- [x] Three core JSON files (Visual Rules, CIDOC Mapping, Connection Rules)  
- [x] Stratigraphic node subclasses  
- [x] Actor and Link nodes implementation  
- [x] Representation Model node  
- [x] GraphML import compatibility  
- [x] Tag parser for EM canvas  
- [x] 3D model library (GLTF) and 2D icons (PNG)  
- [x] Modular architecture revision  
- [x] Information propagation algorithm (v1)  
- [x] Color schema migration to s3Dgraphy  

#### 📋 Planned

- [ ] ParadataGroup node handling for stratigraphic units  
- [ ] Preset qualia vocabulary implementation  
- [ ] Standalone library publication with documentation  

## Version 1.6 (Q3 2025)

### EM-tools for Blender

- [ ] **Enhanced Activity Manager**  
  - Selection buttons  
  - Proxy hiding in 3D space  
  - Extended activity information extraction  
  - Epoch existence visualization  
  - Temporal scope display  

- [ ] **Time Branch Management**  
  - Improved branch handling  
  - UI for alternative temporal sequences  

- [ ] **Panorama Management**  
  - RM manager subsection  
  - JSON nodes for panorama handling  

- [ ] **Formalized Groups**  
  - Anastylosis and USWSWS group detection  
  - Automatic identification based on connections  

- [ ] **Continuity/Discontinuity Nodes**  
  - Concept refinement  
  - Relationship with negative stratigraphic units  

- [ ] **Transforming Units**  
  - Dotted connector implementation  
  - Temporal evolution visualization  

- [ ] **Multiple Unit Representation**  
  - Show units in all observed instances  

- [ ] **Enhanced Metadata**  
  - Author information per graph  
  - Detailed license display in EM Setup  

- [ ] **Property Density Algorithm**  
  - Visualization for property density in 3D models  
  - Quantitative and qualitative algorithms  

- [ ] **Image Viewing System**  
  - Direct image display in EM-Tools  
  - JSON-LD Tropi file import  
  - Excel-based image referencing  
  - Folder-based association  
  - Navigation interface with thumbnails  

### s3Dgraphy Library

- [ ] Information propagation algorithms  
- [ ] SWRL formalization for data propagation  
- [ ] Enhanced reasoning capabilities  

## Future Development (2026 and beyond)

### Integration Projects

- [ ] **Jupyter Notebook Integration**  
  - Template creation using s3Dgraphy  
  - JSON export for Heriverse  

- [ ] **Document Spatialization**  
  - Camera quad creation  
  - Focal length and transparency management  
  - s3Dgraphy camera/quad pairs  

- [ ] **Geophysics System**  
  - Import and filtering  
  - Point-cloud visualization  
  - Slice visualization  

### Advanced Features

- [ ] **Source Graph Visualization**  
- [ ] **Temporal Source Positioning**  
- [ ] **Territorial Graph Implementation**  
- [ ] **Terrain Creation from Elevation Data**  
- [ ] **Direct support to Triple Store Database**  
- [ ] **DigiLab DB Integration**  
- [ ] **AI-based Proxy Rendering**  
- [ ] **Peer Review System**  
- [ ] **REST API for Chronontology**  

## Release Schedule

> 📅 **Target Date** refers to the expected quarter of release:
> - Q1 = January–March
> - Q2 = April–June
> - Q3 = July–September
> - Q4 = October–December  
> These are estimated windows and may shift based on development priorities.


| Version | Target Date | Type    | Focus                          |
|---------|-------------|---------|--------------------------------|
| 1.5.0   | Q1 2025     | Minor   | Extension format, dependencies |
| 1.5.1   | Q2 2025     | Patch   | Bug fixes, stability           |
| 1.6.0   | Q3 2025     | Minor   | Activity Manager, Time Branches|

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute to these roadmap items.

## Tracking Progress

- 🏷️ **GitHub Issues**: Each roadmap item has a corresponding issue  
- 📊 **GitHub Projects**: Visual kanban board for current development  
- 🔄 **Milestones**: Version-based milestones for release planning  

---

*This roadmap is subject to change based on community feedback and development priorities.*
