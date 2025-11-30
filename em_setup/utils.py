# em_setup/utils.py

import bpy


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

        # Verifica che il file sia configurato
        if not aux_file.filepath:
            print(f"⚠️ Skipping '{aux_file.name}': no filepath configured")
            error_count += 1
            continue

        print(f"📥 Auto-importing '{aux_file.name}' ({aux_file.file_type})...")

        try:
            # Chiama l'operatore di import
            result = bpy.ops.em.import_3dgis_database(
                auxiliary_mode=True,
                graphml_index=graphml_index,
                auxiliary_index=i
            )

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
