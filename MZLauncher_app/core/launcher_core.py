import os
import sys
import shutil
import json
import webbrowser
import psutil
import requests
import time
import subprocess

import xml.etree.ElementTree as ET
import threading
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
from pypresence import Presence
from pypresence.exceptions import InvalidID, PipeClosed
from packaging.version import Version, InvalidVersion
import minecraft_launcher_lib.microsoft_account as msa
import uuid 

from MZLauncher_app.settings.settings import get_minecraft_directory, load_settings, save_settings, load_accounts, save_accounts
from MZLauncher_app.download.download import DownloadThread
from MZLauncher_app.minecraft_account.account import UserManagerDialog
from MZLauncher_app.gui.main_window import MainWindow
from MZLauncher_app.gui.pages.home_page import HomePage
from MZLauncher_app.gui.pages.setting_page import SettingsPage
from MZLauncher_app.gui.pages.instance_page import InstancePage, load_instances
from MZLauncher_app.gui.pages.modloader_page import ModLoaderPage

DISCORD_CLIENT_ID = "1410269369748946986"
from MZLauncher_app.core.utils import (list_available_languages, load_language, resource_path, get_appdata_path, get_tmp_dir,
                                       get_installed_versions, get_available_versions, minecraft_version_key)
CLIENT_ID = "YOUR_CLIENT_ID_HERE"  # Replace with your Azure App Client ID
REDIRECT_URI = "http://localhost:12782/callback"

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

class DevConsole(QWidget):
    append_signal = Signal(str)
    
    def __init__(self, parent_launcher, styles="", tr=None):
        super().__init__()
        self.parent_launcher = parent_launcher
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
                print(self.tr.get("minecraft_process_killed_log", "Minecraft process killed.")) 
                self.set_kill_button_enabled(False)
                if self.parent_launcher.isHidden():
                    self.parent_launcher.show()
                    self.parent_launcher.update_rpc_menu()
            except Exception as e:
                print(self.tr.get("kill_minecraft_failed_log", "Failed to kill Minecraft process: {e}").format(e=e)) 

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
        self.setStyleSheet("background-color: #202020; color: white;") 

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
    def show_crash_dialog(self, code, path):
        self.go_home()
        dialog = CrashCheckDialog(code, path, self, self.tr)
        dialog.exec()

    def update_username_combo(self):
        placeholder_text = self.tr.get("add_new_user_placeholder", "Add new user...")
        self.home_page.username_combo.blockSignals(True)
        self.home_page.username_combo.clear()
        
        accounts = load_accounts()
        self.users = [] 

        if not accounts:
            self.home_page.username_combo.addItem(placeholder_text)
            self.home_page.username_combo.model().item(0).setEnabled(False)
            self.home_page.username_combo.setStyleSheet("QComboBox { color: #888; } QComboBox QAbstractItemView { color: #E0E0E0; }")
        else:
            self.home_page.username_combo.setStyleSheet("")
            for acc in accounts:
                if acc.get("type") == "microsoft":
                    name = f"(microsoft) {acc.get('name', 'Unknown')}"
                else:
                    name = f"(offline) {acc.get('name', 'Unknown')}"
                self.home_page.username_combo.addItem(name)
                self.users.append(name) 
            
            settings = load_settings()
            saved_username = settings.get("username")
            if saved_username and self.home_page.username_combo.findText(saved_username) != -1:
                self.home_page.username_combo.setCurrentText(saved_username)
            elif self.users:
                self.home_page.username_combo.setCurrentIndex(0)
                save_settings(username=self.users[0])

        self.home_page.username_combo.addItem(self.tr.get("manage_users", "Manage Users..."))

        self.home_page.username_combo.blockSignals(False)
    
    def on_username_changed(self, text):
        placeholder_text = self.tr.get("add_new_user_placeholder", "Add new user...")
        if text == self.tr.get("manage_users", "Manage Users..."):
            dialog = UserManagerDialog(self, tr=self.tr)
            dialog.exec()
            self.update_username_combo()
            self.home_page.username_combo.setCurrentIndex(0) # Reset to first user after managing
        elif text and text != placeholder_text:
            save_settings(username=text)

    def get_current_game_directory(self) -> Path:
        selected_data = self.home_page.version_combo.currentData()
        if isinstance(selected_data, str) and selected_data.startswith("instance-"):
            instance_name = selected_data.replace("instance-", "")
            instances = load_instances()
            instance_info = next((inst for inst in instances if inst['name'] == instance_name), None)
            if instance_info and 'path' in instance_info:
                print(f"[DEBUG] Using instance directory: {instance_info['path']}")
                return Path(instance_info['path'])
            print(f"[WARN] Instance '{instance_name}' not found or path missing, falling back to global directory.")
        return get_minecraft_directory()

    def open_user_manager(self):
        dialog = UserManagerDialog(self, tr=self.tr)
        dialog.exec()
        self.update_username_combo()

    def on_version_changed(self, index):
        selected_label = self.home_page.version_combo.itemText(index)
        selected_version_id = self.home_page.version_combo.itemData(index)

        if selected_version_id:
            if "Latest Release" in selected_label:
                save_settings(version_id="latest")
            else:
                save_settings(version_id=selected_version_id)

            if self.rpc:
                self.update_rpc_menu()
            
            self.home_page.update_mods_count()
            self.home_page.update_worlds_count()
            self.home_page.update_resource_packs_count()
            self.home_page.update_shader_packs_count()

    def open_minecraft_folder(self):
        mc_dir = self.get_current_game_directory()
        path = str(mc_dir)

        try:
            if sys.platform.startswith('win32'):
                os.startfile(path)
            elif sys.platform.startswith('darwin'):
                subprocess.Popen(['open', path])
            elif sys.platform.startswith('linux'):
                subprocess.Popen(['xdg-open', path])
            else:
                QMessageBox.warning(self, self.tr.get("unsupported_os_title", "Unsupported OS"), self.tr.get("unsupported_os_folder_message", "Cannot open folder on this operating system."))
        except Exception as e:
            QMessageBox.critical(self, self.tr.get("error_title", "Error"), self.tr.get("open_folder_error", "Failed to open Minecraft folder:\n{e}").format(e=e))

    def open_mods_folder(self):
        mc_dir = self.get_current_game_directory()
        mods_path = mc_dir / "mods"
        if not mods_path.exists():
            try:
                mods_path.mkdir(parents=True)
            except Exception as e:
                QMessageBox.critical(self, self.tr.get("create_dir_failed", "Creation Failed"), f"Failed to create mods directory:\nError: {e}")
                return
        
        path = str(mods_path)
        try:
            if sys.platform.startswith('win32'):
                os.startfile(path)
            elif sys.platform.startswith('darwin'):
                subprocess.Popen(['open', path])
            elif sys.platform.startswith('linux'):
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            QMessageBox.critical(self, self.tr.get("error_title", "Error"), self.tr.get("open_folder_error", "Failed to open Minecraft folder:\n{e}").format(e=e))

    def open_worlds_folder(self):
        mc_dir = self.get_current_game_directory()
        worlds_path = mc_dir / "saves"
        if not worlds_path.exists():
            try:
                worlds_path.mkdir(parents=True)
            except Exception as e:
                QMessageBox.critical(self, self.tr.get("create_dir_failed", "Creation Failed"), f"Failed to create saves directory:\nError: {e}")
                return
        
        path = str(worlds_path)
        try:
            if sys.platform.startswith('win32'):
                os.startfile(path)
            elif sys.platform.startswith('darwin'):
                subprocess.Popen(['open', path])
            elif sys.platform.startswith('linux'):
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            QMessageBox.critical(self, self.tr.get("error_title", "Error"), self.tr.get("open_folder_error", "Failed to open Minecraft folder:\n{e}").format(e=e))

    def open_resource_packs_folder(self):
        mc_dir = self.get_current_game_directory()
        packs_path = mc_dir / "resourcepacks"
        if not packs_path.exists():
            try:
                packs_path.mkdir(parents=True)
            except Exception as e:
                QMessageBox.critical(self, self.tr.get("create_dir_failed", "Creation Failed"), f"Failed to create resourcepacks directory:\nError: {e}")
                return
        
        path = str(packs_path)
        try:
            if sys.platform.startswith('win32'):
                os.startfile(path)
            elif sys.platform.startswith('darwin'):
                subprocess.Popen(['open', path])
            elif sys.platform.startswith('linux'):
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            QMessageBox.critical(self, self.tr.get("error_title", "Error"), self.tr.get("open_folder_error", "Failed to open resource packs folder:\n{e}").format(e=e))

    def open_shaderpacks_folder(self):
        mc_dir = self.get_current_game_directory()
        packs_path = mc_dir / "shaderpacks"
        if not packs_path.exists():
            try:
                packs_path.mkdir(parents=True)
            except Exception as e:
                QMessageBox.critical(self, self.tr.get("create_dir_failed", "Creation Failed"), f"Failed to create shaderpacks directory:\nError: {e}")
                return
        
        path = str(packs_path)
        try:
            if sys.platform.startswith('win32'):
                os.startfile(path)
            elif sys.platform.startswith('darwin'):
                subprocess.Popen(['open', path])
            elif sys.platform.startswith('linux'):
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            QMessageBox.critical(self, self.tr.get("error_title", "Error"), self.tr.get("open_folder_error", "Failed to open shaderpacks folder:\n{e}").format(e=e))

    def __init__(self, update_info=None):
        super().__init__()
        self.appdata_dir = get_appdata_path()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.container = QFrame()
        self.container.setObjectName("windowFrame")
        main_layout.addWidget(self.container)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.icon_path = resource_path("icon.ico")
        self.mc_process = None
        self.minecraft_thread = None
        self.download_thread = None
        self.update_info = update_info
        self.users = []
        self.temp_width = 0
        self.temp_height = 0
        self.is_downloading = False
        self.border_width = 8
        self._is_resizing = False
        self._resize_edge = None
        settings = load_settings()
        self.old_pos = None
        self.lang_code = settings.get("language", "en_us")
        self.tr = load_language(self.lang_code)

        self.dev_console = DevConsole(self, styles=self.load_styles(), tr=self.tr)
        if load_settings().get("dev_console", False):
            self.dev_console.show()

        self.rpc = None
        self.setWindowTitle(self.tr.get("launcher_title", "MaZult Launcher"))
        self.setWindowIcon(QIcon(str(self.icon_path)))
        self.setMinimumSize(1024, 600)
        self.setStyleSheet(self.load_styles())

        self.main_window = MainWindow(self)
        container_layout.addWidget(self.main_window)
        self.home_page = HomePage(self)
        self.settings_page = SettingsPage(self, self.tr)
        self.modloader_page = ModLoaderPage(self)
        self.instance_page = InstancePage(self)
        self.global_progress_widget = self.create_global_progress_widget()

        self.modloader_install_page = None

        self.settings_page.refreshVersions.connect(self.reload_game_directory_dependent_data)

        self.page_home_index = self.main_window.add_page(self.home_page)
        self.page_settings_index = self.main_window.add_page(self.settings_page)
        self.page_modloader_index = self.main_window.add_page(self.modloader_page)
        self.page_instance_index = self.main_window.add_page(self.instance_page)
        self.main_window.button_group.addButton(self.main_window.sidebar_buttons["home"], self.page_home_index)
        self.main_window.button_group.addButton(self.main_window.sidebar_buttons["mod_loader"], self.page_modloader_index)
        self.main_window.button_group.addButton(self.main_window.sidebar_buttons["instance"], self.page_instance_index)
        self.main_window.button_group.addButton(self.main_window.sidebar_buttons["settings"], self.page_settings_index)
        self.main_window.sidebar_buttons["home"].clicked.connect(lambda: self.main_window.set_current_page(self.page_home_index))
        self.main_window.sidebar_buttons["settings"].clicked.connect(self.open_settings_page)
        self.main_window.sidebar_buttons["mod_loader"].clicked.connect(lambda: self.main_window.set_current_page(self.page_modloader_index))
        self.main_window.sidebar_buttons["instance"].clicked.connect(lambda: self.main_window.set_current_page(self.page_instance_index))

        
        self.home_page.instant_launch_checkbox.stateChanged.connect(
            lambda state: self.on_instant_launch_changed(state, 'home')
        )
        if hasattr(self.settings_page, 'skip_check_checkbox'):
            self.settings_page.skip_check_checkbox.stateChanged.connect(
                lambda state: self.on_instant_launch_changed(state, 'settings')
            )

        self.connect_rpc()
        self.update_username_combo()
        self.load_versions()
        self.home_page.instant_launch_checkbox.setChecked(settings.get("skip_version_check", False))
        self.notification_toast = self.settings_page.notification_toast

        self.home_page.update_mods_count()
        self.home_page.update_worlds_count()
        self.home_page.update_resource_packs_count()
        self.home_page.update_shader_packs_count()

    def reload_game_directory_dependent_data(self):
        self.load_versions()
        self.instance_page.load_instance_list()
        self.home_page.update_mods_count()
        self.home_page.update_worlds_count()
        self.home_page.update_resource_packs_count()

    def create_global_progress_widget(self):
        progress_widget = QWidget(self.main_window)
        progress_widget.setFixedHeight(50)
        progress_widget.setObjectName("progressWidget")
        progress_widget.setStyleSheet("QWidget#progressWidget { background-color: #0A0D17; border-top: 1px solid rgba(255,255,255,.08); }")
        progress_layout = QVBoxLayout(progress_widget)
        progress_layout.setContentsMargins(24, 8, 24, 8)
        progress_layout.setSpacing(5)
        self.global_progress_label = QLabel("...")
        self.global_progress_label.setAlignment(Qt.AlignCenter)
        self.global_progress_bar = QProgressBar()
        self.global_progress_bar.setTextVisible(False)
        self.global_progress_bar.setFixedHeight(5)
        progress_layout.addWidget(self.global_progress_label)
        progress_layout.addWidget(self.global_progress_bar)
        progress_widget.hide()
        return progress_widget

    def set_global_installing_state(self, installing, status_text=""):
        self.home_page.play_button.setEnabled(not installing)
        if self.modloader_install_page:
            self.modloader_install_page.install_btn.setEnabled(not installing)

        if installing:
            self.global_progress_label.setText(status_text)
            self.global_progress_bar.setValue(0)
            self.global_progress_widget.show()
            self.global_progress_widget.raise_()
        else:
            self.global_progress_widget.hide()


    def toggle_maximize_restore(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def update_styles(self):
        self.style().unpolish(self)
        self.style().polish(self)

    def on_instant_launch_changed(self, state, source_widget_name):
        save_settings(skip_version_check=bool(state))
        if source_widget_name != 'settings' and hasattr(self, 'settings_page') and self.settings_page:
            if hasattr(self.settings_page, 'skip_check_checkbox'): self.settings_page.skip_check_checkbox.setChecked(bool(state))
        if source_widget_name != 'home' and hasattr(self, 'home_page') and self.home_page:
            self.home_page.instant_launch_checkbox.setChecked(bool(state))

    def go_home(self):
        self.main_window.set_current_page(self.page_home_index)

    def go_back(self):
        current_index = self.main_window.content.currentIndex()
        if current_index > 0:
            self.main_window.set_current_page(self.page_home_index)

    def open_settings_page(self):
        self.main_window.set_current_page(self.page_settings_index)

    def open_modloader_install_page(self, loader_name):
        if self.modloader_install_page:
            self.main_window.content.removeWidget(self.modloader_install_page)
            self.modloader_install_page.deleteLater()
        self.modloader_install_page = self.modloader_page.create_install_page(loader_name)
        new_page_index = self.main_window.add_page(self.modloader_install_page)
        self.main_window.set_current_page(new_page_index)

    def launch_from_instance_page(self, instance_name):
        self.go_home()

        instance_data_value = f"instance-{instance_name}"
        index = self.home_page.version_combo.findData(instance_data_value)

        if index != -1:
            self.home_page.version_combo.setCurrentIndex(index)
            QTimer.singleShot(50, self.on_play_clicked)
        else:
            QMessageBox.warning(self, self.tr.get("error_title", "Error"), self.tr.get("instance_not_found_error", "Could not find the selected instance in the version list."))

    def restart_app(self):
        QApplication.quit()

    def reconnect_rpc(self):
        if self.rpc:
            try:
                self.rpc.close()
            except Exception as e:
                print(f"Error while closing Discord RPC: {e}")
        self.rpc = None
        self.connect_rpc()

    def connect_rpc(self):
        settings = load_settings()
        if not settings.get("discord_rpc", True):
            self.rpc = None
            return

        try:
            self.rpc = Presence(DISCORD_CLIENT_ID)
            self.rpc.connect()
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
                selected_version = self.home_page.version_combo.currentText().replace("(Installed) ", "")
                self.rpc.update(
                    details=self.tr.get("rpc_status_menu", "In the menu"),
                    large_image="mzlauncher",
                    large_text="MaZult Launcher", 
                    small_image="nothing",
                    small_text="MaZult Launcher",
                    start=int(time.time())
                )
            except PipeClosed:
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
                self.connect_rpc()


    def on_update_clicked(self):
        if self.update_info:
            latest_version, download_url = self.update_info 
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
        
        if self.home_page.play_button and not self.home_page.play_button.parent() is None:
            self.home_page.play_button.setText(self.tr.get("play", "Play"))
            self.home_page.play_button.setEnabled(True)
            self.home_page.play_button.setStyleSheet(self.load_styles())
            self.dev_console.set_kill_button_enabled(False)
        
            self.home_page.username_combo.setEnabled(True)
            self.home_page.version_combo.setEnabled(True)

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
        self.home_page.version_combo.clear()
        
        settings = load_settings()
        current_version = settings.get("version_id")
        
        filters = settings.get("filters", {})
        show_installed = filters.get("installed", True)
        
        installed_versions = get_installed_versions()
        installed_versions_set = set(installed_versions)
        
        available_versions, latest_release_id = get_available_versions(filters)
        
        instances = load_instances()
        instance_map = {f"instance-{inst['name']}": inst for inst in instances}

        # Add instances to the version list
        for instance_id, instance_data in instance_map.items():
            self.home_page.version_combo.addItem(f"{instance_data['name']} ({instance_data['version']})", instance_id)

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
                    self.home_page.version_combo.addItem(f"(Installed) Latest Release ({version_id})", version_id)
                else:
                    self.home_page.version_combo.addItem(f"Latest Release ({version_id})", version_id)

                if data["is_installed"] and show_installed:
                    self.home_page.version_combo.addItem(f"(Installed) Release - {version_id}", version_id)
                else:
                    self.home_page.version_combo.addItem(f"Release - {version_id}", version_id)
                continue

            if data["is_installed"] and show_installed:
                display_label = f"(Installed) {display_label}"
            
            self.home_page.version_combo.addItem(display_label, version_id)
        
        if current_version:
            matching_indexes = []
            for i in range(self.home_page.version_combo.count()):
                if self.home_page.version_combo.itemData(i) == current_version:
                    label = self.home_page.version_combo.itemText(i)
                    matching_indexes.append((i, label))

            if matching_indexes:
                preferred_index = None
                for idx, label in matching_indexes:
                    if "Release -" in label and "Latest" not in label:
                        preferred_index = idx
                        break
                if preferred_index is None:
                    preferred_index = matching_indexes[0][0]

                self.home_page.version_combo.setCurrentIndex(preferred_index)
            else:
                if latest_release_id:
                    index = self.home_page.version_combo.findData(latest_release_id)
                    if index != -1:
                        self.home_page.version_combo.setCurrentIndex(index)
        else:
            if latest_release_id:
                index = self.home_page.version_combo.findData(latest_release_id)
                if index != -1:
                    self.home_page.version_combo.setCurrentIndex(index)
        
        if self.rpc:
            self.update_rpc_menu()


    def load_styles(self):
        return """
        QWidget {
            background-color: #090B14;
            color: #F5F6FA;
            font-family: "Segoe UI Variable", sans-serif;
            font-size: 15px;
        }
        
        QFrame#windowFrame {
            background-color: #090B14; /* Keep background color */
        }

        QWidget#homePage {
            background-color: #090B14;
        }

        QFrame {
            background-color: #090B14;
        }

        QFrame#sidebar {
            border-right: 1px solid #23283B;
        }

        QLineEdit, QComboBox {
            background-color: #141826;
            border: 1px solid #23283B;
            border-radius: 14px;
            padding: 6px 8px;
            color: #F5F6FA;
            font-size: 15px;
        }
        QComboBox::drop-down {
            border: none;
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
        }
        QComboBox QAbstractItemView {
            background-color: #1B2133;
            border: 1px solid #7C4DFF;
            selection-background-color: #7C4DFF;
            color: #F5F6FA;
            outline: 0px;
        }


        QPushButton {
            background-color: #141826;
            border: 1px solid #23283B;
            border-radius: 14px;
            padding: 8px;
            font-weight: normal;
            color: #F5F6FA;
        }
        QPushButton:hover {
            background-color: #1B2133;
            border: 1px solid #915EFF;
        }
        QPushButton:pressed {
            background-color: #915EFF;
            color: #FFFFFF;
        }
        
        QPushButton#playButton {
            background-color: #4F2E70;
            border: none;
            font-weight: bold;
            font-size: 16px;
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8F52FF, stop:1 #6E38FF);
        }
        QPushButton#playButton:hover {
            background-color: #A26BFF;
        }
        QPushButton#playButton:pressed {
            background-color: #6E38FF;
        }
        
        QPushButton#playButton:disabled {
            background-color: #2a1c36;
            color: #A0A0A0;
        }

        QLabel {
            color: #FFFFFF;
            background: transparent;
        }
        QLabel#titleLabel {
            font-size: 52px;
        }
        QLabel#footer {
            color: #A0A0A0;
            font-size: 11px;
        }
        
        QListWidget {
            background-color: #141826;
            border: 1px solid #23283B;
            border-radius: 18px;
        }
        QListWidget::item {
            padding: 8px;
        }
        QListWidget::item:selected {
            background-color: #7C4DFF;
            color: #FFFFFF;
        }
        QListWidget::item:hover {
            background-color: #1B2133;
        }
        
        QProgressBar {
            background-color: #141826;
            border: 1px solid #23283B;
            border-radius: 12px;
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
            border: 1px solid #303030;
            border-top: none;
            background-color: #2D2D2D;
            border-bottom-left-radius: 4px;
            border-bottom-right-radius: 4px;
        }

        QTabBar::tab {
            background-color: #252525;
            color: #A0A0A0;
            border: 1px solid #303030;
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
    def set_progress_status(self, text):
        self.global_progress_label.setText(text)

    def set_progress_value(self, value):
        self.global_progress_bar.setValue(value)

    def set_progress_max(self, maximum):
        self.global_progress_bar.setMaximum(maximum)

    def set_progress_file(self, text, current, total, speed):
        if speed < 1024:
            spd = f"{speed:.1f} B/s"
        elif speed < 1024**2:
            spd = f"{speed/1024:.1f} KB/s"
        else:
            spd = f"{speed/1024**2:.2f} MB/s"
        
        self.global_progress_label.setText(
            f"Downloading: {text} "
            f"({current/1024/1024:.2f}/{total/1024/1024:.2f} MB) @ {spd}"
        )

    def after_download(self, selected_version_id, options, settings, success=True):
        self.is_downloading = False
        self.global_progress_widget.hide()

        if not success or (self.download_thread and self.download_thread._cancelled):
            print(self.tr.get("download_cancelled_log", "Download process was cancelled."))
            self.reset_after_cancel()
            return

        if self.download_thread:
            self.download_thread = None

        self._start_minecraft_process(selected_version_id, options, settings)


    def reset_after_cancel(self):
        self.is_downloading = False
        self.global_progress_widget.hide()
        self.home_page.play_button.setText(self.tr.get("play", "Play"))
        self.home_page.play_button.setEnabled(True)
        self.home_page.play_button.setStyleSheet(self.load_styles())
        
        self.home_page.username_combo.setEnabled(True)
        self.home_page.version_combo.setEnabled(True)

        self.update_rpc_menu()

    def on_play_clicked(self):
        if self.minecraft_thread and self.minecraft_thread.isRunning():
            try:
                print(self.tr.get("warn_previous_thread_running", "[WARN] Previous Minecraft thread still running, attempting cleanup..."))
                self.minecraft_thread.terminate()
                self.minecraft_thread.wait(2000) 
                self.minecraft_thread = None
            except Exception as e:
                print(f"{self.tr.get('error_cleanup_old_thread', '[ERROR] Failed to cleanup old thread:')} {e}")

        if self.is_downloading and self.download_thread and self.download_thread.isRunning():
            print(self.tr.get("download_cancelled_by_user", "Download canceled by user."))
            self.download_thread.cancel()
            
            self.home_page.play_button.setEnabled(False)
            self.home_page.play_button.setText(self.tr.get("wait", "Please wait"))
            self.home_page.play_button.setStyleSheet("""
                QPushButton#playButton {
                    background-color: #2a1c36;
                    color: white;
                    border: none;
                    font-weight: bold;
                    font-size: 16px;
                }
            """)
            self.set_progress_status(self.tr.get("cancelling", "Cancelling..."))

            return

        username = self.home_page.username_combo.currentText()
        if not self.users or username == self.tr.get("manage_users", "Manage Users...") or username == self.tr.get("add_new_user_placeholder", "+ Add new user..."):
            QMessageBox.warning(self, self.tr.get("invalid_user", "Invalid User"), self.tr.get("no_user_selected", "Please add or select a user before playing."))
            return

        selected_data = self.home_page.version_combo.currentData()
        if not selected_data:
            QMessageBox.warning(self, self.tr.get("no_version_selected", "No Version Selected"), self.tr.get("no_version_selected", "Please select a Minecraft version to play."))
            return

        is_instance = isinstance(selected_data, str) and selected_data.startswith("instance-")
        if is_instance:
            instance_name = selected_data.replace("instance-", "")
            instances = load_instances()
            instance_info = next((inst for inst in instances if inst['name'] == instance_name), None)
            selected_version_id = instance_info['version'] if instance_info else None
        else:
            selected_version_id = selected_data

        minecraft_directory = get_minecraft_directory()
        settings = load_settings()
        skip_check = settings.get("skip_version_check", False)

        version_dir = minecraft_directory / "versions" / selected_version_id
        version_json = version_dir / f"{selected_version_id}.json"

        if skip_check and version_dir.exists() and version_json.exists():
            options = self.prepare_mc_options(is_instance, instance_info if is_instance else None)
            if options:
                self._start_minecraft_process(selected_version_id, options, load_settings())
            else:
                self.reset_after_cancel()
            return

        options = self.prepare_mc_options(is_instance, instance_info if is_instance else None)
        if not options: return

        self.go_home() # Ensure home page is visible
        self.global_progress_widget.show()
        self.set_progress_status(self.tr.get("preparing_download", "Preparing download..."))
        self.set_progress_value(0)
        self.update_rpc_downloading(selected_version_id)

        self.is_downloading = True
        self.home_page.play_button.setText(self.tr.get("cancel", "Cancel"))
        self.home_page.play_button.setEnabled(True)
        self.home_page.play_button.setStyleSheet(self.load_styles())
        
        self.home_page.username_combo.setEnabled(False)
        self.home_page.version_combo.setEnabled(False)

        self.download_thread = DownloadThread(selected_version_id, minecraft_directory, self.tr)
        self.download_thread.status_signal.connect(self.set_progress_status)
        self.download_thread.value_signal.connect(self.set_progress_value)
        self.download_thread.max_signal.connect(self.set_progress_max)
        self.download_thread.progress_signal.connect(self.set_progress_file)
        self.download_thread.finished.connect(self.download_thread.deleteLater)
        self.download_thread.finished_signal.connect(lambda success: self.after_download(selected_version_id, options, settings, success))
        self.download_thread.start()

    def prepare_mc_options(self, is_instance, instance_info):
        accounts = load_accounts()
        username = self.home_page.username_combo.currentText()

        target_account = None
        for acc in accounts:
            if acc.get("type") == "microsoft":
                display = f"(microsoft) {acc.get('name')}"
            else:
                display = f"(offline) {acc.get('name')}"
            
            if display == username:
                target_account = acc
                break

        if not target_account:
            return None

        clean_username = target_account.get("name")

        settings = load_settings()
        allocated_ram_mb = settings.get("ram_mb", 2048)
        user_jvm_args = settings.get("jvm_args", [])
        
        final_jvm_args = []
        has_xmx = False
        has_xms = False

        for arg in user_jvm_args:
            if arg.startswith("-Xmx"):
                has_xmx = True
            if arg.startswith("-Xms"):
                has_xms = True
            final_jvm_args.append(arg)

        if not has_xmx:
            final_jvm_args.insert(0, f"-Xmx{allocated_ram_mb}M")
        if not has_xms:
            final_jvm_args.insert(1, f"-Xms{allocated_ram_mb // 4}M") # Allocate 1/4 of max as min

        options = {
            "jvmArguments": final_jvm_args
        }

        if is_instance:
            options["gameDirectory"] = instance_info['path']

        if target_account.get("type") == "microsoft":
            refresh_token = target_account.get("refresh_token")
            if refresh_token:
                try:
                    new_account_info = msa.complete_refresh(CLIENT_ID, None, REDIRECT_URI, refresh_token)
                    
                    target_account["name"] = new_account_info["name"]
                    target_account["uuid"] = new_account_info["id"]
                    target_account["token"] = new_account_info["access_token"]
                    target_account["refresh_token"] = new_account_info["refresh_token"]
                    save_accounts(accounts)

                except Exception as e:
                    print(f"[Auth] Failed to refresh token: {e}")
                    QMessageBox.warning(self, self.tr.get("login_expired_title", "Login Expired"), self.tr.get("login_expired_message", "Your Microsoft login has expired. Please log in again."))
                    accounts.remove(target_account)
                    save_accounts(accounts)
                    self.update_username_combo()
                    return None
            
            options.update({
                "username": clean_username,
                "uuid": target_account["uuid"],
                "token": target_account["token"],
                "user_type": "msa",
            })
            return options
        else: 
            user_uuid = str(uuid.uuid3(uuid.NAMESPACE_URL, "OfflinePlayer:" + clean_username))
            options.update({ "username": clean_username, "uuid": user_uuid, "token": "" })
            return options

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
            print(f"[Launcher] Running command: {' '.join(command)}")
            self.update_rpc_game(version_id)

            self.home_page.play_button.setText(self.tr.get("launching", "Launching..."))
            self.home_page.play_button.setEnabled(False)
            self.home_page.play_button.setStyleSheet(self.load_styles())

            hide_on_launch = settings.get("hide_on_launch", True)
            if hide_on_launch:
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
