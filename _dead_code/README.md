# _dead_code

Code taken OUT of the add-on and kept for reading. Nothing here is imported or
registered, and the extension build leaves the folder out
(`blender_manifest_template.toml`, `paths_exclude_pattern`).

Each subfolder says why it left. From MICRO-EMTOOLS-MENO-E-MEGLIO (4 October
2026, decisions of E.D. in `AUDIT-UI-EMTOOLS.md`):

- `rm_manager/lod_operators.py`, `anastylosis_manager/operators_lod.py`,
  `anastylosis_manager/lod_utils.py` — **U1**, three codes for one change of
  level. RM Manager and Anastylosis each had their own (`rm.switch_lod`,
  `rm.batch_switch_lod`, `rm.batch_lod_selected`, `rm.open_lod_menu` and the
  `anastylosis.*` copies); the one that stays is the asset versions'
  (`sync_manager/asset_versions.py`: `switch`, `em.asset_lod_step`,
  `em.asset_set_level`, `em.asset_level_menu`), which both panels now call.
  What the old ones did more — the `_LODn` meshes of the same library (the
  tiles of `TempluMare_2021.blend`, the RMSF fragments of `TM0xx.blend`), the
  `_LODn` objects of the scene, the nearest-heavier fallback — moved into
  `asset_versions.named_levels` and `resolve_level`.
- `proxy_inflate_manager/` and the six inflate operators that the Visual
  Manager drew — **U2**, the inflation of the proxies (a Solidify modifier,
  `<name>_inflate`) did not work well (E.D.). Its real purpose — a proxy a
  little outside a flat surface it annotates, so it does not z-fight with the
  RM — is now «Offset proxy» (`proxy_offset/`): a Displace modifier «EM
  offset» along the normals, one distance for the scene. The panel offers to
  remove the old Solidify modifiers a file still carries.
- `graph_editor/` — **U3**, the graph in the Node Editor (EMGraph Tools, four
  panels, and the EMGraph panel of the 3D sidebar). Its own README says why
  and when it might come back.
- `operators/xlsx_wizard.py`, `operators/xlsx_to_graphml.py` — **U4**, the two
  ways from an xlsx to a GraphML file to import again (neither was drawn any
  more: `_draw_graphml_wizard` was defined and called by nothing, measured on
  4 Oct 2026). «Import from tables» (`em.import_from_table`) reads the same
  xlsx through the same mapping (`excel_to_graphml_mapping` is offered with the
  EMdb ones) and makes a real graph saved as em.json in one gesture. The 3D
  GIS mode it replaces (`mode_em_advanced`, `emtools.switch_mode`, the fixed
  graph id `3dgis_graph`) is gone from the code, not kept here.
