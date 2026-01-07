import sys
import os
from cx_Freeze import setup, Executable

build_exe_options = {
    "packages": [
        "os", "sys", "json", "uuid", "requests",
        "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
        "minecraft_launcher_lib",
        "packaging", "psutil"
    ],

    "excludes": [
        "tkinter", "pip"
    ],

    "include_files": [
        "icon.ico", "lang", 
    ],

    "optimize": 2,
    
    "include_msvcr": True,
}

base = "Win32GUI" if sys.platform == "win32" else None

setup(
    name="MaZult Launcher",
    version="1.07.01.2026",
    author="LunarMoonDLCT",
    description="MaZult Launcher",
    options={"build_exe": build_exe_options},
    executables=[Executable(
        "Launcher.py",
        base=base,
        icon="icon.ico",
        copyright="© 2026 LunarMoonDLCT"
    )]
)
