import sys
import os
from cx_Freeze import setup, Executable

# Xác định đường dẫn gốc của dự án để tránh lỗi đường dẫn
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

build_exe_options = {
    # Gói cần thiết, cx_Freeze sẽ tự động tìm các thư viện chuẩn
    "packages": [
        "PySide6",
        "requests",
        "psutil",
        "packaging",
        "minecraft_launcher_lib"
    ],
    # Các tệp và thư mục cần sao chép vào thư mục build
    # (source, destination_in_build_dir)
    "include_files": [
        (os.path.join(ROOT_DIR, "icon.ico"), "icon.ico"),
        (os.path.join(ROOT_DIR, "MZLauncher_app", "lang"), "lang"),
    ],
    # Tối ưu hóa bytecode
    "optimize": 2,
    # Bao gồm MSVCR (cần thiết cho Windows)
    "include_msvcr": True,
    # Giảm lỗi thiếu gói với PySide6
    "zip_include_packages": ["*"],
    "zip_exclude_packages": [],
}

# Sử dụng "Win32GUI" để ẩn cửa sổ console trên Windows
base = "Win32GUI" if sys.platform == "win32" else None

setup(
    name="MaZult Launcher",
    version="1.8.5.2026",
    author="LunarMoonDLCT",
    description="MaZult Launcher",
    options={"build_exe": build_exe_options},
    executables=[Executable(
        os.path.join(ROOT_DIR, "MZLauncher_app", "Launcher.py"),
        base=base,
        icon=os.path.join(ROOT_DIR, "icon.ico"),
        copyright="© 2026 LunarMoonDLCT"
    )]
)
