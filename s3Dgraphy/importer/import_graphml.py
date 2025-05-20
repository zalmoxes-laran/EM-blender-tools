# s3Dgraphy/import_graphml.py

import xml.etree.ElementTree as ET
from ..graph import Graph
from ..nodes.stratigraphic_node import (
    Node, StratigraphicNode, ContinuityNode)
from ..nodes.paradata_node import ParadataNode
from ..nodes.document_node import DocumentNode
from ..nodes.combiner_node import CombinerNode
from ..nodes.extractor_node import ExtractorNode
from ..nodes.property_node import PropertyNode
from ..nodes.epoch_node import EpochNode
from ..nodes.group_node import GroupNode, ParadataNodeGroup, ActivityNodeGroup, TimeBranchNodeGroup
from ..nodes.link_node import *
from ..edges.edge import Edge
from ..utils.utils import convert_shape2type, get_stratigraphic_node_class
import re
from ..edges.edge import EDGE_TYPES
import uuid

class GraphMLImporter:
    """
    Classe per importare grafi da file GraphML.

    Attributes:
        filepath (str): Percorso del file GraphML da importare.
        graph (Graph): Istanza della classe Graph in cui verrà caricato il grafo.
    """

    def __init__(self, filepath, graph=None):
        self.filepath = filepath
        self.graph = graph if graph is not None else Graph(graph_id="imported_graph")
        # Dizionario per la deduplicazione dei nodi documento
        self.document_nodes_map = {}  # nome documento -> node_id
        self.duplicate_id_map = {}    # id originale -> id deduplicated
        self.id_mapping = {}          # id originale -> uuid

    def extract_graph_id_and_code(self, tree):
        """
        Extracts the ID and code of the graph from the GraphML file.
        
        Args:
            tree: XML ElementTree of the GraphML file
            
        Returns:
            tuple: (graph_id, graph_code) where graph_id is the actual ID and graph_code is the
                human-readable code (e.g. VDL16). Both could be None if not found.
        """
        import uuid

        graph_id = None
        graph_code = None
        
        # Look for NodeLabel to find the graph header
        for nodelabel in tree.findall('.//{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}NodeLabel'):
            RowNodeLabelModelParameter = nodelabel.find('.//{http://www.yworks.com/xml/graphml}RowNodeLabelModelParameter')
            ColumnNodeLabelModelParameter = nodelabel.find('.//{http://www.yworks.com/xml/graphml}ColumnNodeLabelModelParameter')
            
            if RowNodeLabelModelParameter is None and ColumnNodeLabelModelParameter is None:
                try:
                    stringa_pulita, vocabolario = self.estrai_stringa_e_vocabolario(nodelabel.text)
                    
                    # Extract ID if present in vocabulary
                    if 'ID' in vocabolario:
                        graph_code = vocabolario['ID']
                        print(f"Found graph code from vocabulary: {graph_code}")
                    
                    # If there's a specific ID in the vocabulary, use it
                    if 'graph_id' in vocabolario:
                        graph_id = vocabolario['graph_id']
                        print(f"Found specific graph ID: {graph_id}")
                    
                    break
                except Exception as e:
                    print(f"Error extracting graph ID from node label: {e}")
        
        # If we didn't find a graph_code, use MISSINGCODE
        if not graph_code or graph_code == "site_id":
            graph_code = "MISSINGCODE"
            print(f"Using fallback graph code: {graph_code}")
        
        # If we don't have a graph_id, generate a UUID
        if not graph_id:
            graph_id = str(uuid.uuid4())
            print(f"Generated graph ID from UUID: {graph_id}")
        
        return graph_id, graph_code

    def parse(self):
        """
        Esegue il parsing del file GraphML e popola l'istanza di Graph.

        Returns:
            Graph: Istanza di Graph popolata con nodi e archi dal file GraphML.
        """
        import uuid
        
        tree = ET.parse(self.filepath)
        
        # Prima estrai il codice del grafo
        graph_id, graph_code = self.extract_graph_id_and_code(tree)
        
        # Se abbiamo trovato un codice, aggiungilo come attributo al grafo
        if graph_code:
            self.graph.attributes['graph_code'] = graph_code
            
        # Genera un ID univoco per il grafo se non esiste
        if not graph_id:
            graph_id = str(uuid.uuid4())
        
        # Imposta l'ID univoco nel grafo
        self.graph.graph_id = graph_id
        
        # Memorizza gli ID originali per la mappatura
        self.id_mapping = {}  # {original_id: uuid_id}
        
        # Prosegui con il parsing normale
        self.parse_nodes(tree)
        self.parse_edges(tree)

        # Aggiungi qui la nuova funzionalità per collegare PropertyNode dai ParadataNodeGroup
        # Impostare verbose=True per avere output dettagliati durante il debug
        stats = self.graph.connect_paradatagroup_propertynode_to_stratigraphic(verbose=True)
        if stats["connections_created"] > 0:
            print(f"\nCreati {stats['connections_created']} nuovi collegamenti diretti tra unità stratigrafiche e PropertyNode")


        self.connect_nodes_to_epochs()
        
        br_nodes = [n for n in self.graph.nodes if hasattr(n, 'node_type') and n.node_type == "BR"]
        print(f"\nTotal BR nodes included in the graph: {len(br_nodes)}")
        for node in br_nodes:
            print(f"  BR Node: UUID={node.node_id}, Original ID={node.attributes.get('original_id', 'Unknown')}, y_pos={node.attributes.get('y_pos', 'Unknown')}")

        # Verifica se i nodi BR esistono nel grafo
        if len(br_nodes) == 0:
            print("\nWARNING: No BR (continuity) nodes found in the graph!")
            print("Looking for nodes with _continuity in description...")
            
            for node in self.graph.nodes:
                if hasattr(node, 'description') and '_continuity' in node.description:
                    print(f"  Found node with _continuity in description: {node.node_id} (Type: {node.node_type if hasattr(node, 'node_type') else 'Unknown'})")
        
        return self.graph

    def parse_nodes(self, tree):
        """
        Esegue il parsing dei nodi dal file GraphML.
        """
        # Prima raccogli tutti gli ID dei nodi per identificare potenziali duplicati
        all_node_ids = {}  # {node_id: count}
        
        for node_element in tree.findall('.//{http://graphml.graphdrawing.org/xmlns}node'):
            node_id = self.getnode_id(node_element)
            all_node_ids[node_id] = all_node_ids.get(node_id, 0) + 1
        
        # Registra i nodi con più occorrenze
        duplicate_ids = {node_id for node_id, count in all_node_ids.items() if count > 1}
        if duplicate_ids:
            print(f"Attenzione: rilevati {len(duplicate_ids)} ID di nodi duplicati nel file GraphML:")
            for node_id in duplicate_ids:
                print(f"  - {node_id}")
        
        # Ora processa i nodi normalmente
        for node_element in tree.findall('.//{http://graphml.graphdrawing.org/xmlns}node'):
            node_type = self._check_node_type(node_element)
            if node_type == 'node_simple':
                self.process_node_element(node_element)
            elif node_type == 'node_swimlane':
                self.extract_epochs(node_element, self.graph)
            elif node_type == 'node_group':
                self.handle_group_node(node_element)

    def parse_edges(self, tree):
        """
        Esegue il parsing degli archi dal file GraphML.
        """
        alledges = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}edge')
        print(f"Found {len(alledges)} edges in GraphML")
        
        # Prima traccia tutti gli ID originali e le loro relazioni
        edge_original_mappings = []
        
        for edge in alledges:
            original_edge_id = str(edge.attrib['id'])
            original_source_id = str(edge.attrib['source'])
            original_target_id = str(edge.attrib['target'])
            edge_type = self.EM_extract_edge_type(edge)
            
            # Gestisci gli ID duplicati
            if original_source_id in self.duplicate_id_map:
                print(f"Remapping source: {original_source_id} -> {self.duplicate_id_map[original_source_id]}")
                original_source_id = self.duplicate_id_map[original_source_id]
            if original_target_id in self.duplicate_id_map:
                print(f"Remapping target: {original_target_id} -> {self.duplicate_id_map[original_target_id]}")
                original_target_id = self.duplicate_id_map[original_target_id]
            
            # Salva le mappature originali
            edge_original_mappings.append({
                'original_edge_id': original_edge_id,
                'original_source_id': original_source_id,
                'original_target_id': original_target_id,
                'edge_type': edge_type
            })
        
        # Ora crea gli archi usando gli UUID
        for mapping in edge_original_mappings:
            original_edge_id = mapping['original_edge_id']
            original_source_id = mapping['original_source_id'] 
            original_target_id = mapping['original_target_id']
            base_edge_type = mapping['edge_type']
            
            # Ottieni gli UUID corrispondenti
            source_uuid = self.id_mapping.get(original_source_id)
            target_uuid = self.id_mapping.get(original_target_id)
            
            if source_uuid is not None and target_uuid is not None:
                try:
                    # Genera un nuovo UUID per l'edge
                    edge_uuid = str(uuid.uuid4())
                    
                    # Get the source and target nodes for edge type enhancement
                    source_node = self.graph.find_node_by_id(source_uuid)
                    target_node = self.graph.find_node_by_id(target_uuid)
                    
                    # Enhance the edge type based on node types
                    enhanced_edge_type = self.enhance_edge_type(base_edge_type, source_node, target_node)
                    
                    # Crea l'arco con il tipo avanzato
                    edge = self.graph.add_edge(edge_uuid, source_uuid, target_uuid, enhanced_edge_type)
                    
                    # Aggiungi attributi di tracciamento
                    edge.attributes = edge.attributes if hasattr(edge, 'attributes') else {}
                    edge.attributes['original_edge_id'] = original_edge_id
                    edge.attributes['original_source_id'] = original_source_id
                    edge.attributes['original_target_id'] = original_target_id
                    
                except Exception as e:
                    print(f"Error adding edge {original_edge_id} ({edge_type}): {e}")
            else:
                # Report specifico sulla mappatura mancante
                if source_uuid is None:
                    print(f"Missing source UUID for edge {original_edge_id}: {original_source_id}")
                if target_uuid is None:
                    print(f"Missing target UUID for edge {original_edge_id}: {original_target_id}")
                
                print(f"Warning: Could not create edge {original_edge_id} - Source: {original_source_id} -> Target: {original_target_id}")
                
    def process_node_element(self, node_element):
        """
        Processa un elemento nodo dal file GraphML e lo aggiunge al grafo.

        Args:
            node_element (Element): Elemento nodo XML dal file GraphML.
        """

        node_counter = getattr(self, '_node_counter', 0)
        self._node_counter = node_counter + 1

        # Estrai l'ID originale
        original_id = self.getnode_id(node_element)
        
        # Se abbiamo già mappato questo ID originale, non creare un nuovo nodo
        if original_id in self.id_mapping:
            #print(f"Skipping already processed node with original ID: {original_id}")
            return

        # Genera un nuovo UUID per questo nodo
        uuid_id = str(uuid.uuid4())
        
        # Memorizza la mappatura per uso futuro
        self.id_mapping[original_id] = uuid_id

        if self.EM_check_node_us(node_element):
            # Creazione del nodo stratigrafico e aggiunta al grafo
            nodename, nodedescription, nodeurl, nodeshape, node_y_pos, fillcolor, borderstyle = self.EM_extract_node_name(node_element)
            
            stratigraphic_type = convert_shape2type(nodeshape, borderstyle)[0]
            node_class = get_stratigraphic_node_class(stratigraphic_type)  # Ottieni la classe usando la funzione
            stratigraphic_node = node_class(
                node_id=uuid_id,
                name=nodename,
                description=nodedescription
            )

            # Aggiungi attributi di tracciamento
            stratigraphic_node.attributes['original_id'] = original_id
            stratigraphic_node.attributes['graph_id'] = self.graph.graph_id
            
            # Prefissa il nome con il codice del grafo se disponibile
            graph_code = self.graph.attributes.get('graph_code')
            if graph_code:
                # Memorizza il nome originale prima di modificarlo
                stratigraphic_node.attributes['original_name'] = nodename
                # Creazione del nome prefissato
                stratigraphic_node.name = f"{graph_code}.{nodename}"

            # Aggiunta di runtime properties
            stratigraphic_node.attributes['shape'] = nodeshape
            stratigraphic_node.attributes['y_pos'] = float(node_y_pos)
            stratigraphic_node.attributes['fill_color'] = fillcolor
            stratigraphic_node.attributes['border_style'] = borderstyle

            #print(f"Node {self._node_counter}: {stratigraphic_node.node_id} (Original ID: {original_id}, Type: {stratigraphic_node.node_type})")

            self.graph.add_node(stratigraphic_node)

        elif self.EM_check_node_document(node_element):
            # Creazione del nodo documento e aggiunta al grafo
            nodename, node_id, nodedescription, nodeurl, _ = self.EM_extract_document_node(node_element)
            # Controlla se esiste già un documento con lo stesso nome

            if nodename in self.document_nodes_map:
                # Ottieni UUID del documento esistente
                existing_uuid = self.document_nodes_map[nodename]
                
                # Cerca il nodo documento esistente
                existing_doc = self.graph.find_node_by_id(existing_uuid)
                
                if existing_doc and hasattr(existing_doc, 'attributes'):
                    # Ottieni l'ID originale del documento esistente
                    existing_original_id = existing_doc.attributes.get('original_id')
                    
                    if existing_original_id:
                        # Mappa l'ID originale del nuovo documento all'ID originale del documento esistente
                        self.duplicate_id_map[original_id] = existing_original_id
                        print(f"Deduplicating document node: {nodename} (Original ID: {original_id} -> {existing_original_id})")
                    else:
                        # Non è stato possibile ottenere l'ID originale, usa l'UUID direttamente
                        self.duplicate_id_map[original_id] = existing_uuid
                        print(f"Deduplicating document node: {nodename} (Original ID: {original_id} -> UUID: {existing_uuid})")
                else:
                    # Non è stato possibile trovare il documento esistente, usa l'UUID direttamente
                    self.duplicate_id_map[original_id] = existing_uuid
                    print(f"Deduplicating document node: {nodename} (ID: {original_id} -> {existing_uuid})")
            else:
                # Crea nuovo documento
                document_node = DocumentNode(
                    node_id=uuid_id,
                    name=nodename,
                    description=nodedescription,
                    url=nodeurl
                )
                
                # Aggiungi attributi di tracciamento
                document_node.attributes['original_id'] = original_id
                document_node.attributes['graph_id'] = self.graph.graph_id
                
                # Prefissa il nome
                graph_code = self.graph.attributes.get('graph_code')
                if graph_code:
                    document_node.attributes['original_name'] = nodename
                    document_node.name = f"{graph_code}.{nodename}"
                
                # Aggiungi al grafo e memorizza UUID
                self.graph.add_node(document_node)
                self.document_nodes_map[nodename] = uuid_id
                # Se c'è un URL valido, crea un nodo Link
                if nodeurl and nodeurl.strip() != 'Empty':
                    link_node = self._create_link_node(document_node, nodeurl)

        elif self.EM_check_node_property(node_element):
            # Creazione del nodo proprietà e aggiunta al grafo
            nodename, node_id, nodedescription, nodeurl, _ = self.EM_extract_property_node(node_element)
            property_node = PropertyNode(
                node_id=uuid_id,
                name=nodename,
                description=nodedescription,
                value=nodeurl,
                data={},  # Popola 'data' se necessario
                url=nodeurl
            )

            # Per PropertyNode
            property_node.attributes['original_id'] = original_id
            property_node.attributes['graph_id'] = self.graph.graph_id

            # Prefissa il nome con il codice del grafo
            graph_code = self.graph.attributes.get('graph_code')
            if graph_code:
                property_node.attributes['original_name'] = nodename
                property_node.name = f"{graph_code}.{nodename}"

            self.graph.add_node(property_node)

        elif self.EM_check_node_extractor(node_element):
            # Creazione del nodo extractor e aggiunta al grafo
            nodename, node_id, nodedescription, nodeurl, _ = self.EM_extract_extractor_node(node_element)
            extractor_node = ExtractorNode(
                node_id=uuid_id,
                name=nodename,
                description=nodedescription,
                source=nodeurl
            )
            # Per extractor_node
            extractor_node.attributes['original_id'] = original_id
            extractor_node.attributes['graph_id'] = self.graph.graph_id

            # Prefissa il nome con il codice del grafo
            graph_code = self.graph.attributes.get('graph_code')
            if graph_code:
                extractor_node.attributes['original_name'] = nodename
                extractor_node.name = f"{graph_code}.{nodename}"

            self.graph.add_node(extractor_node)

            # Se c'è un URL valido, crea un nodo Link
            if nodeurl and nodeurl.strip() != 'Empty':
                link_node = self._create_link_node(extractor_node, nodeurl)


        elif self.EM_check_node_combiner(node_element):
            # Creazione del nodo combiner e aggiunta al grafo
            nodename, node_id, nodedescription, nodeurl, _ = self.EM_extract_combiner_node(node_element)
            combiner_node = CombinerNode(
                node_id=uuid_id,
                name=nodename,
                description=nodedescription,
                sources=[nodeurl]
            )

            # Per combiner_node
            combiner_node.attributes['original_id'] = original_id
            combiner_node.attributes['graph_id'] = self.graph.graph_id

            # Prefissa il nome con il codice del grafo
            graph_code = self.graph.attributes.get('graph_code')
            if graph_code:
                combiner_node.attributes['original_name'] = nodename
                combiner_node.name = f"{graph_code}.{nodename}"

            self.graph.add_node(combiner_node)

        elif self.EM_check_node_continuity(node_element):
            # Creazione del nodo continuity e aggiunta al grafo
            nodedescription, node_y_pos, node_id = self.EM_extract_continuity(node_element)
            continuity_node = ContinuityNode(
                node_id=uuid_id,
                name="continuity_node",
                description=nodedescription
            )
            
            # Aggiungi attributi di tracciamento
            continuity_node.attributes['original_id'] = original_id
            continuity_node.attributes['graph_id'] = self.graph.graph_id
            continuity_node.attributes['y_pos'] = float(node_y_pos)
            
            #print(f"Adding continuity node to graph: {continuity_node.node_id} (Original ID: {original_id})")
            self.graph.add_node(continuity_node)

        else:
            # Creazione di un nodo generico
            node_id = self.getnode_id(node_element)
            node_name = self.EM_extract_generic_node_name(node_element)
            generic_node = Node(
                node_id=uuid_id,
                name=node_name,
                #node_type="Generic",
                description=""
            )
            self.graph.add_node(generic_node)



    def _create_link_node(self, source_node, url):
        """
        Creates a Link node for a resource.

        Args:
            source_node (Node): The source node with which the link is associated
            url (str): The URL or path of the resource

        Returns:
            LinkNode: The Link node created
        """
        from ..nodes.link_node import LinkNode
        
        link_node_id = f"{source_node.node_id}_link"
        
        # Verifica se il nodo Link esiste già
        existing_link_node = self.graph.find_node_by_id(link_node_id)
        if existing_link_node:
            return existing_link_node
        
        # Se non esiste, crealo
        link_node = LinkNode(
            node_id=link_node_id,
            name=f"Link to {source_node.name}",
            description=f"Link to {source_node.description}" if source_node.description else "",
            url=url
        )
        
        self.graph.add_node(link_node)
        
        # Crea l'edge solo se non esiste già
        edge_id = f"{source_node.node_id}_has_linked_resource_{link_node_id}"
        if not self.graph.find_edge_by_id(edge_id):
            self.graph.add_edge(
                edge_id=edge_id,
                edge_source=source_node.node_id,
                edge_target=link_node.node_id,
                edge_type="has_linked_resource"
            )
        
        return link_node
        
    def handle_group_node(self, node_element):
        """
        Gestisce un nodo di tipo gruppo dal file GraphML.

        Args:
            node_element (Element): Elemento nodo XML dal file GraphML.
        """
        
        # Estrarre l'ID originale, il nome e la descrizione del gruppo
        original_id = self.getnode_id(node_element)
        uuid_id = str(uuid.uuid4())
        self.id_mapping[original_id] = uuid_id        
        
        # Estrarre l'ID, il nome e la descrizione del gruppo
        group_name = self.EM_extract_group_node_name(node_element)
        group_description = self.EM_extract_group_node_description(node_element)
        group_background_color = self.EM_extract_group_node_background_color(node_element)
        group_y_pos = self.EM_extract_group_node_y_pos(node_element)

        # Determinare il tipo di nodo gruppo basandoci sul background color
        group_node_type = self.determine_group_node_type_by_color(group_background_color)

        if group_node_type == 'ActivityNodeGroup':
            group_node = ActivityNodeGroup(
                node_id=uuid_id,
                name=group_name,
                description=group_description,
                y_pos=group_y_pos
            )
        elif group_node_type == 'ParadataNodeGroup':
            group_node = ParadataNodeGroup(
                node_id=uuid_id,
                name=group_name,
                description=group_description,
                y_pos=group_y_pos
            )
        elif group_node_type == 'TimeBranchNodeGroup':
            group_node = TimeBranchNodeGroup(
                node_id=uuid_id,
                name=group_name,
                description=group_description,
                y_pos=group_y_pos
            )
        else:
            group_node = GroupNode(
                node_id=uuid_id,
                name=group_name,
                description=group_description,
                y_pos=group_y_pos
            )

        # Aggiungi attributi di tracciamento
        group_node.attributes['original_id'] = original_id
        group_node.attributes['graph_id'] = self.graph.graph_id

        # Aggiungere il nodo gruppo al grafo
        self.graph.add_node(group_node)

        # Processare i nodi contenuti nel gruppo
        subgraph = node_element.find('{http://graphml.graphdrawing.org/xmlns}graph')
        if subgraph is not None:
            subnodes = subgraph.findall('{http://graphml.graphdrawing.org/xmlns}node')
            for subnode in subnodes:
                subnode_original_id = self.getnode_id(subnode)
                subnode_type = self._check_node_type(subnode)
                if subnode_type == 'node_simple':
                    # Processare e aggiungere il nodo al grafo
                    self.process_node_element(subnode)
                elif subnode_type == 'node_group':
                    # Gestire ricorsivamente il sottogruppo
                    self.handle_group_node(subnode)
                elif subnode_type == 'node_swimlane':
                    # Gestire i nodi EpochNode se necessario
                    self.extract_epochs(subnode, self.graph)

                # Qui devi usare la mappatura UUID per creare l'arco
                if subnode_original_id in self.id_mapping:
                    subnode_uuid = self.id_mapping[subnode_original_id]
                    
                    # Creare l'arco appropriato in base al tipo di gruppo
                    edge_type = "generic_connection"  # Fallback sicuro
                    
                    if group_node_type == "ActivityNodeGroup":
                        edge_type = "is_in_activity"
                        edge_id_prefix = "is_in_activity"
                    elif group_node_type == "ParadataNodeGroup":
                        edge_type = "is_in_paradata_nodegroup"
                        edge_id_prefix = "is_in_paradata_nodegroup"
                    elif group_node_type == "TimeBranchNodeGroup":
                        edge_type = "is_in_timebranch"
                        edge_id_prefix = "is_in_timebranch"
                    else:
                        # Per altri tipi di gruppo non specificati
                        edge_id_prefix = "grouped_in"
                    
                    # Crea l'edge con gli UUID
                    edge_id = f"{subnode_uuid}_{edge_id_prefix}_{uuid_id}"
                    try:
                        self.graph.add_edge(
                            edge_id=edge_id,
                            edge_source=subnode_uuid,  # Usa UUID
                            edge_target=uuid_id,      # Usa UUID
                            edge_type=edge_type
                        )
                    except Exception as e:
                        print(f"Error creating edge from {subnode_uuid} to {uuid_id}: {e}")

    def extract_epochs(self, node_element, graph):
        """
        Estrae gli EpochNode dal nodo swimlane nel file GraphML.
        """
        # Mappa per tenere traccia delle righe per ID
        row_id_to_index = {}
        epoch_nodes = []
        
        geometry = node_element.find('.//{http://www.yworks.com/xml/graphml}Geometry')
        y_start = float(geometry.attrib['y'])

        y_min = y_start
        y_max = y_start

        # Crea prima tutti i nodi epoca
        print(f"Creazione nodi epoca iniziali...")
        rows = node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}Table/{http://www.yworks.com/xml/graphml}Rows/{http://www.yworks.com/xml/graphml}Row')
        for i, row in enumerate(rows):
            original_id = row.attrib['id']
            uuid_id = str(uuid.uuid4())
            self.id_mapping[original_id] = uuid_id
            row_id_to_index[original_id] = i
            
            h_row = float(row.attrib['height'])
            y_min = y_max
            y_max += h_row

            epoch_node = EpochNode(
                node_id=uuid_id,
                name=f"temp_{i}",  # Nome temporaneo con indice per debug
                start_time=-10000,
                end_time=10000
            )
        
            epoch_node.attributes['original_id'] = original_id
            epoch_node.min_y = y_min
            epoch_node.max_y = y_max
            self.graph.add_node(epoch_node)
            epoch_nodes.append(epoch_node)
            print(f"Creato nodo epoca {i}: ID orig: {original_id}, UUID: {uuid_id}")

        # Aggiorna i nomi e i colori delle epoche
        print(f"Aggiornamento nomi epoche...")
        for nodelabel in node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}NodeLabel'):
            try:
                row_param = nodelabel.find('.//{http://www.yworks.com/xml/graphml}RowNodeLabelModelParameter')
                if row_param is not None:
                    label_text = nodelabel.text
                    original_id = str(row_param.attrib['id'])
                    
                    # Ottieni il colore se presente
                    e_color = nodelabel.attrib.get('backgroundColor', "#BCBCBC")
                    
                    print(f"Processando etichetta con ID orig: {original_id}")
                    
                    # Cerca l'UUID corrispondente
                    uuid_id = self.id_mapping.get(original_id)
                    if not uuid_id:
                        print(f"WARNING: UUID non trovato per ID originale {original_id}")
                        continue
                    
                    # Cerca il nodo epoca usando l'UUID
                    epoch_node = self.graph.find_node_by_id(uuid_id)
                    if not epoch_node:
                        # Fallback: cerca usando l'indice se disponibile
                        row_index = row_id_to_index.get(original_id)
                        if row_index is not None and row_index < len(epoch_nodes):
                            epoch_node = epoch_nodes[row_index]
                            print(f"Trovato epoch_node usando indice di fallback: {row_index}")
                        else:
                            print(f"WARNING: Nodo epoca non trovato per UUID {uuid_id} o indice {row_index}")
                            continue
                    
                    # Aggiorna le proprietà del nodo epoca
                    try:
                        stringa_pulita, vocabolario = self.estrai_stringa_e_vocabolario(label_text)
                        epoch_node.set_name(stringa_pulita)
                        
                        # Gestisci i valori 'XX' per start_time
                        start_value = vocabolario.get('start', -10000)
                        if isinstance(start_value, str) and start_value.lower() in ['xx', 'x']:
                            start_value = 10000
                            print(f"Trovato valore placeholder 'XX' per start_time in epoca '{stringa_pulita}', usando valore 10000")
                        
                        # Gestisci i valori 'XX' per end_time
                        end_value = vocabolario.get('end', 10000)
                        if isinstance(end_value, str) and end_value.lower() in ['xx', 'x']:
                            end_value = 10000
                            print(f"Trovato valore placeholder 'XX' per end_time in epoca '{stringa_pulita}', usando valore 10000")
                        
                        epoch_node.set_start_time(start_value)
                        epoch_node.set_end_time(end_value)
                        print(f"Aggiornato nodo epoca: '{stringa_pulita}' (start={start_value}, end={end_value})")
                    except Exception as e:
                        epoch_node.set_name(label_text)
                        print(f"Fallback al nome completo: {label_text}: {str(e)}")                    
                    epoch_node.set_color(e_color)
                    print(f"Impostato colore: {e_color}")
            except Exception as e:
                print(f"ERROR durante l'elaborazione dell'etichetta: {e}")

    def process_general_data(self, nodelabel, graph):
        """
        Processa i dati generali dal nodelabel e li aggiunge al grafo.
        """
        print(f"\nProcessing general data from GraphML header:")
        print(f"Raw nodelabel text: '{nodelabel.text}'")
        
        stringa_pulita, vocabolario = self.estrai_stringa_e_vocabolario(nodelabel.text)
        print(f"Stringa pulita: '{stringa_pulita}'")
        print(f"Vocabolario estratto: {vocabolario}")
        
        try:
            # Imposta il nome e l'ID del grafo
            if 'ID' in vocabolario:
                print(f"Found ID: {vocabolario['ID']}")
                graph.graph_id = vocabolario['ID']
            else:
                # Fallback al nome del file
                import os
                graph.graph_id = os.path.splitext(os.path.basename(self.filepath))[0]
                print(f"Using filename as graph ID: {graph.graph_id}")

            graph.name = {'default': stringa_pulita}
            print(f"Set graph ID to: {graph.graph_id}")
            print(f"Set graph name to: {graph.name}")
                
            # Crea il nodo grafo stesso
            from ..nodes.base_node import Node
            graph_node = Node(
                node_id=graph.graph_id,
                name=stringa_pulita
            )
            graph.add_node(graph_node)
                
            # Crea e connetti il nodo autore se presente un ORCID
            if 'ORCID' in vocabolario:
                print(f"Found ORCID: {vocabolario['ORCID']}")
                from ..nodes.author_node import AuthorNode
                
                # Componi il nome completo per il display
                author_name = vocabolario.get('author_name', '')
                author_surname = vocabolario.get('author_surname', '')
                display_name = f"{author_name} {author_surname}".strip()
                
                # Crea l'ID dell'autore
                author_id = f"author_{vocabolario['ORCID']}"
                
                # Crea il nodo autore usando solo i parametri accettati dal costruttore
                author_node = AuthorNode(
                    node_id=author_id,
                    orcid=vocabolario['ORCID'],
                    name=author_name,
                    surname=author_surname
                )
                print(f"Created author node with ID: {author_id}")
                
                # Aggiungi il nodo al grafo
                graph.add_node(author_node)
                
                # Aggiungi l'autore alla lista degli autori nei dati del grafo
                if 'authors' not in graph.data:
                    graph.data['authors'] = []
                if author_id not in graph.data['authors']:
                    graph.data['authors'].append(author_id)
                
                # Crea l'edge tra autore e grafo
                edge_id = f"authorship_{author_id}"
                graph.add_edge(
                    edge_id=edge_id,
                    edge_source=author_id,
                    edge_target=graph.graph_id,
                    edge_type="has_author"
                )
                print(f"Added author node and edge: {author_id}")
                    
            # Aggiorna la descrizione del grafo
            if 'description' in vocabolario:
                print(f"Found description: {vocabolario['description']}")
                graph.description = {'default': vocabolario['description']}
                    
            # Gestisce la data di embargo se presente
            if 'embargo' in vocabolario:
                print(f"Found embargo: {vocabolario['embargo']}")
                graph.data['embargo_until'] = vocabolario['embargo']
                    
            # Gestisce la licenza se presente
            if 'license' in vocabolario:
                print(f"Found license: {vocabolario['license']}")
                graph.data['license'] = vocabolario['license']

            print(f"\nGraph data after processing:")
            print(f"ID: {graph.graph_id}")
            print(f"Name: {graph.name}")
            print(f"Description: {graph.description}")
            print(f"Data: {graph.data}")
            print(f"Authors: {graph.data.get('authors', [])}")
            
        except Exception as e:
            print(f"Error processing general data: {e}")
            import traceback
            traceback.print_exc()




    def connect_nodes_to_epochs(self):
        """
        Assegna le epoche ai nodi nel grafo in base alla posizione Y e gestisce i nodi continuity.
        """
        print("\n=== Connecting nodes to epochs ===")
        
        # Verifica se ci sono nodi BR (continuity)
        br_nodes = [n for n in self.graph.nodes if hasattr(n, 'node_type') and n.node_type == "BR"]
        print(f"Found {len(br_nodes)} BR (continuity) nodes for connection process")
        
        # Esegui una ricerca manuale nelle classi dei nodi per verificare che ContinuityNode esista e sia correttamente definito
        
        print(f"ContinuityNode class node_type: {ContinuityNode.node_type}")

        # Definisce i tipi di nodi stratigrafici fisici che possono estendersi fino all'ultima epoca
        list_of_physical_stratigraphic_nodes = ["US", "serSU"]

        # Crea indici per accesso rapido
        epochs = [n for n in self.graph.nodes if hasattr(n, 'node_type') and n.node_type == "epoch"]

        print(f"Numero totale di epoche trovate: {len(epochs)}")
        if len(epochs) == 0:
            print("AVVISO: Nessuna epoca trovata nel grafo")
            return

        # Crea un dizionario inverso per mappare UUID a ID originali
        reverse_mapping = {}
        for orig_id, uuid in self.id_mapping.items():
            reverse_mapping[uuid] = orig_id

        print(f"Numero totale di epoche trovate: {len(epochs)}")
        if len(epochs) == 0:
            print("AVVISO: Nessuna epoca trovata nel grafo")
            return

        # Debug info
        print(f"Connect nodes to epochs: {len(self.graph.nodes)} nodes, {len(epochs)} epochs")
        
        # Usa una mappatura diretta per trovare i nodi continuity collegati a nodi stratigrafici
        continuity_connections = {}  # node_id -> continuity_node

        # Prima identifica le connessioni continuity dagli archi
        for edge in self.graph.edges:
            # Usa direttamente source e target degli edge
            source_id = edge.edge_source
            target_id = edge.edge_target
            
            # Verifica se il source è un nodo continuity
            source_node = self.graph.find_node_by_id(source_id)
            if source_node and hasattr(source_node, 'node_type') and source_node.node_type == "BR":
                continuity_connections[target_id] = source_node
                print(f"Found continuity connection: {source_node.node_id} -> {target_id}")
        
        # Per ogni nodo stratigrafico
        for node in self.graph.nodes:
            if not hasattr(node, 'attributes') or not 'y_pos' in node.attributes:
                continue
                
            connected_continuity_node = None

            # Cerca il nodo continuity collegato direttamente con l'UUID
            connected_continuity_node = continuity_connections.get(node.node_id)
            
            if connected_continuity_node:
                print(f"Found continuity for node {node.name} ({node.node_id}): {connected_continuity_node.node_id}")
            
            # Connetti alle epoche appropriate
            for epoch in epochs:
                if epoch.min_y < node.attributes['y_pos'] < epoch.max_y:
                    edge_id = f"{node.node_id}_{epoch.node_id}_first_epoch"
                    try:
                        self.graph.add_edge(edge_id, node.node_id, epoch.node_id, "has_first_epoch")
                        #print(f"Connected node {node.name} to epoch {epoch.name} (first)")
                    except Exception as e:
                        print(f"Error connecting node {node.name} to epoch {epoch.name} (first): {e}")
                    
                elif connected_continuity_node and hasattr(connected_continuity_node, 'attributes') and 'y_pos' in connected_continuity_node.attributes:
                    y_pos = node.attributes['y_pos']
                    continuity_y_pos = connected_continuity_node.attributes['y_pos']
                    print(f"Node {node.name} (y_pos: {y_pos}) connected to continuity node {connected_continuity_node.node_id} (y_pos: {continuity_y_pos})")

                    if epoch.max_y < y_pos and epoch.max_y > continuity_y_pos:
                        try:
                            edge_id = f"{node.node_id}_{epoch.node_id}_survive"
                            self.graph.add_edge(edge_id, node.node_id, epoch.node_id, "survive_in_epoch")
                            #print(f"Connected node {node.name} to epoch {epoch.name} yeee (survive with continuity)")
                        except Exception as e:
                            print(f"Error connecting node {node.name} to epoch {epoch.name} (survive): {e}")
                    
                elif hasattr(node, 'node_type') and node.node_type in list_of_physical_stratigraphic_nodes:
                    # L'epoca è più recente del nodo (cioè il max_y dell'epoca è più basso del y_pos del nodo)
                    if epoch.max_y < node.attributes['y_pos']:
                        edge_id = f"{node.node_id}_{epoch.node_id}_survive"
                        try:
                            self.graph.add_edge(edge_id, node.node_id, epoch.node_id, "survive_in_epoch")
                            #print(f"Connected node {node.name} to epoch {epoch.name} (physical)")
                        except Exception as e:
                            print(f"Error connecting node {node.name} to epoch {epoch.name} (physical): {e}")

    # Funzioni di supporto per l'estrazione dei dati dai nodi

    def EM_extract_generic_node_name(self, node_element):
        node_name = ''
        data_d6 = node_element.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d6"]')
        if data_d6 is not None:
            node_label = data_d6.find('.//{http://www.yworks.com/xml/graphml}NodeLabel')
            if node_label is not None:
                node_name = self._check_if_empty(node_label.text)
        return node_name

    def EM_extract_group_node_name(self, node_element):
        group_name = ''
        data_d6 = node_element.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d6"]')
        if data_d6 is not None:
            node_label = data_d6.find('.//{http://www.yworks.com/xml/graphml}NodeLabel')
            if node_label is not None:
                group_name = self._check_if_empty(node_label.text)
        return group_name

    def EM_extract_group_node_description(self, node_element):
        group_description = ''
        data_d5 = node_element.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d5"]')
        if data_d5 is not None and data_d5.text is not None:
            group_description = self.clean_comments(data_d5.text)
        return group_description

    def EM_extract_group_node_background_color(self, node_element):
        background_color = None
        data_d6 = node_element.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d6"]')
        if data_d6 is not None:
            node_label = data_d6.find('.//{http://www.yworks.com/xml/graphml}NodeLabel')
            if node_label is not None:
                background_color = node_label.attrib.get('backgroundColor')
        return background_color

    def EM_extract_group_node_y_pos(self, node_element):
        y_pos = 0.0
        data_d6 = node_element.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d6"]')
        if data_d6 is not None:
            geometry = data_d6.find('.//{http://www.yworks.com/xml/graphml}Geometry')
            if geometry is not None:
                y_pos = float(geometry.attrib.get('y', 0.0))
        return y_pos

    def determine_group_node_type_by_color(self, background_color):
        if background_color == '#CCFFFF':
            return 'ActivityNodeGroup'
        elif background_color == '#FFCC99':
            return 'ParadataNodeGroup'
        elif background_color == '#99CC00':
            return 'TimeBranchNodeGroup'
        else:
            return 'GroupNode'

    # Funzioni per estrarre e verificare i vari tipi di nodi

    def EM_check_node_us(self, node_element):
        US_nodes_list = ['rectangle', 'parallelogram', 'ellipse', 'hexagon', 'octagon', 'roundrectangle']
        nodename, _, _, nodeshape, _, _, _ = self.EM_extract_node_name(node_element)
        return nodeshape in US_nodes_list

    def EM_extract_node_name(self, node_element):
        is_d4 = False
        is_d5 = False
        node_y_pos = None
        nodeshape = None
        nodeurl = None
        nodedescription = None
        nodename = None
        fillcolor = None
        borderstyle = None

        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            attrib = subnode.attrib
            if attrib.get('key') == 'd4':
                is_d4 = True
                nodeurl = subnode.text
            if attrib.get('key') == 'd5':
                is_d5 = True
                if not subnode.text:
                    nodedescription = ''
                else:
                    nodedescription = self.clean_comments(subnode.text)
            if attrib.get('key') == 'd6':
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = self._check_if_empty(USname.text)
                    #print(f'Sto provando ad estrarre il colore alla US con nome {nodename}')
                for fill_color in subnode.findall('.//{http://www.yworks.com/xml/graphml}Fill'):
                    fillcolor = fill_color.attrib['color']
                for border_style in subnode.findall('.//{http://www.yworks.com/xml/graphml}BorderStyle'):
                    borderstyle = border_style.attrib['color']
                for USshape in subnode.findall('.//{http://www.yworks.com/xml/graphml}Shape'):
                    nodeshape = USshape.attrib['type']
                for geometry in subnode.findall('.//{http://www.yworks.com/xml/graphml}Geometry'):
                    node_y_pos = geometry.attrib['y']
        if not is_d4:
            nodeurl = ''
        if not is_d5:
            nodedescription = ''
        return nodename, nodedescription, nodeurl, nodeshape, node_y_pos, fillcolor, borderstyle

    def EM_check_node_document(self, node_element):
        try:
            _, _, _, _, subnode_is_document = self.EM_extract_document_node(node_element)
        except TypeError:
            subnode_is_document = False
        return subnode_is_document

    def EM_extract_document_node(self, node_element):
        is_d4 = False
        is_d5 = False
        node_id = node_element.attrib['id']
        nodename = ""
        node_description = ""
        nodeurl = ""
        subnode_is_document = False

        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            if subnode.attrib.get('key') == 'd6':
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = USname.text
                for nodetype in subnode.findall('.//{http://www.yworks.com/xml/graphml}Property'):
                    if nodetype.attrib.get('name') == 'com.yworks.bpmn.dataObjectType' and nodetype.attrib.get('value') == 'DATA_OBJECT_TYPE_PLAIN':
                        subnode_is_document = True

        if subnode_is_document:
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                if subnode.attrib.get('key') == 'd4':
                    if subnode.text is not None:
                        is_d4 = True
                        nodeurl = subnode.text
                if subnode.attrib.get('key') == 'd5':
                    is_d5 = True
                    node_description = self.clean_comments(subnode.text)

        if not is_d4:
            nodeurl = ''
        if not is_d5:
            node_description = ''
        return nodename, node_id, node_description, nodeurl, subnode_is_document

    def EM_check_node_property(self, node_element):
        try:
            _, _, _, _, subnode_is_property = self.EM_extract_property_node(node_element)
        except UnboundLocalError:
            subnode_is_property = False
        return subnode_is_property

    def EM_extract_property_node(self, node_element):
        is_d4 = False
        is_d5 = False
        node_id = node_element.attrib['id']
        subnode_is_property = False
        nodeurl = ""
        nodename = ""
        node_description = ""

        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            if subnode.attrib.get('key') == 'd6':
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = self._check_if_empty(USname.text)
                for nodetype in subnode.findall('.//{http://www.yworks.com/xml/graphml}Property'):
                    if nodetype.attrib.get('name') == 'com.yworks.bpmn.type' and nodetype.attrib.get('value') == 'ARTIFACT_TYPE_ANNOTATION':
                        subnode_is_property = True

        if subnode_is_property:
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                if subnode.attrib.get('key') == 'd4':
                    if subnode.text is not None:
                        is_d4 = True
                        nodeurl = subnode.text
                if subnode.attrib.get('key') == 'd5':
                    is_d5 = True
                    node_description = self.clean_comments(subnode.text)

        if not is_d4:
            nodeurl = ''
        if not is_d5:
            node_description = ''
        return nodename, node_id, node_description, nodeurl, subnode_is_property

    def EM_check_node_extractor(self, node_element):
        try:
            _, _, _, _, subnode_is_extractor = self.EM_extract_extractor_node(node_element)
        except TypeError:
            subnode_is_extractor = False
        return subnode_is_extractor

    def EM_extract_extractor_node(self, node_element):
        is_d4 = False
        is_d5 = False
        node_id = node_element.attrib['id']
        subnode_is_extractor = False
        nodeurl = ""
        nodename = ""
        node_description = ""

        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            if subnode.attrib.get('key') == 'd6':
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = self._check_if_empty(USname.text)
                if nodename.startswith("D.") and not self.graph.find_node_by_name(nodename):
                    subnode_is_extractor = True

        if subnode_is_extractor:
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                if subnode.attrib.get('key') == 'd4':
                    if subnode.text is not None:
                        is_d4 = True
                        nodeurl = self._check_if_empty(subnode.text)
                if subnode.attrib.get('key') == 'd5':
                    is_d5 = True
                    node_description = self.clean_comments(self._check_if_empty(subnode.text))

        if not is_d4:
            nodeurl = ''
        if not is_d5:
            node_description = ''
        return nodename, node_id, node_description, nodeurl, subnode_is_extractor

    def EM_check_node_combiner(self, node_element):
        try:
            _, _, _, _, subnode_is_combiner = self.EM_extract_combiner_node(node_element)
        except TypeError:
            subnode_is_combiner = False
        return subnode_is_combiner

    def EM_extract_combiner_node(self, node_element):
        is_d4 = False
        is_d5 = False
        node_id = node_element.attrib['id']
        subnode_is_combiner = False
        nodeurl = ""
        nodename = ""
        node_description = ""

        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            if subnode.attrib.get('key') == 'd6':
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = self._check_if_empty(USname.text)
                if nodename.startswith("C."):
                    subnode_is_combiner = True

        if subnode_is_combiner:
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                if subnode.attrib.get('key') == 'd4':
                    if subnode.text is not None:
                        is_d4 = True
                        nodeurl = self._check_if_empty(subnode.text)
                if subnode.attrib.get('key') == 'd5':
                    is_d5 = True
                    node_description = self.clean_comments(self._check_if_empty(subnode.text))

        if not is_d4:
            nodeurl = ''
        if not is_d5:
            node_description = ''
        return nodename, node_id, node_description, nodeurl, subnode_is_combiner

    def EM_check_node_continuity(self, node_element):
        """
        Verifica se un nodo è un nodo di continuità (BR).
        
        Args:
            node_element: Elemento XML del nodo
            
        Returns:
            bool: True se il nodo è di tipo continuity
        """
        # Cerca nei dati del nodo
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            if subnode.attrib.get('key') == 'd5':
                # Verifica se il testo è "_continuity"
                if subnode.text and "_continuity" in subnode.text:
                    print(f"Found continuity node: {node_element.attrib['id']}")
                    return True
                    
        # Verifica se è un SVGNode (alternativa)
        svg_node = node_element.find('.//{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}SVGNode')
        if svg_node is not None:
            # Cerca di nuovo nei dati per confermare se è un nodo continuity
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                if subnode.attrib.get('key') == 'd5' and subnode.text:
                    if "_continuity" in subnode.text:
                        print(f"Found SVG continuity node: {node_element.attrib['id']}")
                        return True
                        
        return False

    def EM_extract_continuity(self, node_element):
        """
        Estrae informazioni da un nodo continuity.
        
        Args:
            node_element: Elemento XML del nodo
            
        Returns:
            tuple: (descrizione, posizione y, id)
        """
        is_d5 = False
        node_y_pos = 0.0
        nodedescription = None
        node_id = node_element.attrib['id']

        # Estrai descrizione dal campo d5
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            if subnode.attrib.get('key') == 'd5':
                is_d5 = True
                nodedescription = subnode.text
            
            # Per SVGNode, estrai la posizione y
            geometry = subnode.find('.//{http://www.yworks.com/xml/graphml}SVGNode/{http://www.yworks.com/xml/graphml}Geometry')
            if geometry is not None:
                y_str = geometry.attrib.get('y', '0.0')
                try:
                    node_y_pos = float(y_str)
                    print(f"Extracted y position from SVGNode: {node_y_pos}")
                except (ValueError, TypeError):
                    print(f"Error converting y position to float: {y_str}")
                    node_y_pos = 0.0
            
            # Fallback per i nodi non SVG
            if subnode.attrib.get('key') == 'd6':
                geometry = subnode.find('.//{http://www.yworks.com/xml/graphml}Geometry')
                if geometry is not None:
                    y_str = geometry.attrib.get('y', '0.0')
                    try:
                        node_y_pos = float(y_str)
                    except (ValueError, TypeError):
                        node_y_pos = 0.0
        
        if not is_d5:
            nodedescription = ''
            
        if nodedescription == "_continuity":
            print(f"Extracting continuity node: ID={node_id}, y_pos={node_y_pos}")
            
        return nodedescription, node_y_pos, node_id

    def enhance_edge_type(self, edge_type, source_node, target_node):
        """
        Enhances the edge type based on the types of the connected nodes.
        
        Args:
            edge_type (str): The basic edge type from GraphML style.
            source_node (Node): The source node.
            target_node (Node): The target node.
            
        Returns:
            str: The enhanced edge type.
        """
        if not source_node or not target_node:
            return edge_type
            
        # Definizione dei tipi stratigrafici
        stratigraphic_types = ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 
                            'serUSVn', 'serUSVs', 'TSU', 'SE', 'BR', 'unknown']

        source_type = source_node.node_type if hasattr(source_node, 'node_type') else ""
        target_type = target_node.node_type if hasattr(target_node, 'node_type') else ""
        
        print(f"Enhancing edge type {edge_type}: {source_type} -> {target_type}")

        # Logica per has_data_provenance
        if edge_type == "has_data_provenance":
            # Se il source è un nodo stratigrafico e il target è una property
            if source_type in stratigraphic_types and target_type == "property":
                edge_type = "has_property"
                print(f"Enhanced to has_property: {source_type} -> PropertyNode")

            # Unità stratigrafica collegata a ParadataNodeGroup
            elif source_type in stratigraphic_types and target_type == "ParadataNodeGroup":
                edge_type = "has_paradata_nodegroup"
                print(f"Enhanced to has_paradata_nodegroup: {source_type} -> ParadataNodeGroup")
            
            # ParadataNodeGroup collegato a unità stratigrafica (direzione invertita)
            elif source_type == "ParadataNodeGroup" and target_type in stratigraphic_types:
                edge_type = "has_paradata_nodegroup"
                print(f"Enhanced to has_paradata_nodegroup (direzione invertita): ParadataNodeGroup -> {target_type}")

            # ExtractorNode -> DocumentNode
            elif (isinstance(source_node, ExtractorNode) and 
                isinstance(target_node, DocumentNode)):
                edge_type = "extracted_from"
                print(f"Enhanced to extracted_from: ExtractorNode -> DocumentNode")
                
            # CombinerNode -> ExtractorNode
            elif (isinstance(source_node, CombinerNode) and 
                isinstance(target_node, ExtractorNode)):
                edge_type = "combines"
                print(f"Enhanced to combines: CombinerNode -> ExtractorNode")
        
        # Post-processing per generic_connection
        elif edge_type == "generic_connection":
            # Nodi ParadataNode (e sottoclassi) collegati a ParadataNodeGroup
            if (isinstance(source_node, (DocumentNode, ExtractorNode, CombinerNode, ParadataNode)) and 
                target_type == "ParadataNodeGroup"):
                edge_type = "is_in_paradata_nodegroup"
                print(f"Enhanced to is_in_paradata_nodegroup: {source_type} -> ParadataNodeGroup")
            
            # ParadataNodeGroup collegato a ActivityNodeGroup
            elif source_type == "ParadataNodeGroup" and target_type == "ActivityNodeGroup":
                edge_type = "has_paradata_nodegroup"
                print(f"Enhanced to has_paradata_nodegroup: ParadataNodeGroup -> ActivityNodeGroup")
            
            # Puoi aggiungere altre regole specifiche qui
        
        return edge_type

    def EM_extract_edge_type(self, edge):
        """
        Extracts the basic semantic type of the edge from the GraphML line style.
        
        Args:
            edge_element (Element): XML element for the edge.

        Returns:
            str: The edge type representing the semantic relationship.
        """
        edge_type = "generic_connection"  # Default edge type
        data_element = edge.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d10"]')

        if data_element is not None:
            # Extract graphical line style and map it to a semantic relationship
            line_style = data_element.find('.//{http://www.yworks.com/xml/graphml}LineStyle')
            if line_style is not None:
                style_type = line_style.attrib.get("type")
                # Map each graphical style to its semantic meaning
                if style_type == "line":
                    edge_type = "is_before"
                elif style_type == "double_line":
                    edge_type = "has_same_time"
                elif style_type == "dotted":
                    edge_type = "changed_from"
                elif style_type == "dashed":
                    edge_type = "has_data_provenance"
                elif style_type == "dashed_dotted":
                    edge_type = "contrasts_with"
                else:
                    edge_type = "generic_connection"  # Default to "generic_connection" if unknown style

        return edge_type


    # Funzioni di utilità

    def _check_node_type(self, node_element):
        id_node = str(node_element.attrib)
        if "yfiles.foldertype" in id_node:
            tablenode = node_element.find('.//{http://www.yworks.com/xml/graphml}TableNode')
            if tablenode is not None:
                return 'node_swimlane'
            else:
                return 'node_group'
        else:
            return 'node_simple'

    def estrai_stringa_e_vocabolario(self, s):
        match = re.search(r'\[(.*?)\]', s)
        vocabolario = {}
        if match:
            contenuto = match.group(1)
            coppie = contenuto.split(';')
            for coppia in coppie:
                coppia = coppia.strip()
                if not coppia:
                    continue
                if ':' in coppia:
                    parti = coppia.split(':', 1)
                    if len(parti) != 2 or not parti[0] or not parti[1]:
                        raise ValueError(f"Coppia chiave:valore malformata: '{coppia}'")
                    chiave, valore = parti
                    chiave = chiave.strip()
                    valore = valore.strip()
                    try:
                        valore = int(valore)
                    except ValueError:
                        pass
                    vocabolario[chiave] = valore
                else:
                    raise ValueError(f"Coppia senza separatore ':': '{coppia}'")
            stringa_pulita = re.sub(r'\[.*?\]', '', s).strip()
        else:
            stringa_pulita = s.strip()
        return stringa_pulita, vocabolario

    def clean_comments(self, multiline_str):
        newstring = ""
        for line in multiline_str.splitlines():
            if line.startswith("«") or line.startswith("#"):
                pass
            else:
                newstring += line + " "
        return newstring.strip()

    def getnode_id(self, node_element):
        return str(node_element.attrib['id'])

    def _check_if_empty(self, name):
        return name if name is not None else ""

    # Aggiungi ulteriori metodi di supporto se necessario
