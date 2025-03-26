from .base_node import Node
from datetime import datetime, date

class EmbargoNode(Node):
    """
    Classe per rappresentare un nodo embargo nel grafo.
    Un embargo è una restrizione temporale sull'accesso o la distribuzione di un contenuto.
    
    Attributi:
        embargo_start (str): Data di inizio dell'embargo nel formato ISO (YYYY-MM-DD).
        embargo_end (str): Data di fine dell'embargo nel formato ISO (YYYY-MM-DD).
        reason (str, opzionale): Motivazione dell'embargo.
    """
    node_type = "embargo"
    
    def __init__(self, node_id, name="Unnamed Embargo", description="", 
                 embargo_start=None, embargo_end=None, reason=""):
        """
        Inizializza una nuova istanza di EmbargoNode.
        
        Args:
            node_id (str): Identificatore univoco del nodo.
            name (str, opzionale): Nome dell'embargo. Default a "Unnamed Embargo".
            description (str, opzionale): Descrizione dell'embargo. Default a stringa vuota.
            embargo_start (str or date, opzionale): Data di inizio dell'embargo.
                Se None, viene usata la data corrente.
            embargo_end (str or date, opzionale): Data di fine dell'embargo.
                Se None, non viene impostata alcuna fine (embargo indefinito).
            reason (str, opzionale): Motivazione dell'embargo. Default a stringa vuota.
        """
        super().__init__(node_id=node_id, name=name, description=description)
        
        # Converti date in formato stringa ISO se necessario
        if embargo_start is None:
            embargo_start = date.today().isoformat()
        elif isinstance(embargo_start, date) or isinstance(embargo_start, datetime):
            embargo_start = embargo_start.isoformat().split('T')[0]
            
        if embargo_end is not None:
            if isinstance(embargo_end, date) or isinstance(embargo_end, datetime):
                embargo_end = embargo_end.isoformat().split('T')[0]
        
        self.data = {
            "embargo_start": embargo_start,
            "embargo_end": embargo_end,
            "reason": reason
        }
        
    def is_active(self, reference_date=None):
        """
        Verifica se l'embargo è attivo in una data specificata.
        
        Args:
            reference_date (date, opzionale): Data di riferimento.
                Se None, viene usata la data corrente.
                
        Returns:
            bool: True se l'embargo è attivo, False altrimenti.
        """
        if reference_date is None:
            reference_date = date.today()
        elif isinstance(reference_date, str):
            reference_date = date.fromisoformat(reference_date)
            
        embargo_start = date.fromisoformat(self.data["embargo_start"])
        
        # Se non c'è una data di fine, l'embargo è indefinito
        if self.data["embargo_end"] is None:
            return reference_date >= embargo_start
            
        embargo_end = date.fromisoformat(self.data["embargo_end"])
        return embargo_start <= reference_date <= embargo_end
        
    def to_dict(self):
        """
        Converte l'istanza di EmbargoNode in un dizionario.
        
        Returns:
            dict: Rappresentazione dell'EmbargoNode come dizionario.
        """
        return {
            "id": self.node_id,
            "type": self.node_type,
            "name": self.name,
            "description": self.description,
            "data": self.data
        }

"""
Esempio di utilizzo:

from datetime import date
from dateutil.relativedelta import relativedelta

# Crea un embargo di 5 anni dal 2024-01-01
future_date = date.today() + relativedelta(years=5)

embargo_node = EmbargoNode(
    node_id="embargo_5y",
    name="Embargo di 5 anni",
    description="Embargo di 5 anni sui dati del progetto",
    embargo_start="2024-01-01",
    embargo_end=future_date.isoformat(),
    reason="Progetto in corso"
)

# Collega l'embargo a una licenza
license_node = LicenseNode(node_id="license_1", name="License CC-BY")
graph.add_node(license_node)
graph.add_node(embargo_node)

graph.add_edge(
    edge_id="license_embargo", 
    edge_source=license_node.node_id, 
    edge_target=embargo_node.node_id,
    edge_type="has_embargo"
)
"""