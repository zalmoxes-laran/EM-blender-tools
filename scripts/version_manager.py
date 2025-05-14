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
        base = f"{config['major']}.{config['minor']}.{config['patch']}"
        
        if config['mode'] == 'dev':
            return f"{base}-dev.{config['dev_build']}"
        elif config['mode'] == 'rc':
            return f"{base}-rc.{config.get('rc_build', 1)}"
        else:  # stable
            return base
    
    def increment_version(self, part: str = 'dev_build') -> str:
        """Incrementa la versione specificata"""
        config = self.load_version_config()
        
        if part == 'dev_build':
            config['dev_build'] += 1
        elif part == 'rc_build':
            config['rc_build'] = config.get('rc_build', 0) + 1
        elif part == 'patch':
            config['patch'] += 1
            config['dev_build'] = 0
            # Reset RC quando incrementiamo patch
            config['rc_build'] = 1
        elif part == 'minor':
            config['minor'] += 1
            config['patch'] = 0
            config['dev_build'] = 0
            config['rc_build'] = 1
        elif part == 'major':
            config['major'] += 1
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
        return self.get_version_string(config)
    
    def generate_wheels_section(self, mode: str) -> str:
        """Genera la sezione wheels per la modalità specifica"""
        if mode == 'dev':
            return '''
# Development mode - no wheels bundled
# External dependencies must be installed manually
'''
        else:
            # Per produzione, include tutte le wheels
            wheels_dir = self.root_dir / "wheels"
            if not wheels_dir.exists():
                return "# No wheels directory found"
            
            wheels = [f for f in wheels_dir.glob("*.whl")]
            if not wheels:
                return "# No wheels found"
            
            return f'''
[build]
# Include all dependency wheels for distribution
generated_wheels = true

[[wheels]]
url = "wheels/"
'''
    
    def generate_dependencies_section(self, mode: str) -> str:
        """Genera la sezione dipendenze"""
        if mode == 'dev':
            return '''
# Development dependencies
# Install manually: pip install pandas networkx PIL openpyxl matplotlib
'''
        else:
            # Per produzione, le dipendenze sono nelle wheels
            return "# Dependencies included in wheels"
    
    def update_manifest(self):
        """Aggiorna il manifest con la versione corrente"""
        config = self.load_version_config()
        version = self.get_version_string(config)
        
        # Leggi il template
        with open(self.manifest_template, 'r') as f:
            template = f.read()
        
        # Sostituisci i placeholder
        manifest_content = template.format(
            VERSION=version,
            WHEELS_SECTION=self.generate_wheels_section(config['mode']),
            DEPENDENCIES_SECTION=self.generate_dependencies_section(config['mode'])
        )
        
        # Scrivi il manifest
        with open(self.manifest_file, 'w') as f:
            f.write(manifest_content)
        
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
    
    args = parser.parse_args()
    vm = VersionManager(Path(__file__).parent.parent)
    
    if args.action == 'increment':
        version = vm.increment_version(args.part)
        vm.update_manifest()
        vm.update_init_py()
        print(f"Version incremented to: {version}")
    
    elif args.action == 'set-mode':
        if not args.mode:
            print("Mode required for set-mode action")
            sys.exit(1)
        version = vm.set_mode(args.mode)
        vm.update_manifest()
        vm.update_init_py()
        print(f"Mode set to {args.mode}, version: {version}")
    
    elif args.action == 'update':
        version = vm.update_manifest()
        vm.update_init_py()
        print(f"Files updated to version: {version}")
    
    elif args.action == 'current':
        config = vm.load_version_config()
        version = vm.get_version_string(config)
        print(f"Current version: {version} (mode: {config['mode']})")