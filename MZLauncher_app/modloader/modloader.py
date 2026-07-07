import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests
import minecraft_launcher_lib
import xml.etree.ElementTree as ET
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QHBoxLayout, QProgressBar, QMessageBox, QWidget, QPlainTextEdit, QDialogButtonBox
from PySide6.QtCore import Qt

from MZLauncher_app.settings.settings import get_minecraft_directory, get_appdata_path


def get_tmp_dir():
    tmp = get_appdata_path() / 'tmp'
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp


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

            quilt_installer_response = session.get('https://meta.quiltmc.org/v3/versions/installer', timeout=10)
            quilt_installer_response.raise_for_status()
            data['quilt'] = quilt_installer_response.json()

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
                subprocess.run(command, cwd=str(mc_dir_path), check=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win32') else 0)

            if self.loader == 'fabric':
                self.status.emit(self.lang.get('installing_fabric', 'Installing Fabric...'))
                self.progress.emit(50)
                minecraft_launcher_lib.fabric.install_fabric(self.mc_ver, self.mc_dir, self.loader_ver)
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
                run_java_installer(installer_path)
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
                run_java_installer(installer_path)
                installer_path.unlink(missing_ok=True)

            self.progress.emit(100)
            self.done.emit(self.lang.get('modloader_install_success', '{loader_name} {loader_ver} installed successfully!').format(loader_name=self.loader.capitalize(), loader_ver=self.loader_ver))
        except Exception as e:
            self.error.emit(str(e))


class ModLoaderDialog(QDialog):
    def __init__(self, parent=None, tr=None):
        super().__init__(parent)
        self.tr = tr if tr else {}
        self.setWindowTitle(self.tr.get('modloader_dialog_title', 'Install Mod Loader'))
        self.setMinimumSize(420, 280)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.fetched_data = {}
        layout = QVBoxLayout(self)
        self.status_label = QLabel('Loading modloader data...')
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.main_widget = QWidget()
        main_layout = QVBoxLayout(self.main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.loader_combo = QComboBox()
        self.loader_combo.addItems(['Fabric', 'Forge', 'NeoForge', 'Quilt'])
        self.mc_version_label = QLabel(self.tr.get('modloader_mc_version_label', 'Minecraft Version:'))
        self.mc_version_combo = QComboBox()
        self.loader_version_label = QLabel(self.tr.get('modloader_loader_version_label', 'Loader Version:'))
        self.loader_version_combo = QComboBox()
        main_layout.addWidget(QLabel(self.tr.get('modloader_loader_label', 'Mod Loader:')))
        main_layout.addWidget(self.loader_combo)
        main_layout.addWidget(self.mc_version_label)
        main_layout.addWidget(self.mc_version_combo)
        main_layout.addWidget(self.loader_version_label)
        self.loader_version_combo.setToolTip(self.tr.get('modloader_version_tooltip', 'Select the specific version of the mod loader.'))
        main_layout.addWidget(self.loader_version_combo)
        self.main_widget.hide()
        self.install_btn = QPushButton(self.tr.get('modloader_install_button', 'Install'))
        self.install_btn.setEnabled(False)
        self.install_btn.clicked.connect(self.install_loader)
        self.cancel_btn = QPushButton('Cancel')
        self.cancel_btn.clicked.connect(self.reject)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.install_btn)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.main_widget)
        layout.addStretch()
        layout.addLayout(button_layout)
        self.loader_combo.currentTextChanged.connect(self.on_loader_changed)
        self.mc_version_combo.currentTextChanged.connect(self.load_loader_versions)
        self.fetch_thread = modloaderf(self)
        self.fetch_thread.loaded.connect(self.on_data_loaded)
        self.fetch_thread.error.connect(self.on_fetch_error)
        self.fetch_thread.start()
        self.cancel_btn.setEnabled(False)

    def on_cancel(self):
        if hasattr(self, 'install_thread') and self.install_thread and self.install_thread.isRunning():
            return
        if self.fetch_thread and self.fetch_thread.isRunning():
            self.status_label.setText('Cancelling...')
            self.fetch_thread.requestInterruption()
            self.fetch_thread.quit()
            self.fetch_thread.wait()
        self.reject()

    def closeEvent(self, event):
        if (self.fetch_thread and self.fetch_thread.isRunning()) or (hasattr(self, 'install_thread') and self.install_thread and self.install_thread.isRunning()):
            self.on_cancel()
        event.accept()

    def on_data_loaded(self, data):
        self.fetch_thread.quit()
        self.fetch_thread.wait()
        self.fetched_data = data
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.status_label.setText(self.tr.get('modloader_select_versions', 'Select mod loader and versions'))
        self.install_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.main_widget.show()
        self.progress_bar.hide()
        self.status_label.hide()
        self.on_loader_changed()

    def on_fetch_error(self, msg):
        self.fetch_thread.quit()
        self.fetch_thread.wait()
        QMessageBox.critical(self, self.tr.get('network_error_title', 'Network Error'), self.tr.get('modloader_fetch_error', 'Could not fetch mod loader data:\n{msg}').format(msg=msg))
        self.reject()

    def install_loader(self):
        mc_dir = get_minecraft_directory()
        mc_ver = ''
        if self.loader_combo.currentText().lower() != 'quilt':
            mc_ver = self.mc_version_combo.currentText()
        loader_ver = self.loader_version_combo.currentData() or self.loader_version_combo.currentText()
        loader = self.loader_combo.currentText().lower()
        self.main_widget.setEnabled(False)
        self.install_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.status_label.show()
        self.progress_bar.show()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.install_thread = ModLoaderInstallThread(loader, mc_ver, loader_ver, mc_dir, self.tr)
        self.install_thread.status.connect(self.status_label.setText)
        self.install_thread.progress.connect(self.progress_bar.setValue)
        self.install_thread.done.connect(self.on_install_done)
        self.install_thread.error.connect(self.on_install_error)
        self.install_thread.start()

    def on_install_done(self, msg):
        QMessageBox.information(self, self.tr.get('success_title', 'Success'), msg)
        self.accept()

    def on_install_error(self, msg):
        QMessageBox.critical(self, self.tr.get('install_error_title', 'Installation Error'), msg)
        self.main_widget.setEnabled(True)
        self.install_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.status_label.hide()
        self.progress_bar.hide()

    def on_loader_changed(self):
        self.mc_version_combo.clear()
        self.loader_version_combo.clear()
        loader = self.loader_combo.currentText().lower()
        is_quilt = (loader == 'quilt')
        self.mc_version_label.setVisible(not is_quilt)
        self.mc_version_combo.setVisible(not is_quilt)
        if is_quilt:
            self.loader_version_label.setText(self.tr.get('modloader_installer_version_label', 'Installer Version:'))
        else:
            self.loader_version_label.setText(self.tr.get('modloader_loader_version_label', 'Loader Version:'))
        if not self.fetched_data:
            return
        mc_versions = []
        try:
            if loader == 'fabric':
                mc_versions = sorted([v['version'] for v in self.fetched_data['fabric']['game'] if v['stable']], key=lambda v: v, reverse=True)
            elif loader == 'forge':
                root = ET.fromstring(self.fetched_data[loader])
                versions_element = root.find('versioning/versions')
                if versions_element is not None:
                    all_versions = [v.text for v in versions_element.findall('version') if v.text]
                    mc_versions = sorted(list(set(v.split('-', 1)[0] for v in all_versions)), reverse=True)
            elif loader == 'neoforge':
                root = ET.fromstring(self.fetched_data[loader])
                versions_element = root.find('versioning/versions')
                if versions_element is not None:
                    mc_versions = [v.text for v in versions_element.findall('version') if v.text]
            if mc_versions:
                self.mc_version_combo.addItems(mc_versions)
        except Exception as e:
            print(f'Could not parse supported Minecraft versions for {loader.capitalize()}: {e}')
            QMessageBox.warning(self, self.tr.get('error_title', 'Error'), self.tr.get('modloader_parse_mc_version_error', 'Could not parse supported Minecraft versions for {loader_name}.').format(loader_name=loader.capitalize()))
        self.load_loader_versions(initial_load=True)

    def load_loader_versions(self, mc_version_text=None, initial_load=False):
        self.loader_version_combo.clear()
        loader = self.loader_combo.currentText().lower()
        mc_ver = self.mc_version_combo.currentText()
        if not self.fetched_data:
            return
        if loader != 'quilt' and not mc_ver:
            self.loader_version_combo.setEnabled(False)
            return
        versions = []
        try:
            if loader == 'fabric':
                is_valid_mc = any(g['version'] == mc_ver for g in self.fetched_data['fabric']['game'])
                if is_valid_mc:
                    versions = [v['version'] for v in self.fetched_data['fabric']['loader']]
            elif loader == 'quilt':
                versions = [v['version'] for v in self.fetched_data['quilt']]
            elif loader == 'forge':
                root = ET.fromstring(self.fetched_data[loader])
                forge_versions = [v.text for v in root.findall('versioning/versions/version') if v.text and v.text.startswith(mc_ver + '-')]
                versions = forge_versions
            elif loader == 'neoforge':
                root = ET.fromstring(self.fetched_data[loader])
                versions = [v.text for v in root.findall('versioning/versions/version') if v.text and v.text.startswith(mc_ver)]
            if not versions:
                self.loader_version_combo.addItem(self.tr.get('modloader_no_versions_available', 'No loader available'))
                self.loader_version_combo.setEnabled(False)
                return
            for v in versions:
                if loader == 'forge':
                    self.loader_version_combo.addItem(v.split('-', 1)[1], v)
                else:
                    self.loader_version_combo.addItem(v, v)
            self.loader_version_combo.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, self.tr.get('modloader_error_title', 'Loader Error'), self.tr.get('modloader_get_versions_error', 'Could not get loader versions for {mc_ver}:\n{e}').format(mc_ver=mc_ver, e=e))
            self.loader_version_combo.setEnabled(False)
