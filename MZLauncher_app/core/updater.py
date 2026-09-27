import sys
import platform
import os
import shutil
import subprocess
import tempfile
import zipfile
import requests
import ctypes
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from packaging.version import Version

LAUNCHER_VERSION = "1.4.10.2026"

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

def is_writable(path: Path) -> bool:
    try:
        test_file = path / f".mzl_write_test_{os.getpid()}"
        test_file.touch()
        test_file.unlink()
        return True
    except (PermissionError, OSError):
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

    if sys.platform.startswith("win32"):
        arch = platform.machine().lower()
        if arch in ("arm64", "aarch64"):
            os_specific_suffix = "-Win-a64.zip"
        else:
            os_specific_suffix = "-Win-x64.zip"
    else:
        os_specific_suffix = "-Other-OS.zip"

    for asset in data.get("assets", []):
        if asset.get("name", "").endswith(os_specific_suffix):
            zip_url = asset["browser_download_url"]
            break

    if not zip_url:
        raise RuntimeError("No updater zip file found in the latest release.")

    return latest_ver, zip_url

class UpdateCheckThread(QThread):
    update_available = Signal(str, str)
    up_to_date = Signal()
    error_occurred = Signal(str)

    def __init__(self, current_version=None):
        super().__init__()
        self.current_version = current_version or LAUNCHER_VERSION

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

def download_update_with_progress(splash):
    _, url = get_latest_updater_info()

    temp_dir = Path(tempfile.mkdtemp(prefix="mzl_update_"))
    temp_dir.mkdir(parents=True, exist_ok=True)

    zip_path = temp_dir / "update.zip"

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

    return zip_path, temp_dir

def apply_update(zip_path, temp_dir, splash: 'Splash'):
    extracted_dir = temp_dir / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    splash.set_progress(92, splash.tr.get("updater_extracting", "Extracting files..."))

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extracted_dir)

    splash.set_progress(96, splash.tr.get("updater_preparing_install", "Preparing to install..."))

    base_dir = get_launcher_root().resolve()

    if sys.platform.startswith("win32"):
        main_exe = base_dir / "MaZult Launcher.exe"
        if not main_exe.exists():
            main_exe = Path(sys.executable).resolve()

        pid = os.getpid()
        bat_path = Path(tempfile.gettempdir()) / f"mzl_updater_{pid}.bat"

        bat_script = f"""@echo off
chcp 65001 >nul
:wait_proc
tasklist /fi "pid eq {pid}" 2>nul | find "{pid}" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_proc
)
timeout /t 1 /nobreak >nul

xcopy "{extracted_dir.resolve()}\\*" "{base_dir}\\" /E /Y /H /R /Q >nul 2>&1

start "" "{main_exe.resolve()}" --Launcher

rmdir /s /q "{temp_dir.resolve()}" >nul 2>&1
(goto) 2>nul & del "%~f0"
"""
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_script)

        splash.set_progress(100, splash.tr.get("updater_installing", "Copying new files..."))

        needs_admin = not is_writable(base_dir) and not is_admin()

        if needs_admin:
            ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                "cmd.exe",
                f'/c "{bat_path}"',
                None,
                0  # SW_HIDE: ẩn cửa sổ cmd khi chạy
            )
        else:
            flags = subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "DETACHED_PROCESS"):
                flags |= subprocess.DETACHED_PROCESS
            subprocess.Popen(
                ["cmd.exe", "/c", str(bat_path)],
                creationflags=flags
            )
        sys.exit(0)
    else:
        for item in base_dir.iterdir():
            if item.name in ("bin", "app", "temp_update", "unins000.exe", "unins000.dat"):
                continue
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except Exception as e:
                print(f"[UPDATER] Failed to remove {item}: {e}")

        for item in extracted_dir.iterdir():
            dest = base_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass

def cleanup_update():
    pass