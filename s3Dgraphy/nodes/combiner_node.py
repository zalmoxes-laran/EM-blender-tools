from .paradata_node import ParadataNode

# CombinerNode Class - Subclass of ParadataNode
class CombinerNode(ParadataNode):
    """
    Nodo che rappresenta un ragionamento che combina informazioni da più sorgenti.

    Attributes:
        sources (list): Lista di sorgenti combinate.
        data (dict): Metadati aggiuntivi, come 'author'.
    """
    node_type = "combiner"
    
    def __init__(self, node_id, name, description="", sources=None, data=None, url=None):
        super().__init__(node_id, name, description, url)
        self.sources = sources if sources is not None else []
        self.data = data if data is not None else {}
