# export_operators/heriverse/utils.py
"""Small helpers used by the Heriverse exporter."""

import bpy


def clean_filename(filename: str) -> str:
    """Clean filename from invalid characters and spaces.

    Replaces spaces with underscores, strips characters that are unsafe on most
    filesystems, and drops non-ASCII characters.
    """
    filename = filename.replace(' ', '_')

    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')

    filename = ''.join(c for c in filename if c.isascii())
    return filename


def find_layer_collection(layer_collection, collection_name):
    """Trova ricorsivamente un layer_collection dato il nome della collection."""
    if layer_collection.name == collection_name:
        return layer_collection

    for child in layer_collection.children:
        found = find_layer_collection(child, collection_name)
        if found:
            return found
    return None


def get_collection_for_object(obj):
    """Trova la collection principale di un oggetto."""
    for collection in bpy.data.collections:
        if obj.name in collection.objects:
            return collection.name
    return None
