# EM Tools Roadmap

This document outlines the development roadmap for EM Tools and the Extended Matrix Framework.

## Version 1.5 (Current Release - Q2 2025)

**Philosophy**: Stratigraphic units and paradata are authored in yED/GraphML. Blender enriches the graph with auxiliary 3D properties (RM, RMSF, Surface Areale, spatial documents) that live in the s3dgraphy runtime graph and .blend file. These can be exported to Heriverse but do NOT modify the source GraphML.

### EM-tools for Blender

#### Completed

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
- [x] Landscape/Multigraph system for managing multiple Extended Matrices simultaneously  
- [x] Complete multigraph management with graph ID prefixes  
- [x] CronoFilter (Horizons Manager) with chronological filtering and horizon-based visualization  
- [x] 3D Document Manager with spatial-temporal document management  
- [x] Tapestry Integration for AI-powered archaeological proxy reconstruction (experimental)  
- [x] XLSX merge wizard with conflict resolution and epoch compatibility validation  
- [x] Special Finds visibility controls (show/hide operators)  
- [x] Proxy-to-RM projection system  
- [x] Proxy Box Creator  
- [x] Epoch Manager operators simplification  
  - [x] Select functionality  
  - [x] Remove Set unselectable  
  - [x] Remove Toggle reconstruction  
  - [x] Remove Soloing mode with new node-based approach  
- [x] **Surface Areale System**
  - [x] Surface proxy creation from Grease Pencil contours on Representation Models
  - [x] Three generation strategies: projective, shrinkwrap adaptive, boolean + LOD
  - [x] Automatic complexity classification (Scenario A/B/C with PCA + normal analysis)
  - [x] Hardware-aware benchmark and time estimation per strategy
  - [x] Working Unit (UL) node type for toolmarks and surface treatments
  - [x] Full paradata chain: US -> Property -> Extractor -> Document -> RM
  - [x] Document-RM linking via extended has_representation_model connector

#### In Progress

- [ ] New labeling system for better visualization  
- [ ] Gate experimental features behind `experimental_features` boolean
  - [ ] Hide Save/Export GraphML buttons (write-back not production-ready)
  - [ ] Hide Merge XLSX button
  - [ ] Hide Create Document button (Document Manager)
  - [ ] Hide Create New US option (Surface Areale)

#### Planned (1.5.x patches)

- [ ] Surface Areale: LOD as user option in Boolean strategy
- [ ] Surface Areale: annular shapes (contour with hole)
- [ ] Surface Areale: overlapping areali with Z offset
- [ ] RMDoc persistence: load handler reconstruction from graph (RMSF pattern)
- [ ] Special Finds (SF) extended visualization panel  
  - [ ] File path entry in EMsetup panel  
  - [ ] Automatic XLSX loader at GraphML import  
  - [ ] Extended info panel integration  
  - [ ] Comprehensive testing  

## Version 1.6 (Q4 2025)

**Philosophy**: Full authoring in Blender — create documents, extractors, properties, and stratigraphic units directly in the 3D environment. Requires a fully functional GraphML export to persist new data back to the source file. The hybrid yED/Blender workflow evolves into Blender-first with GraphML as the interchange format.

### Prerequisites (s3dgraphy)

- [ ] **GraphML exporter: standalone node support**
  - Export DocumentNode, ExtractorNode, PropertyNode as independent top-level nodes (not only as ParadataNodeGroup internals)
  - Preserve original `node_id` for imported nodes (round-trip fidelity)
  - Merge logic: distinguish new vs modified vs deleted nodes
  - Preserve yED positions for unmodified nodes

### EM-tools for Blender

- [ ] **Full GraphML round-trip**
  - Import -> enrich in Blender -> export updated GraphML
  - Save GraphML / Save As buttons enabled for production use
  - Merge XLSX enabled for production use

- [ ] **Create US from Blender**
  - Operator already exists in Surface Areale (`_create_us_node()`)
  - Needs GraphML persistence via updated exporter
  - UI: un-gate "Create New US" from experimental

- [ ] **Create Documents from Blender**
  - Operator already exists (`DOCMANAGER_OT_create_document`)
  - Needs GraphML persistence via updated exporter
  - UI: un-gate "Create Document" from experimental

- [ ] **Create Extractors and Properties from Blender**
  - New operators to be implemented
  - Full paradata chain authoring in Blender

- [ ] **RMDoc Manager: advanced operations**
  - Select, rename, remove operators
  - Create RM from document (promote Doc to RM-Doc/RM-SF)

- [ ] **Document Manager: DOSCo integration**
  - Copy files to DOSCo folder with prefix
  - Document type icons in UIList
  - Content import for documents (OBJ, images, DOSCo links)

- [ ] **3D GIS Mode**  
  - UI section for simple 3D GIS switching  
  - XLSX/CSV parser with JSON mapping schema  
  - Fallback importer for basic ID column support  
  - Property-based visualization in Visual Manager  
  - Color ramp tools for proxy colorization  
  - Complete documentation for GIS features  

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


## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute to these roadmap items.

## Tracking Progress

- GitHub Issues: Each roadmap item has a corresponding issue  
- GitHub Projects: Visual kanban board for current development  
- Milestones: Version-based milestones for release planning  

---

*This roadmap is subject to change based on community feedback and development priorities.*
