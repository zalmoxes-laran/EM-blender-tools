"""Il proxy come proprietà, il glb come risorsa (`proxy_chain`), misurato.

La parte Blender (abbinare l'oggetto per nome, esportare il glb) sta in
`tests/blender_smoke_proxy_chain.py`; qui si misura quello che finisce nel
grafo, con s3Dgraphy vero:

* due unità → la catena nuova, e nessun ``US ─has_semantic_shape→`` diretto;
* un secondo aggiornamento lascia il grafo IDENTICO;
* l'export aggiorna la RISORSA (non l'url della forma), e la distribution è
  quella risorsa, non un secondo nodo con lo stesso file;
* un em.json scritto dal codice di prima si apre e si riscrive nella forma
  nuova, e l'aggiornamento successivo ritrova il proxy migrato invece di
  coniarne un altro.
"""

import hashlib
import importlib.util
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent

s3dgraphy_api = pytest.importorskip(
    "s3dgraphy.api", reason="s3dgraphy not importable (checkout or wheel)")
if not hasattr(s3dgraphy_api, "geometry_to_gltf"):  # pragma: no cover
    pytest.skip("s3dgraphy without the proxy_model resource (< 30 set 2026 source)",
                allow_module_level=True)

from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.resource_node import ResourceNode  # noqa: E402
from s3dgraphy.nodes.semantic_shape_node import SemanticShapeNode  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


PC = _load("proxy_chain", "proxy_chain.py")
RL = _load("resource_levels", "resource_levels.py")


def _graph():
    g = Graph("g")
    g.add_node(StratigraphicUnit("us-1", "US01"))
    g.add_node(StratigraphicUnit("us-2", "US02"))
    return g


def _snapshot(g):
    nodes = {n.node_id: (n.node_type, n.name, repr(sorted((getattr(n, "data", {}) or {}).items())))
             for n in g.nodes}
    edges = {(e.edge_id, e.edge_source, e.edge_type, e.edge_target) for e in g.edges}
    return nodes, edges


def _out(g, source, edge_type):
    return [g.find_node_by_id(e.edge_target) for e in g.edges
            if e.edge_source == source and e.edge_type == edge_type]


def _assert_new_chain(g, unit_id, url):
    assert not _out(g, unit_id, "has_semantic_shape"), \
        "la US non deve più puntare la forma direttamente"
    props = [p for p in _out(g, unit_id, "has_property")
             if getattr(p, "property_type", None) == "geometry"]
    assert len(props) == 1
    shapes = _out(g, props[0].node_id, "has_semantic_shape")
    assert len(shapes) == 1 and shapes[0].node_type == "semantic_shape"
    assert not (shapes[0].data or {}).get("url"), "il percorso non sta più sulla forma"
    res = [r for r in _out(g, shapes[0].node_id, "has_linked_resource")
           if (r.data or {}).get("url_type") == "proxy_model"]
    assert len(res) == 1
    assert res[0].data["url"] == url
    return props[0], shapes[0], res[0]


# ── 1 · due proxy → la catena nuova ─────────────────────────────────────────

def test_due_proxy_producono_la_catena_nuova():
    g = _graph()
    r1 = PC.ensure_unit_proxy(g, "us-1", "US01")
    r2 = PC.ensure_unit_proxy(g, "us-2", "US02")
    assert r1["created"] and r2["created"]
    assert not r1["warnings"] and not r2["warnings"]
    p1, s1, res1 = _assert_new_chain(g, "us-1", "proxies/US01.glb")
    p2, s2, res2 = _assert_new_chain(g, "us-2", "proxies/US02.glb")
    assert s1.node_id != s2.node_id and res1.node_id != res2.node_id
    # gli id sono quelli di s3Dgraphy: deterministici
    from s3dgraphy.geometry.proxy import proxy_resource_id
    assert res1.node_id == proxy_resource_id(s1.node_id)
    assert s1.name == "Shape for US01"


def test_gli_id_non_dipendono_dalla_sessione():
    a, b = _graph(), _graph()
    ra = PC.ensure_unit_proxy(a, "us-1", "US01")
    rb = PC.ensure_unit_proxy(b, "us-1", "US01")
    assert (ra["shape_id"], ra["property_id"], ra["resource_id"]) == \
        (rb["shape_id"], rb["property_id"], rb["resource_id"])


# ── 2 · un secondo aggiornamento lascia il grafo uguale ─────────────────────

def test_un_secondo_aggiornamento_lascia_il_grafo_uguale():
    g = _graph()
    for uid, name in (("us-1", "US01"), ("us-2", "US02")):
        PC.ensure_unit_proxy(g, uid, name)
    PC.migrate_old_proxies(g)
    prima = _snapshot(g)
    for uid, name in (("us-1", "US01"), ("us-2", "US02")):
        assert PC.ensure_unit_proxy(g, uid, name)["created"] is False
    assert PC.migrate_old_proxies(g) == {"properties": 0, "resources": 0, "warnings": []}
    assert _snapshot(g) == prima


def test_il_percorso_scelto_dall_export_non_viene_rimesso():
    """L'export scrive il nome pulito; l'aggiornamento dopo non lo riporta al
    nome grezzo (se no il grafo oscillerebbe a ogni click)."""
    g = Graph("g")
    g.add_node(StratigraphicUnit("us-1", "US 01"))
    PC.ensure_unit_proxy(g, "us-1", "US 01")
    PC.proxy_resource_for_export(g, ["us-1"], "proxies/US_01.glb")
    PC.ensure_unit_proxy(g, "us-1", "US 01")
    _assert_new_chain(g, "us-1", "proxies/US_01.glb")


def test_un_proxy_convesso_non_e_un_proxy_glb():
    """Il bbox di `sync_manager.commands` è un altro proxy della stessa unità:
    non ha risorsa, non viene riusato come glb e non viene toccato."""
    g = _graph()
    s3dgraphy_api.create_geometry_proxy(g, "us-1", {"convexshapes": [[0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]]})
    r = PC.ensure_unit_proxy(g, "us-1", "US01")
    assert r["created"]
    assert len(PC.geometry_shapes(g, "us-1")) == 2


# ── 3 · l'export Heriverse aggiorna la risorsa ─────────────────────────────

def test_l_export_aggiorna_la_risorsa_e_la_distribution_e_quella(tmp_path):
    g = _graph()
    for uid, name in (("us-1", "US01"), ("us-2", "US02")):
        PC.ensure_unit_proxy(g, uid, name)
    n_prima = len(g.nodes)
    for name in ("US01", "US02"):
        glb = tmp_path / f"{name}.glb"
        glb.write_bytes(b"glTF" + name.encode())
        shape_id, res_id, changed = PC.proxy_resource_for_export(
            g, PC.units_named(g, name), f"proxies/{name}.glb")
        assert shape_id and res_id and changed is False
        ok, perche = RL.registra_derivata(
            g, derivata_id=res_id, url=f"proxies/{name}.glb", link_to=shape_id,
            name=f"Proxy for {name}", file_esportato=str(glb))
        assert ok, perche
        res = g.find_node_by_id(res_id)
        assert res.data["url_type"] == "proxy_model"
        assert res.data["checksum"] == "sha256:" + hashlib.sha256(glb.read_bytes()).hexdigest()
        assert res.data.get("tier") == "distribution"
        # un nodo solo per il glb: niente `<forma>_link` accanto
        assert g.find_node_by_id(f"{shape_id}_link") is None
        _assert_new_chain(g, PC.units_named(g, name)[0], f"proxies/{name}.glb")
    # solo il processo del bake (D7) è nuovo, nessuna seconda risorsa
    nuove = [n for n in g.nodes[n_prima:]]
    assert all(n.node_type != "resource" for n in nuove), [n.node_id for n in nuove]


def test_l_export_senza_proxy_lo_dice():
    g = _graph()
    assert PC.proxy_resource_for_export(g, ["us-1"], "proxies/US01.glb") == (None, None, False)


def test_il_json_heriverse_proietta_il_percorso_sulla_forma():
    """Heriverse legge `semantic_shapes[id].data.url`: il JSON di s3Dgraphy lo
    proietta dalla risorsa. La verità resta una."""
    from s3dgraphy.exporter.json_exporter import JSONExporter
    g = _graph()
    r = PC.ensure_unit_proxy(g, "us-1", "US01")
    PC.proxy_resource_for_export(g, ["us-1"], "proxies/US01.glb")
    nodes = JSONExporter.__new__(JSONExporter)._process_nodes(g)
    assert nodes["semantic_shapes"][r["shape_id"]]["data"]["url"] == "proxies/US01.glb"
    # e il grafo non ne tiene una seconda copia
    assert "url" not in (g.find_node_by_id(r["shape_id"]).data or {})


# ── 4 · un em.json vecchio si apre e si riscrive nuovo ──────────────────────

def _old_graph():
    """Quello che EMtools scriveva fino a bf9b193: forma `<US>_shape` con l'url,
    arco diretto dalla US, e la distribution `<US>_shape_link` dell'export."""
    g = _graph()
    for uid, name in (("us-1", "US01"), ("us-2", "US02")):
        sid = f"{name}_shape"
        g.add_node(SemanticShapeNode(node_id=sid, name=f"Shape for {name}",
                                     type="proxy", url=f"proxies/{name}.glb"))
        g.add_edge(f"{uid}_has_shape_{sid}", uid, sid, "has_semantic_shape")
    # l'export vecchio (`promote_resource` senza media_type) lasciava il tipo
    # di default di ResourceNode: «External link»
    link = ResourceNode("US01_shape_link", name="Proxy for US01",
                        url="proxies/US01.glb")
    g.add_node(link)
    g.add_edge("e-link", "US01_shape", "US01_shape_link", "has_linked_resource")
    return g


def test_un_em_json_vecchio_si_apre_e_si_riscrive_nella_forma_nuova():
    old = _old_graph()
    doc = s3dgraphy_api.graph_to_emjson(old)
    # misura: il documento vecchio ha davvero la forma vecchia
    import json
    testo = json.dumps(doc)
    assert '"proxies/US01.glb"' in testo

    g, _warnings = s3dgraphy_api.load_emjson(doc)
    for uid, name in (("us-1", "US01"), ("us-2", "US02")):
        _p, shape, res = _assert_new_chain(g, uid, f"proxies/{name}.glb")
        assert shape.node_id == f"{name}_shape"          # l'id migrato resta
    # la distribution dell'export vecchio È la risorsa, non un doppione
    assert _assert_new_chain(g, "us-1", "proxies/US01.glb")[2].node_id == "US01_shape_link"

    prima = _snapshot(g)
    for uid, name in (("us-1", "US01"), ("us-2", "US02")):
        assert PC.ensure_unit_proxy(g, uid, name)["created"] is False
    assert _snapshot(g) == prima, "l'aggiornamento ha coniato un secondo proxy"

    riscritto = s3dgraphy_api.graph_to_emjson(g)
    g2, _ = s3dgraphy_api.load_emjson(riscritto)
    assert _snapshot(g2)[1] == _snapshot(g)[1]
    for uid, name in (("us-1", "US01"), ("us-2", "US02")):
        _assert_new_chain(g2, uid, f"proxies/{name}.glb")


def test_la_forma_vecchia_in_memoria_si_migra_prima_di_cercare():
    """Un grafo costruito in sessione dal codice di prima (nessun em.json in
    mezzo): `update_semantic_shapes` lo migra e poi ritrova il proxy."""
    g = _old_graph()
    rep = PC.migrate_old_proxies(g)
    assert rep["properties"] == 2 and rep["resources"] == 2
    for uid, name in (("us-1", "US01"), ("us-2", "US02")):
        r = PC.ensure_unit_proxy(g, uid, name)
        assert r["created"] is False and r["shape_id"] == f"{name}_shape"
        _assert_new_chain(g, uid, f"proxies/{name}.glb")


def test_una_risorsa_gia_3d_non_fa_nascere_un_secondo_proxy():
    """s3Dgraphy dev23: la migrazione ritipizza `proxy_model` la risorsa della
    forma che fa da proxy, anche se era `3d_model`. `glb_proxy` la trova per
    tipo, senza il ripiego sul percorso `proxies/…` che serviva con la dev22."""
    g = _old_graph()
    g.find_node_by_id("US01_shape_link").data["url_type"] = "3d_model"
    PC.migrate_old_proxies(g)
    link = g.find_node_by_id("US01_shape_link")
    assert link.data["url_type"] == "proxy_model"
    r = PC.ensure_unit_proxy(g, "us-1", "US01")
    assert r["created"] is False
    assert r["resource_id"] == "US01_shape_link"
    assert len(PC.geometry_shapes(g, "us-1")) == 1


def test_una_risorsa_proxies_non_proxy_model_non_e_un_proxy_glb():
    """Tolto il ripiego: una risorsa col percorso `proxies/…` che la
    migrazione non ha ritipizzato non passa per un proxy-glb."""
    g = _graph()
    PC.ensure_unit_proxy(g, "us-1", "US01")
    shape, res = PC.glb_proxy(g, "us-1")
    res.data["url_type"] = "3d_model"
    assert PC.glb_proxy(g, "us-1") == (None, None)
