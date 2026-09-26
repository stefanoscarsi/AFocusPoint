"""EXIF values and error messages come from the opened file: they must be
shown as text, never interpreted as HTML by Qt."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from gui import info_panel, main_window  # noqa: E402


def test_info_panel_escapes_exif_values():
    row = info_panel._row("Obiettivo", "<b>finto</b> & co")
    assert "&lt;b&gt;finto&lt;/b&gt; &amp; co" in row
    assert row.startswith("<b>Obiettivo:</b>")


def test_error_dialog_shows_plain_text(monkeypatch):
    QApplication.instance() or QApplication([])
    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: shown.append((box.textFormat(), box.text())))

    main_window._show_message(None, QMessageBox.Warning, "Errore", "<b>foto</b>.CR3")

    assert shown == [(Qt.PlainText, "<b>foto</b>.CR3")]
