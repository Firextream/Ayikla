import os
import threading
import time
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from ayikla import images
from ayikla.compare import BurstCompare
from ayikla.ui import MainWindow
from scripts.polish_checks import check_start, check_gallery, check_compare


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    for name in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
        QFontDatabase.addApplicationFont(str(Path(os.environ["WINDIR"]) / "Fonts" / name))
    return app


def wait(app, predicate):
    end = time.monotonic() + 10
    while not predicate() and time.monotonic() < end:
        app.processEvents()
        time.sleep(.005)
    app.processEvents()
    assert predicate()


@pytest.fixture
def window(app, monkeypatch):
    window = MainWindow()
    errors = []
    monkeypatch.setattr(window, "_show_error", errors.append)
    window.show()
    yield window
    wait(app, lambda: not window.busy)
    window.close()
    assert not errors, errors


@pytest.mark.parametrize("size", [(1024, 680), (1152, 768), (1440, 960)])
def test_start_text_bottom_row_single_progress_and_contrast(app, window, shoot, size):
    window.resize(*size)
    app.processEvents()
    check_start(window)
    Image.new("RGB", (1200, 800), "gray").save(shoot / "photo.JPG")
    (shoot / "photo.CR3").write_bytes(b"generated RAW")
    (shoot / "._photo.JPG").write_bytes(b"generated helper")
    window.open_folder(shoot)
    wait(app, lambda: not window.busy and not window.canvas.image.isNull())
    check_gallery(window)
    assert "1 macOS helper" in window.ignored_action.text()
    assert window.ignored_action.isVisible() and not window.ignored_action.isEnabled()
    window.decide(True)
    wait(app, lambda: not window.busy)
    window.set_mode("edit")
    wait(app, lambda: not window.canvas.image.isNull())
    check_gallery(window)


def test_compare_border_badges_and_controls_fit_at_minimum(app, window, shoot):
    for i in range(4):
        Image.new("RGB", (800, 1200) if i == 2 else (1200, 800), "gray").save(shoot / f"{i}.jpg")
    window.open_folder(shoot)
    wait(app, lambda: not window.busy)
    dialog = BurstCompare(window.session.all_photos(), "0", window)
    dialog.resize(800, 550)
    dialog.show()
    try:
        wait(app, lambda: all(not pane.image.isNull() for pane in dialog.panes))
        check_compare(dialog)
    finally:
        dialog.reject()


def test_background_preload_two_next_one_previous_and_immediate_cache_hits(app, window, shoot, monkeypatch):
    main_thread, decode_threads = threading.get_ident(), []
    read = images.read_image
    def record_decode(*args, **kwargs):
        decode_threads.append(threading.get_ident())
        return read(*args, **kwargs)
    monkeypatch.setattr(images, "read_image", record_decode)
    for i in range(7):
        Image.new("RGB", (1200, 800), (30 + i * 20, 60, 100)).save(shoot / f"{i}.jpg")
    window.open_folder(shoot)
    wait(app, lambda: not window.busy and not window.canvas.image.isNull())
    window.refresh("3", rescan=False)
    wait(app, lambda: not window.cache.inflight and not window._resize_timer.isActive())
    assert {Path(key[0]).stem for key in window.cache.desired} == {"2", "3", "4", "5"}
    assert all(key in window.cache.cache for key in window.cache.desired)
    assert decode_threads and all(identity != main_thread for identity in decode_threads)
    stack = list(window.session.stack)
    window.navigate(1)
    assert window.current.key == "4" and not window.canvas.image.isNull()
    window.navigate(-1)
    assert window.current.key == "3" and not window.canvas.image.isNull()
    assert window.session.stack == stack and len(window.session.snapshot().pending) == 7
