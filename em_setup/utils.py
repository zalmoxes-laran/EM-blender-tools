# em_setup/utils.py

import bpy
import os


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
        print(f"⚠️ Invalid GraphML index: {graphml_index}")
        return 0, 0

    graphml = em_tools.graphml_files[graphml_index]

    imported_count = 0
    error_count = 0

    print(f"\n🔄 Auto-import: Checking auxiliary files for '{graphml.name}'...")

    for i, aux_file in enumerate(graphml.auxiliary_files):
        # Salta se auto-reload non è attivo
        if not aux_file.auto_reload_on_em_update:
            continue

        # Verifica che il file/folder sia configurato
        # Per DosCo verifichiamo dosco_folder, per altri tipi filepath
        if aux_file.file_type == "dosco":
            if not aux_file.dosco_folder:
                print(f"⚠️ Skipping '{aux_file.name}': no DosCo folder configured")
                error_count += 1
                continue
        else:
            if not aux_file.filepath:
                print(f"⚠️ Skipping '{aux_file.name}': no filepath configured")
                error_count += 1
                continue

        print(f"📥 Auto-importing '{aux_file.name}' ({aux_file.file_type})...")

        try:
            # Set active auxiliary index and call unified import operator
            graphml.active_auxiliary_index = i
            result = bpy.ops.auxiliary.import_now()

            if result == {'FINISHED'}:
                imported_count += 1
                print(f"✅ Successfully imported '{aux_file.name}'")
            else:
                error_count += 1
                print(f"❌ Failed to import '{aux_file.name}'")

        except Exception as e:
            error_count += 1
            print(f"❌ Error importing '{aux_file.name}': {str(e)}")

    if imported_count > 0:
        print(f"\n✅ Auto-import completed: {imported_count} file(s) imported, {error_count} error(s)")
    elif error_count > 0:
        print(f"\n⚠️ Auto-import completed with {error_count} error(s)")
    else:
        print(f"\nℹ️ No auxiliary files marked for auto-import")

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
            print(f"ℹ️ DosCo already migrated for '{graphml.name}', clearing legacy property")
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
        print(f"✅ Migrated DosCo configuration to Auxiliary Resources")

    if migrated_count > 0:
        print(f"\n✅ DosCo migration completed: {migrated_count} GraphML file(s) migrated")

    return migrated_count
