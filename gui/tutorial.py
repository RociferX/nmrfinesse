"""The usage tutorial: the document window opened from the Help menu (Qt layer).

The tutorial text is **shipped data** (``nmrfinesse_data/tutorial/{zh,en}.md``) and follows the
same language rule as the interface strings: the file for the current language is loaded at run
time, and if that language has no text the other one is used. Why not ``ui_support/locales``:
that is the lookup table for **individual** short strings (keyed by the English source), while
the tutorial is a whole document (a dozen sections, lists and examples) - keeping it in the data
package means it ships with the program and can be switched as a document.

Resources are located through ``core.app_paths.resource_path``: in a source checkout it lives
under ``nmrfinesse_data/``, in an installed copy under ``site-packages/nmrfinesse_data/`` and in
a
frozen build under ``_MEIPASS/nmrfinesse_data/`` - the same relative path in all three shapes
(see packaging/linux/NMRFinesse.spec and docs/packaging.md).
"""

from __future__ import annotations

from pathlib import Path

from qtcompat.QtCore import Qt
from qtcompat.QtGui import QFont, QPalette, QTextCharFormat, QTextCursor
from qtcompat.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QSplitter,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.app_paths import resource_path
from ui_support.i18n import get_language, tr

TUTORIAL_DIR = "tutorial"

TUTORIAL_LANGUAGES: tuple[str, ...] = ("zh", "en")


def tutorial_path(language: str | None = None) -> Path | None:
    'Path of the tutorial file; falls back to the other language, ``None`` if neither exists.'
    code = str(language or get_language() or "").strip().lower()
    for candidate in (code, *(item for item in TUTORIAL_LANGUAGES if item != code)):
        if not candidate:
            continue
        path = resource_path(f"{TUTORIAL_DIR}/{candidate}.md")
        if path.is_file():
            return path
    return None


def load_tutorial_text(language: str | None = None) -> str:
    'Read the tutorial text (UTF-8); empty string when it is missing or unreadable.'
    path = tutorial_path(language)
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


class TutorialDialog(QDialog):
    """The usage tutorial dialog: markdown text plus a close button.

    A plain ``QDialog`` (not the Popup used by ``InfoDialog``): the tutorial is long, so it has
    to be resizable, scrollable and selectable, and clicking outside must not close it. Centring
    is handled by the application-wide filter (``install_dialog_centering`` in gui/dialogs.py).
    """

    def __init__(self, parent: QWidget | None = None, language: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("NMRFinesse usage tutorial"))
        self.resize(1120, 760)
        layout = QVBoxLayout(self)
        self.contents = QTreeWidget()
        self.contents.setHeaderHidden(True)
        self.contents.setMinimumWidth(180)
        self.contents.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.contents.itemClicked.connect(self._navigate)
        self.contents.itemActivated.connect(self._navigate)
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        heading = QLabel(tr("Contents"))
        heading.setObjectName("SectionTitle")
        sidebar_layout.addWidget(heading)
        sidebar_layout.addWidget(self.contents, 1)
        self.view = QTextBrowser()
        self.view.document().setDocumentMargin(14)
        self.view.setOpenExternalLinks(True)
        text = load_tutorial_text(language)
        if text:
            self.view.setMarkdown(text)
        else:
            self.view.setPlainText(
                tr("The tutorial document is missing from this installation.")
            )
        self._build_contents()
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(sidebar)
        self.splitter.addWidget(self.view)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([250, 850])
        layout.addWidget(self.splitter, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(tr("Close"))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


    def _build_contents(self) -> None:
        """Apply heading hierarchy and link the contents to document anchors."""
        document = self.view.document()
        base_size = self.view.font().pointSizeF()
        if base_size <= 0:
            base_size = 10
        block = document.begin()
        parent = None
        number = 0
        while block.isValid():
            level = block.blockFormat().headingLevel()
            if 1 <= level <= 3:
                anchor = f"tutorial-section-{number}"
                number += 1
                cursor = QTextCursor(block)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock,
                                    QTextCursor.MoveMode.KeepAnchor)
                style = QTextCharFormat()
                style.setFontPointSize(base_size + {1: 8, 2: 4, 3: 2}[level])
                style.setFontWeight(QFont.Weight.Bold if level < 3 else QFont.Weight.DemiBold)
                style.setForeground(self.view.palette().color(QPalette.ColorRole.Text))
                style.setAnchor(True)
                style.setAnchorNames([anchor])
                cursor.mergeCharFormat(style)
                paragraph = block.blockFormat()
                paragraph.setTopMargin(16 if level < 3 else 10)
                paragraph.setBottomMargin(8 if level < 3 else 4)
                if level == 2:
                    paragraph.setBackground(
                        self.view.palette().color(QPalette.ColorRole.AlternateBase))
                cursor.setBlockFormat(paragraph)
                if level == 2:
                    parent = QTreeWidgetItem(self.contents, [block.text()])
                    item = parent
                elif level == 3:
                    item = QTreeWidgetItem(parent or self.contents, [block.text()])
                else:
                    block = block.next()
                    continue
                item.setData(0, Qt.ItemDataRole.UserRole, anchor)
                item.setToolTip(0, block.text())
            block = block.next()
        if self.contents.topLevelItemCount():
            self.contents.topLevelItem(0).setExpanded(True)

    def _navigate(self, item, _column=0) -> None:
        anchor = item.data(0, Qt.ItemDataRole.UserRole)
        if anchor:
            self.view.scrollToAnchor(anchor)
