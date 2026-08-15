# export_operators/heriverse/dissemination.py
"""Chi finisce nella scena pubblicata, e chi no.

Heriverse è una superficie di **disseminazione**: una US cancellata deve
esserne **assente**, non marcata (la politica per-superficie sta in
``s3dgraphy.dissemination`` — KEEP em.json / RDF round-trip / snapshot di
stanza, HIDE GraphML / Heriverse / RDF pubblicato).

Il grafo pubblicato è già filtrato dentro la libreria (``JSONExporter``), ma
l'export Heriverse di Blender pubblica **due** cose: il grafo *e* i proxy
``.glb``, e i proxy li sceglie questo elenco di nomi. Senza il filtro qui la
scena conterrebbe il modello 3D di una US che il grafo non nomina più: un
oggetto orfano che nessuno può più spiegare, che è esattamente il modo in cui
una cancellazione riappare a valle.

Il modulo esiste separato dall'operatore per una ragione sola: l'operatore
importa ``bpy``, questo no, e una regola che non si può misurare headless non
è una regola. Il predicato non viene reinventato — è quello di s3Dgraphy.
"""


def is_removed(node) -> bool:
    """Il nodo è un tombstone? Predicato UNICO, quello della libreria.

    Se la libreria è più vecchia del modulo (wheel non risincronizzato) la
    risposta è ``False``: l'export continua senza filtro invece di fallire, e
    chi chiama lo dichiara con :func:`predicate_available`.
    """
    try:
        from s3dgraphy.dissemination import is_removed_node
    except ImportError:  # s3dgraphy privo del modulo (< 1.6.0.dev14)
        return False
    return is_removed_node(node)


def predicate_available() -> bool:
    """La libreria sa rispondere? Serve a dichiarare il limite, non a aggirarlo."""
    try:
        from s3dgraphy.dissemination import is_removed_node  # noqa: F401
    except ImportError:
        return False
    return True


def publishable_stratigraphic_names(graph, node_types):
    """I nomi delle US che possono uscire in una scena Heriverse.

    Ritorna ``(names, removed_count)``: l'elenco dei vivi e quanti morti sono
    stati lasciati fuori — un numero, perché "sono stati filtrati" non è
    un'affermazione che qualcuno possa controllare.
    """
    names = []
    removed = 0
    indices = graph.indices
    for node_type in node_types:
        for node in indices.nodes_by_type.get(node_type, []):
            if is_removed(node):
                removed += 1
                continue
            names.append(node.name)
    return names, removed
