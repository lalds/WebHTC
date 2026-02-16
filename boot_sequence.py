"""
WebHTC: Boot Sequence & Diagnostics Splash
Stylized terminal-style initialization with real-time checks.
"""
import sys
import time
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QProgressBar, 
                             QFrame, QTextEdit)
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QColor

from diagnostics import SystemDiagnostics
from localization import TRANSLATIONS

class BootSplash(QDialog):
    finished = Signal()

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.cfg = config_manager
        self.lang = self.cfg.get('visuals', 'language')
        self.t = TRANSLATIONS[self.lang]
        self.diag = SystemDiagnostics(self.lang)
        
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(600, 400)
        
        # Styles for terminal look
        self.bg_color = "#050605"
        self.accent_color = "#a8ffbc"
        
        layout = QVBoxLayout(self)
        self.frame = QFrame()
        self.frame.setStyleSheet(f"""
            QFrame {{ 
                background-color: {self.bg_color}; 
                border: 2px solid {self.accent_color}; 
                border-radius: 5px;
            }}
        """)
        frame_layout = QVBoxLayout(self.frame)
        
        self.title_lbl = QLabel(f" ~/ {self.t['console_name']}")
        self.title_lbl.setStyleSheet(f"color: {self.accent_color}; font-size: 18px; font-weight: bold; border: none;")
        frame_layout.addWidget(self.title_lbl)
        
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet(f"""
            QTextEdit {{
                background-color: transparent;
                color: {self.accent_color};
                font-family: 'Consolas', 'Monospace';
                font-size: 12px;
                border: none;
            }}
        """)
        frame_layout.addWidget(self.log_area)
        
        self.progress = QProgressBar()
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {self.accent_color};
                background: transparent;
                height: 5px;
                text-align: center;
            }}
            QProgressBar::chunk {{ background: {self.accent_color}; }}
        """)
        self.progress.setTextVisible(False)
        frame_layout.addWidget(self.progress)
        
        layout.addWidget(self.frame)
        
        self.logs = []
        self.step = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_step)
        
    def show_log(self, text, color=None):
        ts = time.strftime('%H:%M:%S')
        line = f"[{ts}] {text}"
        self.log_area.append(line)
        self.log_area.ensureCursorVisible()

    def start(self):
        self.show()
        self.show_log(self.t["boot_init"])
        self.timer.start(500)

    def next_step(self):
        self.step += 1
        self.progress.setValue(int(self.step / 5.0 * 100))
        
        if self.step == 1:
            self.show_log(f"{self.t['boot_check']}KERNEL_X64")
        elif self.step == 2:
            ok, msg = self.diag.check_steamvr()
            self.show_log(f"{self.t['boot_check']}STEAMVR -> {'[OK]' if ok else '[!!!]'} {msg}")
        elif self.step == 3:
            ok, msg = self.diag.check_vmt_driver()
            self.show_log(f"{self.t['boot_check']}VMT_PROTOCOL -> {'[OK]' if ok else '[!!!]'} {msg}")
        elif self.step == 4:
            ok, msg = self.diag.check_cameras()
            self.show_log(f"{self.t['boot_check']}OPTICAL_SENSORS -> {'[OK]' if ok else '[!!!]'} {msg}")
        elif self.step == 5:
            self.show_log(self.t["boot_done"])
            QTimer.singleShot(1000, self.finish)
            
    def finish(self):
        self.timer.stop()
        self.hide()
        self.finished.emit()
        self.accept()

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    from config_manager import ConfigManager
    app = QApplication(sys.argv)
    cfg = ConfigManager()
    splash = BootSplash(cfg)
    splash.start()
    splash.exec()
