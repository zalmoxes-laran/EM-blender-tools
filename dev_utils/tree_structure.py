import os

def list_files(startpath, output_file):
    with open(output_file, 'w') as f:
        for root, dirs, files in os.walk(startpath):
            # Filtra directory nascoste e __pycache__
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            # Filtra file nascosti
            files = [f for f in files if not f.startswith('.')]
            
            level = root.replace(startpath, '').count(os.sep)
            indent = '  ' * level
            f.write(f"{indent}- {os.path.basename(root)}/\n")
            subindent = '  ' * (level + 1)
            for file in files:
                f.write(f"{subindent}- {file}\n")

# Percorso della directory
start_path = r"/Users/emanueldemetrescu/Library/Application Support/Blender/4.2/scripts/addons/EM-blender-tools"

# Percorso del file di output accanto al file Python
output_file = os.path.join(os.path.dirname(__file__), "foldertree.txt")

# Genera la struttura e salva nel file
list_files(start_path, output_file)

print(f"Struttura salvata in: {output_file}")
