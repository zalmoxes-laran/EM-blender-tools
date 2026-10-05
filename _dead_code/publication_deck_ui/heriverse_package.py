"""U1 · Heriverse as a DESTINATION of the Publication Deck (E.D., 5 Oct 2026).

The Heriverse exporter used to hide an optimisation of its own (Draco, the
textures apart, the instancing). The preparation is now a gesture of Asset
versions — «Prepare for a use…» makes a distribution version with its `use` —
and publishing to Heriverse takes those versions: «Package for Heriverse…»
shows each object with a version for the web or realtime at that level while
the package is made, then puts back the level it showed. The package itself
stays in the engine (`export_operators/heriverse/`, `export.heriverse`),
called from here with the provider's settings, and the dissemination filter
is untouched. Q5 (E.D., 5 Oct 2026): the engine has no optimisation of its
own any more — no Draco, no texture compression of the models.
"""

from typing import Any, Dict, List

import bpy  # type: ignore

#: the uses Heriverse takes (the same as `publication_targets.USI_HERIVERSE`)
USES = ("web", "realtime")

#: the last package (session state)
LAST: Dict[str, Any] = {}


def versions_for(graph, objects) -> List[Dict[str, Any]]:
    """`[{object, level, version}]`: the objects with a version for the web or
    realtime, and which level shows it (the lightest when several)."""
    from s3dgraphy import api
    from ..sync_manager import asset_versions as av
    out = []
    for obj in objects:
        asset = obj.get(av.PROP_ASSET)
        if not asset or graph.find_node_by_id(str(asset)) is None:
            continue
        try:
            versions = api.versions_of(graph, str(asset))
        except Exception:  # noqa: BLE001
            continue
        fit = [v for v in versions if set(v.get("use") or []) & set(USES) and v.get("level")]
        if fit:
            best = sorted(fit, key=lambda v: av.level_key(v["level"]))[-1]
            out.append({"object": obj.name, "level": best["level"], "version": best["id"],
                        "use": list(best.get("use") or [])})
    return out


class EM_OT_deck_heriverse_package(bpy.types.Operator):
    """Package for Heriverse: each object with a version for the web or
    realtime shows it while the package is made (then its level comes back);
    the package is the Heriverse exporter's, with its settings"""

    bl_idname = "em.deck_heriverse_package"
    bl_label = "Package for Heriverse"

    go: bpy.props.BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})  # type: ignore

    def _graph(self, context):
        from ..functions import is_graph_available
        ok, graph = is_graph_available(context)
        return graph if ok else None

    def invoke(self, context, event):
        graph = self._graph(context)
        LAST["plan"] = versions_for(graph, context.scene.objects) if graph is not None else []
        return context.window_manager.invoke_popup(self, width=480)

    def draw(self, context):
        layout = self.layout
        plan = LAST.get("plan") or []
        layout.label(text=f"{len(plan)} object(s) go with their version for the web "
                          f"or realtime", icon="WORLD_DATA")
        for row in plan[:8]:
            layout.label(text=f"{row['object']} · {row['level']} "
                              f"({', '.join(row['use'])})", icon="BLANK1")
        try:
            from ..export_manager.providers.heriverse import ui as heri
            heri.draw(layout.box(), context)
        except Exception as exc:  # noqa: BLE001
            layout.label(text=f"Heriverse settings: {exc}", icon="ERROR")
        layout.operator("em.deck_heriverse_package", text="Package for Heriverse",
                        icon="EXPORT").go = True

    def execute(self, context):
        if not self.go:
            return {"FINISHED"}
        from ..sync_manager import asset_versions as av
        graph = self._graph(context)
        plan = versions_for(graph, context.scene.objects) if graph is not None else []
        shown = {}
        for row in plan:
            obj = bpy.data.objects.get(row["object"])
            if obj is None:
                continue
            shown[obj.name] = av.current_level(obj)
            av.show_level(obj, row["level"])
        try:
            result = bpy.ops.export.heriverse()
        finally:
            for name, level in shown.items():
                obj = bpy.data.objects.get(name)
                if obj is not None and level:
                    av.show_level(obj, level)
        LAST.update({"result": list(result), "with_versions": plan})
        self.report({"INFO"}, f"Heriverse package: {len(plan)} object(s) with their "
                              f"web/realtime version · {result}")
        return result


def register():
    bpy.utils.register_class(EM_OT_deck_heriverse_package)


def unregister():
    try:
        bpy.utils.unregister_class(EM_OT_deck_heriverse_package)
    except Exception:  # noqa: BLE001
        pass
