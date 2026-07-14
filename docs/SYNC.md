# Live sync EMtools ⇄ EMStudio

The EMtools (Blender) side of the ADR-002 live sync — the WS host
(`sync_manager/`), em.json import/export (`emjson_support.py`,
`import_operators/importer_emjson.py`, `export_operators/exporter_emjson.py`),
and the reverse-op emitters (`stratigraphy_manager/data.py`,
`us_helpers.py`) — is documented together with the EMStudio side.

**Full handoff:** `../EMStudio/docs/SESSION-HANDOFF-sync.md`
**Persistent memory:** `project_emstudio_graphml_roundtrip`

(Kept as a thin pointer on purpose — the full doc spans both repos to avoid
divergence. Update the EMStudio handoff, not this file.)
