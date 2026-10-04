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
