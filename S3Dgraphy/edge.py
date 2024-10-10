# 3dgraphy/edge.py
class Edge:
    """
    Classe per rappresentare un arco nel grafo.

    Attributes:
        edge_id (str): Identificatore univoco dell'arco.
        edge_source (str): ID del nodo sorgente.
        edge_target (str): ID del nodo destinazione.
        edge_type (str): Tipo di arco, deve essere uno dei valori definiti in EDGE_TYPES.
    """

    EDGE_TYPES = {
        "line": {
            "label": "Chronological Sequence",
            "description": "Relazione di cronologia relativa - una cosa viene prima di un'altra."
        },
        "dashed": {
            "label": "Data Provenance",
            "description": "Indica la provenienza dei dati."
        },
        "dotted": {
            "label": "Temporal Transformation",
            "description": "Rappresenta un oggetto che cambia nel tempo."
        },
        "double_line": {
            "label": "Contemporaneous Elements",
            "description": "Indica che due US sono contemporanee."
        },
        "dashed_dotted": {
            "label": "Contrasting Properties",
            "description": "Rappresenta proprietà contrastanti o in mutua esclusione tra loro."
        },
        "has_first_epoch": {
            "label": "Has First Epoch",
            "description": "Indica l'epoca iniziale associata a un nodo."
        },
        "survive_in_epoch": {
            "label": "Survives In Epoch",
            "description": "Indica che un nodo continua a esistere in una determinata epoca."
        },
        "is_grouped_in": {
            "label": "Is Grouped In",
            "description": "Indica che un nodo è parte di un gruppo."
        },
        "connected_to": {
            "label": "Connected To",
            "description": "Relazione generica di connessione tra due nodi."
        },
        "has_property": {
            "label": "Has Property",
            "description": "Collega un nodo a una sua proprietà."
        },
        "extracted_from": {
            "label": "Extracted From",
            "description": "Indica che un'informazione è stata estratta da una fonte."
        },
        "combines": {
            "label": "Combines",
            "description": "Indica che un nodo combina informazioni da varie fonti."
        },
        # qui altri tipi di edge qui se necessario...
    }

    def __init__(self, edge_id, edge_source, edge_target, edge_type):
        if edge_type not in self.EDGE_TYPES:
            raise ValueError(f"Tipo di arco non valido: {edge_type}")
        self.edge_id = edge_id
        self.edge_source = edge_source
        self.edge_target = edge_target
        self.edge_type = edge_type
        # Si possono aggiungere ulteriori attributi qui, come peso dell'arco, direzionalità, ecc.