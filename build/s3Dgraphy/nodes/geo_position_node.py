# s3Dgraphy/nodes/geo_position_node.py

from .base_node import Node

class GeoPositionNode(Node):
    """
    Classe per rappresentare un nodo GeoPosition all'interno del grafo.

    Attributi:
        type (str): Tipo di nodo, impostato su "geo_position".
        data (dict): Dati relativi alla posizione geografica.
    """
    node_type = "geo_position"
    def __init__(self, node_id, epsg=4326, shift_x=0.0, shift_y=0.0, shift_z=0.0):
        """
        Inizializza una nuova istanza di GeoPositionNode.
        
        Args:
            node_id (str): Identificativo univoco del nodo.
            epsg (int, opzionale): Codice EPSG del sistema di riferimento delle coordinate. Defaults to 4326.
            shift_x (float, opzionale): Spostamento lungo l'asse X. Defaults to 0.0.
            shift_y (float, opzionale): Spostamento lungo l'asse Y. Defaults to 0.0.
            shift_z (float, opzionale): Spostamento lungo l'asse Z. Defaults to 0.0.
        """
        super().__init__(node_id=node_id, name="geo_position")
        self.data = {
            "epsg": epsg,
            "shift_x": shift_x,
            "shift_y": shift_y,
            "shift_z": shift_z
        }
    
    def to_dict(self):
        """
        Converte l'istanza di GeoPositionNode in un dizionario.
        
        Returns:
            dict: Rappresentazione del GeoPositionNode come dizionario.
        """
        return {
            "type": self.node_type,
            "name": self.name,
            "data": self.data
        }
