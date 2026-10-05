"""E1 · l'interfaccia di EM Tools è in inglese (E.D., 4 ottobre 2026, sera).

EM Tools non ha un sistema di traduzione dell'interfaccia (`translation_tags.py`
mostra le traduzioni dei DATI, fatte in EMStudio): quindi ogni frase che una
persona legge in Blender è in inglese. La tab è «EM Room», il pannello «Room»,
«The graph» quello che era «Il grafo»; «Offset proxy» resta.

La prova legge i sorgenti: le etichette (`bl_label`, `bl_category`,
`bl_description`), i `name`/`description`/`text` delle proprietà e dei
`layout`, i `report`, e il docstring degli operatori e dei menu che non hanno un
`bl_description` (è quello che Blender mostra come tooltip). Commenti, docstring
dei moduli e `print` restano fuori: non sono interfaccia.
"""

import ast
import pathlib
import re

_REPO = pathlib.Path(__file__).resolve().parent.parent
_ESCLUSI = ("__pycache__", ".venv", "build/", "tests/", "wheels/", "_dead_code/",
            "scripts/")

#: parole che in inglese non ci sono, più le vocali accentate
_ITALIANO = re.compile(
    r"(?i)\b(il|lo|gli|della|delle|dello|degli|nella|nelle|questo|questa|"
    r"perché|più|già|cartella|nessun[oa]?|scegli|epoche|unità|tabella|"
    r"grafo|stanza|aggiorna|carica|salva|apri|ricarica|esporta|importa|dati|crea|mostra|seleziona)\b"
    r"|[àèìòù]")
_KW = {"text", "name", "description", "label"}
_LABELS = ("bl_label", "bl_description", "bl_category")


def _frasi(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in _LABELS:
                    for c in ast.walk(node.value):
                        if isinstance(c, ast.Constant) and isinstance(c.value, str):
                            yield c.lineno, c.value
        elif isinstance(node, ast.Call):
            fn = node.func
            nome = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            for kw in node.keywords:
                if kw.arg in _KW:
                    for c in ast.walk(kw.value):
                        if isinstance(c, ast.Constant) and isinstance(c.value, str):
                            yield c.lineno, c.value
            if nome in ("report", "label"):
                for a in node.args:
                    for c in ast.walk(a):
                        if isinstance(c, ast.Constant) and isinstance(c.value, str):
                            yield c.lineno, c.value
            if nome == "EnumProperty":
                for kw in node.keywords:
                    if kw.arg == "items" and isinstance(kw.value, (ast.List, ast.Tuple)):
                        for c in ast.walk(kw.value):
                            if isinstance(c, ast.Constant) and isinstance(c.value, str):
                                yield c.lineno, c.value
        elif isinstance(node, ast.ClassDef):
            nomi = {t.id for b in node.body if isinstance(b, ast.Assign)
                    for t in b.targets if isinstance(t, ast.Name)}
            if "bl_idname" in nomi and "bl_description" not in nomi:
                ds = ast.get_docstring(node)
                if ds:
                    yield node.lineno, ds


def test_NESSUNA_FRASE_ITALIANA_NELL_INTERFACCIA():
    trovate = []
    for p in sorted(_REPO.rglob("*.py")):
        rel = p.relative_to(_REPO).as_posix()
        if any(x in rel + "/" for x in _ESCLUSI):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for riga, frase in _frasi(tree):
            if _ITALIANO.search(frase):
                trovate.append(f"{rel}:{riga} {frase[:80]!r}")
    assert not trovate, "\n".join(trovate)


def test_I_NOMI_DELLE_TAB_E_DEI_PANNELLI():
    sync = (_REPO / "sync_manager" / "panel.py").read_text()
    # T1/Z1 (E.D., 5 Oct 2026) · two tabs: «Where you work» heads the tab EM
    assert 'bl_label = "Where you work"' in sync
    assert 'bl_category = "EM"' in sync
    info = (_REPO / "graph_info" / "ui.py").read_text()
    assert 'bl_label = "The graph"' in info
    assert 'text="The graph"' in info
