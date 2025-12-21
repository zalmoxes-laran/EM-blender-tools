# import_operators/importer_registry.py
"""
Registry pattern for import formats.
Centralizes configuration for all supported import formats.

ARCHITECTURE: This module provides a scalable way to add new import formats
without modifying the main import operator. Each format is configured once
and the registry handles parameter validation and importer instantiation.
"""

from .importer_xlsx import GenericXLSXImporter
from s3dgraphy.importer.mapped_xlsx_importer import MappedXLSXImporter
from s3dgraphy.importer.pyarchinit_importer import PyArchInitImporter


class ImporterConfig:
    """Configuration for a single importer type."""

    def __init__(self, importer_class, required_params, optional_params=None):
        """
        Initialize importer configuration.

        Args:
            importer_class: The importer class to instantiate
            required_params: List of required parameter names
            optional_params: List of optional parameter names
        """
        self.importer_class = importer_class
        self.required_params = required_params
        self.optional_params = optional_params or []

    def build_kwargs(self, settings, existing_graph):
        """
        Build kwargs for importer from settings.

        Args:
            settings: Import settings dictionary
            existing_graph: Existing graph for EM_ADVANCED mode, None for 3DGIS

        Returns:
            dict: Kwargs ready to pass to importer __init__

        Raises:
            ValueError: If required parameter is missing
        """
        kwargs = {
            'existing_graph': existing_graph,
            'overwrite': True
        }

        # Add required params
        for param in self.required_params:
            if param not in settings:
                raise ValueError(f"Missing required parameter: {param}")
            kwargs[param] = settings[param]

        # Add optional params if present
        for param in self.optional_params:
            if param in settings:
                kwargs[param] = settings[param]

        return kwargs


# ✅ ARCHITECTURE: Central registry of all supported import formats
# Adding a new format is as simple as adding an entry here
IMPORTER_REGISTRY = {
    'generic_xlsx': ImporterConfig(
        importer_class=GenericXLSXImporter,
        required_params=['filepath', 'sheet_name', 'id_column'],
        optional_params=['desc_column']
    ),

    'emdb_xlsx': ImporterConfig(
        importer_class=MappedXLSXImporter,
        required_params=['filepath', 'mapping_name'],
        optional_params=[]
    ),

    'pyarchinit': ImporterConfig(
        importer_class=PyArchInitImporter,
        required_params=['filepath', 'mapping_name'],
        optional_params=['table_name']
    ),

    # ✅ EXTENSIBILITY: Adding new formats is easy - just add entry here:
    #
    # 'arches': ImporterConfig(
    #     importer_class=ArchesImporter,
    #     required_params=['filepath', 'graph_uuid'],
    #     optional_params=['resource_type']
    # ),
    #
    # 'cidoc_crm': ImporterConfig(
    #     importer_class=CIDOCCRMImporter,
    #     required_params=['filepath', 'entity_mapping'],
    #     optional_params=['namespace']
    # ),
}


def create_importer(import_type: str, settings: dict, existing_graph=None):
    """
    Factory function to create appropriate importer.

    This function provides a centralized, validated way to create importers
    without requiring modifications to the main operator code.

    Args:
        import_type: Type of import (e.g. 'emdb_xlsx', 'pyarchinit', 'generic_xlsx')
        settings: Import settings dictionary
        existing_graph: Existing graph for EM_ADVANCED mode, None for 3DGIS

    Returns:
        Configured importer instance

    Raises:
        ValueError: If import_type is unknown or required params missing

    Example:
        >>> settings = {
        ...     'import_type': 'emdb_xlsx',
        ...     'filepath': '/path/to/file.xlsx',
        ...     'mapping': 'my_mapping'
        ... }
        >>> importer = create_importer('emdb_xlsx', settings, existing_graph=None)
        >>> graph = importer.parse()
    """
    if import_type not in IMPORTER_REGISTRY:
        available = ', '.join(IMPORTER_REGISTRY.keys())
        raise ValueError(
            f"Unknown import type '{import_type}'. "
            f"Available types: {available}"
        )

    config = IMPORTER_REGISTRY[import_type]

    try:
        kwargs = config.build_kwargs(settings, existing_graph)
    except ValueError as e:
        raise ValueError(f"Invalid settings for {import_type}: {str(e)}")

    return config.importer_class(**kwargs)


def get_supported_formats():
    """
    Get list of supported import formats.

    Returns:
        list: List of supported format identifiers
    """
    return list(IMPORTER_REGISTRY.keys())


def get_required_params(import_type: str):
    """
    Get required parameters for a specific import type.

    Args:
        import_type: Type of import

    Returns:
        list: List of required parameter names

    Raises:
        ValueError: If import_type is unknown
    """
    if import_type not in IMPORTER_REGISTRY:
        raise ValueError(f"Unknown import type: {import_type}")

    return IMPORTER_REGISTRY[import_type].required_params
