"""A phone-friendly JPEG grid and optional PDF of the same rendered sheet."""

import math
from dataclasses import dataclass

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QMarginsF, QRect, QSize, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPageSize, QPainter, QPdfWriter

from .core import AyiklaError
from .images import read_image
from .metadata import read_metadata


@dataclass(frozen=True)
class SheetLayout:
    width: int
    height: int
    cards: tuple[QRect, ...]


def layout(count):
    if count < 1:
        raise AyiklaError("Pick at least one photo for editing before exporting a contact sheet.")
    columns = min(count, 3 if count <= 12 else 4)
    width = 660 if columns == 1 else 1200 if columns == 2 else 1800
    margin, gap, header, card_height = 48, 24, 140, 390
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


def render(photos, date_text):
    photos = tuple(photos)
    grid = layout(len(photos))
    sheet = QImage(grid.width, grid.height, QImage.Format.Format_RGB32)
    if sheet.isNull():
        raise AyiklaError("Not enough memory for this contact sheet. Export fewer picks.")
    sheet.fill(QColor("#f1f0eb"))
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.setPen(QColor("#222222"))
    painter.setFont(_font(34, True))
    painter.drawText(QRect(48, 30, 1704, 45), Qt.AlignmentFlag.AlignLeft, "AYIKLA / EDIT PICKS")
    painter.setFont(_font(21))
    painter.setPen(QColor("#666666"))
    painter.drawText(QRect(48, 84, 1704, 35), Qt.AlignmentFlag.AlignLeft, f"{len(photos)} frames  /  {date_text}")
    for photo, card in zip(photos, grid.cards):
        painter.fillRect(card, QColor("#ffffff"))
        image_rect = QRect(card.x() + 12, card.y() + 12, card.width() - 24, 250)
        painter.fillRect(image_rect, QColor("#222222"))
        image, error = read_image(photo.jpeg, image_rect.size())
        if not image.isNull():
            size = image.size().scaled(image_rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRect(image_rect.x() + (image_rect.width() - size.width()) // 2,
                           image_rect.y() + (image_rect.height() - size.height()) // 2,
                           size.width(), size.height())
            painter.drawImage(target, image)
        else:
            painter.setPen(QColor("#eeeeee"))
            painter.setFont(_font(20))
            painter.drawText(image_rect, Qt.AlignmentFlag.AlignCenter, "Preview unavailable")
        info = read_metadata(photo.jpeg)
        settings = [v for v in (info.shutter, info.aperture, f"ISO {info.iso}" if info.iso != "—" else "—") if v != "—"]
        lens = [v for v in (info.focal_length, info.lens) if v != "—"]
        lines = [(photo.jpeg.name, 22, True),
                 (" / ".join(settings) or "No exposure metadata", 18, False),
                 (" / ".join(lens) or "No lens metadata", 17, False),
                 (info.taken.strftime("%Y-%m-%d %H:%M:%S") if info.taken else "No capture time", 17, False)]
        for index, (text, pixels, bold) in enumerate(lines):
            font = _font(pixels, bold)
            painter.setFont(font)
            painter.setPen(QColor("#222222" if bold else "#666666"))
            fitted = QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideMiddle, card.width() - 32)
            painter.drawText(QRect(card.x() + 16, card.y() + 272 + index * 27, card.width() - 32, 27),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, fitted)
    painter.end()
    return sheet


def encode(sheet, include_pdf=False):
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
        writer.setResolution(150)
        writer.setPageSize(QPageSize(QSizeF(sheet.width() * 72 / 150, sheet.height() * 72 / 150), QPageSize.Unit.Point))
        writer.setPageMargins(QMarginsF(0, 0, 0, 0))
        writer.setTitle("Ayikla edit picks")
        writer.setCreator("Ayikla")
        painter = QPainter(writer)
        if not painter.isActive():
            raise AyiklaError("Could not create the contact sheet PDF.")
        painter.drawImage(QRect(0, 0, writer.width(), writer.height()), sheet)
        painter.end()
        del writer
        buffer.close()
        pdf = bytes(data)
    return jpeg, pdf
