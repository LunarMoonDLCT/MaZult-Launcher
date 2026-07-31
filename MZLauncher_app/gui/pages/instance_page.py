import os
import json
import sys
import subprocess
import shutil
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QFrame,
    QDialog, QLineEdit, QComboBox, QDialogButtonBox, QMessageBox, QListWidgetItem, QInputDialog, QCheckBox, QScrollArea
)
from PySide6.QtGui import QFont, QCursor, QIcon, QPixmap
from PySide6.QtCore import Qt, Signal, QSize
from pathlib import Path

from MZLauncher_app.settings.settings import load_settings, save_settings, get_minecraft_directory
from MZLauncher_app.core.utils import get_installed_versions, get_available_versions, minecraft_version_key, resource_path


def get_instances_file():
    return get_minecraft_directory() / "instances" / "instances.json"

def load_instances():
    instances_file = get_instances_file()
    if not instances_file.exists():
        return []
    try:
        with open(instances_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

def save_instances(instances):
    instances_file = get_instances_file()
    instances_file.parent.mkdir(parents=True, exist_ok=True)
    with open(instances_file, "w", encoding="utf-8") as f:
        json.dump(instances, f, indent=4)

class AddInstanceDialog(QDialog):
    def __init__(self, parent=None, tr=None):
        super().__init__(parent)
        self.tr = tr
        self.setWindowTitle(tr.get("add_instance_title", "Add New Instance"))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr.get("instance_name_label", "Instance Name:")))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(tr.get("instance_name_placeholder", "e.g., My Modded Pack"))
        layout.addWidget(self.name_input)
        layout.addWidget(QLabel(tr.get("minecraft_version_label", "Minecraft Version:")))
        self.version_combo = QComboBox()
        layout.addWidget(self.version_combo)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.populate_versions()

    def populate_versions(self):
        filters = load_settings().get("filters", {})
        installed_versions = get_installed_versions()
        available_versions, _ = get_available_versions(filters)

        all_versions = set(installed_versions)
        for _, version_id in available_versions:
            all_versions.add(version_id)

        from packaging.version import Version, InvalidVersion
        def version_key(v_str):
            try: return Version(v_str)
            except InvalidVersion: return Version("0.0.0")

        sorted_versions = sorted(list(all_versions), key=version_key, reverse=True)

        self.version_combo.addItems(sorted_versions)

    def get_instance_data(self):
        return {
            "name": self.name_input.text().strip(),
            "version": self.version_combo.currentText()
        }

class EditInstanceDialog(QDialog):
    def __init__(self, instance_data, parent=None, tr=None):
        super().__init__(parent)
        self.tr = tr
        self.setWindowTitle(tr.get("edit_instance_title", "Edit Instance"))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr.get("instance_name_label", "Instance Name:")))
        self.name_input = QLineEdit(instance_data.get('name', ''))
        layout.addWidget(self.name_input)
        layout.addWidget(QLabel(tr.get("minecraft_version_label", "Minecraft Version:")))
        self.version_combo = QComboBox()
        layout.addWidget(self.version_combo)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.populate_versions()
        self.version_combo.setCurrentText(instance_data.get('version', ''))

    def populate_versions(self):
        filters = load_settings().get("filters", {})
        installed_versions = get_installed_versions()
        available_versions, _ = get_available_versions(filters)

        all_versions = set(installed_versions)
        for _, version_id in available_versions:
            all_versions.add(version_id)

        sorted_versions = sorted(list(all_versions), key=minecraft_version_key, reverse=True)
        self.version_combo.addItems(sorted_versions)

    def get_instance_data(self):
        return {
            "name": self.name_input.text().strip(),
            "version": self.version_combo.currentText()
        }

class InstanceItem(QFrame):
    clicked = Signal(QListWidgetItem)
    edit_requested = Signal()
    delete_requested = Signal()

    def __init__(self, instance_data, list_widget_item, parent=None):
        super().__init__(parent)
        self.instance_data = instance_data
        self.list_widget_item = list_widget_item
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setMouseTracking(True)
        self.setObjectName("instanceItem")
        self.setMinimumHeight(70)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 10)
        main_layout.setSpacing(15)

        icon_frame = QFrame()
        icon_frame.setObjectName("iconFrame")
        icon_frame.setFixedSize(50, 50)
        icon_layout = QVBoxLayout(icon_frame)
        icon_label = QLabel()
        icon_label.setPixmap(QPixmap(resource_path("assets/stack.png")).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(icon_label)
        main_layout.addWidget(icon_frame)

        text_layout = QVBoxLayout()
        name_label = QLabel(instance_data['name'])
        name_label.setFont(QFont("Segoe UI Variable", 14, QFont.Bold))
        version_label = QLabel(f"Version: {instance_data['version']}")
        version_label.setStyleSheet("color: #A0A0A0;")
        text_layout.addWidget(name_label)
        text_layout.addWidget(version_label)
        main_layout.addLayout(text_layout)
        main_layout.addStretch()

        self.action_buttons_widget = QWidget()
        action_buttons_layout = QHBoxLayout(self.action_buttons_widget)
        action_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.action_buttons_widget.setStyleSheet("background-color: transparent;")
        action_buttons_layout.setSpacing(5)

        self.edit_button = QPushButton("✎")
        font = self.edit_button.font()
        font.setPointSize(12)
        self.edit_button.setFont(font)
        self.edit_button.setFixedSize(40, 40)
        self.edit_button.setObjectName("folderButton")
        self.edit_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.edit_button.setToolTip("Sửa instance")
        self.edit_button.clicked.connect(self.on_edit_clicked)
        action_buttons_layout.addWidget(self.edit_button)

        self.delete_button = QPushButton("🗑️")
        self.delete_button.setFont(font)
        self.delete_button.setFixedSize(40, 40)
        self.delete_button.setObjectName("folderButton")
        self.delete_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.delete_button.setToolTip("Xóa instance")
        self.delete_button.clicked.connect(self.on_delete_clicked)
        action_buttons_layout.addWidget(self.delete_button)
        self.open_folder_button = QPushButton("📁")
        self.open_folder_button.setFont(font)
        self.open_folder_button.setFixedSize(40, 40)
        self.open_folder_button.setObjectName("folderButton")
        self.open_folder_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.open_folder_button.setToolTip("Mở thư mục instance")
        self.open_folder_button.clicked.connect(self.open_instance_folder)
        action_buttons_layout.addWidget(self.open_folder_button)

        self.action_buttons_widget.hide()
        main_layout.addWidget(self.action_buttons_widget)

    def open_instance_folder(self):
        path = self.instance_data.get("path")
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy thư mục của instance.")
            return

        try:
            if sys.platform.startswith('win32'):
                os.startfile(path)
            elif sys.platform.startswith('darwin'):
                subprocess.Popen(['open', path])
            elif sys.platform.startswith('linux'):
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể mở thư mục:\n{e}")

    def on_edit_clicked(self):
        self.list_widget_item.listWidget().setCurrentItem(self.list_widget_item)
        self.edit_requested.emit()

    def on_delete_clicked(self):
        self.list_widget_item.listWidget().setCurrentItem(self.list_widget_item)
        self.delete_requested.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self.action_buttons_widget.underMouse():
                self.clicked.emit(self.list_widget_item)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.action_buttons_widget.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.action_buttons_widget.hide()
        super().leaveEvent(event)

class InstancePage(QWidget):
    def __init__(self, launcher):
        super().__init__(launcher)
        self.launcher = launcher
        self.tr = launcher.tr
        self.setObjectName("instancePage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_layout = QHBoxLayout()
        title_label = QLabel(self.tr.get("instances_button", "Instances"))
        title_label.setFont(QFont("Segoe UI Variable", 24, QFont.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        self.reload_button = QPushButton("↻")
        reload_font = QFont("Segoe UI Symbol", 16)
        reload_font.setWeight(QFont.Bold)
        self.reload_button.setFont(reload_font)
        self.reload_button.setFixedSize(40, 40)
        self.reload_button.setObjectName("transparentButton")
        self.reload_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.reload_button.setToolTip(self.tr.get("reload_instances_tooltip", "Reload instance list"))
        self.reload_button.clicked.connect(self.load_instance_list)
        title_layout.addWidget(self.reload_button)

        layout.addLayout(title_layout)

        self.instance_list = QListWidget()
        self.instance_list.setObjectName("transparentListWidget")
        self.instance_list.setSpacing(5)
        self.instance_list.currentItemChanged.connect(self.on_selection_changed)

        layout.addWidget(self.instance_list)
        button_layout = QHBoxLayout()
        self.add_button = QPushButton(self.tr.get("add_instance_button", "Add Instance"))
        self.edit_button = QPushButton(self.tr.get("edit_instance_button", "Edit"))
        self.delete_button = QPushButton(self.tr.get("delete_instance_button", "Delete"))
        self.play_button = QPushButton(self.tr.get("play_instance_button", "Play"))
        self.play_button.setObjectName("playButton")

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()
        button_layout.addWidget(self.play_button)
        layout.addLayout(button_layout)
        self.add_button.clicked.connect(self.add_instance)
        self.edit_button.clicked.connect(self.edit_instance)
        self.delete_button.clicked.connect(self.delete_instance)
        self.play_button.clicked.connect(self.play_instance)

        self.load_instance_list()
        
        self.setStyleSheet("""
            QListWidget#transparentListWidget {
                background-color: transparent;
                border: none;
                outline: 0;
            }
            QListWidget#transparentListWidget::item {
                background-color: transparent;
                border: none;
            }
            QListWidget#transparentListWidget::item:selected, QListWidget#transparentListWidget::item:hover {
                background-color: transparent;
                border: none;
            }
            QFrame#instanceItem {
                background-color: #141826;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 18px;
            }
            QFrame#instanceItem:hover {
                background-color: #1B2133;
            }
            QFrame#instanceItemSelected {
                background-color: #1B2133;
                border: 1px solid #7C4DFF;
                border-radius: 18px;
            }
            QFrame#iconFrame {
                background: rgba(124,77,255,.18);
                border: 1px solid rgba(255,255,255,.08);
                border-radius: 12px;
            }
        """)

    def load_instance_list(self):
        self.instance_list.clear()
        instances = load_instances()
        for instance in instances:
            item = QListWidgetItem(self.instance_list)
            item.setData(Qt.UserRole, instance)
            item.setSizeHint(QSize(100, 80))
            instance_widget = InstanceItem(instance, item)
            instance_widget.clicked.connect(self.instance_list.setCurrentItem)
            instance_widget.edit_requested.connect(self.edit_instance)
            instance_widget.delete_requested.connect(self.delete_instance)
            self.instance_list.setItemWidget(item, instance_widget)

    def on_selection_changed(self, current, previous):
        if previous:
            widget = self.instance_list.itemWidget(previous)
            if widget:
                widget.setObjectName("instanceItem")
                widget.style().unpolish(widget); widget.style().polish(widget)
        if current:
            widget = self.instance_list.itemWidget(current)
            if widget:
                widget.setObjectName("instanceItemSelected")
                widget.style().unpolish(widget); widget.style().polish(widget)

    def add_instance(self):
        dialog = AddInstanceDialog(self, self.tr)
        if dialog.exec() == QDialog.Accepted:
            instance_data = dialog.get_instance_data()
            if not instance_data["name"]:
                QMessageBox.warning(self, self.tr.get("error_title", "Error"), self.tr.get("instance_name_empty_error", "Instance name cannot be empty."))
                return

            instances = load_instances()
            if any(i['name'] == instance_data['name'] for i in instances):
                QMessageBox.warning(self, self.tr.get("error_title", "Error"), self.tr.get("instance_name_exists_error", "An instance with this name already exists."))
                return

            mc_dir = get_minecraft_directory()
            instance_path = mc_dir / "instances" / instance_data["name"]
            try:
                instance_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self, self.tr.get("error_title", "Error"), f"Could not create instance directory:\n{e}")
                return

            instance_data["path"] = str(instance_path)
            instances.append(instance_data)
            save_instances(instances)
            self.load_instance_list()
            self.launcher.load_versions()

    def edit_instance(self):
        current_item = self.instance_list.currentItem()
        if not current_item:
            return

        instance_data = current_item.data(Qt.UserRole)
        dialog = EditInstanceDialog(instance_data, self, self.tr)

        if dialog.exec() == QDialog.Accepted:
            new_data = dialog.get_instance_data()
            old_name = instance_data['name']
            new_name = new_data['name']

            if not new_name:
                QMessageBox.warning(self, self.tr.get("error_title", "Error"), self.tr.get("instance_name_empty_error", "Instance name cannot be empty."))
                return

            instances = load_instances()

            if new_name != old_name:
                if any(i['name'] == new_name for i in instances):
                    QMessageBox.warning(self, self.tr.get("error_title", "Error"), self.tr.get("instance_name_exists_error", "An instance with this name already exists."))
                    return

            for i in instances:
                if i['name'] == old_name:
                    i.update(new_data)
                    break

            save_instances(instances)
            self.load_instance_list()
            self.launcher.load_versions()

    def delete_instance(self):
        current_item = self.instance_list.currentItem()
        if not current_item:
            return

        instance_data = current_item.data(Qt.UserRole)
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(self.tr.get("delete_instance_title", "Delete Instance"))
        msg_box.setText(self.tr.get("delete_instance_confirm", "Are you sure you want to delete the instance '{name}'?").format(name=instance_data['name']))
        msg_box.setInformativeText(self.tr.get("delete_instance_folder_warning", "This will remove the instance from the list. You can also choose to delete the instance's folder and all its contents."))
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        delete_folder_checkbox = QCheckBox(self.tr.get("delete_instance_folder_checkbox", "Delete the instance folder (irreversible)"))
        msg_box.setCheckBox(delete_folder_checkbox)
        reply = msg_box.exec()

        if reply == QMessageBox.Yes:
            instances = load_instances()
            instances = [i for i in instances if i['name'] != instance_data['name']]
            save_instances(instances)

            if delete_folder_checkbox.isChecked():
                try:
                    shutil.rmtree(instance_data['path'])
                except OSError as e:
                    QMessageBox.critical(self, self.tr.get("error_title", "Error"), f"Could not delete instance directory:\n{e}")

            self.load_instance_list()
            self.launcher.load_versions()

    def play_instance(self):
        current_item = self.instance_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, self.tr.get("no_selection_title", "No Selection"), self.tr.get("select_instance_to_play_prompt", "Please select an instance to play."))
            return

        instance_data = current_item.data(Qt.UserRole)
        instance_name = instance_data.get("name")
        if instance_name:
            self.launcher.launch_from_instance_page(instance_name)