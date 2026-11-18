"""The operators of the community packages (MICRO-PL12, W9).

Install from disk (a .zip, or a folder through its ``em-extension.toml`` /
``profile.json``) with the confirmation of the two panels; remove with the
unticked box of the vocabularies (D-19); open the machine folder; apply a
package's colour scheme; take a Proxy Box point from the graph; make an areale
from a surface placed in the graph; compute the measures the packages declare.
The work is in ``core.py`` (no bpy) and in s3Dgraphy.
"""
from __future__ import annotations

import os

import bpy  # type: ignore
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty  # type: ignore
from bpy.types import Operator  # type: ignore
from bpy_extras.io_utils import ImportHelper  # type: ignore

from . import core
from .i18n import tr


# ── context ─────────────────────────────────────────────────────────────────

def lang() -> str:
    try:
        from ..vocabulary_labels import blender_lang
        return blender_lang(getattr(bpy.app.translations, "locale", ""))
    except Exception:  # noqa: BLE001
        return "en"


def active_row(context):
    em_tools = getattr(context.scene, "em_tools", None)
    if em_tools is None or not (0 <= em_tools.active_file_index < len(em_tools.graphml_files)):
        return None
    return em_tools.graphml_files[em_tools.active_file_index]


def active_graph(context):
    row = active_row(context)
    if row is None:
        return None
    try:
        from s3dgraphy import get_graph
        return get_graph(row.name)
    except Exception:  # noqa: BLE001
        return None


def active_container(context):
    """The container the active graph's em.json was opened as (None: a room,
    a GraphML, a graph with no file)."""
    row = active_row(context)
    if row is None:
        return None
    try:
        from .. import graph_origins
        origin = graph_origins.origin_of(row, abspath=bpy.path.abspath)
        return graph_origins.remembered(origin.path) if origin.is_emjson else None
    except Exception:  # noqa: BLE001
        return None


def active_state(context):
    """``(overlay, missing, problems, declared_names)`` of the active file —
    its ``header.profiles`` plus the packages installed here (core.active_overlay)."""
    return core.overlay_cached(core.declared_of(active_container(context)))


def _redraw(context):
    for window in getattr(context.window_manager, "windows", []):
        for area in window.screen.areas:
            area.tag_redraw()


def _source_of(path: str) -> str:
    """A .zip is itself; a file inside a package folder means its folder."""
    path = bpy.path.abspath(path)
    if os.path.isdir(path) or path.lower().endswith(".zip"):
        return path
    return os.path.dirname(path)


# ── install ─────────────────────────────────────────────────────────────────

class EMPKG_OT_install_from_disk(Operator, ImportHelper):
    bl_idname = "empkg.install_from_disk"
    bl_label = "Install from disk…"
    bl_description = "Choose a .zip, or the em-extension.toml / profile.json of a folder"

    filter_glob: StringProperty(default="*.zip;em-extension.toml;profile.json", options={'HIDDEN'})  # type: ignore

    def execute(self, context):
        bpy.ops.empkg.confirm_install('INVOKE_DEFAULT', source=_source_of(self.filepath))
        return {'FINISHED'}


_preview_cache = {}


class EMPKG_OT_confirm_install(Operator):
    bl_idname = "empkg.confirm_install"
    bl_label = "Install the community package"
    bl_options = {'INTERNAL'}

    source: StringProperty(options={'HIDDEN'})  # type: ignore

    def invoke(self, context, event):
        _, X = core.library()
        if X is None:
            self.report({'ERROR'}, tr("The bundled s3dgraphy has no community packages (older than dev117)"))
            return {'CANCELLED'}
        try:
            pv = X.preview(self.source)
        except Exception as exc:  # noqa: BLE001 — not a package: the library says why
            self.report({'ERROR'}, tr("Not installed: {why}").format(why="; ".join(core.error_texts(exc, lang()))))
            return {'CANCELLED'}
        _preview_cache[self.source] = pv
        return context.window_manager.invoke_props_dialog(self, width=560, confirm_text=tr("Install the data"))

    def draw(self, context):
        pv = _preview_cache.get(self.source) or {}
        col = self.layout.column(align=True)
        for text, icon, level in core.preview_lines(pv, lang(), tr):
            row = col.row()
            row.alert = level == "error"
            row.label(text=text, icon=icon)
        plan = core.plan_install(pv)
        if plan["action"] == "refuse" and plan["why"] == "plugin_only":
            row = col.row()
            row.alert = True
            row.label(text=tr("A plugin with no data: EM Tools does not run plugins yet. Install it in "
                              "EMStudio (Tools ▸ Extensions…)"), icon='ERROR')

    def execute(self, context):
        lg = lang()
        pv = _preview_cache.pop(self.source, None)
        if pv is None:                  # run without the dialog (a script, -b)
            try:
                pv = core.library()[1].preview(self.source)
            except Exception as exc:  # noqa: BLE001
                self.report({'ERROR'}, tr("Not installed: {why}").format(why="; ".join(core.error_texts(exc, lg))))
                return {'CANCELLED'}
        plan = core.plan_install(pv)
        if plan["action"] != "data":
            why = (tr("A plugin with no data: EM Tools does not run plugins yet. Install it in EMStudio "
                      "(Tools ▸ Extensions…)") if plan["why"] == "plugin_only"
                   else "; ".join(core.problem_text(p, lg) for p in pv.get("errors") or []))
            self.report({'ERROR'}, tr("Not installed: {why}").format(why=why))
            return {'CANCELLED'}
        try:
            core.install_data(self.source)
        except Exception as exc:  # noqa: BLE001 — nothing written, the library says why
            self.report({'ERROR'}, tr("Not installed: {why}").format(why="; ".join(core.error_texts(exc, lg))))
            return {'CANCELLED'}
        core.forget_cache()
        name = pv.get("name") or pv.get("id")
        msg = ("Installed: {name} {version} (data; the code left out)" if plan.get("code_left_out")
               else "Installed: {name} {version} (data)")
        self.report({'INFO'}, tr(msg).format(name=name, version=pv.get("version") or ""))
        _redraw(context)
        return {'FINISHED'}


# ── remove ──────────────────────────────────────────────────────────────────

class EMPKG_OT_remove(Operator):
    bl_idname = "empkg.remove"
    bl_label = "Remove"
    bl_description = "Remove this community package from the computer (EMStudio's too); its vocabularies stay"
    bl_options = {'INTERNAL'}

    package_id: StringProperty(options={'HIDDEN'})  # type: ignore
    purge_vocabularies: BoolProperty(name="Remove its vocabularies too", default=False)  # type: ignore

    def invoke(self, context, event):
        self.purge_vocabularies = False
        return context.window_manager.invoke_props_dialog(self, width=480, confirm_text=tr("Remove"))

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text=tr("Remove the package {name}?").format(name=self.package_id), icon='TRASH')
        col.label(text=tr("Its data and its code leave this computer, for EMStudio too"), icon='BLANK1')
        only = core.vocabularies_only_here(self.package_id)
        if only:
            col.label(text=tr("Its vocabularies stay (like fonts): {names}").format(names=", ".join(only)),
                      icon='BLANK1')
            col.prop(self, "purge_vocabularies")

    def execute(self, context):
        try:
            core.remove_package(self.package_id, purge_vocabularies=self.purge_vocabularies)
        except Exception as exc:  # noqa: BLE001
            self.report({'ERROR'}, "; ".join(core.error_texts(exc, lang())))
            return {'CANCELLED'}
        core.forget_cache()
        self.report({'INFO'}, tr("Removed: {name}").format(name=self.package_id))
        _redraw(context)
        return {'FINISHED'}


class EMPKG_OT_open_folder(Operator):
    bl_idname = "empkg.open_folder"
    bl_label = "Open the folder"
    bl_description = "Open ~/.s3dgraphy, the folder every EM tool of this computer reads its packages from"

    def execute(self, context):
        P, _ = core.library()
        folder = str(P.profiles_dir().parent) if P else os.path.expanduser("~/.s3dgraphy")
        os.makedirs(folder, exist_ok=True)
        bpy.ops.wm.path_open(filepath=folder)
        return {'FINISHED'}


class EMPKG_OT_refresh(Operator):
    bl_idname = "empkg.refresh"
    bl_label = "Refresh"
    bl_description = "Read the packages of this computer again (installed by EMStudio meanwhile)"

    def execute(self, context):
        core.forget_cache()
        _redraw(context)
        return {'FINISHED'}


# ── Visual Manager ──────────────────────────────────────────────────────────

class EMPKG_OT_apply_scheme(Operator):
    bl_idname = "empkg.apply_scheme"
    bl_label = "Apply"
    bl_description = "Colour the proxies with this colour scheme of a community package"
    bl_options = {'REGISTER', 'UNDO'}

    scheme_id: StringProperty(options={'HIDDEN'})  # type: ignore

    def execute(self, context):
        from ..visual_manager.operators import apply_scheme
        overlay = active_state(context)[0]
        sch = next((s for s in core.package_schemes(overlay, lang()) if s["id"] == self.scheme_id), None)
        if sch is None or sch["emc"] is None:
            self.report({'ERROR'}, tr("not a colour scheme"))
            return {'CANCELLED'}
        graph = active_graph(context)
        names = core.property_names(graph, sch["property"], overlay) if graph is not None else []
        if not names:
            self.report({'ERROR'}, tr("No property {prop} in the active graph").format(prop=sch["property"]))
            return {'CANCELLED'}
        ok, prop = apply_scheme(context, sch["emc"], prop=names[0])
        if not ok:
            self.report({'ERROR'}, prop)
            return {'CANCELLED'}
        self.report({'INFO'}, tr("Colour scheme «{name}» of the package applied ({prop})").format(
            name=sch["name"], prop=prop))
        return {'FINISHED'}


# ── the chain, read: Proxy Box ──────────────────────────────────────────────

def _point_items(self, context):
    graph = active_graph(context)
    if graph is None:
        return [("", "—", "")]
    overlay = active_state(context)[0]
    items = []
    for p in core.measured_points(graph, overlay, lang()):
        src = tr("chain") if p.source == "chain" else tr("attributes")
        items.append((p.extractor_id, p.label[:60], f"{p.name} · {src}"))
    return items or [("", "—", "")]


class EMPKG_OT_proxybox_point_from_graph(Operator):
    bl_idname = "empkg.proxybox_point_from_graph"
    bl_label = "Point from the graph"
    bl_description = "Take the position of a point measured in the graph (EMStudio's chain or EM Tools' x/y/z)"
    bl_options = {'REGISTER', 'UNDO'}
    bl_property = "extractor"

    point_index: IntProperty(min=0, max=6, default=0, options={'HIDDEN'})  # type: ignore
    extractor: EnumProperty(name="Point", items=_point_items)  # type: ignore

    def invoke(self, context, event):
        graph = active_graph(context)
        if graph is None or not core.measured_points(graph):
            self.report({'WARNING'}, tr("No measured point in the active graph"))
            return {'CANCELLED'}
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        graph = active_graph(context)
        overlay = active_state(context)[0]
        place = next((p for p in core.measured_points(graph, overlay, lang())
                      if p.extractor_id == self.extractor), None) if graph is not None else None
        if place is None:
            self.report({'WARNING'}, tr("No measured point in the active graph"))
            return {'CANCELLED'}
        settings = context.scene.em_tools.proxy_box
        while len(settings.points) <= self.point_index:
            settings.points.add()
        # the 3D cursor goes to the point, then Record does everything Record does
        # (point type, document, extractor id): the reading stays one gesture
        context.scene.cursor.location = place.blender[0]
        bpy.ops.proxybox.record_point(point_index=self.point_index)
        point = settings.points[self.point_index]
        if hasattr(point, "graph_extractor_id"):
            point.graph_extractor_id = place.extractor_id
        src = tr("chain") if place.source == "chain" else tr("attributes")
        self.report({'INFO'}, tr("{label}: read from the graph ({source})").format(label=place.label, source=src))
        return {'FINISHED'}


# ── the chain, read: Areale ─────────────────────────────────────────────────

def _surface_items(self, context):
    graph = active_graph(context)
    if graph is None:
        return [("", "—", "")]
    overlay = active_state(context)[0]
    items = []
    for s in core.surfaces(graph, overlay, lang()):
        area = f" · {s.area:.4f} m²" if isinstance(s.area, (int, float)) else ""
        items.append((s.extractor_id, f"{s.label[:50]}{area}", f"{s.name} · {len(s.coords)}"))
    return items or [("", "—", "")]


class EMPKG_OT_areale_from_graph(Operator):
    bl_idname = "empkg.areale_from_graph"
    bl_label = "Areale from a graph surface"
    bl_description = "Make the areale from a surface placed in the graph (EMStudio), on the target RM"
    bl_options = {'REGISTER', 'UNDO'}
    bl_property = "extractor"

    extractor: EnumProperty(name="Surface", items=_surface_items)  # type: ignore

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene.em_tools, "surface_areale", None)
        return settings is not None and settings.target_rm is not None

    def invoke(self, context, event):
        graph = active_graph(context)
        if graph is None or not core.surfaces(graph):
            self.report({'WARNING'}, tr("No surface placed in the active graph"))
            return {'CANCELLED'}
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from ..surface_areale.operators import build_areale_from_ring
        settings = context.scene.em_tools.surface_areale
        rm_obj = settings.target_rm
        if rm_obj is None:
            self.report({'ERROR'}, tr("Pick a target RM first"))
            return {'CANCELLED'}
        graph = active_graph(context)
        overlay = active_state(context)[0]
        place = next((s for s in core.surfaces(graph, overlay, lang()) if s.extractor_id == self.extractor),
                     None) if graph is not None else None
        if place is None:
            self.report({'WARNING'}, tr("No surface placed in the active graph"))
            return {'CANCELLED'}
        why = core.ring_problem(place.blender)
        if why:
            self.report({'ERROR'}, tr("The surface cannot become an areale: {why}").format(why=why))
            return {'CANCELLED'}
        if place.on_id:
            on = graph.find_node_by_id(place.on_id)
            on_name = str(getattr(on, "name", "") or place.on_id)
            if on_name not in (rm_obj.name, rm_obj.data.name if rm_obj.data else ""):
                self.report({'WARNING'}, tr("The surface is on {on}, not on {rm}: made on {rm} all the same")
                            .format(on=on_name, rm=rm_obj.name))
        result = build_areale_from_ring(self, context, rm_obj, place.blender, extractor_id=place.extractor_id)
        if result != {'FINISHED'}:
            return result
        self.report({'INFO'}, tr("Areale made from the surface {label} ({n} vertices)").format(
            label=place.label, n=len(place.blender)))
        return {'FINISHED'}


# ── the declared combiners ──────────────────────────────────────────────────

class EMPKG_OT_compute_measures(Operator):
    bl_idname = "empkg.compute_measures"
    bl_label = "Compute the measures"
    bl_description = "Compute the measures the packages declare from the points placed on each model"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        graph = active_graph(context)
        overlay = active_state(context)[0]
        if graph is None or not overlay or not overlay.combiner_types():
            self.report({'WARNING'}, tr("No package with combiners is active"))
            return {'CANCELLED'}
        done, waiting = core.compute_measures(graph, overlay)
        self.report({'INFO'}, tr("{n} measure(s) computed, {m} waiting for points").format(n=done, m=waiting))
        return {'FINISHED'}


classes = (
    EMPKG_OT_install_from_disk,
    EMPKG_OT_confirm_install,
    EMPKG_OT_remove,
    EMPKG_OT_open_folder,
    EMPKG_OT_refresh,
    EMPKG_OT_apply_scheme,
    EMPKG_OT_proxybox_point_from_graph,
    EMPKG_OT_areale_from_graph,
    EMPKG_OT_compute_measures,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
