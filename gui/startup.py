"""In-window startup status until the interactive workspace is ready."""

from qtcompat.QtCore import QEventLoop, QPropertyAnimation, Qt
from qtcompat.QtWidgets import QApplication, QLabel, QProgressBar, QVBoxLayout, QWidget

from core import __version__
from ui_support.i18n import tr


class StartupScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"NMRFinesse {__version__}")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel(f"NMRFinesse {__version__}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        self.status = QLabel(tr("Loading…"))
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedWidth(360)
        layout.addWidget(self.progress, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_status(self, text, percent):
        self.status.setText(text)
        if self.progress.value() == percent:
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            return
        # Imports run on the GUI thread. Animate between completed stages.
        animation = QPropertyAnimation(self.progress, b"value")
        animation.setDuration(96)
        animation.setStartValue(self.progress.value())
        animation.setEndValue(percent)
        loop = QEventLoop()
        animation.finished.connect(loop.quit)
        animation.start()
        loop.exec(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        self.progress.repaint()


def show_startup(window, prepare):
    """Use the actual main window for loading so its frame and geometry stay fixed."""
    workspace = window.takeCentralWidget()
    loading = StartupScreen(window)
    menu_hidden = window.menuBar().isHidden()
    status_hidden = window.statusBar().isHidden()
    was_enabled = window.isEnabled()
    window.setCentralWidget(loading)
    window.menuBar().hide()
    window.statusBar().hide()
    window.setEnabled(False)
    window.show()
    try:
        loading.set_status(tr("Loading…"), 0)
        prepare(loading.set_status)
    finally:
        ready_size = window.size()
        window.takeCentralWidget()
        window.setCentralWidget(workspace)
        window.menuBar().setVisible(not menu_hidden)
        window.statusBar().setVisible(not status_hidden)
        window.setEnabled(was_enabled)
        window.resize(ready_size)
        loading.deleteLater()
