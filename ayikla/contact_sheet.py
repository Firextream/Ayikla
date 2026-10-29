"""A phone-friendly JPEG grid and optional PDF of the same rendered sheet."""

import math
from dataclasses import dataclass

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QMarginsF, QRect, QRectF, QSize, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter

from .core import AyiklaError
from .images import read_image
from .metadata import read_metadata


@dataclass(frozen=True)
class SheetLayout:
    width: int
    height: int
    cards: tuple[QRect, ...]

    def rows(self):
        """(top, bottom) of each row of cards, for PDF page breaks between rows."""
        return sorted({(card.top(), card.bottom()) for card in self.cards})


HEADER = 140
PAPER = "#f1f0eb"
# PDF: A4 pages with 15 mm margins; the content area (180 × 249 mm) also fits US Letter.
# The raster is printed at 0.1 mm per pixel, so the 4-column sheet (1800 px) fills 180 mm.
PAGE_MM, MARGIN_MM, CONTENT_MM, MM_PER_PIXEL = (210, 297), 15, (180, 249), 0.1


def layout(count):
    if count < 1:
        raise AyiklaError("Pick at least one photo for editing before exporting a contact sheet.")
    columns = min(count, 3 if count <= 9 else 4)
    width = 660 if columns == 1 else 1200 if columns == 2 else 1800
    margin, gap, header, card_height = 48, 24, HEADER, 390
    cell = (width - margin * 2 - gap * (columns - 1)) // columns
    rows = math.ceil(count / columns)
    height = header + rows * (card_height + gap) + 48
    if width * height > 80_000_000 or height > 65000:
        raise AyiklaError("This shortlist is too large for one shareable JPEG. Export a smaller selection.")
    return SheetLayout(width, height, tuple(QRect(margin + (i % columns) * (cell + gap),
                                                  header + (i // columns) * (card_height + gap),
                                                  cell, card_height) for i in range(count)))


def _font(pixels, bold=False):
    font = QFont("Segoe UI")
    font.setPixelSize(pixels)
    font.setBold(bold)
    return font


def metadata_lines(info):
    """The caption lines that have something to say; a scan without EXIF gets none."""
    settings = [v for v in (info.shutter, info.aperture, f"ISO {info.iso}" if info.iso != "—" else "—") if v != "—"]
    lens = [v for v in (info.focal_length, info.lens) if v != "—"]
    lines = [" / ".join(settings), " / ".join(lens), info.taken.strftime("%Y-%m-%d %H:%M:%S") if info.taken else ""]
    return [line for line in lines if line]


def frames(count):
    return f"{count} frame" if count == 1 else f"{count} frames"


def render(photos, title, date_text):
    """The sheet image and its layout (encode uses the rows for PDF page breaks)."""
    photos = tuple(photos)
    grid = layout(len(photos))
    sheet = QImage(grid.width, grid.height, QImage.Format.Format_RGB32)
    if sheet.isNull():
        raise AyiklaError("Not enough memory for this contact sheet. Export fewer picks.")
    sheet.fill(QColor(PAPER))
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.setPen(QColor("#222222"))
    painter.setFont(_font(34, True))
    heading = QFontMetrics(_font(34, True)).elidedText(title, Qt.TextElideMode.ElideMiddle, grid.width - 96)
    painter.drawText(QRect(48, 30, grid.width - 96, 45), Qt.AlignmentFlag.AlignLeft, heading)
    painter.setFont(_font(21))
    painter.setPen(QColor("#666666"))
    painter.drawText(QRect(48, 84, grid.width - 96, 35), Qt.AlignmentFlag.AlignLeft,
                     f"{frames(len(photos))}  /  {date_text}")
    for photo, card in zip(photos, grid.cards):
        painter.fillRect(card, QColor("#ffffff"))
        image_rect = QRect(card.x() + 12, card.y() + 12, card.width() - 24, 250)
        # Keep the fixed rows for PDF pagination and fit every photo without cropping.
        painter.fillRect(image_rect, QColor(PAPER))
        image, error = read_image(photo.jpeg, image_rect.size())
        if not image.isNull():
            size = image.size().scaled(image_rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRect(image_rect.x() + (image_rect.width() - size.width()) // 2,
                           image_rect.y() + (image_rect.height() - size.height()) // 2,
                           size.width(), size.height())
            painter.drawImage(target, image)
        else:
            painter.setPen(QColor("#666666"))
            painter.setFont(_font(20))
            painter.drawText(image_rect, Qt.AlignmentFlag.AlignCenter, "Preview unavailable")
        extra = metadata_lines(read_metadata(photo.jpeg))
        lines = [(photo.jpeg.name, 22, True)] + [(text, 18 if i == 0 else 17, False) for i, text in enumerate(extra)]
        for index, (text, pixels, bold) in enumerate(lines):
            font = _font(pixels, bold)
            painter.setFont(font)
            painter.setPen(QColor("#222222" if bold else "#666666"))
            fitted = QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideMiddle, card.width() - 32)
            painter.drawText(QRect(card.x() + 16, card.y() + 272 + index * 27, card.width() - 32, 27),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, fitted)
    painter.end()
    return sheet, grid


def pdf_pages(grid):
    """Slices (top, bottom) of the raster, one per page, broken between card rows."""
    room = round(CONTENT_MM[1] / MM_PER_PIXEL)
    pages, top, bottom = [], 0, HEADER
    for row_top, row_bottom in grid.rows():
        if row_bottom + 24 - top > room and bottom > top + HEADER * (top == 0):
            pages.append((top, bottom))
            top = row_top - 24
        bottom = row_bottom + 24
    pages.append((top, min(grid.height, bottom + 24)))
    return pages


def encode(sheet, include_pdf=False, grid=None):
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not sheet.save(buffer, "JPEG", 92):
        raise AyiklaError("Could not encode the contact sheet JPEG.")
    buffer.close()
    jpeg, pdf = bytes(data), None
    if include_pdf:
        # QtGui is already shipped. This wraps the identical raster layout;
        # it does not require QtPdf or a second PDF/font runtime in the app.
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        writer = QPdfWriter(buffer)
        writer.setResolution(254)  # 10 dots per mm: one sheet pixel = 0.1 mm
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(QMarginsF(MARGIN_MM, MARGIN_MM, MARGIN_MM, MARGIN_MM), QPageLayout.Unit.Millimeter)
        writer.setTitle("Ayikla edit picks")
        writer.setCreator("Ayikla")
        painter = QPainter(writer)
        if not painter.isActive():
            raise AyiklaError("Could not create the contact sheet PDF.")
        slices = pdf_pages(grid) if grid else [(0, sheet.height())]
        dots = writer.resolution() / 25.4 * MM_PER_PIXEL  # device dots per sheet pixel
        for index, (top, bottom) in enumerate(slices):
            if index:
                writer.newPage()
            width = sheet.width() * dots
            left = max(0, (writer.width() - width) / 2)  # narrow sheets are centred
            painter.drawImage(QRectF(left, 0, width, (bottom - top) * dots), sheet,
                              QRectF(0, top, sheet.width(), bottom - top))
        painter.end()
        del writer
        buffer.close()
        pdf = bytes(data)
    return jpeg, pdf
