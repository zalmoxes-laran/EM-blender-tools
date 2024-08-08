    def import_graphml(self, context):
        scene = context.scene
        graphml_file = bpy.path.abspath(scene.EM_file)
        tree = ET.parse(graphml_file)
        EM_list_clear(context, "em_list")
        EM_list_clear(context, "em_reused")
        EM_list_clear(context, "em_sources_list")
        EM_list_clear(context, "em_properties_list")
        EM_list_clear(context, "em_extractors_list")
        EM_list_clear(context, "em_combiners_list")
        em_list_index_ema = 0
        em_reused_index = 0
        em_sources_index_ema = 0
        em_properties_index_ema = 0
        em_extractors_index_ema = 0
        em_combiners_index_ema = 0

        allnodes = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}node')

        # leggo l'albero xml e popolo tutti gli edges
        self.read_edge_db(context,tree)

        for node_element in allnodes:
            if self._check_node_type(node_element) == 'node_simple': # The node is not a group or a swimlane
                if self.EM_check_node_us(node_element): # Check if the node is an US, SU, USV, USM or USR node
                    my_nodename, my_node_description, my_node_url, my_node_shape, my_node_y_pos, my_node_fill_color = self.EM_extract_node_name(node_element)
                    scene.em_list.add()
                    scene.em_list[em_list_index_ema].name = my_nodename
                    scene.em_list[em_list_index_ema].icon = check_objs_in_scene_and_provide_icon_for_list_element(my_nodename)
                    scene.em_list[em_list_index_ema].y_pos = float(my_node_y_pos)
                    scene.em_list[em_list_index_ema].description = my_node_description
                        #print(my_node_shape)
                    if my_node_fill_color == '#FFFFFF':
                        if my_node_shape == "ellipse" or my_node_shape == "octagon":
                            scene.em_list[em_list_index_ema].shape = my_node_shape+"_white"
                        else:
                            scene.em_list[em_list_index_ema].shape = my_node_shape
                    else:
                        scene.em_list[em_list_index_ema].shape = my_node_shape
                    scene.em_list[em_list_index_ema].id_node = self.getnode_id(node_element)
                    em_list_index_ema += 1

                elif self.EM_check_node_document(node_element):
                    source_already_in_list = False
                    source_number = 2
                    src_nodename, src_node_id, src_node_description, src_nodeurl, subnode_is_document = self.EM_extract_document_node(node_element)
                    src_nodename_safe = src_nodename
                    if em_sources_index_ema > 0: 
                        for source_item in scene.em_sources_list:
                            if source_item.name == src_nodename:
                                source_already_in_list = True
                                #finding the node in the edges list
                                for id_doc_node in scene.edges_list:
                                    if id_doc_node.target == src_node_id:
                                        id_doc_node.target = source_item.id_node

                    if not source_already_in_list:
                        #src_nodename = src_nodename+"_"+str(source_number)
                        #source_number +=1
                        scene.em_sources_list.add()
                        scene.em_sources_list[em_sources_index_ema].name = src_nodename
                        scene.em_sources_list[em_sources_index_ema].icon = check_objs_in_scene_and_provide_icon_for_list_element(src_nodename_safe)
                        scene.em_sources_list[em_sources_index_ema].id_node = src_node_id
                        scene.em_sources_list[em_sources_index_ema].url = src_nodeurl
                        if src_nodeurl == "":
                            scene.em_sources_list[em_sources_index_ema].icon_url = "CHECKBOX_DEHLT"
                        else:
                            scene.em_sources_list[em_sources_index_ema].icon_url = "CHECKBOX_HLT"
                        scene.em_sources_list[em_sources_index_ema].description = src_node_description
                        em_sources_index_ema += 1

                elif self.EM_check_node_property(node_element):
                    pro_nodename, pro_node_id, pro_node_description, pro_nodeurl, subnode_is_property = self.EM_extract_property_node(node_element)
                    scene.em_properties_list.add()
                    scene.em_properties_list[em_properties_index_ema].name = pro_nodename
                    scene.em_properties_list[em_properties_index_ema].icon = check_objs_in_scene_and_provide_icon_for_list_element(pro_nodename)
                    scene.em_properties_list[em_properties_index_ema].id_node = pro_node_id
                    scene.em_properties_list[em_properties_index_ema].url = pro_nodeurl
                    if pro_nodeurl == "":
                        scene.em_properties_list[em_properties_index_ema].icon_url = "CHECKBOX_DEHLT"
                    else:
                        scene.em_properties_list[em_properties_index_ema].icon_url = "CHECKBOX_HLT"
                    scene.em_properties_list[em_properties_index_ema].description = pro_node_description
                    em_properties_index_ema += 1

                elif self.EM_check_node_extractor(node_element):
                    ext_nodename, ext_node_id, ext_node_description, ext_nodeurl, subnode_is_extractor = self.EM_extract_extractor_node(node_element)
                    scene.em_extractors_list.add()
                    scene.em_extractors_list[em_extractors_index_ema].name = ext_nodename
                    scene.em_extractors_list[em_extractors_index_ema].id_node = ext_node_id                   
                    scene.em_extractors_list[em_extractors_index_ema].icon = check_objs_in_scene_and_provide_icon_for_list_element(ext_nodename)
                    scene.em_extractors_list[em_extractors_index_ema].url = ext_nodeurl
                   #print(ext_nodeurl)
                    if ext_nodeurl == "":
                        scene.em_extractors_list[em_extractors_index_ema].icon_url = "CHECKBOX_DEHLT"
                    else:
                        scene.em_extractors_list[em_extractors_index_ema].icon_url = "CHECKBOX_HLT"
                    scene.em_extractors_list[em_extractors_index_ema].description = ext_node_description
                    em_extractors_index_ema += 1
                elif self.EM_check_node_combiner(node_element):
                    ext_nodename, ext_node_id, ext_node_description, ext_nodeurl, subnode_is_combiner = self.EM_extract_combiner_node(node_element)
                    scene.em_combiners_list.add()
                    scene.em_combiners_list[em_combiners_index_ema].name = ext_nodename
                    scene.em_combiners_list[em_combiners_index_ema].id_node = ext_node_id                   
                    scene.em_combiners_list[em_combiners_index_ema].icon = check_objs_in_scene_and_provide_icon_for_list_element(ext_nodename)
                    scene.em_combiners_list[em_combiners_index_ema].url = ext_nodeurl
                   #print(ext_nodeurl)
                    if ext_nodeurl == "":
                        scene.em_combiners_list[em_combiners_index_ema].icon_url = "CHECKBOX_DEHLT"
                    else:
                        scene.em_combiners_list[em_combiners_index_ema].icon_url = "CHECKBOX_HLT"
                    scene.em_combiners_list[em_combiners_index_ema].description = ext_node_description
                    em_combiners_index_ema += 1

            if self._check_node_type(node_element) == 'node_swimlane':
                self.extract_epochs(node_element)

                for em_i in range(len(scene.em_list)):
                    for epoch_in in range(len(scene.epoch_list)):
                        if scene.epoch_list[epoch_in].min_y < scene.em_list[em_i].y_pos < scene.epoch_list[epoch_in].max_y:
                            scene.em_list[em_i].epoch = scene.epoch_list[epoch_in].name



    def extract_epochs(self, node_element):
        geometry = node_element.find('.//{http://www.yworks.com/xml/graphml}Geometry')
        y_start = float(geometry.attrib['y'])
        context = bpy.context
        scene = context.scene    
        EM_list_clear(context, "epoch_list")  
        epoch_list_index_ema = 0
        y_min = y_start
        y_max = y_start

        for row in node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}Table/{http://www.yworks.com/xml/graphml}Rows/{http://www.yworks.com/xml/graphml}Row'):
            id_row = row.attrib['id']
            h_row = float(row.attrib['height'])
            
            scene.epoch_list.add()
            scene.epoch_list[epoch_list_index_ema].id = str(id_row)
            scene.epoch_list[epoch_list_index_ema].height = h_row
            
            y_min = y_max
            y_max += h_row
            scene.epoch_list[epoch_list_index_ema].min_y = y_min
            scene.epoch_list[epoch_list_index_ema].max_y = y_max
            #print(str(id_row))
            epoch_list_index_ema += 1        

        for nodelabel in node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}NodeLabel'):
            RowNodeLabelModelParameter = nodelabel.find('.//{http://www.yworks.com/xml/graphml}RowNodeLabelModelParameter')
            if RowNodeLabelModelParameter is not None:
                label_node = nodelabel.text
                id_node = str(RowNodeLabelModelParameter.attrib['id'])
                # read the color of the epoch from the title of the row, if no color is provided, a default color is used
                if 'backgroundColor' in nodelabel.attrib:
                    e_color = str(nodelabel.attrib['backgroundColor'])
                    #print(e_color)
                else:
                    e_color = "#BCBCBC"
                #print(e_color)
            else:
                id_node = "null"
                
            for i in range(len(scene.epoch_list)):
                id_key = scene.epoch_list[i].id
                if id_node == id_key:
                    scene.epoch_list[i].name = str(label_node)
                    scene.epoch_list[i].epoch_color = e_color
                    scene.epoch_list[i].epoch_RGB_color = hex_to_rgb(e_color)