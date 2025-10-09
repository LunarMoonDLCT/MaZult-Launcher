import os
import sys
import shutil
import json
import webbrowser
import subprocess
import psutil
import requests
import tempfile
import zipfile
import time
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFrame, QDialog, QListView, QAbstractItemView, QCheckBox, QMessageBox,
    QTabWidget, QSlider, QScrollArea, QListWidget, QListWidgetItem, QInputDialog, QDialogButtonBox,
    QGroupBox, QPlainTextEdit, QProgressBar, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsRectItem, QGraphicsItem, QFileDialog
)
from PySide6.QtGui import (
    QPixmap, QIcon, QStandardItemModel, QStandardItem, QFont, QPainter, QColor, QImage,
    QPen, QMouseEvent, QBrush
)
from PySide6.QtCore import (
    Qt, QTimer, QSize, Signal, QThread, QObject, QUrl, QRect, QRectF, QPointF
)
import minecraft_launcher_lib
import datetime
import uuid
from pypresence import Presence
from pypresence.exceptions import InvalidID, PipeClosed
from packaging import version as packaging


LAUNCHER_VERSION = "1.105.27.9"
GITHUB_API_URL = "https://api.github.com/repos/LunarMoonDLCT/MaZult-Launcher/releases/latest"
DISCORD_CLIENT_ID = "1410269369748946986"

class UpdateChecker(QObject):
    update_available = Signal(str, str)
    finished = Signal()

    def __init__(self, current_version, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.latest_version_tag = None
        self.download_url = None

    def run(self):
        try:
            response = requests.get(GITHUB_API_URL, timeout=10)
            if response.status_code == 200:
                release_info = response.json()
                latest_version_tag = release_info.get("tag_name")

                universal_asset = None
                for asset in release_info.get("assets", []):
                    if "Universal.zip" in asset.get("name", ""):
                        universal_asset = asset
                        break
                
                if latest_version_tag and universal_asset:
                    latest_version = packaging.version.parse(latest_version_tag)
                    current_version_parsed = packaging.version.parse(self.current_version)

                    if latest_version > current_version_parsed:
                        self.latest_version_tag = latest_version_tag
                        self.download_url = universal_asset["browser_download_url"]
                        self.update_available.emit(self.latest_version_tag, self.download_url)
            else:
                print(f"Failed to fetch GitHub releases: Status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Network error while checking for updates: {e}")
        finally:
            self.finished.emit()

def get_appdata_path():
    if sys.platform.startswith('win32'):
        return Path(os.getenv("APPDATA")) / ".mazultlauncher"
    elif sys.platform.startswith('linux'):
        return Path.home() / ".mazultlauncher"
    elif sys.platform.startswith('darwin'):
        return Path.home() / "Library" / "Application Support" / ".mazultlauncher"
    else:
        return Path.home() / ".mazultlauncher"

def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
            
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

VERSION_FILE = get_appdata_path() / "versions.json"
VERSION_API = "https://launchermeta.mojang.com/mc/game/version_manifest.json"

class CropBox(QGraphicsRectItem):
    def __init__(self, rect):
        super().__init__(rect)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setPen(QPen(Qt.green, 2))
        self.setBrush(QBrush(QColor(0, 255, 0, 40)))

SETTINGS_FILE = get_appdata_path() / "settings.json"
USERS_FILE = get_appdata_path() / "users.json"

def save_settings(username=None, version_id=None, ram_mb=None, mc_dir=None, filters=None, dev_console=None, hide_on_launch=None, jvm_args=None, discord_rpc=None):
    data = load_settings()
    if username is not None:
        data["username"] = username
    if version_id is not None:
        data["version_id"] = version_id
    if ram_mb is not None:
        data["ram_mb"] = ram_mb
    if mc_dir is not None:
        data["minecraft_directory"] = str(mc_dir)
    if filters is not None:
        data["filters"] = filters
    if dev_console is not None:
        data["dev_console"] = dev_console
    if hide_on_launch is not None:
        data["hide_on_launch"] = hide_on_launch
    if jvm_args is not None:
        data["jvm_args"] = jvm_args
    if discord_rpc is not None:
        data["discord_rpc"] = discord_rpc

        
    os.makedirs(get_appdata_path(), exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "filters": {
            "release": True,
            "snapshot": False,
            "beta": False,
            "alpha": False,
            "installed": True
        },
        "window_width": 925, 
        "window_height": 530,
        "dev_console": False,
        "hide_on_launch": True,
        "jvm_args": [],
        "discord_rpc": True
    }

def save_users(users):
    os.makedirs(get_appdata_path(), exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return [""]

def get_minecraft_directory():
    settings = load_settings()
    if "minecraft_directory" in settings:
        return Path(settings["minecraft_directory"])
    
    if sys.platform.startswith('win32'):
        return Path(os.getenv('APPDATA')) / '.minecraft'
    elif sys.platform.startswith('linux'):
        return Path.home() / '.minecraft'
    elif sys.platform.startswith('darwin'):
        return Path.home() / 'Library' / 'Application Support' / 'minecraft'
    else:
        return Path.home() / 'minecraft'

def get_installed_versions():
    installed_versions = []
    versions_dir = get_minecraft_directory() / "versions"
    if os.path.exists(versions_dir):
        for folder_name in os.listdir(versions_dir):
            if os.path.isdir(os.path.join(versions_dir, folder_name)) and \
               os.path.exists(os.path.join(versions_dir, folder_name, f"{folder_name}.json")):
                installed_versions.append(folder_name)
    
    def sort_key(v):
        try:
            if v and v[0].isdigit():
                parts = v.split('.')
                return tuple(int(part) if part.isdigit() else 0 for part in parts)
            else:
                return (0, 0, 0)
        except (ValueError, IndexError):
            return (0, 0, 0)
    
    return sorted(installed_versions, key=sort_key, reverse=True)

def get_available_versions(filters, offline=False):
    versions = []
    latest_release_id = None
    try:
        if offline:
            raise Exception("Forced offline")
        mc_versions = minecraft_launcher_lib.utils.get_version_list()
        serializable_versions = []
        

        for v in mc_versions:
            if v.get('type') == 'release' and latest_release_id is None:
                
                latest_release_id = v['id']        
        
        
            if isinstance(v.get('releaseTime'), datetime.datetime):
                v['releaseTime'] = v['releaseTime'].isoformat()
            serializable_versions.append(v)
            
        with open(VERSION_FILE, "w") as f:
            json.dump(serializable_versions, f)

    except Exception as e:
        print("Offline or error fetching versions:", e)
        if os.path.exists(VERSION_FILE):
            try:
                with open(VERSION_FILE, "r") as f:
                    mc_versions = json.load(f)
                    
                
                for v in mc_versions:
                    if v.get('type') == 'release' and latest_release_id is None:
                        latest_release_id = v['id']
            except Exception:
                return [("Offline: No cached versions", "")], None 
        else:
            return [("Offline: No cached versions", "")], None 


    filtered_versions = []
    version_types = {
        "release": filters.get("release", True),
        "snapshot": filters.get("snapshot", False),
        "old_beta": filters.get("beta", False),
        "old_alpha": filters.get("alpha", False),
    }

    for v in mc_versions:
        if version_types.get(v.get('type', 'release'), False):
            label = f"{v.get('type', 'release').capitalize()} - {v['id']}"
            filtered_versions.append((label, v['id']))
    
    return filtered_versions, latest_release_id

def get_mojang_uuid(username):
    try:
        url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()['id']
        else:
            print(f"Error fetching Mojang UUID for {username}: Status code {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Network error while fetching Mojang UUID: {e}")
        return None

class SettingsDialog(QDialog):
    refreshVersions = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Launcher Settings")
        self.setMinimumSize(400, 300)

        tabs = QTabWidget()

        general_tab = QWidget()
        general_layout = QVBoxLayout()
        
        mc_dir_layout = QHBoxLayout()
        mc_dir_label = QLabel("Minecraft Directory:")
        self.mc_dir_input = QLineEdit()
        self.mc_dir_input.setText(str(get_minecraft_directory()))
        self.mc_dir_browse_btn = QPushButton("Browse")
        self.mc_dir_browse_btn.clicked.connect(self.browse_mc_dir)
        mc_dir_layout.addWidget(mc_dir_label)
        mc_dir_layout.addWidget(self.mc_dir_input)
        mc_dir_layout.addWidget(self.mc_dir_browse_btn)
        general_layout.addLayout(mc_dir_layout)
        
        settings = load_settings()

        ram_groupbox = QGroupBox("RAM Allocation")
        ram_layout = QVBoxLayout()
        self.ram_slider = QSlider(Qt.Horizontal)
        self.ram_slider.setMinimum(520)
        self.ram_slider.setMaximum(psutil.virtual_memory().total // (1024 * 1024) - 512)
        self.ram_slider.setSingleStep(520)
        ram_mb = settings.get("ram_mb", 2048)
        self.ram_slider.setValue(ram_mb)
        self.ram_label = QLabel()
        self.update_ram_label(self.ram_slider.value())
        self.ram_slider.valueChanged.connect(self.update_ram_label)
        ram_layout.addWidget(self.ram_label)
        ram_layout.addWidget(self.ram_slider)
        ram_groupbox.setLayout(ram_layout)
        general_layout.addWidget(ram_groupbox)

        jvm_groupbox = QGroupBox("JVM Arguments")
        jvm_layout = QVBoxLayout()
        self.jvm_text_edit = QPlainTextEdit()
        self.jvm_text_edit.setPlaceholderText("")
        jvm_layout.addWidget(self.jvm_text_edit)
        jvm_groupbox.setLayout(jvm_layout)
        general_layout.addWidget(jvm_groupbox)

        jvm_args_str = " ".join(settings.get("jvm_args", []))
        self.jvm_text_edit.setPlainText(jvm_args_str)

        filter_groupbox = QGroupBox("Filter Versions")
        filter_layout = QVBoxLayout()
        self.release_checkbox = QCheckBox("Release")
        self.snapshot_checkbox = QCheckBox("Snapshot")
        self.beta_checkbox = QCheckBox("Beta")
        self.alpha_checkbox = QCheckBox("Alpha")
        self.installed_checkbox = QCheckBox("Installed Versions")

        current_filters = settings.get("filters", {})
        self.release_checkbox.setChecked(current_filters.get("release", True))
        self.snapshot_checkbox.setChecked(current_filters.get("snapshot", False))
        self.beta_checkbox.setChecked(current_filters.get("beta", False))
        self.alpha_checkbox.setChecked(current_filters.get("alpha", False))
        self.installed_checkbox.setChecked(current_filters.get("installed", True))
        
        filter_layout.addWidget(self.release_checkbox)
        filter_layout.addWidget(self.snapshot_checkbox)
        filter_layout.addWidget(self.beta_checkbox)
        filter_layout.addWidget(self.alpha_checkbox)
        filter_layout.addWidget(self.installed_checkbox)
        filter_groupbox.setLayout(filter_layout)
        general_layout.addWidget(filter_groupbox)

        general_tab.setLayout(general_layout)

        dev_tab = QWidget()
        dev_layout = QVBoxLayout()
        
        self.dev_console_checkbox = QCheckBox("Dev Console")
        self.dev_console_checkbox.setChecked(settings.get("dev_console", False))
        dev_layout.addWidget(self.dev_console_checkbox)

        self.hide_on_launch_checkbox = QCheckBox("Don't hide launcher when running Minecraft")
        self.hide_on_launch_checkbox.setChecked(not settings.get("hide_on_launch", True))
        dev_layout.addWidget(self.hide_on_launch_checkbox)

        self.discord_rpc_checkbox = QCheckBox("Show status launcher in Discord")
        self.discord_rpc_checkbox.setChecked(settings.get("discord_rpc", True))
        dev_layout.addWidget(self.discord_rpc_checkbox)

        dev_layout.addStretch()
        dev_tab.setLayout(dev_layout)
        
        about_tab = QWidget()
        about_layout = QVBoxLayout()
        
        launcher_name_label = QLabel("MaZult Launcher")
        launcher_name_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        launcher_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(launcher_name_label)

        creator_label = QLabel("Creator: LunarMoon")
        creator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(creator_label)
        
        about_layout.addSpacing(20)

        libraries_title = QLabel("Third-Party Libraries:")
        libraries_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        about_layout.addWidget(libraries_title)
        
        libraries_list = QListWidget()
        libraries_list.setStyleSheet("background-color: #2D2D2D; border: none;")
        libraries_list.setFocusPolicy(Qt.NoFocus)
        libraries_list.addItem("• PySide6 - Qt for Python")
        libraries_list.addItem("• minecraft-launcher-lib")
        libraries_list.addItem("• requests")
        libraries_list.addItem("• psutil")
        libraries_list.addItem("• packaging")
        libraries_list.addItem("• pypresence")
        libraries_list.setMinimumHeight(120)
        about_layout.addWidget(libraries_list)

        source_code_title = QLabel("Source Code Launcher:")
        source_code_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        about_layout.addWidget(source_code_title)

        self.source_code_button = QPushButton("Open GitHub Repository")
        self.source_code_button.clicked.connect(self.open_github_link)
        about_layout.addWidget(self.source_code_button)

        about_layout.addStretch()
        about_tab.setLayout(about_layout)


        tabs.addTab(general_tab, "General")
        tabs.addTab(dev_tab, "Launcher Setting")
        tabs.addTab(about_tab, "About Launcher")

        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_and_close)

        layout = QVBoxLayout()
        layout.addWidget(tabs)
        layout.addWidget(save_button)
        self.setLayout(layout)

    def save_and_close(self):
        old_settings = load_settings()
        
        ram_mb = self.ram_slider.value()
        
        mc_dir = self.mc_dir_input.text().strip()
        if mc_dir:
            mc_path = Path(mc_dir)
            if not mc_path.exists():
                try:
                    os.makedirs(mc_path)
                    print(f"Created new Minecraft directory: {mc_path}")
                except Exception as e:
                    QMessageBox.critical(self, "Creation Failed", f"Failed to create directory: {mc_dir}\nError: {e}")
                    return
        else:
            QMessageBox.warning(self, "Invalid Path", "Minecraft directory path cannot be empty.")
            return
        
        filters = {
            "release": self.release_checkbox.isChecked(),
            "snapshot": self.snapshot_checkbox.isChecked(),
            "beta": self.beta_checkbox.isChecked(),
            "alpha": self.alpha_checkbox.isChecked(),
            "installed": self.installed_checkbox.isChecked(),
        }
        

        
        dev_console_enabled = self.dev_console_checkbox.isChecked()
        hide_on_launch = not self.hide_on_launch_checkbox.isChecked()
        jvm_args = self.jvm_text_edit.toPlainText().strip().split()
        discord_rpc_enabled = self.discord_rpc_checkbox.isChecked()

        save_settings(
            ram_mb=ram_mb, 
            mc_dir=mc_dir, 
            filters=filters, 
            dev_console=dev_console_enabled, 
            hide_on_launch=hide_on_launch, 
            jvm_args=jvm_args,

            discord_rpc=discord_rpc_enabled
        )
        
        if dev_console_enabled and self.parent().dev_console.isHidden():
            self.parent().dev_console.show()
        elif not dev_console_enabled and self.parent().dev_console.isVisible():
            self.parent().dev_console.hide()

        if old_settings.get("discord_rpc") != discord_rpc_enabled:
            self.parent().reconnect_rpc()

        self.refreshVersions.emit()
        self.accept()
        
    def open_github_link(self):
        webbrowser.open("https://github.com/LunarMoonDLCT/MaZult-Launcher")

    def update_ram_label(self, value):
        self.ram_label.setText(f"Allocated RAM: {value} MB")

    def browse_mc_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Minecraft Directory")
        if dir_path:
            self.mc_dir_input.setText(dir_path)

class UserManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Users | Manager Users")
        self.setFixedSize(350, 400)
        self.users = load_users()
        self.parent_window = parent

        layout = QVBoxLayout(self)

        self.user_list = QListWidget()
        self.update_list()
        layout.addWidget(self.user_list)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+")
        self.add_btn.clicked.connect(self.add_user)
        self.edit_btn = QPushButton("✎")
        self.edit_btn.clicked.connect(self.edit_user)
        self.delete_btn = QPushButton("-")
        self.delete_btn.clicked.connect(self.delete_user)
        self.select_btn = QPushButton("Select")
        self.select_btn.clicked.connect(self.select_user)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.select_btn)
        
        layout.addLayout(btn_layout)

    def update_list(self):
        self.user_list.clear()
        for user in self.users:
            self.user_list.addItem(user)
    
    def add_user(self):
        text, ok = QInputDialog.getText(self, "Add User", "Enter new username:")
        if ok and text and text not in self.users:
            self.users.append(text)
            save_users(self.users)
            self.update_list()
            
    def edit_user(self):
        selected = self.user_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a user to edit.")
            return
        
        old_username = selected.text()
        text, ok = QInputDialog.getText(self, "Edit User", "Edit username:", QLineEdit.Normal, old_username)
        if ok and text and text != old_username and text not in self.users:
            index = self.users.index(old_username)
            self.users[index] = text
            save_users(self.users)
            self.update_list()

    def delete_user(self):
        selected = self.user_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a user to delete.")
            return

        username = selected.text()
        if len(self.users) <= 1:
            QMessageBox.warning(self, "Cannot Delete", "You must have at least one user.")
            return

        reply = QMessageBox.question(self, "Delete User", f"Are you sure you want to delete '{username}'?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.users.remove(username)
            save_users(self.users)
            self.update_list()

    def select_user(self):
        selected = self.user_list.currentItem()
        if selected:
            self.parent_window.username_combo.setCurrentText(selected.text())
            self.accept()
        else:
            QMessageBox.warning(self, "No Selection", "Please select a user.")

class DevConsole(QWidget):
    def __init__(self, parent_launcher, styles=""):
        super().__init__()
        self.parent_launcher = parent_launcher
        self.setWindowTitle("Developer Console")
        self.setMinimumSize(700, 400)
        
        self.setStyleSheet(styles)
        
        self.layout = QVBoxLayout(self)
        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setStyleSheet("background-color: #000; color: #fff;")
        self.layout.addWidget(self.console_output)
        
        button_layout = QHBoxLayout()
        self.kill_button = QPushButton("Kill Minecraft")
        self.kill_button.setEnabled(False)
        self.kill_button.clicked.connect(self.kill_minecraft_process)
        button_layout.addWidget(self.kill_button)
        self.layout.addLayout(button_layout)
        
        sys.stdout = self
        
    def write(self, text):
        if self.console_output and not self.console_output.parent() is None:
            self.console_output.appendPlainText(text)
    
    def flush(self):
        pass
        
    def set_kill_button_enabled(self, enabled):
        if self.kill_button and not self.kill_button.parent() is None:
            self.kill_button.setEnabled(enabled)

    def kill_minecraft_process(self):
        if self.parent_launcher.minecraft_thread and self.parent_launcher.minecraft_thread.process:
            try:
                self.parent_launcher.minecraft_thread.process.kill()
                self.parent_launcher.minecraft_thread.process.wait()
                print("Minecraft process killed.")
                self.set_kill_button_enabled(False)
                if self.parent_launcher.isHidden():
                    self.parent_launcher.show()
            except Exception as e:
                print(f"Failed to kill Minecraft process: {e}")

    def closeEvent(self, event):
        save_settings(dev_console=False)
        self.hide()
        event.ignore()

class MinecraftThread(QThread):
    finished_signal = Signal()
    log_signal = Signal(str)

    def __init__(self, command, minecraft_directory, parent=None):
        super().__init__(parent)
        self.command = command
        self.minecraft_directory = minecraft_directory
        self.process = None

    def run(self):
        try:
            if sys.platform.startswith('win32'):
                java_exe_path = self.command[0]
                java_w_exe_path = java_exe_path.replace('java.exe', 'javaw.exe')
                if os.path.exists(java_w_exe_path):
                    self.command[0] = java_w_exe_path
                    
            self.process = subprocess.Popen(
                self.command,
                cwd=self.minecraft_directory,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win32') else 0,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding='utf-8'
            )
            for line in iter(self.process.stdout.readline, ''):
                self.log_signal.emit(line.strip())
            self.process.wait()
        except Exception as e:
            self.log_signal.emit(f"Error launching Minecraft: {e}")
        
        self.finished_signal.emit()

class MaZultLauncher(QWidget):
    def closeEvent(self, event):
        if self.dev_console.isVisible():
            self.dev_console.close()
        
        if self.rpc:
            try:
                self.rpc.close()
                print("Disconnected from Discord RPC.")
            except Exception as e:
                print(f"Error while closing Discord RPC: {e}")

        event.accept()

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.refreshVersions.connect(self.load_versions)
        dialog.exec()

    def update_username_combo(self):
        self.username_combo.clear()
        self.users = load_users()
        self.username_combo.addItems(self.users)
        self.username_combo.addItem("Manage Users...")

        settings = load_settings()
        if "username" in settings and settings["username"] in self.users:
            self.username_combo.setCurrentText(settings["username"])
        else:
            if self.users:
                self.username_combo.setCurrentText(self.users[0])
    
    def on_username_changed(self, text):
        if text == "Manage Users...":
            dialog = UserManagerDialog(self)
            dialog.exec_()
            self.update_username_combo()
        else:
            save_settings(username=text)

    def on_version_changed(self, index):
        selected_version_id = self.version_combo.itemData(index)
        if selected_version_id:
            save_settings(version_id=selected_version_id)
            if self.rpc:
                self.update_rpc_menu()

    def install_legacy_forge(self, version_id):
        mc_dir = get_minecraft_directory()
        installer_url = "https://maven.minecraftforge.net/net/minecraftforge/forge/1.7.10-10.13.4.1614-1.7.10/forge-1.7.10-10.13.4.1614-1.7.10-installer.jar"
        installer_path = get_appdata_path() / "forge_installer_1.7.10.jar"
        version_folder = mc_dir / "versions" / version_id

        try:
            if not os.path.exists(installer_path):
                r = requests.get(installer_url, stream=True, timeout=30)
                if r.status_code == 200:
                    with open(installer_path, "wb") as f:
                        shutil.copyfileobj(r.raw, f)
                    print("Forge 1.7.10 installer downloaded.")
                else:
                    QMessageBox.warning(self, "Download Failed", "Could not download Forge 1.7.10 installer.")
                    return

            try:
                subprocess.run(["javaw", "-version"], capture_output=True, check=True)
            except Exception:
                QMessageBox.critical(self, "Java Missing", "Java is required to install Forge 1.7.10. Please install Java and add it to PATH.")
                return

            subprocess.run(["javaw", "-jar", installer_path, "--installClient"], cwd=mc_dir, creationflags=subprocess.CREATE_NO_WINDOW)

            if not os.path.exists(version_folder):
                QMessageBox.warning(self, "Installation Failed", f"Forge version folder '{version_id}' was not created.")
                return

            jar_path = version_folder / f"{version_id}.jar"
            json_path = version_folder / f"{version_id}.json"

            if not os.path.exists(jar_path) or not os.path.exists(json_path):
                base_version = "1.7.10"
                base_jar = mc_dir / "versions" / base_version / f"{base_version}.jar"
                if os.path.exists(base_jar):
                    shutil.copy(base_jar, jar_path)
                    print("Base jar copied to Forge folder.")
                else:
                    QMessageBox.warning(self, "Missing Base Version", "Minecraft 1.7.10 is not installed. Please install it first.")
                    return

            self.ensure_launcher_profile_exists(version_id)

            username = self.username_combo.currentText()
            user_uuid = str(uuid.uuid3(uuid.NAMESPACE_URL, "OfflinePlayer:" + username))
            user_token = user_uuid
            
            options = {
                "username": username,
                "uuid": user_uuid,
                "token": user_token
            }
            command = minecraft_launcher_lib.command.get_minecraft_command(version_id, mc_dir, options)
            self.hide()
            self.mc_process = subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win32') else 0)
            self.mc_process.wait()
            self.show()
            self.mc_process = None

        except Exception as e:
            QMessageBox.critical(self, "Forge Install Failed", f"Failed to install Forge 1.7.10:\n{e}")

    def fix_forge_missing_jar(self, version_id):
        mc_dir = get_minecraft_directory()
        forge_dir = mc_dir / "versions" / version_id
        forge_jar = forge_dir / f"{version_id}.jar"

        if not os.path.exists(forge_jar):
            base_version = version_id.split('-')[0]
            vanilla_jar = mc_dir / "versions" / base_version / f"{base_version}.jar"

            if os.path.exists(vanilla_jar):
                os.makedirs(forge_dir, exist_ok=True)
                shutil.copy(vanilla_jar, forge_jar)
                print(f"Copied {base_version}.jar to Forge folder as {version_id}.jar")
            else:
                QMessageBox.warning(self, "Missing base version",
                                f"The base version {base_version} is not installed. Please install it first using your launcher.")
    
    def ensure_launcher_profile_exists(self, version_id):
        mc_dir = get_minecraft_directory()
        profile_path = mc_dir / "launcher_profiles.json"

        if os.path.exists(profile_path):
            try:
                with open(profile_path, "r") as f:
                    data = json.load(f)
                return
            except json.JSONDecodeError:
                print("Corrupted launcher_profiles.json, regenerating...")

        data = {
            "profiles": {
                "forge": {
                    "name": "Forge",
                    "lastVersionId": version_id,
                    "type": "custom"
                }
            },
            "selectedProfile": "forge",
            "clientToken": "12345678-1234-1234-1234-123456789abc",
            "launcherVersion": {
                "name": "custom-launcher",
                "format": 21
            }
        }

        with open(profile_path, "w") as f:
            json.dump(data, f, indent=4)
        print("Created default launcher_profiles.json for Forge.")

    def install_and_launch_forge(self, username, version_id):
        minecraft_directory = get_minecraft_directory()
        user_uuid = str(uuid.uuid3(uuid.NAMESPACE_URL, "OfflinePlayer:" + username))
        user_token = user_uuid
        options = {
            "username": username,
            "uuid": user_uuid,
            "token": user_token
        }

        try:
            print(f"Installing Forge for Minecraft version: {version_id}")
            minecraft_launcher_lib.forge.install_forge(version_id, minecraft_directory)
        except AttributeError as e:
            if "install_forge" in str(e) and "1.7.10" in version_id:
                self.install_legacy_forge(version_id)
                return
            else:
                QMessageBox.warning(self, "Unsupported Forge", f"Automatic installation not supported for Forge {version_id}. Please install it manually from the Forge website.")
                self.ensure_launcher_profile_exists(version_id)
            return

        self.ensure_launcher_profile_exists(version_id)
        self.fix_forge_missing_jar(version_id)

        try:
            command = minecraft_launcher_lib.command.get_minecraft_command(version_id, minecraft_directory, options)
            self.hide()
            self.mc_process = subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win32') else 0)
            self.mc_process.wait()
            self.show()
            self.mc_process = None
        except Exception as e:
            print(f"Failed to launch Forge: {e}")

    def __init__(self, update_info=None):
        super().__init__()
        self.appdata_dir = get_appdata_path()
        self.icon_path = resource_path("icon.ico")
        self.mc_process = None
        self.minecraft_thread = None
        self.download_thread = None
        self.update_info = update_info



        self.dev_console = DevConsole(self, styles=self.load_styles())
        if load_settings().get("dev_console", False):
            self.dev_console.show()

        self.rpc = None

        self.setWindowTitle("MaZult Launcher")
        self.setWindowIcon(QIcon(str(self.icon_path)))
        self.setMinimumSize(900, 520)
        self.setStyleSheet(self.load_styles())
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.temp_width = 0
        self.temp_height = 0



        sidebar = QVBoxLayout()
        sidebar.setAlignment(Qt.AlignmentFlag.AlignTop)
        sidebar.setSpacing(20)
        sidebar.setContentsMargins(20, 20, 20, 20)
        
        username_label = QLabel("Username:")
        self.username_combo = QComboBox()
        self.username_combo.currentTextChanged.connect(self.on_username_changed)
        self.update_username_combo()
        
        sidebar.addWidget(username_label)
        sidebar.addWidget(self.username_combo)
        
        self.update_button = QPushButton("Update Launcher")
        self.update_button.clicked.connect(self.on_update_clicked)
        self.update_button.setVisible(False)
        self.update_button.setStyleSheet("background-color: #e74c3c; color: white; border: none; font-weight: bold; font-size: 14px; border-radius: 4px;")
        
        if self.update_info:
            self.update_button.setVisible(True)

        sidebar.addWidget(self.update_button)

        self.settings_button_left = QPushButton("Settings")
        self.settings_button_left.setFixedSize(160, 40)
        self.settings_button_left.clicked.connect(self.open_settings_dialog)
        self.settings_button_left.setStyleSheet("text-align: left; padding: 10px; background-color: #353535; border: 1px solid #404040;")
        sidebar.addStretch()
        sidebar.addWidget(self.settings_button_left, alignment=Qt.AlignmentFlag.AlignBottom)
        
        sidebar_frame = QFrame()
        sidebar_frame.setLayout(sidebar)
        sidebar_frame.setFixedWidth(200)
        sidebar_frame.setStyleSheet("background-color: #252525; border-right: 1px solid #404040;")
        main_layout.addWidget(sidebar_frame)
        
        content_layout = QVBoxLayout()
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        header_layout = QHBoxLayout()
        title = QLabel("Minecraft")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        refresh_button = QPushButton("↻")
        refresh_button.setFixedSize(30, 30)
        refresh_button.setStyleSheet("font-size: 16px; font-weight: bold;")
        refresh_button.clicked.connect(self.load_versions)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(refresh_button)
        content_layout.addLayout(header_layout)

        version_label = QLabel("Select Version:")
        self.version_combo = QComboBox()
        self.version_combo.currentIndexChanged.connect(self.on_version_changed)
        self.load_versions()
        content_layout.addWidget(version_label)
        content_layout.addWidget(self.version_combo)
        
        content_layout.addStretch()

        self.progress_label = QLabel()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        self.progress_label.hide()
        self.progress_bar.hide()
        content_layout.addWidget(self.progress_label)
        content_layout.addWidget(self.progress_bar)


        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("playButton")
        self.play_button.setStyleSheet(self.load_styles())
        self.play_button.clicked.connect(self.on_play_clicked)
        self.is_downloading = False

        content_layout.addWidget(self.play_button)
        
        main_layout.addLayout(content_layout)

        self.connect_rpc()

    def reconnect_rpc(self):
        if self.rpc:
            try:
                self.rpc.close()
                print("Disconnected from Discord RPC.")
            except Exception as e:
                print(f"Error while closing Discord RPC: {e}")
        self.rpc = None
        self.connect_rpc()

    def connect_rpc(self):
        settings = load_settings()
        if not settings.get("discord_rpc", True):
            print("Discord RPC is disabled in settings.")
            self.rpc = None
            return

        try:
            self.rpc = Presence(DISCORD_CLIENT_ID)
            self.rpc.connect()
            print("Connected to Discord RPC.")
            self.update_rpc_menu()
        except InvalidID:
            print("Invalid Client ID for Discord RPC. Please check your settings.")
            self.rpc = None
        except Exception as e:
            print(f"Failed to connect to Discord RPC: {e}")
            self.rpc = None

    def update_rpc_menu(self):
        if self.rpc:
            try:
                selected_version = self.version_combo.currentText().replace("(Installed) ", "")
                self.rpc.update(
                    #state=f"",
                    details="In the menu",
                    large_image="mzlauncher",
                    large_text="MaZult Launcher",
                    small_image="nothing",
                    small_text="MaZult Launcher",
                    start=int(time.time())
                )
            except PipeClosed:
                print("Discord pipe closed. Reconnecting...")
                self.connect_rpc()

    def update_rpc_downloading(self, version_id):
        if self.rpc:
            try:
                self.rpc.update(
                    state=f"Launching Minecraft {version_id}",
                    details="Launching...",
                    large_image="mzlauncher",
                    large_text="MaZult Launcher",
                    small_image="nothing",
                    small_text="MaZult Launcher",
                    start=int(time.time())
                )
            except PipeClosed:
                print("Discord pipe closed. Reconnecting...")
                self.connect_rpc()

    def update_rpc_game(self, version_id):
        if self.rpc:
            try:
                self.rpc.update(
                    state=f"Playing Minecraft {version_id}",
                    details="In game",
                    large_image="mzlauncher",
                    large_text=f"Minecraft {version_id}",
                    small_image="logo",
                    small_text="MaZult Launcher",
                    start=int(time.time())
                )
            except PipeClosed:
                print("Discord pipe closed. Reconnecting...")
                self.connect_rpc()


    def on_update_clicked(self):
        if self.update_info:
            latest_version, download_url = self.update_info
            reply = QMessageBox.question(self, "Update Available",
                                         f"A new version is available: {latest_version}. Do you want to download the update?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                webbrowser.open(download_url)
                self.close()
                QApplication.instance().quit()

    def on_minecraft_finished(self):
        if self.play_button and not self.play_button.parent() is None:
            self.play_button.setText("Play")
            self.play_button.setEnabled(True)
            self.play_button.setStyleSheet(self.load_styles())
            self.dev_console.set_kill_button_enabled(False)
            self.mc_process = None
            self.minecraft_thread = None
            settings = load_settings()
            hide_on_launch = settings.get("hide_on_launch", True)
            if hide_on_launch:
                self.show()
                if self.temp_width > self.minimumWidth() and self.temp_height > self.minimumHeight():
                    self.resize(self.temp_width, self.temp_height)
            self.update_rpc_menu()

    def on_minecraft_log(self, text):
        self.dev_console.write(text)

    def load_versions(self):
        self.version_combo.clear()
        
        settings = load_settings()
        current_version = settings.get("version_id")
        
        filters = settings.get("filters", {})
        show_installed = filters.get("installed", True)
        
        installed_versions = get_installed_versions()
        installed_versions_set = set(installed_versions)
        available_versions, latest_release_id = get_available_versions(filters)
        
        
        
        
        if latest_release_id:
            display_name = f"Latest Release ({latest_release_id})"
            
            
            if latest_release_id in installed_versions_set: 
                display_name = f"(Installed) Latest Release ({latest_release_id})"
            
            self.version_combo.addItem(display_name, latest_release_id)
            
            if current_version is None:
                current_version = latest_release_id
        

        if show_installed:
            for version in installed_versions:
                if version == latest_release_id: 
                    continue
                
                self.version_combo.addItem(f"(Installed) {version}", version)
         
        for label, version_id in available_versions:

            if version_id == latest_release_id:
                if version_id in installed_versions_set:
                    label = f"(Installed) {label}"
                self.version_combo.addItem(label, version_id)
                continue
        
            if version_id not in installed_versions_set:
                self.version_combo.addItem(label, version_id)
            else:
                pass 
                
        if current_version:
            index = self.version_combo.findData(current_version)
            if index != -1:
                self.version_combo.setCurrentIndex(index)
                
                
                
                
        if show_installed:
            for version in installed_versions:
                self.version_combo.addItem(f"(Installed) {version}", version)
        
        installed_versions_set = set(installed_versions)
        for label, version_id in available_versions:
            if version_id not in installed_versions_set:
                self.version_combo.addItem(label, version_id)
        
        if current_version:
            index = self.version_combo.findData(current_version)
            if index != -1:
                self.version_combo.setCurrentIndex(index)
                
        
        
        if self.rpc:
            self.update_rpc_menu()


    def load_styles(self):
        return """
        QWidget {
            background-color: #202020;
            color: #E0E0E0;
            font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
            font-size: 14px;
        }
        
        QFrame {
            background-color: #252525;
            border-right: 1px solid #404040;
        }

        QLineEdit, QComboBox {
            background-color: #353535;
            border: 1px solid #404040;
            border-radius: 4px;
            padding: 8px;
            color: #E0E0E0;
        }
        QComboBox::drop-down {
            border: none;
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
        }


        QPushButton {
            background-color: #353535;
            border: 1px solid #404040;
            border-radius: 4px;
            padding: 8px;
            font-weight: normal;
            color: #E0E0E0;
        }
        QPushButton:hover {
            background-color: #404040;
            border: 1px solid #5A99E5;
        }
        QPushButton:pressed {
            background-color: #5A99E5;
            color: #FFFFFF;
        }
        
        QPushButton#playButton {
            background-color: #4F2E70;
            border: none;
            font-weight: bold;
            font-size: 16px;
        }
        QPushButton#playButton:hover {
            background-color: #6a4692;
        }
        QPushButton#playButton:pressed {
            background-color: #3d2358;
        }
        
        QPushButton#playButton:disabled {
            background-color: #2a1c36;
            color: #A0A0A0;
        }

        QPushButton[text="⚙"] {
            border: none;
            background-color: #2D2D2D;
        }
        QPushButton[text="⚙"]:hover {
            background-color: #404040;
        }
        
        QPushButton[text="↻"] {
            border: none;
            background-color: #2D2D2D;
        }
        QPushButton[text="↻"]:hover {
            background-color: #404040;
        }

        QLabel {
            color: #FFFFFF;
        }
        QLabel#footer {
            color: #A0A0A0;
            font-size: 11px;
        }
        
        QListWidget {
            background-color: #2D2D2D;
            border: 1px solid #404040;
            border-radius: 4px;
        }
        QListWidget::item {
            padding: 8px;
        }
        QListWidget::item:selected {
            background-color: #5A99E5;
            color: #FFFFFF;
        }
        QListWidget::item:hover {
            background-color: #404040;
        }
        
        QGroupBox {
            font-weight: bold;
            margin-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding-left: 10px;
            padding-right: 10px;
            padding-top: -5px;
        }

        QDialog {
            background-color: #2D2D2D;
        }

        QTabWidget::pane {
            border: 1px solid #404040;
            border-top: none;
            background-color: #2D2D2D;
            border-bottom-left-radius: 4px;
            border-bottom-right-radius: 4px;
        }

        QTabBar::tab {
            background-color: #252525;
            color: #A0A0A0;
            border: 1px solid #404040;
            border-bottom: none;
            padding: 2px 4px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            margin-right: 2px;
        }

        QTabBar::tab:hover {
            background-color: #353535;
            color: #E0E0E0;
        }

        QTabBar::tab:selected {
            background-color: #2D2D2D;
            color: #FFFFFF;
            border-bottom: 1px solid #2D2D2D;
        }

        QCheckBox {
            spacing: 5px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #6a4692;
            border-radius: 4px;
            background-color: #353535;
        }
        QCheckBox::indicator:hover {
            border: 1px solid #805ea8;
        }
        QCheckBox::indicator:checked {
            background-color: #6a4692;
            image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0id2hpdGUiIHdpZHRoPSIxOHB4IiBoZWlnaHQ9IjE4cHgiPjxwYXRoIGQ9Ik0wIDBoMjR2MjRIMHoiIGZpbGw9Im5vbmUiLz48cGF0aCBkPSJNOSAxNi4xN0w0LjgzIDEyLjAxbC0xLjQxIDEuNDFMMTkgMTlsMi0yTDEwLjQxIDcuNTlsLTEuNDEgMS40MUw5IDE2LjE3eiIvPjwvc3ZnPg==);
        }
        QCheckBox::indicator:disabled {
            background-color: #404040;
            border: 1px solid #505050;
        }
        QCheckBox:disabled {
            color: #A0A0A0;
        }
        """

    def on_set_status(self, text):
        self.progress_label.setText(text)

    def on_set_progress(self, value):
        self.progress_bar.setValue(value)

    def on_set_max(self, maximum):
        self.progress_bar.setMaximum(maximum)

    def on_set_file(self, text, current, total, speed):
        if speed < 1024:
            spd = f"{speed:.1f} B/s"
        elif speed < 1024**2:
            spd = f"{speed/1024:.1f} KB/s"
        else:
            spd = f"{speed/1024**2:.2f} MB/s"

        self.progress_label.setText(
            f"Downloading: {text} "
            f"({current/1024/1024:.2f}/{total/1024/1024:.2f} MB) @ {spd}"
        )

    def after_download(self, selected_version_id, options, settings):
        print("[DEBUG] after_download triggered")

        self.is_downloading = False
        self.progress_label.hide()
        self.progress_bar.hide()

        if self.download_thread._cancelled:
            print("Download process was cancelled.")
            self.reset_after_cancel()
            return

        try:
            version_dir = os.path.join(get_minecraft_directory(), "versions", selected_version_id)
            jar_path = os.path.join(version_dir, f"{selected_version_id}.jar")

            for _ in range(10):
                if os.path.exists(jar_path):
                    break
                print("[DEBUG] Waiting for jar to exist...")
                time.sleep(0.5)

            command = minecraft_launcher_lib.command.get_minecraft_command(
                selected_version_id,
                get_minecraft_directory(),
                options
            )
            print("Launching with command:", " ".join(command))
            self.update_rpc_game(selected_version_id)

            self.play_button.setText("Launching...")
            self.play_button.setEnabled(False)
            self.play_button.setStyleSheet(self.load_styles())

            hide_on_launch = settings.get("hide_on_launch", True)
            if hide_on_launch:
                self.hide()
                self.temp_width = self.width()
                self.temp_height = self.height()
            

            self.minecraft_thread = MinecraftThread(command, get_minecraft_directory(), self)
            self.minecraft_thread.finished_signal.connect(self.on_minecraft_finished)
            self.minecraft_thread.log_signal.connect(self.on_minecraft_log)
            self.dev_console.set_kill_button_enabled(True)
            self.minecraft_thread.start()

        except Exception as e:
            QMessageBox.critical(self, "Launch Error", f"Failed to launch Minecraft:\n{e}")
            self.dev_console.set_kill_button_enabled(False)
            self.play_button.setText("Play")
            self.play_button.setEnabled(True)
            self.play_button.setStyleSheet(self.load_styles())
            self.show()

        if self.download_thread:
            self.download_thread.deleteLater()
            self.download_thread = None


    def reset_after_cancel(self):
        self.is_downloading = False
        self.progress_label.hide()
        self.progress_bar.hide()
        self.play_button.setText("Play")
        self.play_button.setEnabled(True)
        self.play_button.setStyleSheet(self.load_styles())
        self.update_rpc_menu()

    def on_play_clicked(self):
        print("[DEBUG] Thread created")
        if self.is_downloading and self.download_thread and self.download_thread.isRunning():
            print("Download canceled by user.")
            self.download_thread.cancel()
            
            self.play_button.setEnabled(False)
            self.play_button.setText("Please wait")
            self.play_button.setStyleSheet("""
                QPushButton#playButton {
                    background-color: #2a1c36;
                    color: white;
                    border: none;
                    font-weight: bold;
                    font-size: 16px;
                }
            """)
            self.progress_label.setText("Cancelling...")
            
            return

        username = self.username_combo.currentText()
        if username == "Manage Users...":
            QMessageBox.warning(self, "Invalid User", "Please select a valid username.")
            return

        selected_version_id = self.version_combo.currentData()
        if not selected_version_id:
            QMessageBox.warning(self, "No Version Selected", "Please select a Minecraft version to play.")
            return
        
        settings = load_settings()
        allocated_ram_mb = settings.get("ram_mb", 2048)
        
        user_uuid = get_mojang_uuid(username)
        if user_uuid is None:
            print(f"Cannot get Mojang UUID for {username}. Using offline UUID.")
            user_uuid = str(uuid.uuid3(uuid.NAMESPACE_URL, "OfflinePlayer:" + username))
        user_token = user_uuid

        minecraft_directory = get_minecraft_directory()
        jvm_args = settings.get("jvm_args", [])
        
        default_jvm_args = [f"-Xmx{allocated_ram_mb}M", "-Xms256M"]
        final_jvm_args = []
        overridden_args = set()

        for arg in jvm_args:
            if arg.startswith("-Xmx"):
                print("Ignoring user-provided -Xmx argument.")
            elif arg.startswith("-Xms"):
                final_jvm_args.append(arg)
                overridden_args.add("Xms")
            elif arg.startswith((
                "-Dlog4j2.formatMsgNoLookups", "-Dos.name", "-Dos.version",
                "-Djava.library.path", "-Dminecraft.launcher.brand",
                "-Dminecraft.launcher.version", "-cp",
                "-Djava.net.preferIPv4Stack=true"
            )):
                final_jvm_args.append(arg)
            else:
                final_jvm_args.append(arg)

        for arg in default_jvm_args:
            if arg.startswith("-Xms") and "Xms" in overridden_args:
                continue
            final_jvm_args.append(arg)

        options = {
            "username": username,
            "uuid": user_uuid,
            "token": user_token,
            "jvmArguments": final_jvm_args
        }

        self.progress_label.show()
        self.progress_bar.show()
        self.progress_label.setText("Preparing download...")
        self.progress_bar.setValue(0)
        self.update_rpc_downloading(selected_version_id)

        self.is_downloading = True
        self.play_button.setText("Cancel")
        self.play_button.setEnabled(True)
        self.play_button.setStyleSheet(self.load_styles())

        self.download_thread = DownloadThread(selected_version_id, minecraft_directory)
        self.download_thread.status_signal.connect(self.on_set_status)
        self.download_thread.value_signal.connect(self.on_set_progress)
        self.download_thread.max_signal.connect(self.on_set_max)
        self.download_thread.progress_signal.connect(self.on_set_file)
        self.download_thread.finished.connect(self.download_thread.deleteLater)
        self.download_thread.finished_signal.connect(
            lambda success: self.after_download(selected_version_id, options, settings)
        )
        self.download_thread.start()
    
    


class DownloadThread(QThread):
    progress_signal = Signal(str, int, int, float)
    status_signal = Signal(str)
    value_signal = Signal(int)
    max_signal = Signal(int)
    finished_signal = Signal(bool) 

    def __init__(self, version_id, minecraft_directory):
        print("[DEBUG] DownloadThread init")
        super().__init__()
        self.version_id = version_id
        self.minecraft_directory = minecraft_directory
        self._cancelled = False
        self.is_running = True

    def cancel(self):
        self._cancelled = True
        
    def run(self):
        print("[DEBUG] DownloadThread run start")
        try:
            minecraft_launcher_lib.install.install_minecraft_version(
                self.version_id,
                self.minecraft_directory,
                callback={
                    "setStatus": self.status_signal.emit,
                    "setProgress": self.value_signal.emit,
                    "setMax": self.max_signal.emit,
                    "setFile": self._on_file
                }
            )
            if not self._cancelled:
                self.finished_signal.emit(True)
            else:
                self.finished_signal.emit(False)
        except Exception as e:
            if str(e) == "Download cancelled":
                print(f"Download thread finished because it was cancelled.")
            else:
                print(f"Download error: {e}")
            self.finished_signal.emit(False)
        finally:
            self.is_running = False

    def _on_file(self, text, cur, tot, spd):
        if self._cancelled:
            print("Download aborted safely.")
            raise Exception("Download cancelled")
        self.progress_signal.emit(text, cur, tot, spd)


class LoadingWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.appdata_dir = get_appdata_path()
        self.icon_path = resource_path("icon.ico")
        
        self.setFixedSize(400, 200)
        self.setWindowTitle("Loading...")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("background-color: #202020;")
        if os.path.exists(self.icon_path):
            self.setWindowIcon(QIcon(str(self.icon_path)))

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        self.title_label = QLabel("MaZult Launcher")
        self.title_label.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)


        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #353535;
                color: #FFFFFF;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4F2E70;
            }
        """)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

        self.progress = 0
        self.timer = QTimer()
        self.main_window = None
        self.update_info = None

    def start_loading_animation(self):
        self.timer.timeout.connect(self.update_loading_state)
        self.timer.start(100)
        self.show()
        if not sys.platform.startswith('win32'):
            self.check_for_updates()

    def check_for_updates(self):
        self.update_thread = QThread()
        self.update_checker = UpdateChecker(LAUNCHER_VERSION)
        self.update_checker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_checker.run)
        self.update_checker.update_available.connect(self.handle_update_available)
        self.update_checker.finished.connect(self.update_thread.quit)
        self.update_thread.start()

    def handle_update_available(self, latest_version, download_url):
        self.update_info = (latest_version, download_url)
        self.timer.stop()
        
        reply = QMessageBox.question(self, "Update Available",
                                     f"New version {latest_version}. Do you want to update?",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            webbrowser.open(download_url)
            self.close()
            QApplication.instance().quit()
        else:
            self.timer.start(100)
            self.update_progress(100, "Loading GUI...")


    def update_loading_state(self):
        if self.progress < 100:
            self.progress += 10
            if self.progress == 10:
                self.update_progress(self.progress, "Check For Update...")
            elif self.progress == 50:
                self.update_progress(self.progress, "Loading config.")
            elif self.progress == 90:
                self.update_progress(self.progress, "Loading GUI...")
            else:
                self.update_progress(self.progress, "Installizing...")
        else:
            self.timer.stop()
            self.main_window = MaZultLauncher(self.update_info)
            self.main_window.show()
            self.close()

    def update_progress(self, value, text=""):
        self.progress_bar.setValue(value)
        self.status_label.setText(text)
        QApplication.instance().processEvents()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    appdata_path = get_appdata_path()
    os.makedirs(appdata_path, exist_ok=True)
    os.chdir(appdata_path)

    script_dir = Path(__file__).resolve().parent
    
    is_windows = sys.platform.startswith('win32')
    is_linux = sys.platform.startswith('linux')
    is_launcher_arg = "--Launcher" in sys.argv
    
    print(f"Giá trị của is_launcher_arg: {is_launcher_arg}")
    print(f"Đường dẫn script: {script_dir}")
    
    if (is_windows or is_linux) and not is_launcher_arg:
        frozen_base_dir = Path(os.path.dirname(sys.executable)).parent

        launcher_name = "MaZult Launcher.exe" if is_windows else "MaZult Launcher"
        
        exe_path = frozen_base_dir / launcher_name
        
        print(f"Updater {exe_path}")
            
        if exe_path.exists():
            try:
                print("Found Updater")
                subprocess.Popen([str(exe_path), "--Launcher"])
                sys.exit(0)
            except Exception as e:
                print(f"Error when Launching {e}")
                loading_window = LoadingWindow()
                loading_window.start_loading_animation()
                sys.exit(app.exec())
        else:
            print("No updater, run default app")
            loading_window = LoadingWindow()
            loading_window.start_loading_animation()
            sys.exit(app.exec())
    else: 
        loading_window = LoadingWindow()
        loading_window.start_loading_animation()
        sys.exit(app.exec())