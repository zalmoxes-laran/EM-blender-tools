#s3Dgraphy/nodes/group_node.py
from .base_node import Node

# GroupNode Class
class GroupNode(Node):
    """
    Nodo che rappresenta un gruppo di nodi. Tali gruppi possono essere di vari tipi: vedi sottoclassi di seguito.

    Attributes:
        y_pos (float): Posizione verticale del nodo.
    """

    def __init__(self, node_id, name, description="", y_pos=0.0):
        super().__init__(node_id, name, node_type="Group", description=description)
        self.attributes['y_pos'] = y_pos

class ActivityNodeGroup(GroupNode):
    """
    Nodo gruppo per attività. Una attività è un gruppo logico di azioni che vengono tenute insieme per un fine narrativo e di ordine delle informazioni (es: costruzione di una stanza di un edificio nell'anno x, attività di restauro di varie parti di quella stanza 20 anni dopo)

    """

    def __init__(self, node_id, name, description="", y_pos=0.0):
        super().__init__(node_id, name, description=description, y_pos=y_pos)
        self.node_type = "ActivityNodeGroup"

class ParadataNodeGroup(GroupNode):
    """
    Nodo gruppo per paradata. Questo gruppo tiene insieme tutti i paradati relativi ad una unità stratigrafica: normalmente si chiama "[nome_US]_PD" (ParaData)

    """

    def __init__(self, node_id, name, description="", y_pos=0.0):
        super().__init__(node_id, name, description=description, y_pos=y_pos)
        self.node_type = "ParadataNodeGroup"


class TimeBranchNodeGroup(GroupNode):
    """
    Nodo gruppo per aggregare tuti gli elementi che appartengono ad un ramo temporale.

    """

    def __init__(self, node_id, name, description="", y_pos=0.0):
        super().__init__(node_id, name, description=description, y_pos=y_pos)
        self.node_type = "TimeBranchNodeGroup"