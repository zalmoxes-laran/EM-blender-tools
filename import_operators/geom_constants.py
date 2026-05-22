"""Single source of truth for custom property keys, collection names,
and other magic strings used by the PyArchInit geometry import feature.

Keep all string literals here so renaming is a one-file change and
typos cannot drift across modules.
"""

# Custom property keys on Blender objects
PROP_US_NODE_ID = "em_us_node_id"
PROP_US_NAME = "em_us_name"
PROP_GRAPH_CODE = "em_graph_code"
PROP_PYARCHINIT_SOURCE = "em_pyarchinit_source"
PROP_PYARCHINIT_US_KEY = "em_pyarchinit_us_key"
PROP_IMPORT_TIMESTAMP = "em_import_timestamp"
PROP_ORIGINAL_VERT_COUNT = "em_original_vert_count"
PROP_IMPORTED_MESH_HASH = "em_imported_mesh_hash"
PROP_US_ORPHAN = "em_us_orphan"
PROP_IS_IMPORTED_GEOM = "em_is_imported_geom"
PROP_IS_BACKUP = "em_is_backup"

# Custom attribute on s3dgraphy node (reverse link)
NODE_ATTR_IMPORTED_GEOM_OBJ_NAME = "imported_geom_obj_name"

# Collection names
COLL_US_GEOMETRIES = "EM_US_Geometries"
COLL_US_ORPHAN_POLYGONS = "EM_US_OrphanPolygons"
COLL_US_ORPHANS = "EM_US_Orphans"
COLL_BACKUP_PREFIX = "_Backups_"

# Object name suffix used when colliding with a pre-existing non-imported object
NAME_SUFFIX_IMPORTED = ".imported"

# Aux orphan payload discriminator values (consumed by aux_import.py)
ORPHAN_KIND_POLYGON_NO_US = "polygon_no_us"

# Graph attribute keys
GRAPH_ATTR_AUX_US_NO_GEOM = "aux_us_no_geom"
