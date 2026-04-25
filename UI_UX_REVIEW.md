# UI/UX Review — EM-Tools sidebar panels

**Date**: 2026-04-23 · **Scope**: N-panel sidebar in the 3D Viewport, with primary focus on the **EM Annotator** tab.

## Executive summary

The addon already follows a consistent panel shell (header label + `?` help button + boxed steps). The biggest pain points are:

1. **Two panels ship without a manual link** in their header — a regression from the convention.
2. **Panel order numbers have gaps and mismatches**, producing a visually unpredictable ordering in the sidebar.
3. **Experimental labels are sticky** — features that have left experimental status still carry the tag (now fixed for Proxy Box / Surface Areas; others need review).
4. **Tooltip coverage is uneven** — some operators have no `bl_description`, so hovering gives only the label.
5. **Category fragmentation**: three categories (`EM`, `EM Annotator`, `EM Bridge`) host panels whose names don't always make the split obvious.

Below, issues are grouped by priority.

---

## P0 — Bugs / regressions

### P0.1 Surface Areas has no help button

**File**: [surface_areale/ui.py](surface_areale/ui.py) — the panel's `draw()` never calls `em.help_popup`. Every sibling in EM Annotator does.

**Fix**: add the same header row pattern used by Proxy Box (see [proxy_box_creator/ui.py:70-83](proxy_box_creator/ui.py)):

```python
header_row = layout.row(align=True)
header_row.label(text="Surface Areas", icon='MOD_TRIANGULATE')
help_op = header_row.operator("em.help_popup", text="", icon='QUESTION')
help_op.title = "Surface Areas"
help_op.text = "Five-step checklist: pick RM → link Document → choose Extractor → name Property → assign US. Then draw the area."
help_op.url = "panels/surface_areale.html#surface-areas"
help_op.project = 'em_tools'
```

Also requires a corresponding page in the manual repo (check `panels/surface_areale.html` exists — if not, create it).

### P0.2 Proxy Inflate Manager has no help button

**File**: [proxy_inflate_manager/ui.py](proxy_inflate_manager/ui.py) — same omission. Add a help button with a concise summary of what "inflate" does.

---

## P1 — Ordering and navigation

### P1.1 Panel `bl_order` values are inconsistent

EM Annotator tab current order (after today's changes):

| Order | Panel                                     |
|------:|-------------------------------------------|
| 1     | Representation Model (RM)                 |
| 2     | Anastylosis (RMSF)                        |
| 3     | RMDoc Manager                             |
| 4     | Document Manager                          |
| —     | *(no order 5)*                            |
| 6     | Proxy Box                                 |
| 7     | Surface Areas                             |

The RMDoc ↔ Document ordering reads *backwards* from the data-flow: a Document (metadata) exists before its spatialized RMDoc representation. Swap them so new users read the panels top-to-bottom matching the conceptual order:

1. RM → 2. Document → 3. RMDoc → 4. Anastylosis → 5. Proxy Box → 6. Surface Areas

Assign `bl_order` = 1..6 contiguously (no gaps).

### P1.2 Category split is not self-evident

- `EM` — primary EM Tools (setup, graph editor, epoch, stratigraphy, etc.)
- `EM Annotator` — object-to-graph linking (RM, RMDoc, Anastylosis, ProxyBox, SurfaceAreas)
- `EM Bridge` — export / import adapters

The names are fine in isolation, but new users discovering the sidebar have to click each tab to know what's inside. Consider adding a **one-line descriptor** as the first element of each first-load tab, e.g. a dimmed `label` at the top of the first panel in each tab explaining "EM Annotator: link meshes to the extended matrix".

Low priority — defer unless user testing confirms the confusion.

---

## P2 — Experimental labels that may no longer fit

These panels still carry `(Experimental)` in `bl_label`. Verify each before removing:

| Panel                          | File                                       | Line |
|--------------------------------|--------------------------------------------|------|
| Proxy to RM Projection         | proxy_to_rm_projection/ui.py               | 15   |
| Tapestry                       | tapestry_integration/ui.py                 | 17   |
| EMGraph                        | graph_editor/ui.py                         | 358  |
| EMGraph Tools                  | graph_editor/ui.py                         | 30   |
| StratiMiner                    | em_setup/ui.py                             | 1477 |
| Export Statistics              | em_statistics/ui.py                        | 8    |

Suggested convention going forward: **drop `(Experimental)` from the label** once a feature is user-facing and not gated behind `experimental_features`. Keep only a small red banner at the top of the panel body while still beta, so the warning is seen without mis-sorting the sidebar alphabetically.

Today's removal (Proxy Box / Surface Areas) is the pattern to follow.

---

## P3 — Tooltip quality

### P3.1 Operators missing `bl_description`

When `bl_description` is omitted, Blender falls back to the operator's `bl_label` + docstring, which is often terse. A quick sweep should find the worst offenders. For example (in document_manager):

- Operators created for Phase 1 (`RMDOC_OT_set_drive_mode`, `RMDOC_OT_realign`, `RMDOC_OT_remove_camera`) already have descriptions — good.
- Some older operators in `stratigraphy_manager` and `rm_manager` ship with no description.

### P3.2 Write tooltips in the user's voice

Many descriptions read like implementation notes ("Parent camera to quad, installs drivers"). Prefer a goal-oriented phrasing: *"Create a camera aligned to this quad — you can then pilot it to adjust the frame"*. The doc manager overhaul already moved in that direction; extend to other panels incrementally.

### P3.3 Help-popup text should complement, not duplicate, the tooltip

Pattern in use today (e.g. [proxy_box_creator/ui.py:76-83](proxy_box_creator/ui.py)):

```python
help_op.text = (
    "Step 1: pick an anchor Document ...\n"
    "Step 2: record the 7 measurement points ...\n"
    "The proxy name comes from the active Stratigraphic Unit."
)
```

This is good — the popup walks the user through the flow while the hover-tooltip gives a one-liner. Keep the distinction.

---

## P4 — Workflow clarity

### P4.1 Document Manager ↔ RMDoc Manager separation is invisible to newcomers

Two sibling panels manage the same entity at different levels (catalog vs. scene-object). On first encounter, a user won't know which to use. Suggestions:

- **Cross-reference buttons**: in the Document Manager, a button "Show in scene (RMDoc)" that selects the matching rmdoc_list entry. In the RMDoc Manager, "Show source (Document)" that jumps to the Document Manager entry. Partial infra exists (graph traversal selectors) but the cross-tab navigation isn't wired.
- **Unified detail section**: when a doc is selected in either panel, show the same identity strip (name, certainty, epoch, linked US count) so the user knows it's the same underlying entity.

### P4.2 Proxy Box and Surface Areas share the "requirement checklist" pattern — but differ in step count

Proxy Box: 2 steps (anchor doc, record points). Surface Areas: 5 steps. The visual rhythm is the same (boxed rows with checkmark/X + hint), which is good. Consider extracting the pattern into a helper (`draw_requirement_row(layout, num, label, ok, hint)`) — shared utility would reduce drift.

### P4.3 The Phase 1 Document Manager refactor adds new operators that aren't in the UI yet

`em.rmdoc_set_drive_mode` exists but has no UI entry point — currently only reachable via F3 search. Plan for Step 5 of the refactor: expose a compact mode selector in the RMDoc detail view:

```
Mode: [Quad-driven ▾]   [Re-align]   [Remove Camera]
```

The current UI only shows `Re-align` + `Remove Camera` conditionally. Add the drive_mode enum as a dropdown so power-users can switch between Quad-driven, Camera-driven, Unlinked, or No Camera without going through operator search.

---

## P5 — Minor polish

- **Icon consistency**: Proxy Box uses `MESH_CUBE` in both header and title — fine. Surface Areas uses `MOD_TRIANGULATE` — fine. RMDoc uses custom PNG. Document Manager uses custom PNG. Keep the custom PNGs for flagship panels, stock icons for specialized tools — but make sure the stock icons aren't too similar to each other.
- **Disclosure widgets**: Some panels use `bl_options = {'DEFAULT_CLOSED'}`, others don't. Rule of thumb: collapse by default panels that are used only occasionally (Proxy Box, Surface Areas), keep open panels used every session (RM, Document, RMDoc).
- **Error states**: "Load a GraphML first" (with `icon='ERROR'`) is the standard empty state. Surface Areas prints the same when `active_file_index < 0` — good. Proxy Box does the same. Document Manager same. Consistent. ✓
- **Destructive confirmation**: `RMDOC_OT_remove` + `RMDOC_OT_remove_camera` use `invoke_confirm` — good. Audit other delete operators in RM Manager / Anastylosis for the same pattern; at least one operator deletes without asking.

---

## Proposed action list (short-term)

1. **P0.1**: add help button to Surface Areas panel (15 min).
2. **P0.2**: add help button to Proxy Inflate Manager (15 min).
3. **P1.1**: renumber `bl_order` in EM Annotator to 1..6 without gaps (10 min).
4. **P4.3**: add the `drive_mode` selector to the RMDoc panel (Step 5 of the Phase 1 roadmap — already queued).
5. **P2**: audit each `(Experimental)` label, remove the tag where features are production-ready (30 min per panel, including a banner instead).
6. **P3.1**: sweep operators without `bl_description`, add one-liners (1h).
7. **P4.2**: extract `draw_requirement_row` helper and migrate Proxy Box + Surface Areas onto it (45 min).

Everything else (P4.1 cross-references, P1.2 descriptors) is medium-term and benefits from user testing before committing design decisions.
