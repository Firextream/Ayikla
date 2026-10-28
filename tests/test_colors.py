import time
import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage, QColorSpace
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from ayikla.colors import TONES, analyze, describe, rank, similarity
from ayikla.color_browser import ColorBrowser, AnalysisTask
from ayikla.core import Photo


def solid(color):
    image = QImage(100, 80, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    return image


@pytest.mark.parametrize('color,tone', [('red', 'Red'), ('#ff8000', 'Orange'), ('yellow', 'Yellow'),
    ('#00ff00', 'Green'), ('cyan', 'Teal'), ('blue', 'Blue'), ('#8000ff', 'Purple'),
    ('#ff0080', 'Pink'), ('black', 'Dark'), ('#808080', 'Neutral'), ('white', 'Light')])
def test_tone_coverage(color, tone):
    profile = describe(solid(color))
    assert profile.coverage[TONES.index(tone)] == 1
    assert sum(profile.histogram) == pytest.approx(1)
    assert profile.swatches == (QColor(color).name(),)


def test_percentage_similar_palette_and_threshold():
    image = solid('red')
    for x in range(25):
        for y in range(80):
            image.setPixelColor(x, y, QColor('blue'))
    profiles = {'mixed': describe(image), 'red': describe(solid('red')), 'blue': describe(solid('blue'))}
    assert profiles['mixed'].coverage[0] == pytest.approx(.75, abs=.02)
    assert rank(profiles, tone='Red', minimum=.8) == [('red', 1)]
    assert rank(profiles, reference='mixed')[0][0] == 'red'
    assert rank(profiles, reference='missing') == []
    assert similarity(profiles['red'], profiles['blue']) == 0
    assert len(rank({str(i): profiles['red'] for i in range(30)}, tone='Red')) == 24


def test_decode_scaled_corrupt_and_color_space(shoot, monkeypatch):
    import ayikla.colors as colors
    from ayikla.images import read_image
    path = shoot / 'color.JPG'
    image = solid('red').scaled(6000, 4000)
    assert image.save(str(path))
    before = path.read_bytes()
    calls = []
    def decode(path, bounds):
        calls.append(bounds)
        result, error = read_image(path, bounds)
        assert result.width() <= 128 and result.height() <= 128
        return result, error
    monkeypatch.setattr(colors, 'read_image', decode)
    assert analyze(path).coverage[0] == 1
    assert calls == [QSize(128, 128)] and path.read_bytes() == before
    bad = shoot / 'broken.JPG'
    bad.write_bytes(b'not a jpeg')
    with pytest.raises(ValueError):
        analyze(bad)
    image = solid('red')
    image.setColorSpace(QColorSpace(QColorSpace.NamedColorSpace.AdobeRgb))
    assert describe(image).coverage[0] == 1


def test_browser_filter_jump_cache_cancel_and_no_writes(shoot):
    app = QApplication.instance() or QApplication([])
    photos = []
    for name, color in [('red', 'red'), ('similar', '#ee0010'), ('blue', 'blue')]:
        path = shoot / (name + '.JPG')
        solid(color).save(str(path))
        photos.append(Photo(name, path, None, 'kept'))
    bad = shoot / 'broken.JPG'
    bad.write_bytes(b'broken')
    photos.append(Photo('broken', bad, None, 'kept'))
    before = {p.name: p.read_bytes() for p in shoot.iterdir()}
    cached = {}
    dialog = ColorBrowser(photos, 'red', cached)
    dialog.show()
    for _ in range(500):
        app.processEvents()
        if dialog.profiles:
            break
        QTest.qWait(10)
    assert len(dialog.profiles) == 3 and 'broken' in dialog.failures
    assert dialog.results[0][0] == 'similar'
    dialog.filter.setCurrentIndex(TONES.index('Blue') + 1)
    assert dialog.results == [('blue', 1)]
    jumped = []
    dialog.activated.connect(jumped.append)
    dialog.choose('blue')
    assert jumped == ['blue'] and dialog.closed and dialog.task.cancel.is_set()
    assert len(cached) == 3
    task = AnalysisTask(photos, cached)
    task.cancel.set()
    result = []
    task.signals.finished.connect(lambda values, errors: result.append(values))
    task.run()
    assert result == [{}]
    assert {p.name: p.read_bytes() for p in shoot.iterdir()} == before


def test_analysis_reuses_only_unchanged_signatures(shoot, monkeypatch):
    import ayikla.color_browser as browser
    from ayikla.images import ImageCache
    path = shoot / 'same.JPG'
    solid('red').save(str(path))
    photo = Photo('same', path, None, 'kept')
    signature = ImageCache.key(path, QSize(128, 128))
    cached = {signature: analyze(path)}
    calls = []
    monkeypatch.setattr(browser, 'analyze', lambda path: calls.append(path) or describe(solid('blue')))
    AnalysisTask([photo], cached).run()
    assert calls == []
    path.write_bytes(b'changed size forces re-analysis')
    AnalysisTask([photo], cached).run()
    assert calls == [path]


def test_edit_browser_keyboard_jump_and_error_summary(shoot):
    from PySide6.QtCore import Qt
    from ayikla.ui import MainWindow
    from ayikla.core import ShootSession, LOG, EDIT
    for name in ('first', 'second'):
        solid('red').save(str(shoot / (name + '.JPG')))
        (shoot / (name + '.ARW')).write_bytes(b'generated RAW')
    (shoot / 'bad.JPG').write_bytes(b'corrupt')
    with ShootSession(shoot) as session:
        for photo in session.snapshot().pending:
            session.decide(photo, True)
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    def wait(predicate):
        for _ in range(500):
            app.processEvents()
            if predicate():
                return
            time.sleep(.01)  # Let Python file-operation workers acquire the GIL.
        assert predicate()
    try:
        window.open_folder(shoot)
        wait(lambda: not window.busy)
        assert window.colors_button.isHidden()
        window.jump_to('first')
        assert window.colors_button.isEnabled() and 'ARW' in window.raw_badge.text()
        before_stack = list(window.session.stack)
        QTest.keyClick(window, Qt.Key.Key_C)
        dialog = window.color_browser
        wait(lambda: bool(dialog.profiles))
        assert 'bad' in window.end_errors.toPlainText()
        assert dialog.results[0][0] == 'second'
        dialog.choose('second')
        assert window.current.key == 'second'
        assert window.session.stack == before_stack and not window.session.edits
        QTest.keyClick(window, Qt.Key.Key_E)
        wait(lambda: not window.busy)
        assert (shoot / EDIT / 'second.ARW').read_bytes() == b'generated RAW'
    finally:
        wait(lambda: not window.busy)
        window.close()
