# import_operators/import_validator.py
"""
Centralized validation for import settings.

ARCHITECTURE: This module centralizes all validation logic for import operations,
providing clear error messages and preventing invalid imports before they start.
"""

import os


class ImportValidator:
    """Validates import settings before creating importer."""

    # ✅ ARCHITECTURE: Validation rules for each import type
    # All validation logic in one place, easy to maintain and extend
    VALIDATION_RULES = {
        'generic_xlsx': {
            'required_fields': ['filepath', 'sheet_name', 'id_column'],
            'mapping_required': False,
            'file_extensions': ['.xlsx', '.xls']
        },

        'emdb_xlsx': {
            'required_fields': ['filepath', 'mapping_name'],
            'mapping_required': True,
            'file_extensions': ['.xlsx', '.xls']
        },

        'pyarchinit': {
            'required_fields': ['filepath', 'mapping_name'],
            'mapping_required': True,
            'file_extensions': ['.sqlite', '.db', '.sql']
        }
    }

    @classmethod
    def validate(cls, import_type: str, settings: dict) -> tuple:
        """
        Validate settings for an import type.

        Args:
            import_type: Type of import
            settings: Settings dictionary to validate

        Returns:
            tuple: (is_valid: bool, error_message: str)
                  If is_valid is True, error_message is empty.
                  If is_valid is False, error_message contains description.

        Example:
            >>> validator = ImportValidator()
            >>> is_valid, error = validator.validate('emdb_xlsx', settings)
            >>> if not is_valid:
            ...     print(f"Validation failed: {error}")
        """
        if import_type not in cls.VALIDATION_RULES:
            return False, f"Unknown import type: {import_type}"

        rules = cls.VALIDATION_RULES[import_type]

        # Check required fields
        for field in rules['required_fields']:
            if not settings.get(field):
                return False, f"Missing required field: {field}"

        # Check mapping if required
        if rules['mapping_required']:
            mapping_name = settings.get('mapping_name')
            if not mapping_name or mapping_name == 'none':
                return False, f"{import_type} requires a valid mapping selection"

        # Check file extension
        filepath = settings.get('filepath', '')
        if filepath:
            _, ext = os.path.splitext(filepath)
            if ext.lower() not in rules['file_extensions']:
                expected = ', '.join(rules['file_extensions'])
                return False, f"Expected file extension: {expected}, got: {ext}"

        # Check file exists
        if filepath and not os.path.exists(filepath):
            # Try Blender path expansion
            try:
                import bpy  # type: ignore
                abs_path = bpy.path.abspath(filepath)
                if not os.path.exists(abs_path):
                    return False, f"File not found: {filepath}"
            except ImportError:
                # Not in Blender environment, skip file existence check
                pass

        return True, ""

    @classmethod
    def validate_or_raise(cls, import_type: str, settings: dict):
        """
        Validate and raise exception if invalid.

        Args:
            import_type: Type of import
            settings: Settings dictionary to validate

        Raises:
            ValueError: If validation fails with descriptive message

        Example:
            >>> try:
            ...     ImportValidator.validate_or_raise('emdb_xlsx', settings)
            ... except ValueError as e:
            ...     print(f"Invalid settings: {e}")
        """
        is_valid, error_msg = cls.validate(import_type, settings)
        if not is_valid:
            raise ValueError(error_msg)

    @classmethod
    def get_validation_rules(cls, import_type: str) -> dict:
        """
        Get validation rules for a specific import type.

        Args:
            import_type: Type of import

        Returns:
            dict: Validation rules

        Raises:
            ValueError: If import_type is unknown
        """
        if import_type not in cls.VALIDATION_RULES:
            raise ValueError(f"Unknown import type: {import_type}")

        return cls.VALIDATION_RULES[import_type].copy()

    @classmethod
    def add_validation_rules(cls, import_type: str, rules: dict):
        """
        Add validation rules for a new import type.

        This allows extending the validator with custom import types.

        Args:
            import_type: Type of import
            rules: Validation rules dictionary with keys:
                  - required_fields: list of required field names
                  - mapping_required: bool
                  - file_extensions: list of allowed file extensions

        Example:
            >>> ImportValidator.add_validation_rules('custom_format', {
            ...     'required_fields': ['filepath', 'config'],
            ...     'mapping_required': False,
            ...     'file_extensions': ['.json', '.xml']
            ... })
        """
        cls.VALIDATION_RULES[import_type] = rules
