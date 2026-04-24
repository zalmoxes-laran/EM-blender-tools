# export_manager/providers/tabular/ui.py
"""Draw function for the 'Tabular Export' section of the Export panel."""


def poll(context):
    return True


def draw(box, context):
    row = box.row()
    row.operator("export.uuss_export", text="EM (csv)", emboss=True, icon='LONGDISPLAY')

    row = box.row()
    row.prop(context.window_manager.export_tables_vars, 'table_type', expand=True)
