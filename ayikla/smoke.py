"""Developer-only frozen-executable verification using newly generated files."""

import json
import os
import time
import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFontDatabase, QImage, QKeyEvent, QLinearGradient, QPainter, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from .core import EDIT, KEPT, REJECTED


def run_smoke(app, window, output: str) -> None:
    # Windows' offscreen Qt backend has no system font database or real monitor.
    # Load installed Windows fonts read-only, then render a realistic canvas size.
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        font_root = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for name in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
            QFontDatabase.addApplicationFont(str(font_root / name))
        assert window.isFullScreen()
        window.showNormal()
        window.resize(1440, 960)
    directory = Path(output).resolve() / f"smoke-{uuid.uuid4().hex[:12]}"
    directory.mkdir(parents=True, exist_ok=False)
    shoot = directory / "Yapay çekim"
    shoot.mkdir()
    for index in range(1, 5):
        image = QImage(3000, 2000, QImage.Format.Format_RGB32)
        painter = QPainter(image)
        gradient = QLinearGradient(0, 0, 0, 2000)
        gradient.setColorAt(0, QColor("#517b91"))
        gradient.setColorAt(0.7, QColor("#d2c4a3"))
        gradient.setColorAt(1, QColor("#6d815b"))
        painter.fillRect(image.rect(), gradient)
        painter.setBrush(QColor("#dfd2aa"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2050, 330, 210, 210)
        painter.setBrush(QColor("#3f6458"))
        painter.drawPolygon(QPolygonF([QPointF(0, 1500), QPointF(750, 700),
                                      QPointF(1800, 1600), QPointF(3000, 950),
                                      QPointF(3000, 2000), QPointF(0, 2000)]))
        painter.setBrush(QColor("#233e32"))
        painter.drawPolygon(QPolygonF([QPointF(0, 1800), QPointF(1600, 1350),
                                      QPointF(3000, 1950), QPointF(3000, 2000), QPointF(0, 2000)]))
        painter.end()
        if not image.save(str(shoot / f"IMG_{index:04d}.JPG")):
            raise OSError("Yapay test JPEG'i üretilemedi.")
        if index != 2:
            (shoot / f"img_{index:04d}.cR3").write_bytes(b"GENERATED RAW TEST DATA " * 1000)

    window.grab().save(str(directory / "welcome.png"))
    started = time.monotonic()
    stage = 0
    checks = []
    timer = QTimer(window)
    timer.setInterval(30)

    def key(value):
        QApplication.sendEvent(window, QKeyEvent(QKeyEvent.Type.KeyPress, value,
                                                 Qt.KeyboardModifier.NoModifier))

    def finish(error=None):
        timer.stop()
        result = {"ok": error is None, "error": str(error) if error else None,
                  "checks": checks, "elapsed_seconds": round(time.monotonic() - started, 2),
                  "directory": str(directory)}
        (directory / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
        if window.session:
            window.session.close()
            window.session = None
        window.close()
        app.exit(1 if error else 0)

    def tick():
        nonlocal stage
        try:
            if time.monotonic() - started > 45:
                raise TimeoutError(f"Frozen UI stage {stage}: {window.feedback.text()}")
            if window.busy:
                return
            if stage == 0:
                window.open_folder(shoot)
            elif stage == 1:
                assert window.session and window.current.key == "img_0001"
                if window.canvas.image.isNull():
                    return
                window.grab().save(str(directory / "gallery.png"))
                checks.append("JPEG decode, gallery, full-screen startup and generated RAW pairing")
                key(Qt.Key.Key_Return)
            elif stage == 2:
                assert (shoot / KEPT / "img_0001.cR3").exists()
                assert window.current.key == "img_0002" and "yok" in window.raw_badge.text()
                key(Qt.Key.Key_X)
            elif stage == 3:
                assert (shoot / REJECTED / "IMG_0002.JPG").exists()
                key(Qt.Key.Key_Z)
            elif stage == 4:
                assert (shoot / "IMG_0002.JPG").exists()
                checks.append("Keep, reject missing-RAW JPEG, exact-path undo")
                key(Qt.Key.Key_M)
            elif stage == 5:
                assert window.current.key == "img_0001" and window.mode == "edit"
                key(Qt.Key.Key_E)
            elif stage == 6:
                assert (shoot / EDIT / "img_0001.cR3").read_bytes() == (shoot / KEPT / "img_0001.cR3").read_bytes()
                key(Qt.Key.Key_E)
            elif stage == 7:
                assert not (shoot / EDIT / "IMG_0001.JPG").exists()
                key(Qt.Key.Key_Z)
            elif stage == 8:
                assert (shoot / EDIT / "IMG_0001.JPG").exists()
                checks.append("Edit copies, archive on unmark, undo unmark")
                window.session.close()
                window.session = None
                window.open_folder(shoot)
            elif stage == 9:
                assert window.mode == "edit" and "img_0001" in window.session.edits
                key(Qt.Key.Key_Z)  # Undo edit mark after reopening.
            elif stage == 10:
                assert not window.session.edits
                assert not (shoot / EDIT / "IMG_0001.JPG").exists()
                key(Qt.Key.Key_Z)  # Undo keep after reopening.
            elif stage == 11:
                assert (shoot / "IMG_0001.JPG").exists()
                assert (shoot / "img_0001.cR3").exists()
                assert not window.session.stack
                checks.append("Journal reopen and persistent undo stack")
                finish()
                return
            stage += 1
        except Exception as error:
            finish(error)

    # A smoke failure is written to result.json instead of opening a modal dialog.
    window._show_error = lambda error: finish(error)
    timer.timeout.connect(tick)
    timer.start()
    window._smoke_timer = timer
