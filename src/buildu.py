import sys
import os
from cx_Freeze import setup, Executable

build_exe_options = {

    "packages": [
        "os", "sys", "json", "shutil", "zipfile",
        "time", "subprocess", "requests",
        "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
    ],

    "excludes": [
        "tkinter", "pip", "minecraft-launcher-lib"
    ],

    "include_files": [
        "icon.ico",
    ],

    "optimize": 2,
    "include_msvcr": True,
}

base = "Win32GUI" if sys.platform == "win32" else None

setup(
    name="MaZult Updater",
    version="1.03.01.2026",
    author="LunarMoonDLCT",
    description="MaZult Launcher",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "MaZult Launcher.py", 
            base=base,
            icon="icon.ico",
            copyright="© 2026 LunarMoonDLCT"
        )
    ]
)

