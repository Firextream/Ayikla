"""Neutral photo canvas, quiet overlays and a virtualized filmstrip."""

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, QPropertyAnimation, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QAbstractScrollArea, QGraphicsOpacityEffect, QLabel, QSizePolicy, QWidget

from .images import ImageCache


class ElidedLabel(QLabel):
    """Keep long file/folder names from displacing the photo controls."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = text
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text):
        self._full_text = text
        self.setToolTip(text)
        self._elide()

    def text(self):
        return self._full_text

    def _elide(self):
        super().setText(self.fontMetrics().elidedText(
            self._full_text, Qt.TextElideMode.ElideMiddle, max(0, self.contentsRect().width())))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()


class FadingOverlay(QLabel):
    def __init__(self, parent, fade_to=0.0):
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background: rgba(26,26,26,240); color: #dddddd; border: 1px solid #404040;"
                           "border-radius: 8px; padding: 10px 14px; font-size: 12px;")
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.fade_to = fade_to
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self.fade)
        self.animation = QPropertyAnimation(self.effect, b"opacity", self)
        self.animation.setDuration(180)
        self.hide()

    def reveal(self, text=None, auto_fade=True):
        if text is not None:
            self.setText(text)
        self.adjustSize()
        self.animation.stop()
        self.effect.setOpacity(1.0)
        self.show()
        self.raise_()
        if auto_fade:
            self.timer.start()

    def fade(self):
        self.animation.setStartValue(self.effect.opacity())
        self.animation.setEndValue(self.fade_to)
        self.animation.start()

    def dismiss(self):
        self.timer.stop()
        self.animation.stop()
        self.hide()


class PhotoCanvas(QWidget):
    resized = Signal()
    activity = Signal()

    def __init__(self):
        super().__init__()
        self.image = QImage()
        self.message = ""
        self.zoomed = False
        self.pan = QPointF()
        self._drag = None
        self.hud = FadingOverlay(self)
        self.info = FadingOverlay(self, fade_to=.25)
        self.help = FadingOverlay(self, fade_to=1.0)
        self.toast = FadingOverlay(self)
        self.setMouseTracking(True)
        self.setMinimumSize(240, 120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_zoom(self, enabled):
        self.zoomed = enabled
        self.pan = QPointF()
        self._drag = None
        self.setCursor(Qt.CursorShape.OpenHandCursor if enabled else Qt.CursorShape.ArrowCursor)

    def _clamp_pan(self):
        ratio = self.devicePixelRatioF()
        x_limit = max(0, (self.image.width() / ratio - self.width()) / 2)
        y_limit = max(0, (self.image.height() / ratio - self.height()) / 2)
        self.pan = QPointF(min(x_limit, max(-x_limit, self.pan.x())),
                           min(y_limit, max(-y_limit, self.pan.y())))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1a1a1a"))
        if not self.image.isNull():
            if self.zoomed:
                self._clamp_pan()
                ratio = self.devicePixelRatioF()
                width, height = self.image.width() / ratio, self.image.height() / ratio
                target = QRectF((self.width() - width) / 2 + self.pan.x(),
                                (self.height() - height) / 2 + self.pan.y(), width, height)
                # 100% = one encoded photo pixel per physical display pixel.
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            else:
                area = self.rect().adjusted(8, 8, -8, -8)
                size = self.image.size().scaled(area.size(), Qt.AspectRatioMode.KeepAspectRatio)
                target = QRectF(area.center().x() - size.width() / 2,
                                area.center().y() - size.height() / 2, size.width(), size.height())
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(target, self.image)
        else:
            painter.setPen(QColor("#aaaaaa"))
            painter.setFont(QFont("Segoe UI", 18))
            painter.drawText(self.rect().adjusted(30, 30, -30, -30),
                             Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.message)

    def position_overlays(self):
        self.hud.move(18, 16)
        self.info.move(18, 64)
        parent = self.help.parentWidget()
        self.help.move(max(12, (parent.width() - self.help.width()) // 2),
                       max(12, (parent.height() - self.help.height()) // 2))
        self.toast.move(max(12, (self.width() - self.toast.width()) // 2),
                        max(12, self.height() - self.toast.height() - 28))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_overlays()
        self.resized.emit()

    def mousePressEvent(self, event):
        if self.zoomed and event.button() == Qt.MouseButton.LeftButton:
            self._drag = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.activity.emit()

    def mouseMoveEvent(self, event):
        if self._drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.pan += event.position() - self._drag
            self._drag = event.position()
            self._clamp_pan()
            self.update()
        self.activity.emit()

    def mouseReleaseEvent(self, event):
        self._drag = None
        if self.zoomed:
            self.setCursor(Qt.CursorShape.OpenHandCursor)


class Filmstrip(QAbstractScrollArea):
    activated = Signal(str)
    item_width = 132
    thumbnail_size = QSize(116, 74)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(116)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QAbstractScrollArea.Shape.NoFrame)
        self.items = ()
        self.current_key = None
        self.edits = set()
        self.cache = ImageCache(self, byte_limit=12 * 1024 * 1024)
        self.cache.decoded.connect(lambda _: self.viewport().update())
        self.horizontalScrollBar().valueChanged.connect(self.request_visible)
        self.hide()

    def set_items(self, items, current_key, edits):
        self.items, self.current_key, self.edits = items, current_key, set(edits)
        self.horizontalScrollBar().setRange(0, max(0, len(items) * self.item_width - self.viewport().width()))
        index = next((i for i, photo in enumerate(items) if photo.key == current_key), None)
        if index is not None:
            left, right = index * self.item_width, (index + 1) * self.item_width
            value = self.horizontalScrollBar().value()
            if left < value:
                self.horizontalScrollBar().setValue(left)
            elif right > value + self.viewport().width():
                self.horizontalScrollBar().setValue(right - self.viewport().width())
        self.request_visible()

    def edge_color(self, photo):
        if photo.key in self.edits:
            return QColor("#b1a0d0")
        return QColor({"kept": "#94b39a", "rejected": "#bc9292"}.get(photo.state, "#575757"))

    def visible_range(self):
        start = self.horizontalScrollBar().value() // self.item_width
        return range(start, min(len(self.items), start + self.viewport().width() // self.item_width + 2))

    def request_visible(self):
        if not self.isVisible():
            return
        paths = [self.items[index].jpeg for index in self.visible_range()]
        if paths:
            self.cache.show(paths[0], paths[1:], self.thumbnail_size)
        self.viewport().update()

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        painter.fillRect(self.viewport().rect(), QColor("#1a1a1a"))
        offset = self.horizontalScrollBar().value()
        for index in self.visible_range():
            photo = self.items[index]
            x = index * self.item_width - offset + 4
            card = QRect(x, 2, self.item_width - 8, 93)
            painter.setPen(QPen(self.edge_color(photo), 3 if photo.key == self.current_key else 1))
            painter.drawRoundedRect(card.adjusted(1, 1, -1, -1), 3, 3)
            image = self.cache.get(photo.jpeg, self.thumbnail_size)
            if not image.isNull():
                size = image.size().scaled(self.thumbnail_size, Qt.AspectRatioMode.KeepAspectRatio)
                painter.drawImage(QRectF(x + (card.width() - size.width()) / 2, 7, size.width(), size.height()), image)
            painter.setPen(QColor("#bbbbbb"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(card.adjusted(5, 73, -3, -2), Qt.AlignmentFlag.AlignCenter, photo.jpeg.name)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            index = int(event.position().x() + self.horizontalScrollBar().value()) // self.item_width
            if 0 <= index < len(self.items):
                self.activated.emit(self.items[index].key)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.horizontalScrollBar().setPageStep(self.viewport().width())
        self.horizontalScrollBar().setRange(0, max(0, len(self.items) * self.item_width - self.viewport().width()))
        self.request_visible()

    def showEvent(self, event):
        super().showEvent(event)
        self.request_visible()
