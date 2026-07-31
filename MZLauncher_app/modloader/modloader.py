import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests
import minecraft_launcher_lib
import xml.etree.ElementTree as ET
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtCore import Qt

from MZLauncher_app.settings.settings import get_minecraft_directory
from MZLauncher_app.core.utils import get_tmp_dir

class modloaderf(QThread):
    loaded = Signal(dict)
    error = Signal(str)

    def run(self):
        if self.isInterruptionRequested():
            return

        session = requests.Session()
        try:
            data = {}
            fabric_response = session.get('https://meta.fabricmc.net/v2/versions', timeout=10)
            fabric_response.raise_for_status()
            data['fabric'] = fabric_response.json()

            legacy_fabric_response = session.get('https://meta.legacyfabric.net/v2/versions', timeout=10)
            legacy_fabric_response.raise_for_status()
            data['legacy-fabric'] = legacy_fabric_response.json()

            quilt_installer_response = session.get('https://meta.quiltmc.org/v3/versions/installer', timeout=10)
            quilt_installer_response.raise_for_status()
            data['quilt'] = quilt_installer_response.json()

            quilt_game_response = session.get('https://meta.quiltmc.org/v3/versions/game', timeout=10)
            quilt_game_response.raise_for_status()
            data['quilt_game'] = quilt_game_response.json()

            neoforge_response = session.get('https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml', timeout=10)
            neoforge_response.raise_for_status()
            data['neoforge'] = neoforge_response.text

            forge_response = session.get('https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml', timeout=10)
            forge_response.raise_for_status()
            data['forge'] = forge_response.text

            self.loaded.emit(data)
        except requests.exceptions.RequestException as e:
            self.error.emit(f'Network error: {e}')
        except Exception as e:
            self.error.emit(f'An unexpected error occurred: {e}')
        finally:
            session.close()


class ModLoaderInstallThread(QThread):
    progress = Signal(int)
    status = Signal(str)
    done = Signal(str)
    error = Signal(str)
    java_not_found = Signal()

    def __init__(self, loader, mc_ver, loader_ver, mc_dir, tr=None, parent=None):
        super().__init__(parent)
        self.loader = loader
        self.mc_ver = mc_ver
        self.loader_ver = loader_ver
        self.mc_dir = mc_dir
        self.lang = tr if tr else {}

    def run(self):
        try:
            mc_dir_path = Path(self.mc_dir)
            tmp_dir = get_tmp_dir()
            java_path = 'javaw' if sys.platform.startswith('win32') else 'java'

            def run_java_installer(jar_path: Path, extra_args=None):
                if extra_args is None:
                    extra_args = []
                command = [java_path, '-jar', str(jar_path), *extra_args]
                try:
                    print(f"[ModLoader] Running installer command: {' '.join(command)}")
                    process = subprocess.run(command, cwd=str(mc_dir_path), check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win32') else 0)
                    return process
                except subprocess.CalledProcessError as e:
                    error_message = f"Installer failed with exit code {e.returncode}.\n"
                    error_message += f"STDOUT:\n{e.stdout}\n"
                    error_message += f"STDERR:\n{e.stderr}"
                    raise RuntimeError(error_message) from e
                except FileNotFoundError:
                    self.java_not_found.emit()
                    raise InterruptedError("Java not found")

            if self.loader == 'fabric':
                self.status.emit(self.lang.get('installing_fabric', 'Installing Fabric...'))
                self.progress.emit(50)
                minecraft_launcher_lib.fabric.install_fabric(self.mc_ver, self.mc_dir, self.loader_ver)
            elif self.loader == 'legacy-fabric':
                self.status.emit(self.lang.get('installing_legacy_fabric', 'Installing Legacy Fabric...'))
                self.progress.emit(50)
                
                meta_resp = requests.get('https://meta.legacyfabric.net/v2/versions', timeout=10)
                meta_resp.raise_for_status()
                meta_data = meta_resp.json()
                stable_installers = [v for v in meta_data.get('installer', []) if v.get('stable')]
                if not stable_installers:
                    raise ValueError("Could not find a stable Legacy Fabric installer.")
                
                latest_installer_version = stable_installers[0]['version']
                installer_url = f'https://maven.legacyfabric.net/net/legacyfabric/fabric-installer/{latest_installer_version}/fabric-installer-{latest_installer_version}.jar'
                installer_path = tmp_dir / f'legacy-fabric-installer-{latest_installer_version}.jar'
                
                r = requests.get(installer_url, stream=True)
                r.raise_for_status()
                with open(installer_path, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
                self.progress.emit(70)
                run_java_installer(installer_path, extra_args=["client", "-mcversion", self.mc_ver, "-loader", self.loader_ver])
                installer_path.unlink(missing_ok=True)
            elif self.loader == 'quilt':
                self.status.emit(self.lang.get('installing_quilt', 'Installing Quilt...'))
                self.progress.emit(10)
                new_repo_url = f'https://repo.maven.apache.org/maven2/org/quiltmc/quilt-installer/{self.loader_ver}/quilt-installer-{self.loader_ver}.jar'
                old_repo_url = f'https://maven.quiltmc.org/repository/release/org/quiltmc/quilt-installer/{self.loader_ver}/quilt-installer-{self.loader_ver}.jar'
                installer_urls = [new_repo_url, old_repo_url]
                installer_path = tmp_dir / f'quilt-installer-{self.loader_ver}.jar'

                downloaded = False
                for url in installer_urls:
                    try:
                        self.status.emit(self.lang.get('quilt_downloading_from', 'Trying to download from {server}...').format(server=url.split('/')[2]))
                        r = requests.get(url, stream=True, timeout=15)
                        if r.status_code == 200:
                            with open(installer_path, 'wb') as f:
                                shutil.copyfileobj(r.raw, f)
                            downloaded = True
                            break
                    except requests.RequestException:
                        continue
                if not downloaded:
                    raise FileNotFoundError(f'Could not download Quilt installer {self.loader_ver} from any known repository.')
                self.progress.emit(70)
                run_java_installer(installer_path)
            elif self.loader == 'forge':
                self.status.emit(self.lang.get('installing_forge', 'Installing Forge...'))
                self.progress.emit(30)
                installer_url = f'https://maven.minecraftforge.net/net/minecraftforge/forge/{self.loader_ver}/forge-{self.loader_ver}-installer.jar'
                installer_path = tmp_dir / f'forge-{self.loader_ver}-installer.jar'
                r = requests.get(installer_url, stream=True)
                r.raise_for_status()
                with open(installer_path, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
                self.progress.emit(70)
                process = run_java_installer(installer_path)
                installer_path.unlink(missing_ok=True)
            elif self.loader == 'neoforge':
                self.status.emit(self.lang.get('installing_neoforge_download', 'Downloading NeoForge installer...'))
                self.progress.emit(30)
                installer_url = f'https://maven.neoforged.net/releases/net/neoforged/neoforge/{self.loader_ver}/neoforge-{self.loader_ver}-installer.jar'
                installer_path = tmp_dir / f'neoforge-{self.loader_ver}-installer.jar'
                r = requests.get(installer_url, stream=True)
                r.raise_for_status()
                with open(installer_path, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
                self.status.emit(self.lang.get('installing_neoforge_install', 'Installing NeoForge...'))
                self.progress.emit(70)
                process = run_java_installer(installer_path)
                installer_path.unlink(missing_ok=True)

            self.progress.emit(100)
            self.done.emit(self.lang.get('modloader_install_success', '{loader_name} {loader_ver} installed successfully!').format(loader_name=self.loader.capitalize(), loader_ver=self.loader_ver))
        except subprocess.CalledProcessError as e:
            error_output = f"Installer Error:\n{e.stderr or e.stdout or 'No output from installer.'}"
            self.error.emit(error_output)
        except InterruptedError:
            pass
        except Exception as e:
            self.error.emit(str(e))
