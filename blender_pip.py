import os
import sys
import subprocess
import importlib.util
import site
import platform

class Pip:
    @staticmethod
    def debug_python_environment():
        """
        Stampa informazioni dettagliate sull'ambiente Python
        """
        print("\n--- DEBUG PYTHON ENVIRONMENT ---")
        print(f"Python Executable: {sys.executable}")
        print(f"Python Version: {sys.version}")
        print(f"Platform: {platform.system()} {platform.release()}")
        
        print("\nSys Path:")
        for path in sys.path:
            print(f"- {path}")
        
        print("\nSite Packages:")
        for path in site.getsitepackages():
            print(f"- {path}")
        
        print("\nUser Site Packages:")
        print(site.getusersitepackages())
        
        print("\nEnvironment Variables:")
        env_vars = ['PYTHONPATH', 'PYTHONHOME', 'PATH', 'VIRTUAL_ENV']
        for var in env_vars:
            print(f"{var}: {os.environ.get(var, 'Not set')}")
        
        try:
            import pip
            print(f"\nPip Version: {pip.__version__}")
            print(f"Pip Location: {pip.__file__}")
        except ImportError:
            print("\nPip not installed")
        
        print("\nInstalled Modules:")
        try:
            installed_modules = Pip.list_installed_modules()
            for module in installed_modules:
                print(f"- {module}")
        except Exception as e:
            print(f"Error listing modules: {e}")
        
        print("\n--- END DEBUG ---")

    @staticmethod
    def get_addon_lib_dir():
        """
        Ottiene la directory lib dell'addon per l'installazione locale
        """
        # Determina la directory del modulo corrente (l'addon)
        caller_frame = sys._getframe(1)
        caller_file = caller_frame.f_globals.get('__file__')
        if not caller_file:
            caller_file = __file__
            
        addon_dir = os.path.dirname(os.path.abspath(caller_file))
        
        # Crea la directory lib se non esiste
        lib_dir = os.path.join(addon_dir, 'lib')
        os.makedirs(lib_dir, exist_ok=True)
        
        return lib_dir

    @staticmethod
    def setup_addon_lib_path():
        """
        Aggiunge la directory lib dell'addon al sys.path
        """
        lib_dir = Pip.get_addon_lib_dir()
        
        # Aggiungi al path se non è già presente
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        
        return lib_dir

    @staticmethod
    def get_blender_site_packages():
        """
        Trova la directory site-packages di Blender
        """
        # Trova potenziali directory site-packages
        blender_python_dir = os.path.dirname(sys.executable)
        potential_paths = []
        
        if platform.system() == "Windows":
            # Percorsi tipici su Windows
            potential_paths.extend([
                os.path.join(blender_python_dir, 'lib', 'site-packages'),
                os.path.join(blender_python_dir, 'Scripts', 'Python', 'Lib', 'site-packages'),
                os.path.join(blender_python_dir, '..', 'python', 'lib', 'site-packages'),
                # Blender 2.8+ su Windows
                os.path.join(os.path.dirname(blender_python_dir), 'python', 'lib', 'site-packages')
            ])
        else:
            # Percorsi tipici su Mac/Linux
            potential_paths.extend([
                os.path.join(blender_python_dir, 'lib', 'python3.10', 'site-packages'),
                os.path.join(blender_python_dir, 'lib', 'python3.9', 'site-packages'),
                os.path.join(blender_python_dir, 'lib', 'python3.8', 'site-packages')
            ])
        
        # Aggiungi i site-packages standard
        potential_paths.extend(site.getsitepackages())
        
        # Cerca una directory scrivibile
        for path in potential_paths:
            if os.path.exists(path):
                # Verifica se è scrivibile
                try:
                    test_file = os.path.join(path, 'write_test.txt')
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                    print(f"Found writable site-packages: {path}")
                    return path
                except (IOError, PermissionError):
                    print(f"Site-packages found but not writable: {path}")
                    continue
        
        # Se non troviamo una directory scrivibile, restituiamo None
        print("No writable site-packages found")
        return None

    @staticmethod
    def upgrade_pip():
        """
        Aggiorna pip usando subprocess
        """
        try:
            # Prova prima l'aggiornamento standard
            cmd = [sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip']
            
            print(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                print("Pip upgraded successfully")
                return True
            else:
                print(f"Standard pip upgrade failed: {result.stderr}")
                
                # Prova con l'installazione utente
                cmd.append('--user')
                print(f"Trying with --user: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    print("Pip upgraded successfully with --user flag")
                    return True
                else:
                    print(f"User pip upgrade failed: {result.stderr}")
                    return False
                    
        except Exception as e:
            print(f"Error during pip upgrade: {e}")
            return False

    @staticmethod
    def install(module, upgrade=False, min_version=None):
        """
        Installa un modulo con strategia a cascata:
        1. Prova l'installazione a livello di sistema Blender
        2. Se fallisce, installa nella directory lib dell'addon
        
        Args:
            module (str): Nome del modulo da installare
            upgrade (bool, optional): Se True, forza l'aggiornamento
            min_version (str, optional): Versione minima richiesta (es. "1.3.0")
            
        Returns:
            tuple: (bool success, str message, str installation_path)
        """
        module_base_name = module.split('==')[0].split('<')[0].split('>')[0].strip()
        
        # Verifica se il modulo è già installato correttamente
        if not upgrade and Pip.is_module_installed(module_base_name):
            if min_version:
                try:
                    import pkg_resources
                    installed_version = pkg_resources.get_distribution(module_base_name).version
                    if pkg_resources.parse_version(installed_version) >= pkg_resources.parse_version(min_version):
                        print(f"{module_base_name} {installed_version} is already installed (>= {min_version})")
                        
                        # Trova il percorso del modulo
                        spec = importlib.util.find_spec(module_base_name)
                        install_path = os.path.dirname(spec.origin) if spec else "Unknown"
                        
                        return True, f"Already installed: {module_base_name} {installed_version}", install_path
                except Exception as e:
                    print(f"Error checking version: {e}")
            else:
                print(f"{module_base_name} is already installed")
                
                # Trova il percorso del modulo
                spec = importlib.util.find_spec(module_base_name)
                install_path = os.path.dirname(spec.origin) if spec else "Unknown"
                
                return True, f"Already installed: {module_base_name}", install_path
        
        # Aggiungi la versione minima al nome del modulo se necessario
        if min_version and '==' not in module and '<' not in module and '>' not in module:
            module = f"{module}>={min_version}"
            
        print(f"\nInstalling {module}...")
            
        # STRATEGIA 1: Prova l'installazione nella directory site-packages di Blender
        site_packages_dir = Pip.get_blender_site_packages()
        if site_packages_dir:
            try:
                print(f"Attempting to install in Blender site-packages: {site_packages_dir}")
                
                cmd = [
                    sys.executable, 
                    '-m', 'pip', 
                    'install',
                    '--target', site_packages_dir,
                    '--no-warn-script-location'
                ]
                
                if upgrade:
                    cmd.append('--upgrade')
                    
                cmd.append(module)
                
                print(f"Command: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    print(f"Successfully installed {module} in Blender site-packages")
                    return True, f"Installed in Blender site-packages: {module}", site_packages_dir
                else:
                    print(f"Failed to install in Blender site-packages: {result.stderr}")
            except Exception as e:
                print(f"Error during Blender site-packages installation: {e}")
        
        # STRATEGIA 2: Installazione nella directory lib dell'addon
        try:
            lib_dir = Pip.get_addon_lib_dir()
            print(f"Attempting to install in addon lib directory: {lib_dir}")
            
            cmd = [
                sys.executable, 
                '-m', 'pip', 
                'install',
                '--target', lib_dir,
                '--no-warn-script-location'
            ]
            
            if upgrade:
                cmd.append('--upgrade')
                
            cmd.append(module)
            
            print(f"Command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                # Assicurati che la directory lib sia nel path
                Pip.setup_addon_lib_path()
                
                print(f"Successfully installed {module} in addon lib directory")
                return True, f"Installed in addon lib directory: {module}", lib_dir
            else:
                error_msg = f"Failed to install {module}: {result.stderr}"
                print(error_msg)
                return False, error_msg, None
                
        except Exception as e:
            error_msg = f"Error during installation: {e}"
            print(error_msg)
            return False, error_msg, None

    @staticmethod
    def is_module_installed(module_name):
        """
        Verifica se un modulo è installato
        
        Args:
            module_name (str): Nome del modulo da verificare
            
        Returns:
            bool: True se il modulo è installato
        """
        try:
            spec = importlib.util.find_spec(module_name)
            return spec is not None
        except (ImportError, AttributeError, ValueError):
            return False

    @staticmethod
    def get_module_version(module_name):
        """
        Ottiene la versione di un modulo installato
        
        Args:
            module_name (str): Nome del modulo
            
        Returns:
            str: Versione del modulo o None se non trovato
        """
        try:
            import pkg_resources
            return pkg_resources.get_distribution(module_name).version
        except (ImportError, pkg_resources.DistributionNotFound):
            try:
                module = __import__(module_name)
                return getattr(module, '__version__', None)
            except ImportError:
                return None

    @staticmethod
    def list_installed_modules():
        """
        Elenca tutti i moduli installati
        
        Returns:
            list: Lista di moduli installati con formato "nome==versione"
        """
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'list'], 
                capture_output=True, 
                text=True,
                check=False
            )
            
            modules = []
            for line in result.stdout.split('\n')[2:]:  # Salta le prime due righe di intestazione
                parts = line.strip().split()
                if len(parts) >= 2:
                    modules.append(f"{parts[0]}=={parts[1]}")
            return modules
        except Exception as e:
            print(f"Error listing modules: {e}")
            return []

    @staticmethod
    def uninstall(module):
        """
        Disinstalla un modulo
        
        Args:
            module (str): Nome del modulo da disinstallare
            
        Returns:
            tuple: (bool success, str message)
        """
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'uninstall', '-y', module], 
                capture_output=True, 
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                print(f"Module {module} uninstalled successfully")
                return True, result.stdout
            else:
                print(f"Error uninstalling {module}: {result.stderr}")
                return False, result.stderr
        except Exception as e:
            print(f"Exception during uninstallation of {module}: {e}")
            return False, str(e)