"""
WebHTC Crash Reporter
Captures unhandled exceptions and generates crash reports
"""
import sys
import traceback
import logging
from datetime import datetime
import os

logger = logging.getLogger("CrashReporter")

CRASH_REPORTS_DIR = "crash_reports"

class CrashHandler:
    """Обработчик необработанных исключений"""

    def __init__(self, app_name="WebHTC"):
        self.app_name = app_name
        self._ensure_reports_dir()

    def _ensure_reports_dir(self):
        if not os.path.exists(CRASH_REPORTS_DIR):
            os.makedirs(CRASH_REPORTS_DIR)

    def install(self):
        """Установка обработчиков исключений"""
        sys.excepthook = self._handle_exception
        # Для Qt приложений
        try:
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                # Обработка исключений в слотах
                pass
        except:
            pass

        logger.info("CrashHandler installed")

    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """Обработка необработанного исключения"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        self.generate_report(exc_type, exc_value, exc_traceback)

    def generate_report(self, exc_type, exc_value, exc_traceback):
        """Генерация отчёта о сбое"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(CRASH_REPORTS_DIR, f"crash_{timestamp}.txt")

        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write(f"CRASH REPORT - {self.app_name}\n")
                f.write("=" * 60 + "\n\n")

                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Python Version: {sys.version}\n")
                f.write(f"Platform: {sys.platform}\n\n")

                f.write("-" * 60 + "\n")
                f.write("EXCEPTION INFO\n")
                f.write("-" * 60 + "\n")
                f.write(f"Type: {exc_type.__name__}\n")
                f.write(f"Value: {exc_value}\n\n")

                f.write("-" * 60 + "\n")
                f.write("TRACEBACK\n")
                f.write("-" * 60 + "\n")
                tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
                f.writelines(tb_lines)

                f.write("\n" + "=" * 60 + "\n")
                f.write("END OF REPORT\n")
                f.write("=" * 60 + "\n")

            logger.error(f"Crash report saved to: {report_file}")
            print(f"\n{'='*60}")
            print(f"CRASH DETECTED! Report saved to: {report_file}")
            print(f"{'='*60}")
            print(f"Error: {exc_type.__name__}: {exc_value}")
            print("\nPlease share this report with developers.")
            print("="*60 + "\n")

        except Exception as e:
            logger.error(f"Failed to save crash report: {e}")

    def show_crash_dialog(self, exc_type, exc_value, exc_traceback):
        """Показ диалога о сбое (для Qt приложений)"""
        try:
            from PySide6.QtWidgets import QMessageBox, QTextEdit, QVBoxLayout, QDialog, QPushButton
            from PySide6.QtCore import Qt

            dialog = QDialog()
            dialog.setWindowTitle("Application Error")
            dialog.setModal(True)

            layout = QVBoxLayout(dialog)

            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText(f"An unexpected error occurred:")
            msg.setInformativeText(f"{exc_type.__name__}: {exc_value}")
            msg.setStandardButtons(QMessageBox.Ok)

            # Details
            details_text = QTextEdit()
            details_text.setReadOnly(True)
            details_text.setPlainText(traceback.format_exc())
            details_text.setMaximumHeight(200)

            layout.addWidget(details_text)

            report_btn = QPushButton("Save Crash Report")
            report_btn.clicked.connect(lambda: self.generate_report(exc_type, exc_value, exc_traceback))
            layout.addWidget(report_btn)

            dialog.exec()

        except Exception as e:
            logger.error(f"Failed to show crash dialog: {e}")


def install_crash_handler(app_name="WebHTC"):
    """Установка глобального обработчика сбоев"""
    handler = CrashHandler(app_name)
    handler.install()
    return handler


# Декоратор для защиты функций
def catch_crashes(func):
    """Декоратор для перехвата исключений в функциях"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Exception in {func.__name__}: {e}")
            traceback.print_exc()
            return None
    return wrapper
