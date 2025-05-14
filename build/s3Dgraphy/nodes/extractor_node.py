from .paradata_node import ParadataNode

# ExtractorNode Class - Subclass of ParadataNode
class ExtractorNode(ParadataNode):
    """
    Nodo che rappresenta l'estrazione di informazioni da una fonte.

    Attributes:
        source (str): Fonte da cui è stata estratta l'informazione.
        data (dict): Metadati aggiuntivi, come 'author', 'url_type', 'icon', ecc.
    """
    node_type = "extractor"
    def __init__(self, node_id, name, description="", source=None, data=None, url=None):
        super().__init__(node_id, name, description, url)
        self.source = source
        self.data = data if data is not None else {}
