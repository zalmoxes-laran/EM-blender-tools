# S3Dgraphy/import_graphml.py

import xml.etree.ElementTree as ET
from .graph import Graph
from .node import (
    Node, StratigraphicNode, ParadataNode, DocumentNode,
    CombinerNode, ExtractorNode, PropertyNode, EpochNode, ActivityNode
)
from .edge import Edge

from .utils import convert_shape2type

class GraphMLImporter:
    def __init__(self, filepath, graph=None):
        self.filepath = filepath
        self.graph = graph if graph is not None else Graph()
    
    def parse(self):

        tree = ET.parse(self.filepath)
        
        self.parse_nodes(tree)

        self.parse_edges(tree)

        self.connect_nodes_to_epochs


        # aggiorna le cronologie dei nodi che non hanno continuity
        connected_nodes = self.graph.filter_nodes_by_connection_to_type("_continuity", connected=False)

        return self.graph

    def parse_edges(self,tree):

        alledges = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}edge')

        for edge in alledges:
            # Aggiunta del nodo al grafo
            self.graph.add_edge(str(edge.attrib['id']), str(edge.attrib['source']), str(edge.attrib['target']), self.EM_extract_edge_type(edge))

    def parse_nodes(self,tree):

        #extract nodes from GraphML
        allnodes = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}node')

        # Parse nodes and add them to the graph
        for node_element in allnodes:
            if self._check_node_type(node_element) == 'node_simple':
                if self.EM_check_node_us(node_element):
                    nodename, nodedescription, nodeurl, nodeshape, node_y_pos, fillcolor, borderstyle = self.EM_extract_node_name(node_element)
                        
                    # Creazione del nodo stratigrafico e aggiunta al grafo
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

                    # Aggiunta del nodo al grafo
                    self.graph.add_node(stratigraphic_node)

                elif self.EM_check_node_document(node_element):
                    src_nodename, src_node_id, src_node_description, src_nodeurl, subnode_is_document = self.EM_extract_document_node(node_element)

                    # Crea un nuovo DocumentNode e aggiungilo al grafo
                    document_node = DocumentNode(
                        node_id=src_node_id,
                        name=src_nodename,
                        description=src_node_description,
                        url=src_nodeurl  # Aggiungi l'url come argomento opzionale
                    )
                    self.graph.add_node(document_node)

                elif self.EM_check_node_property(node_element):
                    pro_nodename, pro_node_id, pro_node_description, pro_nodeurl, subnode_is_property = self.EM_extract_property_node(node_element)
                    property_node = PropertyNode(
                        node_id=pro_node_id,
                        name=pro_nodename,
                        description=pro_node_description,
                        value=pro_nodeurl
                    )
                    self.graph.add_node(property_node)

                elif self.EM_check_node_extractor(node_element):
                    ext_nodename, ext_node_id, ext_node_description, ext_nodeurl, subnode_is_extractor = self.EM_extract_extractor_node(node_element)
                    extractor_node = ExtractorNode(
                        node_id=ext_node_id,
                        name=ext_nodename,
                        description=ext_node_description,
                        source=ext_nodeurl
                    )
                    self.graph.add_node(extractor_node)
                    
                elif self.EM_check_node_combiner(node_element):
                    com_nodename, com_node_id, com_node_description, com_nodeurl, subnode_is_combiner = self.EM_extract_combiner_node(node_element)
                    combiner_node = CombinerNode(
                        node_id=com_node_id,
                        name=com_nodename,
                        description=com_node_description,
                        sources=[com_nodeurl]  # Assumendo che sources sia una lista di URL o ID
                    )
                    self.graph.add_node(combiner_node)

                elif self.EM_check_node_continuity(node_element):
                    continuity_node_id, y_pos = self.EM_extract_continuity(node_element)
                    continuity_node = Node(
                        node_id = continuity_node_id,
                        name = "continuity_node",
                        node_type= "_continuity",
                        description=y_pos
                    )
                    self.graph.add_node(continuity_node)

                else:
                    pass
        
            elif self._check_node_type(node_element) == 'node_swimlane':
                # Parsing dei nodi EpochNode
                self.extract_epochs(node_element, self.graph)

        '''
        #porzione di codice per estrarre le continuità
        for node_element in allnodes:
            if self._check_node_type(node_element) == 'node_simple': # The node is not a group or a swimlane
                if self.EM_check_node_continuity(node_element):
                    #print("found continuity node")
                    EM_us_target, continuity_y = self.get_edge_target(tree, node_element)
                    #print(EM_us_target+" has y value: "+str(continuity_y))
                    for EM_item in bpy.context.scene.em_list:
                        if EM_item.icon == "RESTRICT_INSTANCED_OFF":
                            if EM_item.name == EM_us_target:
                                for ep_i in range(len(scene.epoch_list)):
                                    #print("epoca "+epoch.name+" : min"+str(epoch.min_y)+" max: "+str(epoch.max_y)+" minore di "+str(continuity_y)+" e "+ str(epoch.min_y) +" minore di "+str(EM_item.y_pos))
                                    if scene.epoch_list[ep_i].max_y > continuity_y and scene.epoch_list[ep_i].max_y < EM_item.y_pos:
                                        #print("found")
                                        scene.em_reused.add()
                                        scene.em_reused[em_reused_index].epoch = scene.epoch_list[ep_i].name
                                        scene.em_reused[em_reused_index].em_element = EM_item.name
                                    #print("All'epoca "+scene.em_reused[em_reused_index].epoch+ " appartiene : "+ scene.em_reused[em_reused_index].em_element)
                                        em_reused_index += 1
        '''

    def ver2_extract_epochs(self, node_element, graph):
        geometry = node_element.find('.//{http://www.yworks.com/xml/graphml}Geometry')
        y_start = float(geometry.attrib['y'])
        
        y_min = y_start
        y_max = y_start

        # Otteniamo tutte le Row
        rows = node_element.findall('.//{http://www.yworks.com/xml/graphml}Row')
        # Otteniamo tutte le NodeLabel
        nodelabels = node_element.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel')

        # Supponendo che la prima NodeLabel sia l'etichetta principale del nodo (ad esempio, "Soqotra - SHP200"), la escludiamo
        main_label = nodelabels[0]
        epoch_labels = nodelabels[1:]

        # Controlliamo che il numero di Row e di NodeLabel (escluse le etichette principali) corrisponda
        if len(rows) != len(epoch_labels):
            print("Attenzione: il numero di Rows e NodeLabel non corrisponde.")
            # Gestisci questo caso come preferisci, ad esempio lanciando un'eccezione o prendendo altre misure

        # Iteriamo sulle Row e sulle NodeLabel corrispondenti
        for row, nodelabel in zip(rows, epoch_labels):
            id_row = row.attrib['id']
            h_row = float(row.attrib['height'])
            
            y_min = y_max
            y_max += h_row

            label_node = nodelabel.text.strip()
            e_color = nodelabel.attrib.get('backgroundColor', '#BCBCBC')

            epoch_node = EpochNode(
                node_id=id_row,
                name=label_node,
                start_time=0,
                end_time=2000
            )
            epoch_node.min_y = y_min
            epoch_node.max_y = y_max
            epoch_node.set_color = e_color
            self.graph.add_node(epoch_node)

        print(f"Row ID: {id_row}, Label: {label_node}, Color: {e_color}")


        return graph

    def ver0_extract_epochs(self, node_element, graph):
        geometry = node_element.find('.//{http://www.yworks.com/xml/graphml}Geometry')
        y_start = float(geometry.attrib['y'])
        
        y_min = y_start
        y_max = y_start

        # Creiamo una mappatura tra gli ID delle righe e le rispettive etichette e colori
        nodelabels_dict = {}
        for nodelabel in node_element.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
            RowNodeLabelModelParameter = nodelabel.find('.//{http://www.yworks.com/xml/graphml}RowNodeLabelModelParameter')
            if RowNodeLabelModelParameter is not None:
                label_node = nodelabel.text
                id_node = str(RowNodeLabelModelParameter.attrib['id'])
                e_color = str(nodelabel.attrib.get('backgroundColor', '#2C4187'))
                nodelabels_dict[id_node] = {
                    'name': label_node,
                    'color': e_color
                }

        # Iteriamo attraverso le righe e creiamo gli EpochNode con nome e colore
        for row in node_element.findall('.//{http://www.yworks.com/xml/graphml}Row'):
            id_row = row.attrib['id']
            h_row = float(row.attrib['height'])
            
            y_min = y_max
            y_max += h_row

            # Otteniamo il nome e il colore dalla mappatura, se disponibili
            label_info = nodelabels_dict.get(id_row, {'name': 'temp', 'color': '#2C4187'})
            name = label_info['name']
            color = label_info['color']

            epoch_node = EpochNode(
                node_id=id_row,
                name=name,
                start_time=0,
                end_time=2000
            )
            epoch_node.min_y = y_min
            epoch_node.max_y = y_max
            epoch_node.set_color = color
            self.graph.add_node(epoch_node)

        return graph

    #voglio ottimizzare questa funzione in modo che faccia un solo passaggio sui nodi
    def extract_epochs(self, node_element, graph):
        geometry = node_element.find('.//{http://www.yworks.com/xml/graphml}Geometry')
        y_start = float(geometry.attrib['y'])
        
        y_min = y_start
        y_max = y_start

        for row in node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}Table/{http://www.yworks.com/xml/graphml}Rows/{http://www.yworks.com/xml/graphml}Row'):
            id_row = row.attrib['id']
            h_row = float(row.attrib['height'])
            print(str(y_min))
            
            y_min = y_max
            y_max += h_row
            print(str(y_min))

        for nodelabel in row.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}NodeLabel'):
            RowNodeLabelModelParameter = nodelabel.find('.//{http://www.yworks.com/xml/graphml}RowNodeLabelModelParameter')
            if RowNodeLabelModelParameter is not None:
                label_node = nodelabel.text
                id_node = str(RowNodeLabelModelParameter.attrib['id'])
                if 'backgroundColor' in nodelabel.attrib:
                    e_color = str(nodelabel.attrib['backgroundColor'])
                else:
                    e_color = "#BCBCBC"
            else:
                id_node = "null"
                    
        epoch_node = EpochNode(
            node_id=id_row,
            name=label_node,
            start_time = 0,
            end_time = 2000,
            color = e_color
        )
        epoch_node.min_y = y_min
        epoch_node.max_y = y_max
        self.graph.add_node(epoch_node)
        
        return graph

    #voglio ottimizzare questa funzione in modo che faccia un solo passaggio sui nodi
    def ver0_extract_epochs(self, node_element, graph):
        geometry = node_element.find('.//{http://www.yworks.com/xml/graphml}Geometry')
        y_start = float(geometry.attrib['y'])
        
        y_min = y_start
        y_max = y_start

        for row in node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}Table/{http://www.yworks.com/xml/graphml}Rows/{http://www.yworks.com/xml/graphml}Row'):
            id_row = row.attrib['id']
            h_row = float(row.attrib['height'])
            print(str(y_min))
            
            y_min = y_max
            y_max += h_row
            print(str(y_min))
            
            epoch_node = EpochNode(
                node_id=id_row,
                name="temp",
                start_time = 0,
                end_time = 2000
            )
            epoch_node.min_y = y_min
            epoch_node.max_y = y_max
            self.graph.add_node(epoch_node)

        for nodelabel in node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}NodeLabel'):
            RowNodeLabelModelParameter = nodelabel.find('.//{http://www.yworks.com/xml/graphml}RowNodeLabelModelParameter')
            if RowNodeLabelModelParameter is not None:
                label_node = nodelabel.text
                id_node = str(RowNodeLabelModelParameter.attrib['id'])
                if 'backgroundColor' in nodelabel.attrib:
                    e_color = str(nodelabel.attrib['backgroundColor'])
                else:
                    e_color = "#BCBCBC"
            else:
                id_node = "null"
                    
            epoch_node = graph.find_node_by_id(id_node)

            if epoch_node:
                epoch_node.set_name = label_node
                epoch_node.set_color = e_color
                print(epoch_node.color)
                print(epoch_node.name)
                break
        return graph

    def connect_nodes_to_epochs(self):
        #define here a list of StratigraphicNode types that should be filled with a continuity node in the last epoch even if they do not have one. If no continuity node was set (end of life) we suppose that the US survives untill the last epoch
        list_of_surviving_stratigrafic_nodes = ["US", "serSU"]
        # Assegna le epoche ai nodi nel grafo in base alla posizione Y e tenendo in considerazione i nodi continuity
        for node in (node for node in self.graph.nodes if isinstance(node, StratigraphicNode)):
            connected_continuity_node = self.get_connected_node_by_type(self, node, "_continuity")
            # da qui in poi ho y_pos del nodo US e y_pos del nodo continuity
            # e per ogni epoca ho min e max
            # aggiungo il nodo all'epoca per ogni epoca che "contiene" le due y_pos
            # quindi if epoca_max >= intervallo_inizio e epoca_min <= intervallo_fine

            
            # qui si affrontano i nodi che SONO connessi a nodi continuity, per cui si bisogna iterare su tutte le epoche pertinenti per associarle al nodo
            if connected_continuity_node:
                for epoch in (node for node in self.graph.nodes if isinstance(node, EpochNode)):

                    if epoch.max_y >= node.pos_y and epoch.min_y <= connected_continuity_node.pos_y:
                        edge_id = node.node_id + "_" + epoch.name
                        self.graph.add_edge(edge_id, node.node_id, epoch.node_id, "has_epoch")                        
            
            # qui è il caso di nodi che NON sono connessi ad alcun nodo continuity
            else:
                # qui si filtrano nodi che inoltre appartengono ai resti fisici
                if node.node_type in list_of_surviving_stratigrafic_nodes:
                        
                    for epoch in (node for node in self.graph.nodes if isinstance(node, EpochNode)):
                        if node.attributes['y_pos'] < epoch.max_y:
                            edge_id = node.node_id + "_" + epoch.name
                            self.graph.add_edge(edge_id, node.node_id, epoch.node_id, "has_epoch")

                # qui si filtrano nodi che inoltre non appartengono ai resti fisici
                # in questo caso possiamo fermare il loop appena troviamo 
                else: 
                    for epoch in (node for node in self.graph.nodes if isinstance(node, EpochNode)):
                        if epoch.min_y < node.attributes['y_pos'] < epoch.max_y:
                            edge_id = node.node_id + "_" + epoch.name
                            self.graph.add_edge(edge_id, node.node_id, epoch.node_id, "has_epoch")
                            break

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
        my_node_description, my_node_y_pos = self.EM_extract_continuity(node_element)
        if my_node_description == "_continuity":
            id_node_continuity = True

        return id_node_continuity

    def EM_extract_continuity(self, node_element):
        is_d5 = False
        node_y_pos = 0.0
        nodedescription = None
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
        return nodedescription, node_y_pos 

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


