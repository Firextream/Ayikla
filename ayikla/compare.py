"""Keyboard-first burst viewer; decisions are always explicit."""

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtWidgets import QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from .widgets import ElidedLabel

from .images import ImageCache
from .widgets import PhotoCanvas


class BurstCompare(QDialog):
    committed = Signal(object, str)

    def __init__(self, photos, selected, parent=None):
        super().__init__(parent)
        self.photos = tuple(photos)
        self.selected = selected
        self.page_size = 2 if len(photos) == 2 else 4
        self.page = next(i for i, p in enumerate(photos) if p.key == selected) // self.page_size
        self.zoomed = False
        self.saved = False
        self.setWindowTitle("Burst compare")
        self.resize(1200, 800)
        self.setMinimumSize(800, 550)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        self.heading = QLabel()
        layout.addWidget(self.heading)
        grid = QGridLayout()
        grid.setSpacing(12)
        layout.addLayout(grid, 1)
        self.panes, self.labels, self.caches, self.cells = [], [], [], []
        for index in range(self.page_size):
            cell = QFrame()
            cell.setObjectName("compareCell")
            column = QVBoxLayout(cell)
            column.setContentsMargins(12, 10, 12, 10)
            column.setSpacing(6)
            name = ElidedLabel()
            name.setStyleSheet("font-size: 13px; padding: 0;")
            canvas = PhotoCanvas()
            canvas.corner_label = QLabel(str(index + 1), canvas)
            canvas.corner_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            canvas.corner_label.setStyleSheet("background: #222222; color: #eeeeee; font-size: 12px;"
                                              "border: 1px solid #777777; border-radius: 3px; padding: 2px 6px;")
            canvas.corner_label.adjustSize()
            cache = ImageCache(self, byte_limit=96 * 1024 * 1024)
            cache.loaded.connect(lambda path, image, error, pane=canvas: self.loaded(pane, image, error))
            canvas.panned.connect(self.pan_all)
            canvas.resized.connect(self.schedule_load)
            column.addWidget(name)
            column.addWidget(canvas, 1)
            grid.addWidget(cell, index // 2, index % 2)
            self.panes.append(canvas)
            self.labels.append(name)
            self.caches.append(cache)
            self.cells.append(cell)
        controls = QHBoxLayout()
        controls.setSpacing(12)
        self.buttons = []
        for text, callback in (("← Previous page", lambda: self.change_page(-1)),
                               ("Next page →", lambda: self.change_page(1)),
                               ("100% / Fit · F", self.toggle_zoom),
                               ("Confirm · Shift+Enter", self.confirm),
                               ("Return · Esc", self.reject)):
            control = QPushButton(text)
            control.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            control.setFixedHeight(34)
            control.clicked.connect(callback)
            controls.addWidget(control, 1)
            self.buttons.append(control)
        self.buttons[3].setToolTip("Keep the selected frame and reject every other frame in this burst.")
        layout.addLayout(controls)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.load_page)
        self.render_page()

    def schedule_load(self):
        if hasattr(self, "timer"):
            self.timer.start(120)

    def render_page(self):
        pages = (len(self.photos) + self.page_size - 1) // self.page_size
        self.heading.setWordWrap(True)
        self.heading.setText(f"Burst · {len(self.photos)} frames · Page {self.page + 1}/{pages}"
                             "   |   1–4 select · F zoom · Drag pans all · Shift+Enter keeps selected / rejects others")
        for i, (cell, name, canvas) in enumerate(zip(self.cells, self.labels, self.panes)):
            canvas.set_zoom(self.zoomed)
            position = self.page * self.page_size + i
            cell.setVisible(position < len(self.photos))
            if position < len(self.photos):
                photo = self.photos[position]
                chosen = photo.key == self.selected
                name.setText(photo.jpeg.name + ("  · Keeper" if chosen else ""))
                cell.setProperty("selected", chosen)
                cell.style().unpolish(cell)
                cell.style().polish(cell)
        self.load_page()

    def load_page(self):
        for i, (canvas, cache) in enumerate(zip(self.panes, self.caches)):
            position = self.page * self.page_size + i
            if position < len(self.photos):
                cache.clear()
                canvas.image = type(canvas.image)()
                canvas.message = "Loading…"
                cache.show(self.photos[position].jpeg, [], canvas.size() * self.devicePixelRatioF(), self.zoomed)
                canvas.update()

    @staticmethod
    def loaded(pane, image, error):
        pane.image, pane.message = image, error
        pane.position_overlays()
        pane.update()

    def pan_all(self, point):
        for pane in self.panes:
            pane.pan = QPointF(point)
            pane._clamp_pan()
            pane.position_overlays()
            pane.update()

    def toggle_zoom(self):
        self.zoomed = not self.zoomed
        self.render_page()

    def change_page(self, step):
        self.page = max(0, min((len(self.photos) - 1) // self.page_size, self.page + step))
        self.render_page()

    def confirm(self):
        if not self.saved:
            self.committed.emit(self.photos, self.selected)

    def keyPressEvent(self, event):
        key = event.key()
        if event.isAutoRepeat():
            return
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_4 and not self.saved:
            index = key - Qt.Key.Key_1
            position = self.page * self.page_size + index
            if index < self.page_size and position < len(self.photos):
                self.selected = self.photos[position].key
                self.render_page()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.confirm()
        elif key == Qt.Key.Key_F:
            self.toggle_zoom()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.change_page(-1 if key == Qt.Key.Key_Left else 1)
        elif key == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def done(self, result):
        self.timer.stop()
        for cache in self.caches:
            cache.close()
        super().done(result)
