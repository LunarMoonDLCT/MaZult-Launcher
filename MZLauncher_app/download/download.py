import os
import shutil
import subprocess
import sys
import requests
import minecraft_launcher_lib
from pathlib import Path
from PySide6.QtCore import QThread, Signal

from MZLauncher_app.settings.settings import get_appdata_path, get_minecraft_directory


class DownloadThread(QThread):
    progress_signal = Signal(str, int, int, float)
    status_signal = Signal(str)
    value_signal = Signal(int)
    max_signal = Signal(int)
    finished_signal = Signal(bool)

    def __init__(self, version_id, minecraft_directory, tr=None):
        super().__init__()
        self.version_id = version_id
        self.minecraft_directory = minecraft_directory
        self._cancelled = False
        self.is_running = True
        self.tr = tr if tr else {}

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            minecraft_launcher_lib.install.install_minecraft_version(
                self.version_id,
                self.minecraft_directory,
                callback={
                    'setStatus': self.status_signal.emit,
                    'setProgress': self.value_signal.emit,
                    'setMax': self.max_signal.emit,
                    'setFile': self._on_file,
                },
            )
            self.finished_signal.emit(not self._cancelled)
        except Exception as e:
            if str(e) == 'Download cancelled':
                print(self.tr.get('download_thread_cancelled_log', 'Download thread finished because it was cancelled.'))
            else:
                print(f"{self.tr.get('download_error_log', 'Download error:')} {e}")
            self.finished_signal.emit(False)
        finally:
            self.is_running = False

    def _on_file(self, text, cur, tot, spd):
        if self._cancelled:
            raise Exception('Download cancelled')
        self.progress_signal.emit(text, cur, tot, spd)
