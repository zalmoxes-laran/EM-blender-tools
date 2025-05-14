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
        "Width": {
            "symbol": "⬌",
            "label": "Width",
            "description": "The width of the object, typically measured in meters."
        },
        "Depth": {
            "symbol": "⇵",
            "label": "Depth",
            "description": "The depth of the object, typically measured in meters."
        },
        "Length": {
            "symbol": "↔",
            "label": "Length",
            "description": "The length of the object, typically measured in meters."
        },
        "Diameter": {
            "symbol": "⬤",
            "label": "Diameter",
            "description": "The diameter of circular objects, typically measured in meters."
        },
        "Upper Diameter": {
            "symbol": "⬤",
            "label": "Upper Diameter",
            "description": "The diameter at the top of the object, typically measured in meters."
        },
        "Lower Diameter": {
            "symbol": "⬤",
            "label": "Lower Diameter",
            "description": "The diameter at the bottom of the object, typically measured in meters."
        },
        "Material": {
            "symbol": "🔨",
            "label": "Material",
            "description": "The material the object is made from (e.g., stone, wood)."
        },
        "Morphology": {
            "symbol": "🔄",
            "label": "Morphology",
            "description": "The shape and structure of the object."
        },
        "Style": {
            "symbol": "🎨",
            "label": "Style",
            "description": "The architectural or artistic style of the object."
        },
        "Location": {
            "symbol": "📍",
            "label": "Location",
            "description": "The spatial position or general location of the object."
        },
        "Find Spot": {
            "symbol": "🗺️",
            "label": "Find Spot",
            "description": "The stratigraphic unit where the object was found."
        },
        "Restoration": {
            "symbol": "🛠️",
            "label": "Restoration",
            "description": "Details on any restorations performed on the object."
        },
        "Reworking": {
            "symbol": "🔧",
            "label": "Reworking",
            "description": "Information on any modifications or reworkings of the object."
        },
        "Reuse": {
            "symbol": "♻️",
            "label": "Reuse",
            "description": "Indications of whether the object has been reused."
        },
        "Archaeometric Data": {
            "symbol": "📏",
            "label": "Archaeometric Data",
            "description": "Scientific measurements or analyses related to the object."
        },
        "Existence": {
            "symbol": "✅",
            "label": "Existence",
            "description": "Indicates whether the object exists or has existed."
        },
        "Upper Diameter at Apophyge": {
            "symbol": "⬤",
            "label": "Upper Diameter at Apophyge",
            "description": "Diameter measured at the apophyge of the upper section."
        },
        "Lower Diameter at Apophyge": {
            "symbol": "⬤",
            "label": "Lower Diameter at Apophyge",
            "description": "Diameter measured at the apophyge of the lower section."
        },
        "Documentation 2D-3D": {
            "symbol": "📸",
            "label": "Documentation",
            "description": "Details on 2D or 3D documentation of the object."
        },
        "Bibliography": {
            "symbol": "📚",
            "label": "Bibliography",
            "description": "References or literature associated with the object."
        },
        "Field Compilation Responsible": {
            "symbol": "👤",
            "label": "Field Compilation Responsible",
            "description": "Person responsible for data collection in the field."
        }
    }

    node_type = "property"

    def __init__(self, node_id, name, description="", value=None, property_type="string", data=None, url=None):
        super().__init__(node_id, name, description, url)
        self.value = value
        self.property_type = property_type  # Definisce il tipo della proprietà
        self.data = data if data is not None else {}
        
        # Validazione del tipo di proprietà
        #self.validate_property_type()

    def validate_property_type(self):
        """
        Valida il tipo di proprietà in base al vocabolario. Stampa un avviso se il tipo non è valido.
        """
        if self.property_type not in self.PROPERTY_TYPES:
            print(f"Warning: Property type '{self.property_type}' is not recognized for node '{self.name}' (ID: {self.node_id}).")
            pass

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
