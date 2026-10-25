from datetime import datetime, timedelta

from PIL import Image, TiffImagePlugin

from ayikla.metadata import CaptureInfo, burst_hints, read_metadata
from ayikla.preferences import Preferences


def test_reads_all_exif_fields_without_decoding_pixels(tmp_path, monkeypatch):
    path = tmp_path / "IMG_001.JPG"
    exif = Image.Exif()
    exif[34665] = {36867: "2026:10:25 12:34:56", 37521: "123",
                   33434: TiffImagePlugin.IFDRational(1, 320),
                   33437: TiffImagePlugin.IFDRational(28, 10), 34855: 400,
                   37386: TiffImagePlugin.IFDRational(50), 42036: "Generated lens 50mm"}
    Image.new("RGB", (120, 80), "gray").save(path, exif=exif)
    def forbidden_load(*_args, **_kwargs):
        raise AssertionError("EXIF must not decode pixels")
    monkeypatch.setattr(Image.Image, "load", forbidden_load)
    result = read_metadata(path)
    assert result.taken == datetime(2026, 10, 25, 12, 34, 56, 123000)
    assert (result.shutter, result.aperture, result.iso, result.focal_length, result.lens) == (
        "1/320 sn", "f/2.8", "400", "50 mm", "Generated lens 50mm")
    assert "IMG_001.JPG" in result.text() and "25.10.2026" in result.text()


def test_missing_or_invalid_exif_is_harmless(tmp_path):
    path = tmp_path / "no-exif.jpg"
    Image.new("RGB", (10, 10)).save(path)
    assert read_metadata(path) == CaptureInfo(path.name)
    (tmp_path / "bad.jpg").write_bytes(b"not a jpeg")
    assert read_metadata(tmp_path / "bad.jpg").taken is None
    exif = Image.Exif()
    exif[34665] = {36867: "invalid date", 33434: TiffImagePlugin.IFDRational(1, 0)}
    Image.new("RGB", (10, 10)).save(path, exif=exif)
    assert read_metadata(path).shutter == "—"


def test_burst_boundary_order_missing_time_and_separate_groups():
    start = datetime(2026, 10, 25)
    items = {"b": CaptureInfo("IMG_2.JPG", start + timedelta(milliseconds=200)),
             "a": CaptureInfo("IMG_1.JPG", start),
             "c": CaptureInfo("IMG_3.JPG", start + timedelta(milliseconds=1200)),
             "d": CaptureInfo("IMG_4.JPG", start + timedelta(milliseconds=2201)),
             "e": CaptureInfo("IMG_5.JPG", start + timedelta(milliseconds=2400)),
             "missing": CaptureInfo("IMG_6.JPG"),
             "single": CaptureInfo("IMG_7.JPG", start + timedelta(seconds=20))}
    assert burst_hints(items) == {"a": (1, 3), "b": (2, 3), "c": (3, 3), "d": (1, 2), "e": (2, 2)}


def test_recent_five_order_deduplication_append_only(tmp_path):
    preferences = Preferences(tmp_path / "state")
    for index in range(7):
        preferences.add_recent(tmp_path / f"Shoot_{index}")
    before = preferences.path.read_bytes()
    preferences.add_recent(tmp_path / "SHOOT_3")
    assert preferences.path.read_bytes().startswith(before)
    reloaded = Preferences(tmp_path / "state")
    assert len(reloaded.recent) == 5
    assert reloaded.recent[0].endswith("SHOOT_3")
    assert len({path.casefold() for path in reloaded.recent}) == 5
    assert [path.rsplit("_", 1)[-1] for path in reloaded.recent] == ["3", "6", "5", "4", "2"]


def test_window_state_restores_and_skips_identical_writes(tmp_path):
    preferences = Preferences(tmp_path)
    preferences.save_window([20, 30, 1280, 800], False, False)
    before = preferences.path.read_bytes()
    preferences.save_window([20, 30, 1280, 800], False, False)
    assert preferences.path.read_bytes() == before
    assert Preferences(tmp_path).window == {"geometry": [20, 30, 1280, 800],
                                           "fullscreen": False, "maximized": False}


def test_torn_settings_record_preserved_and_next_append_readable(tmp_path):
    preferences = Preferences(tmp_path)
    preferences.add_recent(tmp_path / "one")
    with preferences.path.open("ab") as stream:
        stream.write(b'{"v":1,"type":"window"')
    before = preferences.path.read_bytes()
    preferences = Preferences(tmp_path)
    preferences.add_recent(tmp_path / "two")
    assert preferences.path.read_bytes().startswith(before)
    assert len(Preferences(tmp_path).recent) == 2


def test_invalid_window_geometry_ignored(tmp_path):
    path = tmp_path / "ayikla_settings.jsonl"
    path.write_text('{"v":1,"type":"window","geometry":[0,0,-1,9]}\nnull\n', "utf-8")
    assert Preferences(tmp_path).window == {}
