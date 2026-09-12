"""P1 · Il DATO del Publication Deck — una riga di tabella è un fatto.

Il deck risponde a una domanda sola: *cosa manca perché questo em.json sia
consumabile fuori da Blender?* Questo modulo è la metà che si calcola, e si
prova senza aprire Blender — che è anche il motivo per cui esiste separata dal
pannello: `stato_risorse` costa un `os.stat` per derivata, e un pannello si
ridisegna a ogni movimento del mouse.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent

_pkg = types.ModuleType("emt_deck"); _pkg.__path__ = [str(ROOT)]
sys.modules["emt_deck"] = _pkg
for _n in ("resource_audit", "publication_gesture", "publication_deck"):
    _sp = importlib.util.spec_from_file_location(f"emt_deck.{_n}", ROOT / f"{_n}.py")
    _m = importlib.util.module_from_spec(_sp)
    sys.modules[f"emt_deck.{_n}"] = _m
    _sp.loader.exec_module(_m)                     # type: ignore[union-attr]
PD = sys.modules["emt_deck.publication_deck"]


class N:
    def __init__(self, node_id, tipo="resource", nome="", **dati):
        self.node_id = node_id
        self.node_type = tipo
        self.name = nome or node_id
        self.data = dati


class E:
    def __init__(self, tipo, sorgente, destinazione):
        self.edge_type = tipo
        self.edge_source = sorgente
        self.edge_target = destinazione


def un_grafo():
    """La scena che il deck deve saper mostrare: un master, una
    bakeata, una pubblicata, una stantia, un'irrisolvibile e un tileset di
    container."""
    nodi = [
        N("muro_model", tipo="representation_model", nome="muro"),
        N("muro_model_res_blend", nome="datablock",
          url="blend://s.blend#Object/muro", tier="master"),
        N("muro_model_link", nome="GLTF for muro", url="models/muro.gltf",
          tier="distribution", packaging="file", size_bytes=1147),
        N("porta_model", tipo="representation_model", nome="porta"),
        N("porta_model_link", nome="GLTF for porta",
          url="s3://em/porta.glb", tier="distribution", packaging="file",
          size_bytes=2048, checksum="sha256:aa"),
        N("vecchio_model", tipo="representation_model", nome="vecchio"),
        N("vecchio_model_res_blend", url="blend://s.blend#Object/vecchio",
          tier="master"),
        N("vecchio_model_link", nome="GLTF for vecchio",
          url="models/vecchio.gltf", tier="distribution",
          source_fingerprint="struct:f=6:v=8", size_bytes=900),
        N("muto_model_res_blend", url="", tier="master", unresolved=True),
        N("tileset_model", tipo="representation_model", nome="tileset_ricostr"),
        N("tileset_model_link", nome="Tileset for ricostr",
          url="tilesets/r/tileset.json", tier="distribution",
          packaging="directory", size_bytes=151, checksum="sha256:bb",
          checksum_of="entry-point"),
        N("proc_vecchio", tipo="dtc_process", created_at="2026-09-14T10:00:00Z"),
        N("proc_porta", tipo="dtc_process", modified_at="2026-09-15T08:30:00Z"),
    ]
    archi = [
        E("has_linked_resource", "muro_model", "muro_model_res_blend"),
        E("has_linked_resource", "muro_model", "muro_model_link"),
        E("has_linked_resource", "porta_model", "porta_model_link"),
        E("has_linked_resource", "vecchio_model", "vecchio_model_res_blend"),
        E("has_linked_resource", "vecchio_model", "vecchio_model_link"),
        E("has_linked_resource", "tileset_model", "tileset_model_link"),
        E("dtc_had_output", "proc_vecchio", "vecchio_model_link"),
        E("dtc_had_input", "proc_vecchio", "vecchio_model_res_blend"),
        E("dtc_had_output", "proc_porta", "porta_model_link"),
    ]
    return nodi, archi


def impronta_cambiata(nodo):
    """La sorgente di `vecchio` è cambiata; le altre non si sanno."""
    return "struct:f=24:v=26" if nodo.node_id == "vecchio_model_res_blend" else ""


def container_di(rm_id):
    return ({"id": "c0", "label": "Reconstruction", "membri": 2}
            if rm_id == "tileset_model" else None)


def calcola(**kw):
    nodi, archi = un_grafo()
    return PD.righe(nodi, archi, impronta_attuale=impronta_cambiata,
                    container_di=container_di, esiste=lambda p: True, **kw)


def per_id(esito):
    return {r["id"]: r for r in esito["righe"]}


# ── gli stati ───────────────────────────────────────────────────────────────

def test_ogni_stato_della_scala_e_riconosciuto():
    r = per_id(calcola())
    assert r["muro_model_res_blend"]["stato"] == "master"
    assert r["muro_model_link"]["stato"] == "baked"
    assert r["porta_model_link"]["stato"] == "published"
    assert r["vecchio_model_link"]["stato"] == "stale"
    assert r["muto_model_res_blend"]["stato"] == "unresolved"


def test_una_pubblicata_STANTIA_si_dice_stantia_e_non_pubblicata():
    """L'ordine di precedenza che conta: una pubblicata stantia è IL caso che
    il deck esiste per mostrare, e chiamarla «published» la nasconderebbe."""
    nodi, archi = un_grafo()
    for n in nodi:
        if n.node_id == "vecchio_model_link":
            n.data.update(url="s3://em/vecchio.glb", checksum="sha256:cc")
    esito = PD.righe(nodi, archi, impronta_attuale=impronta_cambiata,
                     container_di=container_di, esiste=lambda p: True)
    assert per_id(esito)["vecchio_model_link"]["stato"] == "stale"


def test_un_master_non_si_pubblica_e_la_riga_lo_dice():
    r = per_id(calcola())["muro_model_res_blend"]
    assert not r["pubblicabile"]["si"]
    assert "archived, not published" in r["pubblicabile"]["perche"]


def test_i_master_COMPAIONO_nel_deck():
    """Sapere che una catena ha la sua fonte al sicuro è metà della risposta
    alla domanda «cosa manca»."""
    assert "muro_model_res_blend" in per_id(calcola())


# ── le due granularità ──────────────────────────────────────────────────────

def test_la_riga_di_un_tileset_NON_finge_di_essere_un_modello():
    r = per_id(calcola())
    assert r["tileset_model_link"]["granularita"] == "container"
    assert r["tileset_model_link"]["etichetta_proprietario"] == "Reconstruction"
    assert r["tileset_model_link"]["membri"] == 2
    assert r["muro_model_link"]["granularita"] == "rm"
    assert r["muro_model_link"]["membri"] == 0


# ── cosa mostra una riga ────────────────────────────────────────────────────

def test_dove_stanno_i_byte_col_vocabolario_che_esiste():
    r = per_id(calcola())
    assert r["muro_model_res_blend"]["dove"] == "blend"
    assert r["muro_model_link"]["dove"] == "disk"
    assert r["porta_model_link"]["dove"] == "store"


def test_formato_impacchettamento_e_peso():
    r = per_id(calcola())
    assert r["muro_model_link"]["formato"] == "gltf"
    assert r["muro_model_res_blend"]["formato"] == "blend"
    assert r["tileset_model_link"]["packaging"] == "directory"
    assert r["tileset_model_link"]["checksum_of"] == "entry-point"
    assert r["porta_model_link"]["peso"] == "2.0 KB"


def test_un_peso_assente_resta_assente():
    """Uno `0 B` inventato direbbe «file vuoto», che è una misura e non
    un'assenza."""
    assert PD._peso_leggibile(None) == ""
    assert PD._peso_leggibile(0) == "0 B"


def test_la_data_dell_ultima_pubblicazione_viene_dall_evento():
    """Non è un campo della risorsa: la risorsa dice *cosa è*, l'evento dice
    *quando è successo*."""
    r = per_id(calcola())
    assert r["porta_model_link"]["pubblicata_il"] == "2026-09-15T08:30:00Z"
    assert r["muro_model_link"]["pubblicata_il"] == ""


def test_sulle_stantie_si_dice_COSA_e_cambiato():
    """Mostrare le due impronte intere direbbe solo che sono diverse — che è
    ciò che l'utente già sa, visto che è per quello che la riga è lì."""
    assert per_id(calcola())["vecchio_model_link"]["cosa_e_cambiato"] == \
        "faces 6 → 24, vertices 8 → 26"


def test_due_impronte_di_famiglia_diversa_non_si_confrontano_campo_per_campo():
    assert "shape" in PD._cosa_e_cambiato("mtime:1:size:2", "struct:v=8")


def test_la_riga_porta_le_sorgenti_della_sua_derivazione():
    assert per_id(calcola())["vecchio_model_link"]["sorgenti"] == \
        ["vecchio_model_res_blend"]


# ── il sommario ─────────────────────────────────────────────────────────────

def test_il_sommario_conta_quello_che_la_testa_mostra():
    s = calcola()["sommario"]
    #: SETTE risorse: tre master (muro, vecchio, il muto), tre distribution
    #: (muro, porta, vecchio) e il tileset. Il primo giro di questa prova ne
    #: contava sei — avevo contato le RIGHE che avevo in mente invece dei nodi
    #: che avevo scritto.
    assert s["assets"] == 7
    #: UNA sola pubblicata: `porta`, che sta nello store. Il tileset ha il suo
    #: checksum ma un url relativo, quindi è `baked` — e questa prova al primo
    #: giro pretendeva due, cioè ripeteva esattamente l'euristica sbagliata di
    #: Heriverse («ha il checksum, quindi è la pubblicata»). Il codice aveva
    #: ragione e l'aspettativa no.
    assert s["published"] == 1
    assert s["stale"] == 1
    assert PD.riga_di_sintesi(s) == "7 assets · 1 published · 1 stale"


def test_un_CHECKSUM_da_solo_non_fa_una_pubblicata():
    """L'euristica che Heriverse usava e che NIGHT-RES ha tolto: il checksum
    dice che quei byte sono verificabili, non che qualcuno da fuori li possa
    prendere. «Pubblicata» è locator raggiungibile **e** checksum."""
    r = per_id(calcola())["tileset_model_link"]
    assert r["checksum"] and r["dove"] == "disk"
    assert r["stato"] == "baked"


def test_il_sommario_dice_quanti_se_ne_possono_pubblicare_adesso():
    """Dirlo evita di offrire un gesto che poi rifiuta riga per riga."""
    assert calcola()["sommario"]["pubblicabili"] >= 1


def test_un_progetto_senza_risorse_da_un_deck_vuoto_e_non_un_errore():
    esito = PD.righe([], [])
    assert esito["righe"] == []
    assert esito["sommario"]["assets"] == 0
    assert PD.riga_di_sintesi(esito["sommario"]) == \
        "0 assets · 0 published · 0 stale"


# ── pronto per chi ──────────────────────────────────────────────────────────

def test_le_destinazioni_sono_N_fin_dall_inizio():
    """Heriverse è la prima, la stanza StratiGraph è già la seconda:
    aggiungere la seconda a una struttura fatta per una sola è il genere di
    refactor che non si fa più."""
    esito = calcola(destinazioni={
        "heriverse": lambda d: {"ok": d.get("packaging") != "archive",
                                "why": "" if d.get("packaging") != "archive"
                                       else "cannot unpack"},
        "room": lambda d: {"ok": True, "why": ""},
    })
    r = per_id(esito)["muro_model_link"]
    assert set(r["pronto_per"]) == {"heriverse", "room"}
    assert r["pronto_per"]["heriverse"]["ok"]


def test_una_destinazione_senza_giudice_e_un_NO_con_la_ragione():
    esito = calcola(destinazioni={"ignota": None})
    r = per_id(esito)["muro_model_link"]["pronto_per"]["ignota"]
    assert not r["ok"] and r["why"]


def test_senza_destinazioni_la_colonna_e_semplicemente_vuota():
    assert per_id(calcola())["muro_model_link"]["pronto_per"] == {}


def test_pubblicare_una_STANTIA_non_la_fa_diventare_fresca():
    """IL DIFETTO CHE IL DECK HA TROVATO, e che nessuna prova prendeva.

    Il bake scrive un processo D7 con un ingresso (il master) e un'uscita (la
    derivata). La PUBBLICAZIONE ne scrive un secondo, che ha un'uscita e
    **nessun ingresso** — perché l'atto è «questi byte vanno nello store», non
    «questi byte vengono da lì».

    `stato_risorse` teneva un processo solo per derivata, l'ultimo visto:
    dopo una pubblicazione vinceva quello senza ingressi, la sorgente non si
    trovava più, e la derivata usciva dalle stantie. **Pubblicare una stantia
    la faceva smettere di risultare stantia** — cioè il «è aggiornato»
    sbagliato che pubblica roba vecchia credendola fresca, che è precisamente
    ciò contro cui tutta questa catena è costruita.

    Trovato misurando un giro completo contro un MinIO vero, non leggendo.
    """
    nodi, archi = un_grafo()
    #: il secondo processo, quello della pubblicazione: uscita e basta
    nodi.append(N("proc_pubblicazione", tipo="dtc_process",
                  modified_at="2026-09-15T12:00:00Z"))
    archi.append(E("dtc_had_output", "proc_pubblicazione", "vecchio_model_link"))
    esito = PD.righe(nodi, archi, impronta_attuale=impronta_cambiata,
                     container_di=container_di, esiste=lambda p: True)
    assert per_id(esito)["vecchio_model_link"]["stato"] == "stale", (
        "una stantia pubblicata è ancora stantia")
    assert esito["sommario"]["stale"] == 1


def test_una_derivata_con_PIU_sorgenti_e_stantia_se_ne_cambia_una():
    """Il tileset: accorpa N mesh, ed è stantio se ne cambia **una
    qualunque**. Conservativo nel verso giusto."""
    nodi, archi = un_grafo()
    nodi.append(N("altro_master", url="blend://s.blend#Object/altro",
                  tier="master"))
    archi.append(E("dtc_had_input", "proc_vecchio", "altro_master"))

    def solo_il_secondo(nodo):
        return "struct:f=99:v=99" if nodo.node_id == "altro_master" else ""

    esito = PD.righe(nodi, archi, impronta_attuale=solo_il_secondo,
                     container_di=container_di, esiste=lambda p: True)
    assert per_id(esito)["vecchio_model_link"]["stato"] == "stale"
