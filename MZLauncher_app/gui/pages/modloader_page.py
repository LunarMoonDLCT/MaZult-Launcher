import os
import traceback
import subprocess
import sys
from pathlib import Path

import xml.etree.ElementTree as ET
from PySide6.QtCore import (QThread, Signal, Qt, QPropertyAnimation, QEasingCurve,
                          Property, QSize, QTimer, QEvent)
from PySide6.QtGui import QFont, QCursor, QPixmap, QPainter, QIcon, QColor
from packaging.version import Version, InvalidVersion
from PySide6.QtWidgets import ( QDialog, QButtonGroup,
    QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QHBoxLayout, QFrame, QGraphicsOpacityEffect,
    QProgressBar, QMessageBox, QGroupBox, QSpacerItem, QSizePolicy
)

from MZLauncher_app.modloader.modloader import modloaderf as ModLoaderFetchThread, ModLoaderInstallThread
from MZLauncher_app.settings.settings import get_minecraft_directory
from MZLauncher_app.core.utils import load_language, resource_path, get_appdata_path

class ModLoaderItem(QFrame):
    clicked = Signal(str)

    def __init__(self, loader_id, text, icon_path, parent=None):
        super().__init__(parent)
        self.loader_id = loader_id
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setObjectName("modloaderItem")
        self.setMinimumHeight(70)
        self.setMaximumHeight(70)
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 10)
        main_layout.setSpacing(15)
        icon_frame = QFrame()
        icon_frame.setObjectName("iconFrame")
        icon_frame.setFixedSize(50, 50)
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel()
        pixmap = QPixmap(resource_path(icon_path))
        if not pixmap.isNull():
            icon_label.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(icon_label)

        text_label = QLabel(text)
        text_label.setFont(QFont("Segoe UI Variable", 16, QFont.Bold))
        text_label.setStyleSheet("background: transparent;")

        main_layout.addWidget(icon_frame)
        main_layout.addWidget(text_label)
        main_layout.addStretch()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.loader_id)
        super().mousePressEvent(event)

class ModLoaderPage(QWidget):
    def __init__(self, launcher):
        super().__init__(launcher)
        self.launcher = launcher
        self.tr = launcher.tr
        self.setObjectName("modloaderPage")

        self.fetched_data = None
        self.fetch_thread = None
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(20, 20, 20, 20)
        page_layout.setSpacing(15)
        title_layout = QHBoxLayout()
        title_layout.setSpacing(12)
        title_label = QLabel(self.tr.get("install_mod_loader_button", "Install Mod Loader"))
        title_label.setFont(QFont("Segoe UI Variable", 24, QFont.Bold))
        title_label.setAlignment(Qt.AlignLeft)

        title_layout.addWidget(title_label)
        title_layout.addStretch()
        page_layout.addLayout(title_layout)        

        self.loader_list_widget = QWidget()
        self.loader_list_layout = QVBoxLayout(self.loader_list_widget)
        self.loader_list_layout.setContentsMargins(0, 0, 0, 0)
        self.loader_list_layout.setSpacing(10)

        self.fabric_item = ModLoaderItem("fabric", "Fabric", "assets/fabric.png")
        self.quilt_item = ModLoaderItem("quilt", "Quilt", "assets/quilt.png")
        self.legacy_fabric_item = ModLoaderItem("legacy-fabric", "Legacy Fabric", "assets/legacy_fabric.png")
        self.forge_item = ModLoaderItem("forge", "Forge", "assets/forge.png")
        self.neoforge_item = ModLoaderItem("neoforge", "NeoForge", "assets/neoforge.png")

        self.loader_list_layout.addWidget(self.fabric_item)
        self.loader_list_layout.addWidget(self.quilt_item)
        self.loader_list_layout.addWidget(self.legacy_fabric_item)
        self.loader_list_layout.addWidget(self.forge_item)
        self.loader_list_layout.addWidget(self.neoforge_item)

        page_layout.addWidget(self.loader_list_widget)
        page_layout.addStretch()

        self.progress_widget = QWidget(self)
        self.progress_widget.setFixedHeight(50)
        self.progress_widget.setObjectName("progressWidget")
        self.progress_widget.setStyleSheet("QWidget#progressWidget { background-color: #0A0D17; border-top: 1px solid rgba(255,255,255,.08); }")
        progress_layout = QVBoxLayout(self.progress_widget)
        progress_layout.setContentsMargins(24, 8, 24, 8)
        progress_layout.setSpacing(5)
        self.status_label = QLabel(self.tr.get("modloader_loading_data", "Loading modloader data..."))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(5)
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)
        self.progress_widget.hide()
        
        self.setStyleSheet("""
            QFrame#modloaderItem {
                background-color: #141826;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 18px;
            }
            QFrame#modloaderItem:hover {
                background-color: #1B2133;
            }
            QFrame#modloaderItem {
                background-color: #141826;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 18px;
            }
            QFrame#iconFrame {
                background: rgba(124,77,255,.18);
                border: 1px solid rgba(255,255,255,.08);
                border-radius: 12px;
            }
        """)
        
        for item in [self.fabric_item, self.quilt_item, self.legacy_fabric_item, self.forge_item, self.neoforge_item]:
            item.clicked.connect(self.on_loader_button_clicked)

        self.animated_items = [self.fabric_item, self.quilt_item, self.legacy_fabric_item, self.forge_item, self.neoforge_item]
        self.prepare_entrance_animation()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.progress_widget.setGeometry(0, self.height() - self.progress_widget.height(), self.width(), self.progress_widget.height())

    def set_ui_loading(self, loading, loader_name="..."):
        self.loader_list_widget.setEnabled(not loading)
        if loading:
            self.status_label.setText(self.tr.get("modloader_loading_data", "Loading modloader data..."))
            self.progress_widget.show()
        else:
            self.progress_widget.hide()

    def on_data_fetched(self, data):
        self.fetched_data = data
        self.set_ui_loading(False)
        if hasattr(self, '_pending_loader_name') and self._pending_loader_name:
            self.launcher.open_modloader_install_page(self._pending_loader_name)
            self._pending_loader_name = None

    def on_fetch_error(self, msg):
        self.set_ui_loading(False)
        QMessageBox.critical(self, self.tr.get('network_error_title', 'Network Error'), self.tr.get('modloader_fetch_error', 'Could not fetch mod loader data:\n{msg}').format(msg=msg))
        self._pending_loader_name = None
        self.fetch_thread = None

    def on_loader_button_clicked(self, loader_name):
        if self.fetched_data:
            self.launcher.open_modloader_install_page(loader_name)
        else:
            if self.fetch_thread and self.fetch_thread.isRunning():
                self.set_ui_loading(True)
                self._pending_loader_name = loader_name
                return
            self.set_ui_loading(True)
            self._pending_loader_name = loader_name
            self.fetch_thread = ModLoaderFetchThread(self)
            self.fetch_thread.loaded.connect(self.on_data_fetched)
            self.fetch_thread.error.connect(self.on_fetch_error)
            self.fetch_thread.finished.connect(self.fetch_thread.deleteLater)
            self.fetch_thread.start()

    def prepare_entrance_animation(self):
        for item in self.animated_items:
            effect = QGraphicsOpacityEffect(item)
            effect.setOpacity(0.0)
            item.setGraphicsEffect(effect)

    def start_entrance_animation(self):
        for i, item in enumerate(self.animated_items):
            effect = item.graphicsEffect()
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(item)
                item.setGraphicsEffect(effect)
            effect.setOpacity(0.0)
            
            anim = QPropertyAnimation(effect, b"opacity", item)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setDuration(300)
            anim.setEasingCurve(QEasingCurve.InOutQuad)
            QTimer.singleShot(100 * i, lambda animation=anim: animation.start(QPropertyAnimation.DeleteWhenStopped))


    def create_install_page(self, loader_name):
        page = InstallPage(loader_name, self.fetched_data, self)
        page.install_requested.connect(self.install_loader)
        page.back_requested.connect(lambda: self.launcher.main_window.set_current_page(self.launcher.page_modloader_index))
        return page

    def install_loader(self, loader, mc_ver, loader_ver):
        install_page = self.launcher.modloader_install_page
        if install_page:
            self.launcher.set_global_installing_state(True, self.tr.get("installing", "Installing..."))

        mc_dir = get_minecraft_directory()

        self.install_thread = ModLoaderInstallThread(loader, mc_ver, loader_ver, mc_dir, self.tr)
        if install_page:
            self.install_thread.status.connect(self.launcher.set_progress_status)
            self.install_thread.progress.connect(self.launcher.set_progress_value)
        self.install_thread.done.connect(self.on_install_done)
        self.install_thread.error.connect(self.on_install_error)
        self.install_thread.java_not_found.connect(self.on_java_not_found)
        self.install_thread.start()

    def on_install_done(self, msg):
        self.install_thread.quit()
        self.install_thread.wait()
        self.launcher.set_global_installing_state(False)
        QMessageBox.information(self, self.tr.get('success_title', 'Success'), msg)
        self.launcher.load_versions()
        self.launcher.go_home()

    def on_java_not_found(self):
        self.install_thread.quit()
        self.install_thread.wait()
        self.launcher.set_global_installing_state(False)

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle(self.tr.get('modloader_java_not_found_title', 'Java Not Found'))
        
        text = self.tr.get('modloader_java_not_found_text', 'Java could not be found...')
        link_text = self.tr.get('modloader_java_download_link_text', 'Download Java from Oracle.com')
        msg_box.setText(f'{text}<br><a href="https://www.oracle.com/java/technologies/downloads/">{link_text}</a>')
        msg_box.setTextFormat(Qt.RichText)
        msg_box.exec()

    def on_install_error(self, msg):
        self.install_thread.quit()
        self.install_thread.wait()
        self.launcher.set_global_installing_state(False)
        QMessageBox.critical(self, self.tr.get('install_error_title', 'Installation Error'), msg)

class InstallPage(QWidget):
    install_requested = Signal(str, str, str)
    back_requested = Signal()

    def __init__(self, loader_name, fetched_data, parent=None):
        super().__init__(parent)
        self.loader_name = loader_name
        self.fetched_data = fetched_data
        self.tr = parent.tr if parent and hasattr(parent, 'tr') else load_language()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        header_layout = QHBoxLayout()
        self.back_button = QPushButton()
        self.back_button.setIcon(QIcon(resource_path("assets/back.png")))
        self.back_button.setIconSize(QSize(24, 24))
        self.back_button.setFixedSize(40, 40)
        self.back_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.back_button.setObjectName("backButton")
        self.back_button.clicked.connect(self.back_requested.emit)
        self.back_button.setStyleSheet("""
            QPushButton#backButton {
                background-color: transparent;
                border: none;
                border-radius: 20px; /* half of fixed size */
            }
            QPushButton#backButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        title_label = QLabel(self.tr.get('modloader_dialog_title', 'Install Mod Loader') + f" ({loader_name.capitalize()})")
        title_label.setFont(QFont("Segoe UI Variable", 22, QFont.Bold))
        header_layout.addWidget(self.back_button)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self.main_widget = QWidget()
        main_layout = QVBoxLayout(self.main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)
        
        self.mc_version_label = QLabel(self.tr.get('modloader_mc_version_label', 'Minecraft Version:'))
        self.mc_version_combo = QComboBox()

        self.loader_version_label = QLabel(self.tr.get('modloader_loader_version_label', 'Loader Version:'))
        self.loader_version_combo = QComboBox()

        self.status_label = QLabel(self.tr.get("modloader_loading_data", "Loading modloader data..."))
        self.loading_progress_bar = QProgressBar()
        self.loading_progress_bar.setRange(0, 0)

        main_layout.addWidget(self.mc_version_label)
        main_layout.addWidget(self.mc_version_combo)
        main_layout.addWidget(self.loader_version_label)
        main_layout.addWidget(self.loader_version_combo)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.loading_progress_bar)
        self.install_btn = QPushButton(self.tr.get('modloader_install_button', 'Install'))
        self.install_btn.setObjectName("playButton") # Use play button style
        self.install_btn.setMinimumHeight(40)
        self.install_btn.clicked.connect(self.on_install_clicked)
        self.install_btn.setEnabled(False)
        main_layout.addWidget(self.install_btn)
        main_layout.addStretch()

        layout.addWidget(self.main_widget)
        layout.addStretch()

        self.mc_version_combo.currentTextChanged.connect(self.load_loader_versions)
        self.mc_version_label.hide()
        self.mc_version_combo.hide()
        self.loader_version_label.hide()
        self.loader_version_combo.hide()
        if self.loader_name == 'quilt':
            self.mc_version_label.hide()
            self.mc_version_combo.hide()


        if self.fetched_data:
            self.set_ui_loaded(True)
            self.populate_mc_versions()
        elif self.loader_name != 'quilt':
            self.set_ui_loaded(False, error=True)

    def on_install_clicked(self):
        mc_ver = ''
        if self.loader_name != 'quilt':
            mc_ver = self.mc_version_combo.currentText()
        loader_ver = self.loader_version_combo.itemData(self.loader_version_combo.currentIndex()) or self.loader_version_combo.currentText()
        self.install_requested.emit(self.loader_name, mc_ver, loader_ver)

    def set_ui_loaded(self, loaded, error=False):
        self.status_label.hide()
        self.loading_progress_bar.hide()
        if loaded:
            self.status_label.hide()
            if self.loader_name != 'quilt':
                self.mc_version_label.show()
                self.mc_version_combo.show()
            self.loader_version_label.show()
            self.loader_version_combo.show()
            self.install_btn.setEnabled(True)
        else:
            if error:
                self.status_label.setText(self.tr.get("modloader_fetch_error_short", "Failed to load data."))
                self.status_label.show()
            self.install_btn.setEnabled(False)

    def populate_mc_versions(self):
        self.mc_version_combo.clear()
        self.loader_version_combo.clear()

        is_quilt = self.loader_name == 'quilt'
        self.loader_version_label.setText(
            self.tr.get('modloader_installer_version_label', 'Installer Version:') if is_quilt
            else self.tr.get('modloader_loader_version_label', 'Loader Version:'))

        if not self.fetched_data:
            return

        mc_versions = []
        try:
            def version_key(v_str):
                try:
                    return Version(v_str)
                except InvalidVersion:
                    return Version("0.0.0")

            if self.loader_name == 'fabric':
                mc_versions = sorted([v['version'] for v in self.fetched_data['fabric']['game'] if v['stable']], key=version_key, reverse=True)
            elif self.loader_name == 'legacy-fabric':
                mc_versions = sorted([v['version'] for v in self.fetched_data['legacy-fabric']['game'] if v['stable']], key=version_key, reverse=True)
            elif self.loader_name == 'forge':
                root = ET.fromstring(self.fetched_data[self.loader_name])
                versions_element = root.find('versioning/versions')
                if versions_element is not None:
                    all_versions = [v.text for v in versions_element.findall('version') if v.text]
                    mc_versions = sorted(list(set(v.split('-', 1)[0] for v in all_versions)), key=version_key, reverse=True)
            elif self.loader_name == 'neoforge':
                root = ET.fromstring(self.fetched_data[self.loader_name])
                versions_element = root.find('versioning/versions')
                if versions_element is not None:
                    mc_versions = [v.text for v in versions_element.findall('version') if v.text]

            if self.loader_name == 'quilt':
                self.load_loader_versions()
            elif mc_versions:
                from PySide6.QtCore import QTimer
                self.mc_version_combo.addItems(mc_versions)
                self.mc_version_combo.setCurrentIndex(0)
                self.load_loader_versions()
            else:
                self.mc_version_combo.addItem(self.tr.get('modloader_no_versions_available', 'No loader available'))
                self.mc_version_combo.setEnabled(False)

        except Exception as e:

            QMessageBox.warning(self, self.tr.get('error_title', 'Error'), self.tr.get('modloader_parse_mc_version_error', 'Could not parse supported Minecraft versions for {loader_name}.').format(loader_name=self.loader_name.capitalize()))

    def load_loader_versions(self, mc_version_text=None):
        self.loader_version_combo.clear()
        mc_ver = self.mc_version_combo.currentText() if self.loader_name != 'quilt' else 'any'

        if not self.fetched_data or not mc_ver:
            self.loader_version_combo.setEnabled(False)
            return

        versions = []
        try:
            if self.loader_name == 'fabric':
                versions = [v['version'] for v in self.fetched_data['fabric']['loader']]
            elif self.loader_name == 'legacy-fabric':
                versions = [v['version'] for v in self.fetched_data['legacy-fabric']['loader']]
            elif self.loader_name == 'quilt':
                versions = [v['version'] for v in self.fetched_data['quilt']]
            elif self.loader_name == 'forge':
                root = ET.fromstring(self.fetched_data[self.loader_name])
                versions = [v.text for v in root.findall('versioning/versions/version') if v.text and v.text.startswith(mc_ver + '-')]
            elif self.loader_name == 'neoforge':
                root = ET.fromstring(self.fetched_data[self.loader_name])
                versions = [v.text for v in root.findall('versioning/versions/version') if v.text and v.text.startswith(mc_ver)]

            if not versions:
                self.loader_version_combo.addItem(self.tr.get('modloader_no_versions_available', 'No loader available'))
                self.loader_version_combo.setEnabled(False)
                return

            for v in versions:
                self.loader_version_combo.addItem(v.split('-', 1)[1] if self.loader_name == 'forge' else v, v)
            self.loader_version_combo.setCurrentIndex(0)
            self.loader_version_combo.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, self.tr.get('modloader_error_title', 'Loader Error'), self.tr.get('modloader_get_versions_error', 'Could not get loader versions for {mc_ver}:\n{e}').format(mc_ver=mc_ver, e=e))
            self.loader_version_combo.setEnabled(False)