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
- `thumbnails/` (`thumb_operators.py`, `thumb_utils.py`, `thumb_async.py`) —
  **U5**, the old images of the units: thumbnails built from the
  `resource_folder` of the ACTIVE auxiliary file, keyed by a hash of the path,
  and «Use Resource Collections instead» when there was none (a concept that no
  longer exists). Now `unit_images/`: each image is a resource (sha256 +
  position, the one resolver R1), linked to its unit by `has_linked_resource`
  when the person confirms what the naming convention proposed, searched first
  in the EM standard tree (C1), with its thumbnail in a derived cache keyed by
  sha256 (`~/.em_cache/thumbs`) and its file's state (R2) in the Stratigraphy
  Manager.

From MICRO-EMJSON-DAPPERTUTTO (4 October 2026, decision of E.D.: the GraphML
is read once and never written again, `graphml-solo-in-entrata`):

- `export_operators/exporter_graphml.py` — **G1**, «Save GraphML»
  (`export.graphml_update`, a patch of the GraphML in place with rotating
  backups) and «Save GraphML As…» (`export.graphml_saveas`). Loading a GraphML
  now turns it into an em.json (`em_setup/graphml_entry.py`) and Save / Save As
  write the em.json; the four automatic saves after a creation go through
  `graph_tree.persist_active`.
- `operators/bake_paradata.py` — **G1**, «Bake Paradata into GraphML»
  (`paradata.bake_to_graphml`): it overwrote a GraphML with em_paradata.xlsx
  baked in. Not drawn by any panel (measured). The enrichment of a loaded graph
  by em_paradata stays (auxiliary files), and «Bake auxiliaries into the graph»
  makes it graph-native in the em.json.
- `graphml_lock.py` — **G1**, the write-lock pre-flight for a GraphML held by
  yEd (`abort_if_graphml_locked`). Nothing writes a GraphML any more, so
  nothing calls it.

From MICRO-DOVE-LAVORI-E-LA-STANZA-COLLABORATIVA (5 October 2026), **D1**:

- `server.py` — the «EM Server» panel and the old TCP server it drove. Not
  imported by `__init__.py` for a long time; only `tests/test_ux_panels_layout.py`
  still listed its panel (now it does not).
- `sync_manager/toggle_and_explain.py` — `em.sync_toggle` and
  `em.mode_explain`, registered and drawn by nothing (grep over EM-blender-tools
  and EMStudio, 5 Oct 2026). The mode is changed by the gestures of «Where you
  work» and by EM ▸ Mode (`em.set_mode`).
- `export_manager/panel.py` — the «Export Manager» panel, no longer registered
  (T1): its providers stay the engine and are opened as dialogs from
  EM ▸ Export (`export_manager/dialogs.py`).
- `em_statistics/ui.py` — the «Export statistics» panel, now the dialog
  EM ▸ Export ▸ Export statistics… (`em.export_statistics_dialog`).
- `resources_tab/promote_minio.py` — **F1**, `em.resources_promote_minio`,
  «Promote to MinIO» in Files: a second upload beside Upload, called by nothing
  else. The promotion function stays (the Publication Deck publishes with it).

From MICRO-IL-PANNELLO-DICE-IL-VERO (5 October 2026), **Q5**:

- `export_operators/heriverse_optimisation.py` — the Heriverse exporter's
  optimisation of its own: `compress_textures_in_folder` (the textures of the
  exported models rescaled and recompressed after the export, the old STEP 6)
  and `export_textures` (a per-object texture export with the same
  compression, called by nothing). Draco is off in `heriverse/gltf.py`. E.D.:
  Heriverse receives the `distribution` version made by «Prepare for a use…».
  The properties (`heriverse_use_draco`, `heriverse_draco_level`,
  `heriverse_enable_compression`, …) stay registered: they are saved in .blend
  files; the panel no longer draws them.

From MICRO-HERIVERSE-LEGGE-LO-STUDIO (5 October 2026), **H4**, with the
correction E.D. gave the same evening (versions on disk too):

- `export_operators/heriverse/` — `operator.py` (`export.heriverse`, the
  re-exporter of a Heriverse project tree: models, proxies, tilesets, RMDoc,
  RMSF, DosCo, panoramas, `project.json`, the zip), `json_export.py`
  (`export.heriversejson`), `collections_op.py` and the old `__init__.py`
  that registered them, with `test_export_esiti.py` beside its operator.
  Heriverse reads the study and picks each model's version with the rule of
  s3dgraphy (`version_for`, uses heriverse → aton → web → realtime); a package
  for Heriverse/ATON is a VERSION ON DISK (use `heriverse`/`aton`, made by
  «Prepare for a use…», registered with its sha256), and the Publication Deck
  writes the folder — em.json, project.json, `versions/` — by
  `publication_heriverse.py` and `publication_deck_ui/heriverse.py`. What the
  version reuses stayed live in `export_operators/heriverse/`: the glTF writing
  (`gltf.py`), `utils.py`, the dissemination filter (`dissemination.py`).
  NOT carried into the package yet: proxies, tilesets, RMDoc/RMSF, DosCo and
  panoramas — the methods that made them are here, to be read when they come
  back as versions of their own.
- `export_threaded.py` — the threaded variant of that export, called by nothing.
- `export_manager/providers/heriverse/ui.py` — its settings section.
- `publication_deck_ui/heriverse_package.py` — the Deck's «Package for
  Heriverse», which showed the web versions and then ran `export.heriverse`;
  replaced by `em.deck_heriverse` (two roads) in `publication_deck_ui/heriverse.py`.
