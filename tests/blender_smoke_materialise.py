"""Headless smoke of the em.materialise_geometry OPERATOR (DP-76, consuming half).

NOT a pytest test (needs bpy) — run it inside Blender with the EM-tools
extension enabled, against a LIVE room:

    EM_ROOM_URL=http://localhost:8000 EM_ROOM_ID=<room> EM_ROOM_TOKEN=$(…token.sh) \\
    /Applications/Blender\\ 520.app/Contents/MacOS/Blender --background \\
        --python tests/blender_smoke_materialise.py

**Why this exists beside `tests/test_room_materialise.py`.** Those 13 tests call
the pure function with the two Blender steps stubbed — which is the right way to
measure the batch logic, and it leaves two things unmeasured:

* **the operator**, i.e. the button: its `poll`, its report, the way it reads the
  active graph out of `em_tools`;
* **the epoch binding for real.** `Object.EM_ep_belong_ob` only exists when the
  addon is REGISTERED, so headless-without-addon the module honestly reported
  `epochs_not_written`. Whether it writes when the property is there could not be
  shown by a stub of the property.

This is the repeatable proof of both. The human counter-proof (one press of the
button in an interactive Blender) is in `em-server/dev-stack/TEST-WALKTHROUGH.md`,
step 5 — measured here, seen there.

Exits non-zero on failure. Nothing is written to disk; the objects it imports
live in the scene of a background Blender that quits.
"""
import os
import sys

import bpy

# THE WHEEL IS A COPY. The addon ships s3dgraphy as a wheel, and Blender installs
# it into the extension's own site-packages — so a Blender enabled before the
# library grew `geometry_summary` has an older copy under the SAME version
# string (measured: 1.6.0.dev14 on both sides). `EM_S3DGRAPHY_SRC` points this
# smoke at a checkout so it can measure the code as it is now; without it, it
# measures what the addon actually ships, which is the other question worth
# asking. Whichever is used is printed.
_SRC = os.environ.get("EM_S3DGRAPHY_SRC", "")
if _SRC:
    sys.path.insert(0, _SRC)

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[SMOKE] {status}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def bail(why):
    print(f"[SMOKE] aborting: {why}")
    sys.exit(1)


# --- 0. the addon is REGISTERED (that is the point of this file) -------------
check("scene.em_tools exists", hasattr(bpy.context.scene, "em_tools"))
has_op = hasattr(bpy.ops.em, "materialise_geometry")
check("em.materialise_geometry registered", has_op)
# the property the binding writes into — absent when the addon is not loaded,
# which is exactly the gap this smoke closes
has_prop = hasattr(bpy.types.Object, "EM_ep_belong_ob")
check("Object.EM_ep_belong_ob exists (the addon's epoch convention)", has_prop)
if not (has_op and hasattr(bpy.context.scene, "em_tools") and has_prop):
    bail("the EM-tools extension is not loaded — enable it, or run without "
         "--factory-startup")

import s3dgraphy                                              # noqa: E402
_api = __import__("s3dgraphy.api", fromlist=["api"])
_knows = hasattr(_api, "geometry_summary")
print(f"[SMOKE] s3dgraphy: {getattr(s3dgraphy, '__file__', '?')}")
# The detail belongs to the FAILURE — a pass that prints its own remediation
# reads like a warning. (The addon ships this library as a wheel, so this can be
# older than the checkout under the very same version string: measured.)
check("…and it knows the consuming half of DP-76", _knows,
      "" if _knows else
      "no `geometry_summary` → the addon's wheel is older than the feature; "
      "rebuild wheels/cp3xx/s3dgraphy-*.whl and re-install it into the "
      "extension's site-packages, then re-enable the extension")

rna = bpy.ops.em.materialise_geometry.get_rna_type()
check("the button says what it does",
      "store" in rna.name.lower() or "store" in rna.description.lower(),
      f"'{rna.name}'")

ROOM_URL = os.environ.get("EM_ROOM_URL", "http://localhost:8000")
ROOM_ID = os.environ.get("EM_ROOM_ID", "")
TOKEN = os.environ.get("EM_ROOM_TOKEN", "")
DIGEST = os.environ.get("EM_ASSET_SHA256", "")
EPOCH = os.environ.get("EM_EPOCH_NAME", "Fase demo")
if not (ROOM_ID and TOKEN and DIGEST):
    bail("this smoke needs a live room: set EM_ROOM_URL / EM_ROOM_ID / "
         "EM_ROOM_TOKEN / EM_ASSET_SHA256 (a resident glTF asset in that room)")

# --- 1. poll: no room, no button --------------------------------------------
#
# The addon's module name is NOT a constant: installed from the repo it is
# `bl_ext.blender_extendedmatrix_org.em_tools`, live-loaded from a checkout it is
# `bl_ext.vscode_development.EM-blender-tools` (a name with hyphens, which no
# `import` statement can even spell). So it is found through the modules Blender
# has already loaded — the registered operator proves one of them is there.
import importlib                                             # noqa: E402
import sys as _sys                                           # noqa: E402

_loaded = [n for n in _sys.modules if n.endswith(".sync_manager.materialise")]
if not _loaded:
    bail("the addon is registered but its `sync_manager.materialise` is not in "
         "sys.modules — a partial load, which is worth looking at")
_PACKAGE = _loaded[0].rsplit(".sync_manager.materialise", 1)[0]
print(f"[SMOKE] addon package: {_PACKAGE}")
mat = _sys.modules[_loaded[0]]
room_cfg = importlib.import_module(f"{_PACKAGE}.sync_manager.room")
SESSION = importlib.import_module(f"{_PACKAGE}.sync_manager.room_session").SESSION

check("poll False outside a room", not bpy.ops.em.materialise_geometry.poll())

# --- 2. the graph the room describes -----------------------------------------
from s3dgraphy.graph import Graph                            # noqa: E402
from s3dgraphy.multigraph.multigraph import multi_graph_manager   # noqa: E402
from s3dgraphy.nodes.epoch_node import EpochNode             # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402
from s3dgraphy.nodes.resource_node import ResourceNode       # noqa: E402

scene = bpy.context.scene
scene.em_tools.graphml_files.clear()

graph = Graph(graph_id="smoke_materialise")
graph.add_node(EpochNode("ep1", name=EPOCH, start_time=-100, end_time=0))
graph.add_node(ResourceNode("res1", name="smoke.glb", checksum=DIGEST,
                            residency="resident", url_type="3d_model"))
graph.add_node(RepresentationModelNode("rm1", name=f"Model for {EPOCH}", type="RM"))
graph.add_edge("e1", "rm1", "res1", "has_linked_resource")
graph.add_edge("e2", "rm1", "ep1", "has_first_epoch")
multi_graph_manager.graphs["smoke_materialise"] = graph
row = scene.em_tools.graphml_files.add()
row.name = "smoke_materialise"
scene.em_tools.active_file_index = 0

records = mat.plan(graph)["resident"]
check("the library lists it as store-backed", len(records) == 1,
      f"{len(records)} record(s)")
check("…bound to the epoch", bool(records) and
      [b["name"] for b in records[0]["bind"]] == [EPOCH],
      str(records[0]["bind"]) if records else "")

# --- 3. in the room: the button becomes pressable ----------------------------
#
# JOINED FOR REAL — `SESSION.joined` is derived from the socket (a read-only
# property, and rightly so: a mode you can set independently of what is true is a
# mode that will eventually lie). So this opens the room the way the addon does,
# with `adopt=False`: the document this smoke uses is the one it built above, and
# adopting would merge the room's on top of it.
_ops = importlib.import_module(f"{_PACKAGE}.sync_manager.operators")
arrival = _ops.join_room(bpy.context, ROOM_URL, ROOM_ID, TOKEN, adopt=False)
if not check("joined the room for real", arrival.get("ok"),
             str(arrival.get("message"))[:80]):
    bail("cannot measure the button without a room")
check("poll True inside a room", bpy.ops.em.materialise_geometry.poll())

before = set(bpy.data.objects)
result = bpy.ops.em.materialise_geometry()
check("the operator finishes", result == {"FINISHED"}, str(result))
made = [o for o in bpy.data.objects if o not in before]
check("an object arrived in the scene", len(made) >= 1,
      ", ".join(o.name for o in made) or "none")

if made:
    obj = made[0]
    check("…carrying the digest it came from",
          obj.get(mat.PROP_DIGEST) == DIGEST, str(obj.get(mat.PROP_DIGEST))[:23])
    check("…and the resource / carrier it belongs to",
          obj.get(mat.PROP_RESOURCE) == "res1"
          and obj.get(mat.PROP_CARRIER) == "rm1",
          f"{obj.get(mat.PROP_RESOURCE)} / {obj.get(mat.PROP_CARRIER)}")
    bound = [slot.epoch for slot in obj.EM_ep_belong_ob]
    # THE ONE THIS FILE EXISTS FOR: with the addon registered the binding is
    # WRITTEN, not reported as pending
    check("EM_ep_belong_ob is written to the right epoch", bound == [EPOCH],
          str(bound))

# --- 4. content-addressed: a second press changes nothing --------------------
report = mat.materialise(graph, objects=bpy.data.objects)
check("the second pass reuses instead of fetching",
      len(report["reused"]) == 1 and report["materialised"] == [],
      mat.summarise(report))
after = [o for o in bpy.data.objects if o not in before]
check("…and nothing was duplicated", len(after) == len(made),
      f"{len(made)} → {len(after)}")

# --- 5. leave: a smoke that stays connected holds a seat in the room ---------
try:
    _ops.leave_room()
    check("left the room (and forgot the token)", not SESSION.joined)
except Exception as exc:                                     # noqa: BLE001
    check("left the room (and forgot the token)", False, str(exc)[:60])

print()
if FAILURES:
    print(f"[SMOKE] {len(FAILURES)} FAILED: " + " · ".join(FAILURES))
    sys.exit(1)
print("[SMOKE] the button materialises, binds the epoch, and does it once.")
