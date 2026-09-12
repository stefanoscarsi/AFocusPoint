"""
main_window.py
--------------
Finestra principale: menu per aprire un CR3, visualizzatore immagine con
overlay AF a sinistra (con zoom/pan), pannello informazioni a destra.
"""

from __future__ import annotations

from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import QPoint, Qt
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

from core import exif_reader, frame_builder
from gui import zoom as zoom_utils
from gui.info_panel import InfoPanel


class _ZoomableImageLabel(QLabel):
    """A QLabel that forwards wheel/mouse events to the owning window, which
    holds the actual zoom/pan state (the label itself is just the paint
    surface)."""

    def __init__(self, window: "MainWindow"):
        super().__init__()
        self._window = window

    def wheelEvent(self, event) -> None:  # noqa: N802 - override Qt
        self._window._on_wheel(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - override Qt
        self._window._reset_zoom()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - override Qt
        if event.button() == Qt.LeftButton:
            self._window._on_drag_start(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - override Qt
        if event.buttons() & Qt.LeftButton:
            self._window._on_drag_move(event.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - override Qt
        if event.button() == Qt.LeftButton:
            self._window._on_drag_end()
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AFocusPoint — Punto di messa a fuoco")
        self.resize(1200, 800)

        self._current_pixmap: QPixmap | None = None  # sempre a piena risoluzione
        self._zoom: float = zoom_utils.MIN_ZOOM
        self._drag_start: QPoint | None = None
        self._drag_start_scroll: tuple[int, int] = (0, 0)

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

        self.image_label = _ZoomableImageLabel(self)
        self.image_label.setText("Apri un file CR3 (File → Apri CR3...)")
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
        # dimensione, cosi' resta coerente con lo zoom corrente.
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
            result = frame_builder.build_frame(path)

            self._reset_zoom_state()
            self._update_cursor()
            self._show_image(result.image)
            self.info_panel.update_data(result)
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
        # schermo e' invece una copia ridotta/ingrandita in base allo zoom
        # corrente (calcolata in _update_displayed_pixmap).
        qt_image = ImageQt(pil_image)
        self._current_pixmap = QPixmap.fromImage(qt_image)
        self._update_displayed_pixmap()

    def _update_displayed_pixmap(self) -> None:
        if self._current_pixmap is None or self._current_pixmap.isNull():
            return
        viewport_size = self.image_scroll.viewport().size()
        if viewport_size.width() <= 0 or viewport_size.height() <= 0:
            return

        if self._zoom <= zoom_utils.MIN_ZOOM:
            # Vista adattata (comportamento originale): la QScrollArea
            # ridimensiona da sola il contenuto, niente scrollbar necessarie.
            self.image_scroll.setWidgetResizable(True)
            scaled = self._current_pixmap.scaled(
                viewport_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        else:
            # Zoomati: disabilitiamo il resize automatico cosi' la label puo'
            # essere piu' grande del viewport, e la QScrollArea mostra le
            # scrollbar per scorrere/panoramicare.
            self.image_scroll.setWidgetResizable(False)
            fit_scale = zoom_utils.compute_fit_scale(
                (self._current_pixmap.width(), self._current_pixmap.height()),
                (viewport_size.width(), viewport_size.height()),
            )
            scale = fit_scale * self._zoom
            target_w = max(1, int(self._current_pixmap.width() * scale))
            target_h = max(1, int(self._current_pixmap.height() * scale))
            scaled = self._current_pixmap.scaled(
                target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())

    # ------------------------------------------------------------------
    # Zoom / pan
    # ------------------------------------------------------------------

    def _reset_zoom_state(self) -> None:
        self._zoom = zoom_utils.MIN_ZOOM
        self._drag_start = None

    def _reset_zoom(self) -> None:
        self._reset_zoom_state()
        self._update_displayed_pixmap()
        self._update_cursor()

    def _update_cursor(self) -> None:
        # A "grab hand" is the standard affordance for "click and drag to
        # pan" -- without it, dragging a zoomed photo only via the
        # scrollbars is easy to miss entirely. Shown only once there's
        # actually something to pan into (i.e. past the fit-to-screen zoom).
        if self._zoom > zoom_utils.MIN_ZOOM:
            self.image_label.setCursor(Qt.OpenHandCursor)
        else:
            self.image_label.unsetCursor()

    def _on_wheel(self, event) -> None:
        if self._current_pixmap is None:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = zoom_utils.ZOOM_STEP if delta > 0 else (1 / zoom_utils.ZOOM_STEP)
        self._zoom_at(event.position().toPoint(), factor)

    def _zoom_at(self, viewport_pos: QPoint, factor: float) -> None:
        new_zoom = zoom_utils.clamp_zoom(self._zoom * factor)
        if new_zoom == self._zoom:
            return

        old_pixmap = self.image_label.pixmap()
        hbar = self.image_scroll.horizontalScrollBar()
        vbar = self.image_scroll.verticalScrollBar()

        # The image point currently under the cursor, expressed as a
        # fraction of the (pre-zoom) displayed pixmap -- kept fixed on
        # screen across the zoom change so zooming feels anchored to the
        # cursor rather than always recentring on the photo's middle.
        if old_pixmap is not None and not old_pixmap.isNull():
            old_x = hbar.value() + viewport_pos.x()
            old_y = vbar.value() + viewport_pos.y()
            frac_x = old_x / max(old_pixmap.width(), 1)
            frac_y = old_y / max(old_pixmap.height(), 1)
        else:
            frac_x = frac_y = 0.5

        self._zoom = new_zoom
        self._update_displayed_pixmap()
        self._update_cursor()

        new_pixmap = self.image_label.pixmap()
        if new_pixmap is not None and not new_pixmap.isNull():
            new_x = frac_x * new_pixmap.width() - viewport_pos.x()
            new_y = frac_y * new_pixmap.height() - viewport_pos.y()
            hbar.setValue(int(new_x))
            vbar.setValue(int(new_y))

    def _on_drag_start(self, pos: QPoint) -> None:
        self._drag_start = pos
        self._drag_start_scroll = (
            self.image_scroll.horizontalScrollBar().value(),
            self.image_scroll.verticalScrollBar().value(),
        )
        if self._zoom > zoom_utils.MIN_ZOOM:
            # "Grabbing" feedback for the duration of the drag, mirroring
            # the open/closed hand convention from Photoshop/Lightroom's
            # pan tool.
            self.image_label.setCursor(Qt.ClosedHandCursor)

    def _on_drag_move(self, pos: QPoint) -> None:
        if self._zoom <= zoom_utils.MIN_ZOOM or self._drag_start is None:
            return  # the whole photo already fits -- nothing to pan into
        dx = pos.x() - self._drag_start.x()
        dy = pos.y() - self._drag_start.y()
        self.image_scroll.horizontalScrollBar().setValue(self._drag_start_scroll[0] - dx)
        self.image_scroll.verticalScrollBar().setValue(self._drag_start_scroll[1] - dy)

    def _on_drag_end(self) -> None:
        self._drag_start = None
        self._update_cursor()
