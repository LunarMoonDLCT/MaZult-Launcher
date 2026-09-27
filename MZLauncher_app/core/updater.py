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

GITHUB_API_URL = "https://api.github.com/repos/LunarMoonDLCT/MaZult-Launcher/releases/latest"

def get_launcher_root():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    else:
        project_root = Path(__file__).resolve().parent.parent.parent
        # Tìm thư mục chứa file exe trong project (ví dụ build/exe.* hoặc bin)
        for candidate in project_root.rglob("MaZult Launcher.exe"):
            if candidate.is_file():
                return candidate.parent
        return project_root

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

    # Nếu file zip chứa 1 thư mục gốc bọc ngoài, trỏ vào thư mục đó
    sub_items = [p for p in extracted_dir.iterdir() if p.is_dir()]
    if len(sub_items) == 1 and len(list(extracted_dir.iterdir())) == 1:
        extracted_dir = sub_items[0]

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
setlocal enabledelayedexpansion

set "SRC={extracted_dir.resolve()}"
set "DEST={base_dir.resolve()}"
set "EXE={main_exe.resolve()}"
set /a count=0

:wait_proc
tasklist /fi "PID eq {pid}" 2>nul | find "{pid}" >nul
if not errorlevel 1 (
    set /a count+=1
    if !count! geq 15 (
        taskkill /f /pid {pid} >nul 2>&1
    )
    ping 127.0.0.1 -n 2 >nul
    goto wait_proc
)
ping 127.0.0.1 -n 2 >nul

robocopy "%SRC%" "%DEST%" /E /IS /IT /NP /NFL /NDL /R:3 /W:1 >nul 2>&1
if errorlevel 8 (
    xcopy "%SRC%\\*" "%DEST%" /E /I /Y /H /R /Q /C >nul 2>&1
)

start "" "%EXE%" --Launcher

rmdir /s /q "{temp_dir.resolve()}" >nul 2>&1
(goto) 2>nul & del "%~f0"
"""
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_script)

        splash.set_progress(100, splash.tr.get("updater_installing", "Copying new files..."))

        needs_admin = not is_writable(base_dir) and not is_admin()

        verb = "runas" if needs_admin else "open"
        res = ctypes.windll.shell32.ShellExecuteW(
            None,
            verb,
            str(bat_path),
            None,
            str(bat_path.parent),
            0  # SW_HIDE: ẩn cửa sổ cmd khi chạy
        )

        # Fallback nếu ShellExecuteW trả về lỗi (<= 32)
        if res <= 32:
            subprocess.Popen(
                f'cmd.exe /c "{bat_path}"',
                shell=True,
                close_fds=True,
                creationflags=subprocess.CREATE_NO_WINDOW)
        os._exit(0)
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