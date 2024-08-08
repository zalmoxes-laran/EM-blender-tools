# 3dgraphy/node.py

class Node:
    def __init__(self, node_id, name, shape="", y_pos=0.0, fill_color="", border_style="", description=""):
        self.node_id = node_id
        self.name = name
        # Parametri opzionali per supportare nodi con informazioni diverse
        self.shape = shape
        self.y_pos = y_pos
        self.fill_color = fill_color
        self.border_style = border_style
        self.description = description
        self.attributes = {}
        self.epoch = None  # Aggiungi questa proprietà per l'epoca

    def add_attribute(self, key, value):
        self.attributes[key] = value


# StratigraphicNode Class
class StratigraphicNode(Node):
    STRATIGRAPHIC_TYPES = {
        "US": {
            "symbol": "white rectangle",
            "label": "US (or US)",
            "description": "Stratigraphic Unit (SU) or negative stratigraphic unit."
        },
        "USVs": {
            "symbol": "black parallelogram",
            "label": "USV/s",
            "description": "Structural Virtual Stratigraphic Unit (USV/s)."
        },
        "serSU": {
            "symbol": "white ellipse",
            "label": "US series",
            "description": "Series of Stratigraphic Units (SU)."
        },
        "serUSVn": {
            "symbol": "black ellipse green border",
            "label": "USVn series",
            "description": "Series of non-structural Virtual Stratigraphic Units."
        },
        "serUSVs": {
            "symbol": "black ellipse blue border",
            "label": "USVs series",
            "description": "Series of Structural Virtual Stratigraphic Units."
        },
        "USVn": {
            "symbol": "black hexagon",
            "label": "USV/n",
            "description": "Non-structural Virtual Stratigraphic Unit (USV/n)."
        },
        "SF": {
            "symbol": "white octagon",
            "label": "Special Find",
            "description": "Not in situ element that needs repositioning."
        },
        "VSF": {
            "symbol": "black octagon",
            "label": "Virtual Special Find",
            "description": "Hypothetical reconstruction of a fragmented Special Find."
        },
        "USD": {
            "symbol": "white round rectangle",
            "label": "USD",
            "description": "Documentary Stratigraphic Unit."
        },
        "TSU": {
            "symbol": "dotted white rectangle",
            "label": "TSU",
            "description": "Transformation Unit."
        },
        "BR": {
            "symbol": "black rhombus",
            "label": "continuity node",
            "description": "End of life of a US/USV."
        },
        "unknow": {
            "symbol": "question mark",
            "label": "nodo sconosciuto",
            "description": "nodo di fallback"
        }
    }


    def __init__(self, node_id, name, stratigraphic_type, description="", shape="", y_pos=0.0, fill_color="", border_style=""):
        super().__init__(node_id, name, shape, y_pos, fill_color, border_style, description)
        self.stratigraphic_type = stratigraphic_type
        self.validate_stratigraphic_type()

    def validate_stratigraphic_type(self):
        if self.stratigraphic_type not in self.STRATIGRAPHIC_TYPES:
            raise ValueError(f"Invalid stratigraphic type: {self.stratigraphic_type}")

    def get_stratigraphic_info(self):
        return self.STRATIGRAPHIC_TYPES.get(self.stratigraphic_type)

# ParadataNode Class - Subclass of Node
class ParadataNode(Node):
    def __init__(self, node_id, name, description="", paradata_type="", url=None):
        super().__init__(node_id, name, description)
        self.paradata_type = paradata_type  # Specific type of paradata
        self.url = url  # Aggiungi l'attributo url

# DocumentNode Class - Subclass of ParadataNode
class DocumentNode(ParadataNode):
    def __init__(self, node_id, name, description="", url=None):
        super().__init__(node_id, name, description, paradata_type="document", url=url)

# CombinerNode Class - Subclass of ParadataNode
class CombinerNode(ParadataNode):
    def __init__(self, node_id, name, description="", sources=[], url=None):
        super().__init__(node_id, name, description, paradata_type="combiner", url=url)
        self.sources = sources

# ExtractorNode Class - Subclass of ParadataNode
class ExtractorNode(ParadataNode):
    def __init__(self, node_id, name, description="", source=None, url=None):
        super().__init__(node_id, name, description, paradata_type="extractor", url=url)
        self.source = source

# PropertyNode Class - Subclass of ParadataNode
class PropertyNode(ParadataNode):
    def __init__(self, node_id, name, description="", value=None, url=None):
        super().__init__(node_id, name, description, paradata_type="property", url=url)
        self.value = value

# Epoch Node
class EpochNode(Node):
    def __init__(self, node_id, name, start_time, end_time, color="#FFFFFF", description=""):
        super().__init__(node_id, name, description)
        self.start_time = start_time
        self.end_time = end_time
        self.color = color

# Activity Node
class ActivityNode(Node):
    def __init__(self, node_id, name, activity_type, duration, description=""):
        super().__init__(node_id, name, description)
        self.activity_type = activity_type
        self.duration = duration

