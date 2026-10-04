"""GUI screenshots · T-U2, the z-fighting of a facade proxy before and after
«Offset proxy», on the COPY of Templu Mare (never saved). NOT headless.

    "/Applications/Blender 520.app/Contents/MacOS/Blender" --python-use-system-env \\
        <copy>.blend --python tests/blender_shots_proxy_offset.py -- <out_dir> [proxy] [distance_m]

Frames the proxy (GT16.USV153 by default, one of the 34 measured coplanar with
the RM) from `distance_m` (default 20) in solid view with the object colours,
and writes `proxy_offset_asis_<d>m.png` (the scene as it is: on Templu Mare the
proxies carry the old inflation, a Solidify of 1 cm), then — the old inflation
removed — `proxy_offset_<mm>mm_<d>m.png` for 0 (nothing), 2, 5 and 10 mm.
"""
import os
import sys

import bpy
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else "/tmp/emtools-offset"
NAME = ARGS[1] if len(ARGS) > 1 else "GT16.USV153"
DIST = float(ARGS[2]) if len(ARGS) > 2 else 20.0
os.makedirs(OUT, exist_ok=True)
STEPS = [None, 0.0, 0.002, 0.005, 0.01]
STATE = {"i": -1}


def view3d():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == 'VIEW_3D'), key=lambda a: a.width * a.height)
    return win, area


def frame():
    win, area = view3d()
    space = area.spaces.active
    space.show_region_ui = False
    space.shading.type = 'SOLID'
    space.shading.color_type = 'OBJECT'
    space.overlay.show_overlays = False
    obj = bpy.data.objects[NAME]
    obj.hide_viewport = False
    obj.hide_set(False)
    obj.color = (1.0, 0.1, 0.1, 1.0)
    # the proxy's centre and its mean normal, in world space
    mw = obj.matrix_world
    centre = sum((mw @ v.co for v in obj.data.vertices), Vector()) / len(obj.data.vertices)
    normal = sum((mw.to_3x3() @ p.normal * p.area for p in obj.data.polygons), Vector()).normalized()
    r3d = space.region_3d
    r3d.view_perspective = 'PERSP'
    # look at the face from 35° to its side and a little from above: grazing
    # angles are where coplanar faces fight most
    from mathutils import Matrix
    eye = (Matrix.Rotation(0.6, 3, 'Z') @ normal + Vector((0, 0, 0.2))).normalized()
    r3d.view_rotation = (-eye).to_track_quat('-Z', 'Y')
    r3d.view_location = centre
    r3d.view_distance = DIST
    # only the proxy and the RM it lies on stay visible, both opaque
    import bmesh
    from mathutils.bvhtree import BVHTree
    best, host = -1, None
    for it in bpy.context.scene.rm_list:
        rm = bpy.data.objects.get(it.name)
        if rm is None or rm.type != 'MESH' or len(rm.data.polygons) > 300000:
            continue
        bm = bmesh.new()
        bm.from_mesh(rm.data)
        bm.transform(rm.matrix_world)
        tree = BVHTree.FromBMesh(bm)
        bm.free()
        near = sum(1 for v in obj.data.vertices
                   if (lambda h: h[0] is not None)(tree.find_nearest(mw @ v.co, 0.005)))
        if near > best:
            best, host = near, rm
    print("[SHOTS] the RM under", NAME, "is", host and host.name, best, "/", len(obj.data.vertices))
    for o in bpy.context.view_layer.objects:
        o.hide_set(o not in (obj, host))
    if host is not None:
        host.color = (0.8, 0.8, 0.8, 1.0)
        host.hide_viewport = False
        for coll in host.users_collection:
            coll.hide_viewport = False
        print("[SHOTS] host visible:", host.visible_get(), "in", [c.name for c in host.users_collection])
    sys.stdout.flush()
    win, area = view3d()
    region = next(r for r in area.regions if r.type == 'WINDOW')
    for o in bpy.context.view_layer.objects:
        o.select_set(o == obj)
    bpy.context.view_layer.objects.active = obj
    with bpy.context.temp_override(window=win, area=area, region=region):
        bpy.ops.view3d.view_selected()
    r3d.view_rotation = (-eye).to_track_quat('-Z', 'Y')
    r3d.view_distance = DIST
    print("[SHOTS] framed", NAME, "centre", tuple(round(c, 2) for c in centre), "normal",
          tuple(round(c, 2) for c in normal), "clip", space.clip_start, space.clip_end)


def step():
    try:
        i = STATE["i"]
        if i == -1:
            frame()
            STATE["i"] = 0
            return 1.5
        if i >= len(STEPS):
            sys.stdout.flush()
            os._exit(0)
        obj = bpy.data.objects[NAME]
        d = STEPS[i]
        if STATE.get("set") != i:
            if d is None:
                STATE["set"] = i
                return 1.5
            if i == 1:
                bpy.ops.em.proxy_old_inflate_remove()
            bpy.context.scene.em_tools.proxy_offset_distance = d or 0.005
            for o in bpy.context.view_layer.objects:
                o.select_set(False)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            if d:
                bpy.ops.em.proxy_offset(scope='ACTIVE')
            STATE["set"] = i
            return 1.5
        win, area = view3d()
        tag = "asis" if d is None else f"{d * 1000:g}mm"
        path = os.path.join(OUT, f"proxy_offset_{tag}_{DIST:g}m.png")
        with bpy.context.temp_override(window=win, area=area):
            bpy.ops.screen.screenshot_area(filepath=path)
        print("[SHOTS] wrote", path, "modifier:", [(m.name, m.type, round(getattr(m, "strength", getattr(m, "thickness", 0)), 4)) for m in obj.modifiers])
        STATE["i"] = i + 1
        return 0.3
    except Exception:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        os._exit(1)


bpy.app.timers.register(step, first_interval=3.0)
