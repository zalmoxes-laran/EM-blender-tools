from .base_node import Node

# EpochNode Class
class EpochNode(Node):
    """
    Nodo che rappresenta un'epoca temporale. Si tratta di un insieme di comodo che permette di attribuire d'ufficio una serie di azioni ad un delta temporale. Una volta che i dati puntuali sulla cronologia, espressi come proprietà start_time ed end_time delle singole US viene definito grazie ad elementi dtanti, tali nodi epoca vengono ignorati laddove ci sono i suddetti dati puntuali. 

    Attributes:
        start_time (float): Tempo di inizio dell'epoca.
        end_time (float): Tempo di fine dell'epoca.
        color (str): Colore associato all'epoca.
    """
    
    node_type = "epoch"

    def __init__(self, node_id, name, start_time, end_time, color="#FFFFFF", description=""):
        super().__init__(node_id, name, description)
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