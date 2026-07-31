from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFrame, QPushButton, QStackedWidget, QLabel, QButtonGroup, QGraphicsOpacityEffect
from PySide6.QtCore import QSize, Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QPoint, QTimer, QRect, Property
from PySide6.QtGui import QIcon, QFont, QCursor, QPainter
from MZLauncher_app.gui.pages.instance_page import InstancePage
from MZLauncher_app.gui.pages.setting_page import SettingsPage

from MZLauncher_app.core.utils import resource_path

class MainWindow(QWidget):
    def __init__(self, launcher):
        super().__init__(launcher)
        self.launcher = launcher
        self.tr = launcher.tr

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar_buttons = {}
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        self.sidebar = self.create_sidebar()
        main_layout.addWidget(self.sidebar)

        self.content = QStackedWidget()
        main_layout.addWidget(self.content)

        # Version Label for Header
        self.header_version_label = QLabel("...")
        self.header_version_label.setFont(QFont("Segoe UI", 10))
        self.header_version_label.setStyleSheet("color: #E0E0E0; background: transparent;")
        self.header_version_label.setAlignment(Qt.AlignCenter)

        self.selection_animation = QPropertyAnimation(self.selection_indicator, b"geometry")
        self.selection_animation.setDuration(250)
        self.selection_animation.setEasingCurve(QEasingCurve.InOutCubic)

        QTimer.singleShot(0, self.update_selection_indicator_position)

    def create_sidebar(self):
        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(10, 8, 10, 8)
        sidebar_layout.setSpacing(18)

        self.selection_indicator = QFrame(sidebar_frame)
        self.selection_indicator.setObjectName("selectionIndicator")
        self.selection_indicator.setFixedSize(44, 44)

        sidebar_layout.addStretch()

        home_button = QPushButton()
        home_button.setIcon(QIcon(resource_path("assets/home.png")))
        home_button.setCheckable(True)
        home_button.setChecked(True)
        home_button.setIconSize(QSize(24, 24))
        home_button.setFixedSize(44, 44)
        home_button.setCursor(QCursor(Qt.PointingHandCursor))
        home_button.setToolTip(self.tr.get("home_button", "Home"))
        sidebar_layout.addWidget(home_button)
        self.sidebar_buttons['home'] = home_button

        mod_loader_button = QPushButton()
        mod_loader_button.setIcon(QIcon(resource_path("assets/modloader.png")))
        mod_loader_button.setCheckable(True)
        mod_loader_button.setIconSize(QSize(24, 24))
        mod_loader_button.setFixedSize(44, 44)
        mod_loader_button.setCursor(QCursor(Qt.PointingHandCursor))
        mod_loader_button.setToolTip(self.tr.get("install_mod_loader_button", "Install Mod Loader"))
        sidebar_layout.addWidget(mod_loader_button)
        self.sidebar_buttons['mod_loader'] = mod_loader_button

        instance_button = QPushButton()
        instance_button.setIcon(QIcon(resource_path("assets/stack.png")))
        instance_button.setCheckable(True)
        instance_button.setIconSize(QSize(24, 24))
        instance_button.setFixedSize(44, 44)
        instance_button.setCursor(QCursor(Qt.PointingHandCursor))
        instance_button.setToolTip(self.tr.get("instances_button", "Instances"))
        sidebar_layout.addWidget(instance_button)
        self.sidebar_buttons['instance'] = instance_button

        settings_button = QPushButton()
        settings_button.setIcon(QIcon(resource_path("assets/settings.png")))
        settings_button.setCheckable(True)
        settings_button.setIconSize(QSize(24, 24))
        settings_button.setFixedSize(44, 44)
        settings_button.setCursor(QCursor(Qt.PointingHandCursor))
        settings_button.setToolTip(self.tr.get("settings", "Settings"))
        sidebar_layout.addWidget(settings_button)
        self.sidebar_buttons['settings'] = settings_button

        sidebar_layout.addStretch()

        font = QFont("Segoe UI Variable")
        font.setPixelSize(8)
        font.setWeight(QFont.Weight.Normal)



        sidebar_frame.setFixedWidth(64)
        sidebar_frame.setStyleSheet("""
            QFrame#sidebar {
                background-color: #0A0D17;
                border-right: 1px solid rgba(255,255,255,.08);
                border-bottom-left-radius: 0px;
            }
            QFrame#sidebar QPushButton {
                background-color: transparent;
                border: 1px solid transparent;
                padding: 0px;
                border-radius: 12px;
            }
            QFrame#sidebar QPushButton:hover:!checked {
                background: rgba(255, 255, 255, 0.08);
            }
            QFrame#sidebar QPushButton:checked {
                background: transparent;
            }
            QFrame#selectionIndicator {
                background: rgba(255, 255, 255, 0.08);
                border-radius: 12px;
            }
        """)

        return sidebar_frame

    def animate_selection(self, button):
        start_geo = self.selection_indicator.geometry()
        end_y = button.y()
        end_geo = QRect(start_geo.x(), end_y, start_geo.width(), start_geo.height())

        self.selection_animation.setStartValue(start_geo)
        self.selection_animation.setEndValue(end_geo)
        self.selection_animation.start()

        self.selection_indicator.raise_()
    
    def update_selection_indicator_position(self):
        checked_button = self.button_group.checkedButton()
        if checked_button:
            current_geo = self.selection_indicator.geometry()
            self.selection_indicator.setGeometry(current_geo.x(), checked_button.y(), current_geo.width(), current_geo.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_selection_indicator_position()
        if hasattr(self.launcher, 'global_progress_widget') and self.launcher.global_progress_widget:
            pg_widget = self.launcher.global_progress_widget
            pg_widget.setGeometry(self.content.x(), self.height() - pg_widget.height(), self.content.width(), pg_widget.height())

    def start_entrance_animation(self):
        def prepare_button_animation(button):
            effect = QGraphicsOpacityEffect(button)
            button.setGraphicsEffect(effect)
            button.setFixedSize(44, 44)
            
            anim = QPropertyAnimation(effect, b"opacity", button)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setDuration(300)
            anim.setEasingCurve(QEasingCurve.InOutQuad)
            
            effect.setOpacity(0.0)
            
            return anim

        home_anim = prepare_button_animation(self.sidebar_buttons['home'])
        mod_loader_anim = prepare_button_animation(self.sidebar_buttons['mod_loader'])
        instance_anim = prepare_button_animation(self.sidebar_buttons['instance'])
        settings_anim = prepare_button_animation(self.sidebar_buttons['settings'])
        
        indicator_effect = QGraphicsOpacityEffect(self.selection_indicator)
        self.selection_indicator.setGraphicsEffect(indicator_effect)
        indicator_anim = prepare_button_animation(self.selection_indicator)

        def run_animations():
            QTimer.singleShot(300, lambda: (home_anim.start(QPropertyAnimation.DeleteWhenStopped), indicator_anim.start(QPropertyAnimation.DeleteWhenStopped)))
            QTimer.singleShot(450, lambda: mod_loader_anim.start(QPropertyAnimation.DeleteWhenStopped))
            QTimer.singleShot(600, lambda: instance_anim.start(QPropertyAnimation.DeleteWhenStopped))
            QTimer.singleShot(750, lambda: settings_anim.start(QPropertyAnimation.DeleteWhenStopped))

        QTimer.singleShot(0, run_animations)

        home_button = self.sidebar_buttons.get('home')
        if home_button:
            self.selection_indicator.move(home_button.x(), home_button.y())
    def add_page(self, widget):
        return self.content.addWidget(widget)

    def set_current_page(self, index):
        current_index = self.content.currentIndex()
        if index == current_index:
            return

        current_widget = self.content.widget(current_index)
        if isinstance(current_widget, SettingsPage):
            if current_widget.save_button.isEnabled():
                if hasattr(current_widget, 'show_unsaved_changes_prompt'):
                    current_widget.show_unsaved_changes_prompt()
                button_to_uncheck = self.button_group.button(index)
                if button_to_uncheck:
                    button_to_uncheck.setChecked(False)
                button_for_current_page = self.button_group.button(current_index)
                if button_for_current_page:
                    button_for_current_page.setChecked(True)
                return

        button_to_animate = self.button_group.button(index)
        if button_to_animate:
            self.animate_selection(button_to_animate)
        self.content.setCurrentIndex(index)

        new_widget = self.content.widget(index)
        if hasattr(new_widget, 'start_entrance_animation'):
            QTimer.singleShot(0, new_widget.start_entrance_animation)
