# em_setup/utils.py

import bpy
import os
from ..functions import em_log


def auto_import_auxiliary_files(context, graphml_index):
    """
    Itera su tutti i file ausiliari di un GraphML e importa automaticamente
    quelli con la flag auto_reload_on_em_update attiva.

    Args:
        context: Blender context
        graphml_index: Indice del file GraphML nella lista

    Returns:
        tuple: (numero_importati, numero_errori)
    """
    em_tools = context.scene.em_tools

    if graphml_index < 0 or graphml_index >= len(em_tools.graphml_files):
        em_log(f"Invalid GraphML index: {graphml_index}", "WARNING")
        return 0, 0

    graphml = em_tools.graphml_files[graphml_index]

    imported_count = 0
    error_count = 0

    em_log(f"Auto-import: Checking auxiliary files for '{graphml.name}'", "INFO")

    for i, aux_file in enumerate(graphml.auxiliary_files):
        # Salta se auto-reload non è attivo
        if not aux_file.auto_reload_on_em_update:
            continue

        # Verify the required path/folder is configured for this type
        if aux_file.file_type == "dosco":
            if not aux_file.dosco_folder:
                em_log(f"Skipping '{aux_file.name}': no DosCo folder configured", "WARNING")
                error_count += 1
                continue
        elif aux_file.file_type == "resource_collection":
            if not aux_file.resource_folder:
                em_log(f"Skipping '{aux_file.name}': no resource folder configured", "WARNING")
                error_count += 1
                continue
        else:
            if not aux_file.filepath:
                em_log(f"Skipping '{aux_file.name}': no filepath configured", "WARNING")
                error_count += 1
                continue

        em_log(f"Auto-importing '{aux_file.name}' ({aux_file.file_type})", "INFO")

        try:
            # Set active auxiliary index and call unified import operator
            graphml.active_auxiliary_index = i
            result = bpy.ops.auxiliary.import_now()

            if result == {'FINISHED'}:
                imported_count += 1
                em_log(f"Successfully imported '{aux_file.name}'", "INFO")
            else:
                error_count += 1
                em_log(f"Failed to import '{aux_file.name}'", "WARNING")

        except Exception as e:
            error_count += 1
            em_log(f"Error importing '{aux_file.name}': {str(e)}", "ERROR")

    if imported_count > 0:
        em_log(f"Auto-import completed: {imported_count} file(s) imported, {error_count} error(s)", "INFO")

        # Invalidate graph index after importing auxiliary files / resource collections
        from s3dgraphy import get_graph
        from ..graph_index import invalidate_graph_index

        graph = get_graph(graphml.name)
        if graph:
            invalidate_graph_index(graph)
            em_log("Graph edge index invalidated (will rebuild on next use)", "DEBUG")

    elif error_count > 0:
        em_log(f"Auto-import completed with {error_count} error(s)", "WARNING")
    else:
        em_log("No auxiliary files or resource collections marked for auto-import", "INFO")

    return imported_count, error_count


def migrate_legacy_dosco_to_auxiliary(context):
    """
    Migrates legacy DosCo configuration (dosco_dir on GraphMLFileItem)
    to the new Auxiliary Resource system.

    This function should be called on addon load/scene load to ensure
    backward compatibility with older .blend files.

    Args:
        context: Blender context

    Returns:
        int: Number of GraphML files migrated
    """
    em_tools = context.scene.em_tools
    migrated_count = 0

    for graphml in em_tools.graphml_files:
        # Check if legacy dosco_dir is set
        if not hasattr(graphml, 'dosco_dir') or not graphml.dosco_dir:
            continue

        # Check if DosCo auxiliary already exists
        has_dosco_aux = any(aux.file_type == "dosco" for aux in graphml.auxiliary_files)

        if has_dosco_aux:
            # Already migrated, just clear legacy property
            print(f"[EMSetup] DosCo already migrated for '{graphml.name}', clearing legacy property")
            graphml.dosco_dir = ""
            continue

        # Migrate: create new DosCo auxiliary resource
        print(f"🔄 Migrating legacy DosCo for '{graphml.name}'...")

        aux_file = graphml.auxiliary_files.add()
        aux_file.name = "DosCo (migrated)"
        aux_file.file_type = "dosco"
        aux_file.dosco_folder = graphml.dosco_dir
        aux_file.dosco_overwrite_paths = True  # Default from legacy behavior
        aux_file.dosco_preserve_web_urls = True  # Default from legacy behavior
        aux_file.auto_reload_on_em_update = True  # Enable auto-reload by default

        # Clear legacy property
        graphml.dosco_dir = ""

        migrated_count += 1
        print(f"[EMSetup] Migrated DosCo configuration to Auxiliary Resources")

    if migrated_count > 0:
        print(f"\n[EMSetup] DosCo migration completed: {migrated_count} GraphML file(s) migrated")

    return migrated_count
