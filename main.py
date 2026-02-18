"""
WebHTC: Ultimate VR Tracking Suite v2.0
Entry point for the application with crash handling
"""
import sys
import os

# Ensure the root directory is in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Install crash handler first
from core.crash_handler import install_crash_handler
crash_handler = install_crash_handler("WebHTC Pro")

from ui.tracking import WebHTCApp
from PySide6.QtWidgets import QApplication


def main():
    # Set application name for Windows
    if os.name == 'nt':
        import ctypes
        myappid = 'lalds.webhtc.tracker.18.2'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    app.setApplicationName("WebHTC Pro")
    app.setOrganizationName("WebHTC Project")

    # Set application style
    app.setStyle("Fusion")

    # Launch main window
    window = WebHTCApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)
