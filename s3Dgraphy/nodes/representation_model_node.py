from .base_node import Node
from typing import Dict, Any

class RepresentationModelNode(Node):
    """
    Node che rappresenta un modello 3D o un'immagine spazializzata.
    
    Attributes:
        node_type (str): Tipo di nodo, impostato su "representation_model".
        type (str): Il tipo di rappresentazione ("RM", "spatialized_image" o "generic").
        url (str): URL della risorsa (es. file .gltf).
    """
    
    node_type = "representation_model"

    # Tipi validi di rappresentazione
    VALID_TYPES = {
        "RM": "Representation Model - Modello 3D",
        "spatialized_image": "Immagine spazializzata",
        "generic": "Rappresentazione generica"
    }

    def __init__(self, 
                 node_id: str,
                 name: str,
                 type: str = "RM",
                 url: str = "",
                 description: str = ""):
        """
        Inizializza un nuovo RepresentationModelNode.
        
        Args:
            node_id (str): Identificatore univoco del nodo.
            name (str): Nome del modello.
            type (str): Tipo di rappresentazione ("RM", "spatialized_image" o "generic").
            url (str): URL della risorsa.
            description (str): Descrizione del modello.
            
        Raises:
            ValueError: Se il tipo non è valido.
        """
        super().__init__(node_id=node_id, name=name, description=description)
        
        if type not in self.VALID_TYPES:
            raise ValueError(f"type must be one of: {list(self.VALID_TYPES.keys())}")
        
        self.type = type
        self.url = url
        
        # Struttura data per serializzazione
        self.data = {
            "url": self.url
        }
    
    def set_url(self, url: str) -> None:
        """
        Imposta l'URL della risorsa.
        
        Args:
            url (str): URL della risorsa.
        """
        self.url = url
        self.data["url"] = url

    def to_dict(self) -> Dict[str, Any]:
        """
        Converte il nodo in un dizionario per la serializzazione JSON.
        
        Returns:
            Dict[str, Any]: Rappresentazione del nodo come dizionario.
        """
        return {
            self.node_id: {
                "type": self.type,
                "name": self.name,
                "description": self.description,
                "data": self.data
            }
        }

# Esempio di utilizzo:
"""
# Creazione di un modello di rappresentazione
rm = RepresentationModelNode(
    node_id="tempio_2_secolo_sgyfg",
    name="Tempio Traiano",
    type="RM",
    url="path/to/model.gltf",
    description="Modello 3D del tempio di Traiano."
)

# Serializzazione in dizionario
json_dict = rm.to_dict()
"""