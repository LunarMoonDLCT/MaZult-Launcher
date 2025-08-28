import sys
import os
import shutil
import zipfile
import requests
import json
import subprocess
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QProgressBar, QLabel, QMessageBox
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont

# Thư viện này cần thiết cho hàm kiểm tra mới
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
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_running = True

    def run(self):
        try:
            self.cleanup()
            os.makedirs(TEMP_UPDATE_DIR, exist_ok=True)

            self.status_updated.emit("Đang kiểm tra cập nhật...")
            current_version = self.get_current_version()
            
            latest_release = None
            try:
                latest_release = self.get_latest_release()
            except requests.exceptions.RequestException as e:
                self.status_updated.emit("Không thể kết nối đến máy chủ cập nhật. Đang khởi động Launcher...")
                print(f"Lỗi kết nối: {e}. Bỏ qua cập nhật.")
                self.cleanup()
                self.update_success.emit()
                return
            
            if not latest_release or not latest_release.tag_name:
                self.status_updated.emit("Không thể lấy thông tin phiên bản mới nhất. Đang khởi động Launcher...")
                self.cleanup()
                self.update_success.emit()
                return

            latest_version = latest_release.tag_name
            
            self.status_updated.emit(f"Phiên bản hiện tại: {current_version} | Phiên bản mới: {latest_version}")
            
            if latest_version == current_version:
                self.status_updated.emit("Bạn đang sử dụng phiên bản mới nhất. Đang khởi động...")
                self.update_success.emit()
                return
            
            download_url, total_size = self.get_download_url(latest_release)
            
            if not download_url:
                self.status_updated.emit("Không tìm thấy tệp cập nhật phù hợp. Đang khởi động Launcher...")
                self.update_success.emit()
                return
            
            temp_zip_file = os.path.join(TEMP_UPDATE_DIR, "update.zip")
            
            self.download_update(download_url, temp_zip_file, total_size)
            self.extract_and_install(temp_zip_file, MAIN_APP_DIR)
            
            self.update_local_version(latest_version)
            self.cleanup()
            
            self.update_success.emit()

        except Exception as e:
            self.status_updated.emit(f"Đã xảy ra lỗi: {e}. Đang khởi động Launcher...")
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
            print(f"Lỗi khi cập nhật file app.json: {e}")

    def get_latest_release(self):
        headers = {"User-Agent": "AutoUpdater"}
        response = requests.get(GITHUB_API_URL, headers=headers)
        response.raise_for_status()
        return GitHubRelease(response.json())

    def get_download_url(self, release):
        os_name = sys.platform
        if os_name.startswith("win"):
            tag = "-Win.zip"
        else:
            tag = "-Universal.zip"

        for asset in release.assets:
            if asset.name.endswith(tag):
                return asset.browser_download_url, asset.size
        
        return None, 0

    def download_update(self, url, file_path, total_size):
        self.status_updated.emit("Đang tải xuống...")
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
        """Kiểm tra xem các gói trong requirements.txt đã được cài đặt chưa."""
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
            print(f"Lỗi khi kiểm tra gói: {e}. Coi như cần cài đặt.")
            return ["all"]
        
        return missing_packages

    def extract_and_install(self, zip_file_path, dest_dir):
        self.status_updated.emit("Đang giải nén và cài đặt...")
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(TEMP_UPDATE_DIR)
        
        for item in os.listdir(TEMP_UPDATE_DIR):
            s = os.path.join(TEMP_UPDATE_DIR, item)
            d = os.path.join(dest_dir, item)
            
            if os.path.basename(s) == UPDATER_SCRIPT_NAME:
                continue

            if os.path.isdir(s):
                if os.path.exists(d):
                    for sub_item in os.listdir(s):
                        shutil.move(os.path.join(s, sub_item), d)
                    shutil.rmtree(s)
                else:
                    shutil.move(s, d)
            else:
                shutil.move(s, d)

        if not sys.platform.startswith("win"):
            requirements_file = os.path.join(dest_dir, "requirements.txt")
            if os.path.exists(requirements_file):
                missing_packages = self.check_installed_packages(requirements_file)
                if missing_packages:
                    self.status_updated.emit("Đang cài đặt thư viện...")
                    try:
                        subprocess.run(
                            [sys.executable, "-m", "pip", "install", "--break-system-packages", "-r", requirements_file],
                            check=True
                        )
                    except subprocess.CalledProcessError as e:
                        print(f"Lỗi khi cài đặt thư viện: {e}")
                        self.status_updated.emit("Không thể cài đặt thư viện. Tiếp tục khởi động...")
                else:
                    self.status_updated.emit("Thư viện đã được cài đặt đầy đủ. Tiếp tục khởi động...")
                    print("Tất cả thư viện đã được cài đặt. Bỏ qua lệnh pip.")
            else:
                print("Không tìm thấy file requirements.txt, bỏ qua cài đặt thư viện.")
    def cleanup(self):
        self.status_updated.emit("Đang dọn dẹp file tạm...")
        if os.path.exists(TEMP_UPDATE_DIR):
            try:
                shutil.rmtree(TEMP_UPDATE_DIR)
            except OSError as e:
                print(f"Lỗi khi xóa thư mục tạm: {e}")

class UpdaterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(400, 200)
        self.setWindowTitle("MaZult Launcher")
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
        self.worker.start()

    def update_status(self, message):
        self.status_label.setText(message)

    def update_progress(self, current, total, percent):
        self.progress_bar.setValue(percent)
        self.progress_bar.setTextVisible(True)
        self.status_label.setText(f"Đang tải xuống: {current / (1024*1024):.2f} MB / {total / (1024*1024):.2f} MB")

    def on_update_success(self):
        self.update_status("Đã cập nhật thành công. Đang khởi động Launcher...")
        try:
            launcher_path = ""
            if sys.platform.startswith("win"):
                launcher_path = os.path.join(MAIN_APP_DIR, LAUNCHER_EXE)
                command = f'start "" "{launcher_path}" --Launcher'
            else:
                launcher_path = os.path.join(MAIN_APP_DIR, LAUNCHER_PY)
                command = [sys.executable, launcher_path, '--Launcher']

            if not os.path.exists(launcher_path):
                raise FileNotFoundError(f"Không tìm thấy file Launcher: {launcher_path}")
            
            if sys.platform.startswith("win"):
                subprocess.Popen(command, shell=True)
            else:
                subprocess.Popen(command, start_new_session=True)
            
        except (FileNotFoundError, OSError) as e:
            QMessageBox.critical(self, "Lỗi khởi chạy", f"Không thể khởi chạy ứng dụng chính: {e}")

        QApplication.quit()

    def closeEvent(self, event):
        if self.worker.isRunning():
            event.ignore()
            QMessageBox.warning(self, "Đang cập nhật", "Không thể đóng cửa sổ trong quá trình cập nhật. Vui lòng chờ.")
        else:
            self.worker.is_running = False
            self.worker.wait()
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UpdaterApp()
    window.show()
    sys.exit(app.exec())