"""MICRO risorsa-file, parte 2 — sostituire, non sovrascrivere.

Una texture riesportata dà una REVISIONE (`api.replace_file`): l'RM segue se
si sceglie «tutti», la vecchia resta citabile coi suoi byte, e la catena DTC
dei byte vecchi (`dtc_had_output`) non si sposta.
"""

from __future__ import annotations

import json

from s3dgraphy import api
from s3dgraphy.graph import Graph
from s3dgraphy.nodes.representation_node import RepresentationModelNode

import resource_digest as rd
import resource_levels as rl
import resource_revisions as rr


def _gltf(folder, tex):
    folder.mkdir(exist_ok=True)
    (folder / "M.gltf").write_text(json.dumps({
        "asset": {"version": "2.0"}, "buffers": [{"uri": "M.bin", "byteLength": 4}],
        "images": [{"uri": "M_tex.png"}]}), encoding="utf-8")
    (folder / "M.bin").write_bytes(b"BIN!")
    (folder / "M_tex.png").write_bytes(tex)
    return folder / "M.gltf"


def _grafo():
    g = Graph("g")
    g.add_node(RepresentationModelNode(node_id="M_model", name="Model for M", type="RM",
                                       description=""))
    rl.assicura_master(g, master_id="M_res_blend", url="blend://s.blend#Object/M",
                       name="datablock for M", link_to="M_model")
    return g


def _bake(g, gltf):
    return rl.registra_derivata(
        g, derivata_id="M_model_link", url="models/M.gltf", source_id="M_res_blend",
        link_to="M_model", name="GLTF for M", file_esportato=str(gltf),
        membri=rd.gltf_members(str(gltf)))


def _cita(g, src, dst, tipo="has_linked_resource"):
    return any(e.edge_source == src and e.edge_target == dst and e.edge_type == tipo
               for e in g.edges)


def test_una_texture_riesportata_da_una_revisione(tmp_path):
    g = _grafo()
    gltf = _gltf(tmp_path / "models", b"PNG-v1")
    _bake(g, gltf)
    vecchia = g.find_node_by_id("M_model_link")
    digest_vecchio = vecchia.data["checksum"]
    file_vecchi = {f["path"]: f["node"].node_id for f in api.resource_files(g, "M_model_link")}

    (tmp_path / "models" / "M_tex.png").write_bytes(b"PNG-v2")   # la riesportazione
    ok, avvisi = _bake(g, gltf)
    assert ok and "revisione" in avvisi

    nuova_id = api.current_revision(g, "M_model_link")
    assert nuova_id != "M_model_link"
    assert api.revisions_of(g, nuova_id) == ["M_model_link", nuova_id]
    nuova = g.find_node_by_id(nuova_id)
    # la vecchia è com'era: stessi file, stesso digest
    assert vecchia.data["checksum"] == digest_vecchio
    assert {f["path"]: f["node"].node_id
            for f in api.resource_files(g, "M_model_link")} == file_vecchi
    # la nuova: stessi file tranne la texture, che deriva dalla vecchia
    nuovi = {f["path"]: f["node"] for f in api.resource_files(g, nuova_id)}
    assert nuovi["M.gltf"].node_id == file_vecchi["M.gltf"]
    assert nuovi["M.bin"].node_id == file_vecchi["M.bin"]
    assert nuovi["M_tex.png"].node_id != file_vecchi["M_tex.png"]
    assert any(e.edge_type == "dtc_derived_from" and e.edge_source == nuovi["M_tex.png"].node_id
               and e.edge_target == file_vecchi["M_tex.png"] for e in g.edges)
    # la nuova ha la porta dove Heriverse guarda, e il digest dei suoi file
    assert nuova.data["url"] == "models/M.gltf"
    assert nuova.data["checksum"] != digest_vecchio
    assert nuova.data["packaging"] == "file_set"
    # chi citava la vecchia non si è spostato da solo
    assert _cita(g, "M_model", "M_model_link") and not _cita(g, "M_model", nuova_id)
    attesa = rr.pending_revisions(g)
    assert [(r["old_id"], r["new_id"]) for r in attesa] == [("M_model_link", nuova_id)]


def test_tutti_sposta_l_rm_ma_non_la_catena(tmp_path):
    g = _grafo()
    gltf = _gltf(tmp_path / "models", b"PNG-v1")
    _bake(g, gltf)
    (tmp_path / "models" / "M_tex.png").write_bytes(b"PNG-v2")
    _bake(g, gltf)
    nuova_id = api.current_revision(g, "M_model_link")
    citing, staying = rr.split_pointers(rr.pointing_at(g, "M_model_link"))
    assert {p["edge_type"] for p in citing} == {"has_linked_resource"}
    assert "dtc_had_output" in {p["edge_type"] for p in staying}
    # «tutti», compresa la catena chiesta per sbaglio: la catena non si muove
    moved = rr.move_citations(g, "M_model_link", nuova_id,
                              [p["edge_id"] for p in citing + staying])
    assert moved == len(citing)
    assert _cita(g, "M_model", nuova_id) and not _cita(g, "M_model", "M_model_link")
    assert any(e.edge_type == "dtc_had_output" and e.edge_target == "M_model_link"
               for e in g.edges)
    assert rr.pending_revisions(g) == []


def test_la_vecchia_resta_citabile(tmp_path):
    g = _grafo()
    gltf = _gltf(tmp_path / "models", b"PNG-v1")
    _bake(g, gltf)
    (tmp_path / "models" / "M_tex.png").write_bytes(b"PNG-v2")
    _bake(g, gltf)
    nuova_id = api.current_revision(g, "M_model_link")
    rr.move_citations(g, "M_model_link", nuova_id,
                      [p["edge_id"] for p in rr.pointing_at(g, "M_model_link")])
    vecchia = g.find_node_by_id("M_model_link")
    assert vecchia is not None and vecchia.data["checksum"]
    assert len(api.resource_files(g, "M_model_link")) == 3
    # e un documento può ancora citarla
    g.add_edge("doc_cita_vecchia", "M_model", "M_model_link", "has_linked_resource")
    assert _cita(g, "M_model", "M_model_link")


def test_lo_stesso_export_due_volte_non_fa_revisioni(tmp_path):
    g = _grafo()
    gltf = _gltf(tmp_path / "models", b"PNG-v1")
    _bake(g, gltf)
    _bake(g, gltf)
    assert api.current_revision(g, "M_model_link") == "M_model_link"


def test_la_terza_esportazione_rivede_l_ultima(tmp_path):
    g = _grafo()
    gltf = _gltf(tmp_path / "models", b"PNG-v1")
    _bake(g, gltf)
    for v in (b"PNG-v2", b"PNG-v3"):
        (tmp_path / "models" / "M_tex.png").write_bytes(v)
        _bake(g, gltf)
    catena = api.revisions_of(g, "M_model_link")
    assert len(catena) == 3 and catena[0] == "M_model_link"


def test_un_glb_cambiato_da_una_revisione_di_un_file(tmp_path):
    g = _grafo()
    glb = tmp_path / "M.glb"
    glb.write_bytes(b"glTF-v1")
    rl.registra_derivata(g, derivata_id="M_model_link", url="models/M.glb",
                         link_to="M_model", file_esportato=str(glb))
    glb.write_bytes(b"glTF-v2")
    ok, avvisi = rl.registra_derivata(g, derivata_id="M_model_link", url="models/M.glb",
                                      link_to="M_model", file_esportato=str(glb))
    nuova_id = api.current_revision(g, "M_model_link")
    assert ok and nuova_id != "M_model_link"
    assert g.find_node_by_id(nuova_id).data["checksum"] == rl.sha256_del_file(str(glb))
    assert g.find_node_by_id(nuova_id).data["url"] == "models/M.glb"


def test_un_proxy_con_i_suoi_byte_non_si_sposta_prima_del_bake():
    """`proxy_resource_for_export` non riscrive il locator di una risorsa che
    ha già un digest: lo fa il bake, che rivede se i byte sono cambiati."""
    import proxy_chain as pc
    g = Graph("g")
    from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit
    g.add_node(StratigraphicUnit(node_id="us-1", name="US01"))
    r = pc.ensure_unit_proxy(g, "us-1", "US01")
    res = g.find_node_by_id(r["resource_id"])
    res.data["checksum"] = "sha256:" + "0" * 64
    res.data["url"] = "proxies/US01.glb"
    _s, _r, changed = pc.proxy_resource_for_export(g, ["us-1"], "proxies/US01_bis.glb")
    assert changed and res.data["url"] == "proxies/US01.glb"
