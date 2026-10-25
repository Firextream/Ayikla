"""Folder access and usable layouts at the supported minimum window size."""

import os
import time
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from ayikla.core import EDIT, KEPT, LOG, REJECTED
from ayikla.ui import MainWindow


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    # The offscreen plugin does not discover Windows fonts. Use the same actual
    # Segoe UI fonts as the packaged screenshot probe for meaningful geometry.
    for name in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
        QFontDatabase.addApplicationFont(str(Path(os.environ["WINDIR"]) / "Fonts" / name))
    return application


def wait(app, predicate):
    deadline = time.monotonic() + 10
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(5)
    assert predicate(), "UI operation did not finish"
    app.processEvents()


@pytest.fixture
def window(app, monkeypatch):
    def capture_error(window, error):
        window.last_error = error
        window._update_enabled()
    monkeypatch.setattr(MainWindow, "_show_error", capture_error)
    window = MainWindow()
    window.resize(1024, 680)
    window.show()
    app.processEvents()
    yield window
    wait(app, lambda: not window.busy)
    window.close()
    app.processEvents()


def open_photos(app, window, shoot, names=("IMG_0001", "IMG_0002")):
    for name in names:
        Image.new("RGB", (160, 100), "gray").save(shoot / f"{name}.JPG")
        (shoot / f"{name}.CR3").write_bytes(b"GENERATED RAW")
    window.open_folder(shoot)
    wait(app, lambda: not window.busy and not window.canvas.image.isNull())


def test_folder_menu_opens_only_managed_shoot_directories(app, window, shoot, monkeypatch):
    assert not window.folders_button.isEnabled()
    open_photos(app, window, shoot)
    window.decide(True)
    wait(app, lambda: not window.busy)
    window.decide(False)
    wait(app, lambda: not window.busy)
    window.set_mode("edit")
    window.toggle_edit()
    wait(app, lambda: not window.busy)
    assert all("(1)" in window.folder_actions[name].text() for name in (KEPT, EDIT, REJECTED))
    opened = []
    monkeypatch.setattr("ayikla.ui.QDesktopServices.openUrl",
                        lambda url: opened.append(Path(url.toLocalFile())) or True)
    before = (shoot / LOG).read_bytes()
    for name in ("", KEPT, EDIT, REJECTED):
        window.folder_actions[name].trigger()
    assert opened == [shoot, shoot / KEPT, shoot / EDIT, shoot / REJECTED]
    assert (shoot / LOG).read_bytes() == before
    window.open_shoot_folder("../outside")
    assert len(opened) == 4 and hasattr(window, "last_error")


def test_current_photo_folder_and_summary_links_follow_moved_files(app, window, shoot, monkeypatch):
    open_photos(app, window, shoot)
    opened = []
    monkeypatch.setattr("ayikla.ui.QDesktopServices.openUrl",
                        lambda url: opened.append(Path(url.toLocalFile())) or True)
    window.current_folder_button.click()
    assert opened[-1] == shoot
    window.decide(True)
    wait(app, lambda: not window.busy)
    window.decide(False)
    wait(app, lambda: not window.busy)
    window.kept_folder_button.click()
    window.rejected_folder_button.click()
    window.explorer_button.click()
    assert opened[-3:] == [shoot / KEPT, shoot / REJECTED, shoot / EDIT]
    window.jump_to("img_0001")
    window.current_folder_button.click()
    assert opened[-1] == shoot / KEPT
    window.jump_to("img_0002")
    window.current_folder_button.click()
    assert opened[-1] == shoot / REJECTED


def test_folder_open_failure_has_actionable_error(app, window, shoot, monkeypatch):
    open_photos(app, window, shoot)
    monkeypatch.setattr("ayikla.ui.QDesktopServices.openUrl", lambda url: False)
    window.folder_actions[KEPT].trigger()
    assert "Explorer açılamadı" in str(window.last_error)
    assert str(shoot / KEPT) in str(window.last_error)


@pytest.mark.parametrize("dimensions", [(1024, 680), (1440, 960)])
def test_gallery_controls_and_help_fit_supported_window_sizes(app, window, shoot, dimensions):
    window.resize(*dimensions)
    open_photos(app, window, shoot)
    controls = (window.filename, window.raw_badge, window.current_folder_button,
                window.zoom_button, window.info_button, window.strip_button)
    for first, second in zip(controls, controls[1:]):
        assert first.geometry().right() <= second.geometry().left()
    assert window.canvas.height() >= 300
    QTest.keyClick(window, Qt.Key.Key_H)
    help_panel = window.canvas.help
    assert help_panel.isVisible() and help_panel.parentWidget() is window.centralWidget()
    assert window.centralWidget().rect().contains(help_panel.geometry())
    QTest.keyClick(window, Qt.Key.Key_H)
    window.notify("Seçildi")
    window.toggle_filmstrip()
    app.processEvents()
    viewer_bounds = window.viewer.rect().translated(window.viewer.mapTo(window.centralWidget(), QPoint(0, 0)))
    assert viewer_bounds.contains(window.toast.geometry())


def test_long_filename_keeps_extension_visible_and_controls_accessible(app, window, shoot):
    name = "IMG_0001_" + "uzun_dosya_adi_" * 8
    open_photos(app, window, shoot, (name,))
    assert window.filename.text() == f"{name}.JPG"
    assert window.filename.toolTip() == f"{name}.JPG"
    assert QLabel.text(window.filename).endswith(".JPG")
    assert len(QLabel.text(window.filename)) < len(window.filename.text())
    assert window.strip_button.geometry().right() < window.photo_info.width()
    assert window.keep_button.isEnabled() and window.current_folder_button.isEnabled()


def test_help_on_welcome_keeps_start_screen_and_recent_folders_accessible(app, window, tmp_path):
    for index in range(5):
        folder = tmp_path / f"Recent {index}"
        folder.mkdir()
        window.preferences.add_recent(folder)
    window._update_recent()
    app.processEvents()
    assert window.recent_layout.count() == 6
    QTest.keyClick(window, Qt.Key.Key_H)
    assert window.pages.currentIndex() == 0 and window.canvas.help.isVisible()
    assert window.centralWidget().rect().contains(window.canvas.help.geometry())
    QTest.keyClick(window, Qt.Key.Key_H)
    last_button = window.recent_layout.itemAt(5).widget()
    window.pages.widget(0).ensureWidgetVisible(last_button)
    app.processEvents()
    viewport = window.pages.widget(0).viewport()
    assert viewport.rect().contains(last_button.mapTo(viewport, QPoint(0, 0)))


def test_summary_uses_scrollable_card_and_hides_inactive_photo_controls(app, window, shoot):
    open_photos(app, window, shoot, ("IMG_0001",))
    window.decide(True)
    wait(app, lambda: not window.busy)
    assert window.viewer.currentIndex() == 1
    assert window.end_card.width() <= 620 and window.end_card.isVisible()
    assert window.controls.isHidden() and window.photo_info.isHidden()
    card_bounds = window.end_card.rect().translated(window.end_card.mapTo(window.centralWidget(), QPoint(0, 0)))
    assert not card_bounds.intersects(window.toast.geometry())
    page = window.viewer.widget(1)
    page.ensureWidgetVisible(window.rejected_folder_button)
    app.processEvents()
    assert page.viewport().rect().contains(window.rejected_folder_button.mapTo(page.viewport(), QPoint(0, 0)))
    window.round2_button.click()
    assert window.controls.isVisible() and window.photo_info.isVisible()
