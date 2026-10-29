"""1.6 review: navigation buttons, the arrow-key choice, click zones and the Reject notice."""

import time

import pytest
from PIL import Image
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ayikla.core import KEPT, REJECTED
from ayikla.preferences import Preferences
from ayikla.ui import MainWindow
from scripts.polish_checks import contrast, row_span


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def wait(app, predicate, seconds=10):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    assert predicate(), "UI operation did not finish"
    app.processEvents()


def make_window(app, monkeypatch):
    def capture_error(window, error):
        window.last_error = error
        window.feedback.setText(str(error))
        window._update_enabled()
    monkeypatch.setattr(MainWindow, "_show_error", capture_error)
    window = MainWindow()
    window.resize(1280, 860)
    window.show()
    app.processEvents()
    return window


@pytest.fixture
def window(app, monkeypatch):
    window = make_window(app, monkeypatch)
    yield window
    wait(app, lambda: not window.busy)
    window.close()
    app.processEvents()


def photos(folder, count):
    for index in range(1, count + 1):
        Image.new("RGB", (1200, 800), (60 + index * 20, 90, 110)).save(folder / f"IMG_{index:04d}.JPG")
        (folder / f"IMG_{index:04d}.CR3").write_bytes(b"dummy raw")


def open_ready(app, window, folder):
    window.open_folder(folder)
    wait(app, lambda: not window.busy and window.session is not None)
    assert not hasattr(window, "last_error")
    if window.current:
        wait(app, lambda: not window.canvas.image.isNull())


def press(app, window, key):
    QTest.keyClick(window, key)
    wait(app, lambda: not window.busy)


def name(window):
    return window.current.jpeg.name if window.current else None


def click(app, widget, x, y, double=False):
    point = QPointF(x, y)
    kinds = [QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease]
    if double:
        kinds += [QEvent.Type.MouseButtonDblClick, QEvent.Type.MouseButtonRelease]
    for kind in kinds:
        buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
        QApplication.sendEvent(widget, QMouseEvent(kind, point, point, Qt.MouseButton.LeftButton, buttons,
                                                   Qt.KeyboardModifier.NoModifier))
    app.processEvents()


# ── A1 buttons ────────────────────────────────────────────────────────────────

def test_undo_previous_next_are_real_buttons_in_the_decision_row(app, window, shoot):
    photos(shoot, 3)
    open_ready(app, window, shoot)
    row = window.controls
    for control in (window.undo_button, window.previous_button, window.next_button):
        assert row.isAncestorOf(control) and control.isVisible()
        assert control.height() == window.keep_button.height() == window.reject_button.height()
    assert window.undo_button.text() == "Undo  ·  Z"
    assert (window.previous_button.text(), window.next_button.text()) == ("↑  Previous", "Next  ↓")
    order = [window.undo_button, window.photo_info, window.previous_button, window.next_button,
             window.reject_button, window.keep_button]
    for first, second in zip(order, order[1:]):
        assert row_span(window, first)[1] < row_span(window, second)[0]
    # with room (full screen) the navigation pair sits in the middle of the row; narrower, it
    # follows the file info and nothing overlaps (checked above)
    window.resize(1900, 900)
    wait(app, lambda: row.width() > 1800)
    middle = (row_span(window, window.previous_button)[0] + row_span(window, window.next_button)[1]) / 2
    assert abs(middle - row.width() / 2) <= 2
    window.resize(1280, 860)
    app.processEvents()
    # first photo, nothing to undo: both disabled and still readable
    assert not window.previous_button.isEnabled() and not window.undo_button.isEnabled()
    for control in (window.previous_button, window.undo_button):
        palette = control.palette()
        ratio = contrast(palette.color(palette.ColorGroup.Disabled, palette.ColorRole.ButtonText),
                         palette.color(palette.ColorGroup.Disabled, palette.ColorRole.Button))
        assert ratio >= 3, (control.text(), ratio)
    window.next_button.click()
    wait(app, lambda: not window.busy)
    assert name(window) == "IMG_0002.JPG" and window.previous_button.isEnabled()
    window.previous_button.click()
    assert name(window) == "IMG_0001.JPG"
    window.decide(True)
    wait(app, lambda: not window.busy)
    assert window.undo_button.isEnabled()
    window.undo_button.click()
    wait(app, lambda: not window.busy)
    assert not (shoot / KEPT / "IMG_0001.JPG").exists() and name(window) == "IMG_0001.JPG"


# ── A2 arrow keys ─────────────────────────────────────────────────────────────

def test_first_launch_asks_for_the_arrow_keys_and_remembers_the_choice(app, monkeypatch, tmp_path):
    state = tmp_path / "first-launch"
    monkeypatch.setenv("AYIKLA_STATE_DIR", str(state))
    window = make_window(app, monkeypatch)
    try:
        assert window.pages.currentWidget() is window.arrow_page
        assert set(window.arrow_cards) == {"fast", "browse"}
        assert window.arrow_mode == "fast"  # the default, before choosing
        QTest.keyClick(window, Qt.Key.Key_2)
        assert window.pages.currentIndex() == 0 and window.arrow_mode == "browse"
        assert window.arrow_actions["browse"].isChecked() and not window.arrow_actions["fast"].isChecked()
        assert window.toast.text() == "Arrow keys · Browse first"
    finally:
        window.close()
    assert Preferences(state).arrow_keys == "browse"
    again = make_window(app, monkeypatch)
    try:
        assert again.pages.currentIndex() == 0 and again.arrow_mode == "browse"
        assert (again.previous_button.text(), again.next_button.text()) == ("←  Previous", "Next  →")
        assert again.keep_button.text() == "Keep  ·  Enter"
    finally:
        again.close()


def test_enter_on_the_chooser_takes_fast_culling(app, monkeypatch, tmp_path):
    monkeypatch.setenv("AYIKLA_STATE_DIR", str(tmp_path / "empty"))
    window = make_window(app, monkeypatch)
    try:
        QTest.keyClick(window, Qt.Key.Key_Return)
        assert window.pages.currentIndex() == 0
        assert Preferences(tmp_path / "empty").arrow_keys == "fast"
    finally:
        window.close()


def test_fast_culling_map(app, window, shoot):
    photos(shoot, 5)
    open_ready(app, window, shoot)
    press(app, window, Qt.Key.Key_Down)
    press(app, window, Qt.Key.Key_PageDown)
    assert name(window) == "IMG_0003.JPG"
    press(app, window, Qt.Key.Key_Backspace)
    assert name(window) == "IMG_0002.JPG"
    press(app, window, Qt.Key.Key_PageUp)
    press(app, window, Qt.Key.Key_Up)
    assert name(window) == "IMG_0001.JPG"
    press(app, window, Qt.Key.Key_Right)
    assert (shoot / KEPT / "IMG_0001.JPG").exists()
    press(app, window, Qt.Key.Key_Left)
    assert (shoot / REJECTED / "IMG_0002.JPG").exists()


def test_browse_first_map(app, window, shoot):
    photos(shoot, 4)
    window.set_arrow_mode("browse")
    open_ready(app, window, shoot)
    press(app, window, Qt.Key.Key_Right)
    press(app, window, Qt.Key.Key_Right)
    assert name(window) == "IMG_0003.JPG"
    press(app, window, Qt.Key.Key_Left)
    assert name(window) == "IMG_0002.JPG"
    assert not any((shoot / folder).exists() for folder in (KEPT, REJECTED))  # arrows never decide here
    press(app, window, Qt.Key.Key_Return)
    assert (shoot / KEPT / "IMG_0002.JPG").exists()
    press(app, window, Qt.Key.Key_X)
    assert (shoot / REJECTED / "IMG_0003.JPG").exists()
    press(app, window, Qt.Key.Key_Delete)
    assert (shoot / REJECTED / "IMG_0004.JPG").exists()
    press(app, window, Qt.Key.Key_Backspace)  # Backspace = Previous, never a delete
    assert len(list((shoot / REJECTED).glob("*.JPG"))) == 2


def test_settings_switches_the_map_and_help_shows_it(app, window, shoot):
    photos(shoot, 2)
    open_ready(app, window, shoot)
    QTest.keyClick(window, Qt.Key.Key_H)
    assert "Arrow keys: Fast culling" in window.canvas.help.text()
    assert "→ / Enter   Keep" in window.canvas.help.text()
    for title in ("ROUND 1", "ROUND 2", "ANYWHERE"):
        assert title in window.canvas.help.text()
    window.arrow_actions["browse"].trigger()
    assert window.arrow_mode == "browse" and "Arrow keys: Browse first" in window.canvas.help.text()
    assert "Enter   Keep" in window.canvas.help.text() and "← / Backspace / PageUp   Previous" in window.canvas.help.text()
    assert window.pages.currentIndex() == 1  # switching keeps the shoot on screen


def test_every_reject_shows_a_three_second_notice(app, window, shoot):
    photos(shoot, 2)
    open_ready(app, window, shoot)
    press(app, window, Qt.Key.Key_Delete)
    assert window.toast.text() == "Rejected IMG_0001 · Z to undo" and window.toast.isVisible()
    assert window.toast.timer.interval() == 3000
    press(app, window, Qt.Key.Key_Right)
    assert window.toast.text() == "Kept" and window.toast.timer.interval() == 1500


# ── A3 click zones ────────────────────────────────────────────────────────────

def test_photo_thirds_step_and_double_click_zooms(app, window, shoot):
    photos(shoot, 3)
    open_ready(app, window, shoot)
    canvas = window.canvas
    photo = canvas.image_rect()
    y = photo.center().y()
    left, middle, right = photo.left() + photo.width() / 6, photo.center().x(), photo.right() - photo.width() / 6
    QTest.mouseMove(canvas, photo.center().toPoint())
    assert canvas.cursor().shape() == Qt.CursorShape.ArrowCursor
    QTest.mouseMove(canvas, QPointF(right, y).toPoint())
    assert canvas.cursor().shape() == Qt.CursorShape.PointingHandCursor and canvas._hover == 1
    click(app, canvas, right, y)
    wait(app, lambda: not window.busy and not canvas.image.isNull())
    assert name(window) == "IMG_0002.JPG"
    click(app, canvas, middle, y)
    assert name(window) == "IMG_0002.JPG" and not window.zoomed
    click(app, canvas, left, y)
    wait(app, lambda: not canvas.image.isNull())
    assert name(window) == "IMG_0001.JPG"
    click(app, canvas, left, y)  # first photo: nothing before it
    assert name(window) == "IMG_0001.JPG"
    click(app, canvas, middle, y, double=True)
    assert window.zoomed
    wait(app, lambda: not canvas.image.isNull())
    zoomed = canvas.image_rect()
    click(app, canvas, zoomed.right() - 10 if zoomed.right() < canvas.width() else canvas.width() - 20, y)
    assert name(window) == "IMG_0001.JPG"  # while zoomed a click only pans
    click(app, canvas, 30, y, double=True)  # zoomed: double-click anywhere returns to fit
    assert not window.zoomed
