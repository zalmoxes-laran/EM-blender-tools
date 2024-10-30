# 3dgraphy/nodes/stratigraphic_node.py

from .base_node import Node

class StratigraphicNode(Node):
    """
    Base class for all stratigraphic units within the graph structure.
    Inherits from Node and provides additional functionality specific to stratigraphy.
    """

    def __init__(self, node_id, name, node_type="StratigraphicUnit", description=""):
        super().__init__(node_id, name, node_type, description)
        self.symbol = None
        self.label = None
        self.detailed_description = None  # To avoid conflict with `description`


class StratigraphicUnit(StratigraphicNode):
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, "US", description)
        self.symbol = "white rectangle"
        self.label = "US (or SU)"
        self.detailed_description = "Stratigraphic Unit (SU) or negative stratigraphic unit."


class StructuralVirtualStratigraphicUnit(StratigraphicNode):
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, "USVs", description)
        self.symbol = "black parallelogram"
        self.label = "USV/s"
        self.detailed_description = "Structural Virtual Stratigraphic Unit (USV/s)."


class SeriesOfStratigraphicUnit(StratigraphicNode):
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, "serSU", description)
        self.symbol = "white ellipse"
        self.label = "US series"
        self.detailed_description = "Series of Stratigraphic Units (SU)."


class SeriesOfNonStructuralVirtualStratigraphicUnit(StratigraphicNode):
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, "serUSVn", description)
        self.symbol = "black ellipse green border"
        self.label = "USVn series"
        self.detailed_description = "Series of non-structural Virtual Stratigraphic Units."


class SeriesOfStructuralVirtualStratigraphicUnit(StratigraphicNode):
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, "serUSVs", description)
        self.symbol = "black ellipse blue border"
        self.label = "USVs series"
        self.detailed_description = "Series of Structural Virtual Stratigraphic Units."


class NonStructuralVirtualStratigraphicUnit(StratigraphicNode):
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, "USVn", description)
        self.symbol = "black hexagon"
        self.label = "USV/n"
        self.detailed_description = "Non-structural Virtual Stratigraphic Unit (USV/n)."


class SpecialFindUnit(StratigraphicNode):
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, "SF", description)
        self.symbol = "white octagon"
        self.label = "Special Find"
        self.detailed_description = "Not in situ element that needs repositioning."


class VirtualSpecialFindUnit(StratigraphicNode):
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, "VSF", description)
        self.symbol = "black octagon"
        self.label = "Virtual Special Find"
        self.detailed_description = "Hypothetical reconstruction of a fragmented Special Find."


class DocumentaryStratigraphicUnit(StratigraphicNode):
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, "USD", description)
        self.symbol = "white round rectangle"
        self.label = "USD"
        self.detailed_description = "Documentary Stratigraphic Unit."


class TransformationStratigraphicUnit(StratigraphicNode):
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, "TSU", description)
        self.symbol = "dotted white rectangle"
        self.label = "TSU"
        self.detailed_description = "Transformation Unit."


class ContinuityNode(StratigraphicNode):
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, "BR", description)
        self.symbol = "black rhombus"
        self.label = "continuity node"
        self.detailed_description = "End of life of a US/USV."


class StratigraphicEventNode(StratigraphicNode):
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, "SE", description)
        self.symbol = "to be defined"
        self.label = "stratigraphic event node"
        self.detailed_description = "A stratigraphic event is the process or event that leads to the formation or alteration of a stratigraphic unit. It is distinct from the unit itself, which represents the result or outcome of the event. The event can be thought of as a precursor and can be paired with its resulting unit to provide a more detailed temporal range. This allows for the documentation of both the initial moment of action (e.g., the start of construction, a collapse, or an incision) and the final state (the resulting unit that persists over time)."


class UnknownNode(StratigraphicNode):
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, "unknown", description)
        self.symbol = "question mark"
        self.label = "Unknown node"
        self.detailed_description = "Fallback node for unrecognized types."
