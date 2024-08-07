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

            if self._check_node_type(node_element) == 'node_swimlane':
                self.extract_epochs(node_element)

                for em_i in range(len(scene.em_list)):
                    for epoch_in in range(len(scene.epoch_list)):
                        if scene.epoch_list[epoch_in].min_y < scene.em_list[em_i].y_pos < scene.epoch_list[epoch_in].max_y:
                            scene.em_list[em_i].epoch = scene.epoch_list[epoch_in].name
