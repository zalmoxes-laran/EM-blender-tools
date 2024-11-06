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

## Roadmap for the upcoming s3Dgraphy library for EMF 1.5

*Note:* the library is currently developed inside the EM-tools add-on but in the future it will be a stand-alone library. A repo for the documentation of the library is already set-up and under development.

### Completed Tasks

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

- [X] **Modified GraphML Import**
  - Updated to work with the new JSON files, ensuring compatibility.

- [X] **Developed a Parser**
  - Recognizes tags within the Extended Matrix canvas for better data interpretation.

- [X] **Added a Representation Model Node**
  - Allows for inclusion of representation models within the graph.

- [X] **Included a Library of Models in Visual Rules**
  - **3D Models** in GLTF format for 3D graph visualization.
  - **2D Icons** in PNG format for node representation.

- [X] **Revised the Architecture of s3Dgraphy**
  - Made the structure more modular for improved scalability and maintenance.

- [X] **Created and Managed Graphs and Multigraphs**
  - Developed a first version of an information propagation algorithm.

### Tasks To Do

- [ ] **Verify and Extend Property Nodes Using Nomenclature**
  - Check if the property node should have subclasses using the nomenclature of qualia.
  - Find a nomenclature to describe stratigraphic units, possibly using the Getty vocabulary or specialized vocabularies developed in Ariadne.
  - *Note*: This task is closely linked to a similar task in the EM development.

- [ ] **Work on Connection Rules in JSON**
  - Formalize the connection rules by working on the JSON file of connection rules.
  - Ensure all nodes and connectors are correctly defined.

- [ ] **Redo the Turtle (`.ttl`) File**
  - Schematize how the data model works.
  - Ensure the data model is clearly defined and up-to-date.

- [ ] **Map to CIDOC Using Updated JSON**
  - Ensure compatibility and standardization with CIDOC CRM.
  - Update the JSON mapping file as needed.

- [ ] **Formalize EM Colors in s3Dgraphy Library**
  - Define and implement the color schemes used in Extended Matrix within the s3Dgraphy library.
  - *Note*: This task is linked to Task 16 in Project C.

- [ ] **Publish s3Dgraphy as Standalone Library**
  - Publish s3Dgraphy as a standalone library.
  - Include documentation and possibly a publication to accompany the release.

- [ ] **Publish Heritage Multidimensional Graph (HMG)**
  - Publish the Heritage Multidimensional Graph, for which a LaTeX draft is already developed.
  - This publication will detail the theoretical framework and applications.


## Future versions of s3Dgraphy

- [ ] **Develop Information Propagation Algorithms**
  - Work within Stratigraphy on information propagation algorithms.
  - Possibly place the algorithm in utils or elsewhere within Stratigraphy.

- [ ] **Formalize Data Propagation Rules Using SWRL**
  - Enhance the reasoning capabilities within the Knowledge Graph.


## Roadmap for the upcoming EM-tools for Blender (EMF 1.5)

### Completed Tasks

- [X] **Modified emtools to Integrate with s3Dgraphy**
  - Enabled emtools to work seamlessly with s3Dgraphy, allowing for the import of 3D models.

### Tasks To Do

- [ ] **Populate New Lists**
  - **Activities List**
    - Populate with activity data for better organization.
  - **Time Branches List**
    - Populate to manage alternative temporal sequences.
  - **Task**: Implement functionality to read and populate these lists.

- [ ] **Develop a Filtering System**
  - Create a system to filter nodes, allowing users to visualize only a subset of stratigraphic units.
  - Improves usability when dealing with complex graphs.

- [ ] **Integrate IDs from Extended Matrix Canvas Tags**
  - Implement a system to append the ID from the canvas tags as a suffix to stratigraphic unit names.
  - **Objective**: Ensure unique naming of units to allow importing stratigraphies from different graphs into the same scene.

- [ ] **Enhance Node Management**
  - Improve handling of newly added nodes such as authors, licenses, time branches, and activities.
  - **Task**: Develop features to manage these nodes effectively within emtools.

- [ ] **Modify Code for Visual Rules in Stratigraphic Nodes**
  - Modify the code to read the visual rules file for converting stratigraphic nodes into colors.
  - *Note*: This task is related to Task 11 in Project B.

- [ ] **Develop JSON Exporter for Heritage Metaverse**
  - Create a JSON exporter that prepares data for use in the Heritage Metaverse.
  - Ensure compatibility and proper data formatting.

- [ ] **Debugging in Extended Matrix Tool**
  - **a.** Debug how paradata are presented in the Extended Matrix Tool.
  - **b.** Correct bugs in handling epoch nodes within the tool.

## Future versions of EM-tools

- [ ] **Develop a JSON Importer with Folder Structure**
  - Develop a JSON importer that uses a folder structure for files.
  - Enable usage outside Blender and yED, allowing other applications to access and use the data.
  - Aim to establish a standard structure for critical models and virtual reconstructions.
  - *Note*: This is for future development.