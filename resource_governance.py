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
4. **Lo Storage panel governa**: «Use this version» (`use_version`),
   «Withdraw from the room» (`withdraw_plan`, `withdraw`), lo stato di un
   oggetto in scena (`object_status`).

Niente `bpy`: si misura con pytest (`tests/test_storage_versions.py`).
"""

from __future__ import annotations

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


def is_superseded(graph, res_id: str) -> bool:
    return any(e.edge_type == EDGE_REVISION_OF and e.edge_target == res_id
               for e in graph.edges)


def revision_info(graph, ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """Per ogni id: ``{head, chain, index}`` — la corrente della sua catena,
    la catena (vecchia → corrente) e il posto che ci occupa. Lo Storage
    panel raggruppa le righe con questo."""
    out: Dict[str, Dict[str, Any]] = {}
    for rid in ids:
        if rid in out or graph.find_node_by_id(rid) is None:
            continue
        chain = chain_of(graph, rid)
        for i, member in enumerate(chain):
            out[member] = {"head": chain[-1], "chain": list(chain), "index": i}
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


# ── 2 · le citazioni seguono la revisione corrente dei proxy ────────────────

def forward_proxy_citations(graph) -> List[Dict[str, Any]]:
    """Una SemanticShape che cita una revisione SUPERATA passa alla corrente.

    Solo le forme dei proxy: il proxy di un'unità è la geometria che la scena
    manda, e la sua revisione corrente è quella; un RM o un documento che cita
    una revisione vecchia resta dov'è e lo propone il pannello delle risorse
    (decisione del 30 set: chi cita non si sposta da solo). Ripara le stanze
    in cui il sync ha creato la revisione senza che la citazione arrivasse.
    → ``[{shape, old, new}]``."""
    move_citations = _rr().move_citations
    moved = []
    for e in list(graph.edges):
        if e.edge_type != EDGE_LINKED:
            continue
        src = graph.find_node_by_id(e.edge_source)
        if getattr(src, "node_type", "") != "semantic_shape":
            continue
        if graph.find_node_by_id(e.edge_target) is None or \
                not is_superseded(graph, e.edge_target):
            continue
        head = head_of(graph, e.edge_target)
        if head == e.edge_target:
            continue
        if move_citations(graph, e.edge_target, head, [e.edge_id]):
            moved.append({"shape": e.edge_source, "old": e.edge_target, "new": head})
    return moved


def revise_and_cite(graph, res_id: str, spec: Dict[str, Any], *,
                    residency: Optional[str] = "resident") -> Dict[str, Any]:
    """I byte di `spec` (``{path, url, checksum, size_bytes, media_type}``)
    come revisione di `res_id`, con le citazioni spostate.

    Si rivede la revisione CORRENTE della catena di `res_id`, mai una vecchia:
    un oggetto legato a una revisione superata che manda byte nuovi farebbe
    altrimenti un ramo. Se la corrente ha già quei byte non si scrive niente
    (``same``): un secondo sync identico è un sync che non c'è stato.

    → ``{resource_id, revision_of, created, moved}``: ``resource_id`` è la
    risorsa che ora porta quei byte."""
    revisions = _rr()

    head = head_of(graph, res_id)
    if digest_of(graph, head) == bare_digest(spec.get("checksum")):
        return {"resource_id": head, "revision_of": None, "created": False, "moved": 0}
    out = revisions.revise_files(graph, head, [spec])
    new_id = out.get("new_resource_id")
    if not new_id:
        return {"resource_id": head, "revision_of": None, "created": False, "moved": 0}
    node = graph.find_node_by_id(new_id)
    if node is not None:
        node.data = dict(getattr(node, "data", None) or {})
        fields = {"url": spec.get("url"), "checksum": spec.get("checksum"),
                  "media_type": spec.get("media_type"), "size_bytes": spec.get("size_bytes"),
                  "residency": residency}
        node.data.update({k: v for k, v in fields.items() if v not in (None, "")})
        if hasattr(node, "url") and spec.get("url"):
            node.url = spec["url"]
    cites, _staying = revisions.split_pointers(revisions.pointing_at(graph, head))
    moved = revisions.move_citations(graph, head, new_id, [c["edge_id"] for c in cites])
    return {"resource_id": new_id, "revision_of": head, "created": True, "moved": moved}


# ── 4 · i gesti dello Storage panel ─────────────────────────────────────────

_BYTE_FIELDS = ("url", "checksum", "media_type", "size_bytes", "residency")


def use_version(graph, res_id: str) -> Dict[str, Any]:
    """«Use this version»: i byte di una revisione passata tornano correnti.

    Non si spostano le citazioni INDIETRO sulla revisione vecchia: resterebbe
    superata (la scena non la riceverebbe, il pannello delle risorse
    proporrebbe di riportarle avanti). Si fa invece una revisione nuova della
    corrente con i byte scelti — la storia dice «tornati a quelli» — e le
    citazioni vanno lì, come a ogni revisione. → come `revise_and_cite`, più
    ``chosen``."""
    from s3dgraphy import api
    chosen = graph.find_node_by_id(res_id)
    if chosen is None:
        raise ValueError(f"{res_id!r} is not in the graph")
    head = head_of(graph, res_id)
    if head == res_id:
        return {"resource_id": res_id, "revision_of": None, "created": False,
                "moved": 0, "chosen": res_id}
    data = dict(getattr(chosen, "data", None) or {})
    files = api.resource_files(graph, res_id)
    if len(files) <= 1:
        path = files[0]["path"] if files else (data.get("url") or res_id)
        spec = {"path": path, **{k: data[k] for k in _BYTE_FIELDS
                                 if k in data and k != "residency"}}
        out = revise_and_cite(graph, head, spec, residency=data.get("residency"))
    else:
        revisions = _rr()
        specs = []
        for f in files:
            fdata = dict(getattr(f["node"], "data", None) or {})
            specs.append({"path": f["path"], "checksum": fdata.get("checksum"),
                          "url": fdata.get("url") or f["path"],
                          "size_bytes": fdata.get("size_bytes")})
        rev = revisions.revise_files(graph, head, specs, force=True)
        new_id = rev.get("new_resource_id") or head
        node = graph.find_node_by_id(new_id)
        if node is not None and new_id != head:
            node.data = {**dict(getattr(node, "data", None) or {}),
                         **{k: data[k] for k in _BYTE_FIELDS if k in data}}
        cites, _ = revisions.split_pointers(revisions.pointing_at(graph, head))
        moved = revisions.move_citations(graph, head, new_id, [c["edge_id"] for c in cites]) \
            if new_id != head else 0
        out = {"resource_id": new_id, "revision_of": head if new_id != head else None,
               "created": new_id != head, "moved": moved}
    out["chosen"] = res_id
    return out


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


def object_status(graph, res_id: str, digest: str = "", *,
                  removed: Iterable[str] = ()) -> str:
    """Lo stato di un oggetto in scena legato a `res_id`, con i byte `digest`:

    * ``withdrawn`` — la risorsa non è più nel grafo e la stanza (o questo
      Blender) l'ha tolta (`removed`: gli id dei tombstone);
    * ``superseded`` — una revisione più nuova porta ALTRI byte;
    * ``""`` — corrente (anche se legato a una revisione vecchia con gli
      stessi byte della corrente: è la stessa geometria).

    Un oggetto segnato si toglie dalla scena con un gesto, mai da solo."""
    if not res_id:
        return STATUS_CURRENT
    if graph.find_node_by_id(res_id) is None:
        return STATUS_WITHDRAWN if res_id in set(removed) else STATUS_CURRENT
    head = head_of(graph, res_id)
    if head == res_id:
        return STATUS_CURRENT
    mine = bare_digest(digest) or digest_of(graph, res_id)
    return STATUS_CURRENT if mine and mine == digest_of(graph, head) else STATUS_SUPERSEDED
