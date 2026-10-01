"""Headless smoke: the RDF export report and the study language (MICRO-EMTOOLS-DEV26, parte 1).

NOT a pytest test (needs bpy) — run it inside Blender with the EM-tools
extension installed (see tests/blender_smoke_dev26.py for the clean user folder):

    /Applications/Blender\\ 520.app/Contents/MacOS/Blender --background \\
        --python tests/blender_smoke_rdf_report.py

* a graph whose study declares no language → the operator reports a WARNING
  and ``<name>.export-report.txt`` lands beside the ``.ttl``;
* ``em.set_study_language`` writes ``GraphNode.data.language`` → the next
  export has no untagged text;
* the unverified AI translation is not in the published ``.ttl``.

Exits non-zero on failure.
"""
import os
import sys
import tempfile

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


if not check("addon loaded", hasattr(bpy.context.scene, "em_tools")
             and hasattr(bpy.types.Scene, "rdf_mode")):
    sys.exit(1)

from s3dgraphy import api  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.multigraph.multigraph import multi_graph_manager  # noqa: E402
from s3dgraphy.nodes.author_node import AuthorAINode, AuthorNode  # noqa: E402
from s3dgraphy.nodes.document_node import DocumentNode  # noqa: E402

g = Graph("smoke_rdf")
g.add_node(AuthorNode("ed", name="Emanuel", orcid="0000-0002-1825-0097", surname="D"))
g.add_node(AuthorAINode("claude", name="Claude"))
doc = DocumentNode("d1", "D.1", "firmitatis, utilitatis, venustatis")
doc.data = {"lang": "la"}
g.add_node(doc)
g.add_node(DocumentNode("d2", "D.2", "una descrizione senza lingua propria"))
api.add_translation(g, "d1", "description", "it", "solidità, utilità, bellezza", by="ed")
api.add_translation(g, "d1", "description", "en", "strength, utility, beauty",
                    by="ed", method="ai", ai="claude", model="claude-opus-5-5")
multi_graph_manager.graphs["smoke_rdf"] = g

scene = bpy.context.scene
row = scene.em_tools.graphml_files.add()
row.name = "smoke_rdf"
scene.em_tools.active_file_index = 0

out = tempfile.mkdtemp(prefix="em_rdf_smoke_")
scene.rdf_export_path = os.path.join(out, "smoke_rdf.ttl")
scene.rdf_base_uri = "urn:em:"
check("default mode is publish", scene.rdf_mode == "publish", scene.rdf_mode)

result = bpy.ops.export.rdf()
ttl = os.path.join(out, "smoke_rdf.ttl")
rep = os.path.join(out, "smoke_rdf.export-report.txt")
check("export finished", result == {'FINISHED'}, str(result))
check("report beside the ttl", os.path.isfile(rep), rep)
text = open(rep, encoding="utf-8").read() if os.path.isfile(rep) else ""
check("untagged texts are a warning", "▲" in text and "without a language" in text)
check("the warning says where to declare", "EM Setup ▸ Graph info ▸ Language" in text)
check("AI translation counted", "AI not verified, left out:     1" in text)
body = open(ttl, encoding="utf-8").read() if os.path.isfile(ttl) else ""
check("AI translation not in the ttl", "strength, utility" not in body)
check("verified translation in the ttl", "solidità, utilità, bellezza" in body)

result = bpy.ops.em.set_study_language('EXEC_DEFAULT', tag="it")
check("study language set", api.working_language(g) == "it", str(result))
try:
    result = bpy.ops.em.set_study_language('EXEC_DEFAULT', tag="not a tag!")
except RuntimeError as exc:  # an ERROR report raises inside a script
    result = str(exc).splitlines()[0][:60]
check("an invalid tag is refused", api.working_language(g) == "it", str(result))

bpy.ops.export.rdf()
text = open(rep, encoding="utf-8").read()
check("no untagged text after declaring", "untagged:             0" in text
      and "smoke_rdf: it" in text)
for line in text.splitlines()[:12]:
    print("[SMOKE]   | " + line)

print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
