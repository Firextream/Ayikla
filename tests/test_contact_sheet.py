from datetime import date
import os
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtGui import QFontDatabase, QFontMetrics, QFont, QImage
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication

from ayikla.contact_sheet import encode, layout, render
from ayikla.core import ShootSession, EDIT, ARCHIVE, AyiklaError


@pytest.fixture(scope="module", autouse=True)
def app():
    application = QApplication.instance() or QApplication([])
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for name in ("segoeui.ttf", "segoeuib.ttf"):
        QFontDatabase.addApplicationFont(str(fonts / name))
    assert QFontMetrics(QFont("Segoe UI")).inFont("A")
    return application


@pytest.mark.parametrize("count", [1, 2, 3, 5, 13, 50])
def test_layout_keeps_every_caption_and_image_inside_nonoverlapping_cards(count):
    grid = layout(count)
    assert len(grid.cards) == count
    for i, card in enumerate(grid.cards):
        assert card.top() >= 140 and card.bottom() < grid.height - 24
        assert card.left() >= 48 and card.right() < grid.width - 24
        assert card.height() >= 272 + 4 * 27
        assert all(not card.intersects(other) for other in grid.cards[i + 1:])


def select_photos(shoot, count=5):
    for i in range(count):
        exif = Image.Exif()
        exif[34665] = {34855: 200, 36867: "2026:10:29 12:34:56"}
        Image.new("RGB", (300, 200), (200 if i % 2 else 20, 80, 150)).save(shoot / f"IMG_{i}.JPG", exif=exif)
    session = ShootSession(shoot)
    for photo in session.snapshot().pending:
        session.decide(photo, True)
    for photo in session.snapshot().kept:
        session.toggle_edit(photo)
    return session


def test_contact_sheet_jpeg_pdf_render_and_undo_after_restart(shoot, tmp_path):
    with select_photos(shoot) as session:
        original = {p: p.read_bytes() for p in shoot.rglob("*.JPG")}
        result = session.export_contact_sheet(True, today=date(2026, 10, 29))
        jpg, pdf = [shoot / path for path in result["contact_sheet"]]
        image = QImage(str(jpg))
        assert not image.isNull() and image.size() == QSize(layout(5).width, layout(5).height)
        document = QPdfDocument()
        assert document.load(str(pdf)) == QPdfDocument.Error.None_
        assert document.pageCount() == 1
        rendered = document.render(0, image.size())
        assert not rendered.isNull()
        # The optional PDF carries the same raster grid and captions.
        assert abs(rendered.width() / rendered.height() - image.width() / image.height()) < .001
        rendered.save(str(tmp_path / "pdf-render.png"))
        document.close()
        del document  # Release the native PDF reader's Windows file handle.
        assert all(path.read_bytes() == content for path, content in original.items())
        second = session.export_contact_sheet(today=date(2026, 10, 29))
        assert second["contact_sheet"] == [f"{EDIT}/contact_sheet_2026-10-29_2.jpg"]
        assert jpg.exists() and pdf.exists()
    with ShootSession(shoot) as session:
        assert session.undo()
        assert not (shoot / second["contact_sheet"][0]).exists()
        assert session.undo()
        assert not jpg.exists() and not pdf.exists()
        assert len(list((shoot / ARCHIVE).rglob("contact_sheet_2026-10-29.pdf"))) == 1


def test_empty_shortlist_and_excessive_sheet_have_clear_errors(shoot):
    with ShootSession(shoot) as session:
        with pytest.raises(AyiklaError, match="at least one"):
            session.export_contact_sheet()
    with pytest.raises(AyiklaError, match="too large"):
        layout(10000)


def test_corrupt_preview_still_exports_named_placeholder(shoot):
    (shoot / "bad.JPG").write_bytes(b"generated unreadable image")
    with ShootSession(shoot) as session:
        session.decide(session.snapshot().pending[0], True)
        session.toggle_edit(session.snapshot().kept[0])
        outputs = session.export_contact_sheet()
        assert not QImage(str(shoot / outputs["contact_sheet"][0])).isNull()


# ── 1.6 review ────────────────────────────────────────────────────────────────

def test_plural_and_metadata_lines():
    from ayikla.contact_sheet import frames, metadata_lines
    from datetime import datetime
    from ayikla.metadata import CaptureInfo
    assert (frames(1), frames(3)) == ("1 frame", "3 frames")
    assert metadata_lines(CaptureInfo("SCAN.tif")) == []  # a scan: just the file name
    partial = CaptureInfo("IMG.JPG", taken=datetime(2026, 10, 29, 12, 0), iso="400")
    assert metadata_lines(partial) == ["ISO 400", "2026-10-29 12:00:00"]  # no "No lens metadata"


@pytest.mark.parametrize("count,columns", [(1, 1), (3, 3), (9, 3), (10, 4)])
def test_three_columns_up_to_nine_picks_then_four(count, columns):
    grid = layout(count)
    assert len({card.left() for card in grid.cards}) == columns


def test_title_is_the_shoot_name_and_its_date(tmp_path):
    shoot = tmp_path / "2026-10-12_club"
    shoot.mkdir()
    with select_photos(shoot, 1) as session:
        assert session.sheet_title([], "2026-10-29") == ("club", "2026-10-12")
    plain = tmp_path / "Autumn walk"
    plain.mkdir()
    with select_photos(plain, 2) as session:
        photos = list(session.snapshot().kept)
        assert session.sheet_title(photos, "2026-10-29") == ("Autumn walk", "2026-10-29")  # from capture time
    scans = tmp_path / "Scans"
    scans.mkdir()
    Image.new("RGB", (60, 40)).save(scans / "SCAN.tif")
    with ShootSession(scans) as session:
        assert session.sheet_title(session.snapshot().pending, "2026-11-01") == ("Scans", "2026-11-01")


def test_pdf_is_a4_with_margins_and_breaks_between_rows(shoot):
    from ayikla.contact_sheet import pdf_pages
    grid = layout(40)  # 10 rows of 4
    pages = pdf_pages(grid)
    assert len(pages) > 1 and pages[0][0] == 0
    rows = grid.rows()
    for top, bottom in pages:
        assert bottom - top <= 2490  # 249 mm at 0.1 mm per pixel: fits A4 and Letter
        assert not any(row_top < top < row_bottom or row_top < bottom < row_bottom for row_top, row_bottom in rows)
    with select_photos(shoot, 13) as session:
        result = session.export_contact_sheet(True, today=date(2026, 10, 29))
        pdf = shoot / result["contact_sheet"][1]
        document = QPdfDocument()
        assert document.load(str(pdf)) == QPdfDocument.Error.None_
        size = document.pagePointSize(0)
        assert abs(size.width() - 595.3) < 1 and abs(size.height() - 841.9) < 1  # A4
        assert document.pageCount() == len(pdf_pages(layout(13)))
        document.close()
        del document
