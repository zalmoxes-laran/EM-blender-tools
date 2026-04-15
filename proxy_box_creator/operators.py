"""
Operators for the Proxy Box Creator
"""

import bpy
from bpy.types import Operator
from bpy.props import IntProperty


class PROXYBOX_OT_record_point(Operator):
    """Record the current 3D cursor position for this measurement point"""
    bl_idname = "proxybox.record_point"
    bl_label = "Record Point"
    bl_description = "Record the 3D cursor position for this measurement point"
    bl_options = {'REGISTER', 'UNDO'}

    point_index: IntProperty(
        name="Point Index",
        description="Index of the point to record (0-6)",
        min=0,
        max=6,
        default=0
    )  # type: ignore

    def execute(self, context):
        settings = context.scene.em_tools.proxy_box

        # Ensure we have enough points in the collection
        while len(settings.points) <= self.point_index:
            settings.points.add()

        # Get the 3D cursor position
        cursor_location = context.scene.cursor.location

        # Record the position
        point = settings.points[self.point_index]
        point.position = cursor_location
        point.is_recorded = True

        # Point type labels (matching ui.py)
        point_labels = {
            0: "Bottom-Left Front",
            1: "Bottom-Right Front",
            2: "Bottom-Right Back",
            3: "Bottom-Left Back",
            4: "Top-Left Front",
            5: "Top-Right Front",
            6: "Thickness Reference"
        }

        point_label = point_labels.get(self.point_index, f"Point {self.point_index + 1}")

        self.report({'INFO'}, f"Recorded {point_label}: ({cursor_location.x:.3f}, {cursor_location.y:.3f}, {cursor_location.z:.3f})")

        return {'FINISHED'}


class PROXYBOX_OT_clear_point(Operator):
    """Clear the recorded position for this measurement point"""
    bl_idname = "proxybox.clear_point"
    bl_label = "Clear Point"
    bl_description = "Clear the recorded position for this measurement point"
    bl_options = {'REGISTER', 'UNDO'}

    point_index: IntProperty(
        name="Point Index",
        description="Index of the point to clear (0-6)",
        min=0,
        max=6,
        default=0
    )  # type: ignore

    def execute(self, context):
        settings = context.scene.em_tools.proxy_box

        if self.point_index < len(settings.points):
            point = settings.points[self.point_index]
            point.position = (0.0, 0.0, 0.0)
            point.is_recorded = False
            point.source_document = ""
            point.source_document_name = ""
            point.extractor_id = ""

            self.report({'INFO'}, f"Cleared point {self.point_index + 1}")
        else:
            self.report({'WARNING'}, f"Point {self.point_index + 1} does not exist")

        return {'FINISHED'}


class PROXYBOX_OT_clear_all_points(Operator):
    """Clear all recorded measurement points"""
    bl_idname = "proxybox.clear_all_points"
    bl_label = "Clear All Points"
    bl_description = "Clear all recorded measurement points"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.em_tools.proxy_box

        # Clear all points
        cleared_count = 0
        for point in settings.points:
            if point.is_recorded:
                point.position = (0.0, 0.0, 0.0)
                point.is_recorded = False
                point.source_document = ""
                point.source_document_name = ""
                point.extractor_id = ""
                cleared_count += 1

        if cleared_count > 0:
            self.report({'INFO'}, f"Cleared {cleared_count} point(s)")
        else:
            self.report({'INFO'}, "No points to clear")

        return {'FINISHED'}


# List of classes to register
classes = [
    PROXYBOX_OT_record_point,
    PROXYBOX_OT_clear_point,
    PROXYBOX_OT_clear_all_points,
]


def register():
    """Register all operator classes"""
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError as e:
            print(f"[proxy_box] Warning: Could not register {cls.__name__}: {e}")


def unregister():
    """Unregister all operator classes"""
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()
