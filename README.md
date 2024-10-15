# Extended Matrix 3D tools (EMTools)

is a Python-based addon that brings the formal language Extended Matrix within the Blender 3D open-source software (version 4.2 or newer). It has been designed and developed by E. Demetrescu (CNR-ISPC, former ITABC) and is part of the Extended Matrix Framework (EMF).

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

## Extended Matrix Tool - Version 1.4 Release Notes

### New Features

* **XLSX Reader:** Added functionality to import source files in `.xlsx` format for easier data handling and integration.

* **JSON Exporter for Aton & EMviq:** Extended support for JSON serialization, enabling the export of knowledge graphs for [Aton](https://osiris.itabc.cnr.it/aton/) and specifically for [EMviq](http://osiris.itabc.cnr.it/scenebaker/index.php/projects/emviq/) workflows.
* **External Libraries Installation:** Introduced new systems to easily install and manage external libraries within the tool.
* **Aton Integration:** Added the ability to launch Aton directly from Blender for streamlined workflows.
* **Statistics & Geometry Tools:** New tools for calculating statistics, volumes, and dimensions, including surface areas of wall structures based on selected proxy models.
* **Automatic Property Numbering:** Support for automatic numbering of properties within the Extended Matrix.
* **Collection Exporter for EMviq:** Added functionality to export collections directly to EMviq for enhanced data management.

### Improvements

* **Code Cleanup:** General code optimization and performance improvements to enhance overall tool stability and efficiency.

* **Bug Fixes:** Resolved various issues and added tools for opening node-related resources, such as images, directly from the operating system.

### Extended Functionality

* **Transformation Stratigraphic Unit (TSU):** Version 1.4 introduces support for TSU, allowing for detailed characterization of degradation surfaces.

These updates make the Extended Matrix Tool even more powerful and adaptable to advanced workflows, enhancing integration with Aton and EMviq.

## Contribute

You are more than welcome to contribute to the project by spotting bugs/issues and providing code or solutions through pull requests to fix or improve EM functionalities (see TODO list below). Get in touch here on github, through the [telegram open-group](https://t.me/UserGroupEM) or through the other channels.

## TODO list

* [ ] New label system
* [ ] New section for visual tools
* [ ] Simplified proxy generation
