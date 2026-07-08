import sys
import os
import shutil
import zipfile
import requests
import ctypes
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from packaging.version import Version

GITHUB_API_URL = "https://api.github.com/repos/LunarMoonDLCT/MZassets/releases/latest"

def get_launcher_root():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent.parent
    else:
        return Path(__file__).resolve().parent.parent.parent

def is_admin():
    if not sys.platform.startswith("win32"):
        return True
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def relaunch_as_admin(extra_args=None):
    if not sys.platform.startswith("win32"):
        return

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
        1
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
    update_available = Signal(str, str)
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

def download_update_with_progress(dest_dir, splash):
    url, _ = get_latest_updater_info()

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

def apply_update(zip_path, splash: 'Splash'):
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