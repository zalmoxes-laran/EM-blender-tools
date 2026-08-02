import bpy # type: ignore
from bpy_extras.io_utils import ImportHelper, ExportHelper # type: ignore
import xml.etree.ElementTree as ET

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

_G = "{%s}" % _GRAPHML_NS
_Y = "{%s}" % _YWORKS_NS

# ── C1: typing the icon nodes of a pre-1.4 graph ────────────────────────────
#
# Old EM graphs draw extractors, combiners and continuity nodes as `y:SVGNode`
# — an icon, no shape, all of them filled with yEd's default `#CCCCFF`. The
# importer recognises them ONLY by the label convention (`D.` = extractor,
# `C.` = combiner). An author who named an extractor after the unit it reads
# from — `SF04.2`, `USR2170.1` — drew a perfectly unambiguous extractor icon
# and still got an untyped node, along with every edge touching it.
#
# The type IS in the file: it is the SVG resource the node points at. What that
# resource MEANS is learned from the file's own usage — in a graph where 102
# nodes sharing one icon are all called `D.something`, that icon is the
# extractor icon, and the 18 stragglers sharing it are extractors too. This is
# reading the drawing, not guessing from names: the individual label is exactly
# what we refuse to trust.
#
# yEd numbers `y:Resource` by serialisation order, so a refid means nothing
# across files and the mapping is rebuilt for every conversion.
#
# The verdict is written as the explicit `_s3d_node_type:<Class>` marker in the
# node's description — the channel s3Dgraphy already uses for round-tripping,
# which takes precedence over every shape/label heuristic and is stripped from
# the description before it reaches any UI.

_S3D_NODE_TYPE_MARKER = "_s3d_node_type:"

#: Label prefix → node class, mirroring the importer's own convention
#: (`EM_extract_extractor_node` / `EM_extract_combiner_node` in
#: s3Dgraphy/importer/import_graphml.py). Longest prefix first when matching.
_LABEL_PREFIX_TO_CLASS = {
    "D.": "ExtractorNode",
    "C.": "CombinerNode",
}

#: A resource whose `sodipodi:docname` names it outright needs no vote.
_DOCNAME_TO_CLASS = {
    "continuity.svg": "ContinuityNode",
}

#: A refid is only assigned a meaning when its labelled users agree
#: overwhelmingly AND there are enough of them to be a convention rather than a
#: coincidence. Below either bar the resource stays unknown and its nodes are
#: left untyped — which is the correct outcome: the author is told, nothing is
#: invented.
_MIN_VOTES = 3
_MIN_AGREEMENT = 0.9


def _svg_nodes(root):
    """Yield ``(node_element, svg_element, refid, label)`` for every SVGNode."""
    for node in root.iter(f"{_G}node"):
        svg = node.find(f".//{_Y}SVGNode")
        if svg is None:
            continue
        content = svg.find(f".//{_Y}SVGContent")
        refid = content.attrib.get("refid") if content is not None else None
        if not refid:
            continue
        label_elem = svg.find(f".//{_Y}NodeLabel")
        label = (label_elem.text or "").strip() if label_elem is not None else ""
        yield node, svg, refid, label


def _class_for_label(label):
    """The node class the label convention claims, or None. Longest prefix
    first so a future ``D.x``/``Dx.`` pair cannot shadow each other."""
    for prefix in sorted(_LABEL_PREFIX_TO_CLASS, key=len, reverse=True):
        if label.startswith(prefix):
            return _LABEL_PREFIX_TO_CLASS[prefix]
    return None


def learn_svg_resource_classes(root):
    """Build ``{refid: node class}`` for this document.

    Two independent routes, strongest first:

    1. the resource names itself (``sodipodi:docname="continuity.svg"``);
    2. the labelled nodes using it agree on a convention, by a wide margin and
       in sufficient number.

    A refid that satisfies neither is simply absent from the result.
    """
    resources = {}
    for res in root.iter(f"{_Y}Resource"):
        rid = res.attrib.get("id")
        if rid:
            resources[rid] = res.text or ""

    learned = {}
    for rid, body in resources.items():
        for docname, cls in _DOCNAME_TO_CLASS.items():
            if f'docname="{docname}"' in body:
                learned[rid] = cls
                break

    votes = {}
    for _node, _svg, refid, label in _svg_nodes(root):
        cls = _class_for_label(label)
        if cls:
            votes.setdefault(refid, []).append(cls)

    for refid, cast in votes.items():
        if refid in learned:
            continue  # the resource named itself; a vote cannot override that
        if len(cast) < _MIN_VOTES:
            continue
        winner = max(set(cast), key=cast.count)
        if cast.count(winner) / len(cast) >= _MIN_AGREEMENT:
            learned[refid] = winner
    return learned


def _description_element(root, node):
    """The node's ``description`` data element, created if absent.

    The key id is read from the document's own ``<key>`` declarations — yEd
    files number them differently (``d5`` here, ``d4`` there) and hardcoding
    one would silently write into the wrong field.
    """
    key_id = None
    for key in root.findall(f"{_G}key"):
        if key.attrib.get("for") == "node" and \
                key.attrib.get("attr.name") == "description":
            key_id = key.attrib.get("id")
            break
    if key_id is None:
        return None
    for data in node.findall(f"{_G}data"):
        if data.attrib.get("key") == key_id:
            return data
    data = ET.SubElement(node, f"{_G}data", {"key": key_id})
    return data


def annotate_icon_node_types(root):
    """Write ``_s3d_node_type:<Class>`` on every SVGNode the label convention
    misses but the icon identifies.

    Returns ``(annotated, skipped_unknown_resource)``. Idempotent: a node that
    already carries a marker is left alone, so converting twice is a no-op.

    Nodes whose label ALREADY matches the convention are not touched — they
    import correctly today, and rewriting 150 descriptions to restate what the
    label already says would only make the file noisier in yEd.
    """
    learned = learn_svg_resource_classes(root)
    annotated = 0
    skipped = 0
    for node, _svg, refid, label in _svg_nodes(root):
        if _class_for_label(label):
            continue  # already recognisable — leave the description alone
        cls = learned.get(refid)
        if cls is None:
            skipped += 1
            continue
        data = _description_element(root, node)
        if data is None:
            skipped += 1
            continue
        existing = data.text or ""
        if _S3D_NODE_TYPE_MARKER in existing:
            continue  # already annotated
        marker = f"{_S3D_NODE_TYPE_MARKER}{cls}"
        data.text = f"{existing.strip()} {marker}".strip() if existing.strip() else marker
        annotated += 1
    return annotated, skipped


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