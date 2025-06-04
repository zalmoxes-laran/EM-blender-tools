"""
Material Override System for Linked Objects
This module handles the creation and management of temporary material overrides
for linked objects that cannot have their materials modified directly.
"""

import bpy


class MaterialOverrideManager:
    """
    Singleton manager for handling temporary material overrides.
    Keeps track of all overrides to ensure proper cleanup.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MaterialOverrideManager, cls).__new__(cls)
            cls._instance.overrides = {}
            cls._instance.temp_materials = {}
        return cls._instance
    
    def create_override(self, obj):
        """
        Create a temporary material override for a linked object.
        
        Args:
            obj: Linked Blender object
            
        Returns:
            True if override was created successfully
        """
        if not obj.library:
            # Not a linked object, no override needed
            return True
        
        if obj.name in self.overrides:
            # Override already exists
            return True
        
        try:
            # Store original materials
            original_materials = [mat for mat in obj.data.materials]
            
            # Create temporary copies of materials
            temp_materials = []
            for i, original_mat in enumerate(original_materials):
                if original_mat:
                    # Create temporary material copy
                    temp_mat_name = f"TEMP_{obj.name}_{original_mat.name}_{i}"
                    temp_mat = original_mat.copy()
                    temp_mat.name = temp_mat_name
                    temp_materials.append(temp_mat)
                    
                    # Store temp material for cleanup
                    self.temp_materials[temp_mat_name] = temp_mat
                else:
                    temp_materials.append(None)
            
            # Create temporary mesh copy
            temp_mesh_name = f"TEMP_{obj.name}_mesh"
            temp_mesh = obj.data.copy()
            temp_mesh.name = temp_mesh_name
            
            # Assign temporary materials to temporary mesh
            temp_mesh.materials.clear()
            for temp_mat in temp_materials:
                temp_mesh.materials.append(temp_mat)
            
            # Store override information
            self.overrides[obj.name] = {
                'original_mesh': obj.data,
                'original_materials': original_materials,
                'temp_mesh': temp_mesh,
                'temp_materials': temp_materials,
                'object': obj
            }
            
            # Switch object to use temporary mesh
            obj.data = temp_mesh
            
            print(f"Created material override for linked object: {obj.name}")
            return True
            
        except Exception as e:
            print(f"Error creating material override for {obj.name}: {e}")
            return False
    
    def restore_override(self, obj):
        """
        Restore original materials for an object.
        
        Args:
            obj: Blender object to restore
            
        Returns:
            True if restore was successful
        """
        if obj.name not in self.overrides:
            return True  # No override to restore
        
        try:
            override_data = self.overrides[obj.name]
            
            # Restore original mesh
            obj.data = override_data['original_mesh']
            
            # Clean up temporary mesh
            temp_mesh = override_data['temp_mesh']
            if temp_mesh:
                bpy.data.meshes.remove(temp_mesh)
            
            # Clean up temporary materials
            for temp_mat in override_data['temp_materials']:
                if temp_mat and temp_mat.name in self.temp_materials:
                    bpy.data.materials.remove(temp_mat)
                    del self.temp_materials[temp_mat.name]
            
            # Remove override record
            del self.overrides[obj.name]
            
            print(f"Restored original materials for: {obj.name}")
            return True
            
        except Exception as e:
            print(f"Error restoring materials for {obj.name}: {e}")
            return False
    
    def clear_all_overrides(self):
        """Clear all active material overrides."""
        objects_to_restore = list(self.overrides.keys())
        
        for obj_name in objects_to_restore:
            obj = bpy.data.objects.get(obj_name)
            if obj:
                self.restore_override(obj)
        
        # Clean up any remaining temporary materials
        temp_mat_names = list(self.temp_materials.keys())
        for temp_mat_name in temp_mat_names:
            temp_mat = self.temp_materials[temp_mat_name]
            if temp_mat:
                try:
                    bpy.data.materials.remove(temp_mat)
                except:
                    pass
        
        self.temp_materials.clear()
        self.overrides.clear()
        
        print("Cleared all material overrides")
    
    def get_override_count(self):
        """Get the number of active overrides."""
        return len(self.overrides)
    
    def get_overridden_objects(self):
        """Get list of objects with active overrides."""
        return list(self.overrides.keys())
    
    def is_object_overridden(self, obj):
        """Check if an object has an active override."""
        return obj.name in self.overrides
    
    def cleanup_orphaned_overrides(self):
        """Clean up overrides for objects that no longer exist."""
        orphaned_objects = []
        
        for obj_name in self.overrides.keys():
            if obj_name not in bpy.data.objects:
                orphaned_objects.append(obj_name)
        
        for obj_name in orphaned_objects:
            try:
                override_data = self.overrides[obj_name]
                
                # Clean up temporary mesh
                temp_mesh = override_data['temp_mesh']
                if temp_mesh:
                    bpy.data.meshes.remove(temp_mesh)
                
                # Clean up temporary materials
                for temp_mat in override_data['temp_materials']:
                    if temp_mat and temp_mat.name in self.temp_materials:
                        bpy.data.materials.remove(temp_mat)
                        del self.temp_materials[temp_mat.name]
                
                del self.overrides[obj_name]
                
            except Exception as e:
                print(f"Error cleaning up orphaned override for {obj_name}: {e}")
        
        if orphaned_objects:
            print(f"Cleaned up {len(orphaned_objects)} orphaned overrides")


# Global manager instance
_override_manager = None


def get_override_manager():
    """Get the global material override manager instance."""
    global _override_manager
    if _override_manager is None:
        _override_manager = MaterialOverrideManager()
    return _override_manager


def create_temporary_override(obj):
    """
    Create a temporary material override for an object.
    
    Args:
        obj: Blender object
        
    Returns:
        True if successful
    """
    manager = get_override_manager()
    return manager.create_override(obj)


def restore_original_materials(obj):
    """
    Restore original materials for an object.
    
    Args:
        obj: Blender object
        
    Returns:
        True if successful
    """
    manager = get_override_manager()
    return manager.restore_override(obj)


def clear_all_material_overrides():
    """Clear all active material overrides."""
    manager = get_override_manager()
    manager.clear_all_overrides()


def get_override_info():
    """
    Get information about current overrides.
    
    Returns:
        Dictionary with override statistics
    """
    manager = get_override_manager()
    return {
        'count': manager.get_override_count(),
        'objects': manager.get_overridden_objects()
    }


# Cleanup handlers
@bpy.app.handlers.persistent
def cleanup_on_file_load(dummy):
    """Clean up overrides when a new file is loaded."""
    manager = get_override_manager()
    manager.clear_all_overrides()


@bpy.app.handlers.persistent
def cleanup_orphaned_on_save(dummy):
    """Clean up orphaned overrides when saving."""
    manager = get_override_manager()
    manager.cleanup_orphaned_overrides()


def register_material_override():
    """Register material override handlers."""
    # Add handlers
    if cleanup_on_file_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(cleanup_on_file_load)
    
    if cleanup_orphaned_on_save not in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.append(cleanup_orphaned_on_save)


def unregister_material_override():
    """Unregister material override handlers and clean up."""
    # Clean up all overrides
    clear_all_material_overrides()
    
    # Remove handlers
    if cleanup_on_file_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(cleanup_on_file_load)
    
    if cleanup_orphaned_on_save in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(cleanup_orphaned_on_save)


# Utility functions for debugging
def print_override_status():
    """Print current override status to console."""
    manager = get_override_manager()
    print(f"\n=== MATERIAL OVERRIDE STATUS ===")
    print(f"Active overrides: {manager.get_override_count()}")
    print(f"Temporary materials: {len(manager.temp_materials)}")
    
    if manager.overrides:
        print("Overridden objects:")
        for obj_name in manager.overrides.keys():
            print(f"  - {obj_name}")
    
    print("================================\n")


def validate_override_integrity():
    """Validate that all overrides are in a consistent state."""
    manager = get_override_manager()
    issues = []
    
    for obj_name, override_data in manager.overrides.items():
        obj = bpy.data.objects.get(obj_name)
        
        if not obj:
            issues.append(f"Object {obj_name} no longer exists")
            continue
        
        if not obj.library:
            issues.append(f"Object {obj_name} is no longer linked")
        
        temp_mesh = override_data.get('temp_mesh')
        if not temp_mesh:
            issues.append(f"Missing temporary mesh for {obj_name}")
        
        for temp_mat in override_data.get('temp_materials', []):
            if temp_mat and temp_mat.name not in bpy.data.materials:
                issues.append(f"Missing temporary material for {obj_name}")
    
    if issues:
        print("Material override integrity issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("All material overrides are in good state")
    
    return len(issues) == 0
