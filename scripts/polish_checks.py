"""Geometry and contrast assertions used at native Windows DPI and in pytest."""

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QLabel, QPushButton


def contrast(first, second):
    def luminance(color):
        channels = [color.redF(), color.greenF(), color.blueF()]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
        return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + .05) / (dark + .05)


def check_header(window):
    buttons = (window.folders_button, window.open_button, window.settings_button, window.full_button, window.help_button)
    gaps = [second.x() - first.geometry().right() - 1 for first, second in zip(buttons, buttons[1:])]
    assert gaps == [24] * 4, gaps
    assert len({button.y() for button in buttons}) == 1
    for button in buttons:
        assert button.fontMetrics().horizontalAdvance(button.text()) <= button.width(), button.text()
    return {"menu_gaps": gaps, "menu_baselines_aligned": True}


def check_start(window):
    sizes = []
    for card in window.step_cards:
        body = card.findChildren(QLabel)[-1]
        # TextWordWrap = 0x1000; calculate the complete two-line body rectangle.
        needed = body.fontMetrics().boundingRect(QRect(0, 0, body.contentsRect().width(), 10000), 0x1000, body.text())
        assert body.height() >= needed.height(), (body.text(), body.size(), needed)
        assert card.rect().contains(body.geometry()), body.text()
        sizes.append({"card_height": card.height(), "body_height": body.height(), "needed": needed.height()})
    return {**check_header(window), "cards": sizes}


def row_span(window, widget):
    """Left / right edge of a photo control in the decision row's coordinates."""
    left = widget.mapTo(window.controls, QPoint(0, 0)).x()
    return left, left + widget.width() - 1


def check_gallery(window):
    assert window.controls.isAncestorOf(window.photo_info)
    assert window.controls.height() <= 54
    ordered = [window.filename, window.raw_badge]
    if window.edit_badge.isVisible():
        ordered.append(window.edit_badge)
    ordered += [window.current_folder_button, window.info_button, window.strip_button, window.zoom_button]
    for first, second in zip(ordered, ordered[1:]):
        assert first.geometry().right() < second.geometry().left(), (first.text(), second.text())
    # 1.6: Undo · file info | ← Previous / Next → | Reject / Keep, all the decision buttons' height
    row = [window.undo_button, window.photo_info, window.previous_button, window.next_button]
    row += [window.reject_button, window.keep_button] if window.keep_button.isVisible() else [window.mark_button]
    for first, second in zip(row, row[1:]):
        assert row_span(window, first)[1] < row_span(window, second)[0], (first, second)
    decision = window.keep_button if window.keep_button.isVisible() else window.mark_button
    for button in (window.undo_button, window.previous_button, window.next_button):
        assert button.height() == decision.height(), (button.text(), button.height(), decision.height())
    middle = (row_span(window, window.previous_button)[0] + row_span(window, window.next_button)[1]) / 2
    centred = abs(middle - window.controls.width() / 2)
    assert window.counter.fontMetrics().horizontalAdvance(window.counter.text()) <= window.counter.width(), window.counter.text()
    progress_labels = [item for item in window.findChildren(QLabel)
                       if item.isVisible() and item.text().startswith(("Round 1 ·", "Round 2 ·"))]
    assert progress_labels == [window.counter], [item.text() for item in progress_labels]
    image = window.canvas.image_rect()
    assert image.left() >= 15.5 and image.top() >= 15.5
    assert image.right() <= window.canvas.width() - 15.5
    assert image.bottom() <= window.canvas.height() - 15.5
    assert abs(image.center().x() - window.canvas.width() / 2) <= 1
    assert abs(image.center().y() - window.canvas.height() / 2) <= 1
    if window.canvas.hud.isVisible():
        assert image.contains(window.canvas.hud.geometry().topLeft())
    ratios = []
    for button in (window.undo_button, window.previous_button, window.keep_button):
        enabled = button.isEnabled()
        button.setEnabled(False)
        palette = button.palette()
        fg = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText)
        bg = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button)
        if bg.alpha() == 0:
            bg = window.palette().color(QPalette.ColorRole.Window)
        value = contrast(fg, bg)
        button.setEnabled(enabled)
        assert value >= 3, (button.text(), fg.name(), bg.name(), value)
        ratios.append(round(value, 2))
    return {**check_header(window), "control_row_height": window.controls.height(), "nav_offset_from_centre": centred,
            "single_counter": True, "disabled_contrast": ratios, "photo_height": window.canvas.height()}


def check_compare(dialog):
    assert len({button.height() for button in dialog.buttons}) == 1
    for first, second in zip(dialog.buttons, dialog.buttons[1:]):
        assert second.x() - first.geometry().right() - 1 == 12
    for button in dialog.buttons:
        assert button.fontMetrics().horizontalAdvance(button.text()) <= button.width() - 12, button.text()
    for index, (cell, pane, label) in enumerate(zip(dialog.cells, dialog.panes, dialog.labels)):
        if not cell.isVisible():
            continue
        assert label.font().pixelSize() == 13
        assert pane.image_rect().contains(pane.corner_label.geometry().topLeft())
        assert pane.corner_label.text() == str(index + 1)
        assert cell.frameWidth() == 2
    assert sum(bool(cell.property("selected")) for cell in dialog.cells) == 1
    return {"selection_border": 2, "number_badges_on_images": True,
            "button_height": dialog.buttons[0].height(), "button_gaps": 12}


def check_summary(window):
    assert window.controls.isHidden() and window.photo_info.isHidden()
    assert window.end_card.width() <= 620
    for label in window.end_card.findChildren(QLabel):
        if label.isVisible():
            assert label.fontMetrics().horizontalAdvance(label.text().split("\n")[0]) <= label.width()
    return {**check_header(window), "photo_controls_hidden": True, "summary_width": window.end_card.width()}


def check_keys(window):
    """First-launch arrow-key chooser: both cards whole, nothing clipped."""
    assert window.pages.currentWidget() is window.arrow_page
    cards = []
    for mode, card in window.arrow_cards.items():
        for item in card.findChildren(QLabel) + card.findChildren(QPushButton):
            text = item.text().split("\n")
            assert all(item.fontMetrics().horizontalAdvance(line) <= item.contentsRect().width() for line in text), item.text()
            assert card.rect().contains(item.geometry()), item.text()
        cards.append({"mode": mode, "height": card.height()})
    assert len({card["height"] for card in cards}) == 1, cards
    return {**check_header(window), "cards": cards}
