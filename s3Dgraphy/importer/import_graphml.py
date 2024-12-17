# s3Dgraphy/import_graphml.py

import xml.etree.ElementTree as ET
from ..graph import Graph
from ..nodes.stratigraphic_node import (
    Node, StratigraphicNode)
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

    def parse(self):
        """
        Esegue il parsing del file GraphML e popola l'istanza di Graph.

        Returns:
            Graph: Istanza di Graph popolata con nodi e archi dal file GraphML.
        """
        tree = ET.parse(self.filepath)
        self.parse_nodes(tree)
        self.parse_edges(tree)
        self.connect_nodes_to_epochs()
        self.graph.display_warnings()
        return self.graph

    def parse_nodes(self, tree):
        """
        Esegue il parsing dei nodi dal file GraphML.

        Args:
            tree (ElementTree): Albero XML del file GraphML.
        """
        allnodes = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}node')

        for node_element in allnodes:
            node_type = self._check_node_type(node_element)
            if node_type == 'node_simple':
                self.process_node_element(node_element)
            elif node_type == 'node_swimlane':
                # Parsing dei nodi EpochNode
                self.extract_epochs(node_element, self.graph)
            elif node_type == 'node_group':
                # Parsing dei nodi Group
                self.handle_group_node(node_element)

    def parse_edges(self, tree):
        """
        Esegue il parsing degli archi dal file GraphML.

        Args:
            tree (ElementTree): Albero XML del file GraphML.
        """
        alledges = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}edge')

        for edge in alledges:
            # Estrazione dei dettagli dell'arco
            edge_id = str(edge.attrib['id'])
            edge_source = str(edge.attrib['source'])
            edge_target = str(edge.attrib['target'])
            edge_type = self.EM_extract_edge_type(edge)

            # Aggiunta dell'arco al grafo
            self.graph.add_edge(edge_id, edge_source, edge_target, edge_type)

    def process_node_element(self, node_element):
        """
        Processa un elemento nodo dal file GraphML e lo aggiunge al grafo.

        Args:
            node_element (Element): Elemento nodo XML dal file GraphML.
        """

        if self.EM_check_node_us(node_element):
            # Creazione del nodo stratigrafico e aggiunta al grafo
            nodename, nodedescription, nodeurl, nodeshape, node_y_pos, fillcolor, borderstyle = self.EM_extract_node_name(node_element)
            
            stratigraphic_type = convert_shape2type(nodeshape, borderstyle)[0]
            node_class = get_stratigraphic_node_class(stratigraphic_type)  # Ottieni la classe usando la funzione
            stratigraphic_node = node_class(
                node_id=self.getnode_id(node_element),
                name=nodename,
                description=nodedescription
            )
            #print(f"Created node {stratigraphic_node.name} with node_type {stratigraphic_node.node_type}")

            # Aggiunta di runtime properties
            stratigraphic_node.attributes['shape'] = nodeshape
            stratigraphic_node.attributes['y_pos'] = float(node_y_pos)
            stratigraphic_node.attributes['fill_color'] = fillcolor
            stratigraphic_node.attributes['border_style'] = borderstyle
            self.graph.add_node(stratigraphic_node)

        elif self.EM_check_node_document(node_element):
            # Creazione del nodo documento e aggiunta al grafo
            nodename, node_id, nodedescription, nodeurl, _ = self.EM_extract_document_node(node_element)
            document_node = DocumentNode(
                node_id=node_id,
                name=nodename,
                description=nodedescription,
                url=nodeurl
            )

            self.graph.add_node(document_node)


            # Se c'è un URL valido, crea un nodo Link
            if nodeurl and nodeurl.strip() != 'Empty':
                link_node = self._create_link_node(document_node, nodeurl)
                

        elif self.EM_check_node_property(node_element):
            # Creazione del nodo proprietà e aggiunta al grafo
            nodename, node_id, nodedescription, nodeurl, _ = self.EM_extract_property_node(node_element)
            property_node = PropertyNode(
                node_id=node_id,
                name=nodename,
                description=nodedescription,
                value=nodeurl,
                data={},  # Popola 'data' se necessario
                url=nodeurl
            )
            self.graph.add_node(property_node)

        elif self.EM_check_node_extractor(node_element):
            # Creazione del nodo extractor e aggiunta al grafo
            nodename, node_id, nodedescription, nodeurl, _ = self.EM_extract_extractor_node(node_element)
            extractor_node = ExtractorNode(
                node_id=node_id,
                name=nodename,
                description=nodedescription,
                source=nodeurl
            )

            self.graph.add_node(extractor_node)

            # Se c'è un URL valido, crea un nodo Link
            if nodeurl and nodeurl.strip() != 'Empty':
                link_node = self._create_link_node(extractor_node, nodeurl)


        elif self.EM_check_node_combiner(node_element):
            # Creazione del nodo combiner e aggiunta al grafo
            nodename, node_id, nodedescription, nodeurl, _ = self.EM_extract_combiner_node(node_element)
            combiner_node = CombinerNode(
                node_id=node_id,
                name=nodename,
                description=nodedescription,
                sources=[nodeurl]
            )
            self.graph.add_node(combiner_node)

        elif self.EM_check_node_continuity(node_element):
            # Creazione del nodo continuity e aggiunta al grafo
            nodedescription, node_y_pos, node_id = self.EM_extract_continuity(node_element)
            continuity_node = StratigraphicNode(
                node_id=node_id,
                name="continuity_node",
                stratigraphic_type="BR",
                description=nodedescription
            )
            continuity_node.attributes['y_pos'] = float(node_y_pos)
            self.graph.add_node(continuity_node)

        else:
            # Creazione di un nodo generico
            node_id = self.getnode_id(node_element)
            node_name = self.EM_extract_generic_node_name(node_element)
            generic_node = Node(
                node_id=node_id,
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
        # Estrarre l'ID, il nome e la descrizione del gruppo
        group_id = self.getnode_id(node_element)
        group_name = self.EM_extract_group_node_name(node_element)
        group_description = self.EM_extract_group_node_description(node_element)
        group_background_color = self.EM_extract_group_node_background_color(node_element)
        group_y_pos = self.EM_extract_group_node_y_pos(node_element)

        # Determinare il tipo di nodo gruppo basandoci sul background color
        group_node_type = self.determine_group_node_type_by_color(group_background_color)

        if group_node_type == 'ActivityNodeGroup':
            group_node = ActivityNodeGroup(
                node_id=group_id,
                name=group_name,
                description=group_description,
                y_pos=group_y_pos
            )
        elif group_node_type == 'ParadataNodeGroup':
            group_node = ParadataNodeGroup(
                node_id=group_id,
                name=group_name,
                description=group_description,
                y_pos=group_y_pos
            )
        elif group_node_type == 'TimeBranchNodeGroup':
            group_node = TimeBranchNodeGroup(
                node_id=group_id,
                name=group_name,
                description=group_description,
                y_pos=group_y_pos
            )
        else:
            group_node = GroupNode(
                node_id=group_id,
                name=group_name,
                description=group_description,
                y_pos=group_y_pos
            )

        # Aggiungere il nodo gruppo al grafo
        self.graph.add_node(group_node)

        # Processare i nodi contenuti nel gruppo
        subgraph = node_element.find('{http://graphml.graphdrawing.org/xmlns}graph')
        if subgraph is not None:
            subnodes = subgraph.findall('{http://graphml.graphdrawing.org/xmlns}node')
            for subnode in subnodes:
                subnode_id = self.getnode_id(subnode)
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

                # Creare l'arco 'is_grouped_in' dopo aver aggiunto il nodo al grafo
                if not self.graph.find_edge_by_nodes(subnode_id, group_id):
                    edge_id = f"{subnode_id}_has_activity_{group_id}"
                    self.graph.add_edge(
                        edge_id=edge_id,
                        edge_source=subnode_id,
                        edge_target=group_id,
                        edge_type="has_activity"
                    )

    def extract_epochs(self, node_element, graph):
        """
        Estrae gli EpochNode dal nodo swimlane nel file GraphML.

        Args:
            node_element (Element): Elemento nodo XML dal file GraphML.
            graph (Graph): Istanza del grafo in cui aggiungere gli EpochNode.
        """
        geometry = node_element.find('.//{http://www.yworks.com/xml/graphml}Geometry')
        y_start = float(geometry.attrib['y'])

        y_min = y_start
        y_max = y_start

        for row in node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}Table/{http://www.yworks.com/xml/graphml}Rows/{http://www.yworks.com/xml/graphml}Row'):
            id_row = row.attrib['id']
            h_row = float(row.attrib['height'])

            #for attribrow in row.attrib:
            #    print(f"Attibuto: {attribrow}")
            #print(f"Il testo dela row è: {row.text}")

            y_min = y_max
            y_max += h_row

            epoch_node = EpochNode(
                node_id=id_row,
                name="temp",
                start_time=-10000,
                end_time=10000
            )
            epoch_node.min_y = y_min
            epoch_node.max_y = y_max
            self.graph.add_node(epoch_node)
            #print(f"Ho creato un nodo epoca con id {id_row}")


        for nodelabel in node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}NodeLabel'):
            RowNodeLabelModelParameter = nodelabel.find('.//{http://www.yworks.com/xml/graphml}RowNodeLabelModelParameter')
            ColumnNodeLabelModelParameter = nodelabel.find('.//{http://www.yworks.com/xml/graphml}ColumnNodeLabelModelParameter')

            #Extract generaldata from the EM
            if RowNodeLabelModelParameter is None and ColumnNodeLabelModelParameter is None:
                self.process_general_data(nodelabel, self.graph)

            #Extract sectors as localdata from the EM
            elif ColumnNodeLabelModelParameter is not None:
                #print(f"Trovate colonne del grafo")
                height = nodelabel.attrib["height"]
                width = nodelabel.attrib["width"]
                x = nodelabel.attrib["x"]
                print(f"La colonna {nodelabel.text} ha altezza: {height}, x: {x} e larghezza: {width}")

            # here check if it is a swimlane (epoch)    
            elif RowNodeLabelModelParameter is not None:

                label_node = nodelabel.text
                id_node = str(RowNodeLabelModelParameter.attrib['id'])

                if 'backgroundColor' in nodelabel.attrib:
                    e_color = str(nodelabel.attrib['backgroundColor'])
                else:
                    e_color = "#BCBCBC"

                epoch_node = graph.find_node_by_id(id_node)

                if epoch_node:
                    try:
                        stringa_pulita, vocabolario = self.estrai_stringa_e_vocabolario(label_node)
                        epoch_node.set_name(stringa_pulita)
                        epoch_node.set_start_time(vocabolario.get('start', -10000))
                        epoch_node.set_end_time(vocabolario.get('end', 10000))
                    except ValueError as e:
                        epoch_node.set_name(label_node)

                    epoch_node.set_color(e_color)
                    print(f'Ho creato un nodo epoca chiamato {epoch_node.name}')


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
        # Definisce i tipi di nodi stratigrafici fisici che possono estendersi fino all'ultima epoca
        list_of_physical_stratigraphic_nodes = ["US", "serSU"]

        # Assegna le epoche ai nodi
        for node in (node for node in self.graph.nodes if isinstance(node, (StratigraphicNode, GroupNode))):
            connected_continuity_node = self.graph.get_connected_node_by_type(node, "BR")

            for epoch in (n for n in self.graph.nodes if isinstance(n, EpochNode)):
                if epoch.min_y < node.attributes['y_pos'] < epoch.max_y:
                    edge_id = f"{node.node_id}_{epoch.name}"
                    self.graph.add_edge(edge_id, node.node_id, epoch.node_id, "has_first_epoch")

                elif connected_continuity_node:
                    if epoch.max_y >= connected_continuity_node.attributes['y_pos'] and epoch.min_y <= node.attributes['y_pos']:
                        edge_id = f"{node.node_id}_{epoch.name}"
                        self.graph.add_edge(edge_id, node.node_id, epoch.node_id, "survive_in_epoch")

                elif (not connected_continuity_node) and (node.node_type in list_of_physical_stratigraphic_nodes):
                    if node.attributes['y_pos'] > epoch.max_y:
                        edge_id = f"{node.node_id}_{epoch.name}"
                        self.graph.add_edge(edge_id, node.node_id, epoch.node_id, "survive_in_epoch")

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
        nodedescription, _, _ = self.EM_extract_continuity(node_element)
        return nodedescription == "_continuity"

    def EM_extract_continuity(self, node_element):
        is_d5 = False
        node_y_pos = 0.0
        nodedescription = None
        node_id = node_element.attrib['id']

        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            if subnode.attrib.get('key') == 'd5':
                is_d5 = True
                nodedescription = subnode.text
            if subnode.attrib.get('key') == 'd6':
                for geometry in subnode.findall('.//{http://www.yworks.com/xml/graphml}Geometry'):
                    node_y_pos = float(geometry.attrib['y'])
        if not is_d5:
            nodedescription = ''
        return nodedescription, node_y_pos, node_id

    def EM_extract_edge_type(self, edge_element):
        """
        Extracts the semantic type of the edge from the GraphML data.
        
        Args:
            edge_element (Element): XML element for the edge.

        Returns:
            str: The edge type representing the semantic relationship.
        """
        edge_type = "generic_connection"  # Default edge type
        data_element = edge_element.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d10"]')

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


        #if edge_type not in EDGE_TYPES:
        #    print(f"Warning: Unrecognized edge type '{edge_type}' detected for edge {edge_element.attrib['id']}. Defaulting to 'generic_connection'.")
        #    edge_type = "generic_connection"

        #print(f"Parsed edge type '{edge_type}' for edge {edge_element.attrib['id']}")
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
