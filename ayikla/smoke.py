"""Developer-only packaged-app verification and screenshots, generated files only."""

import json
import os
import struct
import time
import uuid
from pathlib import Path

from PIL import Image, TiffImagePlugin
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QFontDatabase, QImage, QKeyEvent, QLinearGradient, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QApplication

from .core import EDIT, KEPT, REJECTED
from . import __version__


def run_smoke(app, window, output: str) -> None:
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        font_root = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for name in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
            QFontDatabase.addApplicationFont(str(font_root / name))
    assert window.isFullScreen()
    assert __version__ in window.windowTitle()
    window.showNormal()
    window.resize(1440, 960)
    directory = Path(output).resolve() / f"smoke-{uuid.uuid4().hex[:12]}"
    directory.mkdir(parents=True, exist_ok=False)
    shoot = directory / "Sample shoot"
    shoot.mkdir()
    for index in range(1, 5):
        image = QImage(6000, 4000, QImage.Format.Format_RGB32)
        painter = QPainter(image)
        painter.scale(2, 2)
        gradient = QLinearGradient(0, 0, 0, 2000)
        gradient.setColorAt(0, QColor("#517b91"))
        gradient.setColorAt(.7, QColor("#d2c4a3"))
        gradient.setColorAt(1, QColor("#6d815b"))
        painter.fillRect(0, 0, 3000, 2000, gradient)
        painter.setBrush(QColor("#dfd2aa"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2050 + index * 12, 330, 210, 210)
        painter.setBrush(QColor("#3f6458"))
        painter.drawPolygon(QPolygonF([QPointF(0, 1500), QPointF(750, 700),
                                      QPointF(1800, 1600), QPointF(3000, 950),
                                      QPointF(3000, 2000), QPointF(0, 2000)]))
        painter.setPen(QPen(QColor("#344f47"), .6))
        for x in range(1100, 1900, 4):
            painter.drawLine(x, 1050, x + 80, 1450)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#233e32"))
        painter.drawPolygon(QPolygonF([QPointF(0, 1800), QPointF(1600, 1350),
                                      QPointF(3000, 1950), QPointF(3000, 2000), QPointF(0, 2000)]))
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "JPEG", 94):
            raise OSError("Could not generate the test JPEG.")
        buffer.close()
        exif = Image.Exif()
        exif[34665] = {36867: "2026:10:25 10:12:30", 37521: f"{index * 180:03d}",
                       33434: TiffImagePlugin.IFDRational(1, 320),
                       33437: TiffImagePlugin.IFDRational(28, 10), 34855: 400,
                       37386: TiffImagePlugin.IFDRational(50), 42036: "Yapay test lensi 50mm"}
        payload, jpeg = exif.tobytes(), bytes(data)
        with (shoot / f"IMG_{index:04d}.JPG").open("xb") as stream:
            stream.write(jpeg[:2] + b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload + jpeg[2:])
        if index != 2:
            with (shoot / f"img_{index:04d}.cR3").open("xb") as stream:
                stream.write(b"GENERATED RAW TEST DATA " * 1000)
    del image, data
    helpers = {f"._IMG_{index:04d}.{extension}": b"GENERATED APPLEDOUBLE METADATA"
               for index in range(1, 5) for extension in ("JPG", "CR3")}
    helpers.update({name: b"GENERATED METADATA" for name in ("Thumbs.db", "desktop.ini", ".DS_Store")})
    for name, payload in helpers.items():
        with (shoot / name).open("xb") as stream:
            stream.write(payload)
    window.grab().save(str(directory / "welcome.png"))
    started, stage, finished = time.monotonic(), 0, False
    checks = []
    timer = QTimer(window)
    timer.setInterval(30)

    def key(value):
        QApplication.sendEvent(window, QKeyEvent(QKeyEvent.Type.KeyPress, value,
                                                 Qt.KeyboardModifier.NoModifier))

    def screenshot(name):
        app.processEvents()
        if not window.grab().save(str(directory / f"{name}.png")):
            raise OSError("Screenshot could not be saved")

    def finish(error=None):
        nonlocal finished
        if finished:
            return
        finished = True
        timer.stop()
        result = {"ok": error is None,
                  "error": f"Stage {stage}: {type(error).__name__}: {error}" if error else None,
                  "version": __version__,
                  "checks": checks, "elapsed_seconds": round(time.monotonic() - started, 2),
                  "directory": str(directory)}
        with (directory / "result.json").open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        if window.session:
            window.session.close()
            window.session = None
        window.close()
        app.exit(1 if error else 0)

    def tick():
        nonlocal stage
        try:
            if finished:
                return
            if time.monotonic() - started > 45:
                raise TimeoutError(f"Packaged UI stage {stage}: {window.feedback.text()}")
            if window.busy:
                return
            if stage == 0:
                window.open_folder(shoot)
            elif stage == 1:
                assert window.session and window.current.key == "img_0001"
                assert window.session.snapshot().total == 4
                assert window.session.ignored_files == {"appledouble": 8, "metadata": 3}
                assert "KEEP OR REJECT" in window.round_hint.text() and "01_secilen" in window.round_hint.text()
                assert "8 macOS helper files (._) ignored" in window.ignored_notice.text()
                if window.canvas.image.isNull():
                    return
                screenshot("gallery")
                checks.append("24 MP scaled JPEG, neutral gallery, RAW pairing and fullscreen startup")
                key(Qt.Key.Key_F)
            elif stage == 2:
                if window.canvas.image.width() != 6000:
                    return
                assert window.zoomed
                window.canvas.pan = QPointF(120, 80)
                screenshot("zoom")
                key(Qt.Key.Key_F)
            elif stage == 3:
                if window.canvas.image.isNull() or len(window.metadata) != 4:
                    return
                assert not window.zoomed and window.canvas.image.width() < 6000
                key(Qt.Key.Key_I)
                assert "1/320 s" in window.canvas.info.text() and "Burst 1/4" in window.canvas.hud.text()
                screenshot("info")
                key(Qt.Key.Key_I)
                key(Qt.Key.Key_T)
            elif stage == 4:
                if window.filmstrip.cache.inflight or not window.filmstrip.cache.cache:
                    return
                key(Qt.Key.Key_T)
                key(Qt.Key.Key_H)
                assert window.canvas.help.isVisible()
                assert window.centralWidget().rect().contains(window.canvas.help.geometry())
                screenshot("help")
                key(Qt.Key.Key_H)
                checks.append("100% zoom/pan/fit, EXIF, burst hint, filmstrip, keyboard help")
                key(Qt.Key.Key_Return)
            elif stage == 5:
                assert (shoot / KEPT / "img_0001.cR3").exists()
                assert window.current.key == "img_0002" and "No matching CR3" in window.raw_badge.text()
                assert window.toast.text() == "Kept"
                key(Qt.Key.Key_Delete)
            elif stage == 6:
                assert (shoot / REJECTED / "IMG_0002.JPG").exists()
                key(Qt.Key.Key_Z)
            elif stage == 7:
                assert (shoot / "IMG_0002.JPG").exists()
                checks.append("Keep, reject missing RAW, exact-path undo and action toasts")
                key(Qt.Key.Key_M)
            elif stage == 8:
                assert window.current.key == "img_0001" and window.mode == "edit"
                assert "LIGHTROOM" in window.round_hint.text() and "02_edit" in window.round_hint.text()
                key(Qt.Key.Key_E)
            elif stage == 9:
                assert (shoot / EDIT / "img_0001.cR3").read_bytes() == (shoot / KEPT / "img_0001.cR3").read_bytes()
                key(Qt.Key.Key_E)
            elif stage == 10:
                assert not (shoot / EDIT / "IMG_0001.JPG").exists()
                key(Qt.Key.Key_Z)
            elif stage == 11:
                assert (shoot / EDIT / "IMG_0001.JPG").exists()
                checks.append("Edit copies, archive without deletion, undo unmark")
                window.session.close()
                window.session = None
                window.open_folder(shoot)
            elif stage == 12:
                assert window.mode == "edit" and "img_0001" in window.session.edits
                key(Qt.Key.Key_Z)
            elif stage == 13:
                assert not window.session.edits
                assert not (shoot / EDIT / "IMG_0001.JPG").exists()
                key(Qt.Key.Key_Z)
            elif stage == 14:
                assert (shoot / "IMG_0001.JPG").exists() and not window.session.stack
                assert window.preferences.recent[0] == str(shoot)
                checks.append("Journal reopen, persistent undo and recent folder")
                window.decide(True)
            elif 15 <= stage <= 17:
                window.decide(stage != 16)
            elif stage == 18:
                assert window.viewer.currentIndex() == 1
                assert "3 kept" in window.end_counts.text() and "1 rejected" in window.end_counts.text()
                window.round2_button.click()
                assert window.mode == "edit" and window.current is not None
                key(Qt.Key.Key_E)
            elif stage == 19:
                assert len(window.session.edits) == 1
                key(Qt.Key.Key_T)
            elif stage == 20:
                if window.filmstrip.cache.inflight:
                    return
                screenshot("filmstrip")
                assert {photo.state for photo in window.filmstrip.items} == {"kept", "rejected"}
                assert "(3)" in window.folder_actions[KEPT].text()
                assert "(1)" in window.folder_actions[EDIT].text()
                assert "(1)" in window.folder_actions[REJECTED].text()
                window.folder_menu.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
                window.folder_menu.popup(window.folders_button.mapToGlobal(window.folders_button.rect().bottomLeft()))
                app.processEvents()
                assert window.folder_menu.grab().save(str(directory / "folders.png"))
                window.folder_menu.hide()
                checks.append("Polished layout, contained help and shoot-folder menu with live counts")
                key(Qt.Key.Key_T)
                window.show_summary()
            elif stage == 21:
                assert "1 picked for editing" in window.end_counts.text()
                screenshot("end")
                assert window.controls.isHidden() and window.photo_info.isHidden()
                checks.append("End screen with kept/rejected/edit counts and round-two action")
                for extension in ("JPG", "CR3"):
                    with (shoot / f"CORRUPT.{extension}").open("xb") as stream:
                        stream.write(b"GENERATED CORRUPT PHOTO TEST")
                window.set_mode("cull")
                window.retry()
            elif stage == 22:
                if "Could not open JPEG" not in window.canvas.message:
                    return
                assert window.current.key == "corrupt" and window.current.raw is not None
                assert window.keep_button.isEnabled() and window.reject_button.isEnabled()
                screenshot("corrupt")
                key(Qt.Key.Key_X)
            elif stage == 23:
                assert window.viewer.currentIndex() == 1
                assert "_red/CORRUPT.JPG" in window.end_errors.toPlainText()
                screenshot("corrupt-summary")
                key(Qt.Key.Key_Z)
            elif stage == 24:
                assert (shoot / "CORRUPT.JPG").read_bytes() == b"GENERATED CORRUPT PHOTO TEST"
                key(Qt.Key.Key_Return)
            elif stage == 25:
                assert "01_secilen/CORRUPT.JPG" in window.end_errors.toPlainText()
                assert all((shoot / name).read_bytes() == payload for name, payload in helpers.items())
                assert not any(photo.key.startswith("._") for photo in window.session.all_photos())
                checks.append("AppleDouble/metadata ignored; corrupt JPEG reject, undo, keep and summary")
                checks.append("Delete rejects without deletion; keep versus edit round labels are explicit")
                finish()
                return
            stage += 1
        except Exception as error:
            finish(error)

    window._show_error = lambda error: finish(error)
    timer.timeout.connect(tick)
    timer.start()
    window._smoke_timer = timer
