import hashlib
from array import array

import pytest
from PIL import Image
from PySide6.QtCore import QSize

from ayikla.core import ShootSession, pair_photos, ConflictError
from ayikla.images import read_image
from ayikla.metadata import read_metadata
from ayikla.colors import analyze


def test_mixed_scans_and_pairs_roundtrip_after_restart(shoot, make_pair):
    make_pair(shoot, "digital")
    for name in ("film.JPG", "scan.JPEG", "large.TIF", "other.tIfF"):
        (shoot / name).write_bytes(b"generated " + name.encode())
    original = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in shoot.iterdir()}
    assert len(pair_photos(shoot)) == 5
    assert all(p.raw is None for p in pair_photos(shoot) if p.key != "digital")
    with ShootSession(shoot, write_xmp=True) as session:
        for photo in session.snapshot().pending:
            session.decide(photo, True)
        for photo in session.snapshot().kept:
            session.toggle_edit(photo)
    with ShootSession(shoot) as session:
        for _ in range(10):
            assert session.undo()
        assert len(session.snapshot().pending) == 5
        assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in shoot.iterdir()
                if p.name in original} == original


def test_jpeg_tiff_same_stem_conflicts(shoot):
    for suffix in ("jpg", "tiff"):
        (shoot / f"scan.{suffix}").write_bytes(b"generated")
    with pytest.raises(ConflictError):
        pair_photos(shoot)


@pytest.mark.parametrize("compression", ["raw", "tiff_lzw", "tiff_adobe_deflate"])
def test_tiff_scaled_preview_color_and_missing_exif(shoot, compression):
    path = shoot / "scan.tiff"
    Image.new("RGB", (1800, 1200), (255, 20, 20)).save(path, compression=compression)
    before = path.read_bytes()
    fit, error = read_image(path, QSize(300, 200))
    assert not error and fit.size() == QSize(300, 200)
    assert fit.pixelColor(50, 50).red() > 240
    full, error = read_image(path, QSize(300, 200), True)
    assert not error and full.size() == QSize(1800, 1200)
    assert analyze(path).swatches[0].startswith("#ff")
    assert read_metadata(path).shutter == "—"
    assert path.read_bytes() == before


@pytest.mark.parametrize("mode", ["I;16", "I;16B"])
def test_16bit_tiff_grayscale_preserves_dynamic_range(shoot, mode):
    values = array("H", [0, 16384, 32768, 65535] * 4)
    if mode == "I;16B":
        values.byteswap()
    path = shoot / "gray.tiff"
    Image.frombytes(mode, (4, 4), values.tobytes()).save(path)
    preview, error = read_image(path, QSize(100, 100))
    assert not error
    assert [preview.pixelColor(i, 0).red() for i in range(4)] == [0, 64, 128, 255]


def test_tiff_orientation_and_capture_time(shoot):
    path = shoot / "portrait.tif"
    exif = Image.Exif()
    exif[274] = 6
    exif[306] = "2026:10:29 13:14:15"
    Image.new("RGB", (1200, 800), "green").save(path, exif=exif)
    image, error = read_image(path, QSize(300, 200))
    assert not error and image.width() <= 300 and image.height() <= 200
    assert image.height() > image.width()
    assert read_metadata(path).taken.isoformat() == "2026-10-29T13:14:15"
