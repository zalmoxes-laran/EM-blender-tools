"""U4 · «Import from tables»: the new graph's code and em.json, without Blender.
The gesture itself is measured headless in tests/blender_smoke_import_from_table.py."""
import importlib.util
import pathlib

_P = pathlib.Path(__file__).resolve().parent.parent / "import_operators" / "table_naming.py"
spec = importlib.util.spec_from_file_location("_table_naming", _P)
tn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tn)


def test_the_code_is_the_tables_name_and_the_filters():
    assert tn.graph_code_for("pyarchinit", "/tmp/x/pyarchinit_db.sqlite",
                             {"sito": "Scavo archeologico", "area": "1"}) == "pyarchinit_db_Scavo_archeologico_1"
    assert tn.graph_code_for("emdb_xlsx", "/d/GT16_units.xlsx") == "GT16_units"
    assert tn.graph_code_for("pyarchinit", "postgresql+psycopg2://u@h:5432/pyarchinit?ssl=1") == "pyarchinit"


def test_a_typed_code_wins_and_is_made_safe():
    assert tn.graph_code_for("emdb_xlsx", "/d/a.xlsx", typed=" Tempio Grande/2026 ") == "Tempio_Grande_2026"


def test_the_emjson_goes_beside_the_table_and_never_over_a_file():
    there = {"/d/GT16.em.json", "/d/GT16_2.em.json"}
    assert tn.emjson_path_for("A", "/d", exists=lambda p: False) == "/d/A.em.json"
    assert tn.emjson_path_for("GT16", "/d", exists=there.__contains__) == "/d/GT16_3.em.json"


def test_a_typed_path_gets_its_extension():
    assert tn.emjson_path_for("x", "/d", exists=lambda p: False, typed="/o/new") == "/o/new.em.json"
    assert tn.emjson_path_for("x", "/d", exists=lambda p: False, typed="/o/new.json") == "/o/new.em.json"
