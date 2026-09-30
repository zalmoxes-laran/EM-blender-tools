"""Il sistema della scena (Y-up) e il mondo di Blender (Z-up): una conversione sola."""
import pytest

import scene_space as SS


def test_blender_z_up_diventa_scena_y_up():
    # l'exporter glTF di Blender: (x, y, z) → (x, z, -y)
    assert SS.blender_to_scene((1.0, 2.0, 3.0)) == (1.0, 3.0, -2.0)


def test_l_inversa_e_quella_dell_importer():
    # l'importer glTF di Blender: (x, y, z) → (x, -z, y)
    assert SS.scene_to_blender((1.0, 2.0, 3.0)) == (1.0, -3.0, 2.0)


@pytest.mark.parametrize("p", [(0, 0, 0), (1.5, -2.25, 7), (-3, 4, -5)])
def test_andata_e_ritorno(p):
    assert SS.scene_to_blender(SS.blender_to_scene(p)) == tuple(float(v) for v in p)


def test_il_convesso_piatto_nella_scena_e_ritorno():
    corners = [(0, 0, 0), (1, 0, 0), (0, 2, 0), (0, 0, 3)]
    flat = SS.flat_to_scene(corners)
    assert flat == [0, 0, 0, 1, 0, 0, 0, 0, -2, 0, 3, 0]
    assert all(str(v) != "-0.0" for v in flat), "niente -0.0 nel grafo"
    assert SS.flat_to_blender(flat) == [tuple(float(v) for v in c) for c in corners]


def test_una_lista_non_a_terne_si_rifiuta():
    with pytest.raises(ValueError):
        SS.flat_to_blender([1, 2])
