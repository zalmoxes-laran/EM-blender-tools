"""MICRO-EMTOOLS-PANNELLO (E.D., 30 Oct 2026) · «Where you work» and the EM
Data Tree, more compact. Read as source (the drawing needs a Blender; the
headless measure is `tests/blender_shots_data_tree_compact.py`).

1. «Where you work» is the first row of the EM Data Tree, a chip opening
   EM ▸ Mode; no button of the old panel is lost — each is in that menu.
2. The file is one row: name, Save, Save as…, Open the folder.
3. The pencil on the graph written in; no «Writing in:» row.
4. The warnings: a counter ⚠ n on the file's row, the list only when opened.
5. Import from tables / Re-import a table / Auxiliary files: one «Import».
6. Graph info stays; the em.json schema line is the file row's tooltip.
"""
import pathlib
import re

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _src(*parts):
    return _REPO.joinpath(*parts).read_text(encoding="utf-8")


def _code(text):
    return re.sub(r"#.*", "", text)


def test_1_no_panel_where_you_work_and_the_chip_heads_the_tree():
    panel = _src("sync_manager", "panel.py")
    assert "bpy.types.Panel" not in panel
    setup = _src("em_setup", "ui.py")
    body = setup[setup.index("class EM_SetupPanel"):setup.index("def _draw_graph_info")]
    draw = body[body.index("    def draw(self, context):"):]
    assert draw.index("draw_mode_row(") < draw.index("draw_graph_tree("), "the first row"
    # the chip opens EM ▸ Mode: one source
    assert 'bpy.ops.wm.call_menu(name="EM_MT_mode")' in panel
    menu = _src("em_header_menu.py")
    assert "draw_places(self.layout, context)" in menu
    assert "draw_place_commands(self.layout, context)" in menu


def test_1_every_button_of_the_old_panel_is_in_em_mode():
    panel = _code(_src("sync_manager", "panel.py"))
    places = _code(_src("sync_manager", "windows.py"))
    places = places[places.index("def draw_places"):places.index("def draw_node_step")]
    commands = panel[panel.index("def draw_place_commands"):]
    # on this computer: Work with EMStudio, Enter a collaborative room… (the
    # places), Create a collaborative room from this study… (under them)
    assert "ops.MODE_SIDECAR" in places and '"em.room_enter"' in places
    assert '"em.room_bring"' in panel and "HERE_COMMANDS" in commands
    # with EMStudio: Stop (= On this computer, a place), Permissions…
    assert "ops.MODE_STANDALONE" in places and '"em.sidecar_permissions"' in commands
    # in a room: Sync the scene…, Open in EMStudio, Change…, ⋯, the state's fix
    for said in ('"em.scene_check"', '"em.open_in_emstudio"', '"em.where_change"',
                 '"EM_MT_room_more"', 'st["op"]'):
        assert said in commands, said
    # the zones: Log…, the message's gesture, the node
    assert '"em.sync_log"' in commands and 'msg["op"]' in commands
    assert '"Choose the node…"' in places


def test_1_the_detail_is_the_tooltip_and_a_fix_stays_in_sight():
    panel = _src("sync_manager", "panel.py")
    op = panel[panel.index("class EM_OT_where_menu"):panel.index("def draw_mode_row")]
    assert "def description(cls, context, properties)" in op
    assert 'where.chip(where.read_state(context))["tip"]' in op
    row = panel[panel.index("def draw_mode_row"):panel.index("def draw_place_commands")]
    assert 'a = c["action"]' in row and "fix.operator(" in row


def test_2_the_file_is_one_row():
    tree = _src("em_setup", "graph_tree.py")
    loop = tree[tree.index("def draw_graph_tree("):tree.index("def _unsaved_reasons(")]
    assert '"em.graph_origin_info"' in loop, "the name, its tooltip the path"
    assert "draw_save_row(right, origin, unsaved)" in loop
    assert '"wm.path_open", text=""' in loop and 'icon="FILE_FOLDER"' in loop
    assert 'sub.label(text=f"Writing in:' not in loop
    tip = tree[tree.index("def origin_tooltip("):tree.index("class EM_OT_graph_origin_info")]
    assert "origin.path" in tip and "Unsaved" in tip
    # the path of a LOADED graph is not drawn: it is the tooltip
    path = tree[tree.index("def _draw_active_path("):tree.index("def emjson_branches(")]
    assert "if row.graphml_path and present:" in path


def test_3_the_pencil_marks_the_graph_written_in():
    tree = _src("em_setup", "graph_tree.py")
    loop = tree[tree.index("def draw_graph_tree("):tree.index("def _unsaved_reasons(")]
    assert 'icon="GREASEPENCIL" if i == active else "RADIOBUT_OFF"' in loop


def test_4_the_warnings_are_a_counter_and_no_row_at_zero():
    tree = _src("em_setup", "graph_tree.py")
    loop = tree[tree.index("def draw_graph_tree("):tree.index("def _unsaved_reasons(")]
    assert 'count.prop(rows[active], "show_warnings_section", text=str(warnings)' in loop
    assert "if is_active and warnings" in loop
    setup = _src("em_setup", "ui.py")
    draw = setup[setup.index("    def draw(self, context):", setup.index("class EM_SetupPanel")):
                 setup.index("def _draw_graph_info")]
    assert "_warnings and _active.show_warnings_section" in draw
    assert "summarise(" not in _code(setup), "the collapsed digest line is gone"


def test_5_one_import_with_three_voices():
    setup = _src("em_setup", "ui.py")
    for gone in ("class VIEW3D_PT_import_from_tables", "class VIEW3D_PT_reimport_table",
                 "class VIEW3D_PT_auxiliary_files"):
        assert gone not in setup, gone
    cls = setup[setup.index("class VIEW3D_PT_em_import"):]
    assert 'bl_label = "Import"' in cls and "DEFAULT_CLOSED" in cls
    for draw in ("draw_reimport_table(", "_draw_auxiliary_section(", "draw_import_from_tables("):
        assert draw in cls, draw


def test_6_graph_info_stays_and_the_schema_is_a_tooltip():
    setup = _src("em_setup", "ui.py")
    info = setup[setup.index("    def _draw_graph_info"):setup.index("    def _draw_graph_warnings")]
    for counter in ('"US/USV"', '"Epochs"', '"Properties"', '"Documents"', '"Language"'):
        assert counter in info, counter
    assert "_format_version_banner(" not in _code(info)
    tree = _src("em_setup", "graph_tree.py")
    assert "_format_version_banner(rows[active])" in tree
