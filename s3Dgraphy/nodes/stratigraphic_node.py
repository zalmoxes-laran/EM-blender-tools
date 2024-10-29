# 3dgraphy/nodes/stratigraphic_node.py

from .base_node import Node

# StratigraphicNode Class
class StratigraphicNode(Node):
    """
    Nodo che rappresenta un'unità stratigrafica.

    Attributes:
        epoch (optional): Epoca associata al nodo. Informazione deprecata da quando si usano i nodi epoca per associare le stratigrafie ad insiemi temporali oppure i nodi proprietà per dettagliare gli start end temporali dei singoli nodi. 
    """

    STRATIGRAPHIC_TYPES = {
        "US": {
            "symbol": "white rectangle",
            "label": "US (or SU)",
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
        "SE": {
            "symbol": "to be defined",
            "label": "stratigraphic event node",
            "description": "A stratigraphic event is the process or event that leads to the formation or alteration of a stratigraphic unit. It is distinct from the unit itself, which represents the result or outcome of the event. The event can be thought of as a precursor and can be paired with its resulting unit to provide a more detailed temporal range. This allows for the documentation of both the initial moment of action (e.g., the start of construction, a collapse, or an incision) and the final state (the resulting unit that persists over time)."
        },        
        "unknown": {
            "symbol": "question mark",
            "label": "Unknown node",
            "description": "Fallback node for unrecognized types."
        }
    }

    def __init__(self, node_id, name, stratigraphic_type, description="", epoch=None):
        super().__init__(node_id, name, node_type=stratigraphic_type, description=description)
        self.epoch = epoch  # Proprietà specifica per i nodi stratigrafici
        self.validate_stratigraphic_type()

    def validate_stratigraphic_type(self):
        if self.node_type not in self.STRATIGRAPHIC_TYPES:
            raise ValueError(f"Invalid stratigraphic type: {self.node_type}")

    def get_stratigraphic_info(self):
        return self.STRATIGRAPHIC_TYPES.get(self.node_type)
