# 3dgraphy/edge.py

class Edge:
    def __init__(self, edge_id, edge_source, edge_target, edge_type):
        self.edge_id = edge_id
        self.edge_source = edge_source
        self.edge_target = edge_target
        self.edge_type = edge_type
        # Puoi aggiungere ulteriori attributi qui, come peso dell'arco, direzionalità, ecc.
