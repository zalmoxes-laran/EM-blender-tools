# em_setup/excel_helpers.py
"""
Helper functions for Excel file handling in EM-tools.
"""

import bpy
import os
import tempfile
import shutil
import platform


def validate_excel_file(filepath):
    """
    Valida se un file Excel è accessibile (non aperto in altri programmi).

    Args:
        filepath: Path al file Excel (può essere relativo Blender //)

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if not filepath:
        return False, "Nessun file specificato"

    # Risolvi path relativo Blender
    abs_filepath = bpy.path.abspath(filepath)

    # Verifica esistenza file
    if not os.path.exists(abs_filepath):
        return False, f"File non trovato: {abs_filepath}"

    # Verifica estensione
    ext = os.path.splitext(abs_filepath)[1].lower()
    if ext not in ['.xlsx', '.xls']:
        return False, f"Formato non supportato: {ext}. Usare .xlsx o .xls"

    # Tenta apertura del file per verificare se è bloccato
    try:
        # Strategia diversa per Windows vs macOS/Linux
        is_windows = platform.system() == "Windows"

        if is_windows:
            # Su Windows, prova a copiare il file in temp
            temp_dir = tempfile.gettempdir()
            temp_filename = f"em_validate_{os.path.basename(abs_filepath)}"
            temp_file_path = os.path.join(temp_dir, temp_filename)

            try:
                shutil.copy2(abs_filepath, temp_file_path)
                # Pulizia
                os.remove(temp_file_path)
                return True, None
            except PermissionError:
                return False, f"File bloccato da un altro programma. Chiudere Excel o altri software che stanno usando il file:\n{os.path.basename(abs_filepath)}"
            except Exception as e:
                return False, f"Errore accesso file: {str(e)}"
        else:
            # Su macOS/Linux, prova apertura diretta
            with open(abs_filepath, 'rb') as f:
                f.read(1)  # Leggi un byte per verificare accesso
            return True, None

    except PermissionError:
        return False, f"File bloccato da un altro programma. Chiudere Excel o altri software che stanno usando il file:\n{os.path.basename(abs_filepath)}"
    except Exception as e:
        return False, f"Errore durante validazione: {str(e)}"


def get_excel_sheets(filepath):
    """
    Ottieni lista dei fogli disponibili in un file Excel.

    Args:
        filepath: Path al file Excel

    Returns:
        list: Lista di nomi dei fogli, o lista vuota se errore
    """
    if not filepath:
        return []

    try:
        import pandas as pd
        import io

        abs_filepath = bpy.path.abspath(filepath)

        if not os.path.exists(abs_filepath):
            return []

        # Strategia buffer per evitare lock su file
        is_windows = platform.system() == "Windows"

        if is_windows:
            # Windows: usa file temporaneo
            temp_dir = tempfile.gettempdir()
            temp_filename = f"em_sheets_{os.path.basename(abs_filepath)}"
            temp_file_path = os.path.join(temp_dir, temp_filename)

            try:
                shutil.copy2(abs_filepath, temp_file_path)
                xl = pd.ExcelFile(temp_file_path, engine='openpyxl')
                sheets = xl.sheet_names
                xl.close()
                os.remove(temp_file_path)
                return sheets
            except Exception:
                return []
        else:
            # macOS/Linux: usa buffer memoria
            try:
                with open(abs_filepath, 'rb') as f:
                    buffer = io.BytesIO(f.read())
                xl = pd.ExcelFile(buffer, engine='openpyxl')
                sheets = xl.sheet_names
                xl.close()
                buffer.close()
                return sheets
            except Exception:
                return []

    except ImportError:
        print("pandas o openpyxl non disponibili")
        return []
    except Exception as e:
        print(f"Errore lettura fogli Excel: {e}")
        return []


def get_excel_columns(filepath, sheet_name):
    """
    Ottieni lista delle colonne da un foglio Excel.

    Args:
        filepath: Path al file Excel
        sheet_name: Nome del foglio

    Returns:
        list: Lista di nomi delle colonne, o lista vuota se errore
    """
    if not filepath or not sheet_name:
        return []

    try:
        import pandas as pd
        import io

        abs_filepath = bpy.path.abspath(filepath)

        if not os.path.exists(abs_filepath):
            return []

        # Strategia buffer per evitare lock su file
        is_windows = platform.system() == "Windows"

        if is_windows:
            # Windows: usa file temporaneo
            temp_dir = tempfile.gettempdir()
            temp_filename = f"em_cols_{os.path.basename(abs_filepath)}"
            temp_file_path = os.path.join(temp_dir, temp_filename)

            try:
                shutil.copy2(abs_filepath, temp_file_path)
                # Leggi solo la prima riga (header)
                df = pd.read_excel(temp_file_path, sheet_name=sheet_name,
                                 nrows=0, engine='openpyxl')
                columns = list(df.columns)
                os.remove(temp_file_path)
                return columns
            except Exception as e:
                print(f"Errore Windows get_columns: {e}")
                return []
        else:
            # macOS/Linux: usa buffer memoria
            try:
                with open(abs_filepath, 'rb') as f:
                    buffer = io.BytesIO(f.read())
                # Leggi solo la prima riga (header)
                df = pd.read_excel(buffer, sheet_name=sheet_name,
                                 nrows=0, engine='openpyxl')
                columns = list(df.columns)
                buffer.close()
                return columns
            except Exception as e:
                print(f"Errore macOS get_columns: {e}")
                return []

    except ImportError:
        print("pandas o openpyxl non disponibili")
        return []
    except Exception as e:
        print(f"Errore lettura colonne Excel: {e}")
        return []
