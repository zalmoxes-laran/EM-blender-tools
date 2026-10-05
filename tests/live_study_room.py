"""T-G1/G2, the EM Tools half · a live room that holds a whole study.

Driven by EMStudio's `frontend/scripts/check-study-room-live.mjs`, not by
pytest (it needs a node and a room): it joins with the REAL `RoomSession`,
adopts the room's graphs the way `_lega_grafo_alla_stanza` does, applies what
arrives into the graph `graph_of_message` names (with s3Dgraphy's CRDT, as
`_sicuro` does through the add-on's graph), and writes an edit into the second
graph. Blender is not involved: the session, the wire and the library are the
add-on's own; the panel and the bpy graph are not exercised here.

    python tests/live_study_room.py <base> <room> <token-file> <graph> <node>

One line per step on stdout: READY, GOT, SENT.
"""
import json
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from test_room_per_graph import room, rs          # noqa: E402 — the bpy-free loader

from s3dgraphy import api                         # noqa: E402
from s3dgraphy.container import is_dtc_corpus_member, is_shelf_member  # noqa: E402


def main(base, room_id, token_file, graph, node):
    token = open(token_file, encoding="utf-8").read().strip()
    room.set_room(base, room_id, token)
    session = rs.RoomSession()
    arrival = session.join(timeout=15)
    doc = arrival["snapshot"]["payload"]["doc"]
    ids = [str(sec.get("graph_id") or gid) for gid, sec in doc["graphs"].items()
           if not is_shelf_member(sec) and not is_dtc_corpus_member(sec)]
    session.room_graphs = set(ids)                # as `_lega_grafo_alla_stanza`
    session.writing_graph = ids[0]
    print("READY " + ",".join(sorted(ids)), flush=True)

    deadline = time.time() + 30
    got = None
    while time.time() < deadline and got is None:
        for message in session.drain():
            if message.get("type") != "op":
                continue
            named = rs.graph_of_message(session, message)
            section = doc["graphs"].get(named) if named else None
            applied = (api.apply_op(section, message["payload"])["applied"]
                       if section is not None else False)
            got = (named, message["payload"].get("node_id"), applied)
        time.sleep(0.05)
    print(f"GOT {got[0] if got else None} {got[1] if got else None} "
          f"applied={got[2] if got else False}", flush=True)

    session.writing_graph = graph                 # as `activate(graph)`
    session.send_op({"op": "update_field", "node_id": node, "field": "description",
                     "value": "scritto da EM Tools nel secondo grafo",
                     "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 2))})
    deadline = time.time() + 15
    answer = None
    while time.time() < deadline and answer is None:
        for message in session.drain():
            if message.get("type") == "op_result":
                answer = message["payload"]
        time.sleep(0.05)
    print(f"SENT applied={bool(answer and answer.get('applied'))} "
          f"graph={answer.get('graph_id') if answer else None}", flush=True)
    time.sleep(1.0)
    session.leave()


if __name__ == "__main__":
    main(*sys.argv[1:6])
