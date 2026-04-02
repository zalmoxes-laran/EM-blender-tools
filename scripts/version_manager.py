# scripts/version_manager.py
import re
import json
from pathlib import Path
from typing import Dict, Tuple, Optional

class VersionManager:
    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.version_file = self.root_dir / "version.json"
        self.manifest_template = self.root_dir / "blender_manifest_template.toml"
        self.manifest_file = self.root_dir / "blender_manifest.toml"
        self.init_file = self.root_dir / "__init__.py"
    
    def load_version_config(self) -> Dict:
        """Carica la configurazione della versione da version.json"""
        if self.version_file.exists():
            with open(self.version_file, 'r') as f:
                return json.load(f)
        return {
            "major": 1,
            "minor": 5,
            "patch": 0,
            "dev_build": 43,
            "mode": "dev"  # dev, rc, stable
        }
    
    def save_version_config(self, config: Dict):
        """Salva la configurazione della versione"""
        with open(self.version_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def get_version_string(self, config: Dict) -> str:
        """Genera stringa di versione basata sul mode"""
        base = f"{config.get('major', 1)}.{config.get('minor', 5)}.{config.get('patch', 0)}"
        
        if config.get('mode') == 'dev':
            return f"{base}-dev.{config.get('dev_build', 0)}"
        elif config.get('mode') == 'rc':
            return f"{base}-rc.{config.get('rc_build', 1)}"
        else:  # stable
            return base
    
    def increment_version(self, part: str = 'dev_build') -> str:
        """Incrementa la versione specificata"""
        config = self.load_version_config()
        
        if part == 'dev_build':
            config['dev_build'] = config.get('dev_build', 0) + 1
        elif part == 'rc_build':
            config['rc_build'] = config.get('rc_build', 0) + 1
        elif part == 'patch':
            config['patch'] = config.get('patch', 0) + 1
            config['dev_build'] = 0
            # Reset RC quando incrementiamo patch
            config['rc_build'] = 1
        elif part == 'minor':
            config['minor'] = config.get('minor', 5) + 1
            config['patch'] = 0
            config['dev_build'] = 0
            config['rc_build'] = 1
        elif part == 'major':
            config['major'] = config.get('major', 1) + 1
            config['minor'] = 0
            config['patch'] = 0
            config['dev_build'] = 0
            config['rc_build'] = 1
        
        self.save_version_config(config)
        return self.get_version_string(config)
    
    def set_mode(self, mode: str):
        """Cambia la modalità (dev, rc, stable)"""
        config = self.load_version_config()
        config['mode'] = mode
        self.save_version_config(config)
        self.update_manifest()
        return self.get_version_string(config)
        
    def generate_wheels_section(self, mode: str, python_version: str = None) -> str:
        """Genera la sezione wheels per la modalità specifica.

        Cerca i wheel in ordine:
        1. wheels/cp{ver}/ (nuova struttura, per python_version specificato)
        2. wheels/ (vecchia struttura flat, retrocompatibilità)
        """
        wheels_dir = self.root_dir / "wheels"

        # Determina la directory da usare
        scan_dir = None
        relative_prefix = "wheels"

        if python_version:
            cp_tag = f"cp{python_version.replace('.', '')}"
            versioned_dir = wheels_dir / cp_tag
            if versioned_dir.exists() and any(versioned_dir.glob("*.whl")):
                scan_dir = versioned_dir
                relative_prefix = f"wheels/{cp_tag}"

        # Fallback: prova a trovare una qualsiasi sottocartella cp*
        if scan_dir is None:
            for subdir in sorted(wheels_dir.glob("cp*")):
                if subdir.is_dir() and any(subdir.glob("*.whl")):
                    scan_dir = subdir
                    relative_prefix = f"wheels/{subdir.name}"
                    break

        # Fallback finale: vecchia struttura flat
        if scan_dir is None:
            if wheels_dir.exists() and any(wheels_dir.glob("*.whl")):
                scan_dir = wheels_dir
                relative_prefix = "wheels"
            else:
                return ""

        wheels = list(scan_dir.glob("*.whl"))
        if not wheels:
            return ""

        # Genera la lista di wheels con indentazione consistente
        wheels_list = []
        for wheel in wheels:
            wheels_list.append(f'    "./{relative_prefix}/{wheel.name}",')

        # Rimuovi la virgola dall'ultima entry
        if wheels_list:
            wheels_list[-1] = wheels_list[-1].rstrip(',')

        # Formato che corrisponde al manifest funzionante
        return f'''wheels = [
    {chr(10).join(wheels_list)}
    ]'''
    
    def generate_dependencies_section(self, mode: str) -> str:
        """Genera la sezione dipendenze"""
        wheels_dir = self.root_dir / "wheels"
        if wheels_dir.exists() and any(wheels_dir.glob("*.whl")):
            return ""  # Se hai wheels, non serve la sezione dependencies
        else:
            return '''# External dependencies required:
    # pip install pandas networkx Pillow openpyxl matplotlib
    # Note: Run setup script to download wheels for packaging'''
    
    def repair_manifest_version(self):
        """Assicura che il manifest contenga la versione corretta"""
        try:
            config = self.load_version_config()
            expected_version = self.get_version_string(config)
            
            if self.manifest_file.exists():
                with open(self.manifest_file, 'r') as f:
                    content = f.read()
                    
                # Controlla se la versione è corretta
                version_pattern = r'version = "([^"]*)"'
                match = re.search(version_pattern, content)
                
                if not match or match.group(1) != expected_version:
                    print(f"⚠️ Version mismatch in manifest: found '{match.group(1) if match else 'none'}', expected '{expected_version}'")
                    content = re.sub(version_pattern, f'version = "{expected_version}"', content)
                    
                    with open(self.manifest_file, 'w') as f:
                        f.write(content)
                    
                    print(f"✅ Fixed manifest version to: {expected_version}")
                    return True
            return False
        except Exception as e:
            print(f"⚠️ Error repairing manifest: {e}")
            return False
    
    def update_manifest(self, python_version: str = None):
        """Aggiorna il manifest con la versione corrente"""
        config = self.load_version_config()
        version = self.get_version_string(config)

        if not self.manifest_template.exists():
            raise FileNotFoundError(f"Template manifest not found: {self.manifest_template}")

        with open(self.manifest_template, 'r') as f:
            template = f.read()

        if '{VERSION}' not in template:
            raise ValueError("Template manifest missing {VERSION} placeholder")

        # Sostituisci i placeholder - SOLO VERSION e WHEELS_SECTION
        manifest_content = template.format(
            VERSION=version,
            WHEELS_SECTION=self.generate_wheels_section(config.get('mode', 'dev'), python_version)
        )

        # Scrivi il manifest finale
        with open(self.manifest_file, 'w') as f:
            f.write(manifest_content)

        print(f"✅ Manifest generated: {self.manifest_file}")
        print(f"   Version: {version}")
        print(f"   Mode: {config.get('mode', 'dev')}")
        if python_version:
            print(f"   Python target: {python_version}")

        return version
    
    def update_init_py(self):
        """NOTA: Aggiornamento __init__.py rimosso perché bl_info non esiste più!"""
        # Non facciamo nulla perché Blender Extensions usano solo il manifest
        # Il versionamento è gestito interamente da blender_manifest.toml
        config = self.load_version_config()
        version = self.get_version_string(config)
        print(f"Note: __init__.py update skipped (Extensions use manifest only)")
        return version

# CLI interface
if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage EM Tools versions")
    parser.add_argument('action', choices=['increment', 'set-mode', 'update', 'current'])
    parser.add_argument('--part', choices=['dev_build', 'patch', 'minor', 'major'],
                       default='dev_build', help="Part to increment")
    parser.add_argument('--mode', choices=['dev', 'rc', 'stable'],
                       help="Mode to set")
    parser.add_argument('--python-version', default=None,
                       help="Target Python version for wheels (e.g., 3.11, 3.13)")

    args = parser.parse_args()
    vm = VersionManager(Path(__file__).parent.parent)

    if args.action == 'increment':
        version = vm.increment_version(args.part)
        vm.update_manifest(args.python_version)
        vm.update_init_py()
        print(f"Version incremented to: {version}")

    elif args.action == 'set-mode':
        if not args.mode:
            print("Mode required for set-mode action")
            sys.exit(1)
        version = vm.set_mode(args.mode)
        vm.update_manifest(args.python_version)
        vm.update_init_py()
        print(f"Mode set to {args.mode}, version: {version}")

    elif args.action == 'update':
        version = vm.update_manifest(args.python_version)
        vm.update_init_py()
        print(f"Files updated to version: {version}")

    elif args.action == 'current':
        config = vm.load_version_config()
        version = vm.get_version_string(config)
        print(f"Current version: {version} (mode: {config.get('mode', 'dev')})")