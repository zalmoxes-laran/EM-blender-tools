# 3dgraphy/node.py

class Node:
    def __init__(self, node_id, name, node_type, description=""):
        self.node_id = node_id
        self.name = name
        self.node_type = node_type
        self.description = description
        self.attributes = {}

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

    def __init__(self, node_id, name, stratigraphic_type, description="", epoch=None):
        super().__init__(node_id, name, node_type=stratigraphic_type, description=description)
        self.epoch = epoch  # Aggiunge la proprietà epoch specifica per i nodi stratigrafici
        self.validate_stratigraphic_type()

    def validate_stratigraphic_type(self):
        if self.node_type not in self.STRATIGRAPHIC_TYPES:
            raise ValueError(f"Invalid stratigraphic type: {self.node_type}")

    def get_stratigraphic_info(self):
        return self.STRATIGRAPHIC_TYPES.get(self.node_type)



# ParadataNode Class - Subclass of Node
class ParadataNode(Node):
    def __init__(self, node_id, name, node_type, description="", url=None):
        super().__init__(node_id, name, node_type, description)
        self.url = url  # Aggiungi l'attributo url

# DocumentNode Class - Subclass of ParadataNode
class DocumentNode(ParadataNode):
    def __init__(self, node_id, name, node_type="document", description="", url=None):
        super().__init__(node_id, name, node_type=node_type, description=description, url=url)

# CombinerNode Class - Subclass of ParadataNode
class CombinerNode(ParadataNode):
    def __init__(self, node_id, name, description="", sources=[], url=None):
        super().__init__(node_id, name, "combiner", description, url)
        self.sources = sources

# ExtractorNode Class - Subclass of ParadataNode
class ExtractorNode(ParadataNode):
    def __init__(self, node_id, name, description="", source=None, url=None):
        super().__init__(node_id, name, "extractor", description, url)
        self.source = source

# PropertyNode Class - Subclass of ParadataNode
class PropertyNode(ParadataNode):
    def __init__(self, node_id, name, description="", value=None, url=None):
        super().__init__(node_id, name, "property", description, url)
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

