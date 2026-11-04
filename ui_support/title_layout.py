"""Width-aware display of original title lines without changing stored text."""

from qtcompat.QtCore import QEvent, QRect, QSize, Qt
from qtcompat.QtGui import QFontMetrics
from qtcompat.QtWidgets import QApplication, QLabel, QToolTip

from ui_support.spectrum_metadata import spectrum_tooltip as _spectrum_tooltip


def title_rows(text, width, measure):
    """Pack original lines with separators, breaking between original lines first."""
    rows = []
    current = ''
    for part in text.splitlines():
        part = part.strip()
        if not part:
            continue
        joined = f'{current} | {part}' if current else part
        if current and measure(joined) > width:
            rows.append(current)
            current = part
        else:
            current = joined
    if current:
        rows.append(current)
    return rows


def tooltip_title(text):
    """Use the tooltip font and screen width to join short original title lines."""
    app = QApplication.instance()
    if app is None:
        return text
    screen = app.primaryScreen()
    width = min(600, screen.availableGeometry().width() - 80) if screen else 600
    metrics = QFontMetrics(QToolTip.font())
    width = max(80, width - metrics.horizontalAdvance('Title: '))
    return '\n'.join(title_rows(text, width, metrics.horizontalAdvance))


def spectrum_tooltip(path, manager=None):
    return _spectrum_tooltip(path, manager, title_formatter=tooltip_title)


class TitleLabel(QLabel):
    """Reflow a title from its original lines when the available width changes."""

    def __init__(self, title, parent=None):
        super().__init__('', parent)
        self.original_title = title
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self._reflow()

    def natural_width(self):
        text = ' | '.join(self.original_title.splitlines())
        return self.fontMetrics().horizontalAdvance(text) + 2

    def display_text(self, width):
        return '\n'.join(title_rows(
            self.original_title, max(1, width), self.fontMetrics().horizontalAdvance))

    def heightForWidth(self, width):
        return max(self.fontMetrics().height(), self.fontMetrics().boundingRect(
            QRect(0, 0, max(1, width), 100000), Qt.TextFlag.TextWordWrap,
            self.display_text(width)).height())

    def sizeHint(self):
        return QSize(self.natural_width(), self.fontMetrics().height())

    def minimumSizeHint(self):
        return QSize(0, self.fontMetrics().height())

    def _reflow(self):
        text = self.display_text(self.contentsRect().width())
        if self.text() != text:
            self.setText(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow()

    def changeEvent(self, event):
        super().changeEvent(event)
        if (hasattr(self, 'original_title')
                and event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange)):
            self._reflow()
