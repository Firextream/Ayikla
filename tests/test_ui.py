import time
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QSize, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ayikla.core import EDIT, KEPT, REJECTED
from ayikla.images import read_image
from ayikla.ui import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def no_modal_errors(monkeypatch):
    def fail_visibly(window, error):
        window.last_error = error
        window.feedback.setText(str(error))
        window._update_enabled()
        print(f"UI ERROR: {error}", flush=True)
    monkeypatch.setattr(MainWindow, "_show_error", fail_visibly)


def wait_until(app, predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert predicate(), "Timed out waiting for UI/worker"
    app.processEvents()


def make_jpeg(folder: Path, name: str, raw=True):
    Image.new("RGB", (160, 100), (70, 130, 80)).save(folder / f"{name}.JPG")
    if raw:
        (folder / f"{name}.CR3").write_bytes(b"generated dummy raw")


@pytest.mark.parametrize("orientation,dimensions", [
    (1, (80, 40)), (2, (80, 40)), (3, (80, 40)), (4, (80, 40)),
    (5, (40, 80)), (6, (40, 80)), (7, (40, 80)), (8, (40, 80)),
])
def test_exif_orientation(app, tmp_path, orientation, dimensions):
    path = tmp_path / "rotated.JPG"
    image = Image.new("RGB", (80, 40), "red")
    for x in range(40, 80):
        for y in range(40):
            image.putpixel((x, y), (0, 0, 255))
    exif = Image.Exif()
    exif[274] = orientation
    image.save(path, exif=exif, quality=100, subsampling=0)
    decoded, error = read_image(path, QSize(200, 200))
    assert not error
    assert (decoded.width(), decoded.height()) == dimensions
    first = decoded.pixelColor(5, 5)
    assert (first.red() > first.blue()) == (orientation in (1, 4, 5, 6))


def test_complete_keyboard_flow_and_resume(app, shoot):
    for name, raw in (("IMG_1", True), ("IMG_2", False), ("IMG_3", True)):
        make_jpeg(shoot, name, raw)
    window = MainWindow()
    window.show()
    try:
        window.open_folder(shoot)
        wait_until(app, lambda: not window.busy)
        wait_until(app, lambda: not window.canvas.image.isNull())
        assert window.current.key == "img_1"
        QTest.keyClick(window, Qt.Key.Key_Space)
        assert window.current.key == "img_2"
        assert "yok" in window.raw_badge.text()
        QTest.keyClick(window, Qt.Key.Key_Up)
        QTest.keyClick(window, Qt.Key.Key_Return)
        wait_until(app, lambda: not window.busy)
        assert (shoot / KEPT / "IMG_1.CR3").exists()
        assert window.current.key == "img_2"
        QTest.keyClick(window, Qt.Key.Key_X)
        wait_until(app, lambda: not window.busy)
        assert (shoot / REJECTED / "IMG_2.JPG").exists()
        QTest.keyClick(window, Qt.Key.Key_Z)
        wait_until(app, lambda: not window.busy)
        assert (shoot / "IMG_2.JPG").exists()
        assert window.current.key == "img_2"
        QTest.keyClick(window, Qt.Key.Key_Down)
        assert window.current.key == "img_3"
        QTest.keyClick(window, Qt.Key.Key_Right)
        wait_until(app, lambda: not window.busy)
        QTest.keyClick(window, Qt.Key.Key_M)
        assert window.mode == "edit"
        assert window.current.key == "img_1"
        QTest.keyClick(window, Qt.Key.Key_E)
        wait_until(app, lambda: not window.busy)
        assert (shoot / EDIT / "IMG_1.CR3").exists()
        assert window.edit_badge.isVisible()
        QTest.keyClick(window, Qt.Key.Key_E)
        wait_until(app, lambda: not window.busy)
        assert not (shoot / EDIT / "IMG_1.CR3").exists()
        QTest.keyClick(window, Qt.Key.Key_Z)
        wait_until(app, lambda: not window.busy)
        assert (shoot / EDIT / "IMG_1.CR3").exists()
        QTest.keyClick(window, Qt.Key.Key_Space)
        assert window.current.key == "img_3"
    finally:
        window.close()
        app.processEvents()
    resumed = MainWindow()
    resumed.show()
    try:
        resumed.open_folder(shoot)
        wait_until(app, lambda: not resumed.busy)
        assert resumed.mode == "edit"
        assert resumed.current.key == "img_3"
        assert "img_1" in resumed.session.edits
        wait_until(app, lambda: not resumed.canvas.image.isNull())
        wait_until(app, lambda: not resumed.cache.inflight)
        assert 1 < len(resumed.cache.cache) <= 5  # Adjacent JPEG really preloaded.
    finally:
        resumed.close()
        app.processEvents()


def test_empty_folder_and_finished_round(app, shoot):
    window = MainWindow()
    window.show()
    try:
        window.open_folder(shoot)
        wait_until(app, lambda: not window.busy)
        assert window.current is None
        assert "bulunamadı" in window.canvas.message
        assert not window.keep_button.isEnabled()
        make_jpeg(shoot, "IMG_1")
        window.refresh()
        QTest.keyClick(window, Qt.Key.Key_Return)
        wait_until(app, lambda: not window.busy)
        assert window.current is None
        assert "tamamlandı" in window.canvas.message
        QTest.keyClick(window, Qt.Key.Key_Z)
        wait_until(app, lambda: not window.busy)
        assert window.current.key == "img_1"
    finally:
        window.close()
        app.processEvents()

