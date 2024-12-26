# import_EMdb.py

import bpy # type: ignore
from bpy.types import Operator # type: ignore
import pandas as pd
from ..s3Dgraphy import get_graph, MultiGraphManager
from ..s3Dgraphy.nodes.stratigraphic_node import StratigraphicNode
from ..s3Dgraphy.nodes.property_node import PropertyNode
from ..s3Dgraphy.edges import Edge
from ..s3Dgraphy.graph import Graph
import os

class EM_OT_Import3DGISDatabase(Operator):
    bl_idname = "em.import_3dgis_database"
    bl_label = "Import 3D GIS Database"
    bl_description = "Import stratigraphic units from Excel file"
    
    def import_generic_xlsx(self, context, filepath, sheet_name, id_column):
        """
        Importa dati da un file Excel generico.
        Crea un nodo stratigrafico per ogni riga e nodi proprietà per ogni altra colonna.
        """

        try:
            # Converti il percorso nel formato corretto
            abs_filepath = bpy.path.abspath(filepath)
            
            # Verifica che il file esista
            if not os.path.exists(abs_filepath):
                self.report({'ERROR'}, f"File not found: {abs_filepath}")
                return False

            # Leggi il file Excel
            try:
                df = pd.read_excel(abs_filepath, sheet_name=sheet_name)
            except FileNotFoundError:
                self.report({'ERROR'}, f"Cannot open file: {abs_filepath}")
                return False
            except Exception as e:
                self.report({'ERROR'}, f"Error reading Excel file: {str(e)}")
                return False

            # Verifica che la colonna ID esista
            if id_column not in df.columns:
                self.report({'ERROR'}, f"Column '{id_column}' not found in Excel sheet")
                return False
                
            # Crea un nuovo grafo (rimuovendo eventuali grafi esistenti)
            graph_id = "3dgis_graph"
            if get_graph(graph_id):
                MultiGraphManager().remove_graph(graph_id)
            
            graph = Graph(graph_id=graph_id)
            
            # Processa ogni riga
            for idx, row in df.iterrows():
                try:
                    # Crea nodo stratigrafico
                    strat_id = str(row[id_column])
                    strat_node = StratigraphicNode(
                        node_id=strat_id,
                        name=strat_id,
                        description="Imported from generic XLSX"
                    )
                    graph.add_node(strat_node)
                    
                    # Crea nodi proprietà per ogni altra colonna
                    for col in df.columns:
                        if col != id_column and pd.notna(row[col]):
                            # Crea nodo proprietà
                            prop_id = f"{strat_id}_{col}"
                            prop_node = PropertyNode(
                                node_id=prop_id,
                                name=col,
                                description=str(row[col]),
                                value=str(row[col])
                            )
                            graph.add_node(prop_node)
                            
                            # Crea edge
                            edge_id = f"{strat_id}_{col}_edge"
                            graph.add_edge(
                                edge_id=edge_id,
                                edge_source=strat_id,    # dal nodo stratigrafico
                                edge_target=prop_id,     # al nodo proprietà
                                edge_type="has_property" # tipo corretto secondo le regole
                            )
                            
                except Exception as e:
                    self.report({'WARNING'}, f"Error processing row {idx}: {str(e)}")
                    continue
                    
            # Salva il grafo nel MultiGraphManager
            MultiGraphManager().graphs[graph_id] = graph
            
            # Popola le liste di Blender
            from ..populate_lists import populate_blender_lists_from_graph, clear_lists
            clear_lists(context)  # Pulisci le liste esistenti
            populate_blender_lists_from_graph(context, graph)
            
            self.report({'INFO'}, f"Successfully imported {len(df)} units with properties")
            return True
            
        except Exception as e:
            self.report({'ERROR'}, f"Error importing Excel file: {str(e)}")
            return False
            
    def execute(self, context):
        em_tools = context.scene.em_tools
        
        if em_tools.mode_switch:  # Se in modalità EM avanzata
            self.report({'ERROR'}, "This import is only available in 3D GIS mode")
            return {'CANCELLED'}
            
        # Importazione XLSX generico    
        if em_tools.mode_3dgis_import_type == "generic_xlsx":
            if not em_tools.generic_xlsx_file:
                self.report({'ERROR'}, "No Excel file selected")
                return {'CANCELLED'}
                
            if not em_tools.xlsx_id_column:
                self.report({'ERROR'}, "No ID column specified")
                return {'CANCELLED'}

            result = self.import_generic_xlsx(
                context,
                em_tools.generic_xlsx_file.strip(),  # Rimuovi eventuali spazi
                em_tools.xlsx_sheet_name.strip(),
                em_tools.xlsx_id_column.strip()
            )
            return {'FINISHED'} if result else {'CANCELLED'}
            
        return {'CANCELLED'}


# Lista delle classi da registrare
classes = [
    EM_OT_Import3DGISDatabase
]

def register():
    # Itera sulla lista per registrare le classi
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    # Itera sulla lista per cancellare la registrazione delle classi
    for cls in reversed(classes):  # Usa reversed per evitare problemi di dipendenze
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()