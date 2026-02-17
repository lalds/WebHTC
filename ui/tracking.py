"""
WebHTC: Open Source XR Tracking Suite (V18.1 - Professional)
Focused on Accessibility & High-Contrast Design.
"""
import sys
import cv2
import numpy as np
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QSlider, 
                             QStackedWidget, QFrame, QCheckBox, QComboBox, 
                             QLineEdit, QScrollArea, QMessageBox, QPlainTextEdit)
from PySide6.QtCore import Qt, QSize, Slot, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QColor, QFont, QPalette

from core.config_manager import ConfigManager
from core.tracking_engine import TrackingEngine
from ui.localization import TRANSLATIONS
from core.boot_sequence import BootSplash
from ui.setup_wizard import SetupWizard

# --- THEME DEFINITIONS ---
# ... (rest of the file remains same, just replacing imports and parts of WebHTCApp)
THEMES = {
    "Matrix": {
        "bg": "#050605",
        "surface": "#0a120a",
        "border": "#1a2e1a",
        "accent": "#a8ffbc",
        "text": "#a8ffbc",
        "faded": "#1d331d"
    },
    "Void": {
        "bg": "#000000",
        "surface": "#090909",
        "border": "#1a1a1a",
        "accent": "#ffffff",
        "text": "#eeeeee",
        "faded": "#333333"
    },
    "Terminal": {
        "bg": "#080b12",
        "surface": "#0e141d",
        "border": "#1c2a3d",
        "accent": "#5294e2",
        "text": "#d3dae3",
        "faded": "#384d6b"
    }
}

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
        
        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.root_layout = QVBoxLayout(self.central)
        self.root_layout.setContentsMargins(25, 25, 25, 25)
        self.root_layout.setSpacing(20)
        
        # --- HEADER ---
        self.create_header()
        
        # --- MAIN HUD ---
        main_hud = QHBoxLayout()
        main_hud.setSpacing(25)
        
        # LEFT COLUMN
        left_col = QVBoxLayout()
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
        
        # Console Block
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
        
        # RIGHT COLUMN (SCROLLABLE SETTINGS)
        right_col = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: transparent; }} QScrollBar:vertical {{ width: 0px; }}") # Clean scroll
        scroll_content = QWidget()
        scroll_content.setStyleSheet(f"background-color: transparent;")
        self.config_layout = QVBoxLayout(scroll_content)
        self.config_layout.setContentsMargins(0, 0, 10, 0)
        
        # Identity
        self.id_block = UIBlock(self.t["identity"], self.theme)
        self.id_block.main_layout.addWidget(QLabel(f"{self.t['user_label']}@alice bless"))
        self.config_layout.addWidget(self.id_block)
        
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
        self.config_layout.addWidget(self.mode_block)
        
        # Performance Tuning
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
        
        # System Hardware & Appearance
        self.sys_block = UIBlock(self.t["system"], self.theme)
        
        # Theme Switcher
        self.sys_block.main_layout.addWidget(QLabel(f"{self.t['theme_label']}:"))
        theme_sel = QComboBox()
        theme_sel.addItems(list(THEMES.keys()))
        theme_sel.setCurrentText(self.theme_name)
        theme_sel.currentTextChanged.connect(self.change_theme_live)
        self.sys_block.main_layout.addWidget(theme_sel)
        
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
        
        # --- BOOT SEQUENCE ---
        self.engine = None
        self.boot_and_start()

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
            # Wizard completed successfully
            self.cfg.set('system', 'first_run', False)
            self.cfg.save()
            self.reboot_engine()
        else:
            # Let's run engine but keep first_run=True so it shows next time
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
        
        # Language Switch
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
            if key == 'scale': self.engine.scale = f
            elif key in ['offset_y', 'offset_z']: setattr(self.engine, key, f)
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
        # We need to refresh UI sliders manually or just restart engine
        # For simplicity, let's just update engine values since they are already set inside engine
        QMessageBox.information(self, "System", self.t["calib_success"])
        # Re-sync UI (quick and dirty)
        sys.exit() # Restart to apply all new calibrated values to sliders

    def add_log(self, tag, msg):
        timestamp = time.strftime("%H:%M:%S")
        color = self.theme['accent']
        if tag == "WARN": color = "#ffaa00"
        elif tag == "ERR": color = "#ff5555"
        
        formatted = f'<span style="color: {self.theme["faded"]}">{timestamp}</span> ' \
                    f'<span style="color: {color}">[{tag}]</span> {msg}'
        self.console_out.appendHtml(formatted)
        # Scroll to bottom
        self.console_out.verticalScrollBar().setValue(
            self.console_out.verticalScrollBar().maximum()
        )

    def detect_cams(self):
        self.cam_list.blockSignals(True)
        self.cam_list.clear()
        # Scan more indices for robustness
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
        sys.exit() # Force restart for full lang apply

    def change_theme_live(self, name):
        self.cfg.set('visuals', 'theme', name)
        self.cfg.save()
        QMessageBox.information(self, "System", "Theme changed. Please restart to apply all visual updates.")
        sys.exit()

    def start_tracking(self):
        if self.engine: self.engine.stop(); self.engine.wait()
        self.engine = TrackingEngine(self.cfg)
        self.engine.frame_ready.connect(self.update_video)
        self.engine.status_changed.connect(self.on_status)
        self.engine.fps_updated.connect(lambda f: self.fps_lbl.setText(f"FPS: {f:02d}"))
        self.engine.calib_status.connect(self.on_calib_status)
        self.engine.calib_done.connect(self.on_calib_done)
        self.engine.log_msg.connect(self.add_log)
        self.engine.start()
        self.add_log("SYS", "Tracking Engine Started")

    def reboot_engine(self):
        self.cfg.save()
        self.start_tracking()

    @Slot(np.ndarray)
    def update_video(self, frame):
        h, w, c = frame.shape
        # Visual styling
        frame[0::4, :] = (frame[0::4, :] * 0.6).astype(np.uint8)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, c * w, QImage.Format_RGB888).copy()
        self.video_display.setPixmap(QPixmap.fromImage(qimg).scaled(640, 480, Qt.KeepAspectRatio))

    @Slot(str, str)
    def on_status(self, text, color):
        orig_text = self.t.get(f"status_{text.lower()}", text)
        self.status_lbl.setText(f"[{orig_text.upper()}]")
        self.status_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")

    def closeEvent(self, ev):
        if self.engine:
            self.engine.stop()
            self.engine.wait(1000) # Wait up to 1s for clean exit
        self.cfg.save()
        super().closeEvent(ev)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WebHTCApp()
    window.show()
    sys.exit(app.exec())
