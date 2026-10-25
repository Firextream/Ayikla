from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from ayikla import core
from ayikla.core import ConflictError, ShootSession
from ayikla.images import ImageCache, read_image


def test_snapshot_and_transactions_never_rescan(shoot, make_pair, monkeypatch):
    for index in range(3):
        make_pair(shoot, f"IMG_{index}")
    with ShootSession(shoot) as session:
        original_scan = core.pair_photos
        scans = []
        def record_scan(*args, **kwargs):
            scans.append(args[0])
            return original_scan(*args, **kwargs)
        monkeypatch.setattr(core, "pair_photos", record_scan)
        first = session.snapshot()
        assert session.snapshot() is first
        session.decide(first.pending[0], True)
        assert session.snapshot().kept[0].jpeg.parent.name == core.KEPT
        session.toggle_edit(session.snapshot().kept[0])
        session.toggle_edit(session.snapshot().kept[0])
        session.undo()
        session.undo()
        session.undo()
        assert len(session.snapshot().pending) == 3
        session.decide(session.snapshot().pending[0], False)
        assert len(session.snapshot().rejected) == 1
        assert not scans
        assert [p.key for p in session.all_photos()] == ["img_0", "img_1", "img_2"]
        session.recover_pending()  # Retry is also an explicit external refresh.
        assert len(scans) == 3


def test_index_sees_external_addition_only_on_rescan(shoot, make_pair):
    make_pair(shoot, "IMG_1")
    with ShootSession(shoot) as session:
        make_pair(shoot, "IMG_2")
        assert len(session.snapshot().pending) == 1
        session.rescan()
        assert len(session.snapshot().pending) == 2


def test_conflict_refreshes_index_and_new_raw_never_left_behind(shoot, make_pair):
    make_pair(shoot, raw=False)
    with ShootSession(shoot) as session:
        photo = session.snapshot().pending[0]
        (shoot / "img_1234.cr3").write_bytes(b"new external raw")
        with pytest.raises(ConflictError, match="CR3"):
            session.decide(photo, True)
        assert photo.jpeg.exists()
        assert session.snapshot().pending[0].raw is not None
        session.decide(session.snapshot().pending[0], True)
        assert session.snapshot().kept[0].raw.read_bytes() == b"new external raw"


def test_scaled_decode_uses_viewport_and_full_decode_is_explicit(tmp_path):
    path = tmp_path / "test.jpg"
    Image.new("RGB", (2400, 1600), "gray").save(path)
    fit, error = read_image(path, QSize(600, 300))
    assert not error
    assert fit.size() == QSize(450, 300)
    full, error = read_image(path, QSize(600, 300), full_resolution=True)
    assert not error
    assert full.size() == QSize(2400, 1600)


def test_scaled_portrait_respects_display_bounds(tmp_path):
    path = tmp_path / "portrait.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (2400, 1600), "gray").save(path, exif=exif)
    image, error = read_image(path, QSize(600, 300))
    assert not error
    assert image.size() == QSize(200, 300)


def test_cache_eviction_is_bytes_not_count():
    cache = ImageCache(byte_limit=3000)
    image = QImage(10, 10, QImage.Format.Format_RGB32)
    for index in range(7):
        key = (str(index), 1, 1, 10, 10, False)
        cache.desired.add(key)
        cache._finished(key, image, "")
    assert len(cache.cache) == 7  # No five-image count limit.
    assert cache.bytes == 2800
    key = ("8", 1, 1, 10, 10, False)
    cache.desired.add(key)
    cache._finished(key, image, "")
    assert cache.bytes <= cache.byte_limit
    assert "0" not in [key[0] for key in cache.cache]
    cache.clear()
    assert cache.bytes == 0 and not cache.cache


def test_full_cache_is_released_on_return_to_fit():
    cache = ImageCache(byte_limit=10000)
    image = QImage(10, 10, QImage.Format.Format_RGB32)
    fit, full = ("a", 1, 1, 10, 10, False), ("a", 1, 1, 10, 10, True)
    cache.desired = {fit, full}
    cache._finished(fit, image, "")
    cache._finished(full, image, "")
    cache.discard_full_resolution()
    assert list(cache.cache) == [fit]
    assert cache.bytes == 400


def test_preload_requests_two_ahead_one_behind():
    from types import SimpleNamespace
    from ayikla.ui import MainWindow
    captured = []
    photos = tuple(SimpleNamespace(jpeg=Path(str(index))) for index in range(7))
    window = SimpleNamespace(current=photos[2], photos=photos, index=2,
                             canvas=SimpleNamespace(size=lambda: QSize(800, 600)),
                             devicePixelRatioF=lambda: 1,
                             cache=SimpleNamespace(show=lambda *args, **kwargs: captured.append(args)))
    MainWindow._request_image(window)
    assert captured[0][1] == [Path("3"), Path("4"), Path("1")]
