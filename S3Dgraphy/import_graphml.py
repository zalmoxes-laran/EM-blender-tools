# S3Dgraphy/import_graphml.py

import xml.etree.ElementTree as ET
from .graph import Graph
from .node import (
    Node, StratigraphicNode, ParadataNode, DocumentNode,
    CombinerNode, ExtractorNode, PropertyNode, EpochNode, GroupNode, ParadataNodeGroup, ActivityNodeGroup
)
from .edge import Edge

from .utils import convert_shape2type

import re

class GraphMLImporter:
    def __init__(self, filepath, graph=None):
        self.filepath = filepath
        self.graph = graph if graph is not None else Graph()
    
    def parse(self):

        tree = ET.parse(self.filepath)
        
        self.parse_nodes(tree)

        self.parse_edges(tree)

        self.connect_nodes_to_epochs()

        return self.graph

    def parse_edges(self,tree):

        alledges = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}edge')

        for edge in alledges:
            # Aggiunta del nodo al grafo
            self.graph.add_edge(str(edge.attrib['id']), str(edge.attrib['source']), str(edge.attrib['target']), self.EM_extract_edge_type(edge))

    def parse_nodes(self, tree):
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

    def process_node_element(self, node_element):
        node_type = self._check_node_type(node_element)
        if node_type == 'node_simple':
            if self.EM_check_node_us(node_element):
                # Creazione del nodo stratigrafico e aggiunta al grafo
                nodename, nodedescription, nodeurl, nodeshape, node_y_pos, fillcolor, borderstyle = self.EM_extract_node_name(node_element)
                stratigraphic_node = StratigraphicNode(
                    node_id=self.getnode_id(node_element),
                    name=nodename,
                    stratigraphic_type=convert_shape2type(nodeshape, borderstyle)[0],
                    description=nodedescription
                )
                # Aggiunta di runtime properties
                stratigraphic_node.attributes['shape'] = nodeshape
                stratigraphic_node.attributes['y_pos'] = float(node_y_pos)
                stratigraphic_node.attributes['fill_color'] = fillcolor
                stratigraphic_node.attributes['border_style'] = borderstyle
                self.graph.add_node(stratigraphic_node)

            elif self.EM_check_node_document(node_element):
                # Creazione del nodo documento e aggiunta al grafo
                src_nodename, src_node_id, src_node_description, src_nodeurl, subnode_is_document = self.EM_extract_document_node(node_element)
                document_node = DocumentNode(
                    node_id=src_node_id,
                    name=src_nodename,
                    description=src_node_description,
                    url=src_nodeurl
                )
                self.graph.add_node(document_node)

            elif self.EM_check_node_property(node_element):
                # Creazione del nodo proprietà e aggiunta al grafo
                pro_nodename, pro_node_id, pro_node_description, pro_nodeurl, subnode_is_property = self.EM_extract_property_node(node_element)
                property_node = PropertyNode(
                    node_id=pro_node_id,
                    name=pro_nodename,
                    description=pro_node_description,
                    value=pro_nodeurl
                )
                self.graph.add_node(property_node)

            elif self.EM_check_node_extractor(node_element):
                # Creazione del nodo extractor e aggiunta al grafo
                ext_nodename, ext_node_id, ext_node_description, ext_nodeurl, subnode_is_extractor = self.EM_extract_extractor_node(node_element)
                extractor_node = ExtractorNode(
                    node_id=ext_node_id,
                    name=ext_nodename,
                    description=ext_node_description,
                    source=ext_nodeurl
                )
                self.graph.add_node(extractor_node)

            elif self.EM_check_node_combiner(node_element):
                # Creazione del nodo combiner e aggiunta al grafo
                com_nodename, com_node_id, com_node_description, com_nodeurl, subnode_is_combiner = self.EM_extract_combiner_node(node_element)
                combiner_node = CombinerNode(
                    node_id=com_node_id,
                    name=com_nodename,
                    description=com_node_description,
                    sources=[com_nodeurl]
                )
                self.graph.add_node(combiner_node)

            elif self.EM_check_node_continuity(node_element):
                # Creazione del nodo continuity e aggiunta al grafo
                continuity_node_id, y_pos, node_id = self.EM_extract_continuity(node_element)
                continuity_node = StratigraphicNode(
                    node_id=node_id,
                    name="continuity_node",
                    stratigraphic_type="BR",
                    description=""
                )
                continuity_node.attributes['y_pos'] = float(y_pos)
                self.graph.add_node(continuity_node)

            else:
                # Creazione di un nodo generico
                node_id = self.getnode_id(node_element)
                node_name = self.EM_extract_generic_node_name(node_element)
                generic_node = Node(
                    node_id=node_id,
                    name=node_name,
                    node_type="Generic",
                    description=""
                )
                self.graph.add_node(generic_node)
        else:
            # Se necessario, gestisci altri tipi di nodi qui
            pass

    def EM_extract_generic_node_name(self, node_element):
        node_name = ''
        data_d6 = node_element.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d6"]')
        if data_d6 is not None:
            node_label = data_d6.find('.//{http://www.yworks.com/xml/graphml}NodeLabel')
            if node_label is not None:
                node_name = self._check_if_empty(node_label.text)
        return node_name
    
    def handle_group_node(self, node_element):
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
        else:
            group_node = GroupNode(
                node_id=group_id,
                name=group_name,
                description=group_description,
                y_pos=group_y_pos
            )

        # Aggiungere il nodo gruppo al grafo
        self.graph.add_node(group_node)

        # Processare i nodi contenuti come prima
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
                    edge_id = f"{subnode_id}_grouped_in_{group_id}"
                    self.graph.add_edge(
                        edge_id=edge_id,
                        edge_source=subnode_id,
                        edge_target=group_id,
                        edge_type="is_grouped_in"
                    )

    def EM_extract_group_node_background_color(self, node_element):
        background_color = None
        data_d6 = node_element.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d6"]')
        if data_d6 is not None:
            # Naviga attraverso gli elementi per trovare il backgroundColor
            node_label = data_d6.find('.//{http://www.yworks.com/xml/graphml}NodeLabel')
            if node_label is not None:
                background_color = node_label.attrib.get('backgroundColor')
        return background_color

    def determine_group_node_type_by_color(self, background_color):
        if background_color == '#CCFFFF':
            return 'ActivityNodeGroup'
        elif background_color == '#EBEBEB':
            return 'ParadataNodeGroup'
        else:
            return 'GroupNode'

    def EM_extract_group_node_description(self, node_element):
        group_description = ''
        data_d5 = node_element.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d5"]')
        if data_d5 is not None and data_d5.text is not None:
            group_description = self.clean_comments(data_d5.text)
        return group_description

    def EM_extract_group_node_y_pos(self, node_element):
        y_pos = 0.0
        data_d6 = node_element.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d6"]')
        if data_d6 is not None:
            geometry = data_d6.find('.//{http://www.yworks.com/xml/graphml}Geometry')
            if geometry is not None:
                y_pos = float(geometry.attrib.get('y', 0.0))
        return y_pos

    def EM_extract_group_node_name(self, node_element):
        group_name = ''
        data_d6 = node_element.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d6"]')
        if data_d6 is not None:
            node_label = data_d6.find('.//{http://www.yworks.com/xml/graphml}NodeLabel')
            if node_label is not None:
                group_name = self._check_if_empty(node_label.text)
        return group_name
    
    def EM_extract_nodes_in_group(self, node_element):
        node_ids_in_group = []
        subgraph = node_element.find('{http://graphml.graphdrawing.org/xmlns}graph')
        if subgraph is not None:
            subnodes = subgraph.findall('{http://graphml.graphdrawing.org/xmlns}node')
            for subnode in subnodes:
                subnode_id = self.getnode_id(subnode)
                node_ids_in_group.append(subnode_id)
                # Verifica se il subnode è un gruppo
                if self._check_node_type(subnode) == 'node_group':
                    # Gestire ricorsivamente i nodi contenuti nel sottogruppo
                    subnode_ids_in_group = self.EM_extract_nodes_in_group(subnode)
                    node_ids_in_group.extend(subnode_ids_in_group)
        return node_ids_in_group

    #voglio ottimizzare questa funzione in modo che faccia un solo passaggio sui nodi
    def extract_epochs(self, node_element, graph):
        e = None # iniziamo dicendo che non ci sono errori nel parser
        geometry = node_element.find('.//{http://www.yworks.com/xml/graphml}Geometry')
        y_start = float(geometry.attrib['y'])
        
        y_min = y_start
        y_max = y_start

        for row in node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}Table/{http://www.yworks.com/xml/graphml}Rows/{http://www.yworks.com/xml/graphml}Row'):
            id_row = row.attrib['id']
            h_row = float(row.attrib['height'])
            #print(str(y_min))
            #print(id_row)
            
            y_min = y_max
            y_max += h_row
            
            epoch_node = EpochNode(
                node_id=id_row,
                name="temp",
                start_time = -10000,
                end_time = 10000
            )
            epoch_node.min_y = y_min
            epoch_node.max_y = y_max
            self.graph.add_node(epoch_node)
            

        for nodelabel in node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}NodeLabel'):
            RowNodeLabelModelParameter = nodelabel.find('.//{http://www.yworks.com/xml/graphml}RowNodeLabelModelParameter')
            if RowNodeLabelModelParameter is not None:
                label_node = nodelabel.text
                
                id_node = str(RowNodeLabelModelParameter.attrib['id'])
                #print("il nome del nodo trovato è "+label_node+" ed appartiene alla row: "+ id_node)
                if 'backgroundColor' in nodelabel.attrib:
                    e_color = str(nodelabel.attrib['backgroundColor'])
                else:
                    e_color = "#BCBCBC"
            else:
                id_node = "null"
            
            #print(id_node)
            epoch_node = graph.find_node_by_id(id_node)

            if epoch_node:
                #print("trovato nodo "+epoch_node.node_id)
                #print("sto per settare come nome del nodo: "+label_node)

                try:
                    stringa_pulita, vocabolario = self.estrai_stringa_e_vocabolario(label_node)
                    print("Stringa pulita:", stringa_pulita)
                    print("Vocabolario:", vocabolario)
                except ValueError as e:
                    print("Error:", e)

                epoch_node.set_color(e_color)

                try:
                    epoch_node.set_name(stringa_pulita)
                    epoch_node.set_start_time(vocabolario['start'])
                    epoch_node.set_end_time(vocabolario['end'])
                except UnboundLocalError as e:
                    print("Error:", e)
                    epoch_node.set_name(label_node)


                #print(f"Il min dell'epoca {epoch_node.name} è {epoch_node.min_y}")
                #print(epoch_node.color)
                #print(epoch_node.name)
                #print(str(epoch_node.min_y))
                
        return graph

    def connect_nodes_to_epochs(self):
        #define here a list of StratigraphicNode types that should be filled with a continuity node in the last epoch even if they do not have one. If no continuity node was set (end of life) we suppose that the US survives untill the last epoch
        list_of_phisical_stratigraphic_nodes = ["US", "serSU"]

        # Assegna le epoche ai nodi nel grafo in base alla posizione Y e tenendo in considerazione i nodi continuity
        for node in (node for node in self.graph.nodes if isinstance(node, (StratigraphicNode, GroupNode))):
        # codice per associare l'epoca al nodo
            #print(f"Inizio ad occuparmi di {node.name}")
            
            connected_continuity_node = self.graph.get_connected_node_by_type(node, "BR")

            for epoch in (node for node in self.graph.nodes if isinstance(node, EpochNode)):
                #print(epoch.name)
                if epoch.min_y < node.attributes['y_pos'] < epoch.max_y:
                    edge_id = node.node_id + "_" + epoch.name
                    self.graph.add_edge(edge_id, node.node_id, epoch.node_id, "has_first_epoch")
                    #print(f"ho trovato la prima epoca: {epoch.name} che ha ymin: {epoch.min_y} e ymax: {epoch.max_y} per un nodo {node.name} che ha y: {node.attributes['y_pos']}")
                
                elif connected_continuity_node: ## qui si affrontano i nodi che SONO connessi a nodi continuity, per cui si bisogna iterare su tutte le epoche pertinenti per associarle al nodo
                    print(f"C'è un continuity (id: {connected_continuity_node.node_id} e y_pos: {connected_continuity_node.attributes['y_pos']}) connesso a {node.name} con valore y_pos {node.attributes['y_pos']}. L'epoca {epoch.name} ha ymin: {epoch.min_y} e max: {epoch.max_y}")
                    if epoch.max_y >= connected_continuity_node.attributes['y_pos'] and epoch.min_y <= node.attributes['y_pos']:
                        edge_id = node.node_id + "_" + epoch.name
                        self.graph.add_edge(edge_id, node.node_id, epoch.node_id, "survive_in_epoch") 
                        #print(f"Il nodo {node.name} con pos_y {str(node.attributes['y_pos'])} è connesso ad un continuity node con y_pos {str(connected_continuity_node.attributes['y_pos'])}")
                
                # qui si filtrano nodi che inoltre appartengono ai resti fisici
                elif (not connected_continuity_node) and (node.node_type in list_of_phisical_stratigraphic_nodes):
                    if node.attributes['y_pos'] > epoch.max_y:
                        #print(f"Questo è un nodo che non ha un continuity {node.name} di tipo {node.node_type}con {node.attributes['y_pos']} da confrontare con una epoca {epoch.name} con min {epoch.min_y} e max {epoch.max_y}  ")

                        edge_id = node.node_id + "_" + epoch.name
                        self.graph.add_edge(edge_id, node.node_id, epoch.node_id, "survive_in_epoch")

    def estrai_stringa_e_vocabolario(self,s):
        # Trova il contenuto tra parentesi quadre
        match = re.search(r'\[(.*?)\]', s)
        vocabolario = {}
        if match:
            contenuto = match.group(1)
            # Dividi il contenuto in coppie chiave:valore
            coppie = contenuto.split(';')
            for coppia in coppie:
                coppia = coppia.strip()
                if not coppia:
                    continue  # Ignora coppie vuote
                if ':' in coppia:
                    parti = coppia.split(':', 1)
                    if len(parti) != 2 or not parti[0] or not parti[1]:
                        raise ValueError(f"Coppia chiave:valore malformata: '{coppia}'")
                    chiave, valore = parti
                    chiave = chiave.strip()
                    valore = valore.strip()
                    if not chiave or not valore:
                        raise ValueError(f"Coppia chiave:valore malformata: '{coppia}'")
                    # Prova a convertire il valore in intero, se possibile
                    try:
                        valore = int(valore)
                    except ValueError:
                        pass
                    vocabolario[chiave] = valore
                else:
                    raise ValueError(f"Coppia senza separatore ':': '{coppia}'")
            # Rimuovi il contenuto tra parentesi quadre dalla stringa originale
            stringa_pulita = re.sub(r'\[.*?\]', '', s).strip()
        else:
            stringa_pulita = s.strip()
        return stringa_pulita, vocabolario

    def EM_extract_edge_type(self, edge_element):
        edge_type = "Empty"
        for subedge in edge_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            #print(subedge.attrib)
            attrib1 = subedge.attrib
            #print(subnode.tag)
            if attrib1 == {'key': 'd10'}:
                type_vocab={}
                for property in subedge.findall('.//{http://www.yworks.com/xml/graphml}LineStyle'):
                    type_vocab = property.attrib #json.loads(property.attrib)
                    #print(type_vocab["type"])
                    edge_type = self._check_if_empty(type_vocab["type"])
                    
        return edge_type  

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

    # UUSS NODE
    def EM_check_node_us(self, node_element):
        US_nodes_list = ['rectangle', 'parallelogram', 'ellipse', 'hexagon', 'octagon', 'roundrectangle']
        my_nodename, my_node_description, my_node_url, my_node_shape, my_node_y_pos, my_node_fill_color, my_node_border_style = self.EM_extract_node_name(node_element)
        if my_node_shape in US_nodes_list:
            id_node_us = True
        else:
            id_node_us = False
        return id_node_us

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
            if attrib == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd4'}:
                is_d4 = True
                nodeurl = subnode.text
            if attrib == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
                is_d5 = True
                nodedescription = self.clean_comments(subnode.text)
            if attrib == {'key': 'd6'}:
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = self._check_if_empty(USname.text)
                for fill_color in subnode.findall('.//{http://www.yworks.com/xml/graphml}Fill'):
                    fillcolor = fill_color.attrib['color']
                for border_style in subnode.findall('.//{http://www.yworks.com/xml/graphml}BorderStyle'):
                    borderstyle = border_style.attrib['color']
                for USshape in subnode.findall('.//{http://www.yworks.com/xml/graphml}Shape'):
                    nodeshape = USshape.attrib['type']
                for geometry in subnode.findall('./{http://www.yworks.com/xml/graphml}ShapeNode/{http://www.yworks.com/xml/graphml}Geometry'):
                #for geometry in subnode.findall('./{http://www.yworks.com/xml/graphml}Geometry'):
                    node_y_pos = geometry.attrib['y']
        if not is_d4:
            nodeurl = ''
        if not is_d5:
            nodedescription = ''
        return nodename, nodedescription, nodeurl, nodeshape, node_y_pos, fillcolor, borderstyle     

    # DOCUMENT NODE
    def EM_check_node_document(self, node_element):
        try:
            src_nodename, src_node_id, src_node_description, src_nodeurl, subnode_is_document = self.EM_extract_document_node(node_element)
        except TypeError as e:
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

        # Prima iterazione per determinare se il nodo è un documento
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            attrib1 = subnode.attrib
            if attrib1 == {'key': 'd6'}:
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = USname.text
                for nodetype in subnode.findall('.//{http://www.yworks.com/xml/graphml}Property'):
                    attrib2 = nodetype.attrib
                    if attrib2 == {'class': 'com.yworks.yfiles.bpmn.view.DataObjectTypeEnum', 'name': 'com.yworks.bpmn.dataObjectType', 'value': 'DATA_OBJECT_TYPE_PLAIN'}:
                        subnode_is_document = True

        # Seconda iterazione per estrarre URL e descrizione se il nodo è un documento
        if subnode_is_document:
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                attrib1 = subnode.attrib
                if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd4'}:
                    if subnode.text is not None:
                        is_d4 = True
                        nodeurl = subnode.text
                if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
                    is_d5 = True
                    node_description = self.clean_comments(subnode.text)

        if not is_d4:
            nodeurl = ''
        if not is_d5:
            node_description = ''
        return nodename, node_id, node_description, nodeurl, subnode_is_document

    # PROPERTY NODE
    def EM_check_node_property(self, node_element):
        try:
            pro_nodename, pro_node_id, pro_node_description, pro_nodeurl, subnode_is_property = self.EM_extract_property_node(node_element)
        except UnboundLocalError as e:
            subnode_is_property = False
        return subnode_is_property

    def EM_extract_property_node(self, node_element):
        is_d4 = False
        is_d5 = False
        node_id = node_element.attrib['id']
        if len(node_id) > 2:
            subnode_is_property = False
            nodeurl = " "
            nodename = " "
            node_description = " "
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                attrib1 = subnode.attrib
                if attrib1 == {'key': 'd6'}:
                    for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                        nodename = self._check_if_empty(USname.text)
                    for nodetype in subnode.findall('.//{http://www.yworks.com/xml/graphml}Property'):
                        attrib2 = nodetype.attrib
                        if attrib2 == {'class': 'com.yworks.yfiles.bpmn.view.BPMNTypeEnum', 'name': 'com.yworks.bpmn.type', 'value': 'ARTIFACT_TYPE_ANNOTATION'}:
                            subnode_is_property = True

            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                attrib1 = subnode.attrib                        
                if subnode_is_property is True:

                    if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd4'}:
                        if subnode.text is not None:
                            is_d4 = True
                            nodeurl = subnode.text
                    if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
                        is_d5 = True
                        node_description = self.clean_comments(subnode.text)

            if not is_d4:
                nodeurl = ''
            if not is_d5:
                nodedescription = ''        
        return nodename, node_id, node_description, nodeurl, subnode_is_property

    # EXTRACTOR NODE
    def EM_check_node_extractor(self, node_element):
        try:
            ext_nodename, ext_node_id, ext_node_description, ext_nodeurl, subnode_is_extractor = self.EM_extract_extractor_node(node_element)
        except TypeError as e:
            subnode_is_extractor = False
        return subnode_is_extractor
    
    def EM_extract_extractor_node(self, node_element):

        is_d4 = False
        is_d5 = False
        node_id = node_element.attrib['id']
        if len(node_id) > 2:
            subnode_is_extractor = False
            nodeurl = " "
            nodename = " "
            node_description = " "
            is_document = False
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                attrib1 = subnode.attrib
                #print(subnode.tag)
                if attrib1 == {'key': 'd6'}:
                    for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                        nodename = self._check_if_empty(USname.text)
                    if nodename.startswith("D."):
                        for elem in self.graph.nodes:#bpy.context.scene.em_sources_list:
                            if nodename == elem.name:
                                is_document = True
                        if not is_document:
                            #print(f"il nodo non è un documento e si chiama: {nodename}")
                            subnode_is_extractor = True
                    # for nodetype in subnode.findall('.//{http://www.yworks.com/xml/graphml}SVGContent'):
                    #     attrib2 = nodetype.attrib
                    #     if attrib2 == {'refid': '1'}:
                    #         subnode_is_extractor = True
                            
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                attrib1 = subnode.attrib                        
                if subnode_is_extractor is True:

                    if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd4'}:
                        if subnode.text is not None:
                            is_d4 = True
                            nodeurl = self._check_if_empty(subnode.text)
                    if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
                        is_d5 = True
                        node_description = self.clean_comments(self._check_if_empty(subnode.text))

            if not is_d4:
                nodeurl = ''
            if not is_d5:
                nodedescription = ''
            return nodename, node_id, node_description, nodeurl, subnode_is_extractor

    # COMBINER NODE
    def EM_check_node_combiner(self, node_element):
        try:
            com_nodename, com_node_id, com_node_description, com_nodeurl, subnode_is_combiner = self.EM_extract_combiner_node(node_element)
        except TypeError as e:
            subnode_is_combiner = False
        return subnode_is_combiner

    def EM_extract_combiner_node(self, node_element):
        is_d4 = False
        is_d5 = False
        node_id = node_element.attrib['id']
        if len(node_id) > 2:
            subnode_is_combiner = False
            nodeurl = " "
            nodename = " "
            node_description = " "
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                attrib1 = subnode.attrib
                #print(subnode.tag)
                if attrib1 == {'key': 'd6'}:
                    for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                        nodename = self._check_if_empty(USname.text)
                    if nodename.startswith("C."):
                        subnode_is_combiner = True
                            
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                attrib1 = subnode.attrib                        
                if subnode_is_combiner is True:

                    if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd4'}:
                        if subnode.text is not None:
                            is_d4 = True
                            nodeurl = self._check_if_empty(subnode.text)
                    if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
                        is_d5 = True
                        node_description = self.clean_comments(self._check_if_empty(subnode.text))

            if not is_d4:
                nodeurl = ''
            if not is_d5:
                nodedescription = ''
            return nodename, node_id, node_description, nodeurl, subnode_is_combiner

    #CONTINUITY NODE
    def EM_check_node_continuity(self, node_element):
        id_node_continuity = False
        my_node_description, my_node_y_pos, node_id = self.EM_extract_continuity(node_element)
        if my_node_description == "_continuity":
            id_node_continuity = True

        return id_node_continuity

    def EM_extract_continuity(self, node_element):
        is_d5 = False
        node_y_pos = 0.0
        nodedescription = None
        node_id = node_element.attrib['id']
        print(str(node_id))
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            attrib = subnode.attrib
            
            #print(attrib)
            if attrib == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
                is_d5 = True
                nodedescription = subnode.text
                #print(nodedescription)
            if attrib == {'key': 'd6'}:
                for geometry in subnode.findall('./{http://www.yworks.com/xml/graphml}SVGNode/{http://www.yworks.com/xml/graphml}Geometry'):
                    node_y_pos = float(geometry.attrib['y'])
                    #print("il valore y di nodo "+ str(nodedescription) +" = "+str(node_y_pos))
        if not is_d5:
            nodedescription = ''
        return nodedescription, node_y_pos, node_id

    # FUNZIONE PER ELIMINARE COMMENTI NELLE DESCRIZIONI DEI NODI (laddove ci siano)
    def clean_comments(self, multiline_str):
        newstring = ""
        for line in multiline_str.splitlines():
            if line.startswith("«") or line.startswith("#"):
                pass
            else:
                newstring = newstring+line+" "
        return newstring    

    # SEMPLICI FUNZIONI PER ESTRARRE DATI PUNTUALI
    def getnode_id(self, node_element):
        id_node = str(node_element.attrib['id'])
        return id_node

    def getnode_edge_target(self, node_element):
        id_node_edge_target = str(node_element.attrib['target'])
        return id_node_edge_target

    def getnode_edge_source(self, node_element):
        id_node_edge_source = str(node_element.attrib['source'])
        return id_node_edge_source

    def _check_if_empty(self, name):
        if name == None:
            name = ""
        return name


