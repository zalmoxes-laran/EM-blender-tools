"""Il sistema della scena: Y-up, metri — quello del glb del modello e delle letture.

Blender è Z-up. Il glb del modello che l'export Heriverse scrive passa per
l'exporter glTF di Blender, che converte ``(x, y, z)`` Blender → ``(x, z, -y)``
glTF; l'importer fa l'inversa ``(x, y, z)`` glTF → ``(x, -z, y)`` Blender.
Le letture (``data.coords`` di una regione) e i convessi di un proxy stanno nel
grafo in quel frame (node datamodel: *scene-local, glTF Y-up, metres*), e
s3Dgraphy li scrive VERBATIM nel glTF: la conversione è di chi scrive
coordinate prese dal mondo di Blender, cioè di EMtools.

Una conversione sola, qui, così il proxy, le letture e il modello cadono nello
stesso posto. Niente `bpy`: si misura con pytest.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

Vec = Tuple[float, float, float]


def blender_to_scene(p: Sequence[float]) -> Vec:
    """Un punto del mondo di Blender (Z-up) nel sistema della scena (Y-up)."""
    x, y, z = (float(v) for v in p)
    return (x, z, -y)


def scene_to_blender(p: Sequence[float]) -> Vec:
    """L'inversa: un punto della scena (Y-up) nel mondo di Blender (Z-up)."""
    x, y, z = (float(v) for v in p)
    return (x, -z, y)


def flat_to_scene(points: Iterable[Sequence[float]], ndigits: int = 6) -> List[float]:
    """Punti di Blender → la lista piatta ``[x, y, z, …]`` di un convesso,
    nel sistema della scena (arrotondata al micron, come prima)."""
    flat: List[float] = []
    for p in points:
        flat.extend(round(v, ndigits) + 0.0 for v in blender_to_scene(p))
    return flat


def flat_to_blender(flat: Sequence[float]) -> List[Vec]:
    """La lista piatta di un convesso (scena) → punti del mondo di Blender."""
    if len(flat) % 3:
        raise ValueError(f"a convex shape of {len(flat)} numbers is not x,y,z triplets")
    return [scene_to_blender(flat[i:i + 3]) for i in range(0, len(flat), 3)]
