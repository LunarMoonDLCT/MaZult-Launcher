import sys
import os
import shutil
import time
import traceback
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar, QMessageBox
)
from PySide6.QtGui import QFont, QPainter, QColor
from PySide6.QtCore import Qt, QTimer, Signal

from MZLauncher_app.core.launcher_core import MaZultLauncher, load_language, get_appdata_path, get_tmp_dir, parse_launcher_args
from MZLauncher_app.core.updater import (
    UpdateCheckThread, is_admin, relaunch_as_admin, download_update_with_progress,
    apply_update, cleanup_update, get_launcher_root
)

class Splash(QWidget):
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.setFixedSize(360, 200)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        self.main_layout = layout
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(14)

        self.title = QLabel("MaZult Launcher")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self.title.setStyleSheet("color: white;")

        self.subtitle = QLabel()
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setFont(QFont("Segoe UI", 11))
        self.subtitle.setStyleSheet("color:#BBBBBB;")

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(True)
        self.bar.setFormat("%p%")
        self.bar.setAlignment(Qt.AlignCenter)
        self.bar.setFixedHeight(18)

        self.bar.setStyleSheet("""
            QProgressBar {
                background-color: #2b2b2b;
                border-radius: 9px;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #6a5acd;
                border-radius: 9px;
            }
        """)

        layout.addStretch()
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(6)
        self.bar_container = QWidget()
        bar_layout = QVBoxLayout(self.bar_container)
        bar_layout.setContentsMargins(0,0,0,0)
        bar_layout.addWidget(self.bar)
        layout.addWidget(self.bar_container)
        layout.addStretch()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(32, 32, 32))
        p.drawRoundedRect(self.rect(), 22, 22)

    def set_translator(self, tr_func):
        self.tr = tr_func
        self.subtitle.setText(self.tr.get("splash_starting", "Starting..."))

    def set_progress(self, value, text=None, indeterminate=False):
        if indeterminate:
            self.bar.setRange(0, 0)
        else:
            self.bar.setRange(0, 100)
            self.bar.setValue(max(0, min(100, value)))

        if text:
            self.subtitle.setText(text)
        QApplication.processEvents()
        if not indeterminate and self.bar.value() >= 100:
            self.finished.emit()

    def show_error_and_close(self, title, message):
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        error_title = QLabel(title)
        error_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        error_title.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(error_title)
        self.main_layout.addWidget(QLabel(message))

def start_update_process(splash: Splash):
    try:
        print("[UPDATER] Permissions OK. Starting update process.")
        splash.set_progress(5, splash.tr.get("updater_starting", "Starting update..."), indeterminate=False)

        base_dir = get_launcher_root()
        temp_dir = base_dir / "temp_update"

        zip_path = download_update_with_progress(temp_dir, splash)
        apply_update(zip_path, splash)
        # Cleanup is now handled by the updater itself
        cleanup_update()

        splash.set_progress(100, splash.tr.get("updater_complete", "Update complete. Preparing Launcher"))

    except Exception as e:
        print(f"[UPDATER] Update process failed: {e}")
        splash.show_error_and_close(splash.tr.get("updater_failed_title", "Update Failed"), splash.tr.get("updater_apply_failed", "Could not apply update.\n{e}").format(e=e))

def main():
    def global_exception_hook(exctype, value, tb):
        tr = load_language()
        error_text = "".join(traceback.format_exception(exctype, value, tb))
        try:
            log_dir = get_appdata_path() / "logs"
            os.makedirs(log_dir, exist_ok=True)
            log_file = log_dir / f"crash_{int(time.time())}.log"
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(error_text)
            print(f"[CRASH LOG SAVED] -> {log_file}")
        except Exception as e:
            print(f"[CRASH LOGGING FAILED] {e}")

        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle(tr.get("launcher_title", "MaZult Launcher") + " - " + tr.get("crash_detected", "Crash Detected"))
            msg.setText(tr.get("critical_error", "The launcher has encountered a critical error and will close."))
            msg.setInformativeText(str(value))
            msg.setDetailedText(error_text)
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
        except Exception as e:
            print(f"Failed to show crash dialog: {e}")

        sys.__excepthook__(exctype, value, tb)
        sys.exit(1)

    sys.excepthook = global_exception_hook

    app = QApplication(sys.argv)

    tr = load_language()

    splash = Splash()
    splash.set_translator(tr)

    appdata_path = get_appdata_path()
    os.makedirs(appdata_path, exist_ok=True)
    os.chdir(appdata_path)

    shutil.rmtree(get_tmp_dir(), ignore_errors=True)

    launcher_args = parse_launcher_args()
    print("[Args]", launcher_args)

    is_windows = sys.platform.startswith("win32")
    is_launcher_arg = launcher_args["has_launcher"]

    if is_windows and not is_launcher_arg:
        print("Launcher arg not present. Attempting to start main updater.")
        frozen_base_dir = Path(os.path.dirname(sys.executable)).parent
        updater_name = "MaZult Launcher.exe"
        exe_path = frozen_base_dir / updater_name
        if exe_path.exists():
            try:
                print("Found Updater, launching...")
                subprocess.Popen([str(exe_path), "--Launcher"])
                sys.exit(0)
            except Exception as e:
                print(f"Error when launching updater, proceeding with current instance: {e}")
        else:
            print("No updater found, run default app")

    main_window = MaZultLauncher()
    main_window.hide()

    def open_main_window():
        if not main_window.isVisible():
            splash.close()
            main_window.show()
            main_window.raise_()
            main_window.activateWindow()
            app.main_window = main_window

    splash.finished.connect(open_main_window)

    def on_update_available(version, url):
        if is_windows and not is_admin():
            print("[UPDATER] Requesting administrator privileges...")
            splash.set_progress(0, tr.get("updater_waiting_permission", "Please allow administrator permission to update..."), indeterminate=True)
            relaunch_as_admin()
            return
        start_update_process(splash)

    def on_up_to_date():
        # Keep it indeterminate to maintain the "loading" feel
        splash.set_progress(0, tr.get("updater_up_to_date", "Launcher is up to date."), indeterminate=True)
        
        # After a short delay, show "Preparing" and then finish
        def finish_loading():
            splash.set_progress(0, tr.get("splash_preparing_launcher", "Preparing launcher..."), indeterminate=True)
            QTimer.singleShot(800, lambda: splash.set_progress(100, tr.get("splash_preparing_launcher", "Preparing launcher..."), indeterminate=False))
        
        QTimer.singleShot(1200, finish_loading)

    def on_error(message):
        # Keep it indeterminate even on error
        splash.set_progress(0, tr.get("updater_failed", "Update check failed."), indeterminate=True)
        QTimer.singleShot(1500, lambda: splash.set_progress(100, tr.get("splash_starting_anyway", "Starting launcher..."), indeterminate=False))

    splash.show()
    splash.set_progress(0, tr.get("splash_loading_config", "Loading configuration..."), indeterminate=True)
    QApplication.processEvents()

    try:
        from MZLauncher_app.core.bootstrap import preload_modules
        splash.set_progress(0, tr.get("splash_init_modules", "Initializing modules..."), indeterminate=True)
        QApplication.processEvents()
        preload_modules()
        splash.set_progress(0, tr.get("splash_preparing_launcher", "Preparing launcher..."), indeterminate=True)
        QApplication.processEvents()
    except Exception as e:
        print(f"[BOOTSTRAP] Failed to preload modules: {e}")
        splash.set_progress(0, tr.get("splash_starting_anyway", "Starting launcher..."), indeterminate=True)
        QApplication.processEvents()

    splash.set_progress(0, tr.get("updater_checking", "Checking for updates..."), indeterminate=True)

    update_thread = UpdateCheckThread(launcher_args["updater_ver"])
    update_thread.update_available.connect(on_update_available)
    update_thread.up_to_date.connect(on_up_to_date)
    update_thread.error_occurred.connect(on_error)
    update_thread.start()

    app.update_thread = update_thread

    sys.exit(app.exec())