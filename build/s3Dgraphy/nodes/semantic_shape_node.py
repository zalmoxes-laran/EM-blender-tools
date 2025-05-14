from .base_node import Node
from typing import List, Union, Dict, Any

class SemanticShapeNode(Node):
    """
    Nodo che rappresenta una forma semantica nello spazio 3D.
    Può essere un proxy di un'unità stratigrafica o un'annotazione generica.
    
    Supporta la definizione di forme convesse (convexshapes) e sfere (spheres) 
    per la rappresentazione geometrica.
    
    Attributes:
        node_type (str): Tipo di nodo, impostato su "semantic_shape".
        type (str): Il tipo specifico di forma semantica ("proxy" o "generic").
        url (str): URL della risorsa proxy (es. file .glb).
        convexshapes (List[List[float]]): Lista di forme convesse.
        spheres (List[List[float]]): Lista di sfere (x, y, z, raggio).
    """
    
    node_type = "semantic_shape"

    def __init__(self, 
                 node_id: str,
                 name: str,
                 type: str = "proxy",
                 url: str = "",
                 convexshapes: List[List[float]] = None,
                 spheres: List[List[float]] = None,
                 description: str = ""):
        """
        Inizializza un nuovo nodo SemanticShape.
        
        Args:
            node_id (str): Identificatore univoco del nodo.
            name (str): Nome del nodo.
            type (str): Tipo di forma ("proxy" o "generic").
            url (str, optional): URL della risorsa proxy.
            convexshapes (List[List[float]], optional): Lista di forme convesse.
            spheres (List[List[float]], optional): Lista di sfere.
            description (str, optional): Descrizione del nodo.
        """
        super().__init__(node_id=node_id, name=name, description=description)
        
        if type not in ["proxy", "generic"]:
            raise ValueError("type must be either 'proxy' or 'generic'")
        
        self.type = type
        self.url = url
        self.convexshapes = convexshapes or []
        self.spheres = spheres or []
        
        # Struttura data per serializzazione
        self.data = {
            "url": self.url,
            "convexshapes": self.convexshapes,
            "spheres": self.spheres
        }

    def add_convex_shape(self, vertices: List[float]) -> None:
        """
        Aggiunge una forma convessa definita dai suoi vertici.
        
        Args:
            vertices (List[float]): Lista di coordinate dei vertici [x1,y1,z1, x2,y2,z2, ...].
        
        Raises:
            ValueError: Se la lista di vertici non è valida.
        """
        if len(vertices) % 3 != 0:
            raise ValueError("Vertices list must contain triplets of coordinates (x,y,z)")
        
        self.convexshapes.append(vertices)
        self.data["convexshapes"] = self.convexshapes

    def add_sphere(self, x: float, y: float, z: float, radius: float) -> None:
        """
        Aggiunge una sfera definita da centro e raggio.
        
        Args:
            x (float): Coordinata X del centro.
            y (float): Coordinata Y del centro.
            z (float): Coordinata Z del centro.
            radius (float): Raggio della sfera.
        
        Raises:
            ValueError: Se il raggio non è positivo.
        """
        if radius <= 0:
            raise ValueError("Sphere radius must be positive")
        
        self.spheres.append([x, y, z, radius])
        self.data["spheres"] = self.spheres

    def set_url(self, url: str) -> None:
        """
        Imposta l'URL della risorsa proxy.
        
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
                "name": self.name,
                "type": self.type,
                "description": self.description,
                "data": self.data
            }
        }

# Esempio di utilizzo:
"""
# Creazione di un proxy
proxy = SemanticShapeNode(
    node_id="USM99_proxy",
    name="USM99",
    type="proxy",  # Ora usiamo type invece di shape_type
    url="path/to/proxy.glb"
)

# Aggiunta di una forma convessa
proxy.add_convex_shape([
    0.1283, -0.036071, 0.014002,
    0.11913, -0.0499, 0.027315,
    0.070473, -0.054526, 0.030398,
    0.070019, -0.033705, 0.0087088
])

# Aggiunta di una sfera
proxy.add_sphere(-0.068129, -0.036508, 0.092894, 0.01)

# Serializzazione in dizionario
json_dict = proxy.to_dict()
"""