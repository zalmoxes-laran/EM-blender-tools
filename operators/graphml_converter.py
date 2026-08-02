import bpy # type: ignore
from bpy_extras.io_utils import ImportHelper, ExportHelper # type: ignore
import xml.etree.ElementTree as ET

from .graphml_icon_types import annotate_icon_node_types

# yEd writes GraphML with the graphml namespace as the DEFAULT one and yWorks
# under the `y` prefix. ElementTree does not remember prefixes it was not told
# about: left to itself it re-serialises every element as `ns0:graphml`,
# `ns2:ShapeNode`, … The document stays valid XML and s3Dgraphy still reads it,
# but yEd is far less forgiving, and the file stops being diffable against the
# original. Registering the two prefixes up-front keeps the output shaped like
# the input — the converter should change borders, not the whole serialisation.
_GRAPHML_NS = "http://graphml.graphdrawing.org/xmlns"
_YWORKS_NS = "http://www.yworks.com/xml/graphml"
ET.register_namespace("", _GRAPHML_NS)
ET.register_namespace("y", _YWORKS_NS)


class GRAPHML_OT_convert_borders(bpy.types.Operator, ImportHelper):
    """Convert GraphML file modifying node borders based on shape and background"""
    bl_idname = "graphml.convert_borders"
    bl_label = "Convert GraphML Borders"
    bl_description = "Convert a GraphML file modifying node borders based on shape and background color"
    
    filename_ext = ".graphml"
    filter_glob: bpy.props.StringProperty(
        default="*.graphml",
        options={'HIDDEN'},
        maxlen=255,
    ) # type: ignore

    def modify_node_borders(self, xml_content):
        tree = ET.ElementTree(ET.fromstring(xml_content))
        root = tree.getroot()
        
        ns = {'y': 'http://www.yworks.com/xml/graphml'}
        
        # Define shapes to modify
        target_shapes = {'rectangle', 'hexagon', 'ellipse', 'octagon', 'parallelogram'}
        
        # Define color mapping based on shape type
        color_mapping = {
            'rectangle': '#9B3333',
            'hexagon': '#31792D', 
            'ellipse': '#31792D',
            'parallelogram': '#248FE7',
        }

        # Find ShapeNode elements directly
        for shape_node in root.findall('.//y:ShapeNode', ns):
            # Get shape type
            shape_elem = shape_node.find('y:Shape', ns)
            if shape_elem is None:
                continue
                
            shape_type = shape_elem.get('type')
            if shape_type not in target_shapes:
                continue
            
            # Get Fill element to check background color
            fill_elem = shape_node.find('y:Fill', ns)
            is_black_bg = False
            if fill_elem is not None:
                bg_color = fill_elem.get('color', '#FFFFFF')
                is_black_bg = (bg_color == '#000000')
            
            # Get BorderStyle element
            border_style = shape_node.find('y:BorderStyle', ns)
            if border_style is None:
                continue

            # Set border width to 4.0 for target nodes
            border_style.set('width', '4.0')
            
            # Handle octagon nodes specially based on background
            if shape_type == 'octagon':
                if is_black_bg:
                    border_style.set('color', '#B19F61')  # VSF color
                else:
                    border_style.set('color', '#D8BD30')  # SF color
            # Handle other target shapes
            elif shape_type in color_mapping:
                border_style.set('color', color_mapping[shape_type])

        # C1 — the icon nodes the shape pass cannot reach. Records how many
        # were typed so execute() can report it.
        self._annotated, self._skipped = annotate_icon_node_types(root)

        return ET.tostring(root, encoding='unicode', xml_declaration=True)

    def execute(self, context):
        try:
            # Read input file
            with open(self.filepath, 'r', encoding='utf-8') as f:
                input_content = f.read()

            self._annotated = self._skipped = 0

            # Process content
            modified_content = self.modify_node_borders(input_content)

            # Save to output file
            output_filepath = self.filepath.replace('.graphml', '_converted.graphml')
            with open(output_filepath, 'w', encoding='utf-8') as f:
                f.write(modified_content)

            msg = f"Converted GraphML saved as: {output_filepath}"
            if self._annotated:
                msg += (f" — typed {self._annotated} icon node(s) from their "
                        f"SVG resource")
            if self._skipped:
                # Never let a partial result read as a complete one.
                msg += (f"; {self._skipped} icon node(s) left untyped (their "
                        f"icon is used too inconsistently to identify) — "
                        f"classify them in yEd")
            self.report({'INFO'}, msg)
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error converting file: {str(e)}")
            return {'CANCELLED'}

def register():
    bpy.utils.register_class(GRAPHML_OT_convert_borders)

def unregister():
    bpy.utils.unregister_class(GRAPHML_OT_convert_borders)

if __name__ == "__main__":
    register()