"""Handlers for the Document Manager.

Note: Unlike RM Manager and Anastylosis Manager, the Document Manager does NOT
use a load_post handler. The s3dgraphy graph lives in memory only — it is not
saved in the .blend file. So at load_post time there is no graph to sync from.

Instead, sync_doc_list() is called directly at the end of GraphML import
(in import_operators/importer_graphml.py) when em_sources_list is freshly populated.
"""

# This module is intentionally kept for documentation and future use.
# If a load_post handler becomes needed (e.g. for .blend-only state
# that doesn't depend on the graph), add it here following the pattern
# in rm_manager/handlers.py.
