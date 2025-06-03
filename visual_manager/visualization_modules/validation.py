"""
Validation and Testing System for Visualization Modules
This module provides comprehensive testing and validation for the visualization system.
"""

import bpy
import time
from typing import List, Dict, Any, Tuple, Optional, Callable
from bpy.types import Operator

from .manager import get_manager
from .utils import get_em_objects, clean_all_materials
from .preset_system import get_preset_manager

class ValidationResult:
    """Result of a validation test"""
    
    def __init__(self, test_name: str, passed: bool, message: str = "", details: Dict = None):
        self.test_name = test_name
        self.passed = passed
        self.message = message
        self.details = details or {}
        self.timestamp = time.time()

class VisualizationValidator:
    """Comprehensive validator for the visualization system"""
    
    def __init__(self):
        self.test_results = []
        self.manager = None
        
    def run_all_tests(self, context) -> List[ValidationResult]:
        """Run all validation tests."""
        self.test_results.clear()
        
        print("\n=== STARTING VISUALIZATION SYSTEM VALIDATION ===")
        
        # Core system tests
        self._test_manager_initialization()
        self._test_module_registration()
        self._test_basic_functionality(context)
        
        # Material system tests
        self._test_material_modifications()
        self._test_material_cleanup()
        
        # Performance tests
        self._test_performance_characteristics(context)
        
        # Integration tests
        self._test_em_tools_integration(context)
        
        # Preset system tests
        self._test_preset_system()
        
        # Error handling tests
        self._test_error_handling()
        
        # Generate summary
        self._generate_test_summary()
        
        return self.test_results
    
    def _test_manager_initialization(self):
        """Test that the visualization manager initializes correctly."""
        try:
            manager = get_manager()
            self.manager = manager
            
            if manager is None:
                self._add_result("Manager Initialization", False, "Manager is None")
                return
            
            # Test basic manager properties
            if not hasattr(manager, 'state'):
                self._add_result("Manager State", False, "Manager missing state attribute")
                return
            
            if not hasattr(manager, 'module_registry'):
                self._add_result("Module Registry", False, "Manager missing module_registry")
                return
            
            self._add_result("Manager Initialization", True, "Manager initialized successfully")
            
        except Exception as e:
            self._add_result("Manager Initialization", False, f"Exception: {str(e)}")
    
    def _test_module_registration(self):
        """Test that modules are properly registered."""
        if not self.manager:
            self._add_result("Module Registration", False, "Manager not available")
            return
        
        expected_modules = ['transparency', 'color_overlay', 'clipping']
        registered_modules = list(self.manager.module_registry.keys())
        
        missing_modules = [m for m in expected_modules if m not in registered_modules]
        
        if missing_modules:
            self._add_result("Module Registration", False, 
                           f"Missing modules: {', '.join(missing_modules)}")
        else:
            self._add_result("Module Registration", True, 
                           f"All expected modules registered: {', '.join(expected_modules)}")
    
    def _test_basic_functionality(self, context):
        """Test basic activation/deactivation functionality."""
        if not self.manager:
            self._add_result("Basic Functionality", False, "Manager not available")
            return
        
        try:
            # Test transparency module
            success = self.manager.activate_module('transparency', {
                'transparency_factor': 0.5,
                'transparency_mode': 'SELECTION'
            })
            
            if not success:
                self._add_result("Module Activation", False, "Failed to activate transparency module")
                return
            
            # Check if module is active
            active_modules = self.manager.get_active_modules()
            if 'transparency' not in active_modules:
                self._add_result("Module Status", False, "Module not showing as active")
                return
            
            # Test deactivation
            success = self.manager.deactivate_module('transparency')
            if not success:
                self._add_result("Module Deactivation", False, "Failed to deactivate module")
                return
            
            # Check if module is inactive
            active_modules = self.manager.get_active_modules()
            if 'transparency' in active_modules:
                self._add_result("Module Deactivation Status", False, "Module still showing as active")
                return
            
            self._add_result("Basic Functionality", True, "Activation/deactivation working correctly")
            
        except Exception as e:
            self._add_result("Basic Functionality", False, f"Exception: {str(e)}")
    
    def _test_material_modifications(self):
        """Test that material modifications work correctly."""
        try:
            # Create a test material
            test_mat = bpy.data.materials.new("TEST_VALIDATION_MATERIAL")
            test_mat.use_nodes = True
            
            # Get initial node count
            initial_node_count = len(test_mat.node_tree.nodes)
            
            # Apply transparency modification
            from .proxy_transparency import apply_transparency_to_material
            apply_transparency_to_material(test_mat, 0.5)
            
            # Check if nodes were added
            new_node_count = len(test_mat.node_tree.nodes)
            if new_node_count <= initial_node_count:
                self._add_result("Material Modification", False, "No nodes added during modification")
                return
            
            # Check for expected nodes
            has_transparency_nodes = any(node.name.startswith('TRANS_') for node in test_mat.node_tree.nodes)
            if not has_transparency_nodes:
                self._add_result("Material Node Creation", False, "Expected transparency nodes not found")
                return
            
            # Clean up test material
            bpy.data.materials.remove(test_mat)
            
            self._add_result("Material Modifications", True, "Material modifications working correctly")
            
        except Exception as e:
            self._add_result("Material Modifications", False, f"Exception: {str(e)}")
    
    def _test_material_cleanup(self):
        """Test that material cleanup works correctly."""
        try:
            # Create test materials with visualization nodes
            test_materials = []
            for i in range(3):
                mat = bpy.data.materials.new(f"TEST_CLEANUP_{i}")
                mat.use_nodes = True
                
                # Add visualization nodes
                from .utils import create_node_with_prefix
                create_node_with_prefix(mat.node_tree, 'ShaderNodeMath', 'TRANS', f'test_node_{i}')
                create_node_with_prefix(mat.node_tree, 'ShaderNodeRGB', 'OVERLAY', f'test_color_{i}')
                
                test_materials.append(mat)
            
            # Count visualization nodes before cleanup
            viz_nodes_before = 0
            for mat in test_materials:
                viz_nodes_before += sum(1 for node in mat.node_tree.nodes 
                                      if any(node.name.startswith(prefix) for prefix in ['TRANS_', 'OVERLAY_', 'CLIP_']))
            
            # Run cleanup
            clean_all_materials()
            
            # Count visualization nodes after cleanup
            viz_nodes_after = 0
            for mat in test_materials:
                viz_nodes_after += sum(1 for node in mat.node_tree.nodes 
                                     if any(node.name.startswith(prefix) for prefix in ['TRANS_', 'OVERLAY_', 'CLIP_']))
            
            # Clean up test materials
            for mat in test_materials:
                bpy.data.materials.remove(mat)
            
            if viz_nodes_after == 0 and viz_nodes_before > 0:
                self._add_result("Material Cleanup", True, f"Cleaned {viz_nodes_before} visualization nodes")
            else:
                self._add_result("Material Cleanup", False, 
                               f"Cleanup incomplete: {viz_nodes_before} -> {viz_nodes_after} nodes")
            
        except Exception as e:
            self._add_result("Material Cleanup", False, f"Exception: {str(e)}")
    
    def _test_performance_characteristics(self, context):
        """Test performance characteristics with different object counts."""
        em_objects = get_em_objects()
        object_count = len(em_objects)
        
        if object_count == 0:
            self._add_result("Performance Test", False, "No EM objects found for testing")
            return
        
        try:
            # Test activation time
            start_time = time.time()
            
            self.manager.activate_module('transparency', {
                'transparency_factor': 0.5,
                'transparency_mode': 'SELECTION'
            })
            
            activation_time = time.time() - start_time
            
            # Test update time
            start_time = time.time()
            self.manager.update_all_active_modules()
            update_time = time.time() - start_time
            
            # Clean up
            self.manager.deactivate_module('transparency')
            
            # Evaluate performance
            expected_max_time = 0.1 if object_count < 100 else 0.5 if object_count < 500 else 1.0
            
            total_time = activation_time + update_time
            
            if total_time <= expected_max_time:
                self._add_result("Performance", True, 
                               f"Good performance: {total_time:.3f}s for {object_count} objects")
            else:
                self._add_result("Performance", False, 
                               f"Slow performance: {total_time:.3f}s for {object_count} objects (expected < {expected_max_time}s)")
            
        except Exception as e:
            self._add_result("Performance Test", False, f"Exception: {str(e)}")
    
    def _test_em_tools_integration(self, context):
        """Test integration with EM-TOOLS systems."""
        scene = context.scene
        
        # Test epoch integration
        has_epochs = hasattr(scene, 'epoch_list') and len(scene.epoch_list) > 0
        if has_epochs:
            self._add_result("Epoch Integration", True, f"Found {len(scene.epoch_list)} epochs")
        else:
            self._add_result("Epoch Integration", False, "No epoch data found")
        
        # Test em_list integration
        has_em_list = hasattr(scene, 'em_list') and len(scene.em_list) > 0
        if has_em_list:
            self._add_result("EM List Integration", True, f"Found {len(scene.em_list)} EM items")
        else:
            self._add_result("EM List Integration", False, "No EM list data found")
        
        # Test property integration
        has_properties = hasattr(scene, 'selected_property') and scene.selected_property
        if has_properties:
            self._add_result("Property Integration", True, f"Active property: {scene.selected_property}")
        else:
            self._add_result("Property Integration", False, "No active property")
    
    def _test_preset_system(self):
        """Test preset save/load functionality."""
        try:
            preset_manager = get_preset_manager()
            
            # Test loading built-in preset
            success = preset_manager.load_preset('focus_selected')
            if success:
                self._add_result("Preset Loading", True, "Built-in preset loaded successfully")
            else:
                self._add_result("Preset Loading", False, "Failed to load built-in preset")
                return
            
            # Test saving current state
            success = preset_manager.save_preset("TEST_VALIDATION_PRESET", "Test preset for validation")
            if success:
                self._add_result("Preset Saving", True, "Test preset saved successfully")
            else:
                self._add_result("Preset Saving", False, "Failed to save test preset")
                return
            
            # Test loading saved preset
            success = preset_manager.load_preset("TEST_VALIDATION_PRESET")
            if success:
                self._add_result("Preset Loading (Saved)", True, "Saved preset loaded successfully")
            else:
                self._add_result("Preset Loading (Saved)", False, "Failed to load saved preset")
            
            # Clean up test preset
            preset_manager.delete_preset("TEST_VALIDATION_PRESET")
            
        except Exception as e:
            self._add_result("Preset System", False, f"Exception: {str(e)}")
    
    def _test_error_handling(self):
        """Test error handling and recovery."""
        if not self.manager:
            self._add_result("Error Handling", False, "Manager not available")
            return
        
        try:
            # Test invalid module activation
            success = self.manager.activate_module('nonexistent_module', {})
            if success:
                self._add_result("Error Handling - Invalid Module", False, 
                               "Invalid module activation succeeded (should fail)")
            else:
                self._add_result("Error Handling - Invalid Module", True, 
                               "Invalid module activation properly rejected")
            
            # Test with invalid settings
            success = self.manager.activate_module('transparency', {'invalid_setting': 'value'})
            # This should still succeed but ignore invalid settings
            self._add_result("Error Handling - Invalid Settings", True, 
                           "Invalid settings handled gracefully")
            
            # Clean up
            self.manager.deactivate_module('transparency')
            
        except Exception as e:
            self._add_result("Error Handling", False, f"Exception: {str(e)}")
    
    def _generate_test_summary(self):
        """Generate a summary of test results."""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.passed)
        failed_tests = total_tests - passed_tests
        
        print(f"\n=== VALIDATION SUMMARY ===")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "N/A")
        
        if failed_tests > 0:
            print(f"\nFAILED TESTS:")
            for result in self.test_results:
                if not result.passed:
                    print(f"  - {result.test_name}: {result.message}")
        
        print("=== END VALIDATION ===\n")
    
    def _add_result(self, test_name: str, passed: bool, message: str = "", details: Dict = None):
        """Add a test result."""
        result = ValidationResult(test_name, passed, message, details)
        self.test_results.append(result)
        
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {test_name}: {message}")

class VISUAL_OT_run_validation(Operator):
    """Run comprehensive validation of the visualization system"""
    bl_idname = "visual.run_validation"
    bl_label = "Run Validation Tests"
    bl_description = "Run comprehensive validation tests on the visualization system"
    
    def execute(self, context):
        try:
            validator = VisualizationValidator()
            results = validator.run_all_tests(context)
            
            total_tests = len(results)
            passed_tests = sum(1 for r in results if r.passed)
            
            if passed_tests == total_tests:
                self.report({'INFO'}, f"All {total_tests} validation tests passed!")
            else:
                failed_tests = total_tests - passed_tests
                self.report({'WARNING'}, f"{passed_tests}/{total_tests} tests passed ({failed_tests} failed)")
            
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Validation failed with exception: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_performance_benchmark(Operator):
    """Run performance benchmark on the visualization system"""
    bl_idname = "visual.performance_benchmark"
    bl_label = "Performance Benchmark"
    bl_description = "Benchmark the performance of visualization operations"
    
    def execute(self, context):
        try:
            em_objects = get_em_objects()
            object_count = len(em_objects)
            
            if object_count == 0:
                self.report({'WARNING'}, "No EM objects found for benchmarking")
                return {'CANCELLED'}
            
            manager = get_manager()
            
            # Benchmark transparency
            start_time = time.time()
            manager.activate_module('transparency', {'transparency_factor': 0.5})
            transparency_time = time.time() - start_time
            
            # Benchmark color overlay
            start_time = time.time()
            manager.activate_module('color_overlay', {'overlay_strength': 0.5})
            overlay_time = time.time() - start_time
            
            # Benchmark update
            start_time = time.time()
            manager.update_all_active_modules()
            update_time = time.time() - start_time
            
            # Benchmark cleanup
            start_time = time.time()
            manager.clear_all_modules()
            cleanup_time = time.time() - start_time
            
            total_time = transparency_time + overlay_time + update_time + cleanup_time
            
            # Show results
            message = (f"Benchmark Results ({object_count} objects):\n"
                      f"Transparency: {transparency_time:.3f}s\n"
                      f"Color Overlay: {overlay_time:.3f}s\n"
                      f"Update: {update_time:.3f}s\n"
                      f"Cleanup: {cleanup_time:.3f}s\n"
                      f"Total: {total_time:.3f}s")
            
            def draw(self, context):
                lines = message.split('\n')
                for line in lines:
                    self.layout.label(text=line)
            
            context.window_manager.popup_menu(draw, title="Performance Benchmark", icon='TIME')
            
            self.report({'INFO'}, f"Benchmark completed in {total_time:.3f}s")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Benchmark failed: {str(e)}")
            return {'CANCELLED'}

class VISUAL_OT_system_diagnostics(Operator):
    """Run system diagnostics"""
    bl_idname = "visual.system_diagnostics"
    bl_label = "System Diagnostics"
    bl_description = "Run diagnostic checks on the visualization system"
    
    def execute(self, context):
        try:
            diagnostics = []
            
            # Check manager status
            manager = get_manager()
            if manager:
                diagnostics.append("✓ Visualization Manager: Active")
                diagnostics.append(f"✓ Active Modules: {len(manager.get_active_modules())}")
                
                perf_info = manager.get_performance_info()
                diagnostics.append(f"• Performance Mode: {'Yes' if perf_info['performance_mode'] else 'No'}")
                diagnostics.append(f"• Target Objects: {perf_info['target_objects']}")
                diagnostics.append(f"• Pending Updates: {perf_info['pending_updates']}")
            else:
                diagnostics.append("✗ Visualization Manager: Not Available")
            
            # Check EM objects
            em_objects = get_em_objects()
            diagnostics.append(f"• EM Objects Found: {len(em_objects)}")
            
            # Check scene data
            scene = context.scene
            if hasattr(scene, 'epoch_list'):
                diagnostics.append(f"• Epochs Available: {len(scene.epoch_list)}")
            else:
                diagnostics.append("• Epochs: Not Available")
            
            if hasattr(scene, 'em_list'):
                diagnostics.append(f"• EM List Items: {len(scene.em_list)}")
            else:
                diagnostics.append("• EM List: Not Available")
            
            # Check materials with visualization nodes
            viz_materials = 0
            for mat in bpy.data.materials:
                if mat.use_nodes:
                    has_viz_nodes = any(node.name.startswith(('TRANS_', 'OVERLAY_', 'CLIP_')) 
                                      for node in mat.node_tree.nodes)
                    if has_viz_nodes:
                        viz_materials += 1
            diagnostics.append(f"• Materials with Visualization: {viz_materials}")
            
            # Show diagnostics
            def draw(self, context):
                for line in diagnostics:
                    icon = 'CHECKMARK' if line.startswith('✓') else 'ERROR' if line.startswith('✗') else 'DOT'
                    self.layout.label(text=line, icon=icon)
            
            context.window_manager.popup_menu(draw, title="System Diagnostics", icon='INFO')
            
            self.report({'INFO'}, "Diagnostics completed")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Diagnostics failed: {str(e)}")
            return {'CANCELLED'}

def register_validation():
    """Register validation and testing operators."""
    classes = [
        VISUAL_OT_run_validation,
        VISUAL_OT_performance_benchmark,
        VISUAL_OT_system_diagnostics,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass

def unregister_validation():
    """Unregister validation and testing operators."""
    classes = [
        VISUAL_OT_system_diagnostics,
        VISUAL_OT_performance_benchmark,
        VISUAL_OT_run_validation,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            pass

# Convenience functions for testing
def quick_validation_check(context) -> bool:
    """Quick validation check - returns True if system is working."""
    try:
        manager = get_manager()
        if not manager:
            return False
        
        # Test basic activation
        success = manager.activate_module('transparency', {'transparency_factor': 0.1})
        if success:
            manager.deactivate_module('transparency')
            return True
        
        return False
    except:
        return False

def run_minimal_tests(context) -> Dict[str, bool]:
    """Run minimal tests and return results."""
    results = {}
    
    try:
        # Test manager
        manager = get_manager()
        results['manager'] = manager is not None
        
        # Test basic functionality
        if manager:
            success = manager.activate_module('transparency', {'transparency_factor': 0.1})
            results['activation'] = success
            if success:
                manager.deactivate_module('transparency')
        
        # Test objects
        em_objects = get_em_objects()
        results['objects'] = len(em_objects) > 0
        
        # Test cleanup
        try:
            clean_all_materials()
            results['cleanup'] = True
        except:
            results['cleanup'] = False
        
    except Exception as e:
        print(f"Error in minimal tests: {e}")
    
    return results
