import re

import version


def test_version_is_semantic():
    assert re.fullmatch(r"\d+\.\d+\.\d+", version.__version__)


def test_window_title_and_about_show_the_version(monkeypatch):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox
    from gui import main_window

    QApplication.instance() or QApplication([])
    w = main_window.MainWindow()
    assert version.__version__ in w.windowTitle()

    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: shown.append(box.text()))
    w._show_about()
    assert shown and version.__version__ in shown[0]
