import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper
import xml.etree.ElementTree as ET

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
    )

    def modify_node_borders(self, xml_content):
        tree = ET.ElementTree(ET.fromstring(xml_content))
        root = tree.getroot()
        
        ns = {'y': 'http://www.yworks.com/xml/graphml'}
        
        # Define shapes to modify
        target_shapes = {'rectangle', 'hexagon', 'ellipse', 'octagon'}
        
        # Define color mapping based on shape type
        color_mapping = {
            'rectangle': '#9B3333',
            'hexagon': '#31792D', 
            'ellipse': '#31792D'
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

        return ET.tostring(root, encoding='unicode', xml_declaration=True)

    def execute(self, context):
        try:
            # Read input file
            with open(self.filepath, 'r', encoding='utf-8') as f:
                input_content = f.read()
            
            # Process content
            modified_content = self.modify_node_borders(input_content)
            
            # Save to output file
            output_filepath = self.filepath.replace('.graphml', '_converted.graphml')
            with open(output_filepath, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            
            self.report({'INFO'}, f"Successfully converted GraphML file. Saved as: {output_filepath}")
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