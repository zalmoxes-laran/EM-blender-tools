# em_statistics/materials.py
"""Material density CSV loading and helpers for the mesh statistics exporter."""

import csv
import os


CSV_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources/materials", "ch_materials.csv")


def load_materials():
    """Carica le densità dei materiali dal file CSV."""
    materials = {}
    try:
        with open(CSV_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                materials[row['material'].strip().lower()] = float(row['density_kg_m3'])
    except FileNotFoundError:
        print(f"File {CSV_FILE} non trovato.")
    return materials


def get_material_items(self, context):
    """Restituisce l'elenco dei materiali come items per EnumProperty."""
    materials = load_materials()
    return [(mat, mat.title(), "") for mat in sorted(materials.keys())] if materials else [("none", "No material available", "")]


def format_decimal(value):
    """Converte un valore numerico con virgola come separatore decimale."""
    try:
        if isinstance(value, (int, float)):
            return f"{value:.3f}".replace('.', ',')
        return str(value)
    except Exception:
        return str(value)
