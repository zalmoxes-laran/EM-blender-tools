# Extended Matrix 3D tools (EMTools)

is a Python-based addon that brings the formal language Extended Matrix within the Blender 3D open-source software. It has been designed and developed by E. Demetrescu (CNR-ISPC, former ITABC) and is part of the Extended Matrix Framework (EMF).

With EMtools users can import, manage, visualize, modify, represent and export all the information (geometries, data and paradata) concerning micro and macro scale contexts, single objects or collections of objects.

The [EMtools user manual](https://docs.extendedmatrix.org/projects/EM-tools/en/latest/) is freely available.

Channel to join the community of users [Telegram open-group](https%3A%2F%2Ft.me%2FUserGroupEM&sa=D&sntz=1&usg=AOvVaw2i0GwLjFfh3axOAltYyvlR)

For more details see the [EM-tools page](https://www.extendedmatrix.org/em-framework/emtools) on the EM website

## Main features:

* Integration of Extended Matrix language with Blender

* Full support to create and visualize reconstruction hypotheses (EM reconstructive workflow)

* Full support to annotate archaeological stratigraphy in 3D (EM archaeological workflow)

* Full support to annotate masonry stratigraphy (EM architectonical survey workflow)

* Export full dataset to ATON 3 (EMviq app)

## Changelog of EM-tools 1.4.x dev

* Initial support of EM 1.4
* Refactoring of the UI
* Adding tools to load xlsx files

## Contribute
You are more than welcome to contribute to the project by spotting bugs/issues and providing code or solutions through pull requests to fix or improve EM functionalities (see TODO list below). Get in touch here on github, through the [telegram open-group](https://t.me/UserGroupEM) or through the other channels.

## TODO list for the upcoming EM-tools 1.4.x dev

### specific task for the s3Dgraphy project

- [ ] check if I can maintain the root Node class cleaner, putting specific properties to subclassess
- [ ] check if some GraphML data can be put into a runtime property (y_position for instance) focusing more into a clean and abstract EM graph
- [ ] continuity node
- [ ] add node and populated lists for Activities
- [ ] move duplication controllers to parsers and nodes constructors
- [ ] add to parser and node constructors the ability to parse new propertes like author, time_Start, time_emd etc...

### other general tools
- [ ] Statistical tools for the reconstrucion (volumes, typo of sources, property density)
- [ ] New label system
- [ ] New section for visual tools
- [ ] Simplified proxy generation