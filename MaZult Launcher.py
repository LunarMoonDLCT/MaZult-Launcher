import sys
import os
import shutil
import zipfile
import requests
import json
import subprocess
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QProgressBar, QLabel, QMessageBox
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont, QIcon
from pathlib import Path

import ctypes
from ctypes import windll, wintypes

try:
    from pkg_resources import working_set
except ImportError:
    working_set = None

GITHUB_API_URL = "https://api.github.com/repositories/1044123558/releases/latest"

if getattr(sys, 'frozen', False):
    MAIN_APP_DIR = os.path.dirname(sys.executable)
else:
    MAIN_APP_DIR = os.path.dirname(os.path.abspath(__file__))

CURRENT_VERSION_FILE = os.path.join(MAIN_APP_DIR, 'app', 'app.json')
TEMP_UPDATE_DIR = os.path.join(MAIN_APP_DIR, 'temp_update')
LAUNCHER_EXE = "Launcher.exe"
LAUNCHER_PY = "Launcher.py"
UPDATER_SCRIPT_NAME = os.path.basename(__file__)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin_and_restart():
    try:
        script_path = os.path.abspath(sys.argv[0])
        params = ' '.join([f'"{arg}"' for arg in sys.argv])

        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", script_path, params, None, 1)

        if result <= 32:
            return False
        
        return True
    except Exception as e:
        return False

class GitHubAsset:
    def __init__(self, data):
        self.name = data.get("name", "")
        self.browser_download_url = data.get("browser_download_url", "")
        self.size = data.get("size", 0)

class GitHubRelease:
    def __init__(self, data):
        self.tag_name = data.get("tag_name", "")
        self.assets = [GitHubAsset(asset) for asset in data.get("assets", [])]

class UpdateWorker(QThread):
    status_updated = Signal(str)
    progress_updated = Signal(int, int, int)
    update_success = Signal()
    request_admin_privileges = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_running = True

    def run(self):
        try:
            self.status_updated.emit("Checking for updates...")
            current_version = self.get_current_version()
            
            latest_release = None
            try:
                latest_release = self.get_latest_release()
            except requests.exceptions.RequestException as e:
                self.status_updated.emit("Cannot connect to update server. Starting Launcher...")
                self.cleanup()
                self.update_success.emit()
                return
            
            if not latest_release or not latest_release.tag_name:
                self.status_updated.emit("Could not get latest version info. Starting Launcher...")
                self.cleanup()
                self.update_success.emit()
                return

            latest_version = latest_release.tag_name
            
            self.status_updated.emit(f"Current Version: {current_version} | New Version: {latest_version}")
            
            if latest_version == current_version:
                self.status_updated.emit("You are using the latest version. Starting...")
                self.cleanup()
                self.update_success.emit()
                return

            if sys.platform.startswith("win") and getattr(sys, 'frozen', False):
                if not is_admin():
                    self.status_updated.emit("Update available. Requesting admin privileges...")
                    self.request_admin_privileges.emit()
                    return 

            self.cleanup()
            os.makedirs(TEMP_UPDATE_DIR, exist_ok=True)
            
            download_url, total_size = self.get_download_url(latest_release)
            
            if not download_url:
                self.status_updated.emit("No suitable update file found. Starting Launcher...")
                self.update_success.emit()
                return
            
            temp_zip_file = os.path.join(TEMP_UPDATE_DIR, "update.zip")
            
            self.download_update(download_url, temp_zip_file, total_size)
            self.extract_and_install(temp_zip_file, MAIN_APP_DIR)
            
            self.update_local_version(latest_version)
            self.cleanup()
            
            self.update_success.emit()

        except Exception as e:
            self.status_updated.emit(f"An error occurred: {e}. Starting Launcher...")
            self.cleanup()
            self.update_success.emit()
    
    def get_current_version(self):
        if os.path.exists(CURRENT_VERSION_FILE):
            try:
                with open(CURRENT_VERSION_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get("version", "0.0.0")
            except (IOError, json.JSONDecodeError):
                return "0.0.0"
        return "0.0.0"
    
    def update_local_version(self, new_version):
        try:
            app_dir = os.path.dirname(CURRENT_VERSION_FILE)
            os.makedirs(app_dir, exist_ok=True)
            with open(CURRENT_VERSION_FILE, 'w') as f:
                json.dump({"version": new_version}, f)
        except Exception as e:
            pass

    def get_latest_release(self):
        headers = {"User-Agent": "AutoUpdater"}
        response = requests.get(GITHUB_API_URL, headers=headers)
        response.raise_for_status()
        return GitHubRelease(response.json())

    def get_download_url(self, release):
        os_name = sys.platform
        if os_name.startswith("win"):
            tag = "-Portable-Win.zip"
        else:
            tag = "-Universal.zip"

        for asset in release.assets:
            if asset.name.endswith(tag):
                return asset.browser_download_url, asset.size
        
        return None, 0

    def download_update(self, url, file_path, total_size):
        self.status_updated.emit("Downloading update...")
        with requests.get(url, stream=True, headers={"User-Agent": "AutoUpdater"}) as response:
            response.raise_for_status()
            with open(file_path, 'wb') as f:
                downloaded_bytes = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if not self.is_running: return
                    f.write(chunk)
                    downloaded_bytes += len(chunk)
                    self.progress_updated.emit(downloaded_bytes, total_size, int((downloaded_bytes / total_size) * 100))
        self.progress_updated.emit(total_size, total_size, 100) 
            
    def check_installed_packages(self, requirements_file):
        missing_packages = []
        if working_set is None:
            return ["all"]
            
        try:
            installed_packages = {pkg.key for pkg in working_set}
            with open(requirements_file, 'r') as f:
                required_packages = [line.strip().split('==')[0].split('>')[0].split('<')[0] for line in f if line.strip() and not line.strip().startswith('#')]
            
            for req in required_packages:
                if req.lower() not in installed_packages:
                    missing_packages.append(req)
        except Exception as e:
            return ["all"]
        
        return missing_packages

    def extract_and_install(self, zip_file_path, dest_dir):
        self.status_updated.emit("Extracting and installing...")
        
        bin_dir = os.path.join(dest_dir, 'bin')
        if os.path.exists(bin_dir) and os.path.isdir(bin_dir):
            self.status_updated.emit("Removing old bin directory...")
            try:
                shutil.rmtree(bin_dir)
            except OSError as e:
                self.status_updated.emit("Failed to remove old bin. Update may be incomplete.")

        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(TEMP_UPDATE_DIR)
        
        for item_name in os.listdir(TEMP_UPDATE_DIR):
            temp_item_path = os.path.join(TEMP_UPDATE_DIR, item_name)
            dest_item_path = os.path.join(dest_dir, item_name)

            if os.path.basename(temp_item_path) == UPDATER_SCRIPT_NAME:
                continue

            if os.path.isdir(temp_item_path):
                if os.path.exists(dest_item_path):
                    shutil.rmtree(dest_item_path)
                shutil.move(temp_item_path, dest_item_path)
            else:
                if os.path.exists(dest_item_path):
                    os.remove(dest_item_path)
                shutil.move(temp_item_path, dest_item_path)

        if not sys.platform.startswith("win"):
            requirements_file = os.path.join(dest_dir, "requirements.txt")
            if os.path.exists(requirements_file):
                missing_packages = self.check_installed_packages(requirements_file)
                if missing_packages:
                    self.status_updated.emit("Installing libraries...")
                    try:
                        subprocess.run(
                            [sys.executable, "-m", "pip", "install", "--break-system-packages", "-r", requirements_file],
                            check=True
                        )
                    except subprocess.CalledProcessError as e:
                        self.status_updated.emit("Could not install libraries. Continuing startup...")
                else:
                    self.status_updated.emit("Libraries are already installed. Continuing startup...")
            else:
                pass

    def cleanup(self):
        self.status_updated.emit("Cleaning up temporary files...")
        if os.path.exists(TEMP_UPDATE_DIR):
            try:
                shutil.rmtree(TEMP_UPDATE_DIR)
            except OSError as e:
                pass

class UpdaterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(400, 200)
        self.setWindowTitle("MaZult Launcher")
        self.setWindowIcon(QIcon("icon.ico"))
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("background-color: #202020; color: #FFFFFF;")

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        self.title_label = QLabel("MaZult Launcher")
        self.title_label.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
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
        
        self.worker = UpdateWorker()
        self.worker.status_updated.connect(self.update_status)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.update_success.connect(self.on_update_success)
        self.worker.request_admin_privileges.connect(self.handle_admin_request)
        self.worker.start()

    def update_status(self, message):
        self.status_label.setText(message)

    def update_progress(self, current, total, percent):
        self.progress_bar.setValue(percent)
        self.progress_bar.setTextVisible(True)
        self.status_label.setText(f"Downloading: {current / (1024*1024):.2f} MB / {total / (1024*1024):.2f} MB")

    def on_update_success(self):
        self.update_status("Update successful. Starting Launcher...")
        try:
            is_windows = sys.platform.startswith("win")
            
            launcher_path = ""
            command = None

            if is_windows:
                launcher_path = os.path.join(MAIN_APP_DIR, 'bin', LAUNCHER_EXE)
                try:
                    subprocess.Popen([launcher_path, '--Launcher'])
                except (FileNotFoundError, OSError) as e:
                    app_dir = os.path.join(MAIN_APP_DIR, 'app')
                    if os.path.exists(app_dir):
                        shutil.rmtree(app_dir)
                    QMessageBox.critical(self, "Lỗi khi chạy Launcher", "Launcher đã cài đặt không thể chạy. Đã xóa thư mục 'app'. Vui lòng khởi chạy lại.")
                    QApplication.quit()
                    return

            else:
                launcher_path = os.path.join(MAIN_APP_DIR, LAUNCHER_PY)
                command = [sys.executable, launcher_path, '--Launcher']
                subprocess.Popen(command, start_new_session=True)
            
            if not os.path.exists(launcher_path):
                raise FileNotFoundError(f"Launcher file not found: {launcher_path}")
            
        except (FileNotFoundError, OSError) as e:
            QMessageBox.critical(self, "Error", f"Could not launch the main application: {e}")

        QApplication.quit()

    def handle_admin_request(self):
        self.update_status("Please grant admin privileges to continue the update.")
        if run_as_admin_and_restart():
            QApplication.quit()
        else:
            QMessageBox.critical(self, "ERROR in Downloading update", "Please grant admin privileges to continue the update.")
            QApplication.quit()

    def closeEvent(self, event):
        if self.worker.isRunning():
            event.ignore()
            QMessageBox.warning(self, "Update", "You can't close during an update. Please wait.")
        else:
            self.worker.is_running = False
            self.worker.wait()
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UpdaterApp()
    window.show()
    sys.exit(app.exec())