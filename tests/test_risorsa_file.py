"""MICRO risorsa-file, parte 1 — un solo modo di creare una risorsa.

E.D. 30 set 2026: `ResourceNode` per l'insieme, `ResourceFileNode` per ogni
file (implicito con un file solo); le rappresentazioni sono risorse sorelle
legate da `dtc_derived_from`, la risorsa interna `blend://` è il master
(`datablock`), gli export sono distribution. Ogni punto di EMtools che crea una
risorsa passa per `s3dgraphy.api.add_resource`.
"""

from __future__ import annotations

import json
import os
import pathlib
import re

import pytest

from s3dgraphy import api
from s3dgraphy.graph import Graph
from s3dgraphy.importer.emjson_importer import import_emjson
from s3dgraphy.exporter.emjson_exporter import export_emjson

import resource_levels as rl
import resource_digest as rd


def _load(rel, name):
    """A bpy-free module of a package whose `__init__` imports bpy."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_emjson(graph):
    """The em.json EMtools writes (a container), as a dict."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "g.em.json")
        export_emjson(graph, out)
        with open(out, encoding="utf-8") as handle:
            return json.load(handle)

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "emtools_cb25e71_dev23.em.json"


# ── la guardia: nessuno costruisce una risorsa da sé ─────────────────────────

_SKIP_DIRS = {".venv", "build", "wheels", "tests", "_vendor", "__pycache__", ".git",
              ".claude", "scripts"}


def test_nessun_modulo_costruisce_una_risorsa_da_se():
    """Un solo modo: fuori dai test, nessuno chiama il costruttore di
    `ResourceNode` (o del vecchio `LinkNode`). Misurato il 25 ott 2026: erano
    6 costruttori diretti in 5 moduli, più la `add_resource` di
    `dtc_authoring`, tutti portati su `api.add_resource`."""
    call = re.compile(r"(?<![\w.`])(ResourceNode|LinkNode)\(")
    offenders = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if set(rel.parts[:-1]) & _SKIP_DIRS:
            continue
        in_doc = False
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.count('"""') % 2 == 1 or stripped.count("'''") % 2 == 1:
                in_doc = not in_doc
                continue
            if in_doc or stripped.startswith("#"):
                continue
            code = stripped.split("#", 1)[0]
            if call.search(code) and "isinstance" not in code and "class " not in code:
                offenders.append(f"{rel}:{n}: {stripped}")
    assert offenders == [], "\n".join(offenders)


def test_la_guardia_vede_un_costruttore(tmp_path):
    """La regex della guardia trova davvero una chiamata (non passa per vuoto)."""
    call = re.compile(r"(?<![\w.`])(ResourceNode|LinkNode)\(")
    assert call.search('node = ResourceNode(node_id="x", name="y")')
    assert not call.search("api.add_resource(graph, name='x')")


# ── il master: datablock, dichiarato ─────────────────────────────────────────

def test_un_master_nuovo_e_un_datablock_dichiarato():
    g = Graph("g")
    ok, _ = rl.assicura_master(g, master_id="M_res_blend",
                               url="blend://scene.blend#Object/M", name="datablock for M",
                               misure={"v": 8, "f": 6})
    assert ok
    n = g.find_node_by_id("M_res_blend")
    assert n.node_type == "resource"
    assert n.data["tier"] == "master"
    assert n.data["packaging"] == "datablock"
    assert n.data["residency"] == "resident"
    assert n.data["url"] == "blend://scene.blend#Object/M"
    assert n.data["url_type"] == "3d_model"
    assert api.resource_files(g, "M_res_blend")[0]["implicit"] is True


# ── il glTF separato è un file_set ───────────────────────────────────────────

def _gltf(tmp_path, tex=b"PNG1", bin_=b"BIN!"):
    models = tmp_path / "models"
    models.mkdir(exist_ok=True)
    (models / "M.gltf").write_text(json.dumps({
        "asset": {"version": "2.0"},
        "buffers": [{"uri": "M.bin", "byteLength": 4},
                    {"uri": "data:application/octet-stream;base64,AAAA"}],
        "images": [{"uri": "M%20tex.png"}]}), encoding="utf-8")
    (models / "M.bin").write_bytes(bin_)
    (models / "M tex.png").write_bytes(tex)
    return models / "M.gltf"


def test_i_membri_sono_quelli_che_il_gltf_nomina(tmp_path):
    gltf = _gltf(tmp_path)
    (gltf.parent / "other.png").write_bytes(b"not mine")
    membri = rd.gltf_members(str(gltf))
    assert [m["path"] for m in membri] == ["M.bin", "M tex.png"]


def _bake(g, gltf):
    rl.assicura_master(g, master_id="M_res_blend", url="blend://scene.blend#Object/M",
                       name="datablock for M", link_to="M_model")
    return rl.registra_derivata(
        g, derivata_id="M_model_link", url="models/M.gltf",
        source_id="M_res_blend", link_to="M_model", name="GLTF for M",
        file_esportato=str(gltf), membri=rd.gltf_members(str(gltf)))


def _grafo_con_rm():
    from s3dgraphy.nodes.representation_node import RepresentationModelNode
    g = Graph("g")
    g.add_node(RepresentationModelNode(node_id="M_model", name="Model for M", type="RM",
                                       description=""))
    return g


def test_un_gltf_separato_e_una_risorsa_file_set(tmp_path):
    g = _grafo_con_rm()
    ok, avvisi = _bake(g, _gltf(tmp_path))
    assert ok and not avvisi
    n = g.find_node_by_id("M_model_link")
    assert n.data["packaging"] == "file_set"
    assert n.data["tier"] == "distribution"
    files = api.resource_files(g, "M_model_link")
    assert [(f["role"], f["path"]) for f in files] == [
        ("entry_point", "M.gltf"), ("member", "M tex.png"), ("member", "M.bin")]
    assert all(not f["implicit"] for f in files)
    assert files[2]["node"].data["checksum"] == rl.sha256_del_file(str(tmp_path / "models/M.bin"))
    # il digest della risorsa è la lista canonica di dtcstamp
    specs = [{"role": f["role"], "path": f["path"], "checksum": f["node"].data["checksum"]}
             for f in files]
    assert n.data["checksum"] == rd.members_digest(specs)
    assert n.data["checksum_of"] == "members"
    assert n.data["size_bytes"] == sum(os.path.getsize(tmp_path / "models" / p)
                                       for p in ("M.gltf", "M.bin", "M tex.png"))
    # dtc_derived_from verso il master
    assert any(e.edge_type == "dtc_derived_from" and e.edge_source == "M_model_link"
               and e.edge_target == "M_res_blend" for e in g.edges)
    # la porta resta dove Heriverse guarda (`canConsumeResource` legge data.url)
    assert n.data["url"] == "models/M.gltf" and n.data["url_type"] == "3d_model"


def test_rifare_lo_stesso_export_non_cambia_niente(tmp_path):
    g = _grafo_con_rm()
    gltf = _gltf(tmp_path)
    _bake(g, gltf)
    prima = build_emjson(g)
    _bake(g, gltf)
    assert build_emjson(g)["graphs"] == prima["graphs"]


def test_un_glb_resta_un_file(tmp_path):
    g = _grafo_con_rm()
    glb = tmp_path / "M.glb"
    glb.write_bytes(b"glTF....")
    ok, _ = rl.registra_derivata(g, derivata_id="M_model_link", url="models/M.glb",
                                 link_to="M_model", file_esportato=str(glb))
    assert ok
    files = api.resource_files(g, "M_model_link")
    assert len(files) == 1 and files[0]["implicit"]
    assert g.find_node_by_id("M_model_link").data["checksum"] == rl.sha256_del_file(str(glb))


def test_un_gltf_registrato_ieri_come_un_file_si_descrive_per_intero(tmp_path):
    """Gli stessi byte di prima: non è una revisione, è la stessa risorsa
    descritta per intero (la porta passa nel suo nodo, una volta sola)."""
    g = _grafo_con_rm()
    gltf = _gltf(tmp_path)
    rl.registra_derivata(g, derivata_id="M_model_link", url="models/M.gltf",
                         link_to="M_model", file_esportato=str(gltf))  # come prima
    assert api.resource_files(g, "M_model_link")[0]["implicit"]
    _bake(g, gltf)
    files = api.resource_files(g, "M_model_link")
    assert len(files) == 3 and not files[0]["implicit"]
    assert not [e for e in g.edges if e.edge_type == "was_revision_of"]


# ── dtc_authoring: un wrapper sottile ────────────────────────────────────────

def test_la_risorsa_dtc_passa_per_la_libreria():
    dg = _load("dtc_authoring/dtc_graph.py", "_emtools_test_dtc_graph")
    if not dg.dtc_supported():
        pytest.skip("s3dgraphy without the DTC profile")
    g = Graph("g")
    kind = dg.dtc_kinds()["input"][0]
    rid = dg.add_dtc_resource(g, kind, url="photos/")
    n = g.find_node_by_id(rid)
    assert n.node_type == "resource"
    assert n.data["dtc_kind"] == kind and n.data["resource_type"] == kind
    assert n.data["url"] == "photos/" and n.name == f"{kind} 1"
    assert not hasattr(dg, "add_resource")


# ── un grafo di EMtools di prima si apre e si salva senza differenze ─────────

def _sezione(doc):
    """Nodi e archi, ordinati: ciò che un grafo DICE (non l'header)."""
    graphs = doc.get("graphs") or {}
    out = {}
    for gid, sec in graphs.items():
        out[gid] = {"nodes": sorted(sec.get("nodes") or [], key=lambda n: n["id"]),
                    "edges": sorted(sec.get("edges") or [], key=lambda e: e["id"])}
    return out


def test_un_grafo_di_prima_si_apre_e_si_salva_senza_differenze():
    """La fixture l'ha scritta il codice di `cb25e71` con la dev23
    (`.claude/wip/reports/2026-10-25-risorsa-file/make_old_fixture.py`): master
    senza packaging, glTF come un file solo, tileset con `checksum_of:
    entry-point`. Aperto e salvato con la dev25, dice le stesse cose."""
    graph, _warnings = import_emjson(str(FIXTURE))
    prima = json.loads(FIXTURE.read_text(encoding="utf-8"))
    dopo = build_emjson(graph)
    assert _sezione(dopo) == _sezione(prima)
    # e chi legge ricava quello che la fixture non dichiara, senza scriverlo
    master = graph.find_node_by_id("M_model_res_blend")
    assert "packaging" not in master.data
    assert master.effective_packaging() == "datablock"
