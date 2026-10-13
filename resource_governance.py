"""Lo storage governa le versioni — chi è corrente, chi è storia, chi è ritirato.

Misurato nella stanza `tavolo-2026-10-12` (13 ott 2026): E.D. modifica il
proxy di US2, «Sync the scene…» manda la revisione, e la scena riceve indietro
ANCHE la vecchia. Quattro difetti, quattro regole:

1. **La migrazione chiude la forma vecchia.** ``<US>.model`` (la convenzione
   di EMtools fino alla dev.14) passava i suoi byte alla risorsa canonica della
   catena e restava viva: `geometry_summary` la contava resident, niente la
   superava, e appena il digest spariva dalla scena `materialise` la riportava.
   Ora si TOGLIE dal grafo (tombstone del nodo e dei suoi archi) — vedi
   `close_legacy_models` per il perché di questa scelta.
2. **La revisione sposta la citazione.** L'arco spostato teneva lo stesso id
   (`move_citations` sostituisce l'id vecchio nell'id dell'arco, e un id
   coniato da s3Dgraphy non lo contiene): il delta verso la stanza confronta
   per id e non vedeva nulla, e la stanza (come il Blender che applica un
   `add_edge`) scarta un arco con un id che ha già. Ora l'arco spostato ha un id
   suo (`resource_revisions.move_citations`).
3. **Una revisione per un invio.** Si rivede la revisione CORRENTE, mai una
   vecchia (sarebbe un ramo), e se ha già quei byte non si scrive niente.
4. **Lo Storage panel governa**: «Use» (`use_version`), «Withdraw from the
   room» (`withdraw_plan`, `withdraw`) e il suo «Undo» (`undo_withdraw`), lo
   stato di un oggetto in scena (`object_status`).

E.D., 13 ott 2026 (MICRO lo storage parla come una persona): «se voglio
tornare a una versione precedente mi ritrovo che si crea un'ulteriore versione
futura». Misurato: due andate e ritorni = quattro revisioni. Quindi:

5. **La versione corrente è quella CITATA** (`in_use`), non la testa della
   catena. «Use» sposta il puntatore — la citazione passa a quella versione —
   e non crea niente; le più recenti restano storia. Una revisione nasce solo
   da byte nuovi, mai uguali a una versione della catena: byte che una
   versione ha già spostano il puntatore su di lei.
6. **Una risorsa non si riscrive.** Misurato alle 09:20:17 UTC: `promote_model`
   passava a `promote_resource` una risorsa che aveva già i suoi byte, e quella
   sovrascriveva ``checksum`` e ``url``. Chi scrive byte passa da
   `write_bytes`: nessun byte → si scrivono; gli stessi → niente; altri → una
   revisione. Cambia solo la FORMA (`normalise_formats`): ``sha256:<hex>``, e
   un indirizzo dello store su un'unica base (`room_base`).
7. **Nomi, mai codici** (`display_name`): una risorsa si chiama come ciò che
   la cita («US 2 — proxy», «Epoch 1 — RM»), mai col suo digest.

Niente `bpy`: si misura con pytest (`tests/test_storage_versions.py`,
`tests/test_storage_readable.py`).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional

EDGE_REVISION_OF = "was_revision_of"
EDGE_LINKED = "has_linked_resource"
EDGE_HAS_FILE = "has_file"
LEGACY_MODEL_SUFFIX = ".model"

STATUS_CURRENT = ""
STATUS_SUPERSEDED = "superseded"
STATUS_WITHDRAWN = "withdrawn"


def _rr():
    """`resource_revisions`, dentro l'add-on (pacchetto) o fuori (pytest)."""
    try:
        from . import resource_revisions
    except ImportError:
        import resource_revisions
    return resource_revisions


def _pc():
    try:
        from . import proxy_chain
    except ImportError:
        import proxy_chain
    return proxy_chain


# ── leggere ─────────────────────────────────────────────────────────────────

def bare_digest(value: Any) -> str:
    """``sha256:ab…`` e ``ab…`` sono lo stesso digest."""
    text = str(value or "").strip().lower()
    return text[7:] if text.startswith("sha256:") else text


def full_digest(value: Any) -> str:
    """Un digest come lo si scrive: sempre ``sha256:<hex>`` (vuoto se non c'è).
    Misurato il 13 ott 2026: una revisione con ``e5228d…`` senza prefisso, che
    la cache della scena (``sha256:…``) non riconosceva."""
    bare = bare_digest(value)
    return f"sha256:{bare}" if bare else ""


def digest_of(graph, res_id: str) -> str:
    node = graph.find_node_by_id(res_id)
    data = getattr(node, "data", None) if node is not None else None
    return bare_digest((data or {}).get("checksum") if isinstance(data, dict) else "")


def chain_of(graph, res_id: str) -> List[str]:
    """Le revisioni della risorsa, dalla più vecchia alla corrente (una catena
    che si biforca: la risorsa da sola, che la decida chi l'ha fatta)."""
    from s3dgraphy import api
    try:
        return api.revisions_of(graph, res_id)
    except ValueError:
        return [res_id]


def head_of(graph, res_id: str) -> str:
    return chain_of(graph, res_id)[-1]


def in_use(graph, res_id: str) -> str:
    """La versione IN USO della catena di `res_id`: quella CITATA (da una
    forma, un RM, un documento). «Use» sposta la citazione, e la versione in
    uso con lei; le più recenti restano storia. Più versioni citate (chi cita
    sceglie: un RM può tenere la sua): la più recente fra quelle. Nessuna
    citata: la più recente della catena."""
    chain = chain_of(graph, res_id)
    for member in reversed(chain):
        if citing(graph, member):
            return member
    return chain[-1]


def revision_info(graph, ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """Per ogni id: ``{head, chain, index, in_use}`` — la più recente della sua
    catena, la catena (vecchia → recente), il posto che ci occupa e la
    versione in uso. Lo Storage panel fa una riga per catena con questo."""
    out: Dict[str, Dict[str, Any]] = {}
    for rid in ids:
        if rid in out or graph.find_node_by_id(rid) is None:
            continue
        chain = chain_of(graph, rid)
        used = in_use(graph, chain[-1])
        for i, member in enumerate(chain):
            out[member] = {"head": chain[-1], "chain": list(chain), "index": i,
                           "in_use": used}
    return out


def citing(graph, res_id: str) -> List[Dict[str, Any]]:
    """Le CITAZIONI della risorsa: gli archi che entrano, tranne le sue
    revisioni e la catena DTC (fatti sui byte, non citazioni)."""
    rr = _rr()
    cites, _chain = rr.split_pointers(rr.pointing_at(graph, res_id))
    for c in cites:
        src = graph.find_node_by_id(c["source"])
        c["source_name"] = getattr(src, "name", None) or c["source"]
        c["source_type"] = getattr(src, "node_type", "") if src is not None else ""
    return cites


# ── 1 · la forma vecchia si chiude ──────────────────────────────────────────

def _owned_files(graph, members: Iterable[str]) -> List[str]:
    """I nodi-file che solo questi membri contengono."""
    members = set(members)
    files = {e.edge_target for e in graph.edges
             if e.edge_type == EDGE_HAS_FILE and e.edge_source in members}
    return sorted(f for f in files
                  if not any(e.edge_type == EDGE_HAS_FILE and e.edge_target == f
                             and e.edge_source not in members for e in graph.edges))


def close_legacy_models(graph, unit_ids: Optional[Iterable[str]] = None
                        ) -> Dict[str, Any]:
    """Le ``<US>.model`` rimaste vive dopo la migrazione escono dal grafo.

    Una ``<US>.model`` (o la sua catena di revisioni) si chiude quando:

    * la sua unità non la cita più (la migrazione l'ha passata alla catena
      canonica; finché la cita, è da migrare, non da chiudere);
    * la catena canonica dell'unità ha, in una delle sue revisioni, gli STESSI
      byte della ``<US>.model`` corrente — i fatti sui byte sono passati;
    * nient'altro la cita (un RM, un documento): allora si dice e resta.

    **Tombstone, non ``was_revision_of``.** La ``<US>.model`` e la risorsa
    canonica hanno lo stesso digest: non sono due versioni, sono la stessa
    pubblicazione scritta in due forme, una delle quali solo EMtools leggeva.
    Una revisione direbbe «questi byte ne hanno corretti altri», che non è
    vero; e se la canonica è già una revisione di qualcosa, il secondo
    ``was_revision_of`` la renderebbe un'unione che `revisions_of` rifiuta. La
    genesi (``dtc_had_output``) è già sulla canonica, i byte restano nello
    store della stanza: si toglie dal grafo il doppione, nient'altro.

    Si chiude la CATENA intera della ``<US>.model``: togliere solo la corrente
    farebbe tornare corrente la sua revisione precedente — e la scena la
    riavrebbe. Insieme vanno i nodi-file che solo lei conteneva.

    Idempotente. Ripara anche le stanze migrate prima di questa regola.
    → ``{closed: [{unit_id, removed: [ids], canonical}], warnings}``.
    """
    from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
    glb_proxy = _pc().glb_proxy

    wanted = set(unit_ids) if unit_ids is not None else None
    report: Dict[str, Any] = {"closed": [], "warnings": []}
    for base in [n for n in list(graph.nodes)
                 if getattr(n, "node_type", "") == "resource"
                 and str(n.node_id).endswith(LEGACY_MODEL_SUFFIX)]:
        unit_id = base.node_id[:-len(LEGACY_MODEL_SUFFIX)]
        unit = graph.find_node_by_id(unit_id)
        if not isinstance(unit, StratigraphicNode):
            continue
        if wanted is not None and unit_id not in wanted:
            continue
        if graph.find_node_by_id(base.node_id) is None:
            continue                         # già tolta in questo passaggio
        members = chain_of(graph, base.node_id)
        if members[0] != base.node_id:
            continue                         # è la revisione di altro: non è sua
        if any(e.edge_type == EDGE_LINKED and e.edge_source == unit_id
               and e.edge_target in members for e in graph.edges):
            continue                         # ancora citata: da migrare, non da chiudere
        _shape, canonical = glb_proxy(graph, unit_id)
        if canonical is None:
            continue
        legacy_digest = digest_of(graph, members[-1])
        canonical_chain = chain_of(graph, canonical.node_id)
        if not legacy_digest or legacy_digest not in {
                digest_of(graph, r) for r in canonical_chain}:
            report["warnings"].append(
                f"{unit_id}: '{members[-1]}' holds bytes its proxy chain does not; left as it is")
            continue
        others = [c for m in members for c in citing(graph, m)
                  if c["source"] not in members]
        if others:
            report["warnings"].append(
                f"{unit_id}: '{members[-1]}' is still cited by "
                f"{', '.join(sorted({c['source_name'] for c in others}))}; left as it is")
            continue
        removed = list(members) + _owned_files(graph, members)
        for nid in removed:
            graph.remove_node(nid)
        report["closed"].append({"unit_id": unit_id, "removed": removed,
                                 "canonical": head_of(graph, canonical.node_id)})
    return report


# ── 2 · il puntatore, e i byte che arrivano ─────────────────────────────────

def point_to(graph, res_id: str) -> int:
    """Le citazioni della catena di `res_id` passano a `res_id`: il puntatore
    si sposta, nessun nodo nasce. Gli archi della catena DTC restano sui loro
    byte (`resource_revisions.move_citations`). → quante citazioni."""
    rr = _rr()
    moved = 0
    for member in chain_of(graph, res_id):
        if member == res_id:
            continue
        cites, _staying = rr.split_pointers(rr.pointing_at(graph, member))
        if cites:
            moved += rr.move_citations(graph, member, res_id, [c["edge_id"] for c in cites])
    return moved


def revise_and_cite(graph, res_id: str, spec: Dict[str, Any], *,
                    residency: Optional[str] = "resident") -> Dict[str, Any]:
    """I byte di `spec` (``{path, url, checksum, size_bytes, media_type}``)
    per la risorsa `res_id`, e la citazione su di loro.

    * la versione IN USO ha già quei byte → niente (un secondo sync identico è
      un sync che non c'è stato);
    * li ha un'altra versione della catena → il puntatore va su di lei
      (``reused``): mai due versioni con gli stessi byte;
    * byte nuovi → una revisione della PIÙ RECENTE della catena (mai di una
      vecchia: sarebbe un ramo), e la citazione su di lei.

    → ``{resource_id, revision_of, created, moved, reused}``: ``resource_id``
    è la versione che ora porta quei byte ed è citata."""
    revisions = _rr()
    want = bare_digest(spec.get("checksum"))
    spec = {**spec, "checksum": full_digest(want)}
    chain = chain_of(graph, res_id)
    used = in_use(graph, res_id)
    if digest_of(graph, used) == want:
        return {"resource_id": used, "revision_of": None, "created": False,
                "moved": 0, "reused": None}
    same = next((m for m in reversed(chain) if digest_of(graph, m) == want), None)
    if same is not None:
        return {"resource_id": same, "revision_of": None, "created": False,
                "moved": point_to(graph, same), "reused": same}
    head = chain[-1]
    out = revisions.revise_files(graph, head, [spec])
    new_id = out.get("new_resource_id")
    if not new_id:
        return {"resource_id": head, "revision_of": None, "created": False,
                "moved": point_to(graph, head), "reused": head}
    node = graph.find_node_by_id(new_id)
    if node is not None:
        node.data = dict(getattr(node, "data", None) or {})
        fields = {"url": spec.get("url"), "checksum": spec["checksum"],
                  "media_type": spec.get("media_type"), "size_bytes": spec.get("size_bytes"),
                  "residency": residency}
        node.data.update({k: v for k, v in fields.items() if v not in (None, "")})
        if hasattr(node, "url") and spec.get("url"):
            node.url = spec["url"]
    return {"resource_id": new_id, "revision_of": head, "created": True,
            "moved": point_to(graph, new_id), "reused": None}


def write_bytes(graph, res_id: str, spec: Dict[str, Any], *,
                residency: Optional[str] = "resident") -> Dict[str, Any]:
    """Chi pubblica byte su una risorsa che c'è passa di qui: una risorsa non
    si riscrive mai (decisione del 30 set 2026). Misurato il 13 ott, 09:20:17
    UTC: `promote_model` mandava i byte del proxy a `promote_resource`, che su
    una risorsa con il suo ``checksum`` sovrascriveva ``checksum`` e ``url``.

    → ``{action, …}``: ``write`` (la risorsa non ha ancora byte: chi chiama li
    scrive, è la sua nascita), altrimenti il risultato di `revise_and_cite`
    con ``action`` ``same`` / ``pointer`` / ``revision``."""
    if graph.find_node_by_id(res_id) is None or \
            not any(digest_of(graph, m) for m in chain_of(graph, res_id)):
        return {"action": "write", "resource_id": res_id, "created": False}
    out = revise_and_cite(graph, res_id, spec, residency=residency)
    out["action"] = ("revision" if out["created"] else
                     "pointer" if out.get("reused") else "same")
    return out


# ── 4 · i gesti dello Storage panel ─────────────────────────────────────────

def use_version(graph, res_id: str) -> Dict[str, Any]:
    """«Use»: la versione scelta torna in uso — il PUNTATORE si sposta.

    La citazione (forma, RM, documento → risorsa) passa a questa versione;
    nessuna revisione nasce, le più recenti restano storia («a later version
    exists», un clic per tornarci). Fino al 13 ott 2026 si faceva una
    revisione nuova con i byte scelti: due andate e ritorni erano quattro
    revisioni (misurato su US2). → ``{resource_id, from, moved, created}``;
    ``created`` è sempre False."""
    if graph.find_node_by_id(res_id) is None:
        raise ValueError(f"{res_id!r} is not in the graph")
    before = in_use(graph, res_id)
    moved = 0 if before == res_id else point_to(graph, res_id)
    return {"resource_id": res_id, "from": before, "moved": moved,
            "created": False, "revision_of": None, "chosen": res_id}


def versions(graph, res_id: str, *, people: Optional[Dict[str, str]] = None
             ) -> List[Dict[str, Any]]:
    """Le versioni della catena, dalla prima: ``[{id, n, at, by, in_use,
    later, digest}]`` — «v2 · 11:24 · Editor Due · in use». ``at`` e ``by``
    sono il timbro di nascita che la stanza scrive su ogni nodo; ``people``
    traduce un id in un nome (le persone presenti nella stanza)."""
    people = people or {}
    chain = chain_of(graph, res_id)
    used = in_use(graph, res_id)
    used_at = chain.index(used) if used in chain else len(chain) - 1
    out = []
    for i, member in enumerate(chain):
        node = graph.find_node_by_id(member)
        data = getattr(node, "data", None) if node is not None else None
        data = data if isinstance(data, dict) else {}
        by = str(data.get("created_by") or data.get("modified_by") or "")
        out.append({"id": member, "n": i + 1, "of": len(chain),
                    "at": str(data.get("created_at") or data.get("modified_at") or ""),
                    "by": people.get(by, by), "in_use": member == used,
                    "later": i > used_at, "digest": full_digest(digest_of(graph, member))})
    return out


def object_status(graph, res_id: str, digest: str = "", *,
                  removed: Iterable[str] = ()) -> str:
    """Lo stato di un oggetto in scena legato a `res_id`, con i byte `digest`:

    * ``withdrawn`` — la risorsa non è più nel grafo e la stanza (o questo
      Blender) l'ha tolta (`removed`: gli id dei tombstone);
    * ``superseded`` — un'altra versione della catena è IN USO, con altri byte
      (quella più recente o quella più vecchia: decide la citazione);
    * ``""`` — in uso (anche se legato a un'altra versione con gli stessi
      byte di quella in uso: è la stessa geometria).

    Un oggetto segnato si toglie dalla scena con un gesto, mai da solo."""
    if not res_id:
        return STATUS_CURRENT
    if graph.find_node_by_id(res_id) is None:
        return STATUS_WITHDRAWN if res_id in set(removed) else STATUS_CURRENT
    used = in_use(graph, res_id)
    if used == res_id:
        return STATUS_CURRENT
    mine = bare_digest(digest) or digest_of(graph, res_id)
    return STATUS_CURRENT if mine and mine == digest_of(graph, used) else STATUS_SUPERSEDED


def withdraw_plan(graph, res_id: str) -> Dict[str, Any]:
    """Che cosa toglie «Withdraw from the room»: la risorsa con TUTTA la sua
    catena di revisioni (nel pannello è una voce sola), i nodi-file che solo
    lei contiene, e chi la cita — da dire prima di chiedere conferma.
    → ``{members, files, citing: [{edge_id, edge_type, source, source_name}]}``."""
    members = chain_of(graph, res_id)
    cites = [c for m in members for c in citing(graph, m) if c["source"] not in members]
    return {"members": members, "files": _owned_files(graph, members), "citing": cites}


def withdraw(graph, res_id: str) -> Dict[str, Any]:
    """Ritira la risorsa dal grafo: i nodi del piano tolti con i loro archi (la
    stanza li riceve come tombstone, firmati da chi li manda). I byte restano
    nello store come storia: nessuno li cancella. → il piano eseguito."""
    plan = withdraw_plan(graph, res_id)
    for nid in plan["members"] + plan["files"]:
        if graph.find_node_by_id(nid) is not None:
            graph.remove_node(nid)
    return plan


# ── 4b · il ritiro si annulla finché la stanza lo ricorda ───────────────────

def withdrawal_record(section: Dict[str, Any], plan: Dict[str, Any], *,
                      by: str = "", at: str = "") -> Dict[str, Any]:
    """Quello che un ritiro toglie, preso dalla sezione em.json di PRIMA: i nodi
    del piano e gli archi che li toccano. È ciò che «Undo» rimette.
    → ``{id, nodes, edges, by, at, cited_by}``."""
    gone = set(plan.get("members") or []) | set(plan.get("files") or [])
    nodes = [dict(n) for n in section.get("nodes") or [] if n.get("id") in gone]
    edges = [dict(e) for e in section.get("edges") or []
             if e.get("source") in gone or e.get("target") in gone]
    members = list(plan.get("members") or [])
    return {"id": members[-1] if members else "", "members": members,
            "nodes": nodes, "edges": edges, "by": by, "at": at,
            "cited_by": sorted({e.get("source") for e in edges
                                if e.get("edge_type") == EDGE_LINKED
                                and e.get("target") in gone})}


def withdrawn_in_section(section: Dict[str, Any]) -> List[Dict[str, Any]]:
    """I ritiri che la stanza tiene in tombstone (la sua istantanea li porta,
    il merge ne ha bisogno): una voce per catena di risorse tolte, con chi e
    quando (``data.removed = {ts, by}``). Le ``<US>.model`` chiuse dalla
    migrazione non sono ritiri di qualcuno: non si offrono."""
    from s3dgraphy import crdt
    nodes = [n for n in section.get("nodes") or [] if isinstance(n, dict)]
    dead = {n.get("id"): n for n in nodes
            if n.get("node_type") in ("resource", "resource_file") and crdt.is_removed(n)}
    if not dead:
        return []
    edges = [e for e in section.get("edges") or [] if isinstance(e, dict)]
    parent: Dict[str, str] = {nid: nid for nid in dead}

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for e in edges:
        if e.get("edge_type") in (EDGE_REVISION_OF, EDGE_HAS_FILE) and \
                e.get("source") in dead and e.get("target") in dead:
            parent[root(e["source"])] = root(e["target"])
    groups: Dict[str, List[str]] = {}
    for nid in dead:
        groups.setdefault(root(nid), []).append(nid)
    out = []
    for ids in groups.values():
        resources = [i for i in ids if dead[i].get("node_type") == "resource"]
        if not resources or any(str(i).endswith(LEGACY_MODEL_SUFFIX) for i in resources):
            continue
        older = {e.get("target") for e in edges if e.get("edge_type") == EDGE_REVISION_OF
                 and e.get("source") in ids}
        newest = next((i for i in sorted(resources) if i not in older), sorted(resources)[0])
        mark = (dead[newest].get("data") or {}).get("removed") or {}
        clean = []
        for i in ids:
            payload = dict(dead[i])
            payload["data"] = {k: v for k, v in (payload.get("data") or {}).items()
                               if k != "removed"}
            clean.append(payload)
        touching = []
        for e in edges:
            if e.get("source") in ids or e.get("target") in ids:
                edge = dict(e)
                attrs = {k: v for k, v in (e.get("attributes") or {}).items() if k != "removed"}
                if attrs:
                    edge["attributes"] = attrs
                else:
                    edge.pop("attributes", None)
                touching.append(edge)
        out.append({"id": newest, "members": sorted(resources), "nodes": clean,
                    "edges": touching, "by": str(mark.get("by") or ""),
                    "at": str(mark.get("ts") or ""),
                    "cited_by": sorted({e.get("source") for e in touching
                                        if e.get("edge_type") == EDGE_LINKED
                                        and e.get("target") in ids})})
    return out


def undo_ops(record: Dict[str, Any], *, at: str) -> List[Dict[str, Any]]:
    """«Undo» di un ritiro, come operazioni: i nodi rimessi (``add_node``) e
    una scrittura su ciascuno più recente del tombstone (``data.restored_at``:
    nel merge, chi scrive dopo chi ha cancellato vince), poi gli archi
    (un ``add_edge`` più recente della rimozione la annulla)."""
    ops: List[Dict[str, Any]] = []
    for node in record.get("nodes") or []:
        ops.append({"op": "add_node", "id": node["id"], "node": dict(node)})
        ops.append({"op": "update_field", "node_id": node["id"],
                    "field": "data.restored_at", "value": at})
    for e in record.get("edges") or []:
        ops.append({"op": "add_edge", "id": e.get("id"), "source": e.get("source"),
                    "target": e.get("target"), "edge_type": e.get("edge_type")})
    return ops


# ── 5 · nomi, mai codici ────────────────────────────────────────────────────

_CODE = re.compile(r"(?i)(?<![0-9a-z])(?:sha256:)?[0-9a-f]{12,}"
                   r"|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_RM_TYPES = ("representation_model", "representation_model_doc", "representation_model_sf")


def looks_like_code(text: Any) -> bool:
    """Un digest (12+ cifre esadecimali) o un UUID: non è un nome."""
    return bool(_CODE.search(str(text or "")))


def _unit_of_shape(graph, shape_id: str):
    for e in graph.edges:
        if e.edge_type == "has_semantic_shape" and e.edge_target == shape_id:
            for f in graph.edges:
                if f.edge_type == "has_property" and f.edge_target == e.edge_source:
                    return graph.find_node_by_id(f.edge_source)
    return None


def _is_unit(node) -> bool:
    try:
        from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
    except Exception:  # noqa: BLE001
        return False
    return isinstance(node, StratigraphicNode)


def citer_name(graph, source_id: str) -> str:
    """Il nome di ciò che cita una risorsa, detto per quello che è: «US 2 —
    proxy», «Epoch 1 — RM», il titolo di un documento. Vuoto se non sa
    dirlo senza un codice."""
    src = graph.find_node_by_id(source_id)
    if src is None:
        return ""
    kind = str(getattr(src, "node_type", "") or "")
    name = str(getattr(src, "name", "") or "")
    if kind == "semantic_shape":
        unit = _unit_of_shape(graph, source_id)
        uname = str(getattr(unit, "name", "") or "") if unit is not None else ""
        said = f"{uname} — proxy" if uname else ""
    elif kind in _RM_TYPES:
        said = f"{name} — RM" if name else ""
    elif _is_unit(src):
        # la forma di prima dell'1.6.0-dev.14: l'unità cita il suo glb
        said = f"{name} — proxy" if name else ""
    else:
        data = getattr(src, "data", None)
        title = str((data or {}).get("title") or "") if isinstance(data, dict) else ""
        said = f"{name} · {title}" if title and title != name else name
    return "" if looks_like_code(said) else said


def display_name(graph, res_id: str) -> str:
    """Il nome di una risorsa (della sua catena) per una persona: ciò che la
    cita, poi il suo nome se non è un codice, poi il nome del file. Mai un
    digest né un UUID — quelli vanno nei «Details»."""
    try:
        chain = chain_of(graph, res_id)
    except Exception:  # noqa: BLE001
        chain = [res_id]
    for member in reversed(chain):
        try:
            cites = citing(graph, member)
        except Exception:  # noqa: BLE001 — a graph without edge ids: by its own name
            cites = []
        for c in cites:
            said = citer_name(graph, c["source"])
            if said:
                return said
    node = graph.find_node_by_id(chain[-1]) or graph.find_node_by_id(res_id)
    name = str(getattr(node, "name", "") or "")
    for suffix in (" (glTF)", ".glb"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    if name.startswith("Link to "):
        name = name[8:]
    if name and not looks_like_code(name):
        return name
    data = getattr(node, "data", None) if node is not None else None
    data = data if isinstance(data, dict) else {}
    for where in (data.get("filename"), data.get("path"), data.get("url")):
        seg = str(where or "").rstrip("/").split("/")[-1].split("?")[0]
        if seg and not looks_like_code(seg):
            return seg
    media = str(data.get("media_type") or "")
    return "Unnamed 3D model" if "gltf" in media or "model" in media else "Unnamed file"


def readable(text: Any, fallback: str = "Unnamed file") -> str:
    """Un'etichetta che non mostra codici: se ne ha, il ripiego."""
    text = str(text or "")
    return fallback if not text or looks_like_code(text) else text


# ── 6 · formati uniformi ────────────────────────────────────────────────────

_STORE_URL = re.compile(r"^(?P<base>[a-z][a-z0-9+.-]*://[^?#]*?)/v1/rooms/(?P<room>[^/?#]+)"
                        r"/asset/(?P<ref>[^/?#]+)$", re.I)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def parse_store_url(url: Any) -> Optional[Dict[str, str]]:
    """``…/v1/rooms/<room>/asset/<digest>`` → ``{base, room, digest}``."""
    import urllib.parse
    m = _STORE_URL.match(str(url or "").strip())
    if not m:
        return None
    return {"base": m.group("base").rstrip("/"),
            "room": urllib.parse.unquote(m.group("room")),
            "digest": bare_digest(urllib.parse.unquote(m.group("ref")))}


def store_url(base: str, room_id: str, digest: Any) -> str:
    """L'indirizzo di byte nello store della stanza, nella forma unica."""
    import urllib.parse
    return (f"{str(base).rstrip('/')}/v1/rooms/{urllib.parse.quote(str(room_id), safe='')}"
            f"/asset/{full_digest(digest)}")


def room_base(graph, room_id: str, *, declared: str = "", connected: str = "") -> str:
    """La base con cui si scrive l'``url`` di una risorsa resident.

    Misurato il 13 ott 2026: tre host per la stessa stanza
    (``localhost:8000``, ``em.localhost:8443/em``, ``<mac>.local:8000``) —
    l'host con cui il client di turno era collegato. La scelta:

    1. la base pubblica che il NODO dichiara (``GET /v1/node`` →
       ``public_base``, configurata con ``EM_PUBLIC_BASE``): l'unico indirizzo
       che il nodo stesso garantisce raggiungibile da un'altra macchina;
    2. altrimenti la base che la stanza usa GIÀ di più (pari: la prima in
       ordine): tutti i client leggono lo stesso grafo e convergono sulla
       stessa, senza che nessuno la inventi;
    3. una stanza ancora senza indirizzi: la base con cui si è collegati.

    Non una forma relativa: EMStudio riconosce un indirizzo dello store solo
    assoluto (`store-url.ts`, ``ROOM_URL``) e, fuori linea, legge l'``url``
    com'è scritto. Chi è nella stanza legge comunque per digest."""
    if declared:
        return declared.rstrip("/")
    seen: Counter = Counter()
    for n in getattr(graph, "nodes", []) or []:
        data = getattr(n, "data", None)
        parsed = parse_store_url((data or {}).get("url") if isinstance(data, dict) else "")
        if parsed and parsed["room"] == room_id:
            seen[parsed["base"]] += 1
    if seen:
        top = max(seen.values())
        return sorted(b for b, k in seen.items() if k == top)[0]
    return str(connected or "").rstrip("/")


def normalise_formats(graph, room_id: str = "", base: str = "") -> List[str]:
    """Ripara la FORMA dei fatti sui byte, mai i fatti: ``checksum`` senza
    prefisso → ``sha256:<hex>``; un ``url`` dello store di questa stanza su
    un'altra base → la base unica (solo se nomina gli stessi byte del
    ``checksum``). → gli id cambiati."""
    changed = []
    for n in list(getattr(graph, "nodes", []) or []):
        if getattr(n, "node_type", "") not in ("resource", "resource_file"):
            continue
        data = getattr(n, "data", None)
        if not isinstance(data, dict):
            continue
        touched = False
        raw = str(data.get("checksum") or "").strip()
        if raw and _HEX64.match(raw.lower()):
            data["checksum"] = full_digest(raw)
            touched = True
        parsed = parse_store_url(data.get("url"))
        if parsed and room_id and base and parsed["room"] == room_id and \
                (not data.get("checksum") or parsed["digest"] == bare_digest(data["checksum"])):
            want = store_url(base, room_id, parsed["digest"])
            if data["url"] != want:
                data["url"] = want
                if hasattr(n, "url"):
                    try:
                        n.url = want
                    except Exception:  # noqa: BLE001
                        pass
                touched = True
        if touched:
            changed.append(n.node_id)
    return changed
