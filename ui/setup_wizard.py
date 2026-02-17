"""
WebHTC: Setup Wizard
Guides users through driver installation and system diagnostics.
"""
import sys
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, 
                             QHBoxLayout, QFrame, QStackedWidget)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from core.diagnostics import SystemDiagnostics
from ui.localization import TRANSLATIONS

# --- WIZARD THEME ---
THEME = {
    "bg": "#0a0c0a",
    "surface": "#121a12",
    "border": "#2d4a2d",
    "accent": "#a8ffbc",
    "text": "#a8ffbc",
    "error": "#ff5555"
}

class WizardPage(QFrame):
    def __init__(self, title, content, theme):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        
        t = QLabel(f" ~/ {title.upper()}")
        t.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {theme['accent']}; margin-bottom: 20px;")
        layout.addWidget(t)
        
        c = QLabel(content)
        c.setWordWrap(True)
        c.setStyleSheet(f"font-size: 14px; line-height: 1.5; color: #ccc;")
        layout.addWidget(c)
        layout.addStretch()

class SetupWizard(QDialog):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.cfg = config_manager
        self.lang = self.cfg.get('visuals', 'language')
        self.t = TRANSLATIONS[self.lang]
        self.diag = SystemDiagnostics(self.lang)
        
        self.setWindowTitle(self.t["wizard_title"])
        self.resize(740, 540)
        
        self.setStyleSheet(f"""
            QDialog {{ background-color: {THEME['bg']}; }}
            QLabel {{ color: {THEME['text']}; font-family: 'Consolas'; border: none; }}
            QPushButton {{
                background-color: {THEME['bg']}; color: {THEME['text']};
                border: 1px solid {THEME['border']}; padding: 10px 20px;
                font-family: 'Consolas'; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {THEME['accent']}; color: {THEME['bg']}; }}
        """)
        
        self.layout = QVBoxLayout(self)
        self.pages = QStackedWidget()
        self.layout.addWidget(self.pages)
        
        # --- PAGE 1: WELCOME ---
        self.pages.addWidget(WizardPage(self.t["wizard_welcome"], 
            "WebHTC is a professional accessibility tool that replaces expensive tracking hardware with neural computer vision.\n\n"
            "This wizard will help you link the neural tracking engine to your OpenVR environment.", THEME))
        
        # --- PAGE 2: VMT DRIVER ---
        p2 = QFrame()
        l2 = QVBoxLayout(p2)
        l2.setContentsMargins(40, 40, 40, 40)
        t2 = QLabel(f" ~/ {self.t['wizard_driver']}")
        t2.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {THEME['accent']};")
        l2.addWidget(t2)
        l2.addWidget(QLabel("\nWebHTC uses the Open-Source 'Virtual Motion Tracker' (VMT) protocol to speak with SteamVR.\n"))
        
        dl_btn = QPushButton("GET VMT DRIVER (RELEASES)")
        dl_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/gpsnmeajp/VirtualMotionTracker/releases")))
        l2.addWidget(dl_btn)
        
        l2.addWidget(QLabel("\nSTEPS:\n1. Download VMT Driver package.\n2. Move 'vmt' folder to: SteamVR/drivers/\n3. Restart SteamVR and enable VMT Driver in settings."))
        l2.addStretch()
        self.pages.addWidget(p2)
        
        # --- PAGE 3: DIAGNOSTICS ---
        p3 = QFrame()
        l3 = QVBoxLayout(p3)
        l3.setContentsMargins(40, 40, 40, 40)
        t3 = QLabel(f" ~/ {self.t['wizard_diag']}")
        t3.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {THEME['accent']};")
        l3.addWidget(t3)
        
        self.status_box = QVBoxLayout()
        self.add_check_row(self.t["diag_steamvr"], "WAITING...", self.status_box)
        self.add_check_row(self.t["diag_vmt"], "WAITING...", self.status_box)
        self.add_check_row(self.t["diag_camera"], "WAITING...", self.status_box)
        l3.addLayout(self.status_box)
        
        scan_btn = QPushButton("EXECUTE_SYSTEM_SCAN")
        scan_btn.clicked.connect(self.run_diag)
        l3.addWidget(scan_btn)
        l3.addStretch()
        self.pages.addWidget(p3)
        
        # --- PAGE 4: READY ---
        self.pages.addWidget(WizardPage(self.t["wizard_ready"], 
            "Handshake verified. The neural tracking engine is operational.\n\n"
            "Proceed to the main console to begin tracking injection.", THEME))
        
        # --- NAV ---
        nav = QHBoxLayout()
        self.back_btn = QPushButton("< BACK")
        self.back_btn.clicked.connect(self.prev)
        nav.addWidget(self.back_btn)
        nav.addStretch()
        self.next_btn = QPushButton("NEXT >")
        self.next_btn.clicked.connect(self.nxt)
        nav.addWidget(self.next_btn)
        self.layout.addLayout(nav)
        self.update_nav()

    def add_check_row(self, name, status, layout):
        r = QHBoxLayout()
        r.addWidget(QLabel(f"{name}:"))
        r.addStretch()
        l_stat = QLabel(status)
        r.addWidget(l_stat)
        layout.addLayout(r)

    def run_diag(self):
        res = self.diag.run_all_checks()
        self.update_row(0, res['steamvr'])
        self.update_row(1, res['vmt'])
        self.update_row(2, res['camera'])

    def update_row(self, idx, data):
        row = self.status_box.itemAt(idx).layout()
        lbl = row.itemAt(2).widget()
        if data['ok']:
            lbl.setText(f"[OK] {data['msg']}")
            lbl.setStyleSheet(f"color: {THEME['accent']}; font-weight: bold; border: none;")
        else:
            lbl.setText(f"[FAIL] {data['msg']}")
            lbl.setStyleSheet(f"color: {THEME['error']}; font-weight: bold; border: none;")

    def nxt(self):
        c = self.pages.currentIndex()
        if c < self.pages.count()-1: self.pages.setCurrentIndex(c+1); self.update_nav()
        else: self.accept()

    def prev(self):
        c = self.pages.currentIndex()
        if c > 0: self.pages.setCurrentIndex(c-1); self.update_nav()

    def update_nav(self):
        c = self.pages.currentIndex()
        self.back_btn.setEnabled(c > 0)
        self.next_btn.setText("FINISH" if c == self.pages.count()-1 else "NEXT >")

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    from core.config_manager import ConfigManager
    app = QApplication(sys.argv)
    cfg = ConfigManager()
    w = SetupWizard(cfg)
    w.exec()
