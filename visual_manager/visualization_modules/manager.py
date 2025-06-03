"""
Visualization Manager - Central coordination system for all visualization modules
This module provides event-driven coordination, state management, and performance optimization.
"""

import bpy
import time
from collections import defaultdict
from typing import Dict, List, Set, Any, Optional, Callable

from .utils import get_em_objects, backup_material_state

class VisualizationState:
    """Represents the current state of all visualizations"""
    
    def __init__(self):
        self.active_modules: Dict[str, Dict] = {}
        self.material_snapshots: Dict[str, Any] = {}
        self.last_update: float = 0.0
        self.performance_mode: bool = False
        self.update_pending: bool = False

class VisualizationManager:
    """Central manager for all visualization modules"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.state = VisualizationState()
        self.event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.module_registry: Dict[str, Dict] = {}
        self.performance_settings: Dict[str, Any] = {
            'max_updates_per_second': 30,
            'batch_update_delay': 0.1,
            'auto_performance_mode_threshold': 1000
        }
        self.pending_updates: Set[str] = set()
        self.update_timer_handle = None
        self._initialized = True
        
        print("VisualizationManager initialized")
    
    def register_module(self, module_id: str, module_info: Dict[str, Any]):
        """
        Register a visualization module with the manager.
        
        Args:
            module_id: Unique identifier for the module
            module_info: Module information including callbacks and settings
        """
        self.module_registry[module_id] = {
            'info': module_info,
            'active': False,
            'last_applied': 0.0,
            'settings': module_info.get('default_settings', {}),
            'apply_callback': module_info.get('apply_callback'),
            'clear_callback': module_info.get('clear_callback'),
            'update_callback': module_info.get('update_callback')
        }
        
        print(f"Registered visualization module: {module_id}")
    
    def subscribe_to_event(self, event_type: str, callback: Callable):
        """
        Subscribe to visualization events.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when event occurs
        """
        self.event_handlers[event_type].append(callback)
    
    def emit_event(self, event_type: str, data: Any = None):
        """
        Emit an event to all subscribers.
        
        Args:
            event_type: Type of event to emit
            data: Optional data to pass to handlers
        """
        for handler in self.event_handlers[event_type]:
            try:
                handler(data)
            except Exception as e:
                print(f"Error in event handler for {event_type}: {e}")
    
    def activate_module(self, module_id: str, settings: Optional[Dict] = None):
        """
        Activate a visualization module.
        
        Args:
            module_id: ID of module to activate
            settings: Optional settings to override defaults
        """
        if module_id not in self.module_registry:
            print(f"Warning: Module {module_id} not registered")
            return False
        
        module = self.module_registry[module_id]
        
        # Update settings if provided
        if settings:
            module['settings'].update(settings)
        
        # Create material snapshots before applying
        self._create_material_snapshots()
        
        # Mark as active
        module['active'] = True
        self.state.active_modules[module_id] = module['settings'].copy()
        
        # Schedule update
        self.schedule_update(module_id)
        
        # Emit event
        self.emit_event('module_activated', {'module_id': module_id, 'settings': module['settings']})
        
        print(f"Activated module: {module_id}")
        return True
    
    def deactivate_module(self, module_id: str):
        """
        Deactivate a visualization module.
        
        Args:
            module_id: ID of module to deactivate
        """
        if module_id not in self.module_registry:
            return False
        
        module = self.module_registry[module_id]
        
        # Clear module effects
        if module['clear_callback']:
            try:
                module['clear_callback']()
            except Exception as e:
                print(f"Error clearing module {module_id}: {e}")
        
        # Mark as inactive
        module['active'] = False
        if module_id in self.state.active_modules:
            del self.state.active_modules[module_id]
        
        # Remove from pending updates
        self.pending_updates.discard(module_id)
        
        # Emit event
        self.emit_event('module_deactivated', {'module_id': module_id})
        
        print(f"Deactivated module: {module_id}")
        return True
    
    def schedule_update(self, module_id: str):
        """
        Schedule an update for a specific module.
        
        Args:
            module_id: ID of module to update
        """
        self.pending_updates.add(module_id)
        
        # Start timer if not already running
        if self.update_timer_handle is None:
            self.update_timer_handle = bpy.app.timers.register(
                self._execute_pending_updates,
                first_interval=self.performance_settings['batch_update_delay']
            )
    
    def _execute_pending_updates(self):
        """Execute all pending module updates."""
        if not self.pending_updates:
            self.update_timer_handle = None
            return None  # Stop timer
        
        current_time = time.time()
        min_interval = 1.0 / self.performance_settings['max_updates_per_second']
        
        # Check if enough time has passed since last update
        if current_time - self.state.last_update < min_interval:
            return self.performance_settings['batch_update_delay']  # Try again later
        
        # Get target objects
        target_objects = get_em_objects()
        
        # Check for performance mode
        if len(target_objects) > self.performance_settings['auto_performance_mode_threshold']:
            self._enter_performance_mode()
        
        # Execute updates for pending modules
        modules_to_update = list(self.pending_updates)
        self.pending_updates.clear()
        
        for module_id in modules_to_update:
            if module_id in self.module_registry:
                module = self.module_registry[module_id]
                if module['active'] and module['apply_callback']:
                    try:
                        module['apply_callback'](target_objects, module['settings'])
                        module['last_applied'] = current_time
                    except Exception as e:
                        print(f"Error updating module {module_id}: {e}")
        
        self.state.last_update = current_time
        
        # Emit update complete event
        self.emit_event('update_complete', {'updated_modules': modules_to_update})
        
        # Stop timer
        self.update_timer_handle = None
        return None
    
    def update_all_active_modules(self):
        """Update all currently active modules."""
        for module_id in list(self.state.active_modules.keys()):
            self.schedule_update(module_id)
    
    def clear_all_modules(self):
        """Clear all active visualization modules."""
        active_modules = list(self.state.active_modules.keys())
        
        for module_id in active_modules:
            self.deactivate_module(module_id)
        
        # Restore material snapshots
        self._restore_material_snapshots()
        
        # Exit performance mode
        if self.state.performance_mode:
            self._exit_performance_mode()
        
        print(f"Cleared {len(active_modules)} active modules")
    
    def get_active_modules(self) -> List[str]:
        """Get list of currently active module IDs."""
        return list(self.state.active_modules.keys())
    
    def is_module_active(self, module_id: str) -> bool:
        """Check if a specific module is active."""
        return module_id in self.state.active_modules
    
    def get_module_settings(self, module_id: str) -> Optional[Dict]:
        """Get current settings for a module."""
        if module_id in self.module_registry:
            return self.module_registry[module_id]['settings'].copy()
        return None
    
    def update_module_settings(self, module_id: str, settings: Dict):
        """
        Update settings for a module and trigger refresh.
        
        Args:
            module_id: ID of module to update
            settings: New settings to apply
        """
        if module_id not in self.module_registry:
            return False
        
        module = self.module_registry[module_id]
        module['settings'].update(settings)
        
        if module['active']:
            self.state.active_modules[module_id] = module['settings'].copy()
            self.schedule_update(module_id)
        
        self.emit_event('module_settings_updated', {'module_id': module_id, 'settings': settings})
        return True
    
    def _create_material_snapshots(self):
        """Create snapshots of all materials before modifications."""
        if self.state.material_snapshots:
            return  # Already have snapshots
        
        for material in bpy.data.materials:
            if material.use_nodes:
                self.state.material_snapshots[material.name] = backup_material_state(material)
    
    def _restore_material_snapshots(self):
        """Restore materials from snapshots."""
        # This would be implemented with the backup/restore system
        # For now, we'll use the existing clean_all_materials function
        from .utils import clean_all_materials
        clean_all_materials()
        
        # Clear snapshots
        self.state.material_snapshots.clear()
    
    def _enter_performance_mode(self):
        """Enter performance mode for large scenes."""
        if self.state.performance_mode:
            return
        
        self.state.performance_mode = True
        
        # Reduce update frequency
        self.performance_settings['max_updates_per_second'] = 10
        self.performance_settings['batch_update_delay'] = 0.2
        
        # Emit event so UI can show performance warning
        self.emit_event('performance_mode_entered', {})
        
        print("Entered performance mode due to large scene")
    
    def _exit_performance_mode(self):
        """Exit performance mode."""
        if not self.state.performance_mode:
            return
        
        self.state.performance_mode = False
        
        # Restore normal update frequency
        self.performance_settings['max_updates_per_second'] = 30
        self.performance_settings['batch_update_delay'] = 0.1
        
        self.emit_event('performance_mode_exited', {})
        
        print("Exited performance mode")
    
    def get_performance_info(self) -> Dict[str, Any]:
        """Get current performance information."""
        target_objects = get_em_objects()
        
        return {
            'performance_mode': self.state.performance_mode,
            'active_modules': len(self.state.active_modules),
            'target_objects': len(target_objects),
            'last_update': self.state.last_update,
            'pending_updates': len(self.pending_updates),
            'material_snapshots': len(self.state.material_snapshots)
        }

# Global instance
visualization_manager = VisualizationManager()

# Selection change handler for automatic updates
def handle_selection_change(scene):
    """Handler for selection changes."""
    if hasattr(scene, 'visualization_auto_update') and scene.visualization_auto_update:
        visualization_manager.update_all_active_modules()

# Convenience functions for integration
def get_manager() -> VisualizationManager:
    """Get the global visualization manager instance."""
    return visualization_manager

def register_module(module_id: str, apply_func: Callable, clear_func: Callable, 
                   default_settings: Dict = None):
    """
    Convenience function to register a module.
    
    Args:
        module_id: Unique module identifier
        apply_func: Function to apply module effects
        clear_func: Function to clear module effects  
        default_settings: Default settings for the module
    """
    module_info = {
        'apply_callback': apply_func,
        'clear_callback': clear_func,
        'default_settings': default_settings or {}
    }
    
    visualization_manager.register_module(module_id, module_info)

def activate_module(module_id: str, settings: Dict = None) -> bool:
    """Convenience function to activate a module."""
    return visualization_manager.activate_module(module_id, settings)

def deactivate_module(module_id: str) -> bool:
    """Convenience function to deactivate a module."""
    return visualization_manager.deactivate_module(module_id)

def clear_all_visualizations():
    """Convenience function to clear all visualizations."""
    visualization_manager.clear_all_modules()

def update_all_visualizations():
    """Convenience function to update all active visualizations."""
    visualization_manager.update_all_active_modules()
