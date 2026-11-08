"""GUI usage tutorial: the tutorial document opened from the Help menu (2026-09-22, user request).

It guards three things: the tutorial is present and readable in both languages; the names it
uses
come from the same source as the real interface text (the four pipeline steps, the two Tools
menu
items, software settings); and the first Help menu item really carries the entry and opens the
tutorial dialog. The tutorial body is maintained by hand, so this only guards against drifting
apart when the interface is renamed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from qtcompat.QtWidgets import QApplication, QTextBrowser

from core.app_paths import resource_path
from gui.main_window import MainWindow
from gui.pipeline_panel import STEP_LABEL
from gui.tutorial import (
    TUTORIAL_LANGUAGES,
    TutorialDialog,
    load_tutorial_text,
    tutorial_path,
)
from ui_support.i18n import get_language, load_catalogue, tr

REPO_ROOT = Path(__file__).resolve().parents[1]




def _plain(label: str) -> str:
    """Strip the ellipsis from menu item text (the tutorial writes the name, not the full menu
    label).
    """
    return label.rstrip(". ").strip()


def _mentions(document: str, label: str) -> bool:
    """Whether the tutorial mentions this name; case-insensitive (a name inside a sentence may
    start
    lowercase).
    """
    return label.lower() in document.lower()


def test_both_languages_ship_a_tutorial_document() -> None:
    for language in TUTORIAL_LANGUAGES:
        path = resource_path(f"tutorial/{language}.md")
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert text.startswith("# "), language
        assert text.count("\n## ") >= 8, language


def test_tutorial_falls_back_to_the_other_language() -> None:
    assert tutorial_path("zh").name == "zh.md"
    assert tutorial_path("en").name == "en.md"

    assert tutorial_path("fr").is_file()
    assert load_tutorial_text("fr") == load_tutorial_text(tutorial_path("fr").stem)


def test_tutorial_uses_the_names_the_interface_shows() -> None:
    """Four steps + two Tools items + software settings: the tutorial and the interface must use
    the
    same names (renaming later turns this red).
    """
    english = load_tutorial_text("en")
    chinese = load_tutorial_text("zh")
    catalogue = load_catalogue("zh")
    to_english = {value: key for key, value in catalogue.items()}
    fixed = (
        "Software settings",
        "Data quality inspection...",
        "spectrum quality assessment...",
        "Remove abnormal FIDs and export NUS…",
        "Export UCSF files…",
    )
    for label in (*STEP_LABEL.values(), *fixed):
        source = to_english.get(label, label)
        assert _mentions(english, _plain(source)), source
        assert _mentions(chinese, _plain(catalogue.get(source, source))), source


def test_tutorial_strings_are_translated() -> None:
    """Newly added interface text must have a Chinese counterpart, otherwise the Chinese interface
    would show English.
    """
    catalogue = load_catalogue("zh")
    for key in (
        "Usage tutorial...",
        "NMRFinesse usage tutorial",
        "The tutorial document is missing from this installation.",
    ):
        assert catalogue.get(key), key


def test_tutorial_dialog_renders_the_document(qapp: QApplication) -> None:
    'The requested language loads that document and really renders it into the QTextBrowser.'
    dialog = TutorialDialog(None, language="en")
    try:
        browser = dialog.findChild(QTextBrowser)
        assert browser is not None
        rendered = browser.toPlainText()
        assert "NMRFinesse usage tutorial" in rendered
        assert browser.openExternalLinks()
        assert "Generate FID" in rendered
    finally:
        dialog.close()


def test_tutorial_dialog_survives_a_missing_document(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An installed copy that somehow lacks the tutorial data shows a one-line hint -- never an
    empty window and never an exception.
    """
    monkeypatch.setattr("gui.tutorial.load_tutorial_text", lambda language=None: "")
    dialog = TutorialDialog(None, language="zh")
    try:
        browser = dialog.findChild(QTextBrowser)
        assert browser is not None
        assert browser.toPlainText().strip()
    finally:
        dialog.close()


def test_help_menu_opens_the_tutorial(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first item of the Help menu (the last entry) is the usage tutorial; clicking it opens
    the
    tutorial dialog.
    """
    opened: list[object] = []

    class _Recorder:
        """Stand-in: records that it was opened, avoiding a real modal window that would hang the
        test.
        """

        def __init__(self, parent=None, language=None) -> None:
            opened.append(parent)

        def exec(self) -> int:
            return 0

    monkeypatch.setattr("gui.main_window.TutorialDialog", _Recorder)
    window = MainWindow()
    try:
        bar_menus = [action.menu() for action in window.menuBar().actions()]
        assert window.settings_action.menu() is None
        help_menu = bar_menus[-1]
        tutorial_action = help_menu.actions()[0]
        assert tutorial_action.text() == tr("Usage tutorial...")
        tutorial_action.trigger()
        assert opened == [window]
    finally:
        window.close()


def test_both_tutorial_documents_share_one_section_structure() -> None:
    """The two tutorials have a one-to-one section structure (only the language differs): this
    prevents editing the Chinese one and forgetting the English one.
    """
    zh = load_tutorial_text("zh")
    en = load_tutorial_text("en")
    zh_heads = [line for line in zh.splitlines() if line.startswith("#")]
    en_heads = [line for line in en.splitlines() if line.startswith("#")]
    assert len(zh_heads) == len(en_heads), (len(zh_heads), len(en_heads))
    assert [h.count("#") for h in zh_heads] == [h.count("#") for h in en_heads]


@pytest.mark.parametrize("language", ("en", "zh"))
def test_about_shows_running_versions_and_project_resources(qapp, language) -> None:
    from qtcompat.QtWidgets import QLabel

    from core.version import software_version
    from gui.dialogs import AboutDialog
    from nmrfinesse_api.session import API_VERSION
    from ui_support.i18n import set_language

    previous = get_language()
    set_language(language)
    dialog = AboutDialog()
    try:
        assert any(software_version() in label.text() for label in dialog.findChildren(QLabel))
        text = dialog.view.toPlainText()
        assert API_VERSION in text
        assert "2026" in text and "Xuanfeng Li" in text
        assert "Apache-2.0" in text and "LGPL-3.0" in text
        assert "Four columns" not in text
        html = dialog.view.toHtml()
        for url in (
            "https://github.com/RociferX/nmrfinesse",
            "https://github.com/RociferX/nmrfinesse/issues",
            "https://github.com/RociferX/nmrfinesse/releases",
            "https://doi.org/10.5281/zenodo.22909415",
        ):
            assert f'href="{url}"' in html
        assert dialog.view.openExternalLinks()
    finally:
        dialog.close()
        set_language(previous)


def test_about_action_opens_about_dialog(qapp, monkeypatch) -> None:
    opened = []

    class Recorder:
        def __init__(self, parent):
            opened.append(parent)

        def exec(self):
            return 0

    monkeypatch.setattr("gui.main_window.AboutDialog", Recorder)
    window = MainWindow()
    try:
        window.menuBar().actions()[-1].menu().actions()[-1].trigger()
        assert opened == [window]
    finally:
        window.close()



def test_tutorial_contents_navigates_and_headings_have_distinct_levels(qapp):
    from qtcompat.QtCore import Qt
    from qtcompat.QtTest import QTest

    dialog = TutorialDialog(language='en')
    dialog.resize(1000, 650)
    dialog.show()
    QTest.qWait(30)
    assert dialog.contents.topLevelItemCount() == 9
    assert dialog.contents.topLevelItem(0).childCount() == 2
    target = dialog.contents.topLevelItem(8)
    dialog.contents.scrollToItem(target)
    QTest.mouseClick(dialog.contents.viewport(), Qt.MouseButton.LeftButton,
                    pos=dialog.contents.visualItemRect(target).center())
    QTest.qWait(30)
    assert dialog.view.verticalScrollBar().value() > 0
    sizes = {}
    block = dialog.view.document().begin()
    while block.isValid():
        level = block.blockFormat().headingLevel()
        if level in (1, 2, 3):
            sizes.setdefault(level, block.begin().fragment().charFormat().fontPointSize())
        block = block.next()
    assert sizes[1] > sizes[2] > sizes[3] > 0
    dialog.close()
