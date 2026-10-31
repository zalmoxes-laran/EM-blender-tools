"""MICRO-BLEND-OFFICINA-2 · point 3: the selection between Blender and
EMStudio for EVERY object of the inventory, not only the proxies.

A proxy is found by its NAME (``<graph code>.<unit>``, as before); any other
object by the graph ids it carries — its RM, the asset, version, resource,
document it stands for (s3Dgraphy's ``blend_room.ID_PROPS``, in the order
they are trusted). Pure: the operators of the sidecar call it with the
objects' custom properties.
"""

from typing import Any, Dict, Iterable, List, Mapping

try:
    from s3dgraphy.resources.blend_room import ID_PROPS
except ImportError:  # the bundled s3dgraphy predates it (< 1.6.0.dev79): the same list
    ID_PROPS = ("em_rm_node_id", "em_version_id", "em_asset_id", "em_resource_id", "em_doc_node_id")


def ids_of_props(props: Mapping[str, Any]) -> List[str]:
    out: List[str] = []
    for k in ID_PROPS:
        try:
            v = props.get(k)
        except Exception:  # noqa: BLE001 — an IDProperty group that refuses
            v = None
        if v and str(v) not in out:
            out.append(str(v))
    return out


def first_known(props: Mapping[str, Any], known) -> str:
    """The first id of the object the graph knows (``known(id) -> bool``)."""
    for i in ids_of_props(props):
        if known(i):
            return i
    return ""


def names_for_ids(objects: Iterable[Any], ids: Iterable[str], props_of=lambda o: o) -> List[str]:
    """The objects (by name) that stand for any of ``ids``."""
    want = set(ids)
    out: List[str] = []
    for o in objects:
        got = set(ids_of_props(props_of(o)))
        name = getattr(o, "name", None) or (o.get("name") if isinstance(o, dict) else None)
        if got & want and name not in out:
            out.append(name)
    return out
