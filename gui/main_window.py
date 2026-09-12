"""
main_window.py
--------------
Finestra principale: menu per aprire un CR3, visualizzatore immagine con
overlay AF a sinistra, pannello informazioni a destra.
"""

from __future__ import annotations

from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QWidget,
)

from core import af_parser, exif_reader, overlay_renderer, preview_extractor
from gui.info_panel import InfoPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Canon AF Point Viewer — Punto di messa a fuoco")
        self.resize(1200, 800)

        self._current_pixmap: QPixmap | None = None  # sempre a piena risoluzione

        self._build_menu()
        self._build_layout()

        self._check_exiftool_on_startup()

    # ------------------------------------------------------------------
    # Costruzione interfaccia
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        open_action = QAction("Apri CR3...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file_dialog)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(open_action)

    def _build_layout(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)

        self.image_label = QLabel("Apri un file CR3 (File → Apri CR3...)")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 400)

        self.image_scroll = QScrollArea()
        self.image_scroll.setWidget(self.image_label)
        self.image_scroll.setWidgetResizable(True)

        self.info_panel = InfoPanel()
        self.info_panel.setFixedWidth(320)

        layout.addWidget(self.image_scroll, stretch=3)
        layout.addWidget(self.info_panel, stretch=1)

        self.setCentralWidget(central)

    def _check_exiftool_on_startup(self) -> None:
        try:
            version = exif_reader.check_exiftool_available()
            self.statusBar().showMessage(f"ExifTool {version} pronto.")
        except exif_reader.ExifToolNotFoundError as exc:
            QMessageBox.critical(self, "ExifTool non trovato", str(exc))

    def resizeEvent(self, event) -> None:  # noqa: N802 - override Qt
        super().resizeEvent(event)
        # Ridisegna l'immagine adattata ogni volta che la finestra cambia
        # dimensione, cosi' resta sempre visibile tutta intera.
        self._update_displayed_pixmap()

    # ------------------------------------------------------------------
    # Logica applicativa
    # ------------------------------------------------------------------

    def open_file_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Apri file CR3", "", "Canon RAW (*.cr3 *.CR3);;Tutti i file (*)"
        )
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path: str) -> None:
        path = Path(file_path)
        try:
            metadata = exif_reader.read_all_metadata(path)
            shooting = af_parser.get_shooting_data(metadata["formatted"])
            af_data = af_parser.get_af_data_structured(metadata["raw"], metadata["formatted"])

            preview = preview_extractor.extract_preview_image(path)
            preview_with_overlay = overlay_renderer.draw_af_overlay(preview, af_data)

            self._show_image(preview_with_overlay)
            self.info_panel.update_data(shooting, af_data)
            self.statusBar().showMessage(f"Caricato: {path.name}")

        except Exception as exc:  # noqa: BLE001 - vogliamo mostrare l'errore, non crashare
            QMessageBox.warning(
                self,
                "Errore nel caricamento del file",
                f"Non sono riuscito a elaborare '{path.name}':\n\n{exc}",
            )

    def _show_image(self, pil_image) -> None:
        # Conserviamo SEMPRE il pixmap a piena risoluzione: e' quello su cui
        # e' stato disegnato l'overlay AF in scala 1:1. Cio' che mostriamo a
        # schermo e' invece una copia ridotta per adattarsi alla finestra
        # (calcolata in _update_displayed_pixmap), cosi' l'immagine intera è
        # sempre visibile senza dover scorrere.
        qt_image = ImageQt(pil_image)
        self._current_pixmap = QPixmap.fromImage(qt_image)
        self._update_displayed_pixmap()

    def _update_displayed_pixmap(self) -> None:
        if self._current_pixmap is None or self._current_pixmap.isNull():
            return
        viewport_size = self.image_scroll.viewport().size()
        if viewport_size.width() <= 0 or viewport_size.height() <= 0:
            return
        scaled = self._current_pixmap.scaled(
            viewport_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)
