"""Pure-Python tests for the reimport planner. No bpy imports."""

from import_operators.reimport_planner import build_reimport_plan


class FakeObject(dict):
    """Stand-in for a Blender Object: supports `obj[key]` and `obj.get(key)`."""


class FakeNode:
    def __init__(self, node_id):
        self.id = node_id


def make_objs(specs):
    """specs = list of (node_id, modified_flag). Builds FakeObjects matching the
    contract used by the planner: em_is_imported_geom + em_us_node_id, plus
    a synthetic em_modified flag the test stub uses instead of vertex/hash math.
    """
    out = []
    for node_id, modified in specs:
        o = FakeObject()
        o["em_is_imported_geom"] = True
        o["em_us_node_id"] = node_id
        o["__test_modified"] = modified
        out.append(o)
    return out


def fake_is_modified(obj):
    return bool(obj.get("__test_modified"))


def fake_resolver(graph, us_key):
    """Graph is a dict {us_key_str: node_id}."""
    return FakeNode(graph[us_key]) if us_key in graph else None


def test_plan_create_only():
    incoming = [{"us_key": "a"}, {"us_key": "b"}]
    graph = {"a": "node-a", "b": "node-b"}
    plan = build_reimport_plan(
        scene_objects=[],
        graph=graph,
        incoming_polygons=incoming,
        is_modified=fake_is_modified,
        resolve_us_node=fake_resolver,
    )
    assert len(plan["create"]) == 2
    assert plan["update_safe"] == []
    assert plan["skip_modified"] == []
    assert plan["mark_orphan_obj"] == []


def test_plan_update_safe_when_existing_unmodified():
    existing = make_objs([("node-a", False)])
    incoming = [{"us_key": "a"}]
    graph = {"a": "node-a"}
    plan = build_reimport_plan(
        scene_objects=existing,
        graph=graph,
        incoming_polygons=incoming,
        is_modified=fake_is_modified,
        resolve_us_node=fake_resolver,
    )
    assert plan["create"] == []
    assert len(plan["update_safe"]) == 1
    assert plan["skip_modified"] == []
    assert plan["mark_orphan_obj"] == []


def test_plan_skip_modified():
    existing = make_objs([("node-a", True)])
    incoming = [{"us_key": "a"}]
    graph = {"a": "node-a"}
    plan = build_reimport_plan(
        scene_objects=existing,
        graph=graph,
        incoming_polygons=incoming,
        is_modified=fake_is_modified,
        resolve_us_node=fake_resolver,
    )
    assert plan["create"] == []
    assert plan["update_safe"] == []
    assert len(plan["skip_modified"]) == 1
    assert plan["mark_orphan_obj"] == []


def test_plan_mark_orphan_when_us_disappears():
    existing = make_objs([("node-a", False)])
    incoming = []  # US gone from DB
    graph = {}
    plan = build_reimport_plan(
        scene_objects=existing,
        graph=graph,
        incoming_polygons=incoming,
        is_modified=fake_is_modified,
        resolve_us_node=fake_resolver,
    )
    assert plan["create"] == []
    assert plan["update_safe"] == []
    assert plan["skip_modified"] == []
    assert len(plan["mark_orphan_obj"]) == 1


def test_plan_polygon_orphan_excluded_from_create():
    """If incoming refers to a us_key not in the graph, that polygon is
    routed to the polygon-orphan flow elsewhere — not into create."""
    existing = []
    incoming = [{"us_key": "ghost"}]
    graph = {}
    plan = build_reimport_plan(
        scene_objects=existing,
        graph=graph,
        incoming_polygons=incoming,
        is_modified=fake_is_modified,
        resolve_us_node=fake_resolver,
    )
    assert plan["create"] == []
    assert plan["update_safe"] == []
    assert plan["skip_modified"] == []
    assert plan["mark_orphan_obj"] == []


def test_plan_ignores_non_imported_objects():
    """Objects without em_is_imported_geom or em_us_node_id are ignored."""
    o = FakeObject()
    o["em_us_node_id"] = "node-a"  # but missing em_is_imported_geom
    incoming = []
    graph = {}
    plan = build_reimport_plan(
        scene_objects=[o],
        graph=graph,
        incoming_polygons=incoming,
        is_modified=fake_is_modified,
        resolve_us_node=fake_resolver,
    )
    assert plan["mark_orphan_obj"] == []
