import sys
from cx_Freeze import setup, Executable

# Cấu hình tùy chọn build.
build_exe_options = {
    "packages": ["PySide6", "sys", "os"], 
    "excludes": ["tkinter", "minecraft-launcher-lib",], 
    "include_files": ["icon.ico"]
}

# Đảm bảo không hiển thị cửa sổ console khi chạy.
base = "Win32GUI"
    
# Thiết lập thông tin và file build.
setup(
    name="MaZult Launcher",
    version="1.104.98.1",
    author="LunarMoonDLCT",
    description="MaZult Launcher",
    options={"build_exe": build_exe_options},
    executables=[Executable(
        "MaZult Launcher.py", 
        #"Launcher.py",
        base=base, 
        icon="icon.ico",

        copyright="© 2025 LunarMoonDLCT"
    )]
)
#"Launcher.py",
