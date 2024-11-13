from .paradata_node import ParadataNode

# DocumentNode Class - Subclass of ParadataNode
class DocumentNode(ParadataNode):
    """
    Nodo che rappresenta un documento o una fonte.

    Attributes:
        data (dict): Metadati aggiuntivi, come 'url_type'.
    """
    node_type = "document"

    def __init__(self, node_id, name, description="", url=None, data=None):
        super().__init__(node_id, name, description=description, url=url)
        self.data = data if data is not None else {}
