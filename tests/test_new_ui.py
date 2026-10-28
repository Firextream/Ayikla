import errno
import time
from pathlib import Path

import pytest
from PIL import Image, TiffImagePlugin
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ayikla.core import EDIT, KEPT, REJECTED
from ayikla.errors import error_message
from ayikla.ui import MainWindow, STYLE


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def wait(app, predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)  # Yield to Python workers while pumping Qt events.
    assert predicate(), "UI operation did not finish"
    app.processEvents()


@pytest.fixture
def window(app, monkeypatch):
    def capture_error(window, error):
        window.last_error = error
        window.feedback.setText(str(error))
        window._update_enabled()
    monkeypatch.setattr(MainWindow, "_show_error", capture_error)
    window = MainWindow()
    window.resize(1280, 860)
    window.show()
    app.processEvents()
    yield window
    wait(app, lambda: not window.busy)
    window.close()
    app.processEvents()


def photo(folder, index, second=0, raw=True):
    path = folder / f"IMG_{index:04d}.JPG"
    exif = Image.Exif()
    exif[34665] = {36867: f"2026:10:25 12:34:{second:02d}", 37521: f"{index * 100:03d}",
                   33434: TiffImagePlugin.IFDRational(1, 320),
                   33437: TiffImagePlugin.IFDRational(28, 10), 34855: 400,
                   37386: TiffImagePlugin.IFDRational(50), 42036: "Generated lens"}
    Image.new("RGB", (2400, 1600), (100, 100, 100)).save(path, exif=exif)
    if raw:
        path.with_suffix(".CR3").write_bytes(b"dummy raw")
    return path


def open_ready(app, window, folder):
    window.open_folder(folder)
    wait(app, lambda: not window.busy)
    assert not hasattr(window, "last_error")
    if window.current:
        wait(app, lambda: not window.canvas.image.isNull())


def test_zoom_full_resolution_pan_fit_and_navigation(app, window, shoot):
    photo(shoot, 1)
    photo(shoot, 2)
    open_ready(app, window, shoot)
    assert window.canvas.image.width() < 2400
    QTest.keyClick(window, Qt.Key.Key_F)
    wait(app, lambda: window.canvas.image.width() == 2400)
    assert window.canvas.zoomed and window.zoomed
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(400, 200), QPointF(400, 200),
                        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    move = QMouseEvent(QEvent.Type.MouseMove, QPointF(500, 280), QPointF(500, 280),
                       Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(window.canvas, press)
    QApplication.sendEvent(window.canvas, move)
    assert window.canvas.pan == QPointF(100, 80)
    QTest.keyClick(window, Qt.Key.Key_F)
    wait(app, lambda: not window.canvas.image.isNull())
    assert not window.zoomed and window.canvas.image.width() < 2400
    assert not any(key[5] for key in window.cache.cache)
    QTest.keyClick(window, Qt.Key.Key_F)
    wait(app, lambda: window.canvas.image.width() == 2400)
    QTest.keyClick(window, Qt.Key.Key_Space)
    wait(app, lambda: not window.canvas.image.isNull())
    assert not window.zoomed and window.current.key == "img_0002"


def test_info_burst_fading_help_and_toasts(app, window, shoot):
    photo(shoot, 1)
    photo(shoot, 2)
    photo(shoot, 3)
    open_ready(app, window, shoot)
    wait(app, lambda: len(window.metadata) == 3)
    QTest.keyClick(window, Qt.Key.Key_I)
    assert "1/320 s" in window.canvas.info.text()
    assert "Generated lens" in window.canvas.info.text()
    assert "Burst 1/3" in window.canvas.hud.text()
    QTest.qWait(1800)
    assert window.canvas.hud.effect.opacity() < .01
    assert window.canvas.info.effect.opacity() <= .26
    window._reveal_overlays()
    assert window.canvas.hud.effect.opacity() == 1
    QTest.keyClick(window, Qt.Key.Key_H)
    assert window.canvas.help.isVisible()
    assert "KEYBOARD" in window.canvas.help.text()
    QTest.keyClick(window, Qt.Key.Key_Escape)
    assert not window.canvas.help.isVisible()
    QTest.keyClick(window, Qt.Key.Key_Question)
    assert window.canvas.help.isVisible()
    QTest.keyClick(window, Qt.Key.Key_H)
    QTest.keyClick(window, Qt.Key.Key_Return)
    wait(app, lambda: not window.busy)
    assert window.toast.text() == "Kept" and window.toast.isVisible()
    QTest.qWait(1800)
    assert window.toast.effect.opacity() < .01
    QTest.keyClick(window, Qt.Key.Key_Z)
    wait(app, lambda: not window.busy)
    assert window.toast.text() == "Undone"


def test_filmstrip_colors_thumbnails_click_all_states(app, window, shoot):
    for index in range(1, 5):
        photo(shoot, index)
    open_ready(app, window, shoot)
    window.decide(True)
    wait(app, lambda: not window.busy)
    window.decide(False)
    wait(app, lambda: not window.busy)
    QTest.keyClick(window, Qt.Key.Key_T)
    assert window.filmstrip.isVisible()
    wait(app, lambda: bool(window.filmstrip.cache.cache))
    items = window.filmstrip.items
    assert items[0].state == "kept" and items[1].state == "rejected"
    assert window.filmstrip.edge_color(items[0]) != window.filmstrip.edge_color(items[1])
    assert all(image.width() <= 116 and image.height() <= 74 for image, _ in window.filmstrip.cache.cache.values())
    QTest.mouseClick(window.filmstrip.viewport(), Qt.MouseButton.LeftButton,
                     pos=QPoint(30, 30))
    assert window.current.key == "img_0001" and window.mode == "edit"
    window.toggle_edit()
    wait(app, lambda: not window.busy)
    assert window.filmstrip.edge_color(window.filmstrip.items[0]) == QColor("#b1a0d0")
    window.jump_to("img_0002")
    assert window.current.key == "img_0002" and window.preview_photo is not None
    assert not window.reject_button.isEnabled() and not window.keep_button.isEnabled()
    before = (shoot / REJECTED / "IMG_0002.JPG").read_bytes()
    window.decide(True)
    assert (shoot / REJECTED / "IMG_0002.JPG").read_bytes() == before
    window.navigate(1)
    assert window.current.key == "img_0003" and window.preview_photo is None
    QTest.keyClick(window, Qt.Key.Key_T)
    assert not window.filmstrip.isVisible()


def test_end_screen_counts_round_two_explorer_and_final_toast(app, window, shoot, monkeypatch):
    photo(shoot, 1)
    open_ready(app, window, shoot)
    window.decide(True)
    wait(app, lambda: not window.busy)
    assert window.viewer.currentIndex() == 1
    assert "1 kept" in window.end_counts.text()
    assert window.toast.text() == "Kept" and window.toast.isVisible()
    urls = []
    monkeypatch.setattr("ayikla.ui.QDesktopServices.openUrl", lambda url: urls.append(url.toLocalFile()) or True)
    window.explorer_button.click()
    assert [Path(path) for path in urls] == [shoot / EDIT] and (shoot / EDIT).is_dir()
    window.round2_button.click()
    assert window.mode == "edit" and window.current.key == "img_0001"
    window.toggle_edit()
    wait(app, lambda: not window.busy)
    assert window.toast.text() == "Picked for editing"
    window.navigate(1)
    assert window.viewer.currentIndex() == 1 and "1 picked for editing" in window.end_counts.text()
    assert window.filename.text() == "Round 2 summary"
    window.return_to_photos()
    assert window.current.key == "img_0001"


def test_recent_buttons_window_restore_and_start_help(app, window, shoot):
    QTest.keyClick(window, Qt.Key.Key_H)
    assert window.canvas.help.isVisible()
    QTest.keyClick(window, Qt.Key.Key_H)
    assert window.pages.currentIndex() == 0
    photo(shoot, 1)
    open_ready(app, window, shoot)
    assert window.preferences.recent[0] == str(shoot)
    window.resize(1200, 780)
    window.move(30, 40)
    window.close()
    app.processEvents()
    restored = MainWindow()
    try:
        restored.show_saved_state()
        app.processEvents()
        assert not restored.isFullScreen()
        assert restored.size().width() == 1200 and restored.size().height() == 780
        assert restored.recent_layout.count() == 2
        restored.recent_layout.itemAt(1).widget().click()
        wait(app, lambda: not restored.busy)
        assert restored.session.root == shoot
        restored.showFullScreen()
        app.processEvents()
        restored.close()
        app.processEvents()
        fullscreen = MainWindow()
        fullscreen.show_saved_state()
        app.processEvents()
        assert fullscreen.isFullScreen()
        fullscreen.close()
    finally:
        restored.close()
        app.processEvents()


def test_retry_rescans_external_files_and_info(app, window, shoot):
    photo(shoot, 1)
    open_ready(app, window, shoot)
    photo(shoot, 2)
    assert len(window.session.snapshot().pending) == 1
    window.retry()
    wait(app, lambda: not window.busy)
    assert len(window.photos) == 2
    wait(app, lambda: len(window.metadata) == 2)


@pytest.mark.parametrize("error,fragment", [
    (FileNotFoundError("English text"), "disk connection"),
    (FileExistsError("English text"), "nothing overwritten"),
    (PermissionError("English text"), "write permission"),
    (OSError(errno.ENOSPC, "English text"), "free disk space"),
])
def test_actionable_turkish_errors(error, fragment):
    assert fragment in error_message(error)
    assert "Retry" in error_message(error)


def test_neutral_interface():
    assert "background: #1a1a1a" in STYLE
    assert "#c4f19b" not in STYLE


def test_burst_compare_confirms_returns_to_keeper_and_group_undo(app, window, shoot):
    for index in range(1, 7):
        photo(shoot, index)
    open_ready(app, window, shoot)
    wait(app, lambda: len(window.metadata) == 6)
    QTest.keyClick(window, Qt.Key.Key_B)
    dialog = window.compare
    assert dialog and dialog.page_size == 4
    QTest.keyClick(dialog, Qt.Key.Key_Right)
    QTest.keyClick(dialog, Qt.Key.Key_2)
    assert dialog.selected == "img_0006"
    assert not window.session.stack  # Selecting alone never acts.
    QTest.keyClick(dialog, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    wait(app, lambda: not window.busy)
    assert not hasattr(window, "last_error")
    assert len(window.session.snapshot().rejected) == 5
    assert len(window.session.stack) == 1
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert window.compare is None and window.current.key == "img_0006"
    QTest.keyClick(window, Qt.Key.Key_Z)
    wait(app, lambda: not window.busy)
    assert len(window.session.snapshot().pending) == 6
    assert not list(shoot.glob("*.xmp"))
