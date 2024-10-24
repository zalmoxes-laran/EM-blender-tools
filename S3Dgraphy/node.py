# 3dgraphy/node.py
class Node:
    """
    Classe base per rappresentare un nodo nel grafo.

    Attributes:
        node_id (str): Identificatore univoco del nodo.
        name (str): Nome del nodo.
        node_type (str): Tipo di nodo.
        description (str): Descrizione del nodo.
        attributes (dict): Dizionario per attributi aggiuntivi.
    """

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

# ParadataNode Class - Subclass of Node
class ParadataNode(Node):
    """
    Classe base per i nodi che rappresentano metadati o informazioni su come i dati sono stati generati.

    Attributes:
        url (str): URL associato al nodo.
    """

    def __init__(self, node_id, name, node_type, description="", url=None):
        super().__init__(node_id, name, node_type, description)
        self.url = url  # Aggiunge l'attributo url
        self.data = {}  # Dizionario per dati aggiuntivi

# DocumentNode Class - Subclass of ParadataNode
class DocumentNode(ParadataNode):
    """
    Nodo che rappresenta un documento o una fonte.

    Attributes:
        data (dict): Metadati aggiuntivi, come 'url_type'.
    """

    def __init__(self, node_id, name, description="", url=None, data=None):
        super().__init__(node_id, name, node_type="document", description=description, url=url)
        self.data = data if data is not None else {}

# CombinerNode Class - Subclass of ParadataNode
class CombinerNode(ParadataNode):
    """
    Nodo che rappresenta un ragionamento che combina informazioni da più sorgenti.

    Attributes:
        sources (list): Lista di sorgenti combinate.
        data (dict): Metadati aggiuntivi, come 'author'.
    """

    def __init__(self, node_id, name, description="", sources=None, data=None, url=None):
        super().__init__(node_id, name, "combiner", description, url)
        self.sources = sources if sources is not None else []
        self.data = data if data is not None else {}

# ExtractorNode Class - Subclass of ParadataNode
class ExtractorNode(ParadataNode):
    """
    Nodo che rappresenta l'estrazione di informazioni da una fonte.

    Attributes:
        source (str): Fonte da cui è stata estratta l'informazione.
        data (dict): Metadati aggiuntivi, come 'author', 'url_type', 'icon', ecc.
    """

    def __init__(self, node_id, name, description="", source=None, data=None, url=None):
        super().__init__(node_id, name, "extractor", description, url)
        self.source = source
        self.data = data if data is not None else {}



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

    def __init__(self, node_id, name, description="", value=None, property_type="string", data=None, url=None):
        super().__init__(node_id, name, "property", description, url)
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


# EpochNode Class
class EpochNode(Node):
    """
    Nodo che rappresenta un'epoca temporale. Si tratta di un insieme di comodo che permette di attribuire d'ufficio una serie di azioni ad un delta temporale. Una volta che i dati puntuali sulla cronologia, espressi come proprietà start_time ed end_time delle singole US viene definito grazie ad elementi dtanti, tali nodi epoca vengono ignorati laddove ci sono i suddetti dati puntuali. 

    Attributes:
        start_time (float): Tempo di inizio dell'epoca.
        end_time (float): Tempo di fine dell'epoca.
        color (str): Colore associato all'epoca.
    """

    def __init__(self, node_id, name, start_time, end_time, color="#FFFFFF", description=""):
        super().__init__(node_id, name, "epoch", description)
        self.start_time = start_time
        self.end_time = end_time
        self.color = color

    def set_name(self, name):
        self.name = name

    def set_start_time(self, start_time):
        self.start_time = start_time

    def set_end_time(self, end_time):
        self.end_time = end_time

    def set_color(self, color):
        self.color = color