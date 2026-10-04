# graph_editor (dead code)

**What it was.** «EMGraph Tools» in Blender's Node Editor — the EM graph drawn
as a node tree (`EMGraphNodeTreeType`, one node type per EM node), four panels
(main, edge filters, appearance, node info), the «EMGraph» panel in the 3D
sidebar, the selection kept in sync between the two, a keymap.

**Why it left** (MICRO-EMTOOLS-MENO-E-MEGLIO, U3, 4 October 2026; decision of
E.D. in `AUDIT-UI-EMTOOLS.md`). The canvas of the graph is EMStudio: drawing it
a second time inside Blender gave two editors of the same graph that did not
agree (the filters had their own lists of edge types, and `get_connection_rules`
had been reading a module s3Dgraphy removed in April 2026, so the context view
was empty for months without anyone noticing). In Blender what is needed is
selecting an object selects its node in EMStudio (Sidecar / room) and back.

**What was checked when it left.** No other module imports it (the only call
from outside, the «open in Graph Viewer» button of EM Data Tree, experimental
only, went with it); the add-on loads without it and without errors
(`tests/blender_smoke_without_graph_editor.py`). Its test,
`tests/test_graph_editor_spellings.py`, came here with it.

**Maybe it comes back** as a *landscape* view that orchestrates several graphs
at once — the files of a project and how they connect — which is not what this
code does and is still to be thought through. If it does, start from the idea,
not from this code.
