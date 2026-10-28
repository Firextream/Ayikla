"""Reproducible Windows DPI screenshots using generated photos only."""

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def capture(output, scale, check=False):
    os.environ["QT_SCALE_FACTOR"] = str(scale)
    os.environ["QT_QPA_PLATFORM"] = "windows"
    fixture = ROOT / ".tmp" / f"polish-{uuid.uuid4().hex[:12]}"
    fixture.mkdir(parents=True)
    os.environ["AYIKLA_STATE_DIR"] = str(fixture / "state")
    from PIL import Image, TiffImagePlugin
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QFontDatabase, QImage, QLinearGradient, QPainter, QPolygonF
    from PySide6.QtWidgets import QApplication
    from ayikla.ui import MainWindow
    from ayikla import __version__

    app = QApplication.instance() or QApplication([])
    for name in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
        QFontDatabase.addApplicationFont(str(Path(os.environ["WINDIR"]) / "Fonts" / name))
    window = MainWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    physical = (1440, 960) if scale <= 1.25 else (1920, 1080)
    window.resize(round(physical[0] / scale), round(physical[1] / scale))
    window.show()
    errors = []
    window._show_error = errors.append
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    report = {"version": __version__, "backend": "windows", "scale": scale, "screens": {}}

    def wait(predicate):
        end = time.monotonic() + 15
        while not predicate() and not errors and time.monotonic() < end:
            app.processEvents()
            time.sleep(.005)
        app.processEvents()
        assert not errors, str(errors)
        assert predicate(), "Screenshot fixture did not become ready"

    def snap(name, widget=window):
        app.processEvents()
        target = output / f"{name}.png"
        if target.exists():
            raise FileExistsError(target)
        pixmap = widget.grab()
        assert pixmap.save(str(target))
        report["screens"][name] = {"logical": [widget.width(), widget.height()],
                                   "pixels": [pixmap.width(), pixmap.height()],
                                   "dpr": pixmap.devicePixelRatio(), "photo_height": window.canvas.height()}
        if check:
            from scripts.polish_checks import check_start, check_gallery, check_compare, check_summary
            validator = {"start": check_start, "round1": check_gallery, "round2": check_gallery,
                         "burst": check_compare, "summary": check_summary}[name]
            report["screens"][name]["checks"] = validator(widget)

    try:
        snap("start")
        shoot = fixture / "Autumn walk"
        shoot.mkdir()
        for i in range(4):
            image = QImage(1800, 1200, QImage.Format.Format_RGB32)
            painter = QPainter(image)
            gradient = QLinearGradient(0, 0, 0, 1200)
            gradient.setColorAt(0, QColor("#517b91"))
            gradient.setColorAt(1, QColor("#d2c4a3"))
            painter.fillRect(image.rect(), gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#dfd2aa"))
            painter.drawEllipse(1300 + i * 10, 180, 130, 130)
            painter.setBrush(QColor("#3f6458"))
            painter.drawPolygon(QPolygonF([QPointF(0, 1000), QPointF(550 + i * 10, 430), QPointF(1800, 1100),
                                          QPointF(1800, 1200), QPointF(0, 1200)]))
            painter.setBrush(QColor("#233e32"))
            painter.drawPolygon(QPolygonF([QPointF(0, 1130), QPointF(1100, 750), QPointF(1800, 1000),
                                          QPointF(1800, 1200), QPointF(0, 1200)]))
            painter.end()
            path = shoot / f"IMG_{i + 1:04d}.JPG"
            image.save(str(path), "JPEG", 94)
            with Image.open(path) as source:
                exif = Image.Exif()
                exif[34665] = {36867: "2026:10:29 12:34:56", 37521: str(i * 100),
                               33434: TiffImagePlugin.IFDRational(1, 320),
                               33437: TiffImagePlugin.IFDRational(28, 10), 34855: 400}
                source.save(path, exif=exif)
            path.with_suffix(".CR3").write_bytes(b"GENERATED RAW DATA")
        (shoot / "._IMG_0001.JPG").write_bytes(b"GENERATED HELPER")
        window.open_folder(shoot)
        wait(lambda: not window.busy and not window.canvas.image.isNull() and len(window.metadata) == 4)
        snap("round1")
        window.open_compare()
        dialog = window.compare
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        wait(lambda: all(not pane.image.isNull() for pane in dialog.panes))
        snap("burst", dialog)
        dialog.reject()
        for keep in (True, True, True, False):
            window.decide(keep)
            wait(lambda: not window.busy)
        window.set_mode("edit")
        wait(lambda: not window.canvas.image.isNull())
        window.toggle_edit()
        wait(lambda: not window.busy and not window.canvas.image.isNull())
        snap("round2")
        window.show_summary()
        wait(lambda: not window.busy)
        snap("summary")
        (output / "capture.json").write_text(json.dumps(report, indent=2), "utf-8")
    finally:
        if window.compare:
            window.compare.reject()
        wait(lambda: not window.busy)
        window.close()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--scale", type=float, default=1)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    capture(args.output, args.scale, args.check)
