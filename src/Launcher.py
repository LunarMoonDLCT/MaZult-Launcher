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
import xml.etree.ElementTree as ET
import shlex
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFrame, QDialog, QListView, QAbstractItemView, QCheckBox, QMessageBox,
    QTabWidget, QSlider, QScrollArea, QListWidget, QListWidgetItem, QInputDialog, QDialogButtonBox,
    QGroupBox, QPlainTextEdit, QProgressBar, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsRectItem, QGraphicsItem, QFileDialog, QRadioButton, QStackedWidget
)
from PySide6.QtGui import (
    QPixmap, QIcon, QStandardItemModel, QStandardItem, QFont, QPainter, QColor, QImage,
    QPen, QMouseEvent, QBrush
)
from PySide6.QtCore import (
    Qt, QTimer, QSize, Signal, QThread, QObject, QUrl, QRect, QRectF, QPointF
)
import traceback
import minecraft_launcher_lib
import datetime
import uuid
from pypresence import Presence
from pypresence.exceptions import InvalidID, PipeClosed
from packaging.version import Version, InvalidVersion
if sys.platform.startswith("win32"):
    import ctypes

GITHUB_API_URL = "https://api.github.com/repos/LunarMoonDLCT/MZassets/releases/latest"
DISCORD_CLIENT_ID = "1410269369748946986"

def parse_launcher_args():
    args = sys.argv[1:]

    has_launcher = False
    updater_ver = None

    i = 0
    while i < len(args):
        arg = args[i]

        if arg == "--Launcher":
            has_launcher = True

        elif arg == "--UpdaterVer":
            if i + 1 < len(args):
                updater_ver = args[i + 1]
                i += 1

        i += 1

    if has_launcher and updater_ver is None:
        updater_ver = "0.0.0"

    return {"has_launcher": has_launcher, "updater_ver": updater_ver}


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


def list_available_languages():
    lang_dir = resource_path("lang")
    langs = {}
    if not os.path.exists(lang_dir):
        print("[Lang] No lang directory found.")
        return langs

    for file in os.listdir(lang_dir):
        if file.endswith(".json"):
            lang_code = file.replace(".json", "")
            try:
                with open(os.path.join(lang_dir, file), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    lang_name = data.get("langinfo", lang_code)
                    langs[lang_code] = lang_name
            except Exception as e:
                print(f"[Lang] Failed to read {file}: {e}")
    return langs

def load_language(lang_code="en_us"):
    lang_path = os.path.join(resource_path("lang"), f"{lang_code}.json")
    if os.path.exists(lang_path):
        try:
            with open(lang_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Lang] Error loading {lang_code}: {e}")
    print(f"[Lang] Missing language file: {lang_code}, fallback to English.")
    if lang_code != "en_us":
        return load_language("en_us")
    return {}

VERSION_FILE = get_appdata_path() / "versions.json"
VERSION_API = "https://launchermeta.mojang.com/mc/game/version_manifest.json"

def minecraft_version_key(version_string: str):
    try:
        return Version(version_string)
    except InvalidVersion:
        return Version("0.0.0-alpha")

def sort_versions_smart(versions: list[str], reverse=True) -> list[str]:
    def key(v):
        try:
            return Version(v)
        except InvalidVersion:
            return Version("0.0.0")
    return sorted(versions, key=key, reverse=reverse)

class CropBox(QGraphicsRectItem):
    def __init__(self, rect):
        super().__init__(rect)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setPen(QPen(Qt.green, 2))
        self.setBrush(QBrush(QColor(0, 255, 0, 40)))

def format_jvm_args(args: list[str]) -> str:
    result = []
    for arg in args:
        if " " in arg or "\t" in arg:
            escaped = arg.replace('"', '\\"')
            result.append(f'"{escaped}"')
        else:
            result.append(arg)
    return " ".join(result)
class CropBox(QGraphicsRectItem):
    def __init__(self, rect):
        super().__init__(rect)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setPen(QPen(Qt.green, 2))
        self.setBrush(QBrush(QColor(0, 255, 0, 40)))

SETTINGS_FILE = get_appdata_path() / "settings.json"
USERS_FILE = get_appdata_path() / "users.json"

def save_settings(username=None, version_id=None, ram_mb=None, mc_dir=None, filters=None, dev_console=None, hide_on_launch=None, jvm_args=None, discord_rpc=None, language=None, java_mode=None, java_path=None, skip_version_check=None):
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
    if language is not None:
        data["language"] = language
    if java_mode is not None:
        data["java_mode"] = java_mode
    if java_path is not None:
        data["java_path"] = java_path
    if skip_version_check is not None:
        data["skip_version_check"] = skip_version_check

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
        "jvm_args": [],
        "discord_rpc": True,
        "language": "en_us",
        "java_mode": "default",
        "java_path": "",
        "skip_version_check": False
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
    return []

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

    return sorted(installed_versions, key=minecraft_version_key, reverse=True)

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

def find_java_executable(java_dir):
    if not java_dir:
        return None

    win_candidates = [
        os.path.join(java_dir, "bin", "javaw.exe"),
        os.path.join(java_dir, "bin", "java.exe"),
        os.path.join(java_dir, "javaw.exe"),
        os.path.join(java_dir, "java.exe"),
    ]

    unix_candidates = [
        os.path.join(java_dir, "bin", "java"),
        os.path.join(java_dir, "java"),
    ]
    candidates = []
    if sys.platform.startswith("win32"):
        candidates = win_candidates
    else:
        candidates = unix_candidates

    for path in candidates:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    return None

def get_tmp_dir():
    tmp = get_appdata_path() / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp

class SettingsDialog(QWidget):
    refreshVersions = Signal()

    def __init__(self, parent=None, tr=None):
        super().__init__(parent)
        self.tr = tr if tr else load_language()
        
        self.jvm_args_list = load_settings().get("jvm_args", [])

        tabs = QTabWidget()

        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        mc_dir_layout = QHBoxLayout()
        mc_dir_label = QLabel(self.tr.get("minecraft_directory", "Minecraft Directory:"))
        self.mc_dir_input = QLineEdit()
        self.mc_dir_input.setText(str(get_minecraft_directory()))
        self.mc_dir_browse_btn = QPushButton(self.tr.get("browse", "Browse"))
        self.mc_dir_browse_btn.clicked.connect(self.browse_mc_dir)
        mc_dir_layout.addWidget(mc_dir_label)
        mc_dir_layout.addWidget(self.mc_dir_input)
        mc_dir_layout.addWidget(self.mc_dir_browse_btn)

        settings = load_settings()

        ram_groupbox = QGroupBox(self.tr.get("ram_allocation", "RAM Allocation"))
        ram_layout = QVBoxLayout()
        self.ram_slider = QSlider(Qt.Horizontal)
        self.ram_slider.setMinimum(512)
        self.ram_slider.setMaximum(psutil.virtual_memory().total // (1024 * 1024) - 512)
        self.ram_slider.setSingleStep(512)
        ram_mb = settings.get("ram_mb", 2048)
        self.ram_slider.setValue(ram_mb)
        self.ram_label = QLabel()
        self.update_ram_label(self.ram_slider.value())
        self.ram_slider.valueChanged.connect(self.update_ram_label)
        ram_layout.addWidget(self.ram_label)
        ram_layout.addWidget(self.ram_slider)
        ram_groupbox.setLayout(ram_layout)

        java_groupbox = QGroupBox("Java Runtime")
        java_layout = QVBoxLayout()

        self.java_default_radio = QRadioButton("Use default Java (launcher built-in)")
        self.java_custom_radio = QRadioButton("Use custom Java path")
        self.java_default_radio.toggled.connect(self.update_java_ui_state)
        self.java_custom_radio.toggled.connect(self.update_java_ui_state)

        self.java_path_input = QLineEdit()
        self.java_path_input.setPlaceholderText("Path to Java folder (contains java.exe)")
        self.java_path_input.setStyleSheet("""
            QLineEdit:disabled {
                background-color: #3a3a3a;
                color: #777;
                border: 1px solid #555;
            }
        """)
        self.java_browse_btn = QPushButton(self.tr.get("browse", "Browse"))
        self.java_browse_btn.setStyleSheet("""
            QPushButton:disabled {
                background-color: #444;
                color: #777;
                border: 1px solid #555;
            }
        """)


        java_radio_layout = QHBoxLayout()
        java_radio_layout.addWidget(self.java_default_radio)
        java_radio_layout.addWidget(self.java_custom_radio)

        java_path_layout = QHBoxLayout()
        java_path_layout.addWidget(self.java_path_input)
        java_path_layout.addWidget(self.java_browse_btn)

        java_layout.addLayout(java_radio_layout)
        java_layout.addLayout(java_path_layout)
        java_groupbox.setLayout(java_layout)

        java_mode = settings.get("java_mode", "default")
        java_path = settings.get("java_path", "")

        if java_mode == "default":
            self.java_default_radio.setChecked(True)
        else:
            self.java_custom_radio.setChecked(True)

        self.update_java_ui_state()

        self.java_path_input.setText(java_path)
        self.java_browse_btn.clicked.connect(self.browse_java_path)

        jvm_button = QPushButton(self.tr.get("jvm_args_button", "JVM Arguments…"))
        jvm_button.clicked.connect(self.open_jvm_dialog)

        filter_groupbox = QGroupBox(self.tr.get("filters", "Filter Versions"))
        filter_layout = QVBoxLayout()
        self.release_checkbox = QCheckBox(self.tr.get("release", "Release"))
        self.snapshot_checkbox = QCheckBox(self.tr.get("snapshot", "Snapshot"))
        self.beta_checkbox = QCheckBox(self.tr.get("beta", "Beta"))
        self.alpha_checkbox = QCheckBox(self.tr.get("alpha", "Alpha"))
        self.installed_checkbox = QCheckBox(self.tr.get("installed", "Installed"))

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

        self.general_pages = QStackedWidget()
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        self.skip_check_checkbox = QCheckBox(
            self.tr.get("skip_version_check_checkbox", "Skip version verification (launch instantly)")
        )
        self.skip_check_checkbox.setToolTip(
            self.tr.get("skip_version_check_tooltip", "If enabled, installed versions will launch immediately without re-checking or downloading files.\n"
            "WARNING: This may cause crashes if game files are missing or corrupted. Use if you know what you are doing.")
        )
        self.skip_check_checkbox.setChecked(settings.get("skip_version_check", False))

        content_layout.addLayout(mc_dir_layout)
        content_layout.addWidget(ram_groupbox)
        content_layout.addWidget(jvm_button)
        content_layout.addWidget(filter_groupbox)
        content_layout.addWidget(java_groupbox)
        content_layout.addWidget(self.skip_check_checkbox)
        content_layout.addStretch()

        general_scroll = QScrollArea()
        general_scroll.setWidgetResizable(True)
        general_scroll.setFrameShape(QFrame.NoFrame) # Remove border
        general_scroll.setWidget(content_widget)

        general_layout.addWidget(general_scroll)

        dev_tab = QWidget()
        dev_layout = QVBoxLayout(dev_tab)

        lang_layout = QHBoxLayout()
        lang_label = QLabel(self.tr.get("language", "Language:"))
        self.lang_combo = QComboBox()
        available_langs = list_available_languages()
        self.lang_codes = list(available_langs.keys())
        for code in self.lang_codes:
            self.lang_combo.addItem(available_langs[code])
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.lang_combo)
        dev_layout.addLayout(lang_layout)
        if settings.get("language", "en_us") in self.lang_codes:
            self.lang_combo.setCurrentIndex(self.lang_codes.index(settings.get("language", "en_us")))
        else:
            self.lang_combo.setCurrentIndex(0)


        self.dev_console_checkbox = QCheckBox(self.tr.get("dev_console", "Dev Console"))
        self.dev_console_checkbox.setChecked(settings.get("dev_console", False))
        dev_layout.addWidget(self.dev_console_checkbox)

        self.hide_on_launch_checkbox = QCheckBox(self.tr.get("hide_launcher", "Don't hide launcher when running Minecraft"))
        self.hide_on_launch_checkbox.setChecked(not settings.get("hide_on_launch", True))
        dev_layout.addWidget(self.hide_on_launch_checkbox)

        self.discord_rpc_checkbox = QCheckBox(self.tr.get("discord_rpc", "Show status launcher in Discord"))
        self.discord_rpc_checkbox.setChecked(settings.get("discord_rpc", True))
        dev_layout.addWidget(self.discord_rpc_checkbox)

        dev_layout.addStretch()
        
        about_tab = QWidget()
        about_layout = QVBoxLayout()
        
        launcher_name_label = QLabel(self.tr.get("launcher_name_label", "MaZult Launcher"))
        launcher_name_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        launcher_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(launcher_name_label)

        creator_label = QLabel(self.tr.get("creator", "Creator: LunarMoonDLCT"))
        creator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(creator_label)
        
        about_layout.addSpacing(20)

        libraries_title = QLabel(self.tr.get("third_party_libs", "Third-Party Libraries:"))
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

        source_code_title = QLabel(self.tr.get("source_code", "Source Code Launcher:"))
        source_code_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        about_layout.addWidget(source_code_title)

        self.source_code_button = QPushButton(self.tr.get("open_github", "Open GitHub Repository"))
        self.source_code_button.clicked.connect(self.open_github_link)
        about_layout.addWidget(self.source_code_button)

        about_layout.addStretch()
        about_tab.setLayout(about_layout)

        tabs.addTab(general_tab, self.tr.get("general_tab", "General"))
        tabs.addTab(dev_tab, self.tr.get("launcher_settings_tab", "Launcher Setting"))
        tabs.addTab(about_tab, self.tr.get("about_tab", "About Launcher"))

        self.save_button = QPushButton(self.tr.get("save_settings", "Save Settings"))
        self.save_button.clicked.connect(self.save_and_return)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(tabs)
        container_layout.addStretch()

        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
        main_layout.addWidget(self.save_button)

    def open_jvm_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr.get("jvm_dialog_title", "Edit JVM Arguments"))
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        edit = QPlainTextEdit()
        edit.setMinimumHeight(200)

        current_args_str = format_jvm_args(self.jvm_args_list)
        edit.setPlainText(current_args_str)

        layout.addWidget(edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        layout.addWidget(button_box)

        def save_and_close():
            text = edit.toPlainText().strip()
            self.jvm_args_list = shlex.split(text) if text else []
            dialog.accept()

        button_box.accepted.connect(save_and_close)
        button_box.rejected.connect(dialog.reject)

        dialog.exec()

    def save_and_return(self):
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
                    QMessageBox.critical(self, self.tr.get("create_dir_failed", "Creation Failed"), f"Failed to create directory: {mc_dir}\nError: {e}")
                    return
        else:
            QMessageBox.warning(self, self.tr.get("invalid_path", "Invalid Path"), "Minecraft directory path cannot be empty.")
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
        jvm_args = self.jvm_args_list
        discord_rpc_enabled = self.discord_rpc_checkbox.isChecked()
        skip_version_check = self.skip_check_checkbox.isChecked()

        if self.java_default_radio.isChecked():
            java_mode = "default"
            java_path = ""
        else:
            java_mode = "custom"
            java_path = self.java_path_input.text().strip()

        if len(self.lang_codes) == 0:
            language = "en_us"
        else:
            idx = self.lang_combo.currentIndex()
            if idx < 0 or idx >= len(self.lang_codes):
                language = "en_us"
            else:
                language = self.lang_codes[idx]

        save_settings(
            ram_mb=ram_mb, 
            mc_dir=mc_dir, 
            filters=filters, 
            dev_console=dev_console_enabled, 
            hide_on_launch=hide_on_launch, 
            jvm_args=jvm_args,
            discord_rpc=discord_rpc_enabled,
            language=language,
            java_mode=java_mode,
            java_path=java_path,
            skip_version_check=skip_version_check
        )
        
        if old_settings.get("language") != language:
            QMessageBox.information(self, self.tr.get("language_changed_title", "Language Changed"), self.tr.get("language_changed_message", "Please restart the launcher to apply the new language."))
            QApplication.instance().quit()

        main_window = self.window()
        if hasattr(main_window, "dev_console"):
            if dev_console_enabled and main_window.dev_console.isHidden():
                main_window.dev_console.show()
            elif not dev_console_enabled and main_window.dev_console.isVisible():
                main_window.dev_console.hide()

        if hasattr(main_window, "reconnect_rpc") and old_settings.get("discord_rpc") != discord_rpc_enabled:
            main_window.reconnect_rpc()

        self.refreshVersions.emit()
        if hasattr(self.window(), 'go_home'): # type: ignore
            self.window().go_home()
        
    def open_github_link(self):
        webbrowser.open("https://github.com/LunarMoonDLCT/MaZult-Launcher")

    def update_ram_label(self, value):
        self.ram_label.setText(self.tr.get("ram_allocated", "Allocated RAM: {value} MB").format(value=value))

    def browse_mc_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, self.tr.get("select_mc_dir_title", "Select Minecraft Directory"))
        if dir_path:
            self.mc_dir_input.setText(dir_path)

    def browse_java_path(self):
        dir_path = QFileDialog.getExistingDirectory(self, self.tr.get("select_java_folder_title", "Select Java Folder"))
        if dir_path:
            self.java_path_input.setText(dir_path)

    def update_java_ui_state(self):
        use_default = self.java_default_radio.isChecked()
        self.java_path_input.setEnabled(not use_default)
        self.java_browse_btn.setEnabled(not use_default)

def find_minecraft_java_runtime(mc_dir: Path) -> str | None:
    runtime_dir = mc_dir / "runtime"
    if not runtime_dir.is_dir():
        return None

    candidates = []
    for runtime_version_dir in runtime_dir.iterdir():
        if not runtime_version_dir.is_dir():
            continue

        for platform_dir in runtime_version_dir.iterdir():
            if not platform_dir.is_dir():
                continue
            
            java_exe_name = "javaw.exe" if sys.platform.startswith("win32") else "java"
            java_bin = platform_dir / "bin" / java_exe_name
            if not java_bin.exists() and sys.platform.startswith("win32"):
                 java_bin = platform_dir / "bin" / "java.exe"

            if java_bin.exists() and os.access(java_bin, os.X_OK):
                candidates.append(java_bin)

    if not candidates:
        return None

    candidates.sort(key=lambda p: p.parent.parent.parent.name, reverse=True)
    return str(candidates[0])
class modloaderf(QThread):
    loaded = Signal(dict)
    error = Signal(str)

    def run(self):
        if self.isInterruptionRequested():
            return

        session = requests.Session()
        
        try:
            data = {}
            fabric_response = session.get(
                "https://meta.fabricmc.net/v2/versions",
                timeout=10
            )
            fabric_response.raise_for_status()
            data["fabric"] = fabric_response.json()

            quilt_installer_response = session.get(
                "https://meta.quiltmc.org/v3/versions/installer",
                timeout=10
            )
            quilt_installer_response.raise_for_status()
            data["quilt"] = quilt_installer_response.json()

            neoforge_response = session.get(
                "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml",
                timeout=10
            )
            neoforge_response.raise_for_status()
            data["neoforge"] = neoforge_response.text

            forge_response = session.get(
                "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml",
                timeout=10
            )
            forge_response.raise_for_status()
            data["forge"] = forge_response.text

            self.loaded.emit(data)

        except requests.exceptions.RequestException as e:
            self.error.emit(f"Network error: {e}")
        except Exception as e:
            self.error.emit(f"An unexpected error occurred: {e}")
        finally:
            session.close()

class ModLoaderInstallThread(QThread):
    progress = Signal(int)
    status = Signal(str)
    done = Signal(str)
    error = Signal(str)

    def __init__(self, loader, mc_ver, loader_ver, mc_dir, parent=None):
        super().__init__(parent)
        self.loader = loader
        self.mc_ver = mc_ver
        self.loader_ver = loader_ver
        self.mc_dir = mc_dir

    def run(self):
        try:
            mc_dir_path = Path(self.mc_dir)
            tmp_dir = get_tmp_dir()

            print("[WARN] Minecraft Java runtime not found. Falling back to 'javaw' in PATH.")
            java_path = "javaw" if sys.platform.startswith('win32') else "java"

            def run_java_installer(jar_path: Path, extra_args=None):
                if extra_args is None:
                    extra_args = []
                
                command = [java_path, "-jar", str(jar_path), *extra_args]
                print(f"Running installer with command: {' '.join(command)}")
                
                subprocess.run(
                    command,
                    cwd=str(mc_dir_path),
                    check=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win32') else 0
                )

            if self.loader == "fabric":
                self.status.emit(self.tr.get("installing_fabric", "Installing Fabric..."))
                self.progress.emit(50)
                minecraft_launcher_lib.fabric.install_fabric(self.mc_ver, self.mc_dir, self.loader_ver)
            elif self.loader == "quilt":
                self.status.emit(self.tr.get("installing_quilt", "Installing Quilt..."))
                self.progress.emit(10)
                
                new_repo_url = f"https://repo.maven.apache.org/maven2/org/quiltmc/quilt-installer/{self.loader_ver}/quilt-installer-{self.loader_ver}.jar"
                old_repo_url = f"https://maven.quiltmc.org/repository/release/org/quiltmc/quilt-installer/{self.loader_ver}/quilt-installer-{self.loader_ver}.jar"

                installer_urls = [new_repo_url, old_repo_url]
                installer_path = tmp_dir / f"quilt-installer-{self.loader_ver}.jar"

                downloaded = False
                for url in installer_urls:
                    try:
                        self.status.emit(self.tr.get("quilt_downloading_from", "Trying to download from {server}...").format(server=url.split('/')[2]))
                        r = requests.get(url, stream=True, timeout=15)
                        if r.status_code == 200:
                            with open(installer_path, "wb") as f: shutil.copyfileobj(r.raw, f)
                            downloaded = True
                            break
                    except requests.RequestException:
                        continue
                if not downloaded:
                    raise FileNotFoundError(f"Could not download Quilt installer {self.loader_ver} from any known repository.")

                self.progress.emit(70)
                run_java_installer(installer_path)
            elif self.loader == "forge":
                self.status.emit(self.tr.get("installing_forge", "Installing Forge..."))
                self.progress.emit(30)
                installer_url = (
                    "https://maven.minecraftforge.net/net/minecraftforge/forge/"
                    f"{self.loader_ver}/forge-{self.loader_ver}-installer.jar"
                )
                installer_path = tmp_dir / f"forge-{self.loader_ver}-installer.jar"
                r = requests.get(installer_url, stream=True); r.raise_for_status()
                with open(installer_path, "wb") as f: shutil.copyfileobj(r.raw, f)
                self.progress.emit(70)
                run_java_installer(installer_path)
                installer_path.unlink(missing_ok=True)
            elif self.loader == "neoforge":
                self.status.emit(self.tr.get("installing_neoforge_download", "Downloading NeoForge installer..."))
                self.progress.emit(30)
                installer_url = f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{self.loader_ver}/neoforge-{self.loader_ver}-installer.jar"
                installer_path = tmp_dir / f"neoforge-{self.loader_ver}-installer.jar"

                r = requests.get(installer_url, stream=True); r.raise_for_status()
                with open(installer_path, "wb") as f: shutil.copyfileobj(r.raw, f)

                self.status.emit(self.tr.get("installing_neoforge_install", "Installing NeoForge..."))
                self.progress.emit(70)
                run_java_installer(installer_path, [""])
                installer_path.unlink(missing_ok=True)

            self.progress.emit(100)
            self.done.emit(self.tr.get("modloader_install_success", "{loader_name} {loader_ver} installed successfully!").format(loader_name=self.loader.capitalize(), loader_ver=self.loader_ver))

        except Exception as e:
            self.error.emit(str(e))

class ModLoaderDialog(QDialog): # type: ignore
    def __init__(self, parent=None, tr=None):
        super().__init__(parent)
        self.tr = tr if tr else load_language()
        self.setWindowTitle(self.tr.get("modloader_dialog_title", "Install Mod Loader"))
        self.setMinimumSize(420, 280)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        self.fetched_data = {}
        
        layout = QVBoxLayout(self)

        self.status_label = QLabel("Loading modloader data...")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)

        self.main_widget = QWidget()
        main_layout = QVBoxLayout(self.main_widget)
        main_layout.setContentsMargins(0,0,0,0)

        self.loader_combo = QComboBox()
        self.loader_combo.setToolTip("Select the mod loader you want to install.")
        self.loader_combo.addItems(["Fabric", "Forge", "NeoForge", "Quilt"])
        self.mc_version_label = QLabel(self.tr.get("modloader_mc_version_label", "Minecraft Version:"))
        self.mc_version_combo = QComboBox()
        self.loader_version_label = QLabel(self.tr.get("modloader_loader_version_label", "Loader Version:"))
        self.loader_version_combo = QComboBox()

        main_layout.addWidget(QLabel(self.tr.get("modloader_loader_label", "Mod Loader:")))
        main_layout.addWidget(self.loader_combo)
        main_layout.addWidget(self.mc_version_label)
        main_layout.addWidget(self.mc_version_combo)
        main_layout.addWidget(self.loader_version_label)
        self.loader_version_combo.setToolTip(self.tr.get("modloader_version_tooltip", "Select the specific version of the mod loader."))
        main_layout.addWidget(self.loader_version_combo)
        self.main_widget.hide()

        self.install_btn = QPushButton(self.tr.get("modloader_install_button", "Install"))
        self.install_btn.setEnabled(False)
        self.install_btn.clicked.connect(self.install_loader)

        self.cancel_btn = QPushButton("Cancel")
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
            self.status_label.setText("Cancelling...")
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
        self.status_label.setText(self.tr.get("modloader_select_versions", "Select mod loader and versions"))
        self.install_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.main_widget.show()
        self.progress_bar.hide()
        self.status_label.hide()
        self.on_loader_changed()

    def on_fetch_error(self, msg):
        self.fetch_thread.quit()
        self.fetch_thread.wait()
        QMessageBox.critical(self, self.tr.get("network_error_title", "Network Error"), self.tr.get("modloader_fetch_error", "Could not fetch mod loader data:\n{msg}").format(msg=msg))
        self.reject()

    def install_loader(self):
        mc_dir = get_minecraft_directory()
        mc_ver = ""
        if self.loader_combo.currentText().lower() != "quilt":
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

        self.install_thread = ModLoaderInstallThread(loader, mc_ver, loader_ver, mc_dir)
        self.install_thread.status.connect(self.status_label.setText)
        self.install_thread.progress.connect(self.progress_bar.setValue)
        self.install_thread.done.connect(self.on_install_done)
        self.install_thread.error.connect(self.on_install_error)
        self.install_thread.start()

    def on_install_done(self, msg):
        QMessageBox.information(self, self.tr.get("success_title", "Success"), msg)
        self.accept()

    def on_install_error(self, msg):
        QMessageBox.critical(self, self.tr.get("install_error_title", "Installation Error"), msg)
        self.main_widget.setEnabled(True)
        self.install_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.status_label.hide()
        self.progress_bar.hide()

    def on_loader_changed(self):
        self.mc_version_combo.clear()
        self.loader_version_combo.clear()
        loader = self.loader_combo.currentText().lower()
        
        is_quilt = (loader == "quilt")
        self.mc_version_label.setVisible(not is_quilt)
        self.mc_version_combo.setVisible(not is_quilt)
        if is_quilt:
            self.loader_version_label.setText(self.tr.get("modloader_installer_version_label", "Installer Version:"))
        else:
            self.loader_version_label.setText(self.tr.get("modloader_loader_version_label", "Loader Version:"))


        if not self.fetched_data:
            return

        mc_versions = []
        try:
            if loader == "fabric":
                mc_versions = sorted([v['version'] for v in self.fetched_data["fabric"]['game'] if v['stable']], key=minecraft_version_key, reverse=True)
            elif loader == "quilt":
                pass
            elif loader == "forge":
                root = ET.fromstring(self.fetched_data[loader])
                versions_element = root.find("versioning/versions")
                if versions_element is not None: # type: ignore
                    all_versions = [v.text for v in versions_element.findall("version") if v.text]
                    unique_mc_versions = sorted(
                        list(set(v.split("-", 1)[0] for v in all_versions)),
                        key=minecraft_version_key,
                        reverse=True
                    )
                    mc_versions = unique_mc_versions

            elif loader == "neoforge":
                root = ET.fromstring(self.fetched_data[loader])
                versions_element = root.find("versioning/versions")
                if versions_element is not None:
                    unique_mc_versions = sort_versions_smart([v.text for v in versions_element.findall("version") if v.text])
                    mc_versions = unique_mc_versions


            if mc_versions:
                self.mc_version_combo.addItems(mc_versions)

        except Exception as e:
            print(f"Could not parse supported Minecraft versions for {loader.capitalize()}: {e}")
            QMessageBox.warning(self, self.tr.get("error_title", "Error"), self.tr.get("modloader_parse_mc_version_error", "Could not parse supported Minecraft versions for {loader_name}.").format(loader_name=loader.capitalize()))

        self.load_loader_versions(initial_load=True)

    def load_loader_versions(self, mc_version_text=None, initial_load=False):
        self.loader_version_combo.clear()
        loader = self.loader_combo.currentText().lower()
        mc_ver = self.mc_version_combo.currentText()

        if not self.fetched_data:
            return
        
        if loader != "quilt" and not mc_ver:
            self.loader_version_combo.setEnabled(False)
            return

        versions = []
        try:
            if loader == "fabric":
                is_valid_mc = any(g['version'] == mc_ver for g in self.fetched_data["fabric"]['game'])
                if is_valid_mc:
                    versions = sort_versions_smart([v['version'] for v in self.fetched_data["fabric"]['loader']])

            elif loader == "quilt":
                versions = sort_versions_smart([v['version'] for v in self.fetched_data["quilt"]])

            elif loader == "forge":
                root = ET.fromstring(self.fetched_data[loader])
                forge_versions = [
                    v.text for v in root.findall("versioning/versions/version")
                    if v.text and v.text.startswith(mc_ver + "-")
                ]
                versions = sorted(
                    forge_versions,
                    key=lambda v: Version(v.split('-', 1)[1]) if '-' in v else Version("0"),
                    reverse=True
                )

            elif loader == "neoforge":
                root = ET.fromstring(self.fetched_data[loader])
                all_loader_versions = [v.text for v in root.findall("versioning/versions/version") if v.text and v.text.startswith(mc_ver)]
                versions = sort_versions_smart(all_loader_versions)

            if not versions:
                self.loader_version_combo.addItem(self.tr.get("modloader_no_versions_available", "No loader available"))
                self.loader_version_combo.setEnabled(False)
                return

            for v in versions:
                if loader == "forge":
                    self.loader_version_combo.addItem(v.split('-', 1)[1], v)
                else:
                    self.loader_version_combo.addItem(v, v)
            self.loader_version_combo.setEnabled(True)

        except Exception as e:
            QMessageBox.warning(self, self.tr.get("modloader_error_title", "Loader Error"), self.tr.get("modloader_get_versions_error", "Could not get loader versions for {mc_ver}:\n{e}").format(mc_ver=mc_ver, e=e))
            self.loader_version_combo.setEnabled(False)


class UserManagerDialog(QDialog):
    def __init__(self, parent=None, tr=None):
        super().__init__(parent)
        self.tr = tr if tr else load_language()
        self.setWindowTitle(self.tr.get("user_manager_title", "Add Users | Manager Users"))
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
        self.select_btn = QPushButton(self.tr.get("select_button", "Select"))
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
        text, ok = QInputDialog.getText(self, self.tr.get("add_user_title", "Add User"), self.tr.get("add_user_prompt", "Enter new username:"))
        if ok and text and text not in self.users:
            self.users.append(text)
            save_users(self.users)
            self.update_list()
            
    def edit_user(self):
        selected = self.user_list.currentItem()
        if not selected:
            QMessageBox.warning(self, self.tr.get("no_selection_title", "No Selection"), self.tr.get("select_user_to_edit_prompt", "Please select a user to edit."))
            return
        
        old_username = selected.text()
        text, ok = QInputDialog.getText(self, self.tr.get("edit_user_title", "Edit User"), self.tr.get("edit_user_prompt", "Edit username:"), QLineEdit.Normal, old_username)
        if ok and text and text != old_username and text not in self.users:
            index = self.users.index(old_username)
            self.users[index] = text
            save_users(self.users)
            self.update_list()

    def delete_user(self):
        selected = self.user_list.currentItem()
        if not selected:
            QMessageBox.warning(self, self.tr.get("no_selection_title", "No Selection"), self.tr.get("select_user_to_delete_prompt", "Please select a user to delete."))
            return

        username = selected.text()
        if len(self.users) <= 1:
            QMessageBox.warning(self, self.tr.get("cannot_delete_user_title", "Cannot Delete"), self.tr.get("at_least_one_user_error", "You must have at least one user."))
            return

        reply = QMessageBox.question(self, self.tr.get("delete_user_title", "Delete User"), self.tr.get("delete_user_confirm", "Are you sure you want to delete '{username}'?").format(username=username),
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
            QMessageBox.warning(self, self.tr.get("no_selection_title", "No Selection"), self.tr.get("select_user_prompt", "Please select a user."))

class DevConsole(QWidget):
    append_signal = Signal(str)
    
    def __init__(self, parent_launcher, styles="", tr=None):
        super().__init__()
        self.parent_launcher = parent_launcher # type: ignore
        self.tr = parent_launcher.tr if hasattr(parent_launcher, 'tr') else load_language()
        self.setWindowTitle(self.tr.get("dev_console_title", "Developer Console"))
        self.setMinimumSize(700, 400)
        
        self.setStyleSheet(styles)
        
        self.layout = QVBoxLayout(self)
        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setStyleSheet("background-color: #000; color: #fff;")
        self.layout.addWidget(self.console_output)
        
        button_layout = QHBoxLayout()
        self.kill_button = QPushButton(self.tr.get("kill_minecraft_button", "Kill Minecraft"))
        self.kill_button.setEnabled(False)
        self.kill_button.clicked.connect(self.kill_minecraft_process)
        button_layout.addWidget(self.kill_button)
        self.layout.addLayout(button_layout)
        
        self.append_signal.connect(self._append_text)
        sys.stdout = self
        
    def write(self, text):
        self.append_signal.emit(text)

    def _append_text(self, text):
        self.console_output.appendPlainText(text)
    
    def flush(self):
        pass
        
    def set_kill_button_enabled(self, enabled):
        if self.kill_button and not self.kill_button.parent() is None:
            self.kill_button.setEnabled(enabled)

    def kill_minecraft_process(self):
        if self.parent_launcher.minecraft_thread and self.parent_launcher.minecraft_thread.process:
            try:
                self.parent_launcher.minecraft_thread.killed_by_user = True
                self.parent_launcher.minecraft_thread.process.kill()
                self.parent_launcher.minecraft_thread.process.wait()
                print(self.tr.get("minecraft_process_killed_log", "Minecraft process killed.")) # type: ignore
                self.set_kill_button_enabled(False)
                if self.parent_launcher.isHidden():
                    self.parent_launcher.show()
                    self.parent_launcher.update_rpc_menu()
            except Exception as e:
                print(self.tr.get("kill_minecraft_failed_log", "Failed to kill Minecraft process: {e}").format(e=e)) # type: ignore

    def closeEvent(self, event):
        save_settings(dev_console=False)
        self.hide()
        event.ignore()

class CrashCheckDialog(QDialog):
    def __init__(self, error_code="UNKNOWN", crash_report_path=None, parent=None, tr=None):
        super().__init__(parent)
        self.tr = tr if tr else load_language()
        self.setWindowTitle(self.tr.get("crash_detected", "MaZult Crash Check"))
        self.setFixedSize(400, 250)
        self.setStyleSheet("background-color: #202020; color: white;") # type: ignore

        self.layout = QVBoxLayout()
        self.label = QLabel(self.tr.get("crash_info", "Uh oh, something went wrong."))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.layout.addWidget(self.progress)

        self.setLayout(self.layout)
        QTimer.singleShot(3000, lambda: self.show_crash_info(error_code, crash_report_path))

    def show_crash_info(self, error_code, crash_report_path):
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        title = QLabel(self.tr.get("crash_title_with_code", "Minecraft crashed with code {error_code}").format(error_code=error_code))
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc = QLabel(self.tr.get("crash_description", "An unknown error occurred. Yes, truly unknown C:\n"
                      "Possible causes: MODs, JVM, or RAM settings in launcher."))
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        fix_tips = QLabel(self.tr.get("crash_fix_tips_title", "How to fix:") + "\n" +
                          self.tr.get("crash_fix_tip_1", "- Check recently added mods.") + "\n" +
                          self.tr.get("crash_fix_tip_2", "- Lower allocated RAM if too high.") + "\n" +
                          self.tr.get("crash_fix_tip_3", "- Update Java or try another version.") + "\n" +
                          self.tr.get("crash_fix_tip_4", "- Open crash report if available."))
        fix_tips.setWordWrap(True)
        fix_tips.setAlignment(Qt.AlignmentFlag.AlignLeft)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton(self.tr.get("ok", "OK"))
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        if crash_report_path and os.path.exists(crash_report_path):
            open_btn = QPushButton(self.tr.get("open_crash_report_button", "Open Crash Report"))
            def open_report():
                try:
                    os.startfile(crash_report_path)
                except Exception as e:
                    QMessageBox.warning(self, "ERROR When open log", f"Cannot open log file:\n{e}")
            open_btn.clicked.connect(open_report)
            btn_layout.addWidget(open_btn)

        self.layout.addWidget(title)
        self.layout.addWidget(desc)
        self.layout.addWidget(fix_tips)
        self.layout.addLayout(btn_layout)

class MinecraftThread(QThread):
    finished_signal = Signal()
    log_signal = Signal(str)
    crash_detected = Signal(str, str)

    def __init__(self, command, minecraft_directory, parent=None):
        super().__init__(parent)
        self.command = command
        self.minecraft_directory = minecraft_directory
        self.process = None
        self.killed_by_user = False

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
                encoding='utf-8',
                errors='ignore'
            )
            log_lines = []
            for line in iter(self.process.stdout.readline, ''):
                self.log_signal.emit(line.strip())
                log_lines.append(line.strip())
            
            try:
                self.process.wait(timeout=2)
            except Exception:
                pass

            if self.process.poll() is None:
                print("[WARN] Minecraft process did not terminate correctly.")
                try:
                    self.process.kill()
                except Exception:
                    pass

            log_text = "\n".join(log_lines)
            if not self.killed_by_user and "Stopping!" not in log_text:
                try:
                    crash_report_path = None

                    for line in log_lines:
                        if "crash report saved to:" in line.lower():
                            possible_path = line.split("to:", 1)[1].strip().strip('"')
                            if os.path.exists(possible_path):
                                crash_report_path = possible_path
                                print(f"[DEBUG] Found crash report path from log: {crash_report_path}")
                                break

                    if not crash_report_path:
                        crash_report_dir = Path(self.minecraft_directory) / "crash-reports"
                        if crash_report_dir.exists():
                            reports = sorted(crash_report_dir.glob("*.txt"), key=os.path.getmtime, reverse=True)
                            if reports:
                                crash_report_path = str(reports[0])
                                print(f"[DEBUG] Using fallback crash report path: {crash_report_path}")

                    self.crash_detected.emit("UNKNOWN", crash_report_path)
                except Exception as e:
                    print(f"[CrashCheck] Error showing crash dialog: {e}")

        except Exception as e:
            self.log_signal.emit(f"Error launching Minecraft: {e}")
        
        self.finished_signal.emit()

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

class MaZultLauncher(QWidget):
    def show_crash_dialog(self, code, path): # type: ignore
        self.go_home()
        dialog = CrashCheckDialog(code, path, self, self.tr)
        dialog.exec()

    def update_username_combo(self):
        placeholder_text = self.tr.get("add_new_user_placeholder", "Add new user...")
        self.username_combo.blockSignals(True)
        self.username_combo.clear()

        self.users = load_users()
        
        if not self.users:
            self.username_combo.addItem(placeholder_text)
            self.username_combo.model().item(0).setEnabled(False)
            self.username_combo.setStyleSheet("QComboBox { color: #888; } QComboBox QAbstractItemView { color: #E0E0E0; }")
        else:
            self.username_combo.setStyleSheet("") # Reset stylesheet
            self.username_combo.addItems(self.users)
            
            settings = load_settings()
            saved_username = settings.get("username")

            if saved_username and saved_username in self.users:
                self.username_combo.setCurrentText(saved_username)
            elif self.users: # Default to first user if saved one is not found
                self.username_combo.setCurrentIndex(0)
                save_settings(username=self.users[0])

        self.username_combo.addItem(self.tr.get("manage_users", "Manage Users..."))

        self.username_combo.blockSignals(False)
    
    def on_username_changed(self, text):
        placeholder_text = self.tr.get("add_new_user_placeholder", "Add new user...")
        if text == self.tr.get("manage_users", "Manage Users..."):
            dialog = UserManagerDialog(self, tr=self.tr)
            dialog.exec()
            self.update_username_combo()
        elif text and text != placeholder_text:
            save_settings(username=text)

    def on_version_changed(self, index):
        selected_label = self.version_combo.itemText(index)
        selected_version_id = self.version_combo.itemData(index)

        if selected_version_id:
            if "Latest Release" in selected_label:
                save_settings(version_id="latest")
            else:
                save_settings(version_id=selected_version_id)

            if self.rpc:
                self.update_rpc_menu()

    def open_minecraft_folder(self):
        mc_dir = get_minecraft_directory()
        path = str(mc_dir)

        try:
            if sys.platform.startswith('win32'):
                os.startfile(path)
            elif sys.platform.startswith('darwin'):  # macOS
                subprocess.Popen(['open', path])
            elif sys.platform.startswith('linux'):
                subprocess.Popen(['xdg-open', path])
            else:
                QMessageBox.warning(self, self.tr.get("unsupported_os_title", "Unsupported OS"), self.tr.get("unsupported_os_folder_message", "Cannot open folder on this operating system."))
        except Exception as e:
            QMessageBox.critical(self, self.tr.get("error_title", "Error"), self.tr.get("open_folder_error", "Failed to open Minecraft folder:\n{e}").format(e=e))


    def __init__(self, update_info=None):
        super().__init__()
        self.appdata_dir = get_appdata_path()
        self.icon_path = resource_path("icon.ico")
        self.mc_process = None
        self.minecraft_thread = None
        self.download_thread = None
        self.update_info = update_info

        settings = load_settings()
        self.lang_code = settings.get("language", "en_us")
        self.tr = load_language(self.lang_code)

        self.dev_console = DevConsole(self, styles=self.load_styles(), tr=self.tr)
        if load_settings().get("dev_console", False):
            self.dev_console.show()

        self.rpc = None
        
        self.setWindowTitle(self.tr.get("launcher_title", "MaZult Launcher"))
        self.setWindowIcon(QIcon(str(self.icon_path)))
        self.setMinimumSize(900, 520)
        self.setStyleSheet(self.load_styles())
        self.page_settings = None # Initialize to None
        main_layout = QHBoxLayout(self)
        self.setLayout(main_layout)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.temp_width = 0
        self.temp_height = 0

        sidebar = QVBoxLayout()
        sidebar.setAlignment(Qt.AlignmentFlag.AlignTop)
        sidebar.setSpacing(20)
        sidebar.setContentsMargins(20, 20, 20, 20)
        
        self.username_combo = QComboBox()
        self.username_combo.currentTextChanged.connect(self.on_username_changed)
        self.update_username_combo()
        
        sidebar.addWidget(self.username_combo)

        self.noname = QPushButton(self.tr.get("home_button", "Launcher"))
        self.noname.clicked.connect(self.go_home)
        self.noname.setStyleSheet("text-align: left; padding: 10px; background-color: #353535; border: 1px solid #404040;")
        sidebar.addWidget(self.noname)

        self.update_button = QPushButton(self.tr.get("update_launcher", "Update Launcher"))
        self.update_button.clicked.connect(self.on_update_clicked)
        self.update_button.setVisible(False)
        self.update_button.setStyleSheet("background-color: #e74c3c; color: white; border: none; font-weight: bold; font-size: 14px; border-radius: 4px;")
        
        if self.update_info:
            self.update_button.setVisible(True)
        
        sidebar.addWidget(self.update_button)

        self.settings_button_left = QPushButton(self.tr.get("settings", "Settings"))
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

        self.page_home = QWidget()
        content_layout = QVBoxLayout()
        self.page_home.setLayout(content_layout)
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(20, 20, 20, 20)

        self.page_settings = SettingsDialog(self, self.tr) # Re-use SettingsDialog as a widget
        self.page_settings.refreshVersions.connect(self.load_versions)

        header_layout = QHBoxLayout()
        title = QLabel("Minecraft")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))

        open_folder_button = QPushButton(self.tr.get("open_folder", "📂"))
        open_folder_button.setFixedSize(30, 30)
        open_folder_button.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: #2D2D2D;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #404040;
            }
        """)
        open_folder_button.clicked.connect(self.open_minecraft_folder)

        refresh_button = QPushButton("↻")
        refresh_button.setFixedSize(30, 30)
        refresh_button.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: #2D2D2D;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #404040;
            }
        """)
        refresh_button.clicked.connect(self.load_versions)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(open_folder_button)
        header_layout.addWidget(refresh_button)
        content_layout.addLayout(header_layout)

        version_label = QLabel(self.tr.get("select_version", "Select Version:"))
        self.version_combo = QComboBox()
        self.version_combo.currentIndexChanged.connect(self.on_version_changed)
        self.load_versions()
        content_layout.addWidget(version_label)
        content_layout.addWidget(self.version_combo) # type: ignore

        self.install_loader_btn = QPushButton(self.tr.get("install_mod_loader_button", "Install Mod Loader"))
        self.install_loader_btn.clicked.connect(self.open_modloader_dialog)
        content_layout.addWidget(self.install_loader_btn)
        
        content_layout.addStretch()

        self.progress_label = QLabel()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        self.progress_label.hide()
        self.progress_bar.hide()
        content_layout.addWidget(self.progress_label)
        content_layout.addWidget(self.progress_bar)
        
        self.play_button = QPushButton(self.tr.get("play", "Play"))
        self.play_button.setObjectName("playButton")
        self.play_button.setStyleSheet(self.load_styles())
        self.play_button.clicked.connect(self.on_play_clicked)
        self.is_downloading = False

        content_layout.addWidget(self.play_button)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.page_home)     # Index 0
        self.stacked_widget.addWidget(self.page_settings) # Index 1

        main_layout.addWidget(self.stacked_widget)

        self.connect_rpc()

    def go_home(self):
        self.stacked_widget.setCurrentIndex(0)

    def open_settings_dialog(self):
        if self.page_settings:
            self.page_settings.deleteLater()
        self.page_settings = SettingsDialog(self, self.tr)
        self.page_settings.refreshVersions.connect(self.load_versions)
        self.stacked_widget.insertWidget(1, self.page_settings)
        self.stacked_widget.setCurrentIndex(1)

    def open_modloader_dialog(self):
        dialog = ModLoaderDialog(self, tr=self.tr)
        if dialog.exec():
            self.load_versions()

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
                    details=self.tr.get("rpc_status_menu", "In the menu"),
                    large_image="mzlauncher",
                    large_text="MaZult Launcher", # type: ignore
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
                    state=self.tr.get("rpc_status_launching_version", "Launching Minecraft {version_id}").format(version_id=version_id),
                    details=self.tr.get("launching", "Launching..."),
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
                    state=self.tr.get("rpc_status_playing_version", "Playing Minecraft {version_id}").format(version_id=version_id),
                    details=self.tr.get("rpc_status_ingame", "In game"),
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
            latest_version, download_url = self.update_info # type: ignore
            reply = QMessageBox.question(self, self.tr.get("update_available", "Update Available"),
                                         f"A new version is available: {latest_version}. Do you want to download the update?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                webbrowser.open(download_url)
                self.close()
                QApplication.instance().quit()

    def on_minecraft_finished(self):
        if self.minecraft_thread and self.minecraft_thread.isRunning():
            self.minecraft_thread.quit()
            self.minecraft_thread.wait(1000)
            self.minecraft_thread = None

        if self.play_button and not self.play_button.parent() is None:
            self.play_button.setText(self.tr.get("play", "Play"))
            self.play_button.setEnabled(True)
            self.play_button.setStyleSheet(self.load_styles())
            self.dev_console.set_kill_button_enabled(False)

            self.settings_button_left.setEnabled(True)
            self.username_combo.setEnabled(True)
            self.version_combo.setEnabled(True)

            self.mc_process = None
            self.minecraft_thread = None
            settings = load_settings()
            hide_on_launch = settings.get("hide_on_launch", True)
            if hide_on_launch:
                print("[Launcher] I'm here :)")
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
        
        all_versions_data = {}

        for label, version_id in available_versions:
            all_versions_data[version_id] = {
                "label": label,
                "is_installed": version_id in installed_versions_set
            }

        if show_installed:
            for version_id in installed_versions:
                if version_id not in all_versions_data:
                    all_versions_data[version_id] = {
                        "label": version_id, 
                        "is_installed": True
                    }

        def sort_key_packaging(v_id):
            is_installed = all_versions_data[v_id].get("is_installed", False) and show_installed
            return (is_installed, minecraft_version_key(v_id))
        sorted_version_ids = sorted(all_versions_data.keys(), key=sort_key_packaging, reverse=True)

        for version_id in sorted_version_ids:
            data = all_versions_data[version_id]
            display_label = data["label"]

            if version_id == latest_release_id:
                if data["is_installed"] and show_installed:
                    self.version_combo.addItem(f"(Installed) Latest Release ({version_id})", version_id)
                else:
                    self.version_combo.addItem(f"Latest Release ({version_id})", version_id)

                if data["is_installed"] and show_installed:
                    self.version_combo.addItem(f"(Installed) Release - {version_id}", version_id)
                else:
                    self.version_combo.addItem(f"Release - {version_id}", version_id)
                continue

            if data["is_installed"] and show_installed:
                display_label = f"(Installed) {display_label}"
            
            self.version_combo.addItem(display_label, version_id)
        
        if current_version:
            matching_indexes = []
            for i in range(self.version_combo.count()):
                if self.version_combo.itemData(i) == current_version:
                    label = self.version_combo.itemText(i)
                    matching_indexes.append((i, label))

            if matching_indexes:
                preferred_index = None
                for idx, label in matching_indexes:
                    if "Release -" in label and "Latest" not in label:
                        preferred_index = idx
                        break
                if preferred_index is None:
                    preferred_index = matching_indexes[0][0]

                self.version_combo.setCurrentIndex(preferred_index)
                print(f"[DEBUG] Selected version restored: {self.version_combo.itemText(preferred_index)}")
            else:
                print(f"[DEBUG] Saved version {current_version} not found, fallback to latest release.")
                if latest_release_id:
                    index = self.version_combo.findData(latest_release_id)
                    if index != -1:
                        self.version_combo.setCurrentIndex(index)
        else:
            if latest_release_id:
                index = self.version_combo.findData(latest_release_id)
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
        
        QProgressBar {
            background-color: #2D2D2D;
            border: 1px solid #404040;
            border-radius: 5px;
            text-align: center;
            color: #E0E0E0;
            height: 12px;
        }
        QProgressBar::chunk {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b2f78, stop:1 #e133a0);
            border-radius: 4px;
            margin: 1px;
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

    def after_download(self, selected_version_id, options, settings, success=True):
        print("[DEBUG] after_download triggered")

        self.is_downloading = False
        self.progress_label.hide()
        self.progress_bar.hide()

        if not success or (self.download_thread and self.download_thread._cancelled):
            print(self.tr.get("download_cancelled_log", "Download process was cancelled."))
            self.reset_after_cancel()
            return

        if self.download_thread:
            self.download_thread = None

        # Proceed to launch
        self._start_minecraft_process(selected_version_id, options, settings)


    def reset_after_cancel(self):
        self.is_downloading = False
        self.progress_label.hide() # type: ignore
        self.progress_bar.hide()
        self.play_button.setText(self.tr.get("play", "Play"))
        self.play_button.setEnabled(True)
        self.play_button.setStyleSheet(self.load_styles())

        self.settings_button_left.setEnabled(True)
        self.username_combo.setEnabled(True)
        self.version_combo.setEnabled(True)

        self.update_rpc_menu()

    def on_play_clicked(self):
        print(self.tr.get("debug_thread_created", "[DEBUG] Thread created"))
        # Nếu thread Minecraft cũ vẫn còn, thì hủy trước khi tạo cái mới
        if self.minecraft_thread and self.minecraft_thread.isRunning():
            try:
                print(self.tr.get("warn_previous_thread_running", "[WARN] Previous Minecraft thread still running, attempting cleanup..."))
                self.minecraft_thread.terminate()
                self.minecraft_thread.wait(2000) # type: ignore
                self.minecraft_thread = None
            except Exception as e:
                print(f"{self.tr.get('error_cleanup_old_thread', '[ERROR] Failed to cleanup old thread:')} {e}")

        if self.is_downloading and self.download_thread and self.download_thread.isRunning():
            print(self.tr.get("download_cancelled_by_user", "Download canceled by user."))
            self.download_thread.cancel()
            
            self.play_button.setEnabled(False)
            self.play_button.setText(self.tr.get("wait", "Please wait"))
            self.play_button.setStyleSheet("""
                QPushButton#playButton {
                    background-color: #2a1c36;
                    color: white;
                    border: none;
                    font-weight: bold;
                    font-size: 16px;
                }
            """)
            self.progress_label.setText(self.tr.get("cancelling", "Cancelling..."))
            
            return

        username = self.username_combo.currentText()
        if not self.users or username == self.tr.get("manage_users", "Manage Users...") or username == self.tr.get("add_new_user_placeholder", "Add new user..."):
            QMessageBox.warning(self, self.tr.get("invalid_user", "Invalid User"), self.tr.get("no_user_selected", "Please add or select a user before playing."))
            return

        selected_version_id = self.version_combo.currentData()
        if not selected_version_id:
            QMessageBox.warning(self, self.tr.get("no_version_selected", "No Version Selected"), self.tr.get("no_version_selected", "Please select a Minecraft version to play."))
            return
        
        minecraft_directory = get_minecraft_directory()
        settings = load_settings()
        skip_check = settings.get("skip_version_check", False)

        version_dir = minecraft_directory / "versions" / selected_version_id
        version_json = version_dir / f"{selected_version_id}.json"

        if skip_check and version_dir.exists() and version_json.exists():
            print("[Launch] Skip version verification enabled → launching instantly")
            options = self.prepare_mc_options()
            if options:
                self._start_minecraft_process(selected_version_id, options, settings)
            else:
                # prepare_mc_options will show a message box on error
                self.reset_after_cancel()
            return

        print("[Launch] Normal install / verify flow")

        settings = load_settings()
        allocated_ram_mb = settings.get("ram_mb", 2048)
        
        user_uuid = get_mojang_uuid(username)
        if user_uuid is None:
            print(self.tr.get("mojang_uuid_offline_fallback", "Cannot get Mojang UUID for {username}. Using offline UUID.").format(username=username))
            user_uuid = str(uuid.uuid3(uuid.NAMESPACE_URL, "OfflinePlayer:" + username))
        user_token = user_uuid

        jvm_args = settings.get("jvm_args", [])
        
        default_jvm_args = [f"-Xmx{allocated_ram_mb}M", "-Xms512M"]
        final_jvm_args = []
        overridden_args = set()

        for arg in jvm_args:
            if arg.startswith("-Xmx"):
                print(self.tr.get("ignoring_xmx_arg", "Ignoring user-provided -Xmx argument."))
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
        self.progress_label.setText(self.tr.get("preparing_download", "Preparing download..."))
        self.progress_bar.setValue(0)
        self.update_rpc_downloading(selected_version_id)

        self.is_downloading = True
        self.play_button.setText(self.tr.get("cancel", "Cancel"))
        self.play_button.setEnabled(True)
        self.play_button.setStyleSheet(self.load_styles())
        
        self.settings_button_left.setEnabled(False)
        self.username_combo.setEnabled(False)
        self.version_combo.setEnabled(False)

        self.download_thread = DownloadThread(selected_version_id, minecraft_directory, self.tr)
        self.download_thread.status_signal.connect(self.on_set_status)
        self.download_thread.value_signal.connect(self.on_set_progress)
        self.download_thread.max_signal.connect(self.on_set_max)
        self.download_thread.progress_signal.connect(self.on_set_file)
        self.download_thread.finished.connect(self.download_thread.deleteLater)
        self.download_thread.finished_signal.connect(lambda success: self.after_download(selected_version_id, options, settings, success))
        self.download_thread.start()
    
    def prepare_mc_options(self):
        
        username = self.username_combo.currentText()
        if not self.users or username == self.tr.get("manage_users", "Manage Users...") or username == self.tr.get("add_new_user_placeholder", "Add new user..."):
            QMessageBox.warning(self, self.tr.get("invalid_user", "Invalid User"), self.tr.get("no_user_selected", "Please add or select a user before playing."))
            return None

        settings = load_settings()
        allocated_ram_mb = settings.get("ram_mb", 2048)

        user_uuid = get_mojang_uuid(username)
        if user_uuid is None:
            print(self.tr.get("mojang_uuid_offline_fallback", "Cannot get Mojang UUID for {username}. Using offline UUID.").format(username=username))
            user_uuid = str(uuid.uuid3(uuid.NAMESPACE_URL, "OfflinePlayer:" + username))
        user_token = user_uuid

        jvm_args = settings.get("jvm_args", [])
        default_jvm_args = [f"-Xmx{allocated_ram_mb}M", "-Xms512M"]
        final_jvm_args = []
        overridden_args = set()

        for arg in jvm_args:
            if arg.startswith("-Xmx"): print(self.tr.get("ignoring_xmx_arg", "Ignoring user-provided -Xmx argument."))
            elif arg.startswith("-Xms"): final_jvm_args.append(arg); overridden_args.add("Xms")
            else: final_jvm_args.append(arg)

        for arg in default_jvm_args:
            if arg.startswith("-Xms") and "Xms" in overridden_args: continue
            final_jvm_args.append(arg)

        return {"username": username, "uuid": user_uuid, "token": user_token, "jvmArguments": final_jvm_args}

    def _start_minecraft_process(self, version_id, options, settings):
        
        try:
            java_mode = settings.get("java_mode", "default")
            java_path = settings.get("java_path", "")

            if java_mode == "custom":
                if java_path and os.path.isdir(java_path):
                    custom_java = find_java_executable(java_path)
                    if custom_java:
                        options["executablePath"] = custom_java
                    else:
                        QMessageBox.critical(self,
                            self.tr.get("java_error_title", "Java Error"),
                            self.tr.get("no_valid_java_in_folder_error", 
                                "No valid Java executable found in this folder.\n"
                                "Please check the directory.\n\n"
                                "Supported formats:\n"
                                "- Windows: java.exe / javaw.exe\n"
                                "- Linux/macOS: java")
                        )
                        self.reset_after_cancel()
                        return
                else:
                    QMessageBox.critical(self, self.tr.get("java_error_title", "Java Error"), 
                                         self.tr.get("custom_java_path_invalid_error", "Custom Java path is selected but the path is invalid or empty."))
                    self.reset_after_cancel()
                    return

            command = minecraft_launcher_lib.command.get_minecraft_command(
                version_id,
                get_minecraft_directory(),
                options
            )
            print("Launching with command:", " ".join(command))
            self.update_rpc_game(version_id)

            self.play_button.setText(self.tr.get("launching", "Launching..."))
            self.play_button.setEnabled(False)
            self.play_button.setStyleSheet(self.load_styles())

            hide_on_launch = settings.get("hide_on_launch", True)
            if hide_on_launch:
                print("[Launcher] i'm hide :)")
                self.hide()
                self.temp_width = self.width()
                self.temp_height = self.height()

            self.minecraft_thread = MinecraftThread(command, get_minecraft_directory(), self)
            self.minecraft_thread.finished_signal.connect(self.on_minecraft_finished)
            self.minecraft_thread.log_signal.connect(self.on_minecraft_log)
            self.minecraft_thread.crash_detected.connect(self.show_crash_dialog)
            self.dev_console.set_kill_button_enabled(True)
            self.minecraft_thread.start()

        except Exception as e:
            QMessageBox.critical(self, self.tr.get("launch_error", "Launch Error"), f"{self.tr.get('launch_error_message', 'Failed to launch Minecraft:')}\n{e}")
            self.reset_after_cancel()
            self.show()

class DownloadThread(QThread):
    progress_signal = Signal(str, int, int, float)
    status_signal = Signal(str)
    value_signal = Signal(int)
    max_signal = Signal(int)
    finished_signal = Signal(bool) 

    def __init__(self, version_id, minecraft_directory, tr=None):
        super().__init__()
        self.version_id = version_id
        self.minecraft_directory = minecraft_directory
        self._cancelled = False
        self.is_running = True
        self.tr = tr if tr else {}
        print(self.tr.get("debug_download_thread_init", "[DEBUG] DownloadThread init"))
        
    def cancel(self):
        self._cancelled = True
        
    def run(self):
        print(self.tr.get("debug_download_thread_run_start", "[DEBUG] DownloadThread run start"))
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
                print(self.tr.get("download_thread_cancelled_log", "Download thread finished because it was cancelled."))
            else:
                print(f"{self.tr.get('download_error_log', 'Download error:')} {e}")
            self.finished_signal.emit(False)
        finally:
            self.is_running = False

    def _on_file(self, text, cur, tot, spd):
        if self._cancelled:
            print("Download aborted safely.")
            raise Exception("Download cancelled")
        self.progress_signal.emit(text, cur, tot, spd)

class Splash(QWidget):
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.setFixedSize(360, 200)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground) # type: ignore

        self.progress = 0
        self.use_timer = True # type: ignore

        layout = QVBoxLayout(self)
        self.main_layout = layout # Store layout reference
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(14)

        self.title = QLabel("MaZult Launcher")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self.title.setStyleSheet("color: white;")
        
        self.subtitle = QLabel()
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setFont(QFont("Segoe UI", 11))
        self.subtitle.setStyleSheet("color:#BBBBBB;")
        
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(True)
        self.bar.setFormat("%p%")
        self.bar.setAlignment(Qt.AlignCenter)
        self.bar.setFixedHeight(18)

        self.bar.setStyleSheet("""
            QProgressBar {
                background-color: #2b2b2b;
                border-radius: 9px;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #6a5acd;
                border-radius: 9px;
            }
        """)

        layout.addStretch()
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(6)
        layout.addWidget(self.bar)
        layout.addStretch()

        self.steps = [
            (5, "splash_loading_config"),
            (30, "splash_preparing_ui"),
            (55, "splash_init_modules"),
            (80, "splash_checking_env"),
            (95, "splash_finalizing")
        ]

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(25)

    def _tick(self):
        if not self.use_timer:
            return

        if self.progress < 100:
            self.progress += 1
            self.bar.setValue(self.progress)

            for p, key in self.steps:
                if self.progress == p:
                    self.subtitle.setText(self.tr.get(key, "...")) # type: ignore
        else:
            if self.use_timer:
                self.use_timer = False
                self.finished.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(32, 32, 32))
        p.drawRoundedRect(self.rect(), 22, 22)

    def set_translator(self, tr_func):
        self.tr = tr_func
        self.subtitle.setText(self.tr.get("splash_starting", "Starting..."))

    
    def set_progress(self, value, text=None):
        self.use_timer = False
        self.progress = max(0, min(100, value))
        self.bar.setValue(self.progress)
        if text:
            self.subtitle.setText(text)
        QApplication.processEvents()
        if self.progress >= 100:
            self.finished.emit()
            
    
    def resume_timer(self, start_value=0, text=None):
        self.progress = start_value
        self.bar.setValue(self.progress)
        if text:
            self.subtitle.setText(text)
        self.use_timer = True

    def show_error_and_close(self, title, message):
        
        self.use_timer = False
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        error_title = QLabel(title)
        error_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        error_title.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(error_title)
        self.main_layout.addWidget(QLabel(message))

def download_update_with_progress(dest_dir, splash):
    url = get_updater_asset_url()

    base_dir = get_launcher_root()
    temp_dir = base_dir / "temp_update"
    temp_dir.mkdir(exist_ok=True)

    zip_path = temp_dir / "update.zip"

    print(f"[UPDATER] Download URL: {url}")
    print(f"[UPDATER] Saving to: {zip_path.resolve()}")

    splash.set_progress(1, splash.tr.get("updater_connecting", "Connecting to update server..."))

    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()

    total = int(r.headers.get("Content-Length", 0))
    downloaded = 0

    with open(zip_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if not chunk:
                continue
            f.write(chunk)
            downloaded += len(chunk)

            if total > 0:
                percent = int(downloaded * 100 / total)
                splash.set_progress(
                    min(percent, 90),
                    splash.tr.get("updater_downloading", "Downloading update... {percent}%").format(percent=percent)
                )

    print(f"[UPDATER] Download completed: {zip_path.resolve()}")
    return zip_path



def get_updater_asset_url():
    api_url = "https://api.github.com/repos/LunarMoonDLCT/MZassets/releases/latest"
    r = requests.get(api_url, timeout=15)
    r.raise_for_status()
    data = r.json()

    is_windows = sys.platform.startswith("win")
    asset_name_fragment = "Win.zip" if is_windows else "Other-OS.zip"

    for asset in data.get("assets", []):
        if asset_name_fragment in asset.get("name", ""):
            return asset.get("browser_download_url")

    raise RuntimeError("Updater asset not found for this OS")



def download_file(url, dest):
    r = requests.get(url, stream=True, timeout=20)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

def apply_update(zip_path, splash: Splash):
    base_dir = get_launcher_root()
    temp_dir = base_dir / "temp_update"

    splash.set_progress(92, splash.tr.get("updater_extracting", "Extracting files..."))

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(temp_dir)

    splash.set_progress(94, splash.tr.get("updater_preparing_install", "Preparing to install..."))

    for item in base_dir.iterdir():
        if item.name in ("bin", "app", "temp_update","unins000.exe", "unins000.dat"):
            continue
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        except Exception as e:
            print(f"[UPDATER] Failed to remove {item}: {e}")

    splash.set_progress(96, splash.tr.get("updater_installing", "Copying new files..."))

    for item in temp_dir.iterdir():
        if item.is_file() and item.name.lower() == "update.zip":
            continue
        dest = base_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    splash.set_progress(98, splash.tr.get("updater_cleaning", "Cleaning up..."))

def cleanup_update():
    temp_dir = get_launcher_root() / "temp_update"
    try:
        shutil.rmtree(temp_dir)
        print("[UPDATER] temp_update cleaned")
    except Exception as e:
        print(f"[UPDATER] Cleanup failed: {e}")

def get_launcher_root():
    return Path(MAIN_APP_DIR)

def is_admin():
    
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False
        
def relaunch_as_admin(extra_args=None):
    if extra_args is None:
        extra_args = sys.argv[1:]

    params = " ".join(f'"{arg}"' for arg in extra_args)
    exe = sys.executable

    ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        exe,
        params,
        None,
        1                 # SW_SHOWNORMAL
    )
    sys.exit(0)

def get_latest_updater_info():
    
    r = requests.get(GITHUB_API_URL, timeout=10)
    r.raise_for_status()
    data = r.json()

    latest_ver = data["tag_name"].lstrip("v")
    zip_url = None

    for asset in data.get("assets", []):
        if asset.get("name", "").endswith(".zip"):
            zip_url = asset["browser_download_url"]
            break

    if not zip_url:
        raise RuntimeError("No updater zip file found in the latest release.")

    return latest_ver, zip_url

class UpdateCheckThread(QThread):
    
    update_available = Signal(str, str) # version, url
    up_to_date = Signal()
    error_occurred = Signal(str)

    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version

    def run(self):
        if not self.current_version:
            self.up_to_date.emit()
            return

        try:
            latest_ver, zip_url = get_latest_updater_info()
            print(f"[UPDATER] Current: {self.current_version} | Latest: {latest_ver}")

            if Version(self.current_version) < Version(latest_ver):
                print("[UPDATER] New version available.")
                self.update_available.emit(latest_ver, zip_url)
            else:
                print("[UPDATER] Launcher is up to date.")
                self.up_to_date.emit()

        except requests.exceptions.RequestException as e:
            print(f"[UPDATER] Network error during update check: {e}")
            self.error_occurred.emit("Network error. Could not check for updates.")
        except Exception as e:
            print(f"[UPDATER] Update check/process failed: {e}")
            self.error_occurred.emit(f"Update check failed: {e}")

def start_update_process(splash: Splash):
    
    try:
        print("[UPDATER] Permissions OK. Starting update process.")
        splash.bar.setRange(0, 100)
        splash.set_progress(5, splash.tr.get("updater_starting", "Starting update...")) # type: ignore

        base_dir = get_launcher_root() # type: ignore
        temp_dir = base_dir / "temp_update"
        
        zip_path = download_update_with_progress(temp_dir, splash)
        apply_update(zip_path, splash)
        cleanup_update()

        splash.set_progress(100, splash.tr.get("updater_complete", "Update complete. Preparing Launcher")) # type: ignore

    except Exception as e:
        print(f"[UPDATER] Update process failed: {e}")
        splash.show_error_and_close(splash.tr.get("updater_failed_title", "Update Failed"), splash.tr.get("updater_apply_failed", "Could not apply update.\n{e}").format(e=e)) # type: ignore


if __name__ == "__main__":
    def global_exception_hook(exctype, value, tb):
        settings = load_settings()
        tr = load_language(settings.get("language", "en_us"))

        error_text = "".join(traceback.format_exception(exctype, value, tb))
        try:
            log_dir = get_appdata_path() / "logs"
            os.makedirs(log_dir, exist_ok=True)
            log_file = log_dir / f"crash_{int(time.time())}.log"
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(error_text)
            print(f"[CRASH LOG SAVED] -> {log_file}")
        except Exception as e:
            print(f"[CRASH LOGGING FAILED] {e}")

        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle(
                tr.get("launcher_title", "MaZult Launcher")
                + " - "
                + tr.get("crash_detected", "Crash Detected")
            )
            msg.setText(
                tr.get(
                    "critical_error",
                    "The launcher has encountered a critical error and will close.",
                )
            )
            msg.setInformativeText(str(value))
            msg.setDetailedText(error_text)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
        except Exception as e:
            print(f"Failed to show crash dialog: {e}")

        sys.__excepthook__(exctype, value, tb)
        sys.exit(1)

    sys.excepthook = global_exception_hook

    def get_launcher_root_main():
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).resolve().parent.parent
        else:
            return Path(__file__).resolve().parent.parent

    MAIN_APP_DIR = get_launcher_root_main()

    app = QApplication(sys.argv)

    settings = load_settings()
    tr = load_language(settings.get("language", "en_us"))
    
    splash = Splash()
    splash.set_translator(tr)

    appdata_path = get_appdata_path()
    os.makedirs(appdata_path, exist_ok=True)
    os.chdir(appdata_path)

    shutil.rmtree(get_tmp_dir(), ignore_errors=True)

    script_dir = Path(MAIN_APP_DIR)

    is_windows = sys.platform.startswith("win32")
    is_linux = sys.platform.startswith("linux")
    is_mac = sys.platform.startswith("darwin")
    
    launcher_args = parse_launcher_args()
    print("[Args]", launcher_args)
    
    is_launcher_arg = launcher_args["has_launcher"]

    if (is_windows or is_linux or is_mac) and not is_launcher_arg:
        print(f"Launcher arg not present. Attempting to start main launcher.")
        print(f"Script directory: {script_dir}")
    
        frozen_base_dir = Path(os.path.dirname(sys.executable)).parent
    
        if is_windows:
            launcher_name = "MaZult Launcher.exe"
        else:
            launcher_name = "MaZult Launcher.py" 
    
        exe_path = frozen_base_dir / launcher_name
    
        print(f"Updater path: {exe_path}")
    
        if exe_path.exists():
            try:
                print("Found Launcher, launching...")
                if is_windows:
                    subprocess.Popen([str(exe_path), "--Launcher"])
                else:
                    subprocess.Popen(["python3", str(exe_path), "--Launcher"])
                sys.exit(0)
            except Exception as e:
                print(f"Error when launching launcher, proceeding with current instance: {e}")
        else:
            print("No launcher found, run default app")
    
    
    main_window = MaZultLauncher()
    main_window.hide()

    def open_main_window():
        if not main_window.isVisible(): # Prevent multiple calls
            splash.close()
            main_window.show()
            main_window.raise_()
            main_window.activateWindow()
            app.main_window = main_window

    splash.finished.connect(open_main_window)

    def on_update_available(version, url):
        splash.use_timer = False

        if is_windows and not is_admin():
            print("[UPDATER] Requesting administrator privileges...")
            splash.set_progress(0, tr.get("updater_waiting_permission", "Please allow administrator permission to update..."))
            relaunch_as_admin()
            return

        start_update_process(splash)

    def on_up_to_date(): # type: ignore
        splash.use_timer = False
        splash.set_progress(50, tr.get("updater_up_to_date", "Launcher is up to date."))
        QTimer.singleShot(1200, lambda: splash.resume_timer(splash.progress, tr.get("splash_preparing_launcher", "Preparing launcher...")))

    def on_error(message): # type: ignore
        splash.use_timer = False
        splash.set_progress(50, tr.get("updater_failed", "Update check failed."))
        QTimer.singleShot(1500, lambda: splash.resume_timer(splash.progress, tr.get("splash_starting_anyway", "Starting launcher...")))

    splash.show()
    splash.set_progress(0, tr.get("updater_checking", "Checking for updates..."))
    splash.bar.setRange(0, 0)

    update_thread = UpdateCheckThread(launcher_args["updater_ver"])
    update_thread.update_available.connect(on_update_available)
    update_thread.up_to_date.connect(on_up_to_date)
    update_thread.error_occurred.connect(on_error)
    update_thread.start()

    app.update_thread = update_thread

    sys.exit(app.exec())
