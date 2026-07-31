import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QScrollArea,
    QProgressBar, QFrame, QSpacerItem, QSizePolicy, QCheckBox, QStackedLayout, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QSize, QRect, QPoint, QTimer
from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter, QPainterPath, QCursor, QBrush, QColor
from PySide6.QtCore import Property, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup

from MZLauncher_app.core.utils import resource_path
from MZLauncher_app.settings.settings import get_minecraft_directory

class HeaderFrame(QFrame):
    def __init__(self, parent=None, bg_path="assets/bg1.png", overlay_color=QColor(0, 0, 0, 80)):
        super().__init__(parent)
        self.bg = QPixmap(resource_path(bg_path))
        self.setObjectName("headerFrame")
        self._zoom_factor = 1.0
        self._overlay_opacity = 0.0
        self.overlay_color = overlay_color

        self.zoom_animation = QPropertyAnimation(self, b"zoom_factor", self)
        self.zoom_animation.setDuration(250)
        self.zoom_animation.setEasingCurve(QEasingCurve.InOutQuad)

        self.overlay_animation = QPropertyAnimation(self, b"overlay_opacity", self)
        self.overlay_animation.setDuration(250)
        self.overlay_animation.setEasingCurve(QEasingCurve.InOutQuad)

    def enterEvent(self, event):
        self.zoom_animation.setEndValue(1.05)
        self.zoom_animation.start()
        self.overlay_animation.setEndValue(1.0)
        self.overlay_animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.zoom_animation.setEndValue(1.0)
        self.zoom_animation.start()
        self.overlay_animation.setEndValue(0.0)
        self.overlay_animation.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(self.rect(), 18, 18)
        painter.setClipPath(path)

        target_size = self.size() * self._zoom_factor
        pixmap_scaled = self.bg.scaled(target_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

        draw_x = (self.width() - pixmap_scaled.width()) / 2
        draw_y = (self.height() - pixmap_scaled.height()) / 2
        
        painter.drawPixmap(draw_x, draw_y, pixmap_scaled)

        if self._overlay_opacity > 0:
            overlay_color = self.overlay_color
            overlay_color.setAlphaF(self._overlay_opacity * (self.overlay_color.alphaF()))
            painter.fillRect(self.rect(), overlay_color)

    @Property(float)
    def zoom_factor(self):
        return self._zoom_factor

    @zoom_factor.setter
    def zoom_factor(self, value):
        self._zoom_factor = value
        self.update()

    @Property(float)
    def overlay_opacity(self):
        return self._overlay_opacity

    @overlay_opacity.setter
    def overlay_opacity(self, value):
        self._overlay_opacity = value
        self.update()

class HomePage(QWidget):
    def __init__(self, launcher):
        super().__init__(launcher)
        self.launcher = launcher
        self.tr = launcher.tr
        self.setObjectName("homePage")
 
        self._animation_played = False
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        self.version_combo = QComboBox()
        self.version_combo.setObjectName("transparentComboBox")
        self.version_combo.setFixedSize(240, 48)
        main_content_widget = QWidget()
        main_content_layout = QVBoxLayout(main_content_widget)
        main_content_layout.setContentsMargins(20, 20, 20, 20)
        main_content_layout.setSpacing(0)
        header_frame = HeaderFrame()
        header_frame.setMinimumHeight(280)

        header_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        header_frame.setStyleSheet("""
            QFrame#headerFrame {
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 18px;
            }
        """)

        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 20, 20, 20)

        top_header_layout = QHBoxLayout()
        
        top_header_layout.addStretch()
        self.username_combo = QComboBox()
        self.username_combo.setObjectName("transparentComboBox")
        self.username_combo.setFixedSize(200, 36)
        top_header_layout.addWidget(self.username_combo)
        header_layout.addLayout(top_header_layout)

        header_layout.addStretch(1)

        title_label = QLabel("Minecraft")
        title_label.setFont(QFont("Segoe UI Variable", 68, QFont.Bold))
        header_layout.addWidget(title_label)


        header_layout.addStretch(2)
        bottom_header_layout = QHBoxLayout()
        self.play_button = QPushButton(self.tr.get("play", "Play"))
        self.play_button.setObjectName("playButton")
        self.play_button.setMinimumSize(200, 48)
        bottom_header_layout.addWidget(self.play_button)
        version_group_layout = QVBoxLayout()
        version_group_layout.setSpacing(4)

        version_selector_layout = QHBoxLayout()
        version_selector_layout.setSpacing(5)
        version_selector_layout.setContentsMargins(0,0,0,0)
        version_selector_layout.addWidget(self.version_combo)

        self.reload_versions_button = QPushButton("↻")
        reload_font = QFont("Segoe UI Symbol", 14)
        reload_font.setWeight(QFont.Bold)
        self.reload_versions_button.setFont(reload_font)
        self.reload_versions_button.setStyleSheet("QPushButton#transparentButton { padding: 0px; }")
        self.reload_versions_button.setFixedSize(48, 48)
        self.reload_versions_button.setObjectName("transparentButton")
        self.reload_versions_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.reload_versions_button.setToolTip(self.tr.get("reload_versions_tooltip", "Reload version list"))
        version_selector_layout.addWidget(self.reload_versions_button)

        version_group_layout.addLayout(version_selector_layout)
        self.instant_launch_checkbox = QCheckBox(self.tr.get("instant_launch_main_menu", "Instant Launch"))
        self.instant_launch_checkbox.setObjectName("transparentCheckbox")
        version_group_layout.addWidget(self.instant_launch_checkbox, 0, Qt.AlignLeft)
        bottom_header_layout.addLayout(version_group_layout)
        bottom_header_layout.addStretch()
        header_layout.addLayout(bottom_header_layout)

        main_content_layout.addWidget(header_frame)

        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0) 

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        secondary_features_main_layout = QVBoxLayout()
        secondary_features_main_layout.setSpacing(15)
        secondary_features_main_layout.setContentsMargins(0, 20, 0, 0)
        top_row_layout = QHBoxLayout()
        top_row_layout.setSpacing(15)
        bottom_row_layout = QHBoxLayout()
        bottom_row_layout.setSpacing(15)

        self.frame1 = HeaderFrame(bg_path="assets/bg2.png")
        frame1_layout = QVBoxLayout(self.frame1)
        frame1_layout.setContentsMargins(15, 15, 15, 15)
        frame1_layout.setSpacing(5)

        frame1_title_layout = QHBoxLayout()
        frame1_title_layout.setSpacing(10)

        icon_frame = QFrame()
        icon_frame.setObjectName("iconFrame")
        icon_frame.setFixedSize(36, 36)
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0,0,0,0)
        icon_label = QLabel()
        icon_pixmap = QPixmap(resource_path("assets/modloader.png"))
        icon_label.setPixmap(icon_pixmap.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(icon_label)

        frame1_title_layout.addWidget(icon_frame)

        self.mods_title_label = QLabel() 
        self.mods_title_label.setFont(QFont("Segoe UI Variable", 16, QFont.Bold))
        frame1_title_layout.addWidget(self.mods_title_label)
        mods_count_frame = QFrame()
        mods_count_frame.setObjectName("countFrame")
        mods_count_frame.setFixedSize(30, 20)
        mods_count_layout = QVBoxLayout(mods_count_frame)
        mods_count_layout.setContentsMargins(0,0,0,0)
        self.mods_count_label = QLabel("0")
        self.mods_count_label.setAlignment(Qt.AlignCenter)
        self.mods_count_label.setFont(QFont("Segoe UI Variable", 8, QFont.Bold))
        self.mods_count_label.setStyleSheet("background: transparent; border: none;")
        mods_count_layout.addWidget(self.mods_count_label)

        frame1_title_layout.addWidget(mods_count_frame)

        frame1_title_layout.addStretch()
        
        self.mods_subtitle_label = QLabel(self.tr.get("mods_manager_subtitle", "Manager your mods and enhance your Minecraft experience."))
        self.mods_subtitle_label.setWordWrap(True)
        self.mods_subtitle_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.mods_subtitle_label.setStyleSheet("color: #A0A0A0;")

        frame1_bottom_layout = QHBoxLayout()
        self.open_mods_folder_button = QPushButton(self.tr.get("open_mods_folder_button", "Open Mods Folder"))
        self.open_mods_folder_button.setObjectName("transparentButton")
        self.open_mods_folder_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.open_mods_folder_button.clicked.connect(self.launcher.open_mods_folder)
        
        frame1_bottom_layout.addStretch()
        frame1_bottom_layout.addWidget(self.open_mods_folder_button)

        frame1_layout.addLayout(frame1_title_layout)
        frame1_layout.addWidget(self.mods_subtitle_label)
        frame1_layout.addStretch()
        frame1_layout.addLayout(frame1_bottom_layout)
        
        self.frame1.setMinimumHeight(120)
        self.frame1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.update_mods_count()
        self.frame2 = HeaderFrame(bg_path="assets/bg3.png")
        frame2_layout = QVBoxLayout(self.frame2)
        frame2_layout.setContentsMargins(15, 15, 15, 15)
        frame2_layout.setSpacing(5)
        frame2_title_layout = self.create_secondary_frame_title(
            icon_path="assets/globe.png",
            title=self.tr.get("worlds_manager_title", "Worlds Manager"),
            count_label_attr="worlds_count_label",
            icon_frame_object_name="worldsIconFrame",
            count_frame_object_name="worldsCountFrame"
        )
        worlds_subtitle_label = QLabel(self.tr.get("worlds_manager_subtitle", "Manage your saved worlds and backups."))
        worlds_subtitle_label.setWordWrap(True)
        worlds_subtitle_label.setStyleSheet("color: #A0A0A0;")
        self.open_worlds_folder_button = QPushButton(self.tr.get("open_worlds_folder_button", "Open Worlds Folder"))
        self.open_worlds_folder_button.setObjectName("transparentButton")
        self.open_worlds_folder_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.open_worlds_folder_button.clicked.connect(self.launcher.open_worlds_folder)
        frame2_bottom_layout = QHBoxLayout()
        frame2_bottom_layout.addStretch()
        frame2_bottom_layout.addWidget(self.open_worlds_folder_button)
        frame2_layout.addLayout(frame2_title_layout)
        frame2_layout.addWidget(worlds_subtitle_label)
        frame2_layout.addStretch()
        frame2_layout.addLayout(frame2_bottom_layout)
        self.frame2.setMinimumHeight(120)
        self.frame2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.update_worlds_count()
        self.frame3 = HeaderFrame(bg_path="assets/bg4.png")
        frame3_layout = QVBoxLayout(self.frame3)
        frame3_layout.setContentsMargins(15, 15, 15, 15)
        frame3_layout.setSpacing(5)
        frame3_title_layout = self.create_secondary_frame_title(
            icon_path="assets/file.png",
            title=self.tr.get("resource_packs_title", "Resource Packs"),
            count_label_attr="packs_count_label",
            icon_frame_object_name="packsIconFrame",
            count_frame_object_name="packsCountFrame"
        )
        packs_subtitle_label = QLabel(self.tr.get("resource_packs_subtitle", "Customize the look and feel of your game."))
        packs_subtitle_label.setWordWrap(True)
        packs_subtitle_label.setStyleSheet("color: #A0A0A0;")
        self.open_packs_folder_button = QPushButton(self.tr.get("open_folder_button", "Open Folder"))
        self.open_packs_folder_button.setObjectName("transparentButton")
        self.open_packs_folder_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.open_packs_folder_button.clicked.connect(self.launcher.open_resource_packs_folder)
        frame3_bottom_layout = QHBoxLayout()
        frame3_bottom_layout.addStretch()
        frame3_bottom_layout.addWidget(self.open_packs_folder_button)
        frame3_layout.addLayout(frame3_title_layout)
        frame3_layout.addWidget(packs_subtitle_label)
        frame3_layout.addStretch()
        frame3_layout.addLayout(frame3_bottom_layout)
        self.frame3.setMinimumHeight(120)
        self.frame3.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.update_resource_packs_count()
        self.frame4 = HeaderFrame(bg_path="assets/bg5.png")
        frame4_layout = QVBoxLayout(self.frame4)
        frame4_layout.setContentsMargins(15, 15, 15, 15)
        frame4_layout.setSpacing(5)
        frame4_title_layout = self.create_secondary_frame_title(
            icon_path="assets/camera.png",
            title=self.tr.get("screenshots_title", "Screenshots"),
            count_label_attr="screenshots_count_label",
            icon_frame_object_name="screenshotsIconFrame",
            count_frame_object_name="screenshotsCountFrame"
        )
        screenshots_subtitle_label = QLabel(self.tr.get("screenshots_subtitle", "View your captured in-game moments."))
        screenshots_subtitle_label.setWordWrap(True)
        screenshots_subtitle_label.setStyleSheet("color: #A0A0A0;")
        self.open_screenshots_folder_button = QPushButton(self.tr.get("open_folder_button", "Open Folder"))
        self.open_screenshots_folder_button.setObjectName("transparentButton")
        self.open_screenshots_folder_button.setCursor(QCursor(Qt.PointingHandCursor))
        frame4_bottom_layout = QHBoxLayout()
        frame4_bottom_layout.addStretch()
        frame4_bottom_layout.addWidget(self.open_screenshots_folder_button)
        frame4_layout.addLayout(frame4_title_layout)
        frame4_layout.addWidget(screenshots_subtitle_label)
        frame4_layout.addStretch()
        frame4_layout.addLayout(frame4_bottom_layout)
        self.frame4.setMinimumSize(250, 120)
        self.frame4.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.frame5 = HeaderFrame(bg_path="assets/bg7.png")
        frame5_layout = QVBoxLayout(self.frame5)
        frame5_layout.setContentsMargins(15, 15, 15, 15)
        frame5_layout.setSpacing(5)
        frame5_title_layout = self.create_secondary_frame_title(
            icon_path="assets/folder.png",
            title=self.tr.get("minecraft_folder_title", "Minecraft Folder"),
            count_label_attr=None,
            icon_frame_object_name="mcFolderIconFrame"
        )
        mc_folder_subtitle_label = QLabel(self.tr.get("minecraft_folder_subtitle", "Access the root game directory."))
        mc_folder_subtitle_label.setWordWrap(True)
        mc_folder_subtitle_label.setStyleSheet("color: #A0A0A0;")
        self.open_mc_folder_button = QPushButton(self.tr.get("open_folder_button", "Open Folder"))
        self.open_mc_folder_button.setObjectName("transparentButton")
        self.open_mc_folder_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.open_mc_folder_button.clicked.connect(self.launcher.open_minecraft_folder)
        frame5_bottom_layout = QHBoxLayout()
        frame5_bottom_layout.addStretch()
        frame5_bottom_layout.addWidget(self.open_mc_folder_button)
        frame5_layout.addLayout(frame5_title_layout)
        frame5_layout.addWidget(mc_folder_subtitle_label)
        frame5_layout.addStretch()
        frame5_layout.addLayout(frame5_bottom_layout)
        self.frame5.setMinimumSize(250, 120)
        self.frame5.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.frame6 = HeaderFrame(bg_path="assets/bg6.png")
        frame6_layout = QVBoxLayout(self.frame6)
        frame6_layout.setContentsMargins(15, 15, 15, 15)
        frame6_layout.setSpacing(5)
        frame6_title_layout = self.create_secondary_frame_title(
            icon_path="assets/sun.png",
            title=self.tr.get("shader_packs_title", "Shader Packs"),
            count_label_attr="shader_packs_count_label",
            icon_frame_object_name="shaderIconFrame",
            count_frame_object_name="shaderCountFrame"
        )
        shader_subtitle_label = QLabel(self.tr.get("shader_packs_subtitle", "Install and manage your shader packs."))
        shader_subtitle_label.setWordWrap(True)
        shader_subtitle_label.setStyleSheet("color: #A0A0A0;")
        self.open_shader_packs_folder_button = QPushButton(self.tr.get("open_folder_button", "Open Folder"))
        self.open_shader_packs_folder_button.setObjectName("transparentButton")
        self.open_shader_packs_folder_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.open_shader_packs_folder_button.clicked.connect(self.launcher.open_shaderpacks_folder)
        frame6_bottom_layout = QHBoxLayout()
        frame6_bottom_layout.addStretch()
        frame6_bottom_layout.addWidget(self.open_shader_packs_folder_button)
        frame6_layout.addLayout(frame6_title_layout)
        frame6_layout.addWidget(shader_subtitle_label)
        frame6_layout.addStretch()
        frame6_layout.addLayout(frame6_bottom_layout)
        self.frame6.setMinimumSize(250, 120)
        self.frame6.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        top_row_layout.addWidget(self.frame1)
        top_row_layout.addWidget(self.frame2)
        top_row_layout.addWidget(self.frame3)
        secondary_features_main_layout.addLayout(top_row_layout)
        secondary_features_main_layout.addLayout(bottom_row_layout)
        bottom_row_layout.addWidget(self.frame4)
        bottom_row_layout.addWidget(self.frame5)
        bottom_row_layout.addWidget(self.frame6)
        scroll_content_widget = QWidget()
        scroll_content_widget.setLayout(secondary_features_main_layout)
        scroll_area.setWidget(scroll_content_widget)
        scroll_area.setMinimumHeight(140)

        content_layout.addWidget(scroll_area)

        main_content_layout.addWidget(content_area)
        page_layout.addWidget(main_content_widget)
        self.setStyleSheet("""
            QComboBox#transparentComboBox {
                background: rgba(10, 13, 23, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
                color: #F5F6FA;
                font: 15px "Segoe UI Variable";
                padding-left: 12px;
                padding-right: 28px;
            }
            QComboBox#transparentComboBox:hover {
                background: rgba(10, 13, 23, 0.7);
            }
            QComboBox#transparentComboBox:on {
                background: rgba(10, 13, 23, 0.8);
            }
            QComboBox#transparentComboBox::drop-down {
                border: none;
                width: 24px;
                background: transparent;
            }
            QComboBox#transparentComboBox::down-arrow {
                image: url(assets/down.png);
            }
            QComboBox#transparentComboBox QAbstractItemView {
                background: #141826;
                border: 1px solid rgba(255,255,255,.1);
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

            QFrame#iconFrame {
                background-color: rgba(124, 77, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
            QFrame#worldsIconFrame {
                background-color: rgba(76, 175, 80, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
            QFrame#packsIconFrame {
                background-color: rgba(33, 150, 243, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
            QFrame#screenshotsIconFrame {
                background-color: rgba(255, 152, 0, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
            QFrame#mcFolderIconFrame {
                background-color: rgba(158, 158, 158, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
            QFrame#shaderIconFrame {
                background-color: rgba(255, 193, 7, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
            QFrame#screenshotsCountFrame {
                background-color: rgba(255, 152, 0, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
            QFrame#packsCountFrame {
                background-color: rgba(33, 150, 243, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 0px;
            }
            QFrame#worldsCountFrame {
                background-color: rgba(76, 175, 80, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 0px;
            }
            QFrame#countFrame {
                background-color: rgba(124, 77, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 0px;
            }
            QFrame#shaderCountFrame {
                background-color: rgba(255, 193, 7, 0.2); /* Translucent yellow */
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 0px;
            }
            
            QPushButton#transparentButton {
                background: rgba(10, 13, 23, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
                color: #F5F6FA;
                font: 15px "Segoe UI Variable";
                padding: 8px 12px;
            }
            QPushButton#transparentButton:hover {
                background: rgba(10, 13, 23, 0.7);
            }
            QPushButton#transparentButton:pressed {
                background: rgba(10, 13, 23, 0.8);
            }
        """)
        self.username_combo.currentTextChanged.connect(self.launcher.on_username_changed)
        self.version_combo.currentIndexChanged.connect(self.launcher.on_version_changed)
        self.play_button.clicked.connect(self.launcher.on_play_clicked)
        self.reload_versions_button.clicked.connect(self.launcher.load_versions)

        self.secondary_frames = [self.frame1, self.frame2, self.frame3, self.frame4, self.frame5, self.frame6]
        self.prepare_entrance_animation()

    def create_secondary_frame_title(self, icon_path, title, count_label_attr, icon_frame_object_name="iconFrame", count_frame_object_name="countFrame"):
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)

        icon_frame = QFrame()
        icon_frame.setObjectName(icon_frame_object_name)
        icon_frame.setFixedSize(36, 36)
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0,0,0,0)
        icon_label = QLabel()
        icon_pixmap = QPixmap(resource_path(icon_path))
        icon_label.setPixmap(icon_pixmap.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(icon_label)
        title_layout.addWidget(icon_frame)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI Variable", 16, QFont.Bold))
        title_layout.addWidget(title_label)

        count_frame = QFrame()
        count_frame.setObjectName(count_frame_object_name)
        count_frame.setFixedSize(30, 20)
        count_layout = QVBoxLayout(count_frame)
        count_layout.setContentsMargins(0,0,0,0)
        count_label = QLabel("0")
        count_label.setAlignment(Qt.AlignCenter)
        count_label.setFont(QFont("Segoe UI Variable", 8, QFont.Bold))
        count_label.setStyleSheet("background: transparent; border: none;")
        count_layout.addWidget(count_label)
        if count_label_attr:
            setattr(self, count_label_attr, count_label)
            title_layout.addWidget(count_frame)
        title_layout.addStretch()
        return title_layout

    def update_mods_count(self):
        mc_dir = get_minecraft_directory()
        mods_dir = mc_dir / "mods"
        count = 0
        if mods_dir.exists() and mods_dir.is_dir():
            count = len([f for f in os.listdir(mods_dir) if f.endswith('.jar')])
        
        self.mods_title_label.setText(self.tr.get("mods_manager_title", "Mods Manager"))
        self.mods_count_label.setText(str(count))

    def update_worlds_count(self):
        mc_dir = get_minecraft_directory()
        saves_dir = mc_dir / "saves"
        count = 0
        if saves_dir.exists() and saves_dir.is_dir():
            count = len([d for d in os.listdir(saves_dir) if os.path.isdir(os.path.join(saves_dir, d))])
        self.worlds_count_label.setText(str(count))

    def update_resource_packs_count(self):
        mc_dir = get_minecraft_directory()
        packs_dir = mc_dir / "resourcepacks"
        count = 0
        if packs_dir.exists() and packs_dir.is_dir():
            count = len([f for f in os.listdir(packs_dir) if f.endswith('.zip') or os.path.isdir(os.path.join(packs_dir, f))])
        self.packs_count_label.setText(str(count))

    def update_shader_packs_count(self):
        mc_dir = get_minecraft_directory()
        packs_dir = mc_dir / "shaderpacks"
        count = 0
        if packs_dir.exists() and packs_dir.is_dir():
            count = len([f for f in os.listdir(packs_dir) if f.endswith('.zip') or os.path.isdir(os.path.join(packs_dir, f))])
        self.shader_packs_count_label.setText(str(count))

    def prepare_entrance_animation(self):
        for i, frame in enumerate(self.secondary_frames):
            effect = QGraphicsOpacityEffect(frame)
            effect.setOpacity(0.0)
            frame.setGraphicsEffect(effect)

    def start_entrance_animation(self):
        if self._animation_played:
            return
        self._animation_played = True
    
        for i, frame in enumerate(self.secondary_frames):
            effect = frame.graphicsEffect()
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(frame)
                frame.setGraphicsEffect(effect)
            
            effect.setOpacity(0.0)
    
            fade_in_anim = QPropertyAnimation(effect, b"opacity", frame)
            fade_in_anim.setStartValue(0.0)
            fade_in_anim.setEndValue(1.0)
            fade_in_anim.setDuration(400)
            fade_in_anim.setEasingCurve(QEasingCurve.OutQuad)
    
            def create_auto_hover(target_frame):
                target_frame.zoom_animation.setEndValue(1.05)
                target_frame.zoom_animation.start()
                target_frame.overlay_animation.setEndValue(1.0)
                target_frame.overlay_animation.start()
    
            def create_auto_unhover(target_frame):
                target_frame.zoom_animation.setEndValue(1.0)
                target_frame.zoom_animation.start()
                target_frame.overlay_animation.setEndValue(0.0)
                target_frame.overlay_animation.start()
    
            start_delay = 300 + 200 * i
            QTimer.singleShot(start_delay, lambda f=fade_in_anim: f.start(QPropertyAnimation.DeleteWhenStopped))
            QTimer.singleShot(start_delay + 400, lambda f=frame: create_auto_hover(f))
            QTimer.singleShot(start_delay + 400 + 450, lambda f=frame: create_auto_unhover(f))
