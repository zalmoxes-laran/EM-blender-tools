"""MICRO georef al salvataggio, parte 2 (24 Oct 2026) — the Georeferencing
panel's sentences in Blender's languages (``georef_manager/i18n.py``).

EM Tools had no interface translation (E1: the source is English); the panel's
new sentences now go through ``bpy.app.translations``: it_IT and de_DE, fr_FR and
es marked to validate. Pinned here, outside Blender:

- every sentence has every language, with the same placeholders;
- the sentences the panel composes (with an id, a shift, an EPSG) are recognised
  and recomposed, the captured pieces translated too;
- every literal sentence the panel, the save dialog and the conversion dialog
  pass to ``tr``/``_say`` is in the catalogue, and so are the new operators'
  labels and descriptions (Blender translates those by their exact text).
"""

import ast
import importlib.util
import pathlib
import re
import string

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(
        f"_emtools_test_{name}", _REPO / "georef_manager" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


i18n = _load("i18n")
propagation = _load("propagation")
IT, DE = i18n.catalogue("it_IT"), i18n.catalogue("de_DE")


def _fields(text):
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


def test_every_sentence_has_every_language_with_the_same_placeholders():
    for msgid, by_locale in i18n.MESSAGES.items():
        assert set(by_locale) == set(i18n.LOCALES), msgid
        for locale, msgstr in by_locale.items():
            assert msgstr.strip(), (msgid, locale)
            assert _fields(msgstr) == _fields(msgid), (msgid, locale)


def test_the_languages_to_validate_are_said():
    assert set(i18n.TO_VALIDATE) == {"fr_FR", "es"}
    assert set(i18n.LOCALES) - set(i18n.TO_VALIDATE) == {"it_IT", "de_DE"}


def test_a_sentence_with_values_is_recomposed():
    note = ("Georeferencing read from graph 6af9866e: EPSG:3844 · 327372.560, "
            "448682.650, 0.000")
    assert i18n.translate(note, IT) == ("Georiferimento letto dal grafo 6af9866e: "
                                        "EPSG:3844 · 327372.560, 448682.650, 0.000")
    assert i18n.translate(note, DE).startswith("Georeferenzierung aus dem Graphen 6af9866e")


def test_the_captured_pieces_are_translated_too():
    assert (i18n.translate("Accuracy: unknown (ballpark) → ±3 m", IT)
            == "Accuratezza: sconosciuta (ballpark) → ±3 m")
    assert (i18n.translate("Shift Z: scene 500.000 · graph 0.000", IT)
            == "Shift Z: scena 500.000 · grafo 0.000")
    assert (i18n.translate("Azimuth: scene 12.50° · graph 0.00°", DE)
            == "Azimut: Szene 12.50° · Graph 0.00°")


def test_two_reasons_are_translated_one_by_one():
    reason = ("EPSG:31700 (Dealul Piscului 1970/ Stereo 70) is deprecated in the "
              "EPSG database; PROJ reaches WGS 84 from it only with a «ballpark» "
              "(no datum shift): accuracy unknown, can be ~100 m")
    out = i18n.translate(reason, IT)
    assert out.startswith("EPSG:31700 (Dealul Piscului 1970/ Stereo 70) è deprecato")
    assert "; PROJ arriva a WGS 84" in out


def test_the_shift_z_note_is_translated():
    note = propagation.shift_z_note(500.0)
    assert i18n.translate(note, IT).startswith("Shift Z = 500.000: una scelta esplicita")


def test_an_unknown_sentence_stays_english():
    assert i18n.translate("Something nobody wrote", IT) == "Something nobody wrote"


def test_blender_gets_our_context_and_its_own_only_where_it_translates():
    d = i18n.blender_dict()
    assert set(d) == set(i18n.LOCALES)
    assert d["it_IT"][("EMGeoref", "Pull from graph")] == "Prendi dal grafo"
    assert d["it_IT"][("*", "Pull from graph")] == "Prendi dal grafo"
    assert d["it_IT"][("Operator", "Pull from graph")] == "Prendi dal grafo"
    # «Shift X» is also Blender's Shift key: never registered in its contexts
    assert ("*", "Shift X") not in d["de_DE"]
    assert d["de_DE"][("EMGeoref", "Shift X")] == "Verschiebung X"
    assert all(a in i18n.MESSAGES for a in i18n.AUTO)


# ── what the sources pass is in the catalogue ────────────────────────────────

def _literal(node):
    """The text of a constant or an implicit concatenation; None for f-strings."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _template(node):
    """An f-string as its template: {name} for each value."""
    if not isinstance(node, ast.JoinedStr):
        return None
    out = []
    for v in node.values:
        if isinstance(v, ast.Constant):
            out.append(v.value)
        else:
            out.append("{x}")
    return "".join(out)


def _passed(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", getattr(node.func, "attr", ""))
        if name == "tr" and node.args:
            yield node.args[0]
        elif name == "_say" and len(node.args) > 1:
            yield node.args[1]


def _matches_a_template(template):
    shape = re.sub(r"\{\w+\}", "{x}", template)
    return any(re.sub(r"\{\w+\}", "{x}", m) == shape for m in i18n.MESSAGES)


def test_every_sentence_given_to_tr_is_in_the_catalogue():
    missing = []
    for name in ("panel.py", "on_save.py", "operators.py"):
        for arg in _passed(_REPO / "georef_manager" / name):
            text = _literal(arg)
            if text is not None:
                if text not in i18n.MESSAGES:
                    missing.append((name, text))
                continue
            tpl = _template(arg)
            if tpl is not None and not _matches_a_template(tpl):
                missing.append((name, tpl))
    assert not missing, missing


def test_the_new_operators_labels_and_descriptions_are_in_the_catalogue():
    tree = ast.parse((_REPO / "georef_manager" / "operators.py").read_text(encoding="utf-8"))
    wanted = {"EM_OT_georef_pull_graph", "EM_OT_georef_convert_epsg",
              "EM_OT_georef_undo_conversion", "EM_OT_georef_push_geonode"}
    found = {}
    for cls in ast.walk(tree):
        if isinstance(cls, ast.ClassDef) and cls.name in wanted:
            for stmt in cls.body:
                if isinstance(stmt, ast.Assign) and stmt.targets[0].id == "bl_label":
                    found[cls.name] = stmt.value.value
    assert set(found) == wanted
    for label in found.values():
        assert label in i18n.MESSAGES, label
    pull_doc = next(c for c in ast.walk(tree) if isinstance(c, ast.ClassDef)
                    and c.name == "EM_OT_georef_pull_graph")
    desc = next(s.value.value for s in pull_doc.body if isinstance(s, ast.Assign)
                and s.targets[0].id == "bl_description")
    assert desc in i18n.MESSAGES


def test_the_save_choices_are_in_the_catalogue():
    on_save_src = (_REPO / "georef_manager" / "on_save.py").read_text(encoding="utf-8")
    for name in ("Ask", "Push the scene into the graph", "Pull the graph into the scene",
                 "Keep both as they are"):
        assert f'"{name}"' in on_save_src and name in i18n.MESSAGES
