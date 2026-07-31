import os
import sys
import psutil
import webbrowser
import shlex
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFrame, QDialog, QCheckBox, QMessageBox,
    QTabWidget, QSlider, QScrollArea, QListWidget, QDialogButtonBox, QButtonGroup,
    QGroupBox, QPlainTextEdit, QRadioButton, QStackedWidget, QSpacerItem, QSizePolicy
)
from PySide6.QtGui import QFont, QCursor, QIcon, QColor
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QTimer, QRect, QSize, QPoint, Property, QEvent
from PySide6.QtWidgets import QFileDialog, QApplication

from MZLauncher_app.settings.settings import get_minecraft_directory, load_settings, save_settings
from MZLauncher_app.core.utils import (list_available_languages, load_language, resource_path, get_appdata_path,
                                       Launcher_profiles_json)

def format_jvm_args(args: list[str]) -> str:
    result = []
    for arg in args:
        if " " in arg or "\t" in arg:
            escaped = arg.replace('"', '\\"')
            result.append(f'"{escaped}"')
        else:
            result.append(arg)
    return " ".join(result)

class NotificationToast(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.effect = QPropertyAnimation(self, b"windowOpacity")
        self.effect.setDuration(300)
        self.effect.setEasingCurve(QEasingCurve.InOutQuad)
        self.effect.setStartValue(0.0)
        self.effect.setEndValue(1.0)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._start_hide_animation)

        layout = QVBoxLayout(self)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 24, 38, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 12px;
                color: white;
                font-size: 15px;
                padding: 10px 20px;
            }
        """)

    def show_toast(self, message, timeout=3000):
        self.label.setText(message)
        self.adjustSize()

        if self.parentWidget():
            parent_rect = self.parentWidget().geometry()
            self.move(
                parent_rect.x() + (parent_rect.width() - self.width()) / 2,
                parent_rect.y() + parent_rect.height() - self.height() - 20
            )
        self.setWindowOpacity(0.0)
        self.effect.setDirection(QPropertyAnimation.Forward)
        self.effect.start()
        self.show()
        self.timer.start(timeout)

    def _start_hide_animation(self):
        self.effect.setDirection(QPropertyAnimation.Backward)
        self.effect.start()
        QTimer.singleShot(self.effect.duration(), self.hide)

class SettingCard(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("settingCard")

        self.setMouseTracking(True)
        
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(15)

        title_label = QLabel(title)
        title_label.setObjectName("settingCardTitle")
        card_layout.addWidget(title_label)
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 5, 0, 0)
        self.content_layout.setSpacing(15)
        card_layout.addLayout(self.content_layout)

class SettingsPage(QWidget):
    refreshVersions = Signal()

    def __init__(self, parent=None, tr=None):
        super().__init__(parent)
        self.tr = tr if tr else load_language()
        self.setObjectName("settingsPage")
        
        self.jvm_args_list = load_settings().get("jvm_args", [])

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 20, 20, 10)
        header_title_layout = QVBoxLayout()
        title_label = QLabel(self.tr.get("settings", "Settings"))
        title_label.setFont(QFont("Segoe UI Variable", 24, QFont.Bold))
        subtitle = QLabel("Customize your launcher experience.")
        subtitle.setStyleSheet("color: #A0A0A0; font-size: 15px;")
        header_title_layout.addWidget(title_label)
        header_title_layout.addWidget(subtitle)
        header_layout.addLayout(header_title_layout)
        header_layout.addStretch()
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.scroll_content = QWidget()
        self.main_settings_container = QWidget(self.scroll_content)
        main_settings_container_layout = QVBoxLayout(self.main_settings_container)
        main_settings_container_layout.setContentsMargins(0,0,0,0)

        content_layout = QVBoxLayout(self.scroll_content)
        content_layout.setContentsMargins(20, 20, 20, 30)
        content_layout.setSpacing(14)
        content_layout.addWidget(self.create_path_settings())
        content_layout.addWidget(self.create_launcher_settings())
        content_layout.addWidget(self.create_performance_settings())
        content_layout.addWidget(self.create_about_section())

        content_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_content)
        main_content_widget = QWidget()
        main_content_layout = QVBoxLayout(main_content_widget)
        main_content_layout.setContentsMargins(0,0,0,0)
        main_content_layout.setSpacing(0)

        main_content_layout.addWidget(header_widget)
        main_content_layout.addWidget(self.scroll_area)

        save_button_container = QFrame()
        save_button_container.setObjectName("saveButtonContainer")
        save_button_layout = QHBoxLayout(save_button_container)
        save_button_layout.setContentsMargins(20, 10, 20, 10)

        self.revert_button = QPushButton(self.tr.get("revert_changes", "Revert Changes"))
        self.revert_button.setObjectName("transparentButton")
        self.revert_button.setFixedSize(170, 42)
        self.revert_button.clicked.connect(self.load_settings_to_ui)
        self.revert_button.hide()
        save_button_layout.addWidget(self.revert_button)

        self.reset_default_button_header = QPushButton(self.tr.get("reset_to_default", "Reset All Settings to Default"))
        self.reset_default_button_header.setObjectName("transparentButton")
        self.reset_default_button_header.clicked.connect(self.reset_all_settings_to_default)
        header_layout.addWidget(self.reset_default_button_header)

        save_button_layout.addStretch()
        self.save_button = QPushButton(self.tr.get("save_settings", "Save Settings"))
        self.save_button.setObjectName("playButton")
        self.save_button.setFixedSize(170, 42)
        self.save_button.clicked.connect(self.save_settings_action)
        self.save_button.setEnabled(False)
        save_button_layout.addWidget(self.save_button)
        
        main_content_layout.addWidget(save_button_container)
        
        self.setLayout(main_content_layout)
        self.notification_toast = NotificationToast(parent)
        self.notification_toast = NotificationToast(self.window())
        self.unsaved_dialog = self.create_unsaved_changes_dialog()

        self.load_settings_to_ui()
        self.connect_change_signals()

        self.setStyleSheet("""
            QDialog#unsavedOverlay {
                background-color: rgba(9, 11, 20, 0.7);
            }
            QFrame#saveButtonContainer {
                border-top: 1px solid rgba(255, 255, 255, .08);
                background-color: #0A0D17;
            }
            QPushButton#transparentButton {
                background: rgba(10, 13, 23, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
                color: #F5F6FA;
                font: 15px "Segoe UI Variable";
            }
            QPushButton#transparentButton:hover {
                background: rgba(10, 13, 23, 0.7);
            }
            QFrame#settingCard {
                background-color: #141826;
                border-radius: 20px;
            }
            QFrame#settingCard:hover {
                background-color: #181d2c;
            }
            QLabel#settingCardTitle {
                font-size: 22px;
                font-weight: 700;
                color: #F5F6FA;
                background: transparent;
                border: none;
            }
            QGroupBox {
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #A0A0A0;
            }
            QCheckBox#transparentCheckbox {
                spacing: 8px;
                background: rgba(10, 13, 23, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
                color: #F5F6FA;
                font: 15px "Segoe UI Variable";
                padding: 8px 12px;
            }
            QCheckBox#transparentCheckbox:hover {
                background: rgba(10, 13, 23, 0.7);
            }
            QCheckBox#transparentCheckbox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox#transparentCheckbox::indicator:unchecked {
                image: url(assets/unchecked.png);
            }
            QCheckBox#transparentCheckbox::indicator:checked {
                image: url(assets/checked.png);
            }
        """)

    def resizeEvent(self, event):
        if self.unsaved_dialog.isVisible():
            self.unsaved_dialog.resize(self.window().size())
        super().resizeEvent(event)

    def show_unsaved_changes_prompt(self):
        self.unsaved_dialog.exec()

    def create_unsaved_changes_dialog(self):
        dialog = QDialog(self.window())
        dialog.setObjectName("unsavedOverlay")
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        dialog.setAttribute(Qt.WA_TranslucentBackground)
        dialog.setModal(True)
        close_button = QPushButton("✕")
        close_button.setObjectName("dialogCloseButton")
        close_button.setFixedSize(32, 32)
        close_button.setCursor(QCursor(Qt.PointingHandCursor))
        close_button.clicked.connect(self.discard_changes)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        discard_button = QPushButton("Hủy bỏ thay đổi")
        discard_button.setObjectName("transparentButton")
        discard_button.clicked.connect(self.discard_changes)

        save_button = QPushButton("Lưu và tiếp tục")
        save_button.setObjectName("playButton")
        save_button.clicked.connect(self.save_and_hide_bar)

        button_layout.addWidget(discard_button)
        button_layout.addWidget(save_button)

        title = QLabel("Thay đổi chưa được lưu")
        title.setFont(QFont("Segoe UI Variable", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)

        message = QLabel("Bạn có các thay đổi chưa được lưu. Bạn muốn làm gì?")
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignCenter)
        
        dialog_content_widget = QFrame()
        dialog_content_widget.setObjectName("unsavedDialog")
        dialog_content_widget.setFixedSize(450, 200)
        content_layout = QVBoxLayout(dialog_content_widget)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(15)
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        close_button.setParent(dialog_content_widget)
        close_button.move(dialog_content_widget.width() - close_button.width() - 8, 8)

        content_layout.addWidget(title)
        content_layout.addWidget(message)
        content_layout.addStretch()
        content_layout.addLayout(button_layout)
        dialog_layout.addWidget(dialog_content_widget, 0, Qt.AlignCenter)

        dialog.setStyleSheet("""
            QFrame#unsavedDialog {
                background-color: #141826;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 20px;
            }
            QFrame#unsavedDialog QLabel {
                background: transparent;
                border: none;
                padding: 0;
                margin: 0;
            }
            QPushButton#dialogCloseButton {
                background-color: transparent;
                border: none;
                color: #A0A0A0;
                font-size: 20px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton#dialogCloseButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
            }
        """)
        return dialog

    def create_path_settings(self):
        card = SettingCard(self.tr.get("general_tab", "General"))
        layout = card.content_layout

        mc_dir_group = QGroupBox(self.tr.get("minecraft_directory", "Minecraft Directory"))
        mc_dir_layout = QVBoxLayout(mc_dir_group)
        mc_dir_layout.addWidget(QLabel("The folder where Minecraft is installed."))
        
        row = QHBoxLayout()
        self.mc_dir_input = QLineEdit(str(get_minecraft_directory()))
        self.mc_dir_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.mc_dir_browse_btn = QPushButton(self.tr.get("browse", "Browse"))
        self.mc_dir_browse_btn.clicked.connect(self.browse_mc_dir)
        row.addWidget(self.mc_dir_input)
        row.addWidget(self.mc_dir_browse_btn)
        mc_dir_layout.addLayout(row)
        layout.addWidget(mc_dir_group)

        java_groupbox = QGroupBox(self.tr.get("java_runtime_group", "Java Runtime"))
        java_layout = QVBoxLayout(java_groupbox)
        self.java_default_radio = QRadioButton(self.tr.get("java_default_radio", "Use default Java (built-in)"))
        self.java_custom_radio = QRadioButton(self.tr.get("java_custom_radio", "Use custom Java path"))
        self.java_default_radio.toggled.connect(self.update_java_ui_state)
        self.java_path_input = QLineEdit(placeholderText=self.tr.get("java_path_placeholder", "Path to Java folder (contains java.exe)"))
        self.java_browse_btn = QPushButton(self.tr.get("browse", "Browse"))
        self.java_browse_btn.clicked.connect(self.browse_java_path)
        java_path_row = QHBoxLayout()
        java_path_row.addWidget(self.java_path_input)
        java_path_row.addWidget(self.java_browse_btn)
        java_layout.addWidget(self.java_default_radio)
        java_layout.addWidget(self.java_custom_radio)
        java_layout.addSpacing(8)
        java_layout.addLayout(java_path_row)
        layout.addWidget(java_groupbox)

        return card

    def create_performance_settings(self):
        card = SettingCard("Performance")
        layout = card.content_layout

        ram_group = QGroupBox()
        ram_layout = QVBoxLayout(ram_group)        
        top = QHBoxLayout()
        top.addWidget(QLabel(self.tr.get("ram_allocation", "RAM Allocation")))
        top.addStretch()
        self.ram_slider = QSlider(Qt.Horizontal)
        self.ram_slider.setMinimum(512)
        self.ram_slider.setMaximum(psutil.virtual_memory().total // (1024 * 1024) - 512)
        self.ram_slider.setSingleStep(512)
        self.ram_label = QLabel()
        top.addWidget(self.ram_label)
        self.ram_slider.valueChanged.connect(self.update_ram_label)
        ram_layout.addLayout(top)
        ram_layout.addWidget(self.ram_slider)
        layout.addWidget(ram_group)

        layout.addWidget(QLabel("Launch Arguments"))
        layout.addWidget(QLabel("Additional JVM arguments"))
        self.jvm_button = QPushButton(self.tr.get("jvm_args_button", "Edit Arguments"))
        self.jvm_button.clicked.connect(self.open_jvm_dialog)
        layout.addWidget(self.jvm_button, 0, Qt.AlignLeft)

        layout.addSpacing(10)
        filter_groupbox = QGroupBox(self.tr.get("filters", "Version Filters"))
        filter_layout = QHBoxLayout(filter_groupbox)
        self.release_checkbox = QCheckBox(self.tr.get("release", "Release"))
        self.release_checkbox.setObjectName("transparentCheckbox")
        self.release_checkbox.setProperty("class", "settingCheckBox")
        self.snapshot_checkbox = QCheckBox(self.tr.get("snapshot", "Snapshot"))
        self.snapshot_checkbox.setObjectName("transparentCheckbox")
        self.snapshot_checkbox.setProperty("class", "settingCheckBox")
        self.beta_checkbox = QCheckBox(self.tr.get("beta", "Beta"))
        self.beta_checkbox.setObjectName("transparentCheckbox")
        self.beta_checkbox.setProperty("class", "settingCheckBox")
        self.alpha_checkbox = QCheckBox(self.tr.get("alpha", "Alpha"))
        self.alpha_checkbox.setObjectName("transparentCheckbox")
        self.alpha_checkbox.setProperty("class", "settingCheckBox")
        self.installed_checkbox = QCheckBox(self.tr.get("installed", "Installed Versions"))
        self.installed_checkbox.setObjectName("transparentCheckbox")
        self.installed_checkbox.setProperty("class", "settingCheckBox")
        filter_layout.addWidget(self.release_checkbox)
        filter_layout.addWidget(self.snapshot_checkbox)
        filter_layout.addWidget(self.beta_checkbox)
        filter_layout.addWidget(self.alpha_checkbox)
        filter_layout.addWidget(self.installed_checkbox)
        filter_layout.addStretch()
        
        layout.addWidget(filter_groupbox)
        layout.addSpacing(10)
        self.skip_check_checkbox = QCheckBox(self.tr.get("skip_version_check_checkbox", "Skip version verification (launch instantly)"))
        self.skip_check_checkbox.setToolTip(self.tr.get("skip_version_check_tooltip", "..."))
        self.skip_check_checkbox.setObjectName("transparentCheckbox")
        self.skip_check_checkbox.setProperty("class", "settingCheckBox")
        layout.addWidget(self.skip_check_checkbox)

        return card

    def create_launcher_settings(self):
        card = SettingCard(self.tr.get("launcher_settings_tab", "Launcher Settings"))
        layout = card.content_layout

        lang_layout = QHBoxLayout()
        lang_label = QLabel(self.tr.get("language", "Language:"))
        self.lang_combo = QComboBox()
        available_langs = list_available_languages()
        self.lang_codes = list(available_langs.keys())
        for code in self.lang_codes:
            self.lang_combo.addItem(available_langs[code])
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.lang_combo)
        layout.addLayout(lang_layout)

        def add_separator():
            layout.addSpacing(8)
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet("border-color: rgba(255,255,255,0.05);")
            layout.addWidget(line)
            layout.addSpacing(8)
        add_separator()
        self.discord_rpc_checkbox = QCheckBox(self.tr.get("discord_rpc", "Show status launcher in Discord"), card)
        self.discord_rpc_checkbox.setObjectName("transparentCheckbox")
        self.discord_rpc_checkbox.setProperty("class", "settingCheckBox")
        layout.addWidget(self.discord_rpc_checkbox)
        add_separator()
        self.hide_on_launch_checkbox = QCheckBox(self.tr.get("hide_launcher", "Don't hide launcher when running Minecraft"), card)
        self.hide_on_launch_checkbox.setObjectName("transparentCheckbox")
        self.hide_on_launch_checkbox.setProperty("class", "settingCheckBox")
        layout.addWidget(self.hide_on_launch_checkbox)
        add_separator()
        self.dev_console_checkbox = QCheckBox(self.tr.get("dev_console", "Dev Console"), card)
        self.dev_console_checkbox.setObjectName("transparentCheckbox")
        self.dev_console_checkbox.setProperty("class", "settingCheckBox")
        layout.addWidget(self.dev_console_checkbox)

        return card

    def create_about_section(self):
        card = SettingCard(self.tr.get("about_tab", "About"))
        layout = card.content_layout

        launcher_name_label = QLabel(self.tr.get("launcher_name_label", "MaZult Launcher"))
        launcher_name_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        creator_label = QLabel(self.tr.get("creator", "Creator: LunarMoonDLCT"))
        layout.addWidget(launcher_name_label, 0, Qt.AlignHCenter)
        layout.addWidget(creator_label, 0, Qt.AlignHCenter)
        layout.addSpacing(10)

        libraries_title = QLabel(self.tr.get("third_party_libs", "Third-Party Libraries:"))
        libraries_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        layout.addWidget(libraries_title)
        
        libs = QListWidget()
        libs.addItems([
            "PySide6",
            "minecraft-launcher-lib",
            "requests",
            "psutil",
            "packaging",
            "pypresence"
        ])
        libs.setMinimumHeight(180)
        layout.addWidget(libs)

        source_code_title = QLabel(self.tr.get("source_code", "Source Code Launcher:"))
        source_code_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        layout.addWidget(source_code_title)

        source_code_button = QPushButton(self.tr.get("open_github", "Open GitHub Repository"))
        source_code_button.clicked.connect(self.open_github_link)
        layout.addWidget(source_code_button, 0, Qt.AlignLeft)

        return card

    def open_jvm_dialog(self):
        dialog = QDialog(self.window())
        dialog.setWindowTitle(self.tr.get("jvm_dialog_title", "Edit JVM Arguments"))
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        edit = QPlainTextEdit(format_jvm_args(self.jvm_args_list))
        edit.setMinimumHeight(200)
        layout.addWidget(edit)
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        layout.addWidget(button_box)
        def save_and_close():
            text = edit.toPlainText().strip()
            self.jvm_args_list = shlex.split(text) if text else []
            dialog.accept()
        button_box.accepted.connect(save_and_close)
        button_box.rejected.connect(dialog.reject)
        dialog.exec()
        self.on_setting_changed()

    def save_settings_action(self):
        self.save_and_hide_bar()
        
        main_window = self.window()
        if hasattr(main_window, 'notification_toast'):
            main_window.notification_toast.show_toast(self.tr.get("settings_saved_message", "Your settings have been saved successfully."))


    def save_and_hide_bar(self):
        old_settings = load_settings()
        mc_dir = self.mc_dir_input.text().strip()
        if not Path(mc_dir).exists():
            try:
                os.makedirs(mc_dir)
            except Exception as e:
                QMessageBox.critical(self, self.tr.get("create_dir_failed", "Creation Failed"), f"Failed to create directory: {mc_dir}\nError: {e}")
                return
        Launcher_profiles_json(mc_dir)

        filters = {
            "release": self.release_checkbox.isChecked(),
            "snapshot": self.snapshot_checkbox.isChecked(),
            "beta": self.beta_checkbox.isChecked(),
            "alpha": self.alpha_checkbox.isChecked(),
            "installed": self.installed_checkbox.isChecked(),
        }
        
        language = self.lang_codes[self.lang_combo.currentIndex()]

        save_settings(
            ram_mb=self.ram_slider.value(), 
            mc_dir=mc_dir, 
            filters=filters, 
            dev_console=self.dev_console_checkbox.isChecked(), 
            hide_on_launch=not self.hide_on_launch_checkbox.isChecked(), 
            jvm_args=self.jvm_args_list,
            discord_rpc=self.discord_rpc_checkbox.isChecked(),
            language=language,
            java_mode="custom" if self.java_custom_radio.isChecked() else "default",
            java_path=self.java_path_input.text().strip(),
            skip_version_check=self.skip_check_checkbox.isChecked()
        )
        
        self.save_button.setEnabled(False)
        self.revert_button.hide()
        self.unsaved_dialog.accept()
        main_window = self.window()
        if old_settings.get("language") != language:
            reply = QMessageBox.question(self, self.tr.get("language_changed_title", "Language Changed"), self.tr.get("language_changed_message", "Please restart the launcher to apply the new language."), QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                main_window.restart_app()

        if hasattr(main_window, "dev_console"):
            if self.dev_console_checkbox.isChecked() and main_window.dev_console.isHidden():
                main_window.dev_console.show()
            elif not self.dev_console_checkbox.isChecked() and main_window.dev_console.isVisible():
                main_window.dev_console.hide()

        if hasattr(main_window, "reconnect_rpc") and old_settings.get("discord_rpc") != self.discord_rpc_checkbox.isChecked():
            main_window.reconnect_rpc()
        self.refreshVersions.emit()

    def discard_changes(self):
        self.load_settings_to_ui()
        self.unsaved_dialog.reject()


    def open_github_link(self):
        webbrowser.open("https://github.com/LunarMoonDLCT/MaZult-Launcher")

    def update_ram_label(self, value):
        self.ram_label.setText(self.tr.get("ram_allocated", "Allocated RAM: {value} MB").format(value=value))

    def browse_mc_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, self.tr.get("select_mc_dir_title", "Select Minecraft Directory"))
        if dir_path:
            self.mc_dir_input.setText(dir_path)

    def browse_java_path(self):
        dir_path = QFileDialog.getExistingDirectory(self, self.tr.get("select_java_folder_title", "Select Java Folder"))
        if dir_path:
            self.java_path_input.setText(dir_path)

    def update_java_ui_state(self):
        use_custom = self.java_custom_radio.isChecked()
        self.java_path_input.setEnabled(use_custom)
        self.java_browse_btn.setEnabled(use_custom)

    def on_setting_changed(self):
        self.save_button.setEnabled(True)
        self.revert_button.show()

    def connect_change_signals(self):
        self.mc_dir_input.textChanged.connect(self.on_setting_changed)
        self.ram_slider.valueChanged.connect(self.on_setting_changed)
        self.java_default_radio.toggled.connect(self.on_setting_changed)
        self.java_path_input.textChanged.connect(self.on_setting_changed)
        self.lang_combo.currentIndexChanged.connect(self.on_setting_changed)
        self.release_checkbox.stateChanged.connect(self.on_setting_changed)
        self.snapshot_checkbox.stateChanged.connect(self.on_setting_changed)
        self.beta_checkbox.stateChanged.connect(self.on_setting_changed)
        self.alpha_checkbox.stateChanged.connect(self.on_setting_changed)
        self.installed_checkbox.stateChanged.connect(self.on_setting_changed)
        self.hide_on_launch_checkbox.stateChanged.connect(self.on_setting_changed)
        self.discord_rpc_checkbox.stateChanged.connect(self.on_setting_changed)
        self.dev_console_checkbox.stateChanged.connect(self.on_setting_changed)
        self.skip_check_checkbox.stateChanged.connect(self.on_setting_changed)

    def load_settings_to_ui(self):
        settings = load_settings()
        for widget in self.findChildren(QWidget):
            widget.blockSignals(True)

        self.mc_dir_input.setText(str(get_minecraft_directory()))
        self.ram_slider.setValue(settings.get("ram_mb", 2048))
        self.update_ram_label(self.ram_slider.value())
        self.jvm_args_list = settings.get("jvm_args", [])

        java_mode = settings.get("java_mode", "default")
        self.java_default_radio.setChecked(java_mode == "default")
        self.java_custom_radio.setChecked(java_mode == "custom")
        self.java_path_input.setText(settings.get("java_path", ""))
        self.update_java_ui_state()

        lang_code = settings.get("language", "en_us")
        try:
            lang_index = self.lang_codes.index(lang_code)
            self.lang_combo.setCurrentIndex(lang_index)
        except ValueError:
            self.lang_combo.setCurrentIndex(0)

        current_filters = settings.get("filters", {})
        self.release_checkbox.setChecked(current_filters.get("release", True))
        self.snapshot_checkbox.setChecked(current_filters.get("snapshot", False))
        self.beta_checkbox.setChecked(current_filters.get("beta", False))
        self.alpha_checkbox.setChecked(current_filters.get("alpha", False))
        self.installed_checkbox.setChecked(current_filters.get("installed", True))

        self.hide_on_launch_checkbox.setChecked(not settings.get("hide_on_launch", True))
        self.discord_rpc_checkbox.setChecked(settings.get("discord_rpc", True))
        self.dev_console_checkbox.setChecked(settings.get("dev_console", False))
        self.skip_check_checkbox.setChecked(settings.get("skip_version_check", False))

        for widget in self.findChildren(QWidget):
            widget.blockSignals(False)
        self.save_button.setEnabled(False)
        self.revert_button.hide()
        self.unsaved_dialog.accept()

    def reset_all_settings_to_default(self):
        reply = QMessageBox.question(self, self.tr.get("reset_settings_title", "Reset Settings"), self.tr.get("reset_settings_confirm", "Are you sure you want to reset all settings to their default values? This cannot be undone."), QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            save_settings(_reset_to_default=True)
            self.load_settings_to_ui()
            self.on_setting_changed()