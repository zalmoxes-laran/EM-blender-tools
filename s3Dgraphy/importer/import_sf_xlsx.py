import pandas as pd # type: ignore
from ..graph import Graph
from ..nodes.stratigraphic_node import SpecialFindUnit
from ..nodes.property_node import PropertyNode
from ..edges.edge import Edge

from ...s3Dgraphy import get_graph

class SpecialFindImporter:
    def __init__(self, file_path, graph):
        self.file_path = file_path
        self.graph = graph
        self.qualia_vocabulary = {}

    def load_data(self, sheet_name="Scheda Blocco"):
        # Carica il foglio specificato nel file XLSX
        try:
            data = pd.read_excel(self.file_path, sheet_name=sheet_name)
            self.data = data
        except Exception as e:
            print(f"Errore nel caricamento del file: {e}")
            self.data = None

    def extract_and_link_to_graph(self):
        if self.data is None:
            print("Dati non disponibili. Assicurati di caricare il file correttamente.")
            return

        for _, row in self.data.iterrows():
            # Dati del nodo SpecialFind
            special_find_id = row.get("NUMERO INVENTARIO/CODICE BLOCCO", "")
            special_find_node = self.graph.find_node_by_id(special_find_id)

            # Se il nodo non esiste, creane uno nuovo
            if not special_find_node:
                special_find_node = SpecialFindUnit(
                    node_id=special_find_id,
                    name=row.get("NUMERO INVENTARIO/CODICE BLOCCO", ""),
                    description=row.get("DEFINIZIONE", "")
                )
                special_find_node.attributes["extended_description"] = row.get("DESCRIZIONE", "")
                self.graph.add_node(special_find_node)

            # Estrazione dei qualia come PropertyNode
            qualia = {
                "morfologia": row.get("MORFOLOGIA", ""),
                "materiale": row.get("MATERIALE", ""),
                "ubicazione": row.get("UBICAZIONE", ""),
                "us_di_rinvenimento": row.get("US DI RINVENIMENTO", ""),
                "restauri": row.get("RESTAURI", ""),
                "rilavorazioni": row.get("RILAVORAZIONI", ""),
                "riusi": row.get("RIUSI", ""),
                "dati_archeometrici": row.get("DATI ARCHEOMETRICI", ""),
                "bibliografia": row.get("BIBLIOGRAFIA", ""),
                "documentazione_2d_3d": row.get("DOCUMENTAZIONE 2D-3D", ""),
                "responsabile_compilazione": row.get("RESPONSABILE COMPILAZIONE SUL CAMPO", ""),
                "dimensioni": {
                    "altezza": row.get("ALTEZZA", ""),
                    "larghezza": row.get("LARGHEZZA", ""),
                    "profondità": row.get("PROFONDITÀ", ""),
                    "larghezza_piano_di_attesa": row.get("LARGHEZZA PIANO DI ATTESA", ""),
                    "profondità_piano_di_attesa": row.get("PROFONDITÀ PIANO DI ATTESA", ""),
                    "larghezza_piano_di_posa": row.get("LARGHEZZA PIANO DI POSA", ""),
                    "profondità_piano_di_posa": row.get("PROFONDITÀ PIANO DI POSA", ""),
                    "diametro": row.get("DIAMETRO", ""),
                    "diametro_superiore": row.get("DIAMETRO SUPERIORE", ""),
                    "diametro_inferiore": row.get("DIAMETRO INFERIORE", ""),
                    "diametro_superiore_apophyge": row.get("DIAMETRO SUPERIORE ALL'APOPHYGE", ""),
                    "diametro_inferiore_apophyge": row.get("DIAMETRO INFERIORE ALL'APOPHYGE", "")
                }
            }

            # Crea e collega PropertyNodes per ciascun quale
            for quale_name, quale_value in qualia.items():
                if isinstance(quale_value, dict):  # Per i qualia complessi come dimensioni
                    for sub_quale, sub_value in quale_value.items():
                        if sub_value:  # Solo se il valore è presente
                            quale_id = f"{special_find_id}_{quale_name}_{sub_quale}"
                            self.create_and_link_property_node(special_find_node, quale_id, sub_quale, sub_value)
                else:
                    if quale_value:  # Solo se il valore è presente
                        quale_id = f"{special_find_id}_{quale_name}"
                        self.create_and_link_property_node(special_find_node, quale_id, quale_name, quale_value)

    def create_and_link_property_node(self, special_find_node, quale_id, quale_name, quale_value):
        """
        Crea un PropertyNode e lo collega a uno SpecialFindNode con un edge di tipo 'has_property'.
        
        Args:
            special_find_node (Node): Il nodo SpecialFind a cui collegare il PropertyNode.
            quale_id (str): L'ID del PropertyNode.
            quale_name (str): Nome della proprietà.
            quale_value (str): Valore della proprietà.
        """
        # Verifica se il PropertyNode esiste già
        property_node = self.graph.find_node_by_id(quale_id)
        if not property_node:
            property_node = PropertyNode(
                node_id=quale_id,
                name=quale_name,
                description=quale_value,
                value=quale_value,
                property_type=quale_name
            )
            self.graph.add_node(property_node)

        # Crea l'edge di tipo 'has_property' tra il nodo SpecialFind e il PropertyNode
        edge_id = f"{special_find_node.node_id}_has_property_{property_node.node_id}"
        if not self.graph.find_edge_by_id(edge_id):
            self.graph.add_edge(
                edge_id=edge_id,
                edge_source=special_find_node.node_id,
                edge_target=property_node.node_id,
                edge_type="has_property"
            )

# Esempio di utilizzo
file_path = '/mnt/data/Catalogo_blocchi_13_09.xlsx'
graph = get_graph()  # Assumendo che il grafo sia stato caricato o inizializzato

importer = SpecialFindImporter(file_path, graph)
importer.load_data()
importer.extract_and_link_to_graph()
