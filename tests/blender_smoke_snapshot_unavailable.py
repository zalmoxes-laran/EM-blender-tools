"""Headless smoke · B1, il sidecar silenzioso (MICRO-LA-BARRA-E-LE-STANZE).

NOT a pytest test (needs bpy) — run it inside Blender with the EM-tools
extension enabled:

    /Applications/Blender\\ 520.app/Contents/MacOS/Blender --background \\
        --python tests/blender_smoke_snapshot_unavailable.py

Il caso misurato il 3 ottobre: un .blend riaperto elenca il grafo nel pannello
EM ma non lo ha in memoria, e un `request_snapshot` di EMStudio cadeva in «no
branch handles it» — EMStudio restava vuoto senza un perché. Qui:

1. il ponte serve su una porta libera, una riga di `graphml_files` punta a una
   COPIA della fixture em.json e il grafo NON è caricato;
2. un client (il WsClient dell'add-on, quello che EMtools usa per le stanze)
   chiede lo snapshot → riceve `snapshot_unavailable` con la ragione
   `no_graph_loaded` e il nome del grafo da caricare;
3. il grafo si carica con l'operatore (`import.em_emjson`, la riga 🔄) → lo
   STESSO client riceve `snapshot`, senza riconnettersi.

In `-b` i timer di Blender non girano mentre lo script corre, quindi il drain
che in una sessione vera parte da sé qui si chiama a mano: è la stessa
funzione, un altro chiamante.

Exits non-zero on failure. Nothing is written beside the fixture: the copy
lives in a temporary folder.
"""
import json
import os
import shutil
import socket
import sys
import tempfile
import time

import bpy

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[SMOKE] {status}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def _modulo(suffisso):
    nomi = [n for n in sys.modules if n.endswith(suffisso)
            and n.startswith("bl_ext.")]
    if not nomi:
        print(f"[SMOKE] aborting: {suffisso} not loaded — enable the extension")
        sys.exit(1)
    return sys.modules[nomi[0]]


ops = _modulo(".sync_manager.operators")
pkg = ops.__name__.rsplit(".sync_manager.operators", 1)[0]
ws_client = sys.modules.get(pkg + ".sync_bridge.ws_client")
if ws_client is None:
    import importlib
    ws_client = importlib.import_module(pkg + ".sync_bridge.ws_client")
wire = sys.modules.get(pkg + ".sync_bridge.wire") or __import__(
    "importlib").import_module(pkg + ".sync_bridge.wire")

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixtures", "emtools_cb25e71_dev23.em.json")
work = tempfile.mkdtemp(prefix="em-b1-")
copia = os.path.join(work, "b1.em.json")
shutil.copyfile(FIXTURE, copia)
graph_id = json.load(open(copia, encoding="utf-8"))["active_graph_id"]

# ── 1 · il grafo è ELENCATO e non caricato ──────────────────────────────────
scene = bpy.context.scene
em_tools = scene.em_tools
while len(em_tools.graphml_files):
    em_tools.graphml_files.remove(0)
entry = em_tools.graphml_files.add()
entry.name = graph_id
entry.graphml_path = copia
if hasattr(entry, "file_format"):
    entry.file_format = "EMJSON"
em_tools.active_file_index = 0

from s3dgraphy import get_graph, remove_graph  # noqa: E402
if get_graph(graph_id) is not None:
    remove_graph(graph_id)
ok, _ = ops.is_graph_available(bpy.context)
check("the graph is listed and NOT loaded", not ok and len(em_tools.graphml_files) == 1)

with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
ops._start(port)
check("the bridge serves", ops.is_running(), f"port {port}")

ricevuti = []
client = ws_client.WsClient(f"ws://127.0.0.1:{port}/",
                            on_message=lambda raw: ricevuti.append(json.loads(raw)))
client.connect(timeout=5)
deadline = time.time() + 5
while ops.client_count() < 1 and time.time() < deadline:
    time.sleep(0.05)
check("one client connected", ops.client_count() == 1)


def aspetta(tipo, entro=5.0):
    fine = time.time() + entro
    while time.time() < fine:
        for m in ricevuti:
            if m.get("type") == tipo:
                return m
        time.sleep(0.05)
    return None


def drena():
    srv = ops._server
    fine = time.time() + 5
    while srv.inbox.empty() and time.time() < fine:
        time.sleep(0.05)
    ops._drain_inbox()


# ── 2 · la domanda, e la risposta che prima non c'era ───────────────────────
client.send(json.dumps(wire.envelope("request_snapshot", {}, source="emstudio")))
drena()
risposta = aspetta("snapshot_unavailable")
check("request_snapshot is ANSWERED (snapshot_unavailable)", risposta is not None,
      f"got {[m.get('type') for m in ricevuti]}")
corpo = (risposta or {}).get("payload") or {}
check("reason = no_graph_loaded", corpo.get("reason") == "no_graph_loaded",
      repr(corpo.get("reason")))
check("the listed graph is named", corpo.get("graphs") == [graph_id],
      repr(corpo.get("graphs")))
check("a sentence for a person", "No graph loaded in Blender" in str(corpo.get("message")))
check("host info rides along", isinstance(corpo.get("host"), dict)
      and corpo["host"].get("tool") == "Blender · EMtools")
check("no snapshot yet", aspetta("snapshot", 0.3) is None)
print("[SMOKE] payload:", json.dumps(corpo, ensure_ascii=False)[:400])
check("the panel line says it", "snapshot_unavailable" in ops.ULTIMO_MESSAGGIO["esito"],
      ops.ULTIMO_MESSAGGIO["esito"])

# ── 3 · il grafo si carica → lo snapshot arriva da sé ───────────────────────
ricevuti.clear()
esito = getattr(bpy.ops, "import").em_emjson(file_index=0)
check("the graph loads with the operator", esito == {"FINISHED"}, repr(esito))
ok, graph = ops.is_graph_available(bpy.context)
check("…and is available now", ok)
arrivato = aspetta("snapshot")
check("the snapshot arrives WITHOUT reconnecting", arrivato is not None,
      f"got {[m.get('type') for m in ricevuti]}")
doc = ((arrivato or {}).get("payload") or {}).get("doc") or {}
# the snapshot channel sends the single-graph shape (`build_emjson`)
check("…and it is the graph that was loaded",
      (doc.get("graph") or {}).get("graph_id") == graph_id
      and len((doc.get("graph") or {}).get("nodes") or []) > 0,
      repr((doc.get("graph") or {}).get("graph_id")))
check("the same socket is still open", client.connected)
check("…exactly once", sum(1 for m in ricevuti if m.get("type") == "snapshot") == 1,
      repr([m.get("type") for m in ricevuti]))

# un request_snapshot adesso è risposto con lo snapshot (il ramo di sempre)
ricevuti.clear()
client.send(json.dumps(wire.envelope("request_snapshot", {}, source="emstudio")))
drena()
check("a later request_snapshot gets the snapshot", aspetta("snapshot") is not None)

client.close()
ops._stop()
shutil.rmtree(work, ignore_errors=True)

if FAILURES:
    print(f"[SMOKE] {len(FAILURES)} failure(s): {FAILURES}")
    sys.exit(1)
print("[SMOKE] all checks passed")
