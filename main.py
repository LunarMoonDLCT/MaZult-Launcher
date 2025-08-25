import os
import sys
import shutil
import json
import webbrowser
import subprocess
import psutil
import requests
import tempfile
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFrame, QDialog, QListView, QAbstractItemView, QCheckBox, QMessageBox,
    QTabWidget, QSlider, QScrollArea, QListWidget, QListWidgetItem, QInputDialog, QDialogButtonBox,
    QGroupBox, QPlainTextEdit, QProgressBar
)
from PySide6.QtGui import QPixmap, QIcon, QStandardItemModel, QStandardItem, QFont
from PySide6.QtCore import Qt, QTimer, QSize, Signal, QThread, QObject, QUrl
import minecraft_launcher_lib
import datetime
from PySide6.QtGui import QPainter, QPixmap, QColor, QImage
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QDialog, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QPushButton, QVBoxLayout, QFileDialog, QGraphicsRectItem, QGraphicsItem
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QMouseEvent, QBrush
from PySide6.QtCore import QRectF, Qt, QPointF
import uuid
from PySide6.QtWidgets import QSplashScreen
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Qt, QTimer
import zipfile
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QMouseEvent
from PySide6.QtCore import Qt, QRect


LAUNCHER_VERSION = "1.0.0"
GITHUB_API_RELEASES = "https://api.github.com/repos/LunarMoonDLCT/MaZult-Launcher/releases/latest"

def get_appdata_path():
    if sys.platform.startswith('win32'):
        return Path(os.getenv("APPDATA")) / ".MaZultLauncher"
    elif sys.platform.startswith('linux'):
        return Path.home() / ".MaZultLauncher"
    elif sys.platform.startswith('darwin'):
        return Path.home() / "Library" / "Application Support" / ".MaZultLauncher"
    else:
        return Path.home() / ".MaZultLauncher"

def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
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

def save_settings(username=None, version_id=None, ram_mb=None, mc_dir=None, filters=None, dev_console=None, hide_on_launch=None, jvm_args=None):
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
        "dev_console": False,
        "hide_on_launch": True,
        "jvm_args": []
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
    try:
        if offline:
            raise Exception("Forced offline")
        mc_versions = minecraft_launcher_lib.utils.get_version_list()
        serializable_versions = []
        for v in mc_versions:
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
            except Exception:
                return [("Offline: No cached versions", "")]
        else:
            return [("Offline: No cached versions", "")]

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
    
    return filtered_versions

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
        
        # Minecraft Directory
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

        # RAM Allocation
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

        # JVM Arguments
        jvm_groupbox = QGroupBox("JVM Arguments")
        jvm_layout = QVBoxLayout()
        self.jvm_text_edit = QPlainTextEdit()
        self.jvm_text_edit.setPlaceholderText("")
        jvm_layout.addWidget(self.jvm_text_edit)
        jvm_groupbox.setLayout(jvm_layout)
        general_layout.addWidget(jvm_groupbox)

        jvm_args_str = " ".join(settings.get("jvm_args", []))
        self.jvm_text_edit.setPlainText(jvm_args_str)

        # Version Filters
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

        dev_layout.addStretch()
        dev_tab.setLayout(dev_layout)

        tabs.addTab(general_tab, "General")
        tabs.addTab(QWidget(), "Game Settings")
        tabs.addTab(dev_tab, "DEV")
        tabs.addTab(QWidget(), "Advanced")

        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_and_close)

        layout = QVBoxLayout()
        layout.addWidget(tabs)
        layout.addWidget(save_button)
        self.setLayout(layout)

    def save_and_close(self):
        ram_mb = self.ram_slider.value()
        
        mc_dir = self.mc_dir_input.text().strip()
        if not os.path.exists(mc_dir):
            QMessageBox.warning(self, "Invalid Path", "The specified Minecraft directory does not exist.")
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

        save_settings(ram_mb=ram_mb, mc_dir=mc_dir, filters=filters, dev_console=dev_console_enabled, hide_on_launch=hide_on_launch, jvm_args=jvm_args)
        
        if dev_console_enabled and self.parent().dev_console.isHidden():
            self.parent().dev_console.show()
        elif not dev_console_enabled and self.parent().dev_console.isVisible():
            self.parent().dev_console.hide()

        self.refreshVersions.emit()
        self.accept()

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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Developer Console")
        self.setMinimumSize(700, 400)
        # self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlags(Qt.Window)
        
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
        if self.parent() and self.parent().minecraft_thread and self.parent().minecraft_thread.process:
            try:
                self.parent().minecraft_thread.process.kill()
                self.parent().minecraft_thread.process.wait()
                print("Minecraft process killed.")
                self.set_kill_button_enabled(False)
                if self.parent().isHidden():
                    self.parent().show()
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

    def __init__(self):
        super().__init__()
        self.appdata_dir = get_appdata_path()
        self.assets_dir = self.appdata_dir / "assets"
        self.icon_path = self.assets_dir / "comming soon.ico"
        self.mc_process = None
        self.minecraft_thread = None
        
        self.dev_console = DevConsole(self)
        if load_settings().get("dev_console", False):
            self.dev_console.show()

        self.setWindowTitle(f"MaZult Launcher {LAUNCHER_VERSION}")
        self.setWindowIcon(QIcon(str(self.icon_path)))
        self.setMinimumSize(900, 520)
        self.setStyleSheet(self.load_styles())
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        sidebar = QVBoxLayout()
        sidebar.setAlignment(Qt.AlignTop)
        sidebar.setSpacing(20)
        sidebar.setContentsMargins(20, 20, 20, 20)
        
        username_label = QLabel("Username:")
        self.username_combo = QComboBox()
        self.username_combo.currentTextChanged.connect(self.on_username_changed)
        self.update_username_combo()
        
        sidebar.addWidget(username_label)
        sidebar.addWidget(self.username_combo)

        self.settings_button_left = QPushButton("Settings")
        self.settings_button_left.setFixedSize(160, 40)
        self.settings_button_left.clicked.connect(self.open_settings_dialog)
        self.settings_button_left.setStyleSheet("text-align: left; padding: 10px; background-color: #353535; border: 1px solid #404040;")
        sidebar.addStretch()
        sidebar.addWidget(self.settings_button_left, alignment=Qt.AlignBottom)
        
        sidebar_frame = QFrame()
        sidebar_frame.setLayout(sidebar)
        sidebar_frame.setFixedWidth(200)
        sidebar_frame.setStyleSheet("background-color: #252525; border-right: 1px solid #404040;")
        main_layout.addWidget(sidebar_frame)
        
        content_layout = QVBoxLayout()
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        header_layout = QHBoxLayout()
        title = QLabel("MaZult Launcher")
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

        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("playButton")
        self.play_button.setStyleSheet("background-color: #4F2E70; color: #FFFFFF; border: none; font-weight: bold; font-size: 16px; border-radius: 4px;")
        self.play_button.clicked.connect(self.on_play_clicked)
        content_layout.addWidget(self.play_button)
        
        main_layout.addLayout(content_layout)

    def on_minecraft_finished(self):
        if self.play_button and not self.play_button.parent() is None:
            self.play_button.setText("Play")
            self.play_button.setEnabled(True)
            self.dev_console.set_kill_button_enabled(False)
            self.mc_process = None
            self.minecraft_thread = None
            settings = load_settings()
            hide_on_launch = settings.get("hide_on_launch", True)
            if hide_on_launch:
                self.show()

    def on_minecraft_log(self, text):
        self.dev_console.write(text)

    def load_versions(self):
        self.version_combo.clear()
        
        settings = load_settings()
        current_version = settings.get("version_id")
        
        filters = settings.get("filters", {})
        show_installed = filters.get("installed", True)

        installed_versions = get_installed_versions()
        available_versions = get_available_versions(filters)

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

    def load_styles(self):
        return """
        /* Main Window and General Widgets */
        QWidget {
            background-color: #202020;
            color: #E0E0E0;
            font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
            font-size: 14px;
        }
        
        /* Sidebar Frame */
        QFrame {
            background-color: #252525;
            border-right: 1px solid #404040;
        }

        /* Input Fields and Dropdowns (QLineEdit, QComboBox) */
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


        /* Standard Buttons */
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
        
        /* Play Button (Primary Action) */
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
        
        /* New style for the disabled Play button */
        QPushButton#playButton:disabled {
            background-color: #606060; /* Màu xám */
            color: #A0A0A0; /* Chữ màu xám nhạt */
        }

        /* Settings Button (Gear icon) */
        QPushButton[text="⚙"] {
            border: none;
            background-color: #2D2D2D;
        }
        QPushButton[text="⚙"]:hover {
            background-color: #404040;
        }
        
        /* Refresh Button (Gear icon) */
        QPushButton[text="↻"] {
            border: none;
            background-color: #2D2D2D;
        }
        QPushButton[text="↻"]:hover {
            background-color: #404040;
        }

        /* Title and Footer */
        QLabel {
            color: #FFFFFF;
        }
        QLabel#footer {
            color: #A0A0A0;
            font-size: 11px;
        }
        
        /* List Widget for Versions */
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
        
        /* Group Box for filters */
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
            spd = f"{speed/1024**2:.1f} MB/s"

        self.progress_label.setText(
            f"Downloading: {text} "
            f"({current/1024/1024:.2f}/{total/1024/1024:.2f} MB) @ {spd}"
        )


    def on_play_clicked(self):
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
            elif arg.startswith(("-Dlog4j2.formatMsgNoLookups", "-Dos.name", "-Dos.version", "-Djava.library.path", "-Dminecraft.launcher.brand", "-Dminecraft.launcher.version", "-cp", "-Djava.net.preferIPv4Stack=true")):
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
        
        self.play_button.setText("Launching...")
        self.play_button.setEnabled(False)

        try:
            installed_versions = get_installed_versions()
            if selected_version_id not in installed_versions:
                reply = QMessageBox.question(self, "Download Version", f"Version {selected_version_id} is not installed. Do you want to download and install it?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    minecraft_launcher_lib.install.install_minecraft_version(
                        selected_version_id,
                        minecraft_directory
                    )
                else:
                    self.play_button.setText("Play")
                    self.play_button.setEnabled(True)
                    return
            else:
                print(f"Checking and repairing installation for {selected_version_id}...")
                minecraft_launcher_lib.install.install_minecraft_version(
                    selected_version_id,
                    minecraft_directory
                )

            command = minecraft_launcher_lib.command.get_minecraft_command(
                selected_version_id,
                minecraft_directory,
                options
            )

            print("Launching with command:", " ".join(command))

            hide_on_launch = settings.get("hide_on_launch", True)
            if hide_on_launch:
                self.hide()
                
            self.minecraft_thread = MinecraftThread(command, minecraft_directory, self)
            self.minecraft_thread.finished_signal.connect(self.on_minecraft_finished)
            self.minecraft_thread.log_signal.connect(self.on_minecraft_log)
            self.dev_console.set_kill_button_enabled(True)
            self.minecraft_thread.start()

        except Exception as e:
            QMessageBox.critical(self, "Launch Error", f"Failed to launch Minecraft:\n{e}")
            self.dev_console.set_kill_button_enabled(False)
            self.play_button.setText("Play")
            self.play_button.setEnabled(True)
            self.show()

class SplashScreen(QSplashScreen):
    def __init__(self, parent=None):
        pixmap = QPixmap(400, 250)
        pixmap.fill(QColor(32, 32, 32))
        super().__init__(pixmap, Qt.WindowStaysOnTopHint)

        self.progress_value = 0
        self.loading_text = "Initializing..."
        self.download_progress = 0
        self.download_total = 0

    def set_loading_progress(self, value, text=""):
        self.progress_value = value
        self.loading_text = text
        self.repaint()

    def set_download_progress(self, current, total):
        self.download_progress = current
        self.download_total = total
        self.repaint()

    def drawContents(self, painter: QPainter):
        super().drawContents(painter)
        rect = self.rect()

        painter.setPen(QColor(255, 255, 255))
        title_font = QFont("Segoe UI", 24, QFont.Bold)
        painter.setFont(title_font)
        painter.drawText(rect, Qt.AlignHCenter | Qt.AlignTop, "MaZult Launcher")

        painter.setPen(QColor(200, 200, 200))
        text_font = QFont("Segoe UI", 10)
        painter.setFont(text_font)
        text_rect = rect.adjusted(0, rect.height() - 60, 0, 0)
        
        if self.download_total > 0:
            text = f"{self.loading_text} ({self.download_progress/1024/1024:.2f} MB / {self.download_total/1024/1024:.2f} MB)"
            bar_rect = rect.adjusted(50, rect.height() - 40, -50, -20)
            progress_width = (bar_rect.width() * self.download_progress) // self.download_total if self.download_total > 0 else 0
            progress_rect = bar_rect.adjusted(1, 1, progress_width, -1)
            painter.setPen(QColor(64, 64, 64))
            painter.drawRect(bar_rect)
            painter.fillRect(progress_rect, QColor(90, 153, 229))
        else:
            text = self.loading_text
            bar_rect = rect.adjusted(50, rect.height() - 40, -50, -20)
            painter.setPen(QColor(64, 64, 64))
            painter.drawRect(bar_rect)
            progress_width = (bar_rect.width() * self.progress_value) // 100
            progress_rect = bar_rect.adjusted(1, 1, progress_width, -1)
            painter.fillRect(progress_rect, QColor(90, 153, 229))
            
        painter.drawText(text_rect, Qt.AlignHCenter, text)


class UpdateThread(QThread):
    update_found = Signal(str, str)
    no_update = Signal()
    progress_signal = Signal(int, int)
    
    def run(self):
        try:
            response = requests.get(GITHUB_API_RELEASES, timeout=10)
            response.raise_for_status()
            release_info = response.json()
            latest_version = release_info['tag_name']

            # Compare versions
            current_version_tuple = tuple(map(int, LAUNCHER_VERSION.split('.')))
            latest_version_tuple = tuple(map(int, latest_version.split('.')))

            if latest_version_tuple > current_version_tuple:
                asset_url = None
                for asset in release_info['assets']:
                    if sys.platform.startswith('win32') and asset['name'].endswith('-Win.zip'):
                        asset_url = asset['browser_download_url']
                        break
                    elif (sys.platform.startswith('linux') or sys.platform.startswith('darwin')) and asset['name'].endswith('-Universal.zip'):
                        asset_url = asset['browser_download_url']
                        break
                
                if asset_url:
                    self.update_found.emit(latest_version, asset_url)
                else:
                    self.no_update.emit()
            else:
                self.no_update.emit()

        except requests.RequestException as e:
            print(f"Update check failed: {e}")
            self.no_update.emit()
        except Exception as e:
            print(f"An unexpected error occurred during update check: {e}")
            self.no_update.emit()

class DownloadThread(QThread):
    download_progress = Signal(int, int)
    download_finished = Signal(str)
    download_failed = Signal(str)

    def __init__(self, url, filename, parent=None):
        super().__init__(parent)
        self.url = url
        self.filename = filename

    def run(self):
        try:
            with requests.get(self.url, stream=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                downloaded_size = 0
                with open(self.filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            self.download_progress.emit(downloaded_size, total_size)
            self.download_finished.emit(self.filename)
        except Exception as e:
            self.download_failed.emit(str(e))

def restart_application():
    try:
        if sys.platform.startswith('win32'):
            subprocess.Popen([sys.executable] + sys.argv, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([sys.executable] + sys.argv)
        sys.exit()
    except Exception as e:
        print(f"Failed to restart application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    splash = SplashScreen()
    splash.show()
    app.processEvents()

    appdata_path = get_appdata_path()
    os.makedirs(appdata_path, exist_ok=True)
    os.chdir(appdata_path)

    splash.set_loading_progress(10, "Checking for updates...")
    app.processEvents()

    update_thread = UpdateThread()
    
    def handle_update_found(version, url):
        print(f"New version {version} available. Downloading from {url}")
        
        if getattr(sys, 'frozen', False):
            current_dir = Path(os.path.dirname(sys.executable))
        else:
            current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
            
        zip_path = current_dir / f"MaZulLauncher-{version}.zip"

        splash.set_loading_progress(20, "Downloading update...")
        app.processEvents()

        download_thread = DownloadThread(url, str(zip_path))
        download_thread.download_progress.connect(splash.set_download_progress)
        
        def handle_download_finished(filename):
            splash.set_loading_progress(70, "Extracting update...")
            app.processEvents()
            
            if getattr(sys, 'frozen', False):
                current_dir = Path(os.path.dirname(sys.executable))
            else:
                current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
            temp_dir = current_dir / "temp"
            os.makedirs(temp_dir, exist_ok=True)
            
            try:
                with zipfile.ZipFile(filename, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
          
                extracted_dir = None
                for item in os.listdir(temp_dir):
                    if os.path.isdir(os.path.join(temp_dir, item)):
                        extracted_dir = Path(temp_dir, item)
                        break
                
                if extracted_dir:
                    splash.set_loading_progress(80, "Applying update...")
                    app.processEvents()

                    for item in os.listdir(extracted_dir):
                        s = os.path.join(extracted_dir, item)
                        d = os.path.join(current_dir, item)
                        if os.path.isdir(s):
                            shutil.copytree(s, d, dirs_exist_ok=True)
                        else:
                            shutil.copy2(s, d)

                    # For Linux/macOS
                    if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
                        splash.set_loading_progress(90, "Installing dependencies...")
                        app.processEvents()
                        req_file = current_dir / "requirements.txt"
                        if os.path.exists(req_file):
                            print("Running pip install...")
                            subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_file)], check=True)
                            print("Dependencies installed.")

                    print("Update applied. Relaunching...")
                    os.remove(filename)
                    shutil.rmtree(temp_dir)
                    QMessageBox.information(None, "Update Successful", "The launcher has been updated. It will now restart.")
                    restart_application()
                else:
                    raise Exception("Could not find extracted directory in the zip file.")

            except Exception as e:
                QMessageBox.critical(None, "Update Failed", f"Failed to apply update: {e}")
                print(f"Update failed: {e}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                splash.set_loading_progress(100, "Failed to update. Starting old version...")
                app.processEvents()
                start_main_app()
        
        def handle_download_failed(error_msg):
            QMessageBox.critical(None, "Download Failed", f"Failed to download update: {error_msg}")
            print(f"Download failed: {error_msg}")
            splash.set_loading_progress(100, "Failed to download update. Starting old version...")
            app.processEvents()
            start_main_app()
        
        download_thread.download_finished.connect(handle_download_finished)
        download_thread.download_failed.connect(handle_download_failed)
        download_thread.start()

    def start_main_app():
        global window
        splash.set_loading_progress(100, "Done.")
        app.processEvents()
        window = MaZultLauncher()
        window.show()
        splash.finish(window)

    update_thread.update_found.connect(handle_update_found)
    update_thread.no_update.connect(start_main_app)
    update_thread.start()

    sys.exit(app.exec())