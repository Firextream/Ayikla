import json
import re

import pytest
from PIL import Image

from ayikla.core import ShootSession, EDIT
from ayikla.colors import analyze
from ayikla.images import ImageCache
from PySide6.QtCore import QSize


def photos(shoot):
    for i in range(2):
        exif = Image.Exif()
        exif[271], exif[272] = "Generated", "Camera"
        exif[34665] = {36867: "2026:10:29 12:34:56", 42036: "Test Lens", 34855: 200}
        Image.new("RGB", (80, 60), "red").save(shoot / f"scan_{i}.tiff", exif=exif.tobytes())


def payload(shoot):
    return json.loads((shoot / EDIT / "ayikla_picks.json").read_text("utf-8"))


def test_picks_schema_and_palette_cache_reuse(shoot, monkeypatch):
    photos(shoot)
    path = shoot / "scan_0.tiff"
    palette = analyze(path)
    cached = {}
    with ShootSession(shoot, export_picks=True, palette_cache=cached) as session:
        session.decide(session.snapshot().pending[0], True)
        cached[ImageCache.key(session.snapshot().kept[0].jpeg, QSize(128, 128))] = palette
        def no_reanalysis(_path):
            raise AssertionError("Color ideas palette should be reused")
        monkeypatch.setattr("ayikla.picks.analyze", no_reanalysis)
        session.toggle_edit(session.snapshot().kept[0])
        doc = payload(shoot)
        assert set(doc) == {"schema_version", "picks"} and doc["schema_version"] == 1
        item, = doc["picks"]
        assert set(item) == {"filename", "raw_filename", "capture_time", "camera", "lens", "settings", "palette", "caption"}
        assert item["filename"] == "scan_0.tiff" and item["raw_filename"] is None
        assert item["camera"] == "Generated Camera" and item["lens"] == "Test Lens"
        assert item["capture_time"] == "2026-10-29T12:34:56"
        assert item["settings"] == {"shutter": None, "aperture": None, "iso": "200", "focal_length": None}
        assert item["caption"] == ""
        assert item["palette"] and all(re.fullmatch(r"#[0-9a-f]{6}", value) for value in item["palette"])


def test_removing_earlier_pick_keeps_later_picks_and_undo_after_restart(shoot):
    photos(shoot)
    with ShootSession(shoot, export_picks=True, write_xmp=True) as session:
        for photo in session.snapshot().pending:
            session.decide(photo, True)
        first, second = session.snapshot().kept
        session.toggle_edit(first)
        session.toggle_edit(second)
        session.toggle_edit(first)
        assert [p["filename"] for p in payload(shoot)["picks"]] == [second.jpeg.name]
        before = (shoot / EDIT / "ayikla_picks.json").read_bytes()
        session.refresh_picks()
        assert (shoot / EDIT / "ayikla_picks.json").read_bytes() == before
    with ShootSession(shoot) as session:
        session.undo()
        assert len(payload(shoot)["picks"]) == 2
        session.undo()
        assert [p["filename"] for p in payload(shoot)["picks"]] == [first.jpeg.name]
        session.undo()
        assert not (shoot / EDIT / "ayikla_picks.json").exists()


def test_empty_round_summary_exports_empty_list_without_adding_undo(shoot):
    with ShootSession(shoot, export_picks=True) as session:
        session.refresh_picks()
        assert payload(shoot) == {"schema_version": 1, "picks": []}
        assert not session.stack


def test_corrupt_photo_has_null_metadata_and_empty_palette(shoot):
    (shoot / "bad.jpg").write_bytes(b"generated corrupt image")
    with ShootSession(shoot, export_picks=True) as session:
        session.decide(session.snapshot().pending[0], True)
        session.toggle_edit(session.snapshot().kept[0])
        item = payload(shoot)["picks"][0]
        assert item["palette"] == [] and item["camera"] is None and item["capture_time"] is None


def test_picks_write_failure_recovers_same_decision(shoot, monkeypatch):
    photos(shoot)
    with ShootSession(shoot, export_picks=True) as session:
        session.decide(session.snapshot().pending[0], True)
        original = session._finish_write
        def fail(*args):
            raise OSError("simulated disk interruption")
        monkeypatch.setattr(session, "_finish_write", fail)
        with pytest.raises(OSError):
            session.toggle_edit(session.snapshot().kept[0])
    with ShootSession(shoot) as session:
        assert session.recovery_count == 1 and len(session.edits) == 1
        assert len(payload(shoot)["picks"]) == 1
        session.undo()
        assert not session.edits
