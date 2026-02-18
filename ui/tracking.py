"""
WebHTC: Open Source XR Tracking Suite v2.0
Enhanced with hotkeys, system tray, quality graphs, and overlay mode
"""
import sys
import cv2
import numpy as np
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QSlider,
                             QStackedWidget, QFrame, QCheckBox, QComboBox,
                             QLineEdit, QScrollArea, QMessageBox, QPlainTextEdit,
                             QSystemTrayIcon, QMenu, QAction, QShortcut, QDialog,
                             QGridLayout, QDoubleSpinBox, QGroupBox)
from PySide6.QtCore import Qt, QSize, Slot, QTimer, Signal, QPoint
from PySide6.QtGui import QImage, QPixmap, QColor, QFont, QPalette, QKeySequence, QIcon

from core.config_manager import ConfigManager
from core.tracking_engine import TrackingEngine
from ui.localization import TRANSLATIONS
from core.boot_sequence import BootSplash
from ui.setup_wizard import SetupWizard

# === THEMES ===
THEMES = {
    "Matrix": {
        "bg": "#050605", "surface": "#0a120a", "border": "#1a2e1a",
        "accent": "#a8ffbc", "text": "#a8ffbc", "faded": "#1d331d"
    },
    "Void": {
        "bg": "#000000", "surface": "#090909", "border": "#1a1a1a",
        "accent": "#ffffff", "text": "#eeeeee", "faded": "#333333"
    },
    "Terminal": {
        "bg": "#080b12", "surface": "#0e141d", "border": "#1c2a3d",
        "accent": "#5294e2", "text": "#d3dae3", "faded": "#384d6b"
    }
}


class QualityGraph(QFrame):
    """Виджет графика качества трекинга"""
    def __init__(self, theme, title="Quality"):
        super().__init__()
        self.theme = theme
        self.title = title
        self.data = []
        self.max_points = 60
        self.setFixedHeight(100)
        self.setStyleSheet(f"background-color: {theme['surface']}; border: 1px solid {theme['border']};")

    def update_data(self, value):
        self.data.append(value)
        if len(self.data) > self.max_points:
            self.data.pop(0)
        self.update()

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QPen, QColor
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self.data:
            return

        # Очистка
        painter.fillRect(self.rect(), QColor(self.theme['surface']))

        # Рисуем график
        pen = QPen(QColor(self.theme['accent']), 2)
        painter.setPen(pen)

        width = self.width()
        height = self.height()
        step = width / max(len(self.data) - 1, 1)

        max_val = max(max(self.data), 1)
        min_val = min(self.data)

        points = []
        for i, val in enumerate(self.data):
            x = i * step
            y = height - ((val - min_val) / (max_val - min_val + 0.001)) * height
            points.append(QPoint(int(x), int(y)))

        if len(points) > 1:
            painter.drawPolyline(points)

        # Заголовок
        painter.setPen(QColor(self.theme['text']))
        painter.drawText(5, 15, f"{self.title}: {self.data[-1] if self.data else 0:.1f}")


class UIBlock(QFrame):
    def __init__(self, title="", theme=None):
        super().__init__()
        self.setObjectName("ThemedBlock")
        self.theme = theme
        self.setStyleSheet(f"""
            QFrame#ThemedBlock {{
                border: 1px solid {self.theme['border']};
                margin-top: 15px;
                background-color: {self.theme['bg']};
            }}
        """)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 25, 15, 15)

        self.title_lbl = QLabel(f" [{title.upper()}] ", self)
        self.title_lbl.setStyleSheet(f"background-color: {self.theme['bg']}; color: {self.theme['accent']}; font-size: 11px; font-weight: bold; border: none;")
        self.title_lbl.move(12, 0)
        self.title_lbl.adjustSize()


class WebHTCApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager()
        self.lang = self.cfg.get('visuals', 'language')
        self.theme_name = self.cfg.get('visuals', 'theme')
        self.theme = THEMES.get(self.theme_name, THEMES["Matrix"])
        self.t = TRANSLATIONS[self.lang]

        self.setWindowTitle(self.t["title"])
        self.resize(1150, 850)
        self.apply_global_styles()

        # System Tray
        self.tray_icon = None
        if self.cfg.get('system', 'minimize_to_tray', default=True):
            self.init_system_tray()

        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.root_layout = QVBoxLayout(self.central)
        self.root_layout.setContentsMargins(25, 25, 25, 25)
        self.root_layout.setSpacing(20)

        # === HEADER ===
        self.create_header()

        # === MAIN HUD ===
        main_hud = QHBoxLayout()
        main_hud.setSpacing(25)

        # LEFT COLUMN
        left_col = QVBoxLayout()

        # Video Feed
        self.feed_block = UIBlock(self.t["visual_feed"], self.theme)
        self.video_display = QLabel()
        self.video_display.setFixedSize(640, 480)
        self.video_display.setStyleSheet(f"background-color: #000; border: none;")
        self.feed_block.main_layout.addWidget(self.video_display)

        status_row = QHBoxLayout()
        self.status_lbl = QLabel(f"[{self.t['status_scanning'].upper()}]")
        self.fps_lbl = QLabel("FPS: --")
        status_row.addWidget(self.status_lbl)
        status_row.addStretch()
        status_row.addWidget(self.fps_lbl)
        self.feed_block.main_layout.addLayout(status_row)
        left_col.addWidget(self.feed_block)

        # Calibration
        self.calib_block = UIBlock(self.t["calib_title"], self.theme)
        qc_layout = QVBoxLayout()
        self.add_slider(qc_layout, self.t["sensitivity"], 0.5, 3.0, 'calibration', 'scale')
        self.add_slider(qc_layout, self.t["vert_off"], -1.0, 1.0, 'calibration', 'offset_y')
        self.add_slider(qc_layout, self.t["depth_off"], -2.0, 1.0, 'calibration', 'offset_z')
        self.calib_block.main_layout.addLayout(qc_layout)
        left_col.addWidget(self.calib_block)

        # Smart Calib Button
        self.smart_calib_btn = QPushButton(f"⚡ {self.t['smart_calib']}")
        self.smart_calib_btn.setMinimumHeight(45)
        self.smart_calib_btn.clicked.connect(self.trigger_smart_calib)
        self.smart_calib_btn.setStyleSheet(f"border-color: {self.theme['accent']}; color: {self.theme['accent']}; font-size: 14px; margin-top: 5px;")
        left_col.addWidget(self.smart_calib_btn)

        # Console
        self.console_block = UIBlock(self.t["console_log"], self.theme)
        self.console_out = QPlainTextEdit()
        self.console_out.setReadOnly(True)
        self.console_out.setFixedHeight(120)
        self.console_out.setStyleSheet(f"""
            background-color: {self.theme['bg']};
            color: {self.theme['text']};
            border: none;
            font-size: 10px;
            font-family: 'Consolas', monospace;
        """)
        self.console_block.main_layout.addWidget(self.console_out)
        left_col.addWidget(self.console_block)

        main_hud.addLayout(left_col, 2)

        # RIGHT COLUMN (SCROLLABLE)
        right_col = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: transparent; }} QScrollBar:vertical {{ width: 0px; }}")
        scroll_content = QWidget()
        scroll_content.setStyleSheet(f"background-color: transparent;")
        self.config_layout = QVBoxLayout(scroll_content)
        self.config_layout.setContentsMargins(0, 0, 10, 0)

        # Identity
        self.id_block = UIBlock(self.t["identity"], self.theme)
        self.id_block.main_layout.addWidget(QLabel(f"{self.t['user_label']}@alice bless"))
        self.config_layout.addWidget(self.id_block)

        # Profiles
        self.profile_block = UIBlock("Profiles", self.theme)
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(self.cfg.list_profiles())
        self.profile_combo.setCurrentText(self.cfg.get_active_profile())
        self.profile_combo.currentTextChanged.connect(self.on_profile_changed)
        profile_layout.addWidget(QLabel("Load:"))
        profile_layout.addWidget(self.profile_combo)

        save_profile_btn = QPushButton("Save Current")
        save_profile_btn.clicked.connect(self.save_current_profile)
        profile_layout.addWidget(save_profile_btn)

        self.profile_block.main_layout.addLayout(profile_layout)

        # Export/Import
        exp_imp_layout = QHBoxLayout()
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self.export_config)
        exp_imp_layout.addWidget(export_btn)

        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self.import_config)
        exp_imp_layout.addWidget(import_btn)

        self.profile_block.main_layout.addLayout(exp_imp_layout)
        self.config_layout.addWidget(self.profile_block)

        # Engine Mode
        self.mode_block = UIBlock(self.t["engine_mode"], self.theme)
        self.mode_sel = QComboBox()
        self.mode_sel.addItems(["Full Body", "Upper Body", "Hands Only"])
        self.mode_sel.setCurrentText(self.cfg.get('tracking', 'mode'))
        self.mode_sel.currentTextChanged.connect(lambda v: self.cfg.set('tracking', 'mode', v))
        self.mode_block.main_layout.addWidget(self.mode_sel)

        fingers = QCheckBox(self.t["use_fingers"])
        fingers.setChecked(self.cfg.get('tracking', 'use_fingers'))
        fingers.stateChanged.connect(lambda s: self.cfg.set('tracking', 'use_fingers', s == Qt.Checked))
        self.mode_block.main_layout.addWidget(fingers)

        # Knee/Hip tracking (NEW)
        knees_cb = QCheckBox("Enable Knee Tracking")
        knees_cb.setChecked(self.cfg.get('trackers', 'enable_knees', default=False))
        knees_cb.stateChanged.connect(lambda s: self.cfg.set('trackers', 'enable_knees', s == Qt.Checked))
        self.mode_block.main_layout.addWidget(knees_cb)

        hips_cb = QCheckBox("Enable Hip Tracking")
        hips_cb.setChecked(self.cfg.get('trackers', 'enable_hips', default=False))
        hips_cb.stateChanged.connect(lambda s: self.cfg.set('trackers', 'enable_hips', s == Qt.Checked))
        self.mode_block.main_layout.addWidget(hips_cb)

        self.config_layout.addWidget(self.mode_block)

        # Performance
        self.perf_block = UIBlock(self.t["performance"], self.theme)
        comp = QComboBox()
        comp.addItems([f"COMPLEXITY: 0", f"COMPLEXITY: 1", f"COMPLEXITY: 2"])
        comp.setCurrentIndex(self.cfg.get('tracking', 'model_complexity'))
        comp.currentIndexChanged.connect(lambda i: self.cfg.set('tracking', 'model_complexity', i))
        self.perf_block.main_layout.addWidget(comp)

        self.add_slider(self.perf_block.main_layout, self.t["conf_det"], 0.1, 1.0, 'tracking', 'min_detection_confidence')
        self.add_slider(self.perf_block.main_layout, self.t["conf_tra"], 0.1, 1.0, 'tracking', 'min_tracking_confidence')
        self.add_slider(self.perf_block.main_layout, self.t["smoothing"], 0.05, 0.9, 'tracking', 'smooth_factor')
        self.config_layout.addWidget(self.perf_block)

        # Quality Graphs (NEW)
        self.graph_block = UIBlock("Tracking Quality", self.theme)
        graph_layout = QVBoxLayout()

        self.fps_graph = QualityGraph(self.theme, "FPS")
        graph_layout.addWidget(self.fps_graph)

        self.conf_graph = QualityGraph(self.theme, "Confidence")
        graph_layout.addWidget(self.conf_graph)

        self.graph_block.main_layout.addLayout(graph_layout)
        self.config_layout.addWidget(self.graph_block)

        # System
        self.sys_block = UIBlock(self.t["system"], self.theme)

        # Theme Switcher
        self.sys_block.main_layout.addWidget(QLabel(f"{self.t['theme_label']}:"))
        theme_sel = QComboBox()
        theme_sel.addItems(list(THEMES.keys()))
        theme_sel.setCurrentText(self.theme_name)
        theme_sel.currentTextChanged.connect(self.change_theme_live)
        self.sys_block.main_layout.addWidget(theme_sel)

        # Overlay Mode Toggle (NEW)
        self.overlay_cb = QCheckBox("Overlay Mode (Always on Top)")
        self.overlay_cb.setChecked(self.cfg.get('visuals', 'overlay_mode', default=False))
        self.overlay_cb.stateChanged.connect(self.toggle_overlay_mode)
        self.sys_block.main_layout.addWidget(self.overlay_cb)

        # Camera Source
        self.sys_block.main_layout.addSpacing(10)
        self.sys_block.main_layout.addWidget(QLabel(f"{self.t['cam_source']}:"))
        self.cam_list = QComboBox()
        self.detect_cams()
        self.cam_list.currentIndexChanged.connect(lambda i: self.cfg.set('camera', 'device_id', self.cam_list.itemData(i)))
        self.sys_block.main_layout.addWidget(self.cam_list)

        # Manual Wizard Trigger
        self.sys_block.main_layout.addSpacing(10)
        rerun_btn = QPushButton(self.t["rerun_wizard"])
        rerun_btn.clicked.connect(self.launch_wizard)
        self.sys_block.main_layout.addWidget(rerun_btn)

        save_btn = QPushButton(self.t["save_reboot"])
        save_btn.setStyleSheet(f"background-color: {self.theme['border']}; color: {self.theme['accent']}; font-weight: 800; margin-top: 15px;")
        save_btn.clicked.connect(self.reboot_engine)
        self.sys_block.main_layout.addWidget(save_btn)

        self.config_layout.addWidget(self.sys_block)
        self.config_layout.addStretch()

        scroll.setWidget(scroll_content)
        right_col.addWidget(scroll)
        main_hud.addLayout(right_col, 1)

        self.root_layout.addLayout(main_hud)

        # FOOTER
        footer = QLabel(self.t["footer"])
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet(f"color: {self.theme['faded']}; font-size: 10px; border: none;")
        self.root_layout.addWidget(footer)

        # === HOTKEYS (NEW) ===
        self.setup_hotkeys()

        # === BOOT SEQUENCE ===
        self.engine = None
        self.boot_and_start()

    def init_system_tray(self):
        """Инициализация системного трея"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))

        tray_menu = QMenu()

        show_action = QAction("Show WebHTC", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)

        hide_action = QAction("Hide to Tray", self)
        hide_action.triggered.connect(self.hide_to_tray)
        tray_menu.addAction(hide_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_window()

    def show_window(self):
        self.showNormal()
        self.activateWindow()

    def hide_to_tray(self):
        self.hide()

    def quit_app(self):
        if self.engine:
            self.engine.stop()
            self.engine.wait(1000)
        self.cfg.save()
        QApplication.quit()

    def closeEvent(self, ev):
        if self.cfg.get('system', 'minimize_to_tray', default=True) and self.tray_icon:
            ev.ignore()
            self.hide_to_tray()
            self.tray_icon.showMessage("WebHTC", "Running in system tray", QSystemTrayIcon.Information, 2000)
        else:
            if self.engine:
                self.engine.stop()
                self.engine.wait(1000)
            self.cfg.save()
            super().closeEvent(ev)

    def setup_hotkeys(self):
        """Настройка горячих клавиш"""
        # Space - Toggle tracking
        shortcut_space = QShortcut(QKeySequence("Space"), self)
        shortcut_space.activated.connect(self.toggle_tracking)

        # C - Calibration
        shortcut_c = QShortcut(QKeySequence("C"), self)
        shortcut_c.activated.connect(self.trigger_smart_calib)

        # R - Reset calibration
        shortcut_r = QShortcut(QKeySequence("R"), self)
        shortcut_r.activated.connect(self.reset_calibration)

        # Q - Quit
        shortcut_q = QShortcut(QKeySequence("Ctrl+Q"), self)
        shortcut_q.activated.connect(self.quit_app)

        # F - Toggle overlay
        shortcut_f = QShortcut(QKeySequence("F"), self)
        shortcut_f.activated.connect(self.toggle_overlay_mode)

        # H - Toggle help/hints
        shortcut_h = QShortcut(QKeySequence("H"), self)
        shortcut_h.activated.connect(self.toggle_hints)

        self.add_log("SYS", "Hotkeys: Space=Toggle, C=Calibrate, R=Reset, Ctrl+Q=Quit, F=Overlay, H=Hints")

    def toggle_tracking(self):
        """Включение/выключение трекинга"""
        if self.engine and self.engine.isRunning():
            self.engine.stop()
            self.add_log("SYS", "Tracking paused (Space)")
            self.on_status("PAUSED", "#ffaa00")
        else:
            self.start_tracking()
            self.add_log("SYS", "Tracking resumed (Space)")

    def reset_calibration(self):
        """Сброс калибровки"""
        self.cfg.set('calibration', 'scale', 1.5)
        self.cfg.set('calibration', 'offset_y', 0.0)
        self.cfg.set('calibration', 'offset_z', 0.0)
        self.cfg.save()
        self.reboot_engine()
        self.add_log("SYS", "Calibration reset (R)")

    def toggle_overlay_mode(self):
        """Переключение режима overlay"""
        current = self.cfg.get('visuals', 'overlay_mode', default=False)
        self.cfg.set('visuals', 'overlay_mode', not current)
        self.cfg.save()

        if not current:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.add_log("SYS", "Overlay mode ON (F)")
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            self.add_log("SYS", "Overlay mode OFF (F)")

        self.show()

    def toggle_hints(self):
        """Показать подсказки по горячим клавишам"""
        QMessageBox.information(self, "Hotkeys",
            "Space - Toggle tracking\n"
            "C - Start calibration\n"
            "R - Reset calibration\n"
            "Ctrl+Q - Quit\n"
            "F - Toggle overlay mode\n"
            "H - This help"
        )

    def on_profile_changed(self, name):
        """Смена профиля"""
        if self.cfg.load_profile(name):
            self.cfg.save()
            self.reboot_engine()
            self.add_log("SYS", f"Profile '{name}' loaded")

    def save_current_profile(self):
        """Сохранение текущего профиля"""
        name, ok = QLineEdit.getText(self, "Save Profile", "Profile name:")
        if ok and name:
            self.cfg.save_profile(name)
            self.profile_combo.clear()
            self.profile_combo.addItems(self.cfg.list_profiles())
            self.profile_combo.setCurrentText(name)
            self.add_log("SYS", f"Profile '{name}' saved")

    def export_config(self):
        """Экспорт конфигурации"""
        from PySide6.QtWidgets import QFileDialog
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Config", "webhtc_export.json", "JSON Files (*.json)")
        if filepath:
            if self.cfg.export_config(filepath):
                self.add_log("SYS", f"Config exported to {filepath}")
                QMessageBox.information(self, "Export", "Configuration exported successfully!")

    def import_config(self):
        """Импорт конфигурации"""
        from PySide6.QtWidgets import QFileDialog
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Config", "", "JSON Files (*.json)")
        if filepath:
            if self.cfg.import_config(filepath):
                self.add_log("SYS", f"Config imported from {filepath}")
                QMessageBox.information(self, "Import", "Configuration imported! Restarting...")
                self.reboot_engine()

    def boot_and_start(self):
        self.splash = BootSplash(self.cfg, self)
        self.splash.finished.connect(self.on_boot_finished)
        self.splash.start()

    def on_boot_finished(self):
        if self.cfg.get('system', 'first_run'):
            self.launch_wizard()
        else:
            self.reboot_engine()

    def launch_wizard(self):
        wiz = SetupWizard(self.cfg, self)
        if wiz.exec():
            self.cfg.set('system', 'first_run', False)
            self.cfg.save()
            self.reboot_engine()
        else:
            self.reboot_engine()

    def apply_global_styles(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {self.theme['bg']};
                color: {self.theme['text']};
                font-family: 'Consolas', 'Monospace';
            }}
            QLabel {{ border: none; background: transparent; }}
            QPushButton {{
                background-color: {self.theme['bg']};
                color: {self.theme['text']};
                border: 1px solid {self.theme['border']};
                padding: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {self.theme['border']}; }}
            QComboBox, QLineEdit {{
                background-color: {self.theme['surface']};
                color: {self.theme['accent']};
                border: 1px solid {self.theme['border']};
                padding: 5px;
            }}
            QCheckBox {{ background: transparent; border: none; }}
            QSlider::groove:horizontal {{ background: {self.theme['surface']}; height: 2px; }}
            QSlider::handle:horizontal {{ background: {self.theme['accent']}; width: 14px; height: 14px; margin: -6px 0; }}
        """)

    def create_header(self):
        row = QHBoxLayout()
        self.clock = QLabel(time.strftime('%H:%M'))
        row.addWidget(self.clock)
        row.addStretch()
        title = QLabel(self.t["console_name"])
        title.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {self.theme['accent']}; letter-spacing: 2px;")
        row.addWidget(title)
        row.addStretch()

        lang_btn = QPushButton(f"[{self.lang}]")
        lang_btn.setFixedWidth(60)
        lang_btn.clicked.connect(self.switch_lang)
        row.addWidget(lang_btn)
        self.root_layout.addLayout(row)

    def add_slider(self, layout, text, mn, mx, grp, key):
        val = self.cfg.get(grp, key)
        l = QVBoxLayout()
        lbl = QLabel(f"{text}: {val:.2f}")
        s = QSlider(Qt.Horizontal)
        s.setRange(int(mn*100), int(mx*100))
        s.setValue(int(val*100))
        s.valueChanged.connect(lambda v: self.slider_moved(v, lbl, text, grp, key))
        l.addWidget(lbl)
        l.addWidget(s)
        layout.addLayout(l)

    def slider_moved(self, val, lbl, text, grp, key):
        f = val / 100.0
        lbl.setText(f"{text}: {f:.2f}")
        self.cfg.set(grp, key, f)
        if self.engine:
            if key == 'scale':
                self.engine.scale = f
            elif key in ['offset_y', 'offset_z']:
                setattr(self.engine, key, f)
            elif key == 'smooth_factor':
                min_cutoff = max(0.01, 1.5 * (1.1 - f))
                for filter_obj in self.engine.filters.values():
                    filter_obj.min_cutoff = min_cutoff

    def trigger_smart_calib(self):
        if self.engine:
            self.engine.start_calibration()
            self.smart_calib_btn.setEnabled(False)

    def on_calib_status(self, text_key, n):
        text = self.t.get(text_key, text_key).replace("{n}", str(n))
        self.on_status(text, self.theme['accent'])

    def on_calib_done(self, s, y, z):
        self.cfg.set('calibration', 'scale', s)
        self.cfg.set('calibration', 'offset_y', y)
        self.cfg.set('calibration', 'offset_z', z)
        self.cfg.save()
        self.smart_calib_btn.setEnabled(True)
        QMessageBox.information(self, "System", self.t["calib_success"])

    def on_quality_data(self, data):
        """Обновление графиков качества"""
        self.fps_graph.update_data(data.get('fps_avg', 0))
        self.conf_graph.update_data(data.get('confidence_avg', 0) * 100)

    def add_log(self, tag, msg):
        timestamp = time.strftime("%H:%M:%S")
        color = self.theme['accent']
        if tag == "WARN": color = "#ffaa00"
        elif tag == "ERR": color = "#ff5555"

        formatted = f'<span style="color: {self.theme["faded"]}">{timestamp}</span> ' \
                    f'<span style="color: {color}">[{tag}]</span> {msg}'
        self.console_out.appendHtml(formatted)
        self.console_out.verticalScrollBar().setValue(
            self.console_out.verticalScrollBar().maximum()
        )

    def detect_cams(self):
        self.cam_list.blockSignals(True)
        self.cam_list.clear()
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                self.cam_list.addItem(f"CAM_NODE_{i}", i)
                cap.release()

        target_id = self.cfg.get('camera', 'device_id')
        idx = self.cam_list.findData(target_id)
        if idx != -1:
            self.cam_list.setCurrentIndex(idx)
        else:
            self.cam_list.setCurrentIndex(0)
        self.cam_list.blockSignals(False)

        if self.cam_list.count() == 0:
            self.cam_list.addItem("NO_CAMERA_FOUND", -1)

    def switch_lang(self):
        self.cfg.set('visuals', 'language', "RU" if self.lang == "EN" else "EN")
        self.cfg.save()
        sys.exit()

    def change_theme_live(self, name):
        self.cfg.set('visuals', 'theme', name)
        self.cfg.save()
        QMessageBox.information(self, "System", "Theme changed. Please restart to apply all visual updates.")
        sys.exit()

    def start_tracking(self):
        if self.engine:
            self.engine.stop()
            self.engine.wait()

        self.engine = TrackingEngine(self.cfg)
        self.engine.frame_ready.connect(self.update_video)
        self.engine.status_changed.connect(self.on_status)
        self.engine.fps_updated.connect(lambda f: self.fps_lbl.setText(f"FPS: {f:02d}"))
        self.engine.calib_status.connect(self.on_calib_status)
        self.engine.calib_done.connect(self.on_calib_done)
        self.engine.log_msg.connect(self.add_log)
        self.engine.quality_data.connect(self.on_quality_data)
        self.engine.camera_lost.connect(lambda: self.add_log("WARN", "Camera disconnected!"))
        self.engine.camera_restored.connect(lambda: self.add_log("INFO", "Camera reconnected"))
        self.engine.start()
        self.add_log("SYS", "Tracking Engine Started")

    def reboot_engine(self):
        self.cfg.save()
        self.start_tracking()

    @Slot(np.ndarray)
    def update_video(self, frame):
        h, w, c = frame.shape
        frame[0::4, :] = (frame[0::4, :] * 0.6).astype(np.uint8)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, c * w, QImage.Format_RGB888).copy()
        self.video_display.setPixmap(QPixmap.fromImage(qimg).scaled(640, 480, Qt.KeepAspectRatio))

    @Slot(str, str)
    def on_status(self, text, color):
        orig_text = self.t.get(f"status_{text.lower()}", text)
        self.status_lbl.setText(f"[{orig_text.upper()}]")
        self.status_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")


if __name__ == "__main__":
    from PySide6.QtWidgets import QStyle
    app = QApplication(sys.argv)
    window = WebHTCApp()
    window.show()
    sys.exit(app.exec())
