"""
main_window.py
--------------
Finestra principale: menu per aprire un CR3, visualizzatore immagine con
overlay AF a sinistra (con zoom/pan), pannello informazioni a destra.

The viewer is a QGraphicsView/QGraphicsScene, not a QLabel in a QScrollArea:
panning a QLabel-based view means re-rendering a large QPixmap on every
scroll step, which gets visibly jerky on a several-thousand-pixel-wide RAW
preview. QGraphicsView instead keeps the original pixmap untouched and pans
by translating the view transform -- Qt's own optimized path for exactly
this -- and its built-in ScrollHandDrag mode gives smooth click-drag
panning with the open/closed hand cursor for free.
"""

from __future__ import annotations

from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QAction, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QWidget,
)

from core import exif_reader, frame_builder
from gui import zoom as zoom_utils
from gui.info_panel import InfoPanel


class _ZoomableGraphicsView(QGraphicsView):
    """Forwards wheel/double-click events to the owning window, which holds
    the actual zoom state. Panning itself needs no wiring at all: ScrollHandDrag
    is Qt's built-in drag-to-pan mode."""

    def __init__(self, window: "MainWindow"):
        super().__init__()
        self._window = window
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setDragMode(QGraphicsView.NoDrag)
        # MinimalViewportUpdate (the default) spends time computing exactly
        # which small region changed on every scroll step; with one item
        # that fills the whole viewport, that bookkeeping is pure overhead
        # since virtually the whole viewport is "dirty" on every pan step
        # anyway -- FullViewportUpdate skips it.
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

    def wheelEvent(self, event) -> None:  # noqa: N802 - override Qt
        self._window._on_wheel(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - override Qt
        self._window._reset_zoom()
        super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AFocusPoint — Punto di messa a fuoco")
        self.resize(1200, 800)

        self._zoom: float = zoom_utils.MIN_ZOOM
        # Scale fitInView last applied, i.e. what zoom=1.0 means for the
        # current photo -- needed to cap zoom relative to native resolution
        # (see gui/zoom.py) and to turn a relative zoom step into an
        # absolute QGraphicsView transform.
        self._base_scale: float = 1.0

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

        self.scene = QGraphicsScene()
        self.pixmap_item = QGraphicsPixmapItem()
        # Caches the item's rendered (bilinear-interpolated) pixels in
        # device coordinates. Panning only translates the view -- it
        # doesn't change the item's transform relative to the viewport --
        # so Qt can blit this cache instead of re-interpolating the full
        # multi-megapixel source on every mouse-move step, which is what
        # made dragging feel heavy/sluggish on a large RAW preview.
        self.pixmap_item.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.scene.addItem(self.pixmap_item)

        self.image_view = _ZoomableGraphicsView(self)
        self.image_view.setScene(self.scene)

        self.info_panel = InfoPanel()
        self.info_panel.setFixedWidth(320)

        layout.addWidget(self.image_view, stretch=3)
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
        # Only re-fit automatically while already at the fit-to-view zoom --
        # if the user has zoomed in, resizing the window shouldn't yank
        # their view back to "whole photo".
        if self._zoom <= zoom_utils.MIN_ZOOM:
            self._fit_to_view()

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
        qt_image = ImageQt(pil_image)
        pixmap = QPixmap.fromImage(qt_image)
        self.pixmap_item.setPixmap(pixmap)
        self.scene.setSceneRect(QRectF(pixmap.rect()))
        self._fit_to_view()

    def _fit_to_view(self) -> None:
        self.image_view.resetTransform()
        if not self.pixmap_item.pixmap().isNull():
            self.image_view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self._base_scale = self.image_view.transform().m11()
        self._zoom = zoom_utils.MIN_ZOOM
        self._update_drag_mode()

    # ------------------------------------------------------------------
    # Zoom / pan
    # ------------------------------------------------------------------

    def _update_drag_mode(self) -> None:
        # ScrollHandDrag is what gives the open/closed hand cursor and the
        # actual click-drag panning -- both for free from Qt -- but only
        # once there's something to pan into.
        self.image_view.setDragMode(
            QGraphicsView.ScrollHandDrag if self._zoom > zoom_utils.MIN_ZOOM else QGraphicsView.NoDrag
        )

    def _reset_zoom(self) -> None:
        self._fit_to_view()

    def _on_wheel(self, event) -> None:
        if self.pixmap_item.pixmap().isNull():
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = zoom_utils.ZOOM_STEP if delta > 0 else (1 / zoom_utils.ZOOM_STEP)

        max_zoom = zoom_utils.max_zoom_for_base_scale(self._base_scale)
        new_zoom = min(max(self._zoom * factor, zoom_utils.MIN_ZOOM), max_zoom)
        if new_zoom == self._zoom:
            return

        # QGraphicsView.scale() multiplies the CURRENT transform, so only
        # the relative step is needed -- AnchorUnderMouse (set in
        # _ZoomableGraphicsView) keeps the point under the cursor fixed on
        # screen across the change.
        step = new_zoom / self._zoom
        self._zoom = new_zoom
        self.image_view.scale(step, step)
        self._update_drag_mode()
