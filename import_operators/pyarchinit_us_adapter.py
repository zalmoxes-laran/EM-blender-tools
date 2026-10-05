"""N1 · le geometrie di PyArchInit agganciate alle loro US, con l'etichetta che
resta com'è (E.D., 4 ottobre 2026, sera).

Il nome di un'US lo dà il mapping (`table_settings.node_name_template`, per
pyArchInit ``{area}.{settore}.{unita_tipo}{us}`` → ``1.US10``) e **non si
tocca**: dentro Blender due oggetti non possono chiamarsi entrambi «US10».
Il lettore delle geometrie di Enzo Cocca (`pyarchinit_geom_importer`) cerca
invece il numero nudo della riga (``us=10``), e con «Import from tables»
agganciava 1 poligono su 482.

Questo adattatore sta **fuori** dal modulo di Enzo, che non si modifica. Per
ogni riga di geometria (``sito, area, us``) trova la sua riga in ``us_table``,
che porta quello che la tabella delle geometrie non ha (settore, tipo,
UUID), e risolve l'US:

  1. per UUID, se la riga lo porta (``node_uuid``, la colonna che il mapping
     fa diventare ``node_id``);
  2. per l'etichetta ricomposta con la STESSA regola del mapping
     (`compose_label`, la stessa di ``PyArchInitImporter._resolve_node_name``);
  3. per il numero nudo, come faceva il lettore (un grafo i cui nomi sono i
     numeri continua ad agganciarsi).

Si innesta con `resolving_us_by_label`, che per la durata dell'import mette
il risolutore al posto di ``_resolve_us_node`` e di
``_record_us_without_geometry`` del modulo di Enzo e poi li rimette. Il testo
della issue per lui (un parametro ``resolve_us_node`` in
``import_geometries``, e la riga che porta l'UUID) è nel referto
`decisioni-della-sera`.
"""

from __future__ import annotations

import contextlib
import re
from typing import Any, Dict, Iterable, Optional, Tuple

#: il template del mapping pyArchInit di s3Dgraphy, quando il chiamante non
#: ne passa uno (stesso valore di `pyarchinit_us_mapping.json`)
DEFAULT_TEMPLATE = "{area}.{settore}.{unita_tipo}{us}"

#: le colonne che possono portare l'UUID stabile dell'unità, in ordine: la
#: canonica (`node_uuid`, UUID v7, `is_passthrough` nel mapping) e basta —
#: `entity_uuid` è la vecchia v4 e il mapping non la fa diventare `node_id`
UUID_COLUMNS = ("node_uuid",)


def compose_label(row: Dict[str, Any], template: Optional[str]) -> str:
    """L'etichetta di un'US come la compone il mapping.

    Copia fedele di ``PyArchInitImporter._resolve_node_name``: i segnaposto
    ``{colonna}`` presi dalla riga, i vuoti omessi, i punti doppi ridotti e
    quelli in testa e in coda tolti; tutto vuoto → il valore nudo di ``us``.
    """
    if not template:
        return _text(row.get("us"))

    def _resolve(match):
        return _text(row.get(match.group(1)))

    composed = re.sub(r"\{(\w+)\}", _resolve, template)
    composed = re.sub(r"\.{2,}", ".", composed).strip(".")
    return composed or _text(row.get("us"))


def parse_us_key(us_key: str) -> Dict[str, str]:
    """``sito=…,area=…,us=…`` (la chiave del lettore) → dict."""
    out: Dict[str, str] = {}
    for part in (us_key or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _key(sito: Any, area: Any, us: Any) -> Tuple[str, str, str]:
    return (_text(sito), _text(area), _text(us))


class USResolver:
    """Dalla chiave di una riga di geometria al nodo US del grafo."""

    def __init__(self, us_rows: Iterable[Dict[str, Any]],
                 template: Optional[str] = DEFAULT_TEMPLATE):
        self.template = template
        self._rows: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for row in us_rows:
            self._rows.setdefault(
                _key(row.get("sito"), row.get("area"), row.get("us")), row)
        #: come è stata risolta ciascuna chiave (per il conto e il referto)
        self.how: Dict[str, str] = {}

    # ── le chiavi ──────────────────────────────────────────────────────────
    def us_row(self, us_key: str) -> Optional[Dict[str, Any]]:
        k = parse_us_key(us_key)
        return self._rows.get(_key(k.get("sito"), k.get("area"), k.get("us")))

    def label_for(self, us_key: str) -> Optional[str]:
        row = self.us_row(us_key)
        return compose_label(row, self.template) if row is not None else None

    # ── il risolutore, con la firma di `_resolve_us_node` ─────────────────
    def resolve(self, graph: Any, us_key: str) -> Any:
        if graph is None:
            return None
        nodes = list(getattr(graph, "nodes", []) or [])
        row = self.us_row(us_key)
        if row is not None:
            for col in UUID_COLUMNS:
                uid = _text(row.get(col))
                if uid:
                    node = next((n for n in nodes
                                 if _text(getattr(n, "node_id", None)) == uid), None)
                    if node is not None:
                        self.how[us_key] = "uuid"
                        return node
            label = compose_label(row, self.template)
            node = _pick_stratigraphic(n for n in nodes
                                       if getattr(n, "name", None) == label)
            if node is not None:
                self.how[us_key] = "label"
                return node
        bare = parse_us_key(us_key).get("us")
        node = _pick_stratigraphic(n for n in nodes
                                   if bare and getattr(n, "name", None) == bare)
        self.how[us_key] = "bare" if node is not None else "orphan"
        return node


#: gli stessi tipi del lettore (`_STRATIGRAPHIC_NODE_TYPES`), ripetuti qui
#: perché il suo modulo importa `bpy` e questo si prova senza Blender
STRATIGRAPHIC_NODE_TYPES = frozenset({
    "US", "USN", "USV", "USVS", "USVA", "USM", "USR",
    "SF", "TSU", "VSF", "USD",
})


def _pick_stratigraphic(candidates) -> Any:
    candidates = list(candidates)
    for n in candidates:
        if getattr(n, "node_type", "") in STRATIGRAPHIC_NODE_TYPES:
            return n
    return candidates[0] if candidates else None


# ── la lettura di us_table, sola lettura, con le connessioni del lettore ──

def read_us_rows(db_spec: str, sito: Optional[str] = None) -> list:
    """Le righe di ``us_table`` (tutte le colonne), di un sito se dato."""
    from .pyarchinit_db_reader import (
        is_postgres_spec, open_pg_readonly, open_readonly)
    pg = is_postgres_spec(db_spec)
    conn = open_pg_readonly(db_spec) if pg else open_readonly(db_spec)
    try:
        cur = conn.cursor()
        sql = "SELECT * FROM us_table"
        params: tuple = ()
        if sito:
            sql += " WHERE sito = " + ("%s" if pg else "?")
            params = (sito,)
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def _sito_of(filters: Optional[Dict[str, Any]]) -> Optional[str]:
    for k in ("sito", "site", "scavo", "scavo_s"):
        if filters and filters.get(k):
            return str(filters[k])
    return None


@contextlib.contextmanager
def resolving_us_by_label(db_spec: str, template: Optional[str] = None,
                          filters: Optional[Dict[str, Any]] = None):
    """Per la durata del blocco il lettore di Enzo risolve le US con
    `USResolver`. Il suo modulo non cambia: le due funzioni si rimettono
    all'uscita, anche dopo un errore.

    Rende il risolutore (``.how`` dice, per chiave, uuid/label/bare/orphan).
    Se ``us_table`` non si legge, rende ``None`` e il lettore lavora come
    prima.
    """
    from . import pyarchinit_geom_importer as pgi
    try:
        rows = read_us_rows(db_spec, _sito_of(filters))
    except Exception as exc:  # noqa: BLE001
        print(f"[geometry import] us_table cannot be read ({exc}): "
              "the geometries are matched by the bare US number")
        yield None
        return
    resolver = USResolver(rows, template or DEFAULT_TEMPLATE)
    old_resolve = pgi._resolve_us_node
    old_record = pgi._record_us_without_geometry

    def _record_us_without_geometry(polygons, graph, report):
        """Come quella di Enzo, ma «ha una geometria» vuol dire «un poligono
        si è risolto su di lei», non «il suo nome è un numero della tabella»."""
        if graph is None:
            return
        with_geom = set()
        for p in polygons:
            node = resolver.resolve(graph, p["us_key"])
            if node is not None:
                with_geom.add(id(node))
        for node in getattr(graph, "nodes", []):
            if getattr(node, "node_type", "") not in pgi._STRATIGRAPHIC_NODE_TYPES:
                continue
            name = getattr(node, "name", "")
            if not name or id(node) in with_geom:
                continue
            report["us_without_geometry"].append(name)
            attrs = getattr(graph, "attributes", None)
            if isinstance(attrs, dict):
                node_id = getattr(node, "node_id", None) or getattr(node, "id", None)
                if node_id is not None:
                    attrs.setdefault(pgi.C.GRAPH_ATTR_AUX_US_NO_GEOM, []).append(node_id)

    pgi._resolve_us_node = resolver.resolve
    pgi._record_us_without_geometry = _record_us_without_geometry
    try:
        yield resolver
    finally:
        pgi._resolve_us_node = old_resolve
        pgi._record_us_without_geometry = old_record
