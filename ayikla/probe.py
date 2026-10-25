"""Opt-in first-paint marker used by the local package benchmark."""
import json
import os
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QTimer


class StartupProbe(QObject):
    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Paint and not getattr(self, "done", False):
            self.done = True
            path = Path(os.environ["AYIKLA_STARTUP_PROBE"])
            path.write_text(json.dumps({"ready": time.perf_counter()}), "utf-8")
            QTimer.singleShot(0, watched.close)
        return False


def install_probe(window):
    if os.environ.get("AYIKLA_STARTUP_PROBE"):
        window._startup_probe = StartupProbe(window)
        window.installEventFilter(window._startup_probe)
