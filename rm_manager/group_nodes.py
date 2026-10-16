"""The RM container's other half: its node of group in the graph (EM16-RMNG).

An RM container groups several models under one Document — «Survey 2015» under
D.01, «Reconstruction» under D.09. Until 2026-09-10 it lived ONLY as the
``scene.rm_containers`` PropertyGroup: whoever opened the GraphML outside
Blender saw no grouping at all. This module is the container's projection into
the graph, so the set can be named and read from outside.

WHAT IS AUTHORITATIVE, AND WHAT IS A PROJECTION
-----------------------------------------------
``mesh_names`` on the PropertyGroup stays authoritative on the Blender side;
the group node and its membership edges are the PROJECTION. That is why
:func:`reconcile_container` takes the mesh list as the input and the graph as
the output, and never the other way round.

THE RULE THAT GOVERNS EVERYTHING: IT SITS BESIDE, IT DOES NOT REPLACE
--------------------------------------------------------------------
Nothing here touches the epoch↔model edges, and nothing here touches the
Document→model DIRECT edges. Every function is additive on top of what
``containers.py`` already writes. The clearest way to say it is the shape of
the API: there is no function in this file that removes an edge whose type is
``has_representation_model`` between a Document and a MODEL — only between a
Document and a GROUP.

WHY IT DOES NOT IMPORT bpy
--------------------------
So it can be measured outside Blender, which is the reason
``rm_manager/epoch_edges.py`` gives for the same choice. The operators keep
the scene; this file keeps the graph.
"""

# The membership edge, on the `is_in_*` convention the other node groups use
# (is_in_activity / is_in_location / is_in_timebranch /
# is_in_paradata_nodegroup / is_in_functional_unit). Registered in
# s3Dgraphy's connections datamodel 1.6.14 — without that registration
# `Graph.add_edge` SILENTLY downgrades the edge to `generic_connection`.
MEMBERSHIP_EDGE = "is_in_representation_model_group"

# The documentary edge, reused and not invented: the same type that already
# carries Document→model, with its target widened to accept the group.
DOC_EDGE = "has_representation_model"

GROUP_NODE_TYPE = "RepresentationModelNodeGroup"


def group_node_id_for(container_label: str, doc_node_id: str = "") -> str:
    """A stable id for the container's group node.

    Stable is the whole requirement: the id must survive a save/reload and a
    rename of the label, otherwise every sync would orphan the previous node
    and the graph would accumulate boxes. So it is derived from the DOCUMENT
    when there is one — a container's identity really is «the set D.01
    publishes» — and from the label only for an unattached container, which has
    nothing else to be identified by.

    An unattached container therefore CHANGES id when renamed, and that is
    handled explicitly by :func:`rename_group`, not left to chance.
    """
    if doc_node_id:
        return f"{doc_node_id}_rmgroup"
    slug = "".join(ch if ch.isalnum() or ch in "-_" else "_"
                   for ch in (container_label or "unnamed"))
    return f"rmgroup_{slug}"


def find_group(graph, group_node_id):
    """The group node, or None. Never raises on a missing id."""
    if not graph or not group_node_id:
        return None
    node = graph.find_node_by_id(group_node_id)
    if node is None:
        return None
    if getattr(node, "node_type", None) != GROUP_NODE_TYPE:
        return None
    return node


def ensure_group(graph, group_node_id, label, description=""):
    """The container's group node, created if it is not there yet.

    Returns ``(node, created)``. Idempotent: called twice, the second call
    creates nothing and reports ``created=False``.
    """
    if graph is None or not group_node_id:
        return None, False
    existing = find_group(graph, group_node_id)
    if existing is not None:
        if label and existing.name != label:
            existing.name = label
        return existing, False
    try:
        from s3dgraphy.nodes.group_node import RepresentationModelNodeGroup
    except Exception:                                    # pragma: no cover
        # An older s3Dgraphy without the class. The container keeps working on
        # the Blender side — the projection is simply not written, which is the
        # behaviour of every version before 2026-09-10.
        return None, False
    node = RepresentationModelNodeGroup(
        node_id=group_node_id, name=label or group_node_id,
        description=description)
    graph.add_node(node)
    return node, True


def rename_group(graph, group_node_id, new_label):
    """Rename the group node. Returns True when something changed.

    Only the NAME changes; the id does not, so no edge is invalidated. For an
    unattached container whose id is derived from the label, the caller keeps
    using the id it already has — :func:`ensure_group` is what would mint a new
    one, and a rename deliberately does not.
    """
    node = find_group(graph, group_node_id)
    if node is None or not new_label or node.name == new_label:
        return False
    node.name = new_label
    return True


def members_of(graph, group_node_id):
    """The model node ids tagged into this group, in graph order."""
    out = []
    if graph is None or not group_node_id:
        return out
    for edge in list(graph.edges):
        if edge.edge_type == MEMBERSHIP_EDGE and edge.edge_target == group_node_id:
            if edge.edge_source not in out:
                out.append(edge.edge_source)
    return out


def group_of_member(graph, model_node_id):
    """The group a model belongs to, or None. Singular: one mesh, one
    container — the rule already in force on the PropertyGroup side."""
    if graph is None or not model_node_id:
        return None
    for edge in list(graph.edges):
        if edge.edge_type == MEMBERSHIP_EDGE and edge.edge_source == model_node_id:
            return edge.edge_target
    return None


def _membership_edge_id(model_node_id, group_node_id):
    return f"{model_node_id}_{MEMBERSHIP_EDGE}_{group_node_id}"


def add_member(graph, group_node_id, model_node_id):
    """Tag a model into the group. Returns True when an edge was added.

    Enforces the 1:1 rule by REFUSING rather than by moving: a model already
    in another group is left where it is and False is returned. Silently
    re-homing it would make the graph disagree with ``mesh_names``, which is
    authoritative — and ``add_mesh_to_container`` already refuses the same case
    on the Blender side with a reason the user reads.
    """
    if graph is None or not group_node_id or not model_node_id:
        return False
    if find_group(graph, group_node_id) is None:
        return False
    # IL MODELLO DEVE ESISTERE NEL GRAFO. Misurato il 10-09-2026 sul file di
    # lavoro di E.D. (GreatTemple_2026_v3_multigraph.blend): 98 mesh su 99
    # portano un `em_rm_node_id`, e NESSUNO di quegli id risolve in nessuno dei
    # due grafi caricati — i nodi RM non ci sono. Senza questo controllo si
    # scriverebbe un arco di appartenenza verso un nodo che non esiste, cioè si
    # trasformerebbe una divergenza da segnalare in un grafo rotto.
    if graph.find_node_by_id(model_node_id) is None:
        return False
    current = group_of_member(graph, model_node_id)
    if current == group_node_id:
        return False                       # already there: nothing to do
    if current is not None:
        return False                       # in another group: refuse, do not move
    try:
        graph.add_edge(
            edge_id=_membership_edge_id(model_node_id, group_node_id),
            edge_source=model_node_id,
            edge_target=group_node_id,
            edge_type=MEMBERSHIP_EDGE,
        )
    except Exception:
        return False
    return True


def remove_member(graph, group_node_id, model_node_id):
    """Untag a model from the group. Returns True when an edge was removed.

    Removes the MEMBERSHIP edge and nothing else: the model keeps its epoch
    edges and the Document keeps its direct edge to it. That is the whole
    point of the additive rule, and it is why this function does not take a
    `drop_edge` flag the way `remove_mesh_from_container` does.
    """
    if graph is None:
        return False
    removed = False
    for edge in list(graph.edges):
        if (edge.edge_type == MEMBERSHIP_EDGE
                and edge.edge_source == model_node_id
                and edge.edge_target == group_node_id):
            try:
                graph.remove_edge(edge.edge_id)
                removed = True
            except Exception:
                pass
    return removed


def attach_document(graph, group_node_id, doc_node_id):
    """``Document --has_representation_model--> group``, beside the direct
    edges to each model. Returns True when an edge was added."""
    if graph is None or not group_node_id or not doc_node_id:
        return False
    if find_group(graph, group_node_id) is None:
        return False
    for edge in list(graph.edges):
        if (edge.edge_type == DOC_EDGE and edge.edge_source == doc_node_id
                and edge.edge_target == group_node_id):
            return False
    try:
        graph.add_edge(
            edge_id=f"{doc_node_id}_{DOC_EDGE}_{group_node_id}",
            edge_source=doc_node_id,
            edge_target=group_node_id,
            edge_type=DOC_EDGE,
        )
    except Exception:
        return False
    return True


def remove_group(graph, group_node_id):
    """Remove the group node and the edges that exist ONLY because of it.

    What goes: the group node, its membership edges, and the Document→GROUP
    edge. What stays, and this is the requirement stated in the prompt:

      · the DocumentNode itself;
      · the Document→MODEL direct edges;
      · every epoch↔model edge of every member.

    Returns the number of edges removed (the node is not counted).
    """
    if graph is None or not group_node_id:
        return 0
    n = 0
    for edge in list(graph.edges):
        tocca_il_gruppo = (edge.edge_source == group_node_id
                           or edge.edge_target == group_node_id)
        if not tocca_il_gruppo:
            continue
        # Only the two types this module writes. An edge of any other type
        # pointing at the group is somebody else's and is left alone — being
        # conservative here is what keeps «nothing is removed» true even in a
        # graph this module did not build.
        if edge.edge_type not in (MEMBERSHIP_EDGE, DOC_EDGE):
            continue
        try:
            graph.remove_edge(edge.edge_id)
            n += 1
        except Exception:
            pass
    node = find_group(graph, group_node_id)
    if node is not None:
        try:
            graph.remove_node(group_node_id)
        except Exception:
            try:
                graph.nodes.remove(node)
            except Exception:
                pass
    return n


def reconcile_container(graph, group_node_id, label, model_node_ids,
                        doc_node_id="", description=""):
    """Make the graph agree with the container. Returns a report dict.

    Direction of travel is one-way and deliberate: ``model_node_ids`` (derived
    from ``mesh_names``, which is authoritative) is the INPUT, the graph is the
    OUTPUT. The graph is never read back as truth.

    The report is what the caller turns into warnings — nothing is deleted in
    silence:

        created        the group node did not exist and was made
        added          member ids tagged in
        removed        member ids untagged (they are no longer in mesh_names)
        refused        member ids that belong to ANOTHER group, left alone
        unknown        member ids the graph does not have — a divergence
                       between scene and graph, reported and not written
        doc_attached   the Document→group edge was added

    ``refused`` is the divergence that matters: it means the graph says a model
    is in another container while this container claims it. It is reported, not
    resolved, because resolving it would mean choosing which of two user
    intentions to discard.
    """
    report = {"created": False, "added": [], "removed": [], "refused": [],
              "unknown": [], "doc_attached": False}
    if graph is None or not group_node_id:
        return report
    _node, created = ensure_group(graph, group_node_id, label, description)
    report["created"] = created
    if _node is None:
        return report

    tutti = [m for m in model_node_ids if m]
    # Gli id che il grafo non conosce si SEGNALANO e non si toccano — vedi il
    # commento in `add_member`. Sono una divergenza fra la scena e il grafo,
    # non un'appartenenza da scrivere, e l'unico modo di non perderla è dirla.
    voluti = [m for m in tutti if graph.find_node_by_id(m) is not None]
    report["unknown"] = [m for m in tutti if m not in voluti]
    presenti = members_of(graph, group_node_id)

    for m in voluti:
        if m in presenti:
            continue
        altrove = group_of_member(graph, m)
        if altrove is not None and altrove != group_node_id:
            report["refused"].append(m)
            continue
        if add_member(graph, group_node_id, m):
            report["added"].append(m)

    for m in presenti:
        if m not in voluti:
            if remove_member(graph, group_node_id, m):
                report["removed"].append(m)

    if doc_node_id and attach_document(graph, group_node_id, doc_node_id):
        report["doc_attached"] = True
    return report


def common_group_of(graph, model_node_ids):
    """The group ALL these models share, or None.

    This is the graph half of the gesture the 10-09-2026 meeting asked for — «I
    select the objects, I go to graph, I am on the node». Plural on purpose: a
    SET of models resolves to the container that publishes it, while a single
    model keeps resolving to itself, so nothing that works today changes.

    Returns None when the list is shorter than two, when any member has no
    group, or when they do not all agree. Disagreement is not a tie to be
    broken: two containers selected at once have no single answer, and
    inventing one would take the user somewhere they did not point at.
    """
    ids = [m for m in (model_node_ids or []) if m]
    if graph is None or len(ids) < 2:
        return None
    gruppi = {group_of_member(graph, m) for m in ids}
    if len(gruppi) != 1:
        return None
    solo = gruppi.pop()
    if solo is None:
        return None
    return solo if find_group(graph, solo) is not None else None


# ══════════════════════════════════════════════════════════════════════════════
# LA FRASE SU UN GRAFO CHE NON PORTA NODI RM — UNA, IN UN POSTO SOLO
#
# EM16-UX punto E l'ha introdotta nell'operatore `rmcontainer.project`;
# EM16-UX2 punto C2 la vuole anche nel tooltip della cella `Models` quando
# quella cella è a zero. Due posti, UNA stringa: scriverne una seconda vorrebbe
# dire che il giorno che la prima cambia l'altra mente.
#
# Il fatto che racconta è di disegno e non un guasto: un grafo che viene da
# import GraphML non porta i nodi RM, perché
# `graphml_patcher.INTERNAL_NODE_TYPES` li esclude — i representation model non
# sono lingua formale EM in GraphML.

def no_rm_nodes_yet(mesh=0, container=0) -> str:
    """Cosa manca e il comando da dare prima.

    Con `mesh`/`container` a zero (il caso del tooltip, che non ha un rapporto
    di riconciliazione sotto mano) la frase resta vera e omette i conteggi
    invece di stamparne di finti.
    """
    quanti = ""
    if mesh:
        quanti = (f"{mesh} mesh(es)"
                  + (f" in {container} container(s)" if container else "")
                  + " point at RM ids this graph does not contain. ")
    return (
        quanti
        + "A graph imported from GraphML never carries RM nodes — "
          "representation models are excluded from GraphML by design. "
          "Promote the meshes first (RM Manager \u2192 Promote to RM), then "
          "press Project again."
    )


# ══════════════════════════════════════════════════════════════════════════════
# PRIMA DI OGNI SALVATAGGIO, E ALL'APERTURA (MICRO-EMTOOLS-CONTENITORI, 16-10)
#
# Misurato sui quattro em.json del Templu Mare: 99 representation_model, gli
# archi diretti D.09→87 e D.01→12, e nessun gruppo. La proiezione esisteva
# soltanto dietro i bottoni Sync e Project; il salvataggio dell'em.json non la
# chiamava, e un container mai proiettato (`group_node_id` vuoto) restava fuori
# dal file. Ora ogni salvataggio proietta TUTTI i container, e l'apertura
# confronta senza correggere.
#
# Un container qui è un oggetto qualsiasi con `label`, `doc_node_id`,
# `group_node_id` e `model_node_ids` — la PropertyGroup vista dal lato Blender,
# o un SimpleNamespace in una prova. Il modulo resta senza `bpy`.

def concerns(graph, doc_node_id, model_node_ids):
    """Has this graph anything of the container — its Document or one model?

    A scene holds several graphs and the containers are the scene's, not one
    graph's: a container is projected into the graph that carries its things,
    and an unrelated graph (the shelf, another study) gets no empty group."""
    if graph is None:
        return False
    if doc_node_id and graph.find_node_by_id(doc_node_id) is not None:
        return True
    return any(m and graph.find_node_by_id(m) is not None
               for m in (model_node_ids or []))


def project_all(graph, containers):
    """Reconcile EVERY container that concerns this graph, creating the groups
    that are missing. Returns ``[(container, group_node_id, report)]``.

    The caller writes ``group_node_id`` back on its container: the id is stable
    (:func:`group_node_id_for`), so writing it is idempotent."""
    out = []
    if graph is None:
        return out
    for c in containers:
        models = [m for m in (getattr(c, "model_node_ids", None) or []) if m]
        doc = getattr(c, "doc_node_id", "") or ""
        if not concerns(graph, doc, models):
            continue
        label = getattr(c, "label", "") or ""
        gid = (getattr(c, "group_node_id", "") or ""
               or group_node_id_for(label, doc))
        report = reconcile_container(graph, gid, label=label or gid,
                                     model_node_ids=models, doc_node_id=doc)
        out.append((c, gid, report))
    return out


def groups_in(graph):
    """The RM groups this graph carries: ``[{id, label, doc_node_id, members}]``.

    ``doc_node_id`` is the source of the ``has_representation_model`` edge that
    points at the group (empty for an unattached container)."""
    out = []
    if graph is None:
        return out
    for node in list(graph.nodes):
        if getattr(node, "node_type", None) != GROUP_NODE_TYPE:
            continue
        gid = node.node_id
        doc = ""
        for edge in list(graph.edges):
            if edge.edge_type == DOC_EDGE and edge.edge_target == gid:
                doc = edge.edge_source
                break
        out.append({"id": gid, "label": getattr(node, "name", "") or gid,
                    "doc_node_id": doc, "members": members_of(graph, gid)})
    return out


def compare_with_graph(graph, containers):
    """What the opened graph says against what the scene's containers say.

    Returns one sentence per difference, and touches NOTHING — neither the graph
    nor the containers. On open a difference is a line in the Log, not a silent
    correction: which side is right is the user's call, and the next save
    (where ``mesh_names`` is authoritative) is where it gets decided."""
    righe = []
    if graph is None:
        return righe
    gruppi = {g["id"]: g for g in groups_in(graph)}
    visti = set()
    for c in containers:
        label = getattr(c, "label", "") or "<unnamed>"
        models = [m for m in (getattr(c, "model_node_ids", None) or []) if m]
        doc = getattr(c, "doc_node_id", "") or ""
        gid = (getattr(c, "group_node_id", "") or ""
               or group_node_id_for(label, doc))
        g = gruppi.get(gid)
        if g is None:
            if concerns(graph, doc, models):
                righe.append(f"container {label!r}: the graph has no group "
                             f"{gid} — the next save writes it")
            continue
        visti.add(gid)
        if g["label"] != (getattr(c, "label", "") or gid):
            righe.append(f"container {label!r}: the graph names its group "
                         f"{g['label']!r}")
        if doc and g["doc_node_id"] and g["doc_node_id"] != doc:
            righe.append(f"container {label!r}: the graph attaches its group "
                         f"to {g['doc_node_id']}, the container to {doc}")
        solo_grafo = [m for m in g["members"] if m not in models]
        solo_scena = [m for m in models if m not in g["members"]
                      and graph.find_node_by_id(m) is not None]
        if solo_grafo:
            righe.append(f"container {label!r}: {len(solo_grafo)} model(s) in "
                         f"the graph's group and not in the container "
                         f"({', '.join(solo_grafo[:3])}"
                         f"{', …' if len(solo_grafo) > 3 else ''})")
        if solo_scena:
            righe.append(f"container {label!r}: {len(solo_scena)} model(s) in "
                         f"the container and not in the graph's group "
                         f"({', '.join(solo_scena[:3])}"
                         f"{', …' if len(solo_scena) > 3 else ''})")
    for gid, g in gruppi.items():
        if gid not in visti:
            righe.append(f"group {g['label']!r} ({gid}, {len(g['members'])} "
                         f"model(s)) is in the graph and in no container of "
                         f"this scene")
    return righe
