#!/usr/bin/env python3
"""
Build Blender Extension Package
Legge blender_manifest.toml, scarica i .blext da GitHub, crea lo ZIP
"""

import os
import sys
import zipfile
import shutil
import re
import tomli  # Per Python < 3.11, installa con: pip install tomli
from pathlib import Path
from typing import List, Dict, Optional
import requests
from datetime import datetime


class ExtensionPackager:
    """Crea pacchetti Blender Extension da manifest esistente"""
    
    PLATFORM_MAPPINGS = {
        'linux-x64': ['linux-x64', 'linux_x64', 'linux', 'linux-amd64'],
        'windows-x64': ['windows-x64', 'windows_x64', 'windows', 'win64', 'win-x64'],
        'macos-arm64': ['macos-arm64', 'macos_arm64', 'macos-arm', 'darwin-arm64', 'osx-arm64'],
        'macos-x64': ['macos-x64', 'macos_x64', 'darwin-x64', 'osx-x64']
    }
    
    def __init__(self, addon_dir: Path):
        """
        Args:
            addon_dir: Directory root dell'addon (dove sta blender_manifest.toml)
        """
        self.addon_dir = addon_dir
        self.manifest_path = addon_dir / "blender_manifest.toml"
        self.manifest = None
        
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"❌ blender_manifest.toml non trovato in {addon_dir}")
        
        self._load_manifest()
    
    def _load_manifest(self):
        """Carica e valida il manifest"""
        print(f"📖 Lettura manifest: {self.manifest_path}")
        
        with open(self.manifest_path, 'rb') as f:
            self.manifest = tomli.load(f)
        
        # Valida campi essenziali
        required = ['id', 'version', 'name', 'type', 'maintainer']
        for field in required:
            if field not in self.manifest:
                raise ValueError(f"❌ Campo '{field}' mancante in blender_manifest.toml")
        
        print(f"✓ Addon: {self.manifest['name']} v{self.manifest['version']}")
        print(f"  ID: {self.manifest['id']}")
    
    def detect_platform(self, filename: str) -> Optional[str]:
        """Rileva piattaforma dal nome file"""
        filename_lower = filename.lower()
        
        for platform, patterns in self.PLATFORM_MAPPINGS.items():
            for pattern in patterns:
                if pattern in filename_lower:
                    return platform
        return None
    
    def get_github_info(self) -> tuple[str, str]:
        """
        Estrae info GitHub dal manifest
        Returns: (repo, tag)
        """
        # Default repository
        DEFAULT_REPO = "zalmoxes-laran/EM-blender-tools"
        
        website = self.manifest.get('website', '')
        version = self.manifest['version']
        
        # Estrai owner/repo da URL GitHub se presente
        github_match = re.search(r'github\.com/([^/]+/[^/]+)', website)
        if github_match:
            default_repo = github_match.group(1).rstrip('/')
        else:
            default_repo = DEFAULT_REPO
        
        # Chiedi conferma repository
        print(f"📦 Repository GitHub (default: {default_repo})")
        repo = input(f"   Repository [Enter per '{default_repo}']: ").strip() or default_repo
        
        # Tag della release (default: v + version)
        default_tag = f"v{version}"
        print(f"\n📌 Tag release da scaricare (default: {default_tag})")
        tag = input(f"   Tag [Enter per '{default_tag}']: ").strip() or default_tag
        
        return repo, tag
    
    def download_blext_from_github(self, repo: str, tag: str, output_dir: Path) -> List[Path]:
        """Scarica i .blext da GitHub release"""
        print(f"\n📥 Scaricamento da GitHub: {repo} @ {tag}")
        
        url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            release_data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Errore API GitHub: {e}")
            return []
        
        # Filtra .blext
        assets = [a for a in release_data.get('assets', []) if a['name'].endswith('.blext')]
        
        if not assets:
            print("⚠️  Nessun .blext trovato in questa release")
            return []
        
        print(f"✓ Trovati {len(assets)} file .blext:")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        downloaded = []
        
        for asset in assets:
            filename = asset['name']
            url = asset['browser_download_url']
            output_path = output_dir / filename
            
            print(f"  • {filename}...", end=' ', flush=True)
            
            try:
                resp = requests.get(url, stream=True)
                resp.raise_for_status()
                
                with open(output_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                size_mb = output_path.stat().st_size / 1024 / 1024
                print(f"✓ ({size_mb:.1f} MB)")
                downloaded.append(output_path)
            except Exception as e:
                print(f"❌ {e}")
        
        return downloaded
    
    def generate_extension_toml(self, blext_files: Dict[str, Path]) -> str:
        """Genera extension.toml dai dati del manifest"""
        m = self.manifest
        
        toml = f"""# Blender Extension Manifest
# Auto-generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

[extension]
id = "{m['id']}"
version = "{m['version']}"
name = "{m['name']}"
type = "{m['type']}"
maintainer = "{m['maintainer']}"
"""
        
        # Campi opzionali
        if 'license' in m:
            toml += f'license = "{m["license"]}"\n'
        if 'blender_version_min' in m:
            toml += f'blender_version_min = "{m["blender_version_min"]}"\n'
        if 'tagline' in m:
            toml += f'tagline = "{m["tagline"]}"\n'
        if 'website' in m:
            toml += f'website = "{m["website"]}"\n'
        
        # Builds
        for platform, filepath in sorted(blext_files.items()):
            toml += f'\n[builds.{platform}]\n'
            toml += f'file = "builds/{filepath.name}"\n'
        
        return toml
    
    def create_package(self, blext_dir: Path, output_path: Path) -> Path:
        """Crea il pacchetto .zip finale"""
        print("\n🔨 Creazione pacchetto...")
        
        # Trova .blext
        blext_files = list(blext_dir.glob("*.blext"))
        if not blext_files:
            raise FileNotFoundError(f"❌ Nessun .blext trovato in {blext_dir}")
        
        # Mappa piattaforme
        platform_files = {}
        for blext in blext_files:
            platform = self.detect_platform(blext.name)
            if platform:
                platform_files[platform] = blext
                print(f"  ✓ {blext.name} → {platform}")
            else:
                print(f"  ⚠️  {blext.name} → piattaforma sconosciuta (ignorato)")
        
        if not platform_files:
            raise ValueError("❌ Nessuna piattaforma riconosciuta nei file .blext")
        
        # Struttura temporanea
        temp_dir = blext_dir.parent / "temp_package"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        temp_dir.mkdir(parents=True)
        builds_dir = temp_dir / "builds"
        builds_dir.mkdir()
        
        # Copia .blext
        for platform, blext in platform_files.items():
            shutil.copy2(blext, builds_dir / blext.name)
        
        # Genera extension.toml
        toml_content = self.generate_extension_toml(platform_files)
        (temp_dir / "extension.toml").write_text(toml_content)
        print("  ✓ extension.toml generato")
        
        # Copia README se esiste
        readme_src = self.addon_dir / "README.md"
        if readme_src.exists():
            shutil.copy2(readme_src, temp_dir / "README.md")
            print("  ✓ README.md copiato")
        
        # Copia LICENSE se esiste
        license_src = self.addon_dir / "LICENSE"
        if license_src.exists():
            shutil.copy2(license_src, temp_dir / "LICENSE")
            print("  ✓ LICENSE copiato")
        
        # Crea ZIP
        print(f"\n📦 Creazione {output_path.name}...")
        
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(temp_dir.parent)
                    zipf.write(file_path, arcname)
        
        # Cleanup
        shutil.rmtree(temp_dir)
        
        size_mb = output_path.stat().st_size / 1024 / 1024
        print(f"✅ Pacchetto creato: {output_path}")
        print(f"   Dimensione: {size_mb:.2f} MB")
        
        return output_path


def main():
    print("=" * 70)
    print("🚀 Blender Extension Package Builder")
    print("=" * 70)
    
    # Directory addon (dove sta questo script)
    script_dir = Path(__file__).parent.resolve()
    addon_dir = script_dir
    
    # Cerca blender_manifest.toml
    if not (addon_dir / "blender_manifest.toml").exists():
        print(f"\n❌ blender_manifest.toml non trovato in {addon_dir}")
        print("   Assicurati di eseguire lo script dalla root dell'addon")
        sys.exit(1)
    
    try:
        packager = ExtensionPackager(addon_dir)
    except Exception as e:
        print(f"\n❌ Errore nel caricamento del manifest: {e}")
        sys.exit(1)
    
    # Directory per .blext (da gitignore)
    blext_dir = addon_dir / "blext"
    blext_dir.mkdir(exist_ok=True)
    
    # Controlla .gitignore
    gitignore = addon_dir / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        if 'blext/' not in content and 'blext' not in content:
            print("\n⚠️  Aggiungi 'blext/' al .gitignore!")
    else:
        print("\n💡 Crea un .gitignore con 'blext/' per ignorare i download")
    
    # Download da GitHub
    print("\n" + "=" * 70)
    print("📥 DOWNLOAD FILES")
    print("=" * 70)
    
    try:
        repo, tag = packager.get_github_info()
        downloaded = packager.download_blext_from_github(repo, tag, blext_dir)
        
        if not downloaded:
            print("\n⚠️  Nessun file scaricato.")
            print("   Metti manualmente i .blext in ./blext/ e rilancia lo script")
            
            # Controlla se ci sono già file
            existing = list(blext_dir.glob("*.blext"))
            if existing:
                print(f"\n✓ Trovati {len(existing)} .blext esistenti, procedo...")
            else:
                sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Download annullato. Uso .blext esistenti se disponibili...")
        existing = list(blext_dir.glob("*.blext"))
        if not existing:
            print("❌ Nessun .blext trovato in ./blext/")
            sys.exit(1)
    
    # Crea pacchetto
    print("\n" + "=" * 70)
    print("📦 CREAZIONE PACCHETTO")
    print("=" * 70)
    
    # Output fuori dalla cartella addon
    addon_name = packager.manifest['id'].split('.')[-1]
    version = packager.manifest['version']
    output_dir = addon_dir.parent / "releases"
    output_dir.mkdir(exist_ok=True)
    
    output_zip = output_dir / f"{addon_name}_v{version}.zip"
    
    try:
        packager.create_package(blext_dir, output_zip)
    except Exception as e:
        print(f"\n❌ Errore nella creazione del pacchetto: {e}")
        sys.exit(1)
    
    # Riepilogo finale
    print("\n" + "=" * 70)
    print("✅ COMPLETATO!")
    print("=" * 70)
    print(f"\n📁 File pronto: {output_zip.relative_to(addon_dir.parent)}")
    print(f"\n📤 Prossimi passi:")
    print(f"   1. Vai su https://extensions.blender.org")
    print(f"   2. Login e clicca 'Upload Extension'")
    print(f"   3. Carica: {output_zip.name}")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Operazione annullata")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Errore: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)