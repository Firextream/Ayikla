import os
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from .ui import MainWindow


def main() -> int:
    smoke_output = sys.argv[2] if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test" else None
    app = QApplication(sys.argv)
    app.setApplicationName("Ayikla")
    app.setOrganizationName("Ayikla")
    window = MainWindow()
    if os.environ.get("AYIKLA_HEADLESS_WINDOWS") == "1":
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    from .probe import install_probe
    install_probe(window)
    window.show_saved_state()
    if smoke_output:
        from .smoke import run_smoke
        QTimer.singleShot(0, lambda: run_smoke(app, window, smoke_output))
    elif len(sys.argv) == 2:
        QTimer.singleShot(0, lambda: window.open_folder(sys.argv[1]))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
