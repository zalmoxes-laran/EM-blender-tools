"""Il proxy di una US come PROPRIETÀ, e il suo glb come RISORSA.

Decisione di E.D. (30 set 2026), scritta in s3Dgraphy (connections 1.6.28)::

    US ─has_property→ Property(geometry) ─has_semantic_shape→ SemanticShape
                                                   └─has_linked_resource→ ResourceNode(url, url_type proxy_model)

Fino a oggi EMtools scriveva la forma di prima (``US ─has_semantic_shape→
'<US>_shape'(url proxies/<US>.glb)``) e la riscriveva a ogni aggiornamento, così
la migrazione di s3Dgraphy in lettura veniva disfatta dal primo click. Qui si
scrive solo con l'API di s3Dgraphy (`create_geometry_proxy`,
`link_proxy_resource`), e la forma vecchia che si trova nel grafo in memoria
viene prima portata avanti con le stesse migrazioni che s3Dgraphy applica
all'apertura di un em.json.

**L'abbinamento con Blender resta per nome** (nome esatto, o suffisso
``.<US>``): lo fa chi chiama. Questo modulo non importa `bpy`, così la catena si
misura con pytest.

**L'identità del proxy è l'unità, non il percorso.** `create_geometry_proxy`
conia la forma da ``uuid5(url)``; un proxy migrato da un file vecchio tiene
invece il suo id ``'<US>_shape'``. Cercare per catena (unità → proprietà →
forma → risorsa) fa convergere i due: un secondo aggiornamento, o il primo dopo
aver aperto un em.json vecchio, trova il proxy che c'è e non ne conia un altro.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

#: la cartella dei glb dei proxy, relativa al progetto esportato
PROXY_DIR = "proxies"

_HAS_PROPERTY = "has_property"
_HAS_SEMANTIC_SHAPE = "has_semantic_shape"
_HAS_LINKED_RESOURCE = "has_linked_resource"


def proxy_url(unit_name: str) -> str:
    """Il percorso del glb di un proxy: ``proxies/<US>.glb`` (nome dell'unità,
    senza il prefisso di grafo che l'oggetto Blender può avere)."""
    return f"{PROXY_DIR}/{unit_name}.glb"


def migrate_old_proxies(graph) -> Dict[str, Any]:
    """La forma vecchia che è nel grafo IN MEMORIA → la catena nuova.

    Un em.json vecchio viene migrato da s3Dgraphy quando si apre; un grafo
    costruito in questa sessione dal codice di prima (o da un GraphML) no.
    Stesse funzioni, stesso ordine dell'importer: prima la forma diventa
    proprietà, poi il suo ``url`` diventa risorsa ``proxy_model``. Idempotente.
    """
    from s3dgraphy.geometry.migrate import (migrate_legacy_proxies,
                                            migrate_shape_urls)
    legacy = migrate_legacy_proxies(graph)
    urls = migrate_shape_urls(graph)
    return {"properties": legacy.get("migrated", 0),
            "resources": len(urls.get("migrated", [])),
            "warnings": list(legacy.get("warnings", [])) + list(urls.get("warnings", []))}


def _targets(graph, source_id: str, edge_type: str) -> List[Any]:
    out = []
    for edge in graph.edges:
        if edge.edge_source == source_id and edge.edge_type == edge_type:
            node = graph.find_node_by_id(edge.edge_target)
            if node is not None:
                out.append(node)
    return out


def geometry_shapes(graph, unit_id: str) -> List[Any]:
    """Le SemanticShape che fanno da proxy all'unità, lungo la catena nuova."""
    shapes = []
    for prop in _targets(graph, unit_id, _HAS_PROPERTY):
        if getattr(prop, "node_type", None) != "property":
            continue
        if getattr(prop, "property_type", None) != "geometry":
            continue
        for shape in _targets(graph, prop.node_id, _HAS_SEMANTIC_SHAPE):
            if getattr(shape, "node_type", None) == "semantic_shape":
                shapes.append(shape)
    return shapes


def glb_proxy(graph, unit_id: str) -> Tuple[Optional[Any], Optional[Any]]:
    """``(shape, resource)`` del proxy-glb dell'unità, o ``(None, None)``.

    Un proxy-glb è una forma della catena che raggiunge una risorsa
    ``proxy_model``. I convessi di `sync_manager.commands` (bbox, senza risorsa)
    sono un altro proxy della stessa unità e non si toccano.
    """
    from s3dgraphy.geometry.proxy import linked_proxy_resources
    shapes = geometry_shapes(graph, unit_id)
    for shape in shapes:
        linked = linked_proxy_resources(graph, shape.node_id)
        if linked:
            return shape, linked[0]
    # Misurato (s3Dgraphy 0573ea4): la migrazione lascia com'è una risorsa
    # già tipizzata «3D» (`3d_model`, `point_cloud`) e le toglie l'url della
    # forma, ma `linked_proxy_resources` riconosce solo `proxy_model`. Senza
    # questo ripiego l'aggiornamento non la vedrebbe e conierebbe un secondo
    # proxy accanto al primo. Si riconosce, non si ritipizza: il tipo lo ha
    # scritto qualcuno.
    for shape in shapes:
        for res in _targets(graph, shape.node_id, _HAS_LINKED_RESOURCE):
            data = getattr(res, "data", None) or {}
            if getattr(res, "node_type", None) == "resource" and \
                    str(data.get("url") or "").startswith(f"{PROXY_DIR}/"):
                return shape, res
    return None, None


def ensure_unit_proxy(graph, unit_id: str, unit_name: str, *,
                      author: Optional[str] = None) -> Dict[str, Any]:
    """Il proxy-glb dell'unità: c'è → lo si riusa, non c'è → lo si crea.

    Non riscrive il percorso di un proxy che c'è già: il nome del file lo
    decide l'export Heriverse (che lo pulisce con `clean_filename`) e lo scrive
    nella risorsa; rimetterlo qui a ogni aggiornamento farebbe oscillare il
    grafo fra due valori.

    Returns ``{shape_id, property_id, resource_id, created, warnings}``.
    """
    shape, resource = glb_proxy(graph, unit_id)
    if shape is not None:
        prop_ids = [e.edge_source for e in graph.edges
                    if e.edge_target == shape.node_id
                    and e.edge_type == _HAS_SEMANTIC_SHAPE]
        return {"shape_id": shape.node_id,
                "property_id": prop_ids[0] if prop_ids else None,
                "resource_id": resource.node_id, "created": False,
                "warnings": []}

    from s3dgraphy.api import create_geometry_proxy
    result = create_geometry_proxy(graph, unit_id, {"url": proxy_url(unit_name)},
                                   author=author)
    shape = graph.find_node_by_id(result.shape_id)
    if shape is not None and result.created:
        # il nome è un'etichetta; quello di prima («Shape for US») si legge
        # meglio di «<uuid> geometry», che è il default di s3Dgraphy
        shape.name = f"Shape for {unit_name}"
    return {"shape_id": result.shape_id, "property_id": result.property_id,
            "resource_id": result.resource_id, "created": result.created,
            "warnings": list(result.warnings)}


def proxy_resource_for_export(graph, unit_ids: Iterable[str], url: str
                              ) -> Tuple[Optional[str], Optional[str], bool]:
    """La risorsa ``proxy_model`` che l'export Heriverse aggiorna.

    Cerca il proxy-glb fra le unità date (quelle che portano il nome
    esportato) e ne scrive il percorso nella RISORSA — non più nell'``url``
    della forma. Returns ``(shape_id, resource_id, changed)``; ``(None, None,
    False)`` se nessuna unità ha un proxy-glb.
    """
    for unit_id in unit_ids:
        shape, resource = glb_proxy(graph, unit_id)
        if shape is None:
            continue
        data = resource.data if isinstance(getattr(resource, "data", None), dict) else {}
        changed = str(data.get("url") or "") != url
        if changed:
            data["url"] = url
            resource.data = data
            if hasattr(resource, "url"):
                resource.url = url
        return shape.node_id, resource.node_id, changed
    return None, None, False


def units_named(graph, name: str) -> List[str]:
    """Gli id delle unità stratigrafiche con quel nome (l'export ragiona per
    nome, il grafo per id)."""
    from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
    return [n.node_id for n in graph.nodes
            if isinstance(n, StratigraphicNode) and getattr(n, "name", None) == name]
