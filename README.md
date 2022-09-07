# Extended Matrix 3D tools for Blender

[Official EM website](http://extendedmatrix.org) | 
[Telegram open-group](https://t.me/UserGroupEM) | 

<!---
![Header](./public/res/header.jpg)
-->

[Extended Matrix 3D tools](http://extendedmatrix.org) - shortly EMBT, is an addon for Blender 3.x designed and developed by E. Demetrescu (CNR ISPC, ex ITABC) - EM 3D tools offers:

* Integration of Extended Matrix language with Blender
* Full support to create and visualize reconstruction hypotheses (EM reconstructive workflow)
* Full support to annotate archaeological stratigraphy in 3D (EM archaeological workflow)
* Full support to annotate masonry stratigraphy (EM architectonical survey workflow) 
* Export full dataset to ATON 3 (EMviq app)

## Getting started (quick)
1) Preferably install the addon using the [last stable version](https://github.com/zalmoxes-laran/ExtendedMatrix/raw/main/03_EMF/EM-blender-tools_1.2stable.zip) from the [EM site](https://www.extendedmatrix.org/download). Please use directly the github version here only if you know how to handle it (more for developers..).

2) Quickstart (to come..) 

# Citation
You can cite Extended Matrix   using with the following BibTeX entry:
```
@article{demetrescu_archaeological_2015,
	title = {Archaeological {Stratigraphy} as a formal language for virtual reconstruction. {Theory} and practice},
	volume = {57},
	copyright = {All rights reserved},
	issn = {0305-4403},
	url = {http://www.sciencedirect.com/science/article/pii/S0305440315000382},
	doi = {10.1016/j.jas.2015.02.004},
	abstract = {Abstract In recent years there has been a growing interest in 3D acquisition techniques in the field of cultural heritage, yet, at the same time, only a small percentage of case studies have been conducted on the virtual reconstruction of archaeological sites that are no longer in existence. Such reconstructions are, at times, considered âartisticâ or âaestheticâ endeavors, as the complete list of sources used is not necessarily provided as a reference along with the 3D representation. One of the reasons for this is likely the lack of a shared language in which to store and communicate the steps in the reconstruction process. This paper proposes the use of a formal language with which to keep track of the entire virtual reconstruction process. The proposal is based on the stratigraphic reading approach and aims to create a common framework connecting archaeological documentation and virtual reconstruction in the earliest stages of the survey. To this end, some of the tools and standards used in archaeological research have been extended to taxonomically annotate both the validation of the hypothesis and the sources involved.},
	journal = {Journal of Archaeological Science},
	author = {Demetrescu, Emanuel},
	year = {2015},
	keywords = {Extended Matrix},
	pages = {42--55},
	file = {Demetrescu - 2015 - Archaeological Stratigraphy as a formal language f.pdf:/Users/emanueldemetrescu/Zotero/storage/SVED9M9V/Demetrescu - 2015 - Archaeological Stratigraphy as a formal language f.pdf:application/pdf},
}
```

or - as software - using the Zenodo DOI [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.5957132.svg)](https://doi.org/10.5281/zenodo.5957132) with the following BibTeX entry:
```
@software{emanuel_demetrescu_2022_5957495,
  author       = {Emanuel Demetrescu},
  title        = {zalmoxes-laran/ExtendedMatrix: v.1.2.0},
  month        = feb,
  year         = 2022,
  publisher    = {Zenodo},
  version      = {v.1.2.0},
  doi          = {10.5281/zenodo.5957495},
  url          = {https://doi.org/10.5281/zenodo.5957495}
}
```

# Publications
Main bibliographical reference (open access) of the current version of the EM (1.2) is:

*Demetrescu, Emanuel, e Daniele Ferdani. 2021. «From Field Archaeology to Virtual Reconstruction: A Five Steps Method Using the Extended Matrix». Applied Sciences 11 (11). https://doi.org/10.3390/app11115206.*

<!---
You can find [here](url) a complete list of publications where EM was employed in different national and international projects.
-->

# Contribute
You are more than welcome to contribute to the project by spotting bugs/issues and providing code or solutions through pull requests to fix or improve EM functionalities (see TODO list below). Get in touch here on github, through the [telegram open-group](https://t.me/UserGroupEM) or through the other channels.

# TODO list

## EM
- [ ] Coloured nodes in the EM layout
- [ ] Alternative hypothesis formalization
- [ ] Fusion of epoch and reconstructive epoch
- [ ] New metaphors of visualization for anastylosis and virtual restoration
- [ ] Formalization of color maps to visualize statistical data about the reconstruction (volumes, typo of sources, property density)

## EMF

- [ ] Adding support to switch on and off the reconstructin per single epoch
- [ ] Statistical tools for the reconstrucion (volumes, typo of sources, property density)
- [ ] New label system
- [ ] New section for visual tools
- [ ] Simplified proxy generation