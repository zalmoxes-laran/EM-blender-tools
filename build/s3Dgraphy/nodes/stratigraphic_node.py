# 3dgraphy/nodes/stratigraphic_node.py

from .base_node import Node

class StratigraphicNode(Node):
    """
    Base class for all stratigraphic units within the graph structure.
    Inherits from Node and provides additional functionality specific to stratigraphy.
    """
    node_type = "StratigraphicNode"

    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = None
        self.label = None
        self.detailed_description = None  # To avoid conflict with `description`


class StratigraphicUnit(StratigraphicNode):
    node_type = "US"

    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "white rectangle"
        self.label = "US (or SU)"
        self.detailed_description = "Stratigraphic Unit (SU) or negative stratigraphic unit."

class StructuralVirtualStratigraphicUnit(StratigraphicNode):
    node_type = "USVs"

    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "black parallelogram"
        self.label = "USV/s"
        self.detailed_description = "Structural Virtual Stratigraphic Unit (USV/s)."


class SeriesOfStratigraphicUnit(StratigraphicNode):
    node_type = "serSU"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "white ellipse"
        self.label = "US series"
        self.detailed_description = "Series of Stratigraphic Units (SU)."


class SeriesOfNonStructuralVirtualStratigraphicUnit(StratigraphicNode):
    node_type = "serUSVn"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "black ellipse green border"
        self.label = "USVn series"
        self.detailed_description = "Series of non-structural Virtual Stratigraphic Units."


class SeriesOfStructuralVirtualStratigraphicUnit(StratigraphicNode):
    node_type = "serUSVs"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "black ellipse blue border"
        self.label = "USVs series"
        self.detailed_description = "Series of Structural Virtual Stratigraphic Units."


class NonStructuralVirtualStratigraphicUnit(StratigraphicNode):
    node_type = "USVn"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "black hexagon"
        self.label = "USV/n"
        self.detailed_description = "Non-structural Virtual Stratigraphic Unit (USV/n)."


class SpecialFindUnit(StratigraphicNode):
    node_type = "SF"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "white octagon"
        self.label = "Special Find"
        self.detailed_description = "Not in situ element that needs repositioning."


class VirtualSpecialFindUnit(StratigraphicNode):
    node_type= "VSF"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "black octagon"
        self.label = "Virtual Special Find"
        self.detailed_description = "Hypothetical reconstruction of a fragmented Special Find."


class DocumentaryStratigraphicUnit(StratigraphicNode):
    node_type = "USD"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "white round rectangle"
        self.label = "USD"
        self.detailed_description = "Documentary Stratigraphic Unit."


class TransformationStratigraphicUnit(StratigraphicNode):
    node_type = "TSU"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "dotted white rectangle"
        self.label = "TSU"
        self.detailed_description = "Transformation Unit."


class ContinuityNode(StratigraphicNode):
    node_type = "BR"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "black rhombus"
        self.label = "continuity node"
        self.detailed_description = "End of life of a US/USV."


class StratigraphicEventNode(StratigraphicNode):
    node_type = "SE"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "to be defined"
        self.label = "stratigraphic event node"
        self.detailed_description = "A stratigraphic event is the process or event that leads to the formation or alteration of a stratigraphic unit. It is distinct from the unit itself, which represents the result or outcome of the event. The event can be thought of as a precursor and can be paired with its resulting unit to provide a more detailed temporal range. This allows for the documentation of both the initial moment of action (e.g., the start of construction, a collapse, or an incision) and the final state (the resulting unit that persists over time)."


class UnknownNode(StratigraphicNode):
    node_type = "unknown"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "question mark"
        self.label = "Unknown node"
        self.detailed_description = "Fallback node for unrecognized types."
