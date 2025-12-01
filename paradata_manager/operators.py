"""Operator implementations for the Paradata Manager."""

import os
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urlparse

import bpy
from bpy.props import StringProperty  # type: ignore

from ..functions import (
    check_objs_in_scene_and_provide_icon_for_list_element,
    is_valid_url,
)

# Variabili globali per tracciare lo stato degli aggiornamenti
_paradata_update_in_progress = False
_paradata_refresh_needed = False


def set_paradata_update_state(state):
    global _paradata_update_in_progress, _paradata_refresh_needed
    if state and _paradata_update_in_progress:
        _paradata_refresh_needed = True
        return False
    _paradata_update_in_progress = state
    return True


def check_selection_changed(context):
    """Check if selection has changed and load images if needed."""
    scene = context.scene

    if not hasattr(scene, "paradata_image") or not scene.paradata_image.auto_load:
        return

    if (
        hasattr(scene, "em_v_sources_list_index")
        and scene.em_tools.em_v_sources_list_index >= 0
        and scene.em_tools.em_v_sources_list_index != scene.paradata_image.last_source_index
    ):
        scene.paradata_image.last_source_index = scene.em_tools.em_v_sources_list_index
        if len(scene.em_v_sources_list) > 0:
            auto_load_paradata_image(context, "em_v_sources_list")

    if (
        hasattr(scene, "em_v_extractors_list_index")
        and scene.em_tools.em_v_extractors_list_index >= 0
        and scene.em_tools.em_v_extractors_list_index != scene.paradata_image.last_extractor_index
    ):
        scene.paradata_image.last_extractor_index = scene.em_tools.em_v_extractors_list_index
        if len(scene.em_v_extractors_list) > 0:
            auto_load_paradata_image(context, "em_v_extractors_list")


def auto_load_paradata_image(context, node_type):
    """Helper function for auto-loading images when selection changes."""
    scene = context.scene

    if not hasattr(scene, "paradata_image") or not scene.paradata_image.auto_load:
        return

    if scene.paradata_image.is_loading:
        return

    url = None
    if (
        node_type == "em_v_sources_list"
        and scene.em_tools.em_v_sources_list_index >= 0
        and len(scene.em_v_sources_list) > 0
    ):
        url = scene.em_v_sources_list[scene.em_tools.em_v_sources_list_index].url
    elif (
        node_type == "em_v_extractors_list"
        and scene.em_tools.em_v_extractors_list_index >= 0
        and len(scene.em_v_extractors_list) > 0
    ):
        url = scene.em_v_extractors_list[scene.em_tools.em_v_extractors_list_index].url

    if not url:
        return

    is_web_url = url.startswith(("http://", "https://"))
    img_exts = [".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".gif"]
    is_potential_image = any(url.lower().endswith(ext) for ext in img_exts)

    if is_web_url and not is_potential_image:
        is_potential_image = any(ext in url.lower() for ext in img_exts)

    if is_potential_image or not is_web_url:
        bpy.ops.em.load_paradata_image(node_type=node_type)


class EM_OT_load_paradata_image(bpy.types.Operator):
    """Load an image from a URL or file path for the Paradata Manager."""

    bl_idname = "em.load_paradata_image"
    bl_label = "Load Paradata Image"
    bl_description = "Load an image from a URL or local file for preview"

    node_type: StringProperty()  # type: ignore

    def is_valid_url(self, url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def build_file_path(self, context, path):
        """Build a proper file path based on context and path information."""
        scene = context.scene
        em_tools = scene.em_tools

        if self.is_valid_url(path):
            return path, True

        if em_tools.active_file_index < 0 or not em_tools.graphml_files:
            return None, False

        graphml = em_tools.graphml_files[em_tools.active_file_index]
        dosco_dir = graphml.dosco_dir
        if not dosco_dir:
            dosco_dir = scene.EMDosCo_dir

        if not dosco_dir:
            return None, False

        dosco_dir = bpy.path.abspath(dosco_dir)
        path_variants = [
            path,
            path.split("/")[-1],
            os.path.basename(path),
        ]

        graph_code = graphml.graph_code if hasattr(graphml, "graph_code") else None
        if graph_code:
            path_variants.append(f"{graph_code}.{path}")
            path_variants.append(path.replace(f"{graph_code}.", ""))

        for variant in path_variants:
            variant_path = variant[1:] if variant.startswith(os.path.sep) else variant
            full_path = variant_path if variant_path.startswith(dosco_dir) else os.path.join(dosco_dir, variant_path)
            if os.path.exists(full_path):
                return os.path.normpath(full_path), False

        return None, False

    def execute(self, context):
        scene = context.scene
        path = eval("scene." + self.node_type + "[scene." + self.node_type + "_index].url")

        if scene.paradata_image.is_loading or not path:
            return {"CANCELLED"}

        if scene.paradata_image.loaded_image:
            bpy.data.images.remove(scene.paradata_image.loaded_image)
            scene.paradata_image.loaded_image = None

        scene.paradata_image.is_loading = True
        scene.paradata_image.image_path = path

        try:
            full_path, is_url = self.build_file_path(context, path)
            if not full_path:
                self.report({"ERROR"}, f"Cannot resolve path: {path}. Check DosCo directory settings.")
                scene.paradata_image.is_loading = False
                return {"CANCELLED"}

            if is_url:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                temp_file.close()
                urllib.request.urlretrieve(full_path, temp_file.name)
                img = bpy.data.images.load(temp_file.name)
                img.name = f"ParadataPreview_{os.path.basename(path)}"
                img.use_fake_user = False
                os.unlink(temp_file.name)
            else:
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    img_exts = [".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"]
                    if any(full_path.lower().endswith(ext) for ext in img_exts):
                        img = bpy.data.images.load(full_path)
                        img.name = f"ParadataPreview_{os.path.basename(path)}"
                        img.use_fake_user = False
                    else:
                        self.report({"WARNING"}, f"Not an image file: {full_path}")
                        scene.paradata_image.is_loading = False
                        return {"CANCELLED"}
                else:
                    self.report({"WARNING"}, f"File not found: {full_path}")
                    scene.paradata_image.is_loading = False
                    return {"CANCELLED"}

            scene.paradata_image.loaded_image = img
        except Exception as exc:
            self.report({"ERROR"}, f"Error loading image: {exc}")
            scene.paradata_image.is_loading = False
            return {"CANCELLED"}

        scene.paradata_image.is_loading = False
        return {"FINISHED"}


class EM_OT_save_paradata_image(bpy.types.Operator):
    """Save the displayed paradata image to disk."""

    bl_idname = "em.save_paradata_image"
    bl_label = "Save Paradata Image"
    bl_description = "Save the displayed image to disk"

    filepath: StringProperty(
        subtype="FILE_PATH",
        options={"PATH_SUPPORTS_BLEND_RELATIVE"} if bpy.app.version >= (4, 5, 0) else set(),
    )  # type: ignore

    def execute(self, context):
        scene = context.scene
        if not scene.paradata_image.loaded_image:
            self.report({"ERROR"}, "No image loaded")
            return {"CANCELLED"}

        try:
            scene.paradata_image.loaded_image.save_render(self.filepath)
            self.report({"INFO"}, f"Image saved to {self.filepath}")
        except Exception as exc:
            self.report({"ERROR"}, f"Error saving image: {exc}")
            return {"CANCELLED"}

        return {"FINISHED"}

    def invoke(self, context, event):
        scene = context.scene
        if scene.paradata_image.image_path:
            base_name = os.path.basename(scene.paradata_image.image_path)
            self.filepath = base_name
        else:
            self.filepath = "paradata_image.png"

        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


def sources_index_update(self, context):
    """Function to call when sources list index changes."""
    if hasattr(context.scene, "paradata_image") and context.scene.paradata_image.auto_load:
        auto_load_paradata_image(context, "em_v_sources_list")


def extractors_index_update(self, context):
    """Function to call when extractors list index changes."""
    if hasattr(context.scene, "paradata_image") and context.scene.paradata_image.auto_load:
        auto_load_paradata_image(context, "em_v_extractors_list")


class EM_OT_previous_image(bpy.types.Operator):
    """Go to previous image."""

    bl_idname = "em.previous_image"
    bl_label = "Previous Image"

    def execute(self, context):
        scene = context.scene
        images = scene.paradata_image.image_collection
        if len(images) > 1:
            scene.paradata_image.active_image_index = (scene.paradata_image.active_image_index - 1) % len(images)
        return {"FINISHED"}


class EM_OT_next_image(bpy.types.Operator):
    """Go to next image."""

    bl_idname = "em.next_image"
    bl_label = "Next Image"

    def execute(self, context):
        scene = context.scene
        images = scene.paradata_image.image_collection
        if len(images) > 1:
            scene.paradata_image.active_image_index = (scene.paradata_image.active_image_index + 1) % len(images)
        return {"FINISHED"}


class EM_files_opener(bpy.types.Operator):
    """Open a local file or URL from the paradata lists."""

    bl_idname = "open.file"
    bl_label = "Open a file using external software or a url using the default system browser"
    bl_options = {"REGISTER", "UNDO"}

    node_type: StringProperty()  # type: ignore

    def execute(self, context):
        scene = context.scene
        file_res_path = eval("scene." + self.node_type + "[scene." + self.node_type + "_index].url")

        if is_valid_url(file_res_path):
            bpy.ops.wm.url_open(url=file_res_path)
            return {"FINISHED"}

        if scene.em_tools.active_file_index >= 0 and scene.em_tools.graphml_files:
            graphml = scene.em_tools.graphml_files[scene.em_tools.active_file_index]
            dosco_dir = graphml.dosco_dir
            if dosco_dir:
                basedir = bpy.path.abspath(dosco_dir)
                path_to_file = os.path.join(basedir, file_res_path)
                if os.path.exists(path_to_file):
                    try:
                        if os.name == "nt":
                            os.startfile(path_to_file)
                        elif os.name == "posix":
                            opener = "open" if sys.platform == "darwin" else "xdg-open"
                            subprocess.run([opener, path_to_file])
                    except Exception as exc:
                        self.report({"WARNING"}, f"Cannot open file: {exc}")
                        return {"CANCELLED"}
                else:
                    self.report({"WARNING"}, f"File not found: {path_to_file}")
            else:
                self.report({"WARNING"}, "DosCo directory not set for the active GraphML file")
        else:
            self.report({"WARNING"}, "No active GraphML file")

        return {"FINISHED"}


class EM_OT_update_paradata_lists(bpy.types.Operator):
    bl_idname = "em.update_paradata_lists"
    bl_label = "Update Paradata Lists"
    bl_description = "Update all paradata lists based on streaming settings"

    def execute(self, context):
        global _paradata_update_in_progress, _paradata_refresh_needed

        scene = context.scene
        em_tools = context.scene.em_tools

        if _paradata_update_in_progress:
            _paradata_refresh_needed = True
            return {"FINISHED"}

        _paradata_update_in_progress = True

        try:
            scene.em_v_properties_list.clear()
            scene.em_v_combiners_list.clear()
            scene.em_v_extractors_list.clear()
            scene.em_v_sources_list.clear()

            if em_tools.active_file_index < 0 or not em_tools.graphml_files:
                set_paradata_update_state(False)
                return {"FINISHED"}

            graphml = em_tools.graphml_files[em_tools.active_file_index]
            from s3dgraphy import get_graph

            graph = get_graph(graphml.name)
            if not graph:
                set_paradata_update_state(False)
                return {"FINISHED"}

            strat = scene.em_tools.stratigraphy
            strat_node_id = None
            if scene.em_tools.paradata_streaming_mode and strat.units_index >= 0 and len(strat.units) > 0:
                strat_node_id = strat.units[strat.units_index].id_node

            self.update_property_list(scene, graph, strat_node_id)

            if len(scene.em_v_properties_list) > 0:
                if scene.em_tools.em_v_properties_list_index >= len(scene.em_v_properties_list):
                    scene.em_tools.em_v_properties_list_index = 0

                if (
                    scene.em_tools.em_v_properties_list_index >= 0
                    and scene.em_tools.em_v_properties_list_index < len(scene.em_v_properties_list)
                    and hasattr(scene.em_v_properties_list[scene.em_tools.em_v_properties_list_index], "id_node")
                ):
                    prop_node_id = scene.em_v_properties_list[scene.em_tools.em_v_properties_list_index].id_node
                    self.update_combiner_list(scene, graph, prop_node_id)
                    self.update_extractor_list(scene, graph, prop_node_id)

                if len(scene.em_v_extractors_list) > 0:
                    if scene.em_tools.em_v_extractors_list_index >= len(scene.em_v_extractors_list):
                        scene.em_tools.em_v_extractors_list_index = 0

                    if scene.em_tools.em_v_extractors_list_index >= 0:
                        ext_node_id = scene.em_v_extractors_list[scene.em_tools.em_v_extractors_list_index].id_node
                        self.update_document_list(scene, graph, ext_node_id)
            else:
                scene.em_tools.em_v_properties_list_index = -1
                scene.em_v_combiners_list.clear()
                scene.em_v_extractors_list.clear()
                scene.em_v_sources_list.clear()
                scene.em_tools.em_v_combiners_list_index = -1
                scene.em_tools.em_v_extractors_list_index = -1
                scene.em_tools.em_v_sources_list_index = -1

            try:
                if hasattr(context, "area") and context.area:
                    context.area.tag_redraw()
            except AttributeError:
                pass

            return {"FINISHED"}

        except Exception as exc:
            self.report({"ERROR"}, f"Error updating paradata lists: {exc}")
            import traceback

            traceback.print_exc()
            return {"CANCELLED"}

        finally:
            set_paradata_update_state(False)
            if _paradata_refresh_needed and scene.em_tools.paradata_auto_update:
                _paradata_refresh_needed = False
                print("Update needed but skipped - use Refresh button for manual update")

            _paradata_update_in_progress = False

    def update_property_list(self, scene, graph, strat_node_id=None):
        """Aggiorna la lista delle proprietà con controlli di sicurezza."""
        scene.em_v_properties_list.clear()

        if strat_node_id:
            prop_nodes = graph.get_property_nodes_for_node(strat_node_id)
        else:
            prop_nodes = [node for node in graph.nodes if hasattr(node, "node_type") and node.node_type == "property"]

        for prop_node in prop_nodes:
            item = scene.em_v_properties_list.add()
            item.name = prop_node.name
            item.description = prop_node.description if hasattr(prop_node, "description") else ""
            item.url = prop_node.value if hasattr(prop_node, "value") else ""
            try:
                item.icon = check_objs_in_scene_and_provide_icon_for_list_element(prop_node.name)
            except Exception:
                item.icon = "RESTRICT_INSTANCED_ON"

            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = prop_node.node_id

    def update_combiner_list(self, scene, graph, prop_node_id):
        """Aggiorna la lista dei combiner in modo sicuro."""
        scene.em_v_combiners_list.clear()

        if not scene.em_tools.prop_paradata_streaming_mode:
            combiners = [node for node in graph.nodes if hasattr(node, "node_type") and node.node_type == "combiner"]
        else:
            try:
                combiners = graph.get_combiner_nodes_for_property(prop_node_id)
            except Exception:
                combiners = []

        for combiner in combiners:
            item = scene.em_v_combiners_list.add()
            item.name = combiner.name if hasattr(combiner, "name") and combiner.name is not None else ""
            item.description = (
                combiner.description if hasattr(combiner, "description") and combiner.description is not None else ""
            )
            if hasattr(combiner, "url") and combiner.url is not None:
                item.url = combiner.url
            elif hasattr(combiner, "sources") and combiner.sources and len(combiner.sources) > 0:
                item.url = combiner.sources[0]
            else:
                item.url = ""

            try:
                item.icon = check_objs_in_scene_and_provide_icon_for_list_element(combiner.name)
            except Exception:
                item.icon = "RESTRICT_INSTANCED_ON"

            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = combiner.node_id

        if len(scene.em_v_combiners_list) > 0:
            if scene.em_tools.em_v_combiners_list_index >= len(scene.em_v_combiners_list):
                scene.em_tools.em_v_combiners_list_index = 0
        else:
            scene.em_tools.em_v_combiners_list_index = -1

    def update_extractor_list(self, scene, graph, node_id):
        """Aggiorna la lista degli estrattori in modo sicuro."""
        scene.em_v_extractors_list.clear()
        extractors = []

        if scene.em_tools.prop_paradata_streaming_mode:
            try:
                property_extractors = graph.get_extractor_nodes_for_node(node_id)
                extractors.extend(property_extractors)

                if (
                    scene.em_tools.comb_paradata_streaming_mode
                    and scene.em_tools.em_v_combiners_list_index >= 0
                    and len(scene.em_v_combiners_list) > 0
                ):
                    comb_node_id = scene.em_v_combiners_list[scene.em_tools.em_v_combiners_list_index].id_node
                    combiner_extractors = graph.get_extractor_nodes_for_node(comb_node_id)
                    extractors.extend(combiner_extractors)
            except Exception:
                pass
        else:
            extractors = [node for node in graph.nodes if hasattr(node, "node_type") and node.node_type == "extractor"]

        seen = set()
        unique_extractors = []
        for node in extractors:
            if hasattr(node, "node_id") and node.node_id not in seen:
                seen.add(node.node_id)
                unique_extractors.append(node)

        for extractor in unique_extractors:
            item = scene.em_v_extractors_list.add()
            item.name = extractor.name if hasattr(extractor, "name") and extractor.name is not None else ""
            item.description = (
                extractor.description if hasattr(extractor, "description") and extractor.description is not None else ""
            )
            if hasattr(extractor, "source") and extractor.source is not None:
                item.url = extractor.source
            elif hasattr(extractor, "url") and extractor.url is not None:
                item.url = extractor.url
            else:
                item.url = ""

            try:
                item.icon = check_objs_in_scene_and_provide_icon_for_list_element(extractor.name)
            except Exception:
                item.icon = "RESTRICT_INSTANCED_ON"

            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = extractor.node_id

        if len(scene.em_v_extractors_list) > 0:
            if scene.em_tools.em_v_extractors_list_index >= len(scene.em_v_extractors_list):
                scene.em_tools.em_v_extractors_list_index = 0
        else:
            scene.em_tools.em_v_extractors_list_index = -1

    def update_document_list(self, scene, graph, extractor_id):
        """Aggiorna la lista dei documenti in modo sicuro."""
        scene.em_v_sources_list.clear()

        if scene.em_tools.extr_paradata_streaming_mode:
            try:
                documents = graph.get_document_nodes_for_extractor(extractor_id)
            except Exception:
                documents = []
        else:
            documents = [node for node in graph.nodes if hasattr(node, "node_type") and node.node_type == "document"]

        for doc in documents:
            item = scene.em_v_sources_list.add()
            item.name = doc.name if hasattr(doc, "name") and doc.name is not None else ""
            item.description = doc.description if hasattr(doc, "description") and doc.description is not None else ""
            item.url = doc.url if hasattr(doc, "url") and doc.url is not None else ""

            try:
                item.icon = check_objs_in_scene_and_provide_icon_for_list_element(doc.name)
            except Exception:
                item.icon = "RESTRICT_INSTANCED_ON"

            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = doc.node_id

        if len(scene.em_v_sources_list) > 0:
            if scene.em_tools.em_v_sources_list_index >= len(scene.em_v_sources_list):
                scene.em_tools.em_v_sources_list_index = 0
        else:
            scene.em_tools.em_v_sources_list_index = -1


classes = (
    EM_OT_load_paradata_image,
    EM_OT_save_paradata_image,
    EM_OT_previous_image,
    EM_OT_next_image,
    EM_files_opener,
    EM_OT_update_paradata_lists,
)


def register_operators():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister_operators():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
