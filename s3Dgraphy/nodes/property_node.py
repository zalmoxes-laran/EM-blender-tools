from .paradata_node import ParadataNode

# PropertyNode Class - Subclass of ParadataNode
class PropertyNode(ParadataNode):
    """
    Nodo che rappresenta una proprietà associata a un altro nodo.

    Attributes:
        value (any): Valore della proprietà.
        property_type (str): Tipo di proprietà (es. "Height", "Length", etc.).
        data (dict): Metadati aggiuntivi, come 'author', 'time_start', 'time_end'.
    """

    # Vocabolario delle proprietà
    PROPERTY_TYPES = {
        "Height": {
            "symbol": "↕",
            "label": "Height",
            "description": "The height of the object, typically measured in meters."
        },
        "Length": {
            "symbol": "↔",
            "label": "Length",
            "description": "The length of the object, typically measured in meters."
        },
        "Depth": {
            "symbol": "⇵",
            "label": "Depth",
            "description": "The depth of the object, typically measured in meters."
        },
        "Style": {
            "symbol": "🎨",
            "label": "Style",
            "description": "The architectural or artistic style of the object."
        },
        "Masonry": {
            "symbol": "🧱",
            "label": "Masonry",
            "description": "Details about the type of masonry or construction technique."
        },
        "Start_time": {
            "symbol": "⏱️",
            "label": "Start Time",
            "description": "The beginning of the temporal range, typically a year."
        },
        "End_time": {
            "symbol": "⌛",
            "label": "End Time",
            "description": "The end of the temporal range, typically a year."
        },
        "Temporal_delta": {
            "symbol": "Δt",
            "label": "Temporal Delta",
            "description": "The time span or delta between the start and end times."
        },
        "Existence": {
            "symbol": "✅",
            "label": "Existence",
            "description": "Indicates whether the object exists or has existed."
        },
        "Material": {
            "symbol": "🔨",
            "label": "Material",
            "description": "The material the object is made from (e.g., stone, wood)."
        },
        "Position": {
            "symbol": "📍",
            "label": "Position",
            "description": "The spatial position or coordinates of the object."
        }
    }

    node_type = "property"

    def __init__(self, node_id, name, description="", value=None, property_type="string", data=None, url=None):
        super().__init__(node_id, name, description, url)
        self.value = value
        self.property_type = property_type  # Definisce il tipo della proprietà
        self.data = data if data is not None else {}
        
        # Validazione del tipo di proprietà
        self.validate_property_type()

    def validate_property_type(self):
        """
        Valida il tipo di proprietà in base al vocabolario. Stampa un avviso se il tipo non è valido.
        """
        if self.property_type not in self.PROPERTY_TYPES:
            print(f"Warning: Property type '{self.property_type}' is not recognized for node '{self.name}' (ID: {self.node_id}).")

    def get_property_info(self):
        """
        Restituisce le informazioni sul tipo e valore della proprietà.
        """
        return {
            "name": self.name,
            "value": self.value,
            "type": self.property_type,
            "description": self.description
        }
