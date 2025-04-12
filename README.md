# Extended Matrix 3D tools (EMTools)

is a Python-based addon that brings the formal language Extended Matrix within the Blender 3D open-source software. It has been designed and developed by E. Demetrescu (CNR-ISPC, former ITABC) and is part of the Extended Matrix Framework (EMF).

With EMtools users can import, manage, visualize, modify, represent and export all the information (geometries, data and paradata) concerning micro and macro scale contexts, single objects or collections of objects.

The [EMtools user manual](https://docs.extendedmatrix.org/projects/EM-tools/en/latest/) is freely available.

Channel to join the community of users [Telegram open-group](https%3A%2F%2Ft.me%2FUserGroupEM&sa=D&sntz=1&usg=AOvVaw2i0GwLjFfh3axOAltYyvlR)

For more details see the [EM-tools page](https://www.extendedmatrix.org/em-framework/emtools) on the EM website

## Main features

* Integration of Extended Matrix language with Blender

* Full support to create and visualize reconstruction hypotheses (EM reconstructive workflow)

* Full support to annotate archaeological stratigraphy in 3D (EM archaeological workflow)

* Full support to annotate masonry stratigraphy (EM architectonical survey workflow)

* Export full dataset to ATON 3 (EMviq app)

* Statistical tools for the reconstrucion (volumes, typo of sources, property density)

## Contribute

You are more than welcome to contribute to the project by spotting bugs/issues and providing code or solutions through pull requests to fix or improve EM functionalities (see TODO list below). Get in touch here on github, through the [telegram open-group](https://t.me/UserGroupEM) or through the other channels.

## Roadmap for EMF 1.5

### s3Dgraphy Library

*Note:* the library is currently developed inside the EM-tools add-on but in the future it will be a stand-alone library. A repo for the documentation of the library is already set-up and under development.

#### Completed Tasks

- [X] **Created Three JSON Files**
  - **Visual Rules JSON**
  - **CIDOC Mapping JSON**
  - **Connection Rules JSON**

- [X] **Added Subclasses of the Stratigraphic Node**
  - To identify various types of stratigraphic nodes for better classification.

- [X] **Added Nodes**
  - **Actor Nodes**
    - Represent individuals or groups involved in the stratigraphy.
  - **Link Nodes**
    - Allow expression of resources connected to reference nodes (e.g., documents, properties).
    - Specify the type of link (e.g., 3D models, JPEGs, PDFs, Zenodo links).
  - [X] **Added a Representation Model Node**
    - Allows for inclusion of representation models within the graph.

- [X] **Modified GraphML Import**
  - Updated to work with the new JSON files, ensuring compatibility.

- [X] **Developed a Parser**
  - Recognizes tags within the Extended Matrix canvas for better data interpretation.

- [X] **Included a Library of Models in Visual Rules**
  - **3D Models** in GLTF format for 3D graph visualization.
  - **2D Icons** in PNG format for node representation.

- [X] **Revised the Architecture of s3Dgraphy**
  - Made the structure more modular for improved scalability and maintenance.

- [X] **Created and Managed Graphs and Multigraphs**
  - Developed a first version of an information propagation algorithm.

- [X] **Work on Connection Rules in JSON**
  - Formalize the connection rules by working on the JSON file of connection rules.
  - Ensure all nodes and connectors are correctly defined.

- [X] **The EM color schema was moved outside the EM tools code and now is part of the s3Dgraphy library**

- [X] **Verify and Extend Property Nodes Using Nomenclature**
  - Check if the property node should have subclasses using the nomenclature of qualia.
  - Find a nomenclature to describe stratigraphic units, possibly using the Getty vocabulary or specialized vocabularies developed in Ariadne.

#### Tasks To Do

- [ ] **Redo the Turtle (`.ttl`) File**
  - Schematize how the data model works.
  - Ensure the data model is clearly defined and up-to-date.

- [ ] **Modify the GraphML parser to handle ParadataGroup nodes connected to a stratigraphic unit**
  - Allow direct connection of stratigraphic units to ParadataGroup nodes
  - Automatically link property nodes within the ParadataGroup to the stratigraphic unit

- [ ] **Create preset qualia vocabulary**
  - Implement standardized property types for the knowledge graph
  - Ensure consistent naming conventions

- [ ] **Publish s3Dgraphy as Standalone Library**
  - Publish s3Dgraphy as a standalone library.
  - Include documentation and a publication to accompany the release.

### EM-tools for Blender

#### Completed Tasks

- [X] **Modified emtools to Integrate with s3Dgraphy**
  - Enabled emtools to work seamlessly with s3Dgraphy, allowing for the import of 3D models.

- [X] **Fix operators in the Epoch Manager with the old approach**
  - [X] **Select**
  - [X] **Set unselectable**
  - [X] **Toggle reconstruction**

- [X] **Rewrite the way EMtools's operators interact with scene lists (like scene.em_list)**
  - [X] **Create a new "ubermethod" in graph.py to find connected nodes with node_type and edge_type as variables**
  - [X] **Create a function that manage both missing proxies and proxies in hidden layers**

- [X] **Implement full multigraph management with graph ID as prefix**
  - Used to enrich node IDs and ensure uniqueness across multiple graphs

- [X] **Heriverse export with texture management**
  - Implemented optimized settings similar to Envik

- [X] **Instanced GLTF export**
  - Added helper for managing model groups

- [X] **New label system**
  - Implemented improved system for creating labels and metric scales

#### Tasks To Do

- [ ] **Fix operators in the Epoch Manager with the old approach**
  - [ ] **Soloing to be done with the new node-based approach**

- [ ] **Develop the 3D GIS mode for EM tools**
  - [X] Adding a section to the UI to switch to simple 3D GIS
  - [ ] Developing an operator to parse xlsx/csv files driven by a JSON mapping schema oriented to QKGs
  - [ ] Developing a fallback simple importer assuming an "ID" column to work with and using all the others columns like properties
  - [ ] Adding a section visual manager to the UI with the ability to show the available properties in the graph as a drop menu
  - [ ] Developing an operator to create a color ramp or other tools to colorize the proxies according to the properties
  - [ ] Documentation of the new tool

- [ ] **Develop a SF panel for extended visualization of data from a standardized excel file**
  - [ ] **Add a file path entry in EMsetup panel**
  - [ ] **Create operator to load xlsx file at convenience and/or automatically at graphml import**
  - [ ] **Create a panel to show extended info for SF - or integrate it in the Stratigraphic Nodes Manager**
  - [ ] **Testing**

- [ ] **Documentation for EMF 1.5**
  - Add "Info" button in the panel linked to the EM Tools manual
  - Include detailed explanations for each node type

- [ ] **Cleanup**
  - Remove updater
  - Remove old JSON configuration files
  - Remove DevUtils

- [ ] **Update website contact information**
  - Add contacts on extendedmatrix.org
  - Add ways for people to join the Extended Matrix Facebook group

## Roadmap for EMF 1.6

### s3Dgraphy Library

- [ ] **Develop Information Propagation Algorithms**
  - Work within Stratigraphy on information propagation algorithms.
  - Possibly place the algorithm in utils or elsewhere within Stratigraphy.

- [ ] **Formalize Data Propagation Rules Using SWRL**
  - Enhance the reasoning capabilities within the Knowledge Graph.

### EM-tools for Blender

- [ ] **Enhance the Activity Manager panel**
  - Add selection buttons
  - Add proxy hiding functionality in 3D space
  - Add functionality to extract more information about activities
  - Show in which epochs nodes exist
  - Show temporal scope of activities

- [ ] **Time branch management**
  - Improve handling of time branches
  - User interface for creating and managing alternative temporal sequences

- [ ] **Panorama management for individual epochs**
  - Add subsection in RM manager
  - Create nodes in JSON for panorama management

- [ ] **Formalize Anastylosis and USWSWS groups**
  - Implement automatic detection based on connections

- [ ] **Modify Continuity Node concept**
  - Consider changing to Discontinuity Node
  - Clarify if it represents destruction or just last sighting
  - Define relationship with negative stratigraphic units

- [ ] **Handle transforming stratigraphic units**
  - Implement dotted connector for units that transform into each other
  - Add sub-panel in Stratigraphy Manager to visualize temporal evolution

- [ ] **Multiple representation of the same unit**
  - Allow showing a unit multiple times to represent all instances where it's observed

- [ ] **Show authors and detailed license for each graph**
  - Implement in EM Setup

- [ ] **Property Density algorithm**
  - Develop visualization to show density of properties behind 3D models
  - Implement both quantitative and qualitative algorithms

## Future Development

- [ ] **Jupyter Notebook integration**
  - Create template using s3Dgraphy
  - Use JSON exported for Heriverse or server system with 3D data

- [ ] **Spatialization tool for documents**
  - Create camera with quad
  - Console to manage focal length, transparency, and x/y shift
  - Add camera/quad pair in s3Dgraphy

- [ ] **Source graph visualization**
  - Develop separate graph view focused on sources and their temporal relationships

- [ ] **Temporal positioning of sources**
  - Research approaches for handling source chronology without creating upward vectors

- [ ] **Geophysics import and annotation system**
  - Develop import and filtering system
  - Add point-cloud and slice visualization
  - Possibly develop as separate project

- [ ] **Territorial graph**
  - Reimplement landscape graph
  - Add topographic units and canvas concept

- [ ] **Terrain and stratigraphy creation from elevation points**
  - Implement handling of elevation points and core samples
  - Develop propagation algorithm based on data
  - Possibly integrate with GRASS or other external libraries

- [ ] **Triple Store database**
  - Create database of holistic documentation for archaeology and cultural heritage
  - Implement search functionality

- [ ] **Tool shelf and search engine**
  - Develop tools to retrieve graph fragments for comparison

- [ ] **DigiLab DB integration**
  - Create system to retrieve data, patterns, and comparisons

- [ ] **AI-based proxy rendering**
  - Connect to Stable Diffusion
  - Create photorealistic renderings based on proxies and node information

- [ ] **Peer review system**
  - Implement collaborative environment for reconstruction review

- [ ] **REST API connection to chronontology**
  - Define chronological epochs in space-time