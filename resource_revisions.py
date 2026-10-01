"""Sostituire, non sovrascrivere — la revisione di una risorsa in EMtools.

E.D., 30 set 2026: quando i byte di una risorsa cambiano (una texture
riesportata, un glb rifatto) non si riscrive la risorsa che c'era: se ne fa
una REVISIONE (`api.replace_file`, ``new ──was_revision_of──▶ old``). La
vecchia resta com'era, citabile coi suoi byte; chi la citava non si sposta da
solo. Si chiede quali citazioni spostare, con «tutti» come proposta — come
EMStudio (`replaceFileFlow` in `frontend/src/main.ts`).

**La catena DTC resta sui byte vecchi.** Misurato da EMStudio: «tutti»
sposterebbe anche il `dtc_had_output` del processo che ha prodotto la risorsa
vecchia, e direbbe che quell'export ha fatto i byte nuovi. Gli archi della
catena (``"dtc_role": "chain"`` nel datamodel delle connessioni) sono
affermazioni sui byte vecchi, e non sono citazioni: non si propongono.

Questo modulo non importa `bpy`: decide cosa spostare, e il pannello lo chiede.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

EDGE_REVISION_OF = "was_revision_of"


def chain_edge_types() -> frozenset:
    """Gli archi della catena DTC, letti dal datamodel (non elencati qui)."""
    try:
        from s3dgraphy.dtc.neighbourhood import CHAIN_EDGES
        return frozenset(CHAIN_EDGES)
    except Exception:                              # noqa: BLE001
        return frozenset({"dtc_had_input", "dtc_had_output", "dtc_derived_from"})


def split_pointers(pointing: Iterable[Dict[str, Any]]):
    """`pointing_at_old` di `replace_file` diviso in (citazioni, catena)."""
    chain = chain_edge_types()
    citing, staying = [], []
    for ptr in pointing or []:
        (staying if ptr.get("edge_type") in chain else citing).append(dict(ptr))
    return citing, staying


def pointing_at(graph, res_id: str) -> List[Dict[str, Any]]:
    """Gli archi che ENTRANO in `res_id`, tranne le sue revisioni — la stessa
    lista che `replace_file` restituisce, rifatta quando serve dopo."""
    return [{"edge_id": e.edge_id, "edge_type": e.edge_type, "source": e.edge_source}
            for e in graph.edges
            if e.edge_target == res_id and e.edge_type != EDGE_REVISION_OF]


def pending_revisions(graph) -> List[Dict[str, Any]]:
    """Le risorse che hanno una revisione più nuova e sono ancora CITATE.

    → ``[{old_id, new_id, old_name, new_name, citing, staying}]``: ``new_id``
    è la revisione corrente della catena, ``citing`` le citazioni che si
    possono spostare. Una risorsa vecchia senza citazioni non è in attesa di
    niente: è una revisione passata, e resta citabile così com'è.
    """
    from s3dgraphy import api
    out, seen = [], set()
    olds = sorted({e.edge_target for e in graph.edges if e.edge_type == EDGE_REVISION_OF})
    for old_id in olds:
        if old_id in seen or graph.find_node_by_id(old_id) is None:
            continue
        seen.add(old_id)
        try:
            new_id = api.current_revision(graph, old_id)
        except ValueError:
            continue            # una catena che si biforca: la decide chi l'ha fatta
        if new_id == old_id:
            continue
        citing, staying = split_pointers(pointing_at(graph, old_id))
        if not citing:
            continue
        old, new = graph.find_node_by_id(old_id), graph.find_node_by_id(new_id)
        out.append({"old_id": old_id, "new_id": new_id,
                    "old_name": getattr(old, "name", old_id),
                    "new_name": getattr(new, "name", new_id),
                    "citing": citing, "staying": staying})
    return out


def move_citations(graph, old_id: str, new_id: str, edge_ids: Iterable[str]) -> int:
    """Sposta le citazioni scelte da `old_id` a `new_id`. → quante.

    Come `movePointers` di EMStudio: l'arco si toglie e si rifà verso la
    revisione, con l'id in cui il vecchio id è sostituito dal nuovo (o lo
    stesso, se l'id non lo nomina). Un arco della catena DTC non si sposta
    mai, anche se qualcuno lo chiede: è un fatto sui byte vecchi.
    """
    chain = chain_edge_types()
    want = set(edge_ids or ())
    moved = 0
    for e in [e for e in graph.edges if e.edge_id in want and e.edge_target == old_id]:
        if e.edge_type in chain:
            continue
        attrs = dict(getattr(e, "attributes", None) or {})
        graph.remove_edge(e.edge_id)
        nid = str(e.edge_id).replace(old_id, new_id)
        if graph.find_edge_by_id(nid) is None:
            edge = graph.add_edge(nid, e.edge_source, new_id, e.edge_type)
            if attrs and edge is not None:
                edge.attributes.update(attrs)
        moved += 1
    return moved


def revise_files(graph, res_id: str, new_files: List[Dict[str, Any]], *,
                 force: bool = False) -> Dict[str, Any]:
    """I file di `res_id` sono diventati `new_files`: una revisione.

    ``new_files`` sono le specifiche di `api.add_resource`
    (``{path, url, checksum, size_bytes, role}``). Il primo file cambiato passa
    per `api.replace_file` (la revisione nasce lì, con l'id derivato e il
    `dtc_derived_from` del file nuovo verso il vecchio); gli altri cambiamenti
    si fanno sulla revisione appena nata — nessuno la cita ancora — con
    `add_file` / `remove_file`, e un file sostituito dichiara il suo padre
    come fa `replace_file`. Un file solo implicito si sostituisce col suo
    `None`.

    ``force``: il chiamante sa che il CONTENUTO è cambiato anche se i file
    elencati no — una `directory` si descrive con la sua porta (`tileset.json`)
    e il suo digest è quello dell'albero: cambia una tile, la porta resta
    uguale. Allora la revisione si fa rimettendo la porta com'è.

    → ``{new_resource_id, pointing_at_old, changed, added, removed}``; un
    `new_resource_id` None vuol dire che i file erano già quelli.
    """
    from s3dgraphy import api
    current = api.resource_files(graph, res_id)
    implicit = bool(current) and current[0]["implicit"]
    old_by_path = {f["path"]: f for f in current}
    new_by_path = {f["path"]: f for f in new_files}
    if implicit and len(new_files) == 1:
        #: un file solo: il «percorso» della forma implicita è il nome del
        #: locator, e conta solo il contenuto
        old = current[0]
        spec = new_files[0]
        if (old["node"].data.get("checksum") or "") == spec["checksum"] and not force:
            return {"new_resource_id": None, "pointing_at_old": [],
                    "changed": [], "added": [], "removed": []}
        out = api.replace_file(graph, res_id, None, checksum=spec["checksum"],
                               path=spec.get("path"), url=spec.get("url"),
                               size_bytes=spec.get("size_bytes"))
        return {"new_resource_id": out["new_resource_id"],
                "pointing_at_old": out["pointing_at_old"],
                "changed": [spec["path"]], "added": [], "removed": []}

    def checksum_of(f):
        return (f["node"].data or {}).get("checksum") if f.get("node") is not None else None

    changed = [p for p in new_by_path if p in old_by_path
               and checksum_of(old_by_path[p]) != new_by_path[p]["checksum"]]
    added = [p for p in new_by_path if p not in old_by_path]
    removed = [p for p in old_by_path if p not in new_by_path]
    if not (changed or added or removed or force):
        return {"new_resource_id": None, "pointing_at_old": [],
                "changed": [], "added": [], "removed": []}

    # la revisione nasce dal primo file cambiato (o, se cambia solo la
    # composizione, dalla porta rimessa uguale: la revisione dice comunque
    # «questa è un'altra versione», e la porta è il file che la apre)
    first = changed[0] if changed else next(
        (p for p, f in old_by_path.items() if f["role"] == "entry_point"),
        next(iter(old_by_path)))
    first_old = old_by_path[first]
    first_new = new_by_path.get(first) or {
        "checksum": checksum_of(first_old), "path": first}
    out = api.replace_file(
        graph, res_id, None if first_old["implicit"] else first_old["node"].node_id,
        checksum=first_new["checksum"], path=first,
        url=first_new.get("url") or getattr(first_old["node"], "url", None),
        size_bytes=first_new.get("size_bytes"))
    new_id = out["new_resource_id"]
    # gli altri cambiamenti, sulla revisione appena nata
    revised = {f["path"]: f for f in api.resource_files(graph, new_id)}
    for p in changed[1:]:
        old_file = revised[p]["node"].node_id
        api.remove_file(graph, new_id, old_file)
        spec = dict(new_by_path[p])
        added_file = api.add_file(graph, new_id, **spec)
        if added_file.get("file_id") and added_file["file_id"] != old_file:
            edge_id = f"{added_file['file_id']}~>{old_file}"
            if graph.find_edge_by_id(edge_id) is None:
                graph.add_edge(edge_id, added_file["file_id"], old_file, "dtc_derived_from")
    for p in removed:
        if p in revised:
            api.remove_file(graph, new_id, revised[p]["node"].node_id)
    for p in added:
        api.add_file(graph, new_id, **dict(new_by_path[p]))
    return {"new_resource_id": new_id, "pointing_at_old": out["pointing_at_old"],
            "changed": changed, "added": added, "removed": removed}
