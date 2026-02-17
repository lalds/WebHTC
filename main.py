"""
WebHTC: Ultimate VR Tracking Suite
Entry point for the application.
"""
import sys
import os

# Ensure the root directory is in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from ui.tracking import WebHTCApp
from PySide6.QtWidgets import QApplication

def main():
    # Set application name for Windows
    if os.name == 'nt':
        import ctypes
        myappid = 'lalds.webhtc.tracker.18.1' # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    app.setApplicationName("WebHTC Pro")
    
    # Launch main window
    window = WebHTCApp()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
